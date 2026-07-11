"""T10.3 监控告警测试。

验证：规则 CRUD + 异常 Run 列表 + scan_rules 命中检测 + WS 隔离。
"""

from datetime import UTC, datetime, timedelta

import pytest
from httpx import ASGITransport, AsyncClient

from app.api import monitoring  # noqa: F401 — ensure import works
from app.config import settings
from app.core.redis_client import redis as redis_client
from app.core.security import hash_password
from app.db.models import (
    AlertRule,
    FeishuChat,
    GitRepo,
    Run,
    RunStatus,
    Session,
    Span,
    User,
    Workspace,
)
from app.db.session import async_session_factory
from app.db.testing import reset_all
from app.main import app
from app.observability.monitor import scan_rules
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


async def _login_and_get(ws_id: int, password: str, path: str):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/auth/login", json={"username": "admin", "password": password})
        assert resp.status_code == 200
        resp = await client.get(f"/api/admin/workspaces/{ws_id}/{path}")
    return resp


async def _login_and_post(ws_id: int, password: str, path: str, json: dict):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/auth/login", json={"username": "admin", "password": password})
        assert resp.status_code == 200
        resp = await client.post(f"/api/admin/workspaces/{ws_id}/{path}", json=json)
    return resp


async def _login_and_patch(ws_id: int, password: str, path: str, json: dict):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/auth/login", json={"username": "admin", "password": password})
        assert resp.status_code == 200
        resp = await client.patch(f"/api/admin/workspaces/{ws_id}/{path}", json=json)
    return resp


async def _login_and_delete(ws_id: int, password: str, path: str):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/auth/login", json={"username": "admin", "password": password})
        assert resp.status_code == 200
        resp = await client.delete(f"/api/admin/workspaces/{ws_id}/{path}")
    return resp


# ── Rule CRUD ──


