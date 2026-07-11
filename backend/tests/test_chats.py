"""FeishuChat 绑定测试（T2.3 验收）。"""

from typing import ClassVar

import pytest
from httpx import ASGITransport, AsyncClient

from app.api import chats as chats_module
from app.config import settings
from app.core.redis_client import redis as redis_client
from app.core.security import encrypt_secret, hash_password
from app.db.models import FeishuApp, User, Workspace
from app.db.session import async_session_factory
from app.db.testing import reset_all
from app.main import app
from app.workspace.fs import workspace_root

pytestmark = pytest.mark.asyncio

U1 = {"username": "u1", "password": "u1pass11"}
U2 = {"username": "u2", "password": "u2pass22"}


class _FakeChatData:
    def __init__(self, name):
        self.name = name


class _FakeFeishuClient:
    """按 chat_id 返回预设结果；oc_out → None（bot 不在群）。"""

    responses: ClassVar[dict[str, str | None]] = {}  # chat_id -> name | None

    def __init__(self, app_id, secret):
        pass

    async def get_chat(self, chat_id):
        name = self.responses.get(chat_id, None)
        return None if name is None else _FakeChatData(name)


@pytest.fixture(autouse=True)
async def _isolated(tmp_path_factory, monkeypatch):
    monkeypatch.setattr(settings, "data_dir", str(tmp_path_factory.mktemp("cf_data")))
    _FakeFeishuClient.responses = {"oc_in": "研发群", "oc_out": None}
    monkeypatch.setattr(chats_module, "FeishuClient", _FakeFeishuClient)
    await reset_all()
    await redis_client.flushdb()
    yield
    await redis_client.flushdb()


async def _seed():
    """u1 拥有 ws + app1；u2 拥有 app2（用于 403）。返回 (u1, ws_id, app1_id, app2_id)。"""
    async with async_session_factory() as s:
        u1 = User(username=U1["username"], password_hash=hash_password(U1["password"]))
        u2 = User(username=U2["username"], password_hash=hash_password(U2["password"]))
        s.add_all([u1, u2])
        await s.commit()
        await s.refresh(u1)
        await s.refresh(u2)
        ws = Workspace(name="ws", owner_id=u1.id)
        s.add(ws)
        await s.commit()
        await s.refresh(ws)
        app1 = FeishuApp(
            app_id="cli_app1", app_secret_enc=encrypt_secret("s1"),
            name="app1", owner_id=u1.id,
        )
        app2 = FeishuApp(
            app_id="cli_app2", app_secret_enc=encrypt_secret("s2"),
            name="app2", owner_id=u2.id,
        )
        s.add_all([app1, app2])
        await s.commit()
        return u1.id, ws.id, "cli_app1", "cli_app2"


def _client():
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _login(ac, creds):
    await ac.post("/api/auth/login", json=creds)


