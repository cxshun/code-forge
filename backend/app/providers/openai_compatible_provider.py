"""OpenAI 兼容 Provider（design D3 多模型备选 / D34 摘要模型可指）。

用 httpx 打**任意** OpenAI Chat Completions 兼容端点（智谱 GLM / 通义千问 / DeepSeek /
Moonshot / 本地 vLLM 等），不引入 openai SDK、**不绑定具体厂商**。``base_url`` /
``api_key`` / ``model`` 由 ``settings.openai_compatible_*`` 注入，三项齐配才启用。
compaction 摘要用 ``chat``（非流式）；token 计数字符估算（design.md:869）。

design.md:312 「Provider 层必须支持国内模型（**如** GLM）作为备选」——GLM 是举例，
本 Provider 把它泛化为「任意 OpenAI 兼容服务」，避免厂商锁定。
"""

import json
import logging
from collections.abc import AsyncIterator

import httpx

from app.config import settings
from app.providers.base import (
    Message,
    Provider,
    StreamEvent,
    ToolDef,
    Usage,
)

log = logging.getLogger("providers.openai_compatible")

_FALLBACK_CTX = 128_000
_BLOCKED_ERR = "provider unavailable"


def _to_openai_messages(messages: list[Message], system: str | None) -> list[dict]:
    """转 OpenAI chat 格式（system 单独置顶 + user/assistant/tool 交替）。"""
    out: list[dict] = []
    if system:
        out.append({"role": "system", "content": system})
    for m in messages:
        if m.role == "tool_result":
            out.append(
                {
                    "role": "tool",
                    "tool_call_id": m.tool_call_id or "",
                    "content": m.content or "",
                }
            )
        else:
            msg: dict = {"role": m.role, "content": m.content or ""}
            # thinking 模型（deepseek-v4-flash）的 reasoning_content 在多轮中必须回传给 API
            if m.role == "assistant" and m.reasoning:
                msg["reasoning_content"] = m.reasoning
            if m.tool_calls:
                msg["tool_calls"] = [
                    {
                        "id": tc["id"],
                        "type": "function",
                        "function": {
                            "name": tc["name"],
                            "arguments": tc.get("input", "{}"),
                        },
                    }
                    for tc in m.tool_calls
                ]
            out.append(msg)
    return out


def _to_openai_tools(tools: list[ToolDef] | None) -> list[dict] | None:
    if not tools:
        return None
    return [
        {
            "type": "function",
            "function": {
                "name": t.name,
                "description": t.description,
                "parameters": t.input_schema,
            },
        }
        for t in tools
    ]


