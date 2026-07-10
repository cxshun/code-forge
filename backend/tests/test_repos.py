"""Git Repo 挂载与同步测试（T2.2 验收，用本地 bare repo 避免网络依赖）。"""

import asyncio
import subprocess

import pytest
from httpx import ASGITransport, AsyncClient

from app.config import settings
from app.core.redis_client import redis as redis_client
from app.core.security import hash_password
from app.db.models import User, Workspace
from app.db.session import async_session_factory
from app.db.testing import reset_all
from app.main import app
from app.workspace.fs import workspace_root

ADMIN = {"username": "admin", "password": "adminpass1"}


@pytest.fixture(autouse=True)
async def _isolated(tmp_path_factory, monkeypatch):
    monkeypatch.setattr(settings, "data_dir", str(tmp_path_factory.mktemp("cf_data")))
    await reset_all()
    await redis_client.flushdb()
    yield
    await redis_client.flushdb()


def _make_bare_repo(parent) -> str:
    src = parent / "src"
    src.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=src, check=True)
    (src / "README.md").write_text("hello")
    subprocess.run(["git", "add", "."], cwd=src, check=True)
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "init"],
        cwd=src,
        check=True,
    )
    bare = parent / "bare.git"
    subprocess.run(["git", "clone", "--bare", "-q", str(src), str(bare)], check=True)
    return str(bare)


async def _seed_admin_ws() -> tuple[int, int]:
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
        s.add(ws)
        await s.commit()
        await s.refresh(ws)
        return admin.id, ws.id


def _client():
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def test_clone_local_bare_repo(tmp_path_factory):
    _, ws_id = await _seed_admin_ws()
    bare = _make_bare_repo(tmp_path_factory.mktemp("git"))
    async with _client() as ac:
        await ac.post("/api/auth/login", json=ADMIN)
        r = await ac.post(f"/api/admin/workspaces/{ws_id}/repos", json={"url": bare})
        assert r.status_code == 202
        repo_id = r.json()["repo_id"]
        task_id = r.json()["task_id"]

        status = None
        for _ in range(200):
            t = await ac.get(f"/api/admin/tasks/{task_id}")
            status = t.json()["status"]
            if status in ("done", "failed"):
                break
            await asyncio.sleep(0.05)
        assert status == "done", t.json()

        repo = (await ac.get(f"/api/admin/workspaces/{ws_id}/repos/{repo_id}")).json()
        assert repo["clone_status"] == "ready"
        assert (workspace_root(ws_id) / "repos" / str(repo_id) / "README.md").exists()


async def test_clone_invalid_url_fails(tmp_path_factory):
    _, ws_id = await _seed_admin_ws()
    async with _client() as ac:
        await ac.post("/api/auth/login", json=ADMIN)
        r = await ac.post(
            f"/api/admin/workspaces/{ws_id}/repos",
            json={"url": "/nonexistent/path/.git"},
        )
        repo_id = r.json()["repo_id"]
        task_id = r.json()["task_id"]
        status = None
        for _ in range(200):
            t = await ac.get(f"/api/admin/tasks/{task_id}")
            status = t.json()["status"]
            if status in ("done", "failed"):
                break
            await asyncio.sleep(0.05)
        assert status == "failed"
        repo = (await ac.get(f"/api/admin/workspaces/{ws_id}/repos/{repo_id}")).json()
        assert repo["clone_status"] == "failed"
