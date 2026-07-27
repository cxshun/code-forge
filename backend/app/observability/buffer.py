"""SpanBuffer — 内存队列 + 后台单协程批量 UPSERT（design §7.4 / D28）。

span 事件进 ``asyncio.Queue``（put_nowait 纳秒级，绝不阻塞 Agent Loop），
后台单协程批量 UPSERT 到 PG。失败降级：
- 队列满 → 丢弃 + warning
- PG 不可用 → 重试 → fallback 文件
- tracer 异常 → swallow + 日志

Run 结束前 ``flush_trace()`` 同步等待本 trace 的 span 全部写入。
"""

import asyncio
import json
import logging
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.config import settings
from app.db.models.span import Span
from app.db.session import async_session_factory

log = logging.getLogger("observability.buffer")

QUEUE_MAX = 5000
BATCH_SIZE = 50
BATCH_TIMEOUT_S = 2.0
RETRY_DELAYS = [0.5, 1.0, 2.0]


class SpanBuffer:
    """span 事件内存队列 + 后台批量写入 PG。"""

    def __init__(self) -> None:
        self._queue: asyncio.Queue[dict] = asyncio.Queue(maxsize=QUEUE_MAX)
        self._consumer: asyncio.Task | None = None
        self._stopping = False
        self._pending: dict[str, asyncio.Future] = {}

    def put(self, span_dict: dict) -> None:
        """非阻塞入队。队列满时丢弃 + warning（§7.4 降级矩阵）。"""
        try:
            self._queue.put_nowait(span_dict)
        except asyncio.QueueFull:
            log.warning("span buffer full, dropping span %s", span_dict.get("span_id"))

    async def flush_trace(self, trace_id: str, timeout_s: float = 10.0) -> None:
        """等待指定 trace 的所有 span 写入完成。

        Run 结束前调用（§7.4：Run 结束前同步 flush 本 trace 的剩余 span）。
        """
        fut = asyncio.get_event_loop().create_future()
        self._pending[trace_id] = fut
        # 唤醒 consumer 处理剩余
        await self._queue.put({})
        try:
            await asyncio.wait_for(fut, timeout=timeout_s)
        except TimeoutError:
            log.warning("flush trace %s timed out", trace_id)
        finally:
            self._pending.pop(trace_id, None)

    def start(self) -> None:
        if self._consumer is None:
            self._stopping = False
            self._consumer = asyncio.create_task(
                self._consume(), name="span-buffer-consumer"
            )

    async def stop(self) -> None:
        self._stopping = True
        # 哨兵唤醒
        await self._queue.put({})
        if self._consumer is not None:
            try:
                await asyncio.wait_for(self._consumer, timeout=5.0)
            except TimeoutError:
                self._consumer.cancel()
            self._consumer = None

    async def _consume(self) -> None:
        """后台消费：攒批 → UPSERT → 降级。"""
        batch: list[dict] = []
        while True:
            try:
                item = await asyncio.wait_for(
                    self._queue.get(), timeout=BATCH_TIMEOUT_S
                )
            except TimeoutError:
                item = None

            if item is not None:
                if item == {}:
                    pass  # 哨兵
                else:
                    batch.append(item)
                self._queue.task_done()

            # 攒够或超时则写
            should_flush = len(batch) >= BATCH_SIZE or (
                batch and (item is None or item == {})
            )
            if should_flush and batch:
                await self._write_batch(batch)
                batch = []

            if self._stopping and self._queue.empty():
                if batch:
                    await self._write_batch(batch)
                break

    async def _write_batch(self, batch: list[dict]) -> None:
        """批量 UPSERT，失败降级 fallback 文件。"""
        trace_ids = {s.get("trace_id") for s in batch}
        try:
            await self._upsert(batch)
        except Exception:
            log.exception("batch upsert failed (%d spans), fallback to file", len(batch))
            await self._fallback_file(batch)

        # 通知 flush_trace 等待者
        for tid in trace_ids:
            fut = self._pending.get(tid)
            if fut is not None and not fut.done():
                fut.set_result(None)

    @staticmethod
    def _sort_batch(batch: list[dict]) -> list[dict]:
        """拓扑排序：parent span 排在 child 之前（同 batch 内）。

        即使 FK 约束已移除，先写 parent 仍有利于查询一致性。
        """
        ids = {s["span_id"] for s in batch}
        roots = [s for s in batch if not s.get("parent_span_id") or s["parent_span_id"] not in ids]
        children = [s for s in batch if s not in roots]
        result = list(roots)
        placed = {s["span_id"] for s in result}
        remaining = children
        while remaining:
            progressed = False
            next_remaining = []
            for s in remaining:
                if s["parent_span_id"] in placed:
                    result.append(s)
                    placed.add(s["span_id"])
                    progressed = True
                else:
                    next_remaining.append(s)
            remaining = next_remaining
            if not progressed:
                result.extend(remaining)
                break
        return result

    async def _upsert(self, batch: list[dict]) -> None:
        """UPSERT 到 PG spans 表。"""
        sorted_batch = self._sort_batch(batch)
        async with async_session_factory() as db:
            stmt = pg_insert(Span).values(sorted_batch)
            stmt = stmt.on_conflict_do_update(
                index_elements=["span_id"],
                set_={
                    "status": stmt.excluded.status,
                    "ended_at": stmt.excluded.ended_at,
                    "duration_ms": stmt.excluded.duration_ms,
                    "stop_reason": stmt.excluded.stop_reason,
                    "input_tokens": stmt.excluded.input_tokens,
                    "output_tokens": stmt.excluded.output_tokens,
                    "cache_read_input_tokens": stmt.excluded.cache_read_input_tokens,
                    "cache_creation_input_tokens": stmt.excluded.cache_creation_input_tokens,
                    "cost_usd": stmt.excluded.cost_usd,
                    "error_type": stmt.excluded.error_type,
                    "error_message": stmt.excluded.error_message,
                    "payload_ref": stmt.excluded.payload_ref,
                    "payload_size_bytes": stmt.excluded.payload_size_bytes,
                    "payload_truncated": stmt.excluded.payload_truncated,
                    "tool_output_summary": stmt.excluded.tool_output_summary,
                    "updated_at": datetime.now(UTC),
                },
            )
            await db.execute(stmt)
            await db.commit()

    async def _fallback_file(self, batch: list[dict]) -> None:
        """PG 故障时写本地 fallback 文件（§7.4 降级矩阵）。"""
        fallback_dir = Path(settings.data_dir) / "trace_fallback"
        fallback_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(UTC).strftime("%Y%m%d_%H%M%S_%f")
        path = fallback_dir / f"spans_{ts}.jsonl"
        try:
            def _write():
                with path.open("w", encoding="utf-8") as f:
                    for s in batch:
                        f.write(json.dumps(s, default=str, ensure_ascii=False) + "\n")
            await asyncio.to_thread(_write)
            log.info("wrote %d spans to fallback %s", len(batch), path)
        except Exception:
            log.exception("fallback file write failed, spans lost")


span_buffer = SpanBuffer()

__all__ = ["SpanBuffer", "span_buffer"]
