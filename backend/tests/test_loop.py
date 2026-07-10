"""Agentic Loop 测试（T5.2 验收）。"""

from typing import ClassVar

import pytest

from app.agent.loop import RunContext, run_loop
from app.providers.base import Message
from app.providers.mock_provider import MockProvider
from app.tools.base import Tool, ToolContext
from app.tools.registry import ToolRegistry


class EchoTool(Tool):
    name: ClassVar[str] = "echo"
    description: ClassVar[str] = "echo text"
    input_schema: ClassVar[dict] = {
        "type": "object",
        "properties": {"text": {"type": "string"}},
        "required": ["text"],
    }
    read_only: ClassVar[bool] = True

    async def run(self, input, ctx):
        return f"echo: {input.get('text', '')}"


class MarkTool(Tool):
    name: ClassVar[str] = "mark"
    description: ClassVar[str] = "mark done"
    input_schema: ClassVar[dict] = {"type": "object", "properties": {}}
    read_only: ClassVar[bool] = False

    async def run(self, input, ctx):
        ctx.todos.append({"done": True})
        return "marked"


@pytest.fixture
def ctx():
    return RunContext(
        messages=[Message(role="user", content="hi")],
        tool_ctx=ToolContext(ws_id=1, workspaces_root="/tmp"),
    )


async def test_loop_no_tools_returns_text(ctx):
    provider = MockProvider(mock_text="hello")
    result = await run_loop(provider, ctx, registry=None)
    assert result == "hello"


async def test_loop_tool_then_done(ctx):
    provider = MockProvider(
        mock_tool_name="echo",
        mock_tool_input={"text": "world"},
        mock_text="done",
    )
    registry = ToolRegistry().register(EchoTool())
    result = await run_loop(provider, ctx, registry)
    assert result == "done"
    # tool 执行了：tool_result 进 messages
    assert any(
        m.role == "tool_result" and "echo: world" in (m.content or "")
        for m in ctx.messages
    )


async def test_loop_write_tool_executed(ctx):
    provider = MockProvider(mock_tool_name="mark", mock_tool_input={}, mock_text="ok")
    registry = ToolRegistry().register(MarkTool())
    await run_loop(provider, ctx, registry)
    assert ctx.tool_ctx.todos == [{"done": True}]


async def test_loop_abort_raises(ctx):
    provider = MockProvider(mock_tool_name="echo", mock_tool_input={"text": "x"})
    registry = ToolRegistry().register(EchoTool())
    ctx.abort.set()
    with pytest.raises(InterruptedError):
        await run_loop(provider, ctx, registry)


async def test_loop_unknown_tool_error_fed_back(ctx):
    # LLM 调了未注册的工具 → 回灌错误，第二轮正常回复
    provider = MockProvider(mock_tool_name="ghost", mock_tool_input={}, mock_text="recovered")
    registry = ToolRegistry().register(EchoTool())
    result = await run_loop(provider, ctx, registry)
    assert result == "recovered"
    assert any(
        m.role == "tool_result" and "unknown tool" in (m.content or "")
        for m in ctx.messages
    )
