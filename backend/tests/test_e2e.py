"""T11.1 端到端测试：核心闭环 + Trace 回放 + 多租户隔离。

覆盖 spec §2.2 典型场景与验收标准：
- 核心闭环：start_run → tool 调用 → JSONL 落盘 → span 入库 → trace 回放
- Memory 写入：Agent 通过 Write 工具写 memory 文件
- 多租户隔离：WS 间 traces / runs / memory / span payload 不可互访（D31 / NF4.6.1）
- Handler 全链路：飞书消息 → handler → RunQueue → Agent Loop → 卡片回复
"""

import json

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select

from app.agent.queue import run_queue
from app.agent.run import start_run
from app.config import settings
from app.core.redis_client import redis as redis_client
from app.core.security import hash_password
from app.db.models import FeishuChat, GitRepo, Run, RunStatus, Span, User, Workspace
from app.db.session import async_session_factory
from app.db.testing import reset_all
from app.main import app
from app.observability.buffer import span_buffer
from app.providers.mock_provider import MockProvider
from app.tools.builtin.read import ReadTool
from app.tools.builtin.write import WriteTool
from app.tools.registry import ToolRegistry
from app.workspace.fs import (
    create_chat_memory_skeleton,
    create_workspace_skeleton,
    workspace_root,
)

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
async def _isolated(tmp_path_factory, monkeypatch):
    monkeypatch.setattr(settings, "data_dir", str(tmp_path_factory.mktemp("cf_data")))
    monkeypatch.setattr(settings, "anthropic_api_key", "sk-test")
    await reset_all()
    await redis_client.flushdb()
    span_buffer.start()
    yield
    await span_buffer.stop()
    await redis_client.flushdb()


async def _seed_ws(
    *, username: str = "admin", role: str = "admin"
) -> tuple[int, int, int, int]:
    """Seed user → workspace → repo → chat + filesystem skeleton.

    Returns (user_id, ws_id, chat_db_id, repo_id).
    Repo directory created as repos/{repo_id}/ matching resolve_cwd output.
    """
    async with async_session_factory() as s:
        u = User(username=username, password_hash=hash_password("p"), role=role)
        s.add(u)
        await s.commit()
        await s.refresh(u)
        ws = Workspace(name=f"ws-{username}", owner_id=u.id)
        s.add(ws)
        await s.commit()
        await s.refresh(ws)
        repo = GitRepo(workspace_id=ws.id, url="https://x", clone_status="ready")
        s.add(repo)
        await s.commit()
        await s.refresh(repo)
        chat = FeishuChat(
            workspace_id=ws.id,
            app_id=f"cli_{username}",
            chat_id=f"oc_{username}",
            chat_name="g",
        )
        s.add(chat)
        await s.commit()
        await s.refresh(chat)
        create_workspace_skeleton(ws.id)
        repo_dir = workspace_root(ws.id) / "repos" / str(repo.id)
        repo_dir.mkdir(parents=True, exist_ok=True)
        (repo_dir / "hello.txt").write_text("world")
        return u.id, ws.id, chat.id, repo.id


# =====================================================================
# 1. Core loop: tool call → trace spans → JSONL
# =====================================================================

async def test_e2e_tool_call_produces_trace_spans():
    """核心闭环：start_run with tool call → spans in DB with correct tree structure."""
    _, ws_id, chat_id, repo_id = await _seed_ws()
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
        cwd=str(repo_id),
    )
    assert final == "saw world"

    async with async_session_factory() as s:
        run = (
            await s.scalars(select(Run).where(Run.workspace_id == ws_id))
        ).first()
        assert run is not None
        assert run.status == RunStatus.completed.value

        spans = (
            await s.scalars(
                select(Span).where(Span.run_id == run.id).order_by(Span.span_order)
            )
        ).all()
        assert len(spans) >= 2

        root = spans[0]
        assert root.span_type == "run"
        assert root.status == "ok"
        assert root.parent_span_id is None

        for sp in spans[1:]:
            assert sp.trace_id == root.trace_id
            assert sp.parent_span_id is not None

        span_types = {sp.span_type for sp in spans}
        assert "llm" in span_types
        assert "tool" in span_types


