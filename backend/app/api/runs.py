"""Run 管理 API（design §6.6 / T6.2 / T6.3）。

- GET /workspaces/{ws_id}/runs：Run 列表（可按 chat / status 筛选）
- GET /workspaces/{ws_id}/runs/{run_id}/messages：Run 的会话消息
- POST /workspaces/{ws_id}/runs/{run_id}:cancel：取消排队中的 Run
- POST /workspaces/{ws_id}/runs/{run_id}:interrupt：中断运行中的 Run

cancel 仅作用于排队中（未启动 Agent Loop）；interrupt 作用于运行中（排队中的退化为 cancel）。
ws_id 取自路径并校验归属（D31），run 须属该 WS。
"""

import json

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.queue import run_queue
from app.api.schemas import RunOut
from app.core.deps import require_ws_owner
from app.core.errors import api_error
from app.db.models import Run, Workspace
from app.db.session import get_db
from app.workspace.fs import workspace_root

router = APIRouter(prefix="/workspaces", tags=["runs"])


def _run_out(r: Run) -> RunOut:
    return RunOut(
        id=r.id,
        session_id=r.session_id,
        feishu_chat_id=r.feishu_chat_id,
        status=r.status,
        trigger_message_id=r.trigger_message_id,
        started_at=r.started_at.isoformat() if r.started_at else None,
        ended_at=r.ended_at.isoformat() if r.ended_at else None,
        error=r.error,
    )


@router.get("/{ws_id}/runs")
async def list_runs(
    ws: Workspace = Depends(require_ws_owner),
    db: AsyncSession = Depends(get_db),
    chat_id: int | None = Query(default=None),
    status: str | None = Query(default=None),
):
    stmt = select(Run).where(Run.workspace_id == ws.id).order_by(Run.id.desc())
    if chat_id is not None:
        stmt = stmt.where(Run.feishu_chat_id == chat_id)
    if status:
        stmt = stmt.where(Run.status == status)
    runs = (await db.scalars(stmt)).all()
    return {"items": [_run_out(r) for r in runs], "total": len(runs)}


@router.get("/{ws_id}/runs/{run_id}/messages")
async def get_run_messages(
    run_id: int,
    ws: Workspace = Depends(require_ws_owner),
    db: AsyncSession = Depends(get_db),
):
    """读取 Run 的会话消息（session JSONL，含模型思考内容）。"""
    run = await db.get(Run, run_id)
    if run is None or run.workspace_id != ws.id:
        raise api_error(404, "Run 不存在")
    session_file = (
        workspace_root(ws.id)
        / "chats"
        / str(run.feishu_chat_id)
        / "sessions"
        / f"{run.session_id}.jsonl"
    )
    if not session_file.exists():
        return {"messages": []}
    messages: list[dict] = []
    try:
        with session_file.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    messages.append(json.loads(line))
    except Exception:
        raise api_error(500, "读取会话消息失败")
    return {"messages": messages}


@router.post("/{ws_id}/runs/{run_id}:cancel")
async def cancel_run(
    run_id: int,
    ws: Workspace = Depends(require_ws_owner),
    db: AsyncSession = Depends(get_db),
):
    run = await db.get(Run, run_id)
    if run is None or run.workspace_id != ws.id:
        raise api_error(404, "Run 不存在")
    ok = await run_queue.cancel(run_id)
    return {"run_id": run_id, "cancelled": ok}


@router.post("/{ws_id}/runs/{run_id}:interrupt")
async def interrupt_run(
    run_id: int,
    ws: Workspace = Depends(require_ws_owner),
    db: AsyncSession = Depends(get_db),
):
    run = await db.get(Run, run_id)
    if run is None or run.workspace_id != ws.id:
        raise api_error(404, "Run 不存在")
    ok = await run_queue.interrupt(run_id)
    return {"run_id": run_id, "interrupted": ok}
