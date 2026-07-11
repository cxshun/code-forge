"""Trace 观测 API（design §7.7 / T9.6）。

- GET /workspaces/{ws_id}/traces：Trace 列表（按 chat / status 筛选）
- GET /workspaces/{ws_id}/traces/{run_id}：单 Run span 树（瀑布图数据）
- GET /workspaces/{ws_id}/spans/{span_id}/payload：payload 文件读取（先 PG 校验归属）

ws_id 取自路径 + require_ws_owner（D31）；payload 读取前先 PG 校验 span 归属再读文件。
"""

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import SpanOut, TraceListItem
from app.core.deps import require_ws_owner
from app.core.errors import api_error
from app.db.models import Run, Span, Workspace
from app.db.session import get_db
from app.observability.payload import read_payload

router = APIRouter(prefix="/workspaces", tags=["traces"])


def _span_out(s: Span) -> SpanOut:
    return SpanOut(
        span_id=s.span_id,
        trace_id=s.trace_id,
        parent_span_id=s.parent_span_id,
        span_order=s.span_order,
        span_type=s.span_type,
        status=s.status,
        workspace_id=s.workspace_id,
        feishu_chat_id=s.feishu_chat_id,
        session_id=s.session_id,
        run_id=s.run_id,
        provider=s.provider,
        model=s.model,
        stop_reason=s.stop_reason,
        input_tokens=s.input_tokens,
        output_tokens=s.output_tokens,
        cache_read_input_tokens=s.cache_read_input_tokens,
        cache_creation_input_tokens=s.cache_creation_input_tokens,
        tool_name=s.tool_name,
        tool_input_summary=s.tool_input_summary,
        tool_output_summary=s.tool_output_summary,
        tool_acquired_lock=s.tool_acquired_lock,
        tool_path_rejected=s.tool_path_rejected,
        cost_usd=float(s.cost_usd) if s.cost_usd is not None else None,
        error_type=s.error_type,
        error_message=s.error_message,
        payload_ref=s.payload_ref,
        payload_size_bytes=s.payload_size_bytes,
        payload_truncated=s.payload_truncated,
        attributes=s.attributes,
        started_at=s.started_at.isoformat() if s.started_at else None,
        ended_at=s.ended_at.isoformat() if s.ended_at else None,
        duration_ms=s.duration_ms,
    )


@router.get("/{ws_id}/traces")
async def list_traces(
    ws: Workspace = Depends(require_ws_owner),
    db: AsyncSession = Depends(get_db),
    chat_id: int | None = Query(default=None),
    status: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
):
    """Trace 列表：查根 span（type=run），按 started_at desc。

    聚合 token / cost / span_count 供列表展示。
    """
    db.info["ws_id"] = ws.id

    stmt = (
        select(Span)
        .where(Span.workspace_id == ws.id)
        .where(Span.span_type == "run")
        .order_by(Span.started_at.desc())
        .limit(limit)
    )
    if chat_id is not None:
        stmt = stmt.where(Span.feishu_chat_id == chat_id)
    if status:
        stmt = stmt.where(Span.status == status)

    root_spans = (await db.scalars(stmt)).all()
    if not root_spans:
        return {"items": [], "total": 0}

    trace_ids = [s.trace_id for s in root_spans]

    # 聚合：每 trace 的 token / cost / span_count
    agg_stmt = (
        select(
            Span.trace_id,
            func.sum(Span.input_tokens).label("total_input"),
            func.sum(Span.output_tokens).label("total_output"),
            func.sum(Span.cost_usd).label("total_cost"),
            func.count(Span.span_id).label("span_count"),
        )
        .where(Span.trace_id.in_(trace_ids))
        .group_by(Span.trace_id)
    )
    agg_rows = (await db.execute(agg_stmt)).all()
    agg_map = {row.trace_id: row for row in agg_rows}

    items: list[TraceListItem] = []
    for s in root_spans:
        agg = agg_map.get(s.trace_id)
        items.append(
            TraceListItem(
                run_id=s.run_id,
                trace_id=s.trace_id,
                root_span_id=s.span_id,
                span_type=s.span_type,
                status=s.status,
                started_at=s.started_at.isoformat() if s.started_at else None,
                ended_at=s.ended_at.isoformat() if s.ended_at else None,
                duration_ms=s.duration_ms,
                total_input_tokens=int(agg.total_input) if agg and agg.total_input else None,
                total_output_tokens=int(agg.total_output) if agg and agg.total_output else None,
                total_cost_usd=float(agg.total_cost) if agg and agg.total_cost else None,
                span_count=int(agg.span_count) if agg else 0,
                error_type=s.error_type,
            )
        )
    return {"items": items, "total": len(items)}


@router.get("/{ws_id}/traces/{run_id}")
async def get_trace_spans(
    run_id: int,
    ws: Workspace = Depends(require_ws_owner),
    db: AsyncSession = Depends(get_db),
):
    """单 Run 的 span 树：查该 run_id 的所有 span，按 span_order 排序。"""
    db.info["ws_id"] = ws.id

    # 先校验 Run 归属
    run = await db.get(Run, run_id)
    if run is None or run.workspace_id != ws.id:
        raise api_error(404, "Run 不存在")

    stmt = (
        select(Span)
        .where(Span.run_id == run_id)
        .where(Span.workspace_id == ws.id)
        .order_by(Span.span_order)
    )
    spans = (await db.scalars(stmt)).all()
    return {"items": [_span_out(s) for s in spans], "total": len(spans)}


@router.get("/{ws_id}/spans/{span_id}/payload")
async def get_span_payload(
    span_id: str,
    suffix: str = Query(pattern="^(request|response|tool|skill)$"),
    ws: Workspace = Depends(require_ws_owner),
    db: AsyncSession = Depends(get_db),
):
    """读取 span payload 文件。先 PG 校验 span 归属，再读文件（D31 防路径穿越）。"""
    db.info["ws_id"] = ws.id

    span = await db.get(Span, span_id)
    if span is None or span.workspace_id != ws.id:
        raise api_error(404, "Span 不存在")

    data = await read_payload(
        ws_id=ws.id,
        feishu_chat_id=span.feishu_chat_id,
        trace_id=span.trace_id,
        span_id=span.span_id,
        suffix=suffix,
    )
    if data is None:
        raise api_error(404, "Payload 文件不存在")

    return Response(
        content=data,
        media_type="application/json",
        headers={
            "Content-Disposition": f'inline; filename="{span_id}.{suffix}"',
            "Content-Length": str(len(data)),
        },
    )
