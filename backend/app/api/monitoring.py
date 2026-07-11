"""监控告警 API（design §7.7 / T10.3 / api §9.3）。

- GET /workspaces/{ws_id}/monitoring/anomalies：异常 Run 列表
- GET /workspaces/{ws_id}/monitoring/rules：规则列表
- POST /workspaces/{ws_id}/monitoring/rules：创建规则
- PATCH /workspaces/{ws_id}/monitoring/rules/{rule_id}：更新规则
- DELETE /workspaces/{ws_id}/monitoring/rules/{rule_id}：删除规则
"""


from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import require_ws_owner
from app.db.models import AlertRule, Run, RunStatus, Workspace
from app.db.models.alert_rule import RuleType
from app.db.session import get_db

router = APIRouter(prefix="/workspaces", tags=["monitoring"])


class RuleIn(BaseModel):
    name: str
    rule_type: str
    threshold: float
    window_minutes: int = 60
    enabled: bool = True


class RulePatch(BaseModel):
    name: str | None = None
    threshold: float | None = None
    window_minutes: int | None = None
    enabled: bool | None = None


@router.get("/{ws_id}/monitoring/anomalies")
async def list_anomalies(
    ws: Workspace = Depends(require_ws_owner),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(default=50, ge=1, le=200),
):
    """异常 Run 列表：error / interrupted / timeout 状态。"""
    db.info["ws_id"] = ws.id
    stmt = (
        select(Run)
        .where(Run.workspace_id == ws.id)
        .where(
            Run.status.in_([
                RunStatus.error.value,
                RunStatus.interrupted.value,
                RunStatus.timeout.value,
            ])
        )
        .order_by(Run.started_at.desc())
        .limit(limit)
    )
    runs = (await db.scalars(stmt)).all()
    return {
        "items": [
            {
                "id": r.id,
                "status": r.status,
                "started_at": r.started_at.isoformat() if r.started_at else None,
                "ended_at": r.ended_at.isoformat() if r.ended_at else None,
                "error": r.error,
            }
            for r in runs
        ],
        "total": len(runs),
    }


@router.get("/{ws_id}/monitoring/rules")
async def list_rules(
    ws: Workspace = Depends(require_ws_owner),
    db: AsyncSession = Depends(get_db),
):
    """告警规则列表。"""
    db.info["ws_id"] = ws.id
    stmt = (
        select(AlertRule)
        .where(AlertRule.workspace_id == ws.id)
        .order_by(AlertRule.id)
    )
    rules = (await db.scalars(stmt)).all()
    return {
        "items": [_rule_out(r) for r in rules],
        "total": len(rules),
    }


@router.post("/{ws_id}/monitoring/rules")
async def create_rule(
    body: RuleIn,
    ws: Workspace = Depends(require_ws_owner),
    db: AsyncSession = Depends(get_db),
):
    """创建告警规则。"""
    db.info["ws_id"] = ws.id
    valid_types = {t.value for t in RuleType}
    if body.rule_type not in valid_types:
        from app.core.errors import api_error
        raise api_error(400, f"无效规则类型，可选: {', '.join(valid_types)}")
    rule = AlertRule(
        workspace_id=ws.id,
        name=body.name,
        rule_type=body.rule_type,
        threshold=body.threshold,
        window_minutes=body.window_minutes,
        enabled=body.enabled,
    )
    db.add(rule)
    await db.commit()
    await db.refresh(rule)
    return _rule_out(rule)


@router.patch("/{ws_id}/monitoring/rules/{rule_id}")
async def update_rule(
    rule_id: int,
    body: RulePatch,
    ws: Workspace = Depends(require_ws_owner),
    db: AsyncSession = Depends(get_db),
):
    """更新规则阈值 / 开关。"""
    db.info["ws_id"] = ws.id
    rule = await db.get(AlertRule, rule_id)
    if rule is None or rule.workspace_id != ws.id:
        from app.core.errors import api_error
        raise api_error(404, "规则不存在")
    if body.name is not None:
        rule.name = body.name
    if body.threshold is not None:
        rule.threshold = body.threshold
    if body.window_minutes is not None:
        rule.window_minutes = body.window_minutes
    if body.enabled is not None:
        rule.enabled = body.enabled
    await db.commit()
    await db.refresh(rule)
    return _rule_out(rule)


@router.delete("/{ws_id}/monitoring/rules/{rule_id}")
async def delete_rule(
    rule_id: int,
    ws: Workspace = Depends(require_ws_owner),
    db: AsyncSession = Depends(get_db),
):
    """删除规则。"""
    db.info["ws_id"] = ws.id
    rule = await db.get(AlertRule, rule_id)
    if rule is None or rule.workspace_id != ws.id:
        from app.core.errors import api_error
        raise api_error(404, "规则不存在")
    await db.delete(rule)
    await db.commit()
    return {"ok": True}


def _rule_out(r: AlertRule) -> dict:
    return {
        "id": r.id,
        "name": r.name,
        "rule_type": r.rule_type,
        "threshold": r.threshold,
        "window_minutes": r.window_minutes,
        "enabled": r.enabled,
        "last_triggered_at": r.last_triggered_at.isoformat() if r.last_triggered_at else None,
        "last_result": r.last_result,
    }


DEFAULT_RULES = [
    {"name": "高错误率", "rule_type": "error_rate", "threshold": 0.1, "window_minutes": 60},
    {"name": "高超时率", "rule_type": "timeout_rate", "threshold": 0.05, "window_minutes": 60},
    {"name": "P95 延迟异常", "rule_type": "p95_latency", "threshold": 300000, "window_minutes": 60},
    {"name": "单 Run 费用异常", "rule_type": "run_cost", "threshold": 1.0, "window_minutes": 0},
    {"name": "WS 日费用上限", "rule_type": "ws_daily_cost", "threshold": 50.0, "window_minutes": 1440},
]
