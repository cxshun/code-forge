"""MCP 广场测试（T3.2 验收）。"""

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.redis_client import redis as redis_client
from app.core.security import hash_password
from app.db.models import User, Workspace, WorkspaceMcp
from app.db.session import async_session_factory
from app.db.testing import reset_all
from app.main import app

ADMIN = {"username": "admin", "password": "adminpass1"}
SECRET = "sk-1234567890abcdef"


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


async def test_create_masks_secrets():
    await _seed()
    async with _client() as ac:
        await ac.post("/api/auth/login", json=ADMIN)
        r = await ac.post(
            "/api/admin/mcps",
            json={
                "name": "m1",
                "type": "stdio",
                "config": {"command": "x", "env": {"API_KEY": SECRET}},
            },
        )
        assert r.status_code == 201
        masked = r.json()["config"]["env"]["API_KEY"]
        assert "..." in masked
        assert SECRET not in r.text  # 明文不入响应


async def test_list_visibility_and_patch():
    await _seed()
    async with _client() as ac:
        await ac.post("/api/auth/login", json=ADMIN)
        await ac.post(
            "/api/admin/mcps",
            json={
                "name": "pub",
                "type": "http",
                "config": {"endpoint": "http://x"},
                "visibility": "public",
            },
        )
        assert (await ac.get("/api/admin/mcps")).json()["total"] == 1
        mid = (await ac.get("/api/admin/mcps")).json()["items"][0]["id"]
        p = await ac.patch(
            f"/api/admin/mcps/{mid}", json={"read_only": True}
        )
        assert p.json()["read_only"] is True


async def test_delete_referenced_rejected():
    admin = await _seed()
    async with _client() as ac:
        await ac.post("/api/auth/login", json=ADMIN)
        mid = (
            await ac.post(
                "/api/admin/mcps",
                json={"name": "m", "type": "http", "config": {"endpoint": "http://x"}},
            )
        ).json()["id"]
        async with async_session_factory() as s:
            ws = Workspace(name="w", owner_id=admin.id)
            s.add(ws)
            await s.commit()
            await s.refresh(ws)
            s.add(WorkspaceMcp(workspace_id=ws.id, mcp_id=mid))
            await s.commit()
        assert (await ac.delete(f"/api/admin/mcps/{mid}")).status_code == 422
