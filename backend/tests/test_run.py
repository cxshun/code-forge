"""Run 编排集成测试（T5.4 验收）：start_run E2E。"""

import json

import pytest
from sqlalchemy import select

from app.agent.run import start_run
from app.config import settings
from app.core.redis_client import redis as redis_client
from app.db.models import FeishuChat, Run, RunStatus, User, Workspace
from app.db.session import async_session_factory
from app.db.testing import reset_all
from app.providers.mock_provider import MockProvider
from app.tools.builtin.read import ReadTool
from app.tools.builtin.write import WriteTool
from app.tools.registry import ToolRegistry
from app.workspace.fs import create_workspace_skeleton, workspace_root

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
async def _isolated(tmp_path_factory, monkeypatch):
    monkeypatch.setattr(settings, "data_dir", str(tmp_path_factory.mktemp("cf_data")))
    await reset_all()
    await redis_client.flushdb()
    yield
    await redis_client.flushdb()


async def _seed() -> tuple[int, int]:
    async with async_session_factory() as s:
        admin = User(username="a", password_hash="x", role="admin")
        s.add(admin)
        await s.commit()
        await s.refresh(admin)
        ws = Workspace(name="w", owner_id=admin.id)
        s.add(ws)
        await s.commit()
        await s.refresh(ws)
        chat = FeishuChat(
            workspace_id=ws.id, app_id="cli_x", chat_id="oc_x", chat_name="g"
        )
        s.add(chat)
        await s.commit()
        await s.refresh(chat)
        create_workspace_skeleton(ws.id)
        repo = workspace_root(ws.id) / "repos" / "myrepo"
        repo.mkdir(parents=True, exist_ok=True)
        (repo / "hello.txt").write_text("world")
        return ws.id, chat.id


async def test_start_run_e2e_completed_and_jsonl():
    ws_id, chat_id = await _seed()
    provider = MockProvider(mock_text="done")
    registry = ToolRegistry().register(ReadTool()).register(WriteTool())

    final = await start_run(
        ws_id=ws_id,
        feishu_chat_id=chat_id,
        user_message="hi",
        provider=provider,
        registry=registry,
        cwd="myrepo",
    )
    assert final == "done"

    async with async_session_factory() as s:
        run = (await s.scalars(select(Run).where(Run.workspace_id == ws_id))).first()
        assert run is not None
        assert run.status == RunStatus.completed.value

    # JSONL 落盘
    sessions_dir = workspace_root(ws_id) / "chats" / str(chat_id) / "sessions"
    jsonl_files = list(sessions_dir.glob("*.jsonl"))
    assert len(jsonl_files) == 1
    lines = jsonl_files[0].read_text(encoding="utf-8").splitlines()
    msgs = [json.loads(line) for line in lines]
    assert msgs[0]["role"] == "user"
    assert msgs[0]["content"] == "hi"


async def test_start_run_with_tool_executed():
    ws_id, chat_id = await _seed()
    provider = MockProvider(
        mock_tool_name="Read",
        mock_tool_input={"path": "hello.txt"},
        mock_text="saw world",
    )
    registry = ToolRegistry().register(ReadTool())

    final = await start_run(
        ws_id=ws_id,
        feishu_chat_id=chat_id,
        user_message="read hello",
        provider=provider,
        registry=registry,
        cwd="myrepo",
    )
    assert final == "saw world"
    # tool_result（含 "world"）落盘进 JSONL
    sessions_dir = workspace_root(ws_id) / "chats" / str(chat_id) / "sessions"
    body = next(sessions_dir.glob("*.jsonl")).read_text(encoding="utf-8")
    assert "world" in body
