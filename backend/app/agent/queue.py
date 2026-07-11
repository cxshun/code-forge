"""Run 队列 + 排队 / 中断反馈（design §6.6 / D20 / T6.2 / T6.3）。

同一 WS 的 Run 经 ``RunQueue.submit`` 入队：抢 ``ws_lock`` 成功 → 立即跑（推
"▶️ 开始执行"）；否则按入队顺序排队（推"⏳ 排队中，前面 N 个"），等前序 Run 释放
锁后唤醒。

- **FIFO 公平**：Redis sorted set（score = ``INCR`` 自增 seq）排序，``rank==0`` 的
  队首才尝试抢锁，避免多 waiter 抢占破坏顺序
- **唤醒**：锁释放走 ``WsLock.release()`` 的 pub/sub（跨进程）+ 进程内 per-ws
  ``asyncio.Condition``（本进程零空轮询），另设 5s 兜底超时防丢通知
- **排队取消**（``cancel``）：notify 唤醒 ``_wait_turn`` → 抛 ``RunCancelled`` →
  标 ``cancelled``，未启动 Agent Loop、无副作用
- **运行中断**（``interrupt``）：set ``abort`` → Loop 下一检查点抛
  ``InterruptedError`` → 标 ``interrupted``
- **释放保证**：``try/finally`` 释放锁 + 出队 + notify，覆盖完成 / 异常 / 中断 / 取消
"""

import asyncio
import contextlib
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from redis.asyncio import Redis

from app.agent.lock import WsLock
from app.agent.run import _create_run, _execute_run, _set_run_status
from app.core.redis_client import redis as redis_client
from app.db.models import RunStatus
from app.providers.base import Provider
from app.tools.registry import ToolRegistry

log = logging.getLogger("agent.queue")

QUEUE_PREFIX = "ws_queue:"  # sorted set: member=run_id, score=seq
SEQ_PREFIX = "ws_seq:"      # INCR 自增序号（FIFO 排序键，跨进程单调）

WAIT_FALLBACK_S = 5.0  # 兜底唤醒间隔（防 pub/sub 丢通知）

OnText = Callable[[str], Awaitable[None] | None]
OnToolCall = Callable[[dict], Awaitable[None] | None]
OnQueue = Callable[[int], Awaitable[None] | None]  # 位置（>0 表示排队中）
OnStart = Callable[[], Awaitable[None] | None]
OnDone = Callable[[Exception | None], Awaitable[None] | None]  # Run 结束（None=成功）


class RunCancelled(Exception):
    """排队中被取消。"""


@dataclass
class _RunParams:
    """``_execute_run`` 所需参数（run_id / session_id / abort 由 RunQueue 注入）。"""

    ws_id: int
    feishu_chat_id: int
    user_message: str
    provider: Provider
    registry: ToolRegistry
    cwd: str = ""
    skill_descriptions: list[str] | None = None
    on_text: OnText | None = None
    on_tool_call: OnToolCall | None = None
    on_done: OnDone | None = None


class _ActiveRun:
    __slots__ = ("abort", "cancelled", "on_queue", "on_start", "params", "run_id", "session_id", "state", "task", "ws_id")

    def __init__(
        self,
        run_id: int,
        ws_id: int,
        session_id: int,
        params: _RunParams,
        on_queue: OnQueue | None,
        on_start: OnStart | None,
    ) -> None:
        self.run_id = run_id
        self.ws_id = ws_id
        self.session_id = session_id
        self.state = "queued"  # queued | running
        self.abort = asyncio.Event()
        self.cancelled = asyncio.Event()
        self.task: asyncio.Task | None = None
        self.params = params
        self.on_queue = on_queue
        self.on_start = on_start


async def _maybe(cb, *args) -> None:
    if cb is None:
        return
    res = cb(*args)
    if asyncio.iscoroutine(res):
        await res


