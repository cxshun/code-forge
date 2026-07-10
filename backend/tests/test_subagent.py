"""子代理测试（T5.9 验收）。"""

from typing import ClassVar

from app.agent.subagent import AgentTool
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
    tool = AgentTool(provider, registry, system="sys")
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
    tool = AgentTool(provider, registry, system="sys")
    ctx = ToolContext(ws_id=1, workspaces_root="/tmp")
    result = await tool.run({"prompt": "echo hi"}, ctx)
    assert result == "saw echo"


async def test_sub_registry_excludes_agent():
    provider = MockProvider(mock_text="ok")
    registry = ToolRegistry().register(EchoTool())
    registry.register(AgentTool(provider, registry, "sys"))
    sub = registry.sub_registry(exclude={"Agent"})
    assert "Agent" not in sub.names()
    assert "echo" in sub.names()
