"""Skill 工具测试（T5.7 验收）。"""


import pytest

from app.db.models import Skill, User, Workspace, WorkspaceSkill
from app.db.session import async_session_factory
from app.db.testing import reset_all
from app.tools.base import ToolContext
from app.tools.skill import SkillTool, build_skill_tools
from app.workspace.fs import skill_dir

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
async def _reset(tmp_path_factory, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "data_dir", str(tmp_path_factory.mktemp("cf_data")))
    await reset_all()
    yield


async def test_skill_tool_returns_md():
    async with async_session_factory() as s:
        admin = User(username="a", password_hash="x", role="admin")
        s.add(admin)
        await s.commit()
        await s.refresh(admin)
        ws = Workspace(name="w", owner_id=admin.id)
        s.add(ws)
        await s.commit()
        await s.refresh(ws)
        sk = Skill(name="py-test", description="gen python tests", owner_id=admin.id, dir_path="")
        s.add(sk)
        await s.commit()
        await s.refresh(sk)
        s.add(WorkspaceSkill(workspace_id=ws.id, skill_id=sk.id))
        # 写 SKILL.md
        (skill_dir(sk.id)).mkdir(parents=True, exist_ok=True)
        (skill_dir(sk.id) / "SKILL.md").write_text("# py-test\n## 工作流\n...")
        await s.commit()
        ws_id, skill_id = ws.id, sk.id

    # name 格式 skill__{name}
    tool = SkillTool("py-test", "gen python tests", skill_dir(skill_id) / "SKILL.md")
    assert tool.name == "skill__py-test"
    assert tool.read_only is True

    ctx = ToolContext(ws_id=ws_id, workspaces_root="/tmp")
    result = await tool.run({}, ctx)
    assert "# py-test" in result


async def test_build_skill_tools_from_db():
    async with async_session_factory() as s:
        admin = User(username="b", password_hash="x", role="admin")
        s.add(admin)
        await s.commit()
        await s.refresh(admin)
        ws = Workspace(name="w2", owner_id=admin.id)
        s.add(ws)
        await s.commit()
        await s.refresh(ws)
        sk = Skill(name="code-review", description="review code", owner_id=admin.id, dir_path="")
        s.add(sk)
        await s.commit()
        await s.refresh(sk)
        s.add(WorkspaceSkill(workspace_id=ws.id, skill_id=sk.id))
        await s.commit()
        ws_id = ws.id

    async with async_session_factory() as s:
        tools = await build_skill_tools(s, ws_id)
    assert len(tools) == 1
    assert tools[0].name == "skill__code-review"
