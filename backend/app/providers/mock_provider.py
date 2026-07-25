"""Mock LLM Provider（测试与开发用）。

返回预设回复 / echo / 模拟 tool_use，不调真实 LLM。供 Agent Loop 单测驱动（B5），
以及上下文管理（D34）的 clearing / compaction 测试 —— 用 mock 隔离 LLM 行为，专注
测试 Loop 逻辑与工具执行。
"""

import json
from collections.abc import AsyncIterator

from app.providers.base import (
    Message,
    Provider,
    StreamEvent,
    ToolDef,
    Usage,
)


class MockProvider(Provider):
    """Mock Provider，可配置预设回复。

    默认：echo 用户最后一条消息，无 tool_use。支持模拟工具调用（mock_tool_results）
    与多个回复轮回。
    """

    def __init__(
        self,
        *,
        mock_text: str | None = None,
        mock_tool_name: str | None = None,
        mock_tool_input: dict | None = None,
        context_window: int = 200000,
    ) -> None:
        self._mock_text = mock_text
        self._mock_tool_name = mock_tool_name
        self._mock_tool_input = mock_tool_input or {}
        self._ctx_window = context_window
        self._call_count = 0

    @property
    def context_window(self) -> int:
        return self._ctx_window

    @property
    def model(self) -> str:
        return "mock-model"

    @property
    def name(self) -> str:
        return "mock"

    async def chat(
        self,
        messages: list[Message],
        tools: list[ToolDef] | None = None,
        system: str | None = None,
        max_tokens: int | None = None,
    ) -> tuple[list[Message], Usage]:
        self._call_count += 1
        text = self._mock_text or self._echo(messages)
        tool_calls = None
        if self._mock_tool_name and self._call_count <= 2:
            tool_calls = [
                {
                    "id": f"mock_tool_{self._call_count}",
                    "name": self._mock_tool_name,
                    "input": json.dumps(self._mock_tool_input),
                }
            ]
        assistant = Message(role="assistant", content=text, tool_calls=tool_calls)
        usage = Usage(input_tokens=10, output_tokens=len(next((m.content for m in reversed(messages) if m.content), "") or "") // 4 + 10)
        return [assistant], usage

    async def stream(
        self,
        messages: list[Message],
        tools: list[ToolDef] | None = None,
        system: str | None = None,
        max_tokens: int | None = None,
    ) -> AsyncIterator[StreamEvent]:
        text = self._mock_text or self._echo(messages)
        if self._mock_tool_name and self._call_count == 0:
            yield StreamEvent(type="tool_use_start", tool_name=self._mock_tool_name, tool_input=json.dumps(self._mock_tool_input))
            yield StreamEvent(type="tool_use_end")
        else:
            yield StreamEvent(type="text", text=text)
        self._call_count += 1
        yield StreamEvent(
            type="stop",
            input_tokens=10,
            output_tokens=len(text) // 4 + 10,
        )

    async def count_tokens(
        self, messages: list[Message], system: str | None = None
    ) -> Usage:
        # 简单估算：每 4 字符 1 token
        total = sum(len(m.content or "") // 4 for m in messages)
        total += len(system or "") // 4
        return Usage(input_tokens=total, output_tokens=0)

    @staticmethod
    def _echo(messages: list[Message]) -> str:
        for m in reversed(messages):
            if m.content:
                return f"echo: {m.content[:200]}"
        return ""
