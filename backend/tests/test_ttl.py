"""T10.4 TTL 清理测试。

验证：span 行过期删除、payload 文件清理 + DB ref 置空、旧 Run 保留上限。
"""

import json
from datetime import UTC, datetime, timedelta

import pytest

from app.config import settings
from app.core.redis_client import redis as redis_client
from app.core.security import hash_password
from app.db.models import FeishuChat, GitRepo, Run, RunStatus, Session, Span, User, Workspace
from app.db.session import async_session_factory
from app.db.testing import reset_all
from app.observability.ttl import cleanup_excess_runs, cleanup_old_payloads, cleanup_old_spans
from app.workspace.fs import create_workspace_skeleton, workspace_root

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
async def _isolated(tmp_path_factory, monkeypatch):
    monkeypatch.setattr(settings, "data_dir", str(tmp_path_factory.mktemp("cf_data")))
    await reset_all()
    await redis_client.flushdb()
    yield
    await redis_client.flushdb()


async def _seed_ws_and_chat() -> tuple[int, int]:
    async with async_session_factory() as s:
        u = User(username="admin", password_hash=hash_password("p"), role="admin")
        s.add(u)
        await s.commit()
        await s.refresh(u)
        ws = Workspace(name="w", owner_id=u.id)
        s.add(ws)
        await s.commit()
        await s.refresh(ws)
        repo = GitRepo(workspace_id=ws.id, url="https://x", clone_status="ready")
        s.add(repo)
        await s.commit()
        chat = FeishuChat(workspace_id=ws.id, app_id="cli_x", chat_id="oc_x", chat_name="g")
        s.add(chat)
        await s.commit()
        await s.refresh(chat)
        create_workspace_skeleton(ws.id)
        return ws.id, chat.id


async def test_cleanup_old_spans():
    """Spans older than span_ttl_days are deleted."""
    ws_id, chat_id = await _seed_ws_and_chat()
    monkeypatch_ttl_days(1)

    old = datetime.now(UTC) - timedelta(days=5)
    recent = datetime.now(UTC) - timedelta(minutes=10)

    async with async_session_factory() as s:
        sess = Session(feishu_chat_id=chat_id)
        s.add(sess)
        await s.commit()
        await s.refresh(sess)
        run = Run(session_id=sess.id, workspace_id=ws_id, feishu_chat_id=chat_id, status=RunStatus.completed.value)
        s.add(run)
        await s.commit()
        await s.refresh(run)

        s.add(Span(
            span_id="o" * 32, trace_id="t" * 32, span_type="llm", status="ok",
            workspace_id=ws_id, feishu_chat_id=chat_id, session_id=sess.id, run_id=run.id,
            started_at=old,
        ))
        s.add(Span(
            span_id="r" * 32, trace_id="t" * 32, span_type="llm", status="ok",
            workspace_id=ws_id, feishu_chat_id=chat_id, session_id=sess.id, run_id=run.id,
            started_at=recent,
        ))
        await s.commit()

    deleted = await cleanup_old_spans()
    assert deleted == 1

    async with async_session_factory() as s:
        from sqlalchemy import select
        remaining = (await s.scalars(select(Span))).all()
        assert len(remaining) == 1
        assert remaining[0].span_id == "r" * 32


async def test_cleanup_old_payloads():
    """Payload files older than payload_ttl_days are deleted and DB ref cleared."""
    ws_id, chat_id = await _seed_ws_and_chat()
    monkeypatch_ttl_days(span_days=99, payload_days=1)

    old_time = datetime.now(UTC) - timedelta(days=5)

    async with async_session_factory() as s:
        sess = Session(feishu_chat_id=chat_id)
        s.add(sess)
        await s.commit()
        await s.refresh(sess)
        run = Run(session_id=sess.id, workspace_id=ws_id, feishu_chat_id=chat_id, status=RunStatus.completed.value)
        s.add(run)
        await s.commit()
        await s.refresh(run)

        span_id = "p" * 32
        trace_id = "t" * 32

        # Create payload file on disk
        trace_dir = workspace_root(ws_id) / "chats" / str(chat_id) / "traces" / trace_id
        trace_dir.mkdir(parents=True, exist_ok=True)
        payload_file = trace_dir / f"{span_id}.request.json"
        payload_file.write_text(json.dumps({"old": "data"}))

        s.add(Span(
            span_id=span_id, trace_id=trace_id, span_type="llm", status="ok",
            workspace_id=ws_id, feishu_chat_id=chat_id, session_id=sess.id, run_id=run.id,
            started_at=old_time,
            payload_ref=f"{span_id}.request.json",
            payload_size_bytes=100,
            payload_truncated=True,
        ))
        await s.commit()

    assert payload_file.exists()

    count = await cleanup_old_payloads()
    assert count == 1

    # File should be deleted
    assert not payload_file.exists()

    # DB ref should be cleared
    async with async_session_factory() as s:
        from sqlalchemy import select
        span = (await s.scalars(select(Span).where(Span.span_id == span_id))).first()
        assert span.payload_ref is None
        assert span.payload_size_bytes is None
        assert span.payload_truncated is False
        # Span row should still exist (only payload cleaned, not the span)
        assert span is not None


async def test_cleanup_excess_runs():
    """When a chat has more than max_runs_per_chat runs, oldest are deleted."""
    ws_id, chat_id = await _seed_ws_and_chat()
    monkeypatch_max_runs(3)

    async with async_session_factory() as s:
        for i in range(5):
            sess = Session(feishu_chat_id=chat_id)
            s.add(sess)
            await s.commit()
            await s.refresh(sess)
            r = Run(
                session_id=sess.id,
                workspace_id=ws_id,
                feishu_chat_id=chat_id,
                status=RunStatus.completed.value,
                started_at=datetime.now(UTC) - timedelta(minutes=10 - i),
            )
            s.add(r)
            await s.commit()

    deleted = await cleanup_excess_runs()
    assert deleted == 2

    # Only 3 runs should remain
    async with async_session_factory() as s:
        from sqlalchemy import select
        remaining_runs = (await s.scalars(select(Run).where(Run.feishu_chat_id == chat_id))).all()
        assert len(remaining_runs) == 3


async def test_cleanup_excess_runs_under_limit():
    """No deletion when under the limit."""
    ws_id, chat_id = await _seed_ws_and_chat()
    monkeypatch_max_runs(100)

    async with async_session_factory() as s:
        sess = Session(feishu_chat_id=chat_id)
        s.add(sess)
        await s.commit()
        await s.refresh(sess)
        r = Run(session_id=sess.id, workspace_id=ws_id, feishu_chat_id=chat_id, status=RunStatus.completed.value)
        s.add(r)
        await s.commit()

    deleted = await cleanup_excess_runs()
    assert deleted == 0


def monkeypatch_ttl_days(span_days: int = 30, payload_days: int = 7):
    settings.span_ttl_days = span_days
    settings.payload_ttl_days = payload_days


def monkeypatch_max_runs(n: int):
    settings.max_runs_per_chat = n