async def test_e2e_jsonl_and_trace_separate_storage():
    """D29: session JSONL and trace payload are stored separately."""
    _, ws_id, chat_id, repo_id = await _seed_ws()
    create_chat_memory_skeleton(ws_id, chat_id)
    provider = MockProvider(mock_text="done")
    registry = ToolRegistry().register(ReadTool())

    await start_run(
        ws_id=ws_id,
        feishu_chat_id=chat_id,
        user_message="hi",
        provider=provider,
        registry=registry,
        cwd=str(repo_id),
    )

    sessions_dir = (
        workspace_root(ws_id) / "chats" / str(chat_id) / "sessions"
    )
    jsonl_files = list(sessions_dir.glob("*.jsonl"))
    assert len(jsonl_files) == 1
    msgs = [json.loads(line) for line in jsonl_files[0].read_text().splitlines()]
    assert msgs[0]["role"] == "user"
    assert msgs[0]["content"] == "hi"

    traces_dir = (
        workspace_root(ws_id) / "chats" / str(chat_id) / "traces"
    )
    assert traces_dir.exists()


# =====================================================================
# 2. Memory write during run
# =====================================================================

async def test_e2e_memory_write_via_write_tool():
    """Agent writes memory file via Write tool during run (D22)."""
    _, ws_id, chat_id, repo_id = await _seed_ws()
    create_chat_memory_skeleton(ws_id, chat_id)

    provider = MockProvider(
        mock_tool_name="Write",
        mock_tool_input={
            "path": "memory/feedback.md",
            "content": "# Feedback\nUser prefers ruff format",
        },
        mock_text="已记下偏好",
    )
    registry = ToolRegistry().register(WriteTool())

    await start_run(
        ws_id=ws_id,
        feishu_chat_id=chat_id,
        user_message="记住我用 ruff",
        provider=provider,
        registry=registry,
        cwd=str(repo_id),
    )

    mem_file = (
        workspace_root(ws_id) / "chats" / str(chat_id) / "memory" / "feedback.md"
    )
    assert mem_file.exists()
    assert "ruff" in mem_file.read_text()


# =====================================================================
# 3. Multi-tenant isolation (D31)
# =====================================================================

async def _login_client(username: str) -> AsyncClient:
    client = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
    await client.post(
        "/api/auth/login", json={"username": username, "password": "p"}
    )
    return client


async def test_e2e_cross_ws_trace_access_denied():
    """D31: User B cannot access WS A's traces."""
    _, ws_a, chat_a, repo_a = await _seed_ws(username="alice")
    _, ws_b, _, _ = await _seed_ws(username="bob", role="user")

    provider = MockProvider(mock_text="ok")
    registry = ToolRegistry().register(ReadTool())
    await start_run(
        ws_id=ws_a,
        feishu_chat_id=chat_a,
        user_message="hi",
        provider=provider,
        registry=registry,
        cwd=str(repo_a),
    )

    async with async_session_factory() as s:
        count_a = await s.scalar(
            select(func.count()).select_from(Span).where(Span.workspace_id == ws_a)
        )
        assert count_a > 0

    client_b = await _login_client("bob")
    resp = await client_b.get(f"/api/admin/workspaces/{ws_a}/traces")
    assert resp.status_code in (403, 404)

    resp = await client_b.get(f"/api/admin/workspaces/{ws_a}/runs")
    assert resp.status_code in (403, 404)

    resp = await client_b.get(f"/api/admin/workspaces/{ws_b}/traces")
    assert resp.status_code == 200

    await client_b.aclose()


