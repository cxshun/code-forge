"""T10.2 Insights 聚合视图测试。

验证：cost/tools/models 三个聚合端点数据正确 + WS 隔离。
"""

from datetime import UTC, datetime

import pytest
from httpx import ASGITransport, AsyncClient

from app.api import insights  # noqa: F401 — ensure import works
from app.config import settings
from app.core.redis_client import redis as redis_client
from app.core.security import hash_password
from app.db.models import FeishuChat, GitRepo, Run, RunStatus, Session, Span, User, Workspace
from app.db.session import async_session_factory
from app.db.testing import reset_all
from app.main import app
from app.workspace.fs import create_workspace_skeleton

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
async def _isolated(tmp_path_factory, monkeypatch):
    monkeypatch.setattr(settings, "data_dir", str(tmp_path_factory.mktemp("cf_data")))
    await reset_all()
    await redis_client.flushdb()
    yield
    await redis_client.flushdb()


async def _seed_ws(username="admin", role="admin") -> tuple[int, str]:
    async with async_session_factory() as s:
        u = User(username=username, password_hash=hash_password("p"), role=role)
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
        await s.refresh(repo)
        chat = FeishuChat(workspace_id=ws.id, app_id="cli_x", chat_id="oc_x", chat_name="g")
        s.add(chat)
        await s.commit()
        await s.refresh(chat)
        create_workspace_skeleton(ws.id)
        return ws.id, "p"


async def _seed_spans(ws_id: int, chat_id: int):
    """Insert test spans: 2 llm spans (different models), 1 tool span."""
    async with async_session_factory() as s:
        sess = Session(feishu_chat_id=chat_id)
        s.add(sess)
        await s.commit()
        await s.refresh(sess)

        run = Run(
            session_id=sess.id,
            workspace_id=ws_id,
            feishu_chat_id=chat_id,
            status=RunStatus.completed.value,
        )
        s.add(run)
        await s.commit()
        await s.refresh(run)

        # Root run span
        run_span = Span(
            span_id="a" * 32,
            trace_id="t" * 32,
            span_type="run",
            status="ok",
            workspace_id=ws_id,
            feishu_chat_id=chat_id,
            session_id=sess.id,
            run_id=run.id,
            started_at=datetime(2026, 7, 11, 10, 0, 0, tzinfo=UTC),
            ended_at=datetime(2026, 7, 11, 10, 1, 0, tzinfo=UTC),
            duration_ms=60000,
        )
        s.add(run_span)

        # LLM span 1 — sonnet
        llm1 = Span(
            span_id="b" * 32,
            trace_id="t" * 32,
            parent_span_id="a" * 32,
            span_order=1,
            span_type="llm",
            status="ok",
            workspace_id=ws_id,
            feishu_chat_id=chat_id,
            session_id=sess.id,
            run_id=run.id,
            provider="anthropic",
            model="claude-sonnet-4-20250514",
            input_tokens=1000,
            output_tokens=500,
            cost_usd=0.0105,
            started_at=datetime(2026, 7, 11, 10, 0, 1, tzinfo=UTC),
            ended_at=datetime(2026, 7, 11, 10, 0, 10, tzinfo=UTC),
            duration_ms=9000,
        )
        s.add(llm1)

        # LLM span 2 — opus
        llm2 = Span(
            span_id="c" * 32,
            trace_id="t" * 32,
            parent_span_id="a" * 32,
            span_order=2,
            span_type="llm",
            status="ok",
            workspace_id=ws_id,
            feishu_chat_id=chat_id,
            session_id=sess.id,
            run_id=run.id,
            provider="anthropic",
            model="claude-opus-4-20250514",
            input_tokens=2000,
            output_tokens=1000,
            cost_usd=0.105,
            started_at=datetime(2026, 7, 11, 10, 0, 11, tzinfo=UTC),
            ended_at=datetime(2026, 7, 11, 10, 0, 20, tzinfo=UTC),
            duration_ms=9000,
        )
        s.add(llm2)

        # Tool span
        tool_span = Span(
            span_id="d" * 32,
            trace_id="t" * 32,
            parent_span_id="a" * 32,
            span_order=3,
            span_type="tool",
            status="error",
            workspace_id=ws_id,
            feishu_chat_id=chat_id,
            session_id=sess.id,
            run_id=run.id,
            tool_name="Read",
            duration_ms=500,
            started_at=datetime(2026, 7, 11, 10, 0, 21, tzinfo=UTC),
            ended_at=datetime(2026, 7, 11, 10, 0, 22, tzinfo=UTC),
        )
        s.add(tool_span)
        await s.commit()


async def _login_and_get(ws_id: int, password: str, path: str):
    """Login as admin, GET the path, return response JSON."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/auth/login", json={"username": "admin", "password": password})
        assert resp.status_code == 200
        resp = await client.get(f"/api/admin/workspaces/{ws_id}/{path}")
    return resp.json()


async def test_insights_cost():
    ws_id, pwd = await _seed_ws()
    await _seed_spans(ws_id, chat_id=1)
    data = await _login_and_get(ws_id, pwd, "insights/cost?days=7")
    assert data["total"] >= 1
    summary = data["summary"]
    assert summary["total_input_tokens"] == 3000
    assert summary["total_output_tokens"] == 1500
    assert abs(summary["total_cost_usd"] - 0.1155) < 0.0001


async def test_insights_tools():
    ws_id, pwd = await _seed_ws()
    await _seed_spans(ws_id, chat_id=1)
    data = await _login_and_get(ws_id, pwd, "insights/tools")
    items = data["items"]
    assert len(items) == 1
    assert items[0]["tool_name"] == "Read"
    assert items[0]["call_count"] == 1
    assert items[0]["error_count"] == 1
    assert items[0]["error_rate"] == 1.0


async def test_insights_models():
    ws_id, pwd = await _seed_ws()
    await _seed_spans(ws_id, chat_id=1)
    data = await _login_and_get(ws_id, pwd, "insights/models")
    items = data["items"]
    assert len(items) == 2
    models = {i["model"] for i in items}
    assert "claude-sonnet-4-20250514" in models
    assert "claude-opus-4-20250514" in models
    opus = next(i for i in items if i["model"] == "claude-opus-4-20250514")
    assert opus["call_count"] == 1
    assert opus["input_tokens"] == 2000
    assert opus["cost_usd"] == 0.105


async def test_insights_unauthenticated_rejected():
    ws_id, _ = await _seed_ws()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(f"/api/admin/workspaces/{ws_id}/insights/cost")
    assert resp.status_code == 401