class RunQueue:
    """同 WS 串行调度 Run，提供排队位置反馈与取消 / 中断。"""

    def __init__(self, redis: Redis) -> None:
        self._redis = redis
        self._active: dict[int, _ActiveRun] = {}
        self._conds: dict[int, asyncio.Condition] = {}

    # ---- 内部 ----
    def _cond(self, ws_id: int) -> asyncio.Condition:
        c = self._conds.get(ws_id)
        if c is None:
            c = asyncio.Condition()
            self._conds[ws_id] = c
        return c

    def _qkey(self, ws_id: int) -> str:
        return f"{QUEUE_PREFIX}{ws_id}"

    def _seqkey(self, ws_id: int) -> str:
        return f"{SEQ_PREFIX}{ws_id}"

    # ---- 公开 API ----
    async def submit(
        self,
        *,
        ws_id: int,
        feishu_chat_id: int,
        user_message: str,
        provider: Provider,
        registry: ToolRegistry,
        cwd: str = "",
        skill_descriptions: list[str] | None = None,
        trigger_message_id: str | None = None,
        on_text: OnText | None = None,
        on_tool_call: OnToolCall | None = None,
        on_queue: OnQueue | None = None,
        on_start: OnStart | None = None,
        on_done: OnDone | None = None,
    ) -> int:
        """入队一个 Run（fire-and-forget）。返回 run_id；用 ``join`` 等待结束。"""
        session_id, run_id = await _create_run(ws_id, feishu_chat_id, trigger_message_id)

        # FIFO 入队（自增 seq 作 score，跨进程单调）
        seq = await self._redis.incr(self._seqkey(ws_id))
        await self._redis.zadd(self._qkey(ws_id), {str(run_id): seq})
        rank = await self._redis.zrank(self._qkey(ws_id), str(run_id))
        ahead = rank if rank is not None else 0

        params = _RunParams(
            ws_id=ws_id,
            feishu_chat_id=feishu_chat_id,
            user_message=user_message,
            provider=provider,
            registry=registry,
            cwd=cwd,
            skill_descriptions=skill_descriptions,
            on_text=on_text,
            on_tool_call=on_tool_call,
            on_done=on_done,
        )
        ar = _ActiveRun(run_id, ws_id, session_id, params, on_queue, on_start)
        self._active[run_id] = ar
        ar.task = asyncio.create_task(self._drive(ar), name=f"run-{run_id}")

        # 锁有竞争时推"排队中"卡片（rank==0 将立即起跑，由 on_start 反馈）
        if ahead > 0:
            await _maybe(on_queue, ahead)

        return run_id

    async def _drive(self, ar: _ActiveRun) -> None:
        lock = WsLock(self._redis, ar.ws_id)
        drive_exc: Exception | None = None
        try:
            await self._wait_turn(ar, lock)
            ar.state = "running"
            await _maybe(ar.on_start)
            p = ar.params
            await _execute_run(
                run_id=ar.run_id,
                session_id=ar.session_id,
                ws_id=ar.ws_id,
                feishu_chat_id=p.feishu_chat_id,
                user_message=p.user_message,
                provider=p.provider,
                registry=p.registry,
                cwd=p.cwd,
                skill_descriptions=p.skill_descriptions,
                abort=ar.abort,
                on_text=p.on_text,
                on_tool_call=p.on_tool_call,
            )
        except RunCancelled as e:
            drive_exc = e
            await _set_run_status(ar.run_id, RunStatus.cancelled.value)
            log.info("run %d cancelled while queued", ar.run_id)
        except InterruptedError as e:
            drive_exc = e
            # _execute_run 已标 interrupted
            log.info("run %d interrupted", ar.run_id)
        except Exception as e:
            log.exception("run %d drive failed", ar.run_id)
            # _execute_run 已标 error；此处兜底 _wait_turn 阶段失败
            await _set_run_status(ar.run_id, RunStatus.error.value, error=str(e))
            drive_exc = e
        finally:
            try:
                await lock.release()  # 未抢到锁时为幂等 no-op
            except Exception:
                log.exception("run %d lock release failed", ar.run_id)
            await self._redis.zrem(self._qkey(ar.ws_id), str(ar.run_id))
            cond = self._conds.get(ar.ws_id)
            if cond is not None:
                async with cond:
                    cond.notify_all()
            self._active.pop(ar.run_id, None)
            # on_done 在锁释放 / 出队后调（接入层据此 finalize 卡片）；异常吞掉不破坏调度
            if ar.params.on_done is not None:
                try:
                    await _maybe(ar.params.on_done, drive_exc)
                except Exception:
                    log.exception("run %d on_done failed", ar.run_id)
            log.info("run %d drained (ws=%s)", ar.run_id, ar.ws_id)

    async def _wait_turn(self, ar: _ActiveRun, lock: WsLock) -> None:
        """FIFO 等待：``rank==0``（队首）才尝试抢锁；被取消抛 ``RunCancelled``。"""
        cond = self._cond(ar.ws_id)
        async with cond:
            while True:
                if ar.cancelled.is_set():
                    raise RunCancelled()
                rank = await self._redis.zrank(self._qkey(ar.ws_id), str(ar.run_id))
                if rank is None:
                    # 已被移出队列（外部 zrem / cancel）→ 视为取消
                    raise RunCancelled()
                if rank == 0 and await lock.acquire():
                    return  # 队首且抢到锁
                # 锁仍被前序 Run 持有 → 等释放通知再试
                with contextlib.suppress(TimeoutError):
                    await asyncio.wait_for(cond.wait(), timeout=WAIT_FALLBACK_S)

    async def cancel(self, run_id: int) -> bool:
        """取消**排队中**的 Run（未启动 Agent Loop）。运行中的 Run 用 ``interrupt``。

        返回是否命中并触发取消。
        """
        ar = self._active.get(run_id)
        if ar is None or ar.state != "queued":
            return False
        ar.cancelled.set()
        # 立即出队 + 唤醒 _wait_turn
        await self._redis.zrem(self._qkey(ar.ws_id), str(run_id))
        cond = self._cond(ar.ws_id)
        async with cond:
            cond.notify_all()
        return True

    async def interrupt(self, run_id: int) -> bool:
        """中断**运行中**的 Run（set abort → Loop 下一检查点停止）。

        排队中的 Run 退化为 ``cancel``。返回是否命中。
        """
        ar = self._active.get(run_id)
        if ar is None:
            return False
        if ar.state == "queued":
            return await self.cancel(run_id)
        ar.abort.set()
        return True

    def get_state(self, run_id: int) -> str | None:
        """返回活跃 Run 的调度态（queued / running）；非活跃返回 None。"""
        ar = self._active.get(run_id)
        return ar.state if ar is not None else None

    async def join(self, run_id: int) -> None:
        """等待某 Run 的任务结束（测试 / 同步语义用）。"""
        ar = self._active.get(run_id)
        if ar is not None and ar.task is not None:
            await ar.task


run_queue = RunQueue(redis_client)

__all__ = ["RunCancelled", "RunQueue", "run_queue"]
