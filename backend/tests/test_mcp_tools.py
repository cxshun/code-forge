"""MCP 工具测试：decrypt_secrets / McpTool 属性 / build_mcp_tools 降级 / register_mcp_tools cleanup。

不连真实 MCP 服务——用 monkeypatch / mock client 验证接线与降级行为。
"""

import pytest

from app.agent.runtime import build_registry, make_provider, register_mcp_tools
from app.config import settings
from app.core.security import decrypt_secrets, encrypt_secrets
from app.db.models import MCP, User, Workspace, WorkspaceMcp
from app.db.session import async_session_factory
from app.db.testing import reset_all
from app.tools.base import ToolContext
from app.tools.mcp.client import McpClient, McpToolDef
from app.tools.mcp.tool import McpTool
from app.workspace.fs import create_workspace_skeleton

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
async def _isolated(tmp_path_factory, monkeypatch):
    monkeypatch.setattr(settings, "data_dir", str(tmp_path_factory.mktemp("cf_data")))
    await reset_all()
    yield


# ---- decrypt_secrets ----


async def test_decrypt_secrets_roundtrip():
    original = {
        "command": "npx",
        "args": ["-y", "@mcp/server"],
        "env": {"api_key": "secret123"},
    }
    encrypted = encrypt_secrets(original)
    assert encrypted["env"]["api_key"] != "secret123"
    decrypted = decrypt_secrets(encrypted)
    assert decrypted == original


async def test_decrypt_secrets_plain_value_passthrough():
    assert decrypt_secrets("hello") == "hello"
    assert decrypt_secrets(42) == 42
    assert decrypt_secrets(None) is None


async def test_decrypt_secrets_non_ciphertext_passthrough():
    assert decrypt_secrets({"token": "not-encrypted"}) == {"token": "not-encrypted"}


async def test_decrypt_secrets_nested_list():
    original = {"headers": [{"authorization": "Bearer xyz"}]}
    encrypted = encrypt_secrets(original)
    assert encrypted["headers"][0]["authorization"] != "Bearer xyz"
    assert decrypt_secrets(encrypted) == original


# ---- McpTool ----


class _MockClient(McpClient):
    """绕过真实连接的 mock client。"""

    def __init__(self, call_result: str = "ok", read_only: bool = False):
        super().__init__(mcp_id=0, name="mock", mcp_type="stdio", config={}, read_only=read_only)
        self._call_result = call_result
        self._available = True
        self._closed = False

    async def call_tool(self, name: str, arguments: dict) -> str:
        return self._call_result

    async def close(self) -> None:
        self._closed = True
        self._available = False


async def test_mcp_tool_properties():
    client = _MockClient(read_only=True)
    tool = McpTool(
        client=client,
        tool_name="search",
        description="Search the web",
        input_schema={"type": "object", "properties": {"q": {"type": "string"}}},
        read_only=True,
    )
    assert tool.name == "mcp__search"
    assert tool.description == "Search the web"
    assert tool.read_only is True
    assert tool.input_schema["type"] == "object"


async def test_mcp_tool_run_delegates_to_client():
    client = _MockClient(call_result="result: 42")
    tool = McpTool(
        client=client,
        tool_name="calc",
        description="",
        input_schema={},
        read_only=False,
    )
    ctx = ToolContext(ws_id=1, workspaces_root="/tmp")
    result = await tool.run({"expr": "6*7"}, ctx)
    assert result == "result: 42"
    assert tool.read_only is False


async def test_mcp_tool_description_fallback():
    client = _MockClient()
    tool = McpTool(
        client=client,
        tool_name="unnamed",
        description="",
        input_schema={},
        read_only=True,
    )
    assert "unnamed" in tool.description


# ---- build_mcp_tools 降级 ----


