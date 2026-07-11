"""Skill / MCP 挂载管理测试（T2.4 验收）。"""

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.mounts import MAX_SKILLS_PER_WS
from app.config import settings
from app.core.redis_client import redis as redis_client
from app.core.security import hash_password
from app.db.models import MCP, Skill, User, Workspace
from app.db.session import async_session_factory
from app.db.testing import reset_all
from app.main import app

pytestmark = pytest.mark.asyncio

ADMIN = {"username": "admin", "password": "adminpass1"}


@pytest.fixture(autouse=True)
async def _isolated(tmp_path_factory, monkeypatch):
    monkeypatch.setattr(settings, "data_dir", str(tmp_path_factory.mktemp("cf_data")))
    await reset_all()
    await redis_client.flushdb()
    yield
    await redis_client.flushdb()


async def _seed():
    """admin 拥有 ws + 一批 Skill/MCP；u2 拥有私有 Skill。返回 (admin_id, ws_id, u2_id)。"""
    async with async_session_factory() as s:
        admin = User(
            username=ADMIN["username"], password_hash=hash_password(ADMIN["password"]),
            role="admin",
        )
        u2 = User(username="u2", password_hash=hash_password("u2pass22"))
        s.add_all([admin, u2])
        await s.commit()
        await s.refresh(admin)
        await s.refresh(u2)
        ws = Workspace(name="ws", owner_id=admin.id)
        s.add(ws)
        await s.commit()
        await s.refresh(ws)
        return admin.id, ws.id, u2.id


async def _make_skill(db, *, name, owner_id, visibility="public"):
    sk = Skill(
        name=name, description=f"desc {name}", owner_id=owner_id,
        visibility=visibility, dir_path="/skills/x",
    )
    db.add(sk)
    await db.commit()
    await db.refresh(sk)
    return sk


async def _make_mcp(db, *, name, owner_id, visibility="public"):
    m = MCP(
        name=name, type="stdio", config={"command": "x"}, owner_id=owner_id,
        visibility=visibility, read_only=False,
    )
    db.add(m)
    await db.commit()
    await db.refresh(m)
    return m


def _client():
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _login(ac):
    await ac.post("/api/auth/login", json=ADMIN)


async def test_mount_list_unmount_skill():
    _, ws_id, _ = await _seed()
    async with async_session_factory() as s:
        sk = await _make_skill(s, name="sk1", owner_id=1)
        sk_id = sk.id
    async with _client() as ac:
        await _login(ac)
        r = await ac.post(f"/api/admin/workspaces/{ws_id}/skills", json={"skill_id": sk_id})
        assert r.status_code == 201, r.text
        r = await ac.get(f"/api/admin/workspaces/{ws_id}/skills")
        assert r.json()["total"] == 1
        assert r.json()["items"][0]["name"] == "sk1"
        r = await ac.delete(f"/api/admin/workspaces/{ws_id}/skills/{sk_id}")
        assert r.status_code == 204
        r = await ac.get(f"/api/admin/workspaces/{ws_id}/skills")
        assert r.json()["total"] == 0


async def test_mount_private_skill_non_owner_403():
    """挂载 u2 的私有 Skill（admin 是 admin 可豁免，故用非 admin 用户）。"""
    async with async_session_factory() as s:
        u = User(username="u1", password_hash=hash_password("u1pass11"))
        s.add(u)
        await s.commit()
        await s.refresh(u)
        ws = Workspace(name="ws", owner_id=u.id)
        s.add(ws)
        await s.commit()
        await s.refresh(ws)
        ws_id = ws.id
        u2 = User(username="u2", password_hash=hash_password("u2pass22"))
        s.add(u2)
        await s.commit()
        await s.refresh(u2)
        sk = await _make_skill(s, name="priv", owner_id=u2.id, visibility="private")
        sk_id = sk.id
    async with _client() as ac:
        await ac.post("/api/auth/login", json={"username": "u1", "password": "u1pass11"})
        r = await ac.post(f"/api/admin/workspaces/{ws_id}/skills", json={"skill_id": sk_id})
        assert r.status_code == 403


async def test_mount_duplicate_skill_409():
    _, ws_id, _ = await _seed()
    async with async_session_factory() as s:
        sk = await _make_skill(s, name="sk1", owner_id=1)
        sk_id = sk.id
    async with _client() as ac:
        await _login(ac)
        await ac.post(f"/api/admin/workspaces/{ws_id}/skills", json={"skill_id": sk_id})
        r = await ac.post(f"/api/admin/workspaces/{ws_id}/skills", json={"skill_id": sk_id})
        assert r.status_code == 409


async def test_mount_skill_over_limit_422():
    """挂载第 51 个 Skill → 422（F3.5.6 上限 50）。"""
    _, ws_id, _ = await _seed()
    async with async_session_factory() as s:
        ids = []
        for i in range(MAX_SKILLS_PER_WS):
            sk = await _make_skill(s, name=f"sk{i}", owner_id=1)
            ids.append(sk.id)
        extra = await _make_skill(s, name="sk_extra", owner_id=1)
        extra_id = extra.id
    async with _client() as ac:
        await _login(ac)
        for sid in ids:
            r = await ac.post(f"/api/admin/workspaces/{ws_id}/skills", json={"skill_id": sid})
            assert r.status_code == 201
        r = await ac.post(f"/api/admin/workspaces/{ws_id}/skills", json={"skill_id": extra_id})
        assert r.status_code == 422


async def test_unmount_not_mounted_404():
    _, ws_id, _ = await _seed()
    async with async_session_factory() as s:
        sk = await _make_skill(s, name="sk1", owner_id=1)
        sk_id = sk.id
    async with _client() as ac:
        await _login(ac)
        r = await ac.delete(f"/api/admin/workspaces/{ws_id}/skills/{sk_id}")
        assert r.status_code == 404


async def test_mount_mcp_no_limit():
    """MCP 无 50 上限：挂载多个成功。"""
    _, ws_id, _ = await _seed()
    async with async_session_factory() as s:
        m1 = await _make_mcp(s, name="m1", owner_id=1)
        m2 = await _make_mcp(s, name="m2", owner_id=1)
        m1_id, m2_id = m1.id, m2.id
    async with _client() as ac:
        await _login(ac)
        r = await ac.post(f"/api/admin/workspaces/{ws_id}/mcps", json={"mcp_id": m1_id})
        assert r.status_code == 201
        r = await ac.post(f"/api/admin/workspaces/{ws_id}/mcps", json={"mcp_id": m2_id})
        assert r.status_code == 201
        r = await ac.get(f"/api/admin/workspaces/{ws_id}/mcps")
        assert r.json()["total"] == 2
        r = await ac.delete(f"/api/admin/workspaces/{ws_id}/mcps/{m1_id}")
        assert r.status_code == 204


async def test_mount_skill_not_found_404():
    _, ws_id, _ = await _seed()
    async with _client() as ac:
        await _login(ac)
        r = await ac.post(f"/api/admin/workspaces/{ws_id}/skills", json={"skill_id": 99999})
        assert r.status_code == 404
