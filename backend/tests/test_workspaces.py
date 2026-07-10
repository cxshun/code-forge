"""Workspace CRUD + 异步任务测试（T2.1 / T2.6 验收）。"""

import asyncio

import pytest
from httpx import ASGITransport, AsyncClient

from app.config import settings
from app.core.redis_client import redis as redis_client
from app.core.security import hash_password
from app.db.models import Skill, User, WorkspaceSkill
from app.db.session import async_session_factory
from app.db.testing import reset_all
from app.main import app
from app.workspace.fs import workspace_root

ADMIN = {"username": "admin", "password": "adminpass1"}
PLAIN = {"username": "alice", "password": "alicepass1"}


@pytest.fixture(autouse=True)
async def _isolated(tmp_path_factory, monkeypatch):
    monkeypatch.setattr(settings, "data_dir", str(tmp_path_factory.mktemp("cf_data")))
    await reset_all()
    await redis_client.flushdb()
    yield
    await redis_client.flushdb()


async def _seed() -> User:
    async with async_session_factory() as s:
        admin = User(
            username=ADMIN["username"],
            password_hash=hash_password(ADMIN["password"]),
            role="admin",
        )
        s.add_all(
            [
                admin,
                User(
                    username=PLAIN["username"],
                    password_hash=hash_password(PLAIN["password"]),
                    role="user",
                ),
            ]
        )
        await s.commit()
        await s.refresh(admin)
        return admin


def _client():
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def test_create_list_get_patch():
    admin = await _seed()
    async with _client() as ac:
        await ac.post("/api/auth/login", json=ADMIN)
        r = await ac.post("/api/admin/workspaces", json={"name": "ws1"})
        assert r.status_code == 201
        ws_id = r.json()["id"]
        assert workspace_root(ws_id).exists()
        assert (await ac.get("/api/admin/workspaces")).json()["total"] == 1
        d = await ac.get(f"/api/admin/workspaces/{ws_id}")
        assert d.json()["repos"] == []
        p = await ac.patch(
            f"/api/admin/workspaces/{ws_id}", json={"name": "ws1-renamed"}
        )
        assert p.json()["name"] == "ws1-renamed"
    assert admin.id  # sanity


async def test_delete_cascade_and_task_poll():
    await _seed()
    async with _client() as ac:
        await ac.post("/api/auth/login", json=ADMIN)
        ws_id = (await ac.post("/api/admin/workspaces", json={"name": "todelete"})).json()["id"]
        r = await ac.delete(f"/api/admin/workspaces/{ws_id}")
        assert r.status_code == 202
        task_id = r.json()["task_id"]

        status = None
        for _ in range(100):
            t = await ac.get(f"/api/admin/tasks/{task_id}")
            status = t.json()["status"]
            if status in ("done", "failed"):
                break
            await asyncio.sleep(0.05)
        assert status == "done"
        assert not workspace_root(ws_id).exists()
        assert (await ac.get("/api/admin/workspaces")).json()["total"] == 0


async def test_delete_with_mount_rejected():
    admin = await _seed()
    async with _client() as ac:
        await ac.post("/api/auth/login", json=ADMIN)
        ws_id = (await ac.post("/api/admin/workspaces", json={"name": "ws"})).json()["id"]
        async with async_session_factory() as s:
            sk = Skill(
                name="s1", description="d", owner_id=admin.id, dir_path="/tmp/s1"
            )
            s.add(sk)
            await s.commit()
            await s.refresh(sk)
            s.add(WorkspaceSkill(workspace_id=ws_id, skill_id=sk.id))
            await s.commit()
        r = await ac.delete(f"/api/admin/workspaces/{ws_id}")
        assert r.status_code == 422


async def test_non_owner_forbidden():
    await _seed()
    async with _client() as ac:
        await ac.post("/api/auth/login", json=ADMIN)
        ws_id = (await ac.post("/api/admin/workspaces", json={"name": "ws"})).json()["id"]
        await ac.post("/api/auth/login", json=PLAIN)
        assert (await ac.get(f"/api/admin/workspaces/{ws_id}")).status_code == 403


async def test_task_not_found():
    await _seed()
    async with _client() as ac:
        await ac.post("/api/auth/login", json=ADMIN)
        assert (await ac.get("/api/admin/tasks/999999")).status_code == 404
