"""Anthropic Claude Provider（design D3）。

基于 ``anthropic`` SDK 实现 ``Provider`` 接口。支持流式与非流式两种模式；token 计数
使用 SDK 内置 ``count_tokens``（精确）与粗估双模式，供上下文管理（D34）决策。

需 ``settings.anthropic_api_key`` 有效（非空）；否则初始化时记录告警。
支持 ``messages.count_tokens``（精确）与 ``len()//4`` 回退（provider 不可用时不阻塞）。
"""

import json
import logging
from collections.abc import AsyncIterator

import anthropic

from app.config import settings
from app.providers.base import (
    Message,
    Provider,
    StreamEvent,
    ToolDef,
    Usage,
)

log = logging.getLogger("providers.anthropic")

_DEFAULT_MODEL = "claude-sonnet-5-20250710"
_BLOCKED_ERR = "provider unavailable"
_FALLBACK_CTX = 200_000


def _to_anthropic_messages(messages: list[Message]) -> list[dict]:
    """按 Anthropic 消息协议转换，只保留 user/assistant（tool_result 在 system 或内联）。"""
    result = []
    for m in messages:
        if m.role == "tool_result":
            result.append({"role": "user", "content": [{"type": "tool_result", "tool_use_id": m.tool_call_id or "", "content": m.content or ""}]})
        elif m.tool_calls:
            result.append({"role": "assistant", "content": [{"type": "text", "text": m.content or ""}, *[{"type": "tool_use", "id": tc["id"], "name": tc["name"], "input": json.loads(tc.get("input", "{}"))} for tc in m.tool_calls]]})
        else:
            result.append({"role": m.role, "content": [{"type": "text", "text": m.content or ""}]})
    return result


def _to_tool_defs(tools: list[ToolDef] | None) -> list[dict] | None:
    if not tools:
        return None
    return [{"name": t.name, "description": t.description, "input_schema": t.input_schema} for t in tools]


def _parse_stream_event(event) -> StreamEvent | None:
    """Anthropic stream 事件 → StreamEvent。"""
    if event.type == "content_block_delta" and event.delta.type == "text_delta":
        return StreamEvent(type="text", text=event.delta.text)
    if event.type == "content_block_start" and event.content_block.type == "tool_use":
        return StreamEvent(type="tool_use_start", tool_name=event.content_block.name, tool_input=json.dumps(event.content_block.input))
    if event.type == "content_block_stop":
        return StreamEvent(type="tool_use_end")
    if event.type == "message_delta":
        usage = event.usage or getattr(event.delta, "usage", None) if hasattr(event, "delta") else None
        return StreamEvent(type="stop",
                           input_tokens=getattr(usage, "input_tokens", None) or 0,
                           output_tokens=getattr(usage, "output_tokens", None) or 0)
    if event.type == "message_start":
        usage = getattr(event.message, "usage", None)
        return StreamEvent(type="text", text="")
    return None


class AnthropicProvider(Provider):
    """Anthropic Claude Provider 实现。"""

    def __init__(self, api_key: str | None = None) -> None:
        key = api_key or settings.anthropic_api_key
        if not key:
            log.warning("anthropic_api_key 未设置; Provider 在 chat/stream 时会失败")
            self._available = False
            return
        self._available = True
        self._client = anthropic.AsyncAnthropic(api_key=key)
        self._model = getattr(settings, "anthropic_model", _DEFAULT_MODEL)
        self._ctx_window = _FALLBACK_CTX

    @property
    def context_window(self) -> int:
        return self._ctx_window

    @property
    def model(self) -> str:
        return self._model

    @property
    def name(self) -> str:
        return "anthropic"

    async def chat(
        self,
        messages: list[Message],
        tools: list[ToolDef] | None = None,
        system: str | None = None,
    ) -> tuple[list[Message], Usage]:
        if not self._available:
            raise RuntimeError(_BLOCKED_ERR)
        api_messages = _to_anthropic_messages(messages)
        api_tools = _to_tool_defs(tools)
        resp = await self._client.messages.create(
            model=self._model,
            max_tokens=4096,
            system=system or "",
            messages=api_messages,
            tools=api_tools or anthropic.NotGiven(),
        )
        usage = Usage(
            input_tokens=resp.usage.input_tokens,
            output_tokens=resp.usage.output_tokens,
            cache_read_input_tokens=getattr(resp.usage, "cache_read_input_tokens", 0) or 0,
            cache_creation_input_tokens=getattr(resp.usage, "cache_creation_input_tokens", 0) or 0,
        )
        assistant = Message(role="assistant", content="")
        tool_calls = []
        for block in resp.content:
            if block.type == "text":
                assistant.content = (assistant.content or "") + block.text
            elif block.type == "tool_use":
                tool_calls.append({"id": block.id, "name": block.name, "input": json.dumps(block.input)})
        assistant.tool_calls = tool_calls or None
        return [assistant], usage

    async def stream(
        self,
        messages: list[Message],
        tools: list[ToolDef] | None = None,
        system: str | None = None,
    ) -> AsyncIterator[StreamEvent]:
        if not self._available:
            raise RuntimeError(_BLOCKED_ERR)
        api_messages = _to_anthropic_messages(messages)
        api_tools = _to_tool_defs(tools)
        async with self._client.messages.stream(
            model=self._model,
            max_tokens=4096,
            system=system or "",
            messages=api_messages,
            tools=api_tools or anthropic.NotGiven(),
        ) as stream:
            async for event in stream:
                parsed = _parse_stream_event(event)
                if parsed:
                    yield parsed

    async def count_tokens(
        self, messages: list[Message], system: str | None = None
    ) -> Usage:
        if not self._available:
            total = sum(len(m.content or "") // 4 for m in messages) + len(system or "") // 4
            return Usage(input_tokens=total, output_tokens=0)
        api_messages = _to_anthropic_messages(messages)
        try:
            resp = await self._client.messages.count_tokens(
                model=self._model, messages=api_messages, system=system or "",
            )
            return Usage(input_tokens=resp.input_tokens, output_tokens=0)
        except Exception:
            raise
