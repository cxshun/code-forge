"""AGENT.md 读写测试（T2.5 验收）。"""

import pytest
from httpx import ASGITransport, AsyncClient

from app.config import settings
from app.core.redis_client import redis as redis_client
from app.core.security import hash_password
from app.db.models import GitRepo, User
from app.db.session import async_session_factory
from app.db.testing import reset_all
from app.main import app
from app.workspace.fs import create_workspace_skeleton, workspace_root

ADMIN = {"username": "admin", "password": "adminpass1"}


@pytest.fixture(autouse=True)
async def _isolated(tmp_path_factory, monkeypatch):
    monkeypatch.setattr(settings, "data_dir", str(tmp_path_factory.mktemp("cf_data")))
    await reset_all()
    await redis_client.flushdb()
    yield
    await redis_client.flushdb()


async def _seed_ws() -> tuple[int, int]:
    async with async_session_factory() as s:
        admin = User(
            username=ADMIN["username"],
            password_hash=hash_password(ADMIN["password"]),
            role="admin",
        )
        s.add(admin)
        await s.commit()
        await s.refresh(admin)
        from app.db.models import Workspace

        ws = Workspace(name="ws", owner_id=admin.id)
        s.add(ws)
        await s.commit()
        await s.refresh(ws)
        create_workspace_skeleton(ws.id)
        return admin.id, ws.id


def _client():
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def test_ws_agent_md_empty_then_write():
    _, ws_id = await _seed_ws()
    async with _client() as ac:
        await ac.post("/api/auth/login", json=ADMIN)
        r = await ac.get(f"/api/admin/workspaces/{ws_id}/agent-md")
        assert r.status_code == 200
        assert r.json()["content"] == ""
        await ac.put(
            f"/api/admin/workspaces/{ws_id}/agent-md", json={"content": "# rules\n"}
        )
        r2 = await ac.get(f"/api/admin/workspaces/{ws_id}/agent-md")
        assert r2.json()["content"] == "# rules\n"
        assert (workspace_root(ws_id) / "AGENT.md").read_text() == "# rules\n"


async def test_repo_agent_md_readonly_405():
    _, ws_id = await _seed_ws()
    # 建一个 repo 记录 + 目录 + AGENT.md
    async with async_session_factory() as s:
        repo = GitRepo(
            workspace_id=ws_id, url="https://x", clone_status="ready", local_path="r"
        )
        s.add(repo)
        await s.commit()
        await s.refresh(repo)
        repo_id = repo.id
    repo_dir = workspace_root(ws_id) / "repos" / str(repo_id)
    repo_dir.mkdir(parents=True, exist_ok=True)
    (repo_dir / "AGENT.md").write_text("# repo rules\n", encoding="utf-8")

    async with _client() as ac:
        await ac.post("/api/auth/login", json=ADMIN)
        r = await ac.get(f"/api/admin/workspaces/{ws_id}/repos/{repo_id}/agent-md")
        assert r.json()["content"] == "# repo rules\n"
        # Repo 级 PUT → 405（只读）
        p = await ac.put(
            f"/api/admin/workspaces/{ws_id}/repos/{repo_id}/agent-md",
            json={"content": "x"},
        )
        assert p.status_code == 405
