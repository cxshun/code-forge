"""TTL 清理引擎（design §7.8 / T10.4）。

三类清理：
1. span 行：超过 ``span_ttl_days`` 的 span 行直接删除（CASCADE 自动清子 span）。
2. payload 文件：超过 ``payload_ttl_days`` 的 payload 文件删除，但保留 span 行（供聚合统计）。
3. 旧 Run 保留：每个 chat 超过 ``max_runs_per_chat`` 条的旧 Run（含 Session + Span）删除。
"""

import asyncio
import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import delete, func, select

from app.config import settings
from app.db.models import Run, Session, Span
from app.db.session import async_session_factory
from app.workspace.fs import workspace_root

log = logging.getLogger("observability.ttl")

TTL_LOOP_INTERVAL_S = 3600  # 1h


async def cleanup_old_spans() -> int:
    """删除超过 span_ttl_days 的 span 行。返回删除数。"""
    cutoff = datetime.now(UTC) - timedelta(days=settings.span_ttl_days)
    async with async_session_factory() as s:
        result = await s.execute(
            delete(Span).where(Span.started_at < cutoff)
        )
        await s.commit()
    deleted = result.rowcount or 0
    if deleted:
        log.info("cleanup_old_spans: deleted %d rows older than %d days", deleted, settings.span_ttl_days)
    return deleted


async def cleanup_old_payloads() -> int:
    """清空超过 payload_ttl_days 的 payload_ref 及对应文件。返回清理数。"""
    cutoff = datetime.now(UTC) - timedelta(days=settings.payload_ttl_days)
    async with async_session_factory() as s:
        rows = (await s.execute(
            select(Span.span_id, Span.payload_ref, Span.workspace_id, Span.feishu_chat_id, Span.trace_id).where(
                Span.started_at < cutoff,
                Span.payload_ref.isnot(None),
            )
        )).all()

        count = 0
        for span_id, payload_ref, ws_id, chat_id, trace_id in rows:
            if payload_ref:
                trace_dir = workspace_root(ws_id) / "chats" / str(chat_id) / "traces" / trace_id
                for f in Path(trace_dir).glob(f"{span_id}.*"):
                    try:
                        f.unlink(missing_ok=True)
                    except OSError:
                        log.warning("failed to delete payload file: %s", f)
                count += 1

        # Clear payload_ref, payload_size_bytes, payload_truncated in DB
        if rows:
            await s.execute(
                Span.__table__.update()
                .where(
                    Span.started_at < cutoff,
                    Span.payload_ref.isnot(None),
                )
                .values(payload_ref=None, payload_size_bytes=None, payload_truncated=False)
            )
            await s.commit()

    if count:
        log.info("cleanup_old_payloads: cleared %d payloads older than %d days", count, settings.payload_ttl_days)
    return count


async def cleanup_excess_runs() -> int:
    """每个 chat 保留最近 max_runs_per_chat 条 Run，多余的删除。返回删除数。"""
    async with async_session_factory() as s:
        # Find chats that exceed the limit
        chat_counts = (
            await s.execute(
                select(Run.feishu_chat_id, func.count(Run.id).label("cnt"))
                .group_by(Run.feishu_chat_id)
                .having(func.count(Run.id) > settings.max_runs_per_chat)
            )
        ).all()

        if not chat_counts:
            return 0

        total_deleted = 0
        for chat_id, cnt in chat_counts:
            excess = cnt - settings.max_runs_per_chat
            # Find the oldest runs to delete
            old_run_ids = (
                await s.scalars(
                    select(Run.id)
                    .where(Run.feishu_chat_id == chat_id)
                    .order_by(Run.started_at.asc().nulls_last())
                    .limit(excess)
                )
            ).all()

            if old_run_ids:
                # Delete spans for these runs first (they reference run_id)
                await s.execute(
                    delete(Span).where(Span.run_id.in_(old_run_ids))
                )
                # Delete runs (sessions cascade via FK)
                await s.execute(
                    delete(Run).where(Run.id.in_(old_run_ids))
                )
                # Delete orphaned sessions
                old_session_ids = (
                    await s.scalars(
                        select(Session.id)
                        .where(Session.feishu_chat_id == chat_id)
                        .order_by(Session.id.asc())
                        .limit(excess)
                    )
                ).all()
                if old_session_ids:
                    await s.execute(
                        delete(Session).where(Session.id.in_(old_session_ids))
                    )
                total_deleted += len(old_run_ids)

        await s.commit()

    if total_deleted:
        log.info("cleanup_excess_runs: deleted %d old runs", total_deleted)
    return total_deleted


async def run_ttl_cleanup() -> dict[str, int]:
    """执行一轮完整清理。返回各策略删除数。"""
    spans = await cleanup_old_spans()
    payloads = await cleanup_old_payloads()
    runs = await cleanup_excess_runs()
    return {"spans": spans, "payloads": payloads, "runs": runs}


async def ttl_loop() -> None:
    """后台 TTL 清理循环：每小时执行一次。"""
    log.info("ttl cleanup loop started")
    while True:
        try:
            result = await run_ttl_cleanup()
            if any(result.values()):
                log.info("ttl cleanup: %s", result)
        except Exception:
            log.exception("ttl loop error")
        await asyncio.sleep(TTL_LOOP_INTERVAL_S)
