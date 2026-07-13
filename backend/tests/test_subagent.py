"""子代理测试（T5.9 验收）。"""

import asyncio
from typing import ClassVar

from app.agent.subagent import AgentTool
from app.providers.base import StreamEvent
from app.providers.mock_provider import MockProvider
from app.tools.base import Tool, ToolContext
from app.tools.registry import ToolRegistry

pytestmark = __import__("pytest").mark.asyncio


class EchoTool(Tool):
    name: ClassVar[str] = "echo"
    description: ClassVar[str] = "echo"
    input_schema: ClassVar[dict] = {
        "type": "object",
        "properties": {"text": {"type": "string"}},
    }
    read_only: ClassVar[bool] = True

    async def run(self, input, ctx):
        return f"echo: {input.get('text', '')}"


async def test_agent_tool_returns_subagent_final():
    provider = MockProvider(mock_text="sub done")
    registry = ToolRegistry().register(EchoTool())
    tool = AgentTool(provider, registry, asyncio.Semaphore(5))
    ctx = ToolContext(ws_id=1, workspaces_root="/tmp")
    result = await tool.run({"prompt": "research X"}, ctx)
    assert result == "sub done"


async def test_subagent_can_use_tools():
    provider = MockProvider(
        mock_tool_name="echo",
        mock_tool_input={"text": "hi"},
        mock_text="saw echo",
    )
    registry = ToolRegistry().register(EchoTool())
    tool = AgentTool(provider, registry, asyncio.Semaphore(5))
    ctx = ToolContext(ws_id=1, workspaces_root="/tmp")
    result = await tool.run({"prompt": "echo hi"}, ctx)
    assert result == "saw echo"


async def test_sub_registry_excludes_agent():
    provider = MockProvider(mock_text="ok")
    registry = ToolRegistry().register(EchoTool())
    registry.register(AgentTool(provider, registry, asyncio.Semaphore(5)))
    sub = registry.sub_registry(exclude={"Agent"})
    assert "Agent" not in sub.names()
    assert "echo" in sub.names()


class _StatelessToolProvider(MockProvider):
    """无实例共享状态：按 messages 末尾决定产 tool_use 还是 text（多子代理并发安全）。"""

    async def stream(self, messages, tools=None, system=None):
        if messages and messages[-1].role == "tool_result":
            yield StreamEvent(type="text", text="ok")
        else:
            yield StreamEvent(type="tool_use_start", tool_name="slow", tool_input="{}")
            yield StreamEvent(type="tool_use_end")
        yield StreamEvent(type="stop", input_tokens=5, output_tokens=5)


async def test_semaphore_limits_concurrency():
    """并行度上限：Semaphore(2) + 4 个子代理并发，峰值并发 ≤ 2。"""
    current = {"n": 0, "peak": 0}

    class _SlowEcho(Tool):
        name: ClassVar[str] = "slow"
        description: ClassVar[str] = "slow"
        input_schema: ClassVar[dict] = {"type": "object"}
        read_only: ClassVar[bool] = True

        async def run(self, input, ctx):
            current["n"] += 1
            current["peak"] = max(current["peak"], current["n"])
            await asyncio.sleep(0.05)
            current["n"] -= 1
            return "done"

    provider = _StatelessToolProvider()
    registry = ToolRegistry().register(_SlowEcho())
    tool = AgentTool(provider, registry, asyncio.Semaphore(2))
    ctx = ToolContext(ws_id=1, workspaces_root="/tmp")
    await asyncio.gather(*[tool.run({"prompt": "p"}, ctx) for _ in range(4)])
    assert current["peak"] <= 2
    assert current["peak"] >= 2  # 确实发生了并发（非完全串行）


async def test_single_failure_isolated():
    """单个子代理失败转 Error 文本回灌，不抛、不影响调用方。"""

    class _BoomProvider(MockProvider):
        async def stream(self, messages, tools=None, system=None):
            raise RuntimeError("boom")
            yield  # type: ignore[unreachable]  # 保持 async generator 语义

    provider = _BoomProvider()
    registry = ToolRegistry().register(EchoTool())
    tool = AgentTool(provider, registry, asyncio.Semaphore(5))
    ctx = ToolContext(ws_id=1, workspaces_root="/tmp")
    result = await tool.run({"prompt": "x"}, ctx)
    assert result.startswith("Error: subagent failed:")