async def _seed_ws_with_mcp(mcp_type="stdio", config=None, read_only=False):
    if config is None:
        config = {"command": "echo", "args": ["hi"]}
    async with async_session_factory() as s:
        u = User(username="u", password_hash="x", role="admin")
        s.add(u)
        await s.commit()
        await s.refresh(u)
        ws = Workspace(name="w", owner_id=u.id)
        s.add(ws)
        await s.commit()
        await s.refresh(ws)
        create_workspace_skeleton(ws.id)
        mcp = MCP(
            name="test-mcp",
            type=mcp_type,
            config=encrypt_secrets(config),
            owner_id=u.id,
            visibility="public",
            read_only=read_only,
        )
        s.add(mcp)
        await s.commit()
        await s.refresh(mcp)
        s.add(WorkspaceMcp(workspace_id=ws.id, mcp_id=mcp.id))
        await s.commit()
        return ws.id, mcp.id


async def test_build_mcp_tools_connect_failure_skipped(monkeypatch):
    """MCP 连接失败时跳过，不阻断其他工具。"""
    ws_id, _ = await _seed_ws_with_mcp()

    async def _fail_connect(self):
        raise ConnectionError("server down")

    monkeypatch.setattr(McpClient, "connect", _fail_connect)

    from app.tools.mcp.builder import build_mcp_tools

    async with async_session_factory() as db:
        tools, clients = await build_mcp_tools(db, ws_id)
    assert tools == []
    assert clients == []


async def test_build_mcp_tools_success(monkeypatch):
    """MCP 连接成功时返回工具列表。"""
    ws_id, _ = await _seed_ws_with_mcp(read_only=True)

    async def _fake_connect(self):
        self._available = True
        return [McpToolDef(name="search", description="Search", input_schema={})]

    monkeypatch.setattr(McpClient, "connect", _fake_connect)

    from app.tools.mcp.builder import build_mcp_tools

    async with async_session_factory() as db:
        tools, clients = await build_mcp_tools(db, ws_id)
    assert len(tools) == 1
    assert tools[0].name == "mcp__search"
    assert tools[0].read_only is True
    assert len(clients) == 1
    # cleanup 关闭客户端
    await clients[0].close()
    assert not clients[0].available


async def test_build_mcp_tools_no_mounts():
    """无 MCP 挂载时返回空列表。"""
    async with async_session_factory() as s:
        u = User(username="u2", password_hash="x", role="admin")
        s.add(u)
        await s.commit()
        await s.refresh(u)
        ws = Workspace(name="w2", owner_id=u.id)
        s.add(ws)
        await s.commit()
        await s.refresh(ws)
        create_workspace_skeleton(ws.id)
        ws_id = ws.id

    from app.tools.mcp.builder import build_mcp_tools

    async with async_session_factory() as db:
        tools, clients = await build_mcp_tools(db, ws_id)
    assert tools == []
    assert clients == []


# ---- build_registry 整合 ----


async def test_build_registry_with_mcp(monkeypatch):
    """build_registry + register_mcp_tools 注册 MCP 工具并返回 cleanup 回调。"""
    ws_id, _ = await _seed_ws_with_mcp(read_only=True)

    async def _fake_connect(self):
        self._available = True
        return [McpToolDef(name="lookup", description="Look up", input_schema={})]

    monkeypatch.setattr(McpClient, "connect", _fake_connect)

    async with async_session_factory() as db:
        registry, _descs = await build_registry(db, ws_id, make_provider())
        mcp_cleanup = await register_mcp_tools(db, ws_id, registry)

    names = set(registry.names())
    assert "mcp__lookup" in names
    assert registry.is_readonly("mcp__lookup")  # read_only=True
    assert mcp_cleanup is not None
    # cleanup 可调用且幂等
    await mcp_cleanup()
    await mcp_cleanup()  # 不抛


async def test_build_registry_without_mcp_returns_none_cleanup():
    """无 MCP 挂载时 register_mcp_tools 返回 None。"""
    async with async_session_factory() as s:
        u = User(username="u3", password_hash="x", role="admin")
        s.add(u)
        await s.commit()
        await s.refresh(u)
        ws = Workspace(name="w3", owner_id=u.id)
        s.add(ws)
        await s.commit()
        await s.refresh(ws)
        create_workspace_skeleton(ws.id)
        ws_id = ws.id

    async with async_session_factory() as db:
        registry, _ = await build_registry(db, ws_id, make_provider())
        mcp_cleanup = await register_mcp_tools(db, ws_id, registry)
    assert mcp_cleanup is None
    assert {"Read", "Write", "Bash"} <= set(registry.names())
