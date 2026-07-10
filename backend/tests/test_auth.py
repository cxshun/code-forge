"""鉴权接口测试（task T1.4 验收）。"""

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.redis_client import redis as redis_client
from app.core.security import hash_password
from app.db.models import User
from app.db.session import async_session_factory
from app.db.testing import reset_all
from app.main import app

ADMIN = {"username": "admin", "password": "adminpass1"}
PLAIN = {"username": "alice", "password": "alicepass1"}


@pytest.fixture(autouse=True)
async def _reset():
    await reset_all()
    await redis_client.flushdb()
    yield
    await redis_client.flushdb()


async def _seed():
    async with async_session_factory() as s:
        s.add_all(
            [
                User(
                    username=ADMIN["username"],
                    password_hash=hash_password(ADMIN["password"]),
                    role="admin",
                ),
                User(
                    username=PLAIN["username"],
                    password_hash=hash_password(PLAIN["password"]),
                    role="user",
                ),
            ]
        )
        await s.commit()


def _client():
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def test_login_success():
    await _seed()
    async with _client() as ac:
        r = await ac.post("/api/auth/login", json=ADMIN)
        assert r.status_code == 200
        assert r.json()["user"]["username"] == "admin"
        assert "cf_session" in r.cookies


async def test_login_wrong_password():
    await _seed()
    async with _client() as ac:
        r = await ac.post(
            "/api/auth/login", json={"username": "admin", "password": "wrongpass1"}
        )
        assert r.status_code == 401
        assert r.json()["error"]["code"] == "unauthorized"


async def test_login_rate_limit():
    await _seed()
    async with _client() as ac:
        for _ in range(5):
            r = await ac.post(
                "/api/auth/login",
                json={"username": "admin", "password": "wrongpass1"},
            )
            assert r.status_code == 401
        # 第 6 次：即便密码正确，同 IP 已超 5 次/分钟 → 429
        r = await ac.post("/api/auth/login", json=ADMIN)
        assert r.status_code == 429


async def test_me_unauthorized():
    async with _client() as ac:
        r = await ac.get("/api/auth/me")
        assert r.status_code == 401


async def test_me_ok_returns_workspaces():
    await _seed()
    async with _client() as ac:
        await ac.post("/api/auth/login", json=ADMIN)
        r = await ac.get("/api/auth/me")
        assert r.status_code == 200
        body = r.json()
        assert body["user"]["username"] == "admin"
        assert body["workspaces"] == []


async def test_logout_clears_session():
    await _seed()
    async with _client() as ac:
        await ac.post("/api/auth/login", json=ADMIN)
        assert (await ac.post("/api/auth/logout")).status_code == 200
        assert (await ac.get("/api/auth/me")).status_code == 401


async def test_change_password():
    await _seed()
    async with _client() as ac:
        await ac.post("/api/auth/login", json=ADMIN)
        r = await ac.post(
            "/api/auth/change-password",
            json={"old_password": "adminpass1", "new_password": "newpass123"},
        )
        assert r.status_code == 200
        # 用新密码登录
        r2 = await ac.post(
            "/api/auth/login", json={"username": "admin", "password": "newpass123"}
        )
        assert r2.status_code == 200
