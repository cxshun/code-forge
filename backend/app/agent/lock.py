"""WS 写锁（协调后端分布式锁，design D20 / D33 / §6.6）。

- ``ws_lock:{ws_id}``，整个 Run 期间持有；后台心跳续 TTL（30s TTL / 10s 续期）
- holder token 保证只释放自己的锁（不误删别人）
- 可重入：Run 层复用同一锁实例，子代理不新建（D33）
- 硬超时由 Run 编排层（10 min）兜底，锁本身靠心跳保活

D-ZD.5：去掉 Lua 脚本，改用 CoordinationBackend 的 get + expire / delete 组合操作。
Memory 模式下 asyncio.Lock 保证原子性；Redis 模式下竞态窗口 < 1ms，TTL 30s 兜底。
"""

import asyncio
import logging
import secrets
import time

from app.core.coordination import CoordinationBackend

log = logging.getLogger("agent.lock")

LOCK_PREFIX = "ws_lock:"
LOCK_NOTIFY_PREFIX = "ws_lock_notify:"  # 锁释放通知频道（§6.6 pub/sub，唤醒排队 Run）
LOCK_TTL_S = 30
LOCK_HEARTBEAT_S = 10  # ≈ TTL/3


class WsLock:
    """WS 写锁（async context manager）。

    用法::

        lock = WsLock(backend, ws_id)
        if await lock.acquire(timeout_s=30):
            try:
                ...  # Run / 写工具
            finally:
                await lock.release()
    """

    def __init__(self, backend: CoordinationBackend, ws_id: int, holder: str | None = None) -> None:
        self._backend = backend
        self._ws_id = ws_id
        self._holder = holder or secrets.token_hex(8)
        self._key = f"{LOCK_PREFIX}{ws_id}"
        self._heartbeat: asyncio.Task | None = None
        self._acquired = False

    @property
    def acquired(self) -> bool:
        return self._acquired

    @property
    def holder(self) -> str:
        return self._holder

    async def acquire(self, timeout_s: float | None = None) -> bool:
        """获取锁。timeout_s=None 立即返回（try）；>0 轮询等待。返回是否拿到。"""
        deadline = None if timeout_s is None else time.monotonic() + timeout_s
        while True:
            ok = await self._backend.set(self._key, self._holder, nx=True, ex=LOCK_TTL_S)
            if ok:
                self._acquired = True
                self._heartbeat = asyncio.create_task(self._renew_loop())
                log.info("lock acquired ws=%s holder=%s", self._ws_id, self._holder)
                return True
            if deadline is None or time.monotonic() >= deadline:
                if deadline is not None:
                    log.warning("lock acquire timeout ws=%s holder=%s", self._ws_id, self._holder)
                return False
            await asyncio.sleep(0.2)

    async def _renew_loop(self) -> None:
        try:
            while True:
                await asyncio.sleep(LOCK_HEARTBEAT_S)
                current = await self._backend.get(self._key)
                if current != self._holder:
                    log.warning("lock lost during heartbeat ws=%s", self._ws_id)
                    break
                await self._backend.expire(self._key, LOCK_TTL_S)
        except asyncio.CancelledError:
            pass

    async def release(self) -> None:
        if self._heartbeat:
            self._heartbeat.cancel()
            self._heartbeat = None
        if self._acquired:
            current = await self._backend.get(self._key)
            if current == self._holder:
                await self._backend.delete(self._key)
            self._acquired = False
            # 通知排队中的 Run（§6.6：pub/sub 唤醒，避免空轮询）
            await self._backend.publish(f"{LOCK_NOTIFY_PREFIX}{self._ws_id}", "released")
            log.info("lock released ws=%s", self._ws_id)

    async def __aenter__(self) -> "WsLock":
        await self.acquire()
        return self

    async def __aexit__(self, *exc) -> None:
        await self.release()
