"""MCP 客户端连接封装（design D37）。

封装官方 ``mcp`` SDK 的 ``ClientSession``，管理单个 MCP 服务的连接生命周期：
- ``connect()``：建立 transport（stdio / sse）→ initialize → list_tools
- ``call_tool()``：60s 超时调用（D37）
- ``close()``：清理连接

连接失败 / crash 时标记 unavailable，调用报错回灌 Agent（§6.5 错误回灌）。
"""

import asyncio
import contextlib
import logging
from dataclasses import dataclass

from mcp import ClientSession, StdioServerParameters
from mcp.client.sse import sse_client
from mcp.client.stdio import stdio_client

log = logging.getLogger("tools.mcp.client")

MCP_CALL_TIMEOUT_S = 60  # D37：单次 MCP 工具调用默认 60s 超时


@dataclass
class McpToolDef:
    """MCP 服务发现的工具元信息。"""

    name: str
    description: str
    input_schema: dict


class McpClient:
    """单个 MCP 服务的客户端连接（stdio / http）。

    使用 ``mcp`` SDK 的 ``ClientSession`` 统一两种 transport：
    - stdio：``stdio_client(StdioServerParameters)`` 拉起子进程
    - http：``sse_client(endpoint)`` 建立 SSE 连接

    transport 和 session 作为 async context manager 手动管理生命周期，
    在 ``connect()`` 时进入、``close()`` 时退出。
    """

    def __init__(
        self,
        mcp_id: int,
        name: str,
        mcp_type: str,
        config: dict,
        read_only: bool = False,
    ) -> None:
        self._mcp_id = mcp_id
        self._name = name
        self._type = mcp_type
        self._config = config
        self.read_only = read_only
        self._session: ClientSession | None = None
        self._transport_cm: contextlib.AsyncExitStack | None = None
        self._available = False

    @property
    def name(self) -> str:
        return self._name

    @property
    def available(self) -> bool:
        return self._available

    async def connect(self) -> list[McpToolDef]:
        """建立连接并返回发现的工具列表。

        失败时抛异常（由 ``build_mcp_tools`` 捕获后跳过该 MCP）。
        """
        try:
            return await self._do_connect()
        except Exception as e:
            log.warning("MCP %s (id=%d) connect failed: %s", self._name, self._mcp_id, e)
            await self.close()
            raise

    async def _do_connect(self) -> list[McpToolDef]:
        self._transport_cm = contextlib.AsyncExitStack()
        transport_cm = self._transport_cm

        if self._type == "stdio":
            params = StdioServerParameters(
                command=self._config["command"],
                args=self._config.get("args", []),
                env={k: str(v) for k, v in self._config.get("env", {}).items()} or None,
            )
            read, write = await transport_cm.enter_async_context(stdio_client(params))
        elif self._type == "http":
            endpoint = self._config["endpoint"]
            read, write = await transport_cm.enter_async_context(sse_client(endpoint))
        else:
            raise ValueError(f"unsupported MCP type: {self._type}")

        self._session = await transport_cm.enter_async_context(
            ClientSession(read, write)
        )
        await self._session.initialize()
        self._available = True

        result = await self._session.list_tools()
        tools: list[McpToolDef] = []
        for t in result.tools:
            tools.append(
                McpToolDef(
                    name=t.name,
                    description=t.description or "",
                    input_schema=t.inputSchema if isinstance(t.inputSchema, dict) else {},
                )
            )
        log.info(
            "MCP %s (id=%d) connected: %d tools",
            self._name,
            self._mcp_id,
            len(tools),
        )
        return tools

    async def call_tool(self, name: str, arguments: dict) -> str:
        """调用 MCP 工具，60s 超时（D37）。返回文本结果。

        连接不可用或超时时返回 error 文本（不抛异常，由 registry 兜底回灌 Agent）。
        """
        if not self._available or self._session is None:
            return f"Error: MCP '{self._name}' is not available"

        try:
            result = await asyncio.wait_for(
                self._session.call_tool(name, arguments),
                timeout=MCP_CALL_TIMEOUT_S,
            )
        except TimeoutError:
            return f"Error: MCP tool '{name}' timed out after {MCP_CALL_TIMEOUT_S}s"
        except Exception as e:
            log.warning("MCP %s tool '%s' call failed: %s", self._name, name, e)
            self._available = False
            return f"Error: MCP tool '{name}' call failed: {e}"

        return _extract_text(result)

    async def close(self) -> None:
        """清理连接（幂等，可多次调用）。"""
        self._available = False
        self._session = None
        if self._transport_cm is not None:
            try:
                await self._transport_cm.aclose()
            except Exception:
                log.warning(
                    "MCP %s (id=%d) close error", self._name, self._mcp_id, exc_info=True
                )
            self._transport_cm = None


def _extract_text(result) -> str:
    """从 CallToolResult 提取纯文本。

    MCP 工具返回 ``content`` 列表（TextContent / ImageContent / EmbeddedResource），
    仅提取 TextContent.text 拼接；isError 时前缀标注。
    """
    parts: list[str] = []
    for block in result.content:
        text = getattr(block, "text", None)
        if text:
            parts.append(text)
    text = "\n".join(parts) if parts else ""
    if result.isError:
        return f"Error: {text}"
    return text
