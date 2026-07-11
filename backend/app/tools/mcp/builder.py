"""MCP 工具构建器（design D37 / spec F3.4.2）。

查 WS 挂载的 MCP 配置，连接每个 MCP 服务，发现工具并包装为 ``McpTool`` 列表。
连接失败的 MCP 跳过（不影响其他工具），日志记录。
"""

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decrypt_secrets
from app.db.models import MCP, WorkspaceMcp
from app.tools.mcp.client import McpClient
from app.tools.mcp.tool import McpTool

log = logging.getLogger("tools.mcp.builder")


async def build_mcp_tools(
    db: AsyncSession, ws_id: int
) -> tuple[list[McpTool], list[McpClient]]:
    """查 WS 挂载的 MCP，连接并返回工具列表。

    返回 (tools, clients)：
    - tools：已注册的 McpTool 列表
    - clients：已连接的 McpClient 列表（供调用方在 Run 结束后 close）

    连接失败的 MCP 跳过，不阻断其他工具。
    """
    mcps = (
        await db.scalars(
            select(MCP)
            .join(WorkspaceMcp, WorkspaceMcp.mcp_id == MCP.id)
            .where(WorkspaceMcp.workspace_id == ws_id)
        )
    ).all()

    tools: list[McpTool] = []
    clients: list[McpClient] = []

    for mcp in mcps:
        config = decrypt_secrets(mcp.config)
        client = McpClient(
            mcp_id=mcp.id,
            name=mcp.name,
            mcp_type=mcp.type,
            config=config,
            read_only=mcp.read_only,
        )
        try:
            tool_defs = await client.connect()
        except Exception as e:
            log.warning("MCP %s (id=%d) skipped: %s", mcp.name, mcp.id, e)
            continue

        clients.append(client)
        for td in tool_defs:
            tools.append(
                McpTool(
                    client=client,
                    tool_name=td.name,
                    description=td.description,
                    input_schema=td.input_schema,
                    read_only=mcp.read_only,
                )
            )

    if tools:
        log.info("WS %d: %d MCP tools from %d servers", ws_id, len(tools), len(clients))

    return tools, clients