class OpenAICompatibleProvider(Provider):
    """OpenAI 兼容协议 Provider（智谱/通义/DeepSeek/Moonshot 等通用，非厂商绑定）。"""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        context_window: int = _FALLBACK_CTX,
    ) -> None:
        key = api_key or settings.openai_compatible_api_key
        base = (base_url or settings.openai_compatible_base_url or "").rstrip("/")
        mdl = model or settings.openai_compatible_model
        self._ctx_window = context_window
        if not key or not base or not mdl:
            log.warning(
                "openai_compatible_* 未完整配置（需 api_key + base_url + model）；Provider 不可用"
            )
            self._available = False
            self._api_key = ""
            self._base_url = ""
            self._model = mdl or ""
            return
        self._available = True
        self._api_key = key
        self._base_url = base
        self._model = mdl

    @property
    def context_window(self) -> int:
        return self._ctx_window

    @property
    def model(self) -> str:
        return self._model

    @property
    def name(self) -> str:
        return "openai_compatible"

    async def chat(
        self,
        messages: list[Message],
        tools: list[ToolDef] | None = None,
        system: str | None = None,
    ) -> tuple[list[Message], Usage]:
        if not self._available:
            raise RuntimeError(_BLOCKED_ERR)
        payload: dict = {
            "model": self._model,
            "messages": _to_openai_messages(messages, system),
            "max_tokens": 4096,
        }
        openai_tools = _to_openai_tools(tools)
        if openai_tools:
            payload["tools"] = openai_tools
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                f"{self._base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self._api_key}"},
                json=payload,
            )
            if resp.status_code >= 400:
                log.error(
                    "openai_compatible chat %d (%s): %s",
                    resp.status_code,
                    self._model,
                    resp.text[:800],
                )
                resp.raise_for_status()
            data = resp.json()
        choice = data["choices"][0]["message"]
        reasoning = choice.get("reasoning_content")
        text = choice.get("content") or ""
        if reasoning:
            text = f"【思考过程】\n{reasoning}\n\n【回答】\n{text}"
        tool_calls = None
        raw_tc = choice.get("tool_calls")
        if raw_tc:
            tool_calls = [
                {
                    "id": tc["id"],
                    "name": tc["function"]["name"],
                    "input": tc["function"].get("arguments", "{}"),
                }
                for tc in raw_tc
            ]
        usage = data.get("usage", {})
        return [
            Message(role="assistant", content=text, tool_calls=tool_calls)
        ], Usage(
            input_tokens=usage.get("prompt_tokens", 0),
            output_tokens=usage.get("completion_tokens", 0),
        )

    async def stream(
        self,
        messages: list[Message],
        tools: list[ToolDef] | None = None,
        system: str | None = None,
    ) -> AsyncIterator[StreamEvent]:
        # OpenAI Chat Completions SSE 流式：text delta 实时 yield；tool_calls 分片累积，
        # 流末统一 emit（OpenAI 把一个 tool_call 的 arguments 拆多片传，需等完整再 yield）。
        # 支持 reasoning_content（DeepSeek 等模型的思考内容），累积后作为 text delta 发出。
        if not self._available:
            raise RuntimeError(_BLOCKED_ERR)
        payload: dict = {
            "model": self._model,
            "messages": _to_openai_messages(messages, system),
            "max_tokens": 4096,
            "stream": True,
        }
        openai_tools = _to_openai_tools(tools)
        if openai_tools:
            payload["tools"] = openai_tools
        # index -> {id, name, args}
        tc_buf: dict[int, dict] = {}
        usage_in = 0
        usage_out = 0
        async with httpx.AsyncClient(timeout=120) as client:
            async with client.stream(
                "POST",
                f"{self._base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self._api_key}"},
                json=payload,
            ) as resp:
                if resp.status_code >= 400:
                    err_body = await resp.aread()
                    log.error(
                        "openai_compatible stream %d (%s): %s",
                        resp.status_code,
                        self._model,
                        err_body.decode("utf-8", "ignore")[:800],
                    )
                    resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line or not line.startswith("data:"):
                        continue
                    data = line[len("data:") :].strip()
                    if data == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data)
                    except json.JSONDecodeError:
                        continue
                    u = chunk.get("usage")
                    if u:
                        usage_in = u.get("prompt_tokens", usage_in)
                        usage_out = u.get("completion_tokens", usage_out)
                    choices = chunk.get("choices") or []
                    if not choices:
                        continue
                    delta = choices[0].get("delta", {}) or {}
                    # DeepSeek thinking 模型的 reasoning_content：作为思考单独记录
                    # （多轮需回传 reasoning_content，由 Loop 累积到 Message.reasoning）
                    reasoning = delta.get("reasoning_content")
                    if reasoning:
                        yield StreamEvent(type="reasoning", reasoning=reasoning)
                    text = delta.get("content")
                    if text:
                        yield StreamEvent(type="text", text=text)
                    for tc in delta.get("tool_calls", []) or []:
                        idx = tc.get("index", 0)
                        buf = tc_buf.setdefault(idx, {"id": "", "name": "", "args": ""})
                        if tc.get("id"):
                            buf["id"] = tc["id"]
                        fn = tc.get("function") or {}
                        if fn.get("name"):
                            buf["name"] = fn["name"]
                        if fn.get("arguments"):
                            buf["args"] += fn["arguments"]
        # 流末统一 emit 工具调用（args 已累积完整）
        for buf in tc_buf.values():
            yield StreamEvent(
                type="tool_use_start",
                tool_name=buf["name"],
                tool_input=buf["args"],
            )
            yield StreamEvent(type="tool_use_end")
        yield StreamEvent(type="stop", input_tokens=usage_in, output_tokens=usage_out)

    async def count_tokens(
        self, messages: list[Message], system: str | None = None
    ) -> Usage:
        # 字符估算（design.md:869：国内模型用 tokenizer 或字符估算）
        total = sum(len(m.content or "") // 4 for m in messages)
        total += len(system or "") // 4
        return Usage(input_tokens=total, output_tokens=0)