async def test_e2e_cross_ws_memory_access_denied():
    """D31: User B cannot access WS A's memory files."""
    _, ws_a, chat_a, _ = await _seed_ws(username="alice")
    _, ws_b, chat_b, _ = await _seed_ws(username="bob", role="user")

    client_b = await _login_client("bob")
    resp = await client_b.get(
        f"/api/admin/workspaces/{ws_a}/chats/{chat_a}/memory"
    )
    assert resp.status_code in (403, 404)

    resp = await client_b.get(
        f"/api/admin/workspaces/{ws_b}/chats/{chat_b}/memory"
    )
    assert resp.status_code == 200

    await client_b.aclose()


async def test_e2e_cross_ws_span_payload_denied():
    """D31: User B cannot read WS A's span payload (anti path traversal)."""
    _, ws_a, chat_a, repo_a = await _seed_ws(username="alice")
    await _seed_ws(username="bob", role="user")

    provider = MockProvider(
        mock_tool_name="Read",
        mock_tool_input={"path": "hello.txt"},
        mock_text="ok",
    )
    registry = ToolRegistry().register(ReadTool())
    await start_run(
        ws_id=ws_a,
        feishu_chat_id=chat_a,
        user_message="read",
        provider=provider,
        registry=registry,
        cwd=str(repo_a),
    )

    async with async_session_factory() as s:
        span = (
            await s.scalars(
                select(Span).where(Span.workspace_id == ws_a).limit(1)
            )
        ).first()
        assert span is not None
        span_id = span.span_id

    client_b = await _login_client("bob")
    resp = await client_b.get(
        f"/api/admin/workspaces/{ws_a}/spans/{span_id}/payload",
        params={"suffix": "request"},
    )
    assert resp.status_code in (403, 404)

    await client_b.aclose()


# =====================================================================
# 4. Handler full chain: Feishu message → Run → cards
# =====================================================================

async def test_e2e_handler_to_run_with_cards(monkeypatch):
    """Full chain: Feishu message → handler → RunQueue → Agent Loop → card reply."""
    from app.feishu import handler as handler_module

    _, ws_id, _, _ = await _seed_ws()

    class _FakeClient:
        def __init__(self):
            self.sent: list[dict] = []
            self.updated: list[tuple[str, dict]] = []

        async def send_card(self, chat_id, card):
            self.sent.append(card)
            return f"om_card_{len(self.sent)}"

        async def update_card(self, message_id, card):
            self.updated.append((message_id, card))

        async def get_message(self, parent_id):
            return None

    fake_client = _FakeClient()
    monkeypatch.setattr(
        handler_module, "FeishuClient", lambda *a, **k: fake_client
    )

    mock_provider = MockProvider(mock_text="hello from agent")
    monkeypatch.setattr(handler_module, "make_provider", lambda: mock_provider)

    content = json.dumps({"text": '<at user_id="ou_bot">bot</at> 你好'})
    event = {
        "header": {"app_id": "cli_admin"},
        "event": {
            "sender": {"sender_id": {"open_id": "ou_sender123"}},
            "message": {
                "chat_id": "oc_admin",
                "message_id": "om_msg_e2e_1",
                "message_type": "text",
                "chat_type": "group",
                "content": content,
                "parent_id": None,
                "mentions": [{"id": {"open_id": "ou_bot"}}],
            },
        },
    }

    await handler_module.handle_message(event, "cli_admin", "secret", "ou_bot")

    async with async_session_factory() as s:
        run = (
            await s.scalars(select(Run).where(Run.workspace_id == ws_id))
        ).first()
        assert run is not None
        run_id = run.id

    await run_queue.join(run_id)

    async with async_session_factory() as s:
        run = await s.get(Run, run_id)
        assert run.status == RunStatus.completed.value

        span_count = await s.scalar(
            select(func.count()).select_from(Span).where(Span.run_id == run_id)
        )
        assert span_count > 0

    assert len(fake_client.sent) > 0 or len(fake_client.updated) > 0
