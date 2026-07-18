"""用户管理接口测试（task T1.6 验收）。"""

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


async def test_non_admin_forbidden():
    await _seed()
    async with _client() as ac:
        await ac.post("/api/auth/login", json=PLAIN)
        r = await ac.get("/api/admin/users")
        assert r.status_code == 403


async def test_admin_create_user_and_list():
    await _seed()
    async with _client() as ac:
        await ac.post("/api/auth/login", json=ADMIN)
        r = await ac.post(
            "/api/admin/users",
            json={"username": "bob", "password": "bobpass12", "role": "user"},
        )
        assert r.status_code == 201
        assert r.json()["username"] == "bob"
        lst = await ac.get("/api/admin/users")
        assert lst.status_code == 200
        assert lst.json()["total"] == 3  # admin + alice + bob


async def test_create_dup_username_conflict():
    await _seed()
    async with _client() as ac:
        await ac.post("/api/auth/login", json=ADMIN)
        r = await ac.post(
            "/api/admin/users",
            json={"username": "alice", "password": "xyzpass123", "role": "user"},
        )
        assert r.status_code == 409


async def test_patch_and_reset_password():
    await _seed()
    async with _client() as ac:
        await ac.post("/api/auth/login", json=ADMIN)
        # 拿 alice id
        users = (await ac.get("/api/admin/users")).json()["items"]
        alice = next(u for u in users if u["username"] == "alice")
        # 停用
        r = await ac.patch(
            f"/api/admin/users/{alice['id']}", json={"status": "disabled"}
        )
        assert r.status_code == 200
        assert r.json()["status"] == "disabled"
        # 重置密码
        r2 = await ac.post(
            f"/api/admin/users/{alice['id']}:reset-password",
            json={"new_password": "resetpass1"},
        )
        assert r2.status_code == 200


async def test_cannot_demote_self():
    """管理员不能把自己降级为 user（防止管理后台自锁）。"""
    await _seed()
    async with _client() as ac:
        await ac.post("/api/auth/login", json=ADMIN)
        me = next(
            u
            for u in (await ac.get("/api/admin/users")).json()["items"]
            if u["username"] == ADMIN["username"]
        )
        r = await ac.patch(f"/api/admin/users/{me['id']}", json={"role": "user"})
        assert r.status_code == 400
        # role 必须仍是 admin（未被修改）
        me_now = next(
            u
            for u in (await ac.get("/api/admin/users")).json()["items"]
            if u["username"] == ADMIN["username"]
        )
        assert me_now["role"] == "admin"


async def test_can_demote_other_admin_when_multiple():
    """存在多个管理员时，可以降级其他管理员（不被一刀切禁止）。"""
    async with async_session_factory() as s:
        s.add_all(
            [
                User(
                    username="admin",
                    password_hash=hash_password("adminpass1"),
                    role="admin",
                ),
                User(
                    username="boss",
                    password_hash=hash_password("bosspass1"),
                    role="admin",
                ),
            ]
        )
        await s.commit()
    async with _client() as ac:
        await ac.post("/api/auth/login", json=ADMIN)
        boss = next(
            u
            for u in (await ac.get("/api/admin/users")).json()["items"]
            if u["username"] == "boss"
        )
        r = await ac.patch(f"/api/admin/users/{boss['id']}", json={"role": "user"})
        assert r.status_code == 200
        assert r.json()["role"] == "user"


async def test_can_promote_user_to_admin():
    """把普通用户升级为管理员不受降级保护影响。"""
    await _seed()
    async with _client() as ac:
        await ac.post("/api/auth/login", json=ADMIN)
        alice = next(
            u
            for u in (await ac.get("/api/admin/users")).json()["items"]
            if u["username"] == "alice"
        )
        r = await ac.patch(f"/api/admin/users/{alice['id']}", json={"role": "admin"})
        assert r.status_code == 200
        assert r.json()["role"] == "admin"
