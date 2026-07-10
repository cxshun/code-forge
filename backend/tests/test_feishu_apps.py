"""飞书 App 注册测试（T3.3 验收）。"""

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.redis_client import redis as redis_client
from app.core.security import hash_password
from app.db.models import FeishuChat, User, Workspace
from app.db.session import async_session_factory
from app.db.testing import reset_all
from app.main import app

ADMIN = {"username": "admin", "password": "adminpass1"}
SECRET = "secret_12345678"


@pytest.fixture(autouse=True)
async def _reset():
    await reset_all()
    await redis_client.flushdb()
    yield
    await redis_client.flushdb()


async def _seed() -> User:
    async with async_session_factory() as s:
        u = User(
            username=ADMIN["username"],
            password_hash=hash_password(ADMIN["password"]),
            role="user",
        )
        s.add(u)
        await s.commit()
        await s.refresh(u)
        return u


def _client():
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def test_create_returns_full_secret_once():
    await _seed()
    async with _client() as ac:
        await ac.post("/api/auth/login", json=ADMIN)
        r = await ac.post(
            "/api/admin/feishu-apps",
            json={"app_id": "cli_a", "app_secret": SECRET, "name": "app1"},
        )
        assert r.status_code == 201
        body = r.json()
        assert body["app_secret"] == SECRET  # 完整仅创建时返回
        assert "..." in body["app_secret_masked"]


async def test_list_masks_secret():
    await _seed()
    async with _client() as ac:
        await ac.post("/api/auth/login", json=ADMIN)
        await ac.post(
            "/api/admin/feishu-apps",
            json={"app_id": "cli_a", "app_secret": SECRET, "name": "app1"},
        )
        body = (await ac.get("/api/admin/feishu-apps")).json()["items"][0]
        assert "app_secret" not in body  # 列表不含完整 secret
        assert "..." in body["app_secret_masked"]
        assert SECRET not in str(body)


async def test_delete_with_chat_rejected():
    admin = await _seed()
    async with _client() as ac:
        await ac.post("/api/auth/login", json=ADMIN)
        pk = (
            await ac.post(
                "/api/admin/feishu-apps",
                json={"app_id": "cli_a", "app_secret": SECRET, "name": "app1"},
            )
        ).json()["id"]
        async with async_session_factory() as s:
            ws = Workspace(name="w", owner_id=admin.id)
            s.add(ws)
            await s.commit()
            await s.refresh(ws)
            s.add(
                FeishuChat(
                    workspace_id=ws.id, app_id="cli_a", chat_id="oc_x", chat_name="g"
                )
            )
            await s.commit()
        assert (await ac.delete(f"/api/admin/feishu-apps/{pk}")).status_code == 422
