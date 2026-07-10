"""Skill 广场测试（T3.1 验收）。"""

import io
import zipfile

import pytest
from httpx import ASGITransport, AsyncClient

from app.config import settings
from app.core.redis_client import redis as redis_client
from app.core.security import hash_password
from app.db.models import User, Workspace, WorkspaceSkill
from app.db.session import async_session_factory
from app.db.testing import reset_all
from app.main import app
from app.workspace.fs import skill_dir

ADMIN = {"username": "admin", "password": "adminpass1"}


@pytest.fixture(autouse=True)
async def _isolated(tmp_path_factory, monkeypatch):
    monkeypatch.setattr(settings, "data_dir", str(tmp_path_factory.mktemp("cf_data")))
    await reset_all()
    await redis_client.flushdb()
    yield
    await redis_client.flushdb()


def _skill_zip(name="s1", desc="d1", with_desc=True) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        front = "---\nname: " + name + "\n"
        if with_desc:
            front += "description: " + desc + "\n"
        front += "---\n# body\n"
        z.writestr("SKILL.md", front)
        z.writestr("resources/t.txt", "r")
        z.writestr("scripts/run.sh", "echo hi")
    return buf.getvalue()


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


async def test_create_skill_with_structure():
    await _seed()
    async with _client() as ac:
        await ac.post("/api/auth/login", json=ADMIN)
        r = await ac.post(
            "/api/admin/skills",
            files={"file": ("skill.zip", _skill_zip(), "application/zip")},
            data={"visibility": "public"},
        )
        assert r.status_code == 201
        body = r.json()
        assert body["name"] == "s1"
        d = skill_dir(body["id"])
        assert (d / "SKILL.md").exists()
        assert (d / "resources" / "t.txt").exists()
        assert (d / "scripts" / "run.sh").exists()


async def test_create_missing_description_rejected():
    await _seed()
    async with _client() as ac:
        await ac.post("/api/auth/login", json=ADMIN)
        r = await ac.post(
            "/api/admin/skills",
            files={"file": ("skill.zip", _skill_zip(with_desc=False), "application/zip")},
        )
        assert r.status_code == 422


async def test_create_dup_name_rejected():
    await _seed()
    async with _client() as ac:
        await ac.post("/api/auth/login", json=ADMIN)
        await ac.post(
            "/api/admin/skills",
            files={"file": ("skill.zip", _skill_zip(), "application/zip")},
        )
        r = await ac.post(
            "/api/admin/skills",
            files={"file": ("skill.zip", _skill_zip(), "application/zip")},
        )
        assert r.status_code == 422


async def test_list_and_search():
    await _seed()
    async with _client() as ac:
        await ac.post("/api/auth/login", json=ADMIN)
        await ac.post(
            "/api/admin/skills",
            files={"file": ("skill.zip", _skill_zip("alpha", "d"), "application/zip")},
        )
        await ac.post(
            "/api/admin/skills",
            files={"file": ("skill.zip", _skill_zip("beta", "d"), "application/zip")},
        )
        assert (await ac.get("/api/admin/skills")).json()["total"] == 2
        assert (await ac.get("/api/admin/skills?q=alp")).json()["total"] == 1


async def test_get_mounted_count_and_delete_rejected():
    admin = await _seed()
    async with _client() as ac:
        await ac.post("/api/auth/login", json=ADMIN)
        sid = (
            await ac.post(
                "/api/admin/skills",
                files={"file": ("skill.zip", _skill_zip(), "application/zip")},
            )
        ).json()["id"]
        async with async_session_factory() as s:
            ws = Workspace(name="w", owner_id=admin.id)
            s.add(ws)
            await s.commit()
            await s.refresh(ws)
            s.add(WorkspaceSkill(workspace_id=ws.id, skill_id=sid))
            await s.commit()
        body = (await ac.get(f"/api/admin/skills/{sid}")).json()
        assert body["mounted_count"] == 1
        assert (await ac.delete(f"/api/admin/skills/{sid}")).status_code == 422