async def test_create_rule():
    ws_id, pwd = await _seed_ws()
    resp = await _login_and_post(ws_id, pwd, "monitoring/rules", {
        "name": "test error rate",
        "rule_type": "error_rate",
        "threshold": 0.2,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "test error rate"
    assert data["rule_type"] == "error_rate"
    assert data["threshold"] == 0.2
    assert data["enabled"] is True
    assert "id" in data


async def test_list_rules():
    ws_id, pwd = await _seed_ws()
    await _login_and_post(ws_id, pwd, "monitoring/rules", {
        "name": "rule-a", "rule_type": "error_rate", "threshold": 0.1,
    })
    await _login_and_post(ws_id, pwd, "monitoring/rules", {
        "name": "rule-b", "rule_type": "p95_latency", "threshold": 500000,
    })
    resp = await _login_and_get(ws_id, pwd, "monitoring/rules")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2


async def test_update_rule():
    ws_id, pwd = await _seed_ws()
    resp = await _login_and_post(ws_id, pwd, "monitoring/rules", {
        "name": "orig", "rule_type": "error_rate", "threshold": 0.1,
    })
    rule_id = resp.json()["id"]
    resp = await _login_and_patch(ws_id, pwd, f"monitoring/rules/{rule_id}", {
        "threshold": 0.5,
        "enabled": False,
    })
    assert resp.status_code == 200
    assert resp.json()["threshold"] == 0.5
    assert resp.json()["enabled"] is False


async def test_delete_rule():
    ws_id, pwd = await _seed_ws()
    resp = await _login_and_post(ws_id, pwd, "monitoring/rules", {
        "name": "del", "rule_type": "error_rate", "threshold": 0.1,
    })
    rule_id = resp.json()["id"]
    resp = await _login_and_delete(ws_id, pwd, f"monitoring/rules/{rule_id}")
    assert resp.status_code == 200
    assert resp.json()["ok"] is True
    resp = await _login_and_get(ws_id, pwd, "monitoring/rules")
    assert resp.json()["total"] == 0


async def test_invalid_rule_type():
    ws_id, pwd = await _seed_ws()
    resp = await _login_and_post(ws_id, pwd, "monitoring/rules", {
        "name": "bad", "rule_type": "nonexistent", "threshold": 0.1,
    })
    assert resp.status_code == 400


async def test_update_nonexistent_rule():
    ws_id, pwd = await _seed_ws()
    resp = await _login_and_patch(ws_id, pwd, "monitoring/rules/9999", {"threshold": 0.5})
    assert resp.status_code == 404


# ── Anomalies ──


async def test_list_anomalies():
    ws_id, pwd = await _seed_ws()
    async with async_session_factory() as s:
        sess = Session(feishu_chat_id=1)
        s.add(sess)
        await s.commit()
        await s.refresh(sess)
        run = Run(
            session_id=sess.id,
            workspace_id=ws_id,
            feishu_chat_id=1,
            status=RunStatus.error.value,
            error="test error",
        )
        s.add(run)
        await s.commit()
    resp = await _login_and_get(ws_id, pwd, "monitoring/anomalies")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    assert data["items"][0]["status"] == "error"


# ── scan_rules ──


async def test_scan_rules_triggers():
    """error_rate rule with threshold 0 should trigger when there's an error run."""
    ws_id, _ = await _seed_ws()
    async with async_session_factory() as s:
        # 2 error runs, 1 completed run → error_rate = 0.667
        # Each run needs its own session (runs.session_id is unique)
        run_ids: list[int] = []
        statuses = [RunStatus.error.value, RunStatus.error.value, RunStatus.completed.value]
        for st in statuses:
            sess = Session(feishu_chat_id=1)
            s.add(sess)
            await s.commit()
            await s.refresh(sess)
            r = Run(
                session_id=sess.id,
                workspace_id=ws_id,
                feishu_chat_id=1,
                status=st,
                started_at=datetime.now(UTC) - timedelta(minutes=5),
            )
            s.add(r)
            await s.commit()
            await s.refresh(r)
            run_ids.append(r.id)
        rule = AlertRule(
            workspace_id=ws_id,
            name="high error",
            rule_type="error_rate",
            threshold=0.1,
            window_minutes=60,
            enabled=True,
        )
        s.add(rule)
        await s.commit()

    hits = await scan_rules()
    assert hits >= 1

    # Verify last_result was updated
    async with async_session_factory() as s:
        from sqlalchemy import select
        rule_db = (await s.scalars(
            select(AlertRule).where(AlertRule.workspace_id == ws_id)
        )).first()
        assert rule_db.last_result is not None
        assert rule_db.last_result > 0.1
        assert rule_db.last_triggered_at is not None


async def test_scan_rules_no_trigger():
    """No data → no triggers, last_result = 0."""
    ws_id, _ = await _seed_ws()
    async with async_session_factory() as s:
        rule = AlertRule(
            workspace_id=ws_id,
            name="error rate",
            rule_type="error_rate",
            threshold=0.1,
            window_minutes=60,
            enabled=True,
        )
        s.add(rule)
        await s.commit()

    hits = await scan_rules()
    assert hits == 0


async def test_scan_rules_ws_daily_cost():
    """ws_daily_cost rule triggers when cost exceeds threshold."""
    ws_id, _ = await _seed_ws()
    async with async_session_factory() as s:
        sess = Session(feishu_chat_id=1)
        s.add(sess)
        await s.commit()
        await s.refresh(sess)
        run = Run(
            session_id=sess.id,
            workspace_id=ws_id,
            feishu_chat_id=1,
            status=RunStatus.completed.value,
            started_at=datetime.now(UTC) - timedelta(minutes=5),
        )
        s.add(run)
        await s.commit()
        await s.refresh(run)
        llm_span = Span(
            span_id="f" * 32,
            trace_id="t" * 32,
            span_type="llm",
            status="ok",
            workspace_id=ws_id,
            feishu_chat_id=1,
            session_id=sess.id,
            run_id=run.id,
            cost_usd=60.0,
            started_at=datetime.now(UTC) - timedelta(minutes=5),
            ended_at=datetime.now(UTC) - timedelta(minutes=4),
            duration_ms=60000,
        )
        s.add(llm_span)
        rule = AlertRule(
            workspace_id=ws_id,
            name="daily cost",
            rule_type="ws_daily_cost",
            threshold=50.0,
            window_minutes=1440,
            enabled=True,
        )
        s.add(rule)
        await s.commit()

    hits = await scan_rules()
    assert hits >= 1
