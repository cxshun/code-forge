"""Memory 管理后端 API 测试（T7.5 验收）。"""

import pytest
from httpx import ASGITransport, AsyncClient

from app.config import settings
from app.core.redis_client import redis as redis_client
from app.core.security import hash_password
from app.db.models import FeishuChat, User, Workspace
from app.db.session import async_session_factory
from app.db.testing import reset_all
from app.main import app
from app.workspace.fs import workspace_root

ADMIN = {"username": "admin", "password": "adminpass1"}

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
async def _isolated(tmp_path_factory, monkeypatch):
    monkeypatch.setattr(settings, "data_dir", str(tmp_path_factory.mktemp("cf_data")))
    await reset_all()
    await redis_client.flushdb()
    yield
    await redis_client.flushdb()


async def _seed() -> tuple[int, int, int]:
    """返回 (ws_id, chat_id_in_ws, other_ws_id)。"""
    async with async_session_factory() as s:
        admin = User(
            username=ADMIN["username"],
            password_hash=hash_password(ADMIN["password"]),
            role="admin",
        )
        s.add(admin)
        await s.commit()
        await s.refresh(admin)
        ws = Workspace(name="ws", owner_id=admin.id)
        ws2 = Workspace(name="ws2", owner_id=admin.id)
        s.add_all([ws, ws2])
        await s.commit()
        await s.refresh(ws)
        await s.refresh(ws2)
        chat = FeishuChat(
            workspace_id=ws.id, app_id="cli_a", chat_id="oc_a", chat_name="g"
        )
        s.add(chat)
        await s.commit()
        await s.refresh(chat)
        return ws.id, chat.id, ws2.id


def _client():
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _login(ac: AsyncClient):
    await ac.post("/api/auth/login", json=ADMIN)


async def test_list_default_memory_index():
    ws_id, chat_id, _ = await _seed()
    async with _client() as ac:
        await _login(ac)
        r = await ac.get(f"/api/admin/workspaces/{ws_id}/chats/{chat_id}/memory")
        assert r.status_code == 200
        names = [f["filename"] for f in r.json()["files"]]
        assert "MEMORY.md" in names  # 首次访问建空索引


async def test_put_get_delete_roundtrip():
    ws_id, chat_id, _ = await _seed()
    async with _client() as ac:
        await _login(ac)
        r = await ac.put(
            f"/api/admin/workspaces/{ws_id}/chats/{chat_id}/memory/feedback_lint.md",
            json={"content": "用 ruff 不用 black"},
        )
        assert r.status_code == 200
        r = await ac.get(
            f"/api/admin/workspaces/{ws_id}/chats/{chat_id}/memory/feedback_lint.md"
        )
        assert r.status_code == 200
        assert r.json()["content"] == "用 ruff 不用 black"
        r = await ac.delete(
            f"/api/admin/workspaces/{ws_id}/chats/{chat_id}/memory/feedback_lint.md"
        )
        assert r.status_code == 200
        assert r.json()["deleted"] is True
        # 删后再 GET → 404
        r = await ac.get(
            f"/api/admin/workspaces/{ws_id}/chats/{chat_id}/memory/feedback_lint.md"
        )
        assert r.status_code == 404


async def test_filename_whitelist_rejects_traversal():
    ws_id, chat_id, _ = await _seed()
    async with _client() as ac:
        await _login(ac)
        # 非法字符 / 路径穿越 → 422（或被路由解析为 404）
        for bad in ("../etc.md", "sub/dir.md", "noext", "a b.md"):
            r = await ac.get(
                f"/api/admin/workspaces/{ws_id}/chats/{chat_id}/memory/{bad}"
            )
            assert r.status_code in (404, 422), bad
        # 合法名
        r = await ac.put(
            f"/api/admin/workspaces/{ws_id}/chats/{chat_id}/memory/ok-file_1.md",
            json={"content": "x"},
        )
        assert r.status_code == 200


async def test_chat_not_in_ws_404():
    """chat 属于 ws1，用 ws2 访问 → 404（D31 多租户隔离）。"""
    _ws_id, chat_id, other_ws_id = await _seed()
    async with _client() as ac:
        await _login(ac)
        r = await ac.get(
            f"/api/admin/workspaces/{other_ws_id}/chats/{chat_id}/memory"
        )
        assert r.status_code == 404


async def test_cross_ws_memory_isolation():
    """ws1 的 memory 写入不影响 ws2（物理隔离）。"""
    ws_id, chat_id, other_ws_id = await _seed()
    # ws2 下也建一个 chat
    async with async_session_factory() as s:
        chat2 = FeishuChat(
            workspace_id=other_ws_id, app_id="cli_b", chat_id="oc_b", chat_name="g2"
        )
        s.add(chat2)
        await s.commit()
        await s.refresh(chat2)
        chat2_id = chat2.id
    async with _client() as ac:
        await _login(ac)
        await ac.put(
            f"/api/admin/workspaces/{ws_id}/chats/{chat_id}/memory/feedback_lint.md",
            json={"content": "ws1-lint"},
        )
        # ws2 的 chat 列表里没有该文件
        r = await ac.get(
            f"/api/admin/workspaces/{other_ws_id}/chats/{chat2_id}/memory"
        )
        names = [f["filename"] for f in r.json()["files"]]
        assert "feedback_lint.md" not in names
        # 物理路径也确实不在 ws2
        assert not (
            workspace_root(other_ws_id)
            / "chats"
            / str(chat2_id)
            / "memory"
            / "feedback_lint.md"
        ).exists()


async def test_unauth_401():
    ws_id, chat_id, _ = await _seed()
    async with _client() as ac:
        r = await ac.get(f"/api/admin/workspaces/{ws_id}/chats/{chat_id}/memory")
        assert r.status_code == 401
