"""MCP 客户端模块（design D37 / spec F3.4.2）。

连接外部 MCP 服务（stdio / http），发现工具并注册到 Agent 工具集。

- ``client`` — McpClient：封装单个 MCP 服务连接（connect / call_tool / close）
- ``tool`` — McpTool：将 MCP 工具包装为 Tool 接口
- ``builder`` — build_mcp_tools：查 WS 挂载 MCP，连接并返回工具列表
"""

from app.tools.mcp.builder import build_mcp_tools
from app.tools.mcp.client import McpClient
from app.tools.mcp.tool import McpTool

__all__ = ["McpClient", "McpTool", "build_mcp_tools"]
