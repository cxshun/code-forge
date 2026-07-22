"""runtime 工厂测试（端到端集成件）。"""

import pytest

from app.agent.runtime import (
    build_registry,
    fetch_quote_text,
    make_provider,
    resolve_cwd,
)
from app.config import settings
from app.db.models import GitRepo, Skill, User, Workspace, WorkspaceSkill
from app.db.session import async_session_factory
from app.db.testing import reset_all
from app.providers.anthropic_provider import AnthropicProvider
from app.workspace.fs import create_workspace_skeleton

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
async def _isolated(tmp_path_factory, monkeypatch):
    monkeypatch.setattr(settings, "data_dir", str(tmp_path_factory.mktemp("cf_data")))
    await reset_all()
    yield


async def _seed_ws_with_repo_and_skill():
    async with async_session_factory() as s:
        u = User(username="u", password_hash="x", role="admin")
        s.add(u)
        await s.commit()
        await s.refresh(u)
        ws = Workspace(name="w", owner_id=u.id)
        s.add(ws)
        await s.commit()
        await s.refresh(ws)
        create_workspace_skeleton(ws.id)
        repo = GitRepo(workspace_id=ws.id, url="https://x", clone_status="ready")
        s.add(repo)
        await s.commit()
        await s.refresh(repo)
        sk = Skill(
            name="lint", description="lint skill", owner_id=u.id,
            visibility="public", dir_path="/skills/x",
        )
        s.add(sk)
        await s.commit()
        await s.refresh(sk)
        s.add(WorkspaceSkill(workspace_id=ws.id, skill_id=sk.id))
        await s.commit()
        return ws.id, repo.id, sk.name


async def test_build_registry_builtins_and_skills():
    ws_id, _, skill_name = await _seed_ws_with_repo_and_skill()
    async with async_session_factory() as db:
        registry, descs, mcp_cleanup = await build_registry(db, ws_id, make_provider())
    names = set(registry.names())
    assert {"Read", "Glob", "Grep", "Write", "Edit", "Bash"} <= names
    assert "Agent" in names  # T5.9：子代理工具已接线进 build_registry
    assert f"skill__{skill_name}" in names
    assert any(f"skill__{skill_name}" in d for d in descs)
    assert registry.is_readonly("Read")
    assert not registry.is_readonly("Write")
    # 无 MCP 挂载时 cleanup 为 None
    assert mcp_cleanup is None


async def test_resolve_cwd_prefers_cwd_repo_id():
    ws_id, repo_id, _ = await _seed_ws_with_repo_and_skill()
    async with async_session_factory() as s:
        ws = await s.get(Workspace, ws_id)
        ws.cwd_repo_id = repo_id
        await s.commit()
        await s.refresh(ws)
        cwd = await resolve_cwd(s, ws)
    assert cwd == str(repo_id)


async def test_resolve_cwd_falls_back_to_first_repo():
    ws_id, repo_id, _ = await _seed_ws_with_repo_and_skill()
    async with async_session_factory() as s:
        ws = await s.get(Workspace, ws_id)
        assert ws.cwd_repo_id is None
        cwd = await resolve_cwd(s, ws)
    assert cwd == str(repo_id)


async def test_resolve_cwd_no_repo_empty():
    async with async_session_factory() as s:
        u = User(username="u2", password_hash="x", role="admin")
        s.add(u)
        await s.commit()
        await s.refresh(u)
        ws = Workspace(name="w2", owner_id=u.id)
        s.add(ws)
        await s.commit()
        await s.refresh(ws)
        cwd = await resolve_cwd(s, ws)
    assert cwd == ""


async def test_make_provider_returns_anthropic(monkeypatch):
    # 确保全局未配 openai_compatible → make_provider 回退 Anthropic
    monkeypatch.setattr(settings, "openai_compatible_api_key", "")
    monkeypatch.setattr(settings, "openai_compatible_base_url", "")
    monkeypatch.setattr(settings, "openai_compatible_model", "")
    p = make_provider()
    assert isinstance(p, AnthropicProvider)


class _FakeBody:
    def __init__(self, content):
        self.content = content


class _FakeMsg:
    def __init__(self, content, msg_type="text"):
        self.body = _FakeBody(content)
        self.msg_type = msg_type


class _FakeMsgData:
    def __init__(self, items):
        self.items = items


class _FakeClient:
    def __init__(self, data=None, exc=None):
        self._data = data
        self._exc = exc

    async def get_message(self, parent_id):
        if self._exc:
            raise self._exc
        return self._data


async def test_fetch_quote_text_ok():
    import json as _json

    data = _FakeMsgData([_FakeMsg(_json.dumps({"text": "用 ruff 不用 black"}), "text")])
    out = await fetch_quote_text(_FakeClient(data), "om_x")
    assert out is not None
    assert "用 ruff 不用 black" in out
    assert out.startswith("**引用消息：**")


async def test_fetch_quote_text_no_parent():
    assert await fetch_quote_text(_FakeClient(None), None) is None


async def test_fetch_quote_text_empty_content():
    import json as _json

    data = _FakeMsgData([_FakeMsg(_json.dumps({"text": ""}), "text")])
    assert await fetch_quote_text(_FakeClient(data), "om_x") is None


async def test_fetch_quote_text_get_message_none():
    assert await fetch_quote_text(_FakeClient(None), "om_x") is None


async def test_fetch_quote_text_swallows_exception():
    assert await fetch_quote_text(_FakeClient(exc=RuntimeError("boom")), "om_x") is None
