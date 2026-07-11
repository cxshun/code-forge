"""Insights 聚合视图 API（design §7.7 / T10.2 / api §9.2）。

- GET /workspaces/{ws_id}/insights/cost：token/cost 按日趋势
- GET /workspaces/{ws_id}/insights/tools：TopN 工具耗时 / 次数 / 错误率
- GET /workspaces/{ws_id}/insights/models：模型占比

ws_id 取自路径 + require_ws_owner（D31）。
"""

from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import require_ws_owner
from app.db.models import Span, Workspace
from app.db.session import get_db

router = APIRouter(prefix="/workspaces", tags=["insights"])


@router.get("/{ws_id}/insights/cost")
async def insights_cost(
    ws: Workspace = Depends(require_ws_owner),
    db: AsyncSession = Depends(get_db),
    chat_id: int | None = Query(default=None),
    days: int = Query(default=30, ge=1, le=365),
):
    """Token / cost 按日聚合趋势（实时 SQL GROUP BY）。"""
    db.info["ws_id"] = ws.id

    start = date.today() - timedelta(days=days)
    stmt = (
        select(
            func.date(Span.started_at).label("d"),
            func.sum(Span.input_tokens).label("input_tokens"),
            func.sum(Span.output_tokens).label("output_tokens"),
            func.sum(Span.cost_usd).label("cost_usd"),
            func.count(func.distinct(Span.run_id)).label("run_count"),
        )
        .where(Span.workspace_id == ws.id)
        .where(Span.span_type == "llm")
        .where(Span.started_at >= start)
        .group_by(func.date(Span.started_at))
        .order_by(func.date(Span.started_at))
    )
    if chat_id is not None:
        stmt = stmt.where(Span.feishu_chat_id == chat_id)

    rows = (await db.execute(stmt)).all()
    items = [
        {
            "date": str(row.d),
            "input_tokens": int(row.input_tokens or 0),
            "output_tokens": int(row.output_tokens or 0),
            "cost_usd": float(row.cost_usd) if row.cost_usd else 0.0,
            "run_count": int(row.run_count or 0),
        }
        for row in rows
    ]
    total_cost = sum(r["cost_usd"] for r in items)
    total_input = sum(r["input_tokens"] for r in items)
    total_output = sum(r["output_tokens"] for r in items)
    total_runs = sum(r["run_count"] for r in items)
    return {
        "items": items,
        "total": len(items),
        "summary": {
            "total_cost_usd": round(total_cost, 6),
            "total_input_tokens": total_input,
            "total_output_tokens": total_output,
            "total_runs": total_runs,
        },
    }


@router.get("/{ws_id}/insights/tools")
async def insights_tools(
    ws: Workspace = Depends(require_ws_owner),
    db: AsyncSession = Depends(get_db),
    chat_id: int | None = Query(default=None),
    limit: int = Query(default=10, ge=1, le=50),
):
    """TopN 工具统计：调用次数 / 平均耗时 / 错误率。"""
    db.info["ws_id"] = ws.id

    stmt = (
        select(
            Span.tool_name,
            func.count().label("call_count"),
            func.avg(Span.duration_ms).label("avg_duration_ms"),
            func.max(Span.duration_ms).label("max_duration_ms"),
            func.sum(case((Span.status == "error", 1), else_=0)).label("error_count"),
        )
        .where(Span.workspace_id == ws.id)
        .where(Span.span_type.in_(["tool", "skill"]))
        .where(Span.tool_name.isnot(None))
        .group_by(Span.tool_name)
        .order_by(func.count().desc())
        .limit(limit)
    )
    if chat_id is not None:
        stmt = stmt.where(Span.feishu_chat_id == chat_id)

    rows = (await db.execute(stmt)).all()
    items = [
        {
            "tool_name": row.tool_name,
            "call_count": int(row.call_count),
            "avg_duration_ms": int(row.avg_duration_ms) if row.avg_duration_ms else 0,
            "max_duration_ms": int(row.max_duration_ms) if row.max_duration_ms else 0,
            "error_count": int(row.error_count or 0),
            "error_rate": round(int(row.error_count or 0) / int(row.call_count), 4),
        }
        for row in rows
    ]
    return {"items": items, "total": len(items)}


@router.get("/{ws_id}/insights/models")
async def insights_models(
    ws: Workspace = Depends(require_ws_owner),
    db: AsyncSession = Depends(get_db),
    chat_id: int | None = Query(default=None),
):
    """模型占比：调用次数 / token / cost 按模型聚合。"""
    db.info["ws_id"] = ws.id

    stmt = (
        select(
            Span.model,
            func.count().label("call_count"),
            func.sum(Span.input_tokens).label("input_tokens"),
            func.sum(Span.output_tokens).label("output_tokens"),
            func.sum(Span.cost_usd).label("cost_usd"),
        )
        .where(Span.workspace_id == ws.id)
        .where(Span.span_type == "llm")
        .where(Span.model.isnot(None))
        .group_by(Span.model)
        .order_by(func.sum(Span.cost_usd).desc())
    )
    if chat_id is not None:
        stmt = stmt.where(Span.feishu_chat_id == chat_id)

    rows = (await db.execute(stmt)).all()
    total_cost = sum(float(r.cost_usd or 0) for r in rows)
    items = [
        {
            "model": row.model,
            "call_count": int(row.call_count),
            "input_tokens": int(row.input_tokens or 0),
            "output_tokens": int(row.output_tokens or 0),
            "cost_usd": float(row.cost_usd) if row.cost_usd else 0.0,
            "cost_pct": round(float(row.cost_usd or 0) / total_cost, 4) if total_cost else 0.0,
        }
        for row in rows
    ]
    return {"items": items, "total": len(items)}
