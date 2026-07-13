"""OpenAI 兼容 Provider（design D3 多模型备选 / D34 摘要模型可指）。

用 httpx 打**任意** OpenAI Chat Completions 兼容端点（智谱 GLM / 通义千问 / DeepSeek /
Moonshot / 本地 vLLM 等），不引入 openai SDK、**不绑定具体厂商**。``base_url`` /
``api_key`` / ``model`` 由 ``settings.openai_compatible_*`` 注入，三项齐配才启用。
compaction 摘要用 ``chat``（非流式）；token 计数字符估算（design.md:869）。

design.md:312 「Provider 层必须支持国内模型（**如** GLM）作为备选」——GLM 是举例，
本 Provider 把它泛化为「任意 OpenAI 兼容服务」，避免厂商锁定。
"""

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
        elif m.tool_calls:
            out.append(
                {
                    "role": "assistant",
                    "content": m.content or "",
                    "tool_calls": [
                        {
                            "id": tc["id"],
                            "type": "function",
                            "function": {
                                "name": tc["name"],
                                "arguments": tc.get("input", "{}"),
                            },
                        }
                        for tc in m.tool_calls
                    ],
                }
            )
        else:
            out.append({"role": m.role, "content": m.content or ""})
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
            resp.raise_for_status()
            data = resp.json()
        choice = data["choices"][0]["message"]
        text = choice.get("content") or ""
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
        # MVP：compaction 只依赖 chat；主模型切 OpenAI 兼容服务的流式留作后续
        raise NotImplementedError(
            "OpenAICompatibleProvider.stream 暂未实现；compaction 用 chat"
        )
        if False:  # pragma: no cover  - 保持 async generator 语义
            yield

    async def count_tokens(
        self, messages: list[Message], system: str | None = None
    ) -> Usage:
        # 字符估算（design.md:869：国内模型用 tokenizer 或字符估算）
        total = sum(len(m.content or "") // 4 for m in messages)
        total += len(system or "") // 4
        return Usage(input_tokens=total, output_tokens=0)
