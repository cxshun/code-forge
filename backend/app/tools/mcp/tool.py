"""MCP 工具包装（design D37 / spec F3.4.2 / F3.4.7）。

将 MCP 服务发现的单个工具包装为 ``Tool`` 接口，委托 ``McpClient`` 执行。

- ``read_only`` 从 MCP 模型透传（D37：read_only=True 豁免 WS 锁）
- 不受 D17 路径校验（MCP 工具行为不可控，design 明确排除）
- 60s 超时在 ``McpClient.call_tool`` 内实现
"""

from app.tools.base import Tool, ToolContext
from app.tools.mcp.client import McpClient


class McpTool(Tool):
    """mcp__{tool_name}：委托 MCP 客户端执行。

    name 为 ``mcp__{tool_name}`` 前缀，与 builtin / skill 工具命名空间隔离。
    """

    def __init__(
        self,
        client: McpClient,
        tool_name: str,
        description: str,
        input_schema: dict,
        read_only: bool,
    ) -> None:
        self.name = f"mcp__{tool_name}"
        self.description = description or f"MCP tool: {tool_name}"
        self.input_schema = input_schema
        self.read_only = read_only
        self._client = client
        self._tool_name = tool_name

    async def run(self, input: dict, ctx: ToolContext) -> str:
        return await self._client.call_tool(self._tool_name, input)