async def test_check_bot_in_chat():
    _, ws_id, app1, _ = await _seed()
    async with _client() as ac:
        await _login(ac, U1)
        r = await ac.post(
            f"/api/admin/workspaces/{ws_id}/chats:check",
            json={"app_id": app1, "chat_id": "oc_in"},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["valid"] is True
        assert body["bot_in_chat"] is True
        assert body["chat_name"] == "研发群"
        assert body["existing_binding"] is None


async def test_check_bot_not_in_chat():
    _, ws_id, app1, _ = await _seed()
    async with _client() as ac:
        await _login(ac, U1)
        r = await ac.post(
            f"/api/admin/workspaces/{ws_id}/chats:check",
            json={"app_id": app1, "chat_id": "oc_out"},
        )
        assert r.status_code == 200
        assert r.json()["bot_in_chat"] is False
        assert r.json()["valid"] is False


async def test_bind_creates_chat_and_memory_dir():
    _, ws_id, app1, _ = await _seed()
    async with _client() as ac:
        await _login(ac, U1)
        r = await ac.post(
            f"/api/admin/workspaces/{ws_id}/chats",
            json={"app_id": app1, "chat_id": "oc_in"},
        )
        assert r.status_code == 201, r.text
        chat = r.json()
        assert chat["chat_name"] == "研发群"
        assert chat["workspace_id"] == ws_id
        # memory 目录骨架已建（D18）
        mem = workspace_root(ws_id) / "chats" / str(chat["id"]) / "memory" / "MEMORY.md"
        assert mem.exists()


async def test_bind_bot_not_in_chat_422():
    _, ws_id, app1, _ = await _seed()
    async with _client() as ac:
        await _login(ac, U1)
        r = await ac.post(
            f"/api/admin/workspaces/{ws_id}/chats",
            json={"app_id": app1, "chat_id": "oc_out"},
        )
        assert r.status_code == 422


async def test_bind_duplicate_409():
    _, ws_id, app1, _ = await _seed()
    async with _client() as ac:
        await _login(ac, U1)
        await ac.post(f"/api/admin/workspaces/{ws_id}/chats",
                      json={"app_id": app1, "chat_id": "oc_in"})
        r = await ac.post(f"/api/admin/workspaces/{ws_id}/chats",
                          json={"app_id": app1, "chat_id": "oc_in"})
        assert r.status_code == 409


async def test_bind_cross_ws_duplicate_409():
    """同一 (app_id, chat_id) 已绑 ws1，ws2 再绑 → 409。"""
    u1_id, ws1_id, app1, _ = await _seed()
    async with async_session_factory() as s:
        ws2 = Workspace(name="ws2", owner_id=u1_id)
        s.add(ws2)
        await s.commit()
        await s.refresh(ws2)
        ws2_id = ws2.id
    async with _client() as ac:
        await _login(ac, U1)
        await ac.post(f"/api/admin/workspaces/{ws1_id}/chats",
                      json={"app_id": app1, "chat_id": "oc_in"})
        r = await ac.post(f"/api/admin/workspaces/{ws2_id}/chats",
                          json={"app_id": app1, "chat_id": "oc_in"})
        assert r.status_code == 409


async def test_bind_app_not_owned_403():
    """u1 绑定 u2 的 app → 403。"""
    _, ws_id, _, app2 = await _seed()
    async with _client() as ac:
        await _login(ac, U1)
        r = await ac.post(
            f"/api/admin/workspaces/{ws_id}/chats",
            json={"app_id": app2, "chat_id": "oc_in"},
        )
        assert r.status_code == 403


async def test_bind_app_not_registered_422():
    _, ws_id, _, _ = await _seed()
    async with _client() as ac:
        await _login(ac, U1)
        r = await ac.post(
            f"/api/admin/workspaces/{ws_id}/chats",
            json={"app_id": "cli_unknown", "chat_id": "oc_in"},
        )
        assert r.status_code == 422


async def test_list_and_unbind():
    _, ws_id, app1, _ = await _seed()
    async with _client() as ac:
        await _login(ac, U1)
        r = await ac.post(f"/api/admin/workspaces/{ws_id}/chats",
                          json={"app_id": app1, "chat_id": "oc_in"})
        chat_id = r.json()["id"]
        r = await ac.get(f"/api/admin/workspaces/{ws_id}/chats")
        assert r.status_code == 200
        assert r.json()["total"] == 1
        r = await ac.delete(f"/api/admin/workspaces/{ws_id}/chats/{chat_id}")
        assert r.status_code == 204
        # 删后列表空
        r = await ac.get(f"/api/admin/workspaces/{ws_id}/chats")
        assert r.json()["total"] == 0


async def test_unbind_other_ws_chat_404():
    u1_id, ws1_id, app1, _ = await _seed()
    async with async_session_factory() as s:
        ws2 = Workspace(name="ws2", owner_id=u1_id)
        s.add(ws2)
        await s.commit()
        await s.refresh(ws2)
        ws2_id = ws2.id
    async with _client() as ac:
        await _login(ac, U1)
        r = await ac.post(f"/api/admin/workspaces/{ws1_id}/chats",
                          json={"app_id": app1, "chat_id": "oc_in"})
        chat_id = r.json()["id"]
        # ws2 解绑 ws1 的 chat → 404
        r = await ac.delete(f"/api/admin/workspaces/{ws2_id}/chats/{chat_id}")
        assert r.status_code == 404
