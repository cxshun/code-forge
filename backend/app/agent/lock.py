"""WS 写锁（Redis 分布式锁，design D20 / D33 / §6.6）。

- ``ws_lock:{ws_id}``，整个 Run 期间持有；后台心跳续 TTL（30s TTL / 10s 续期）
- holder token 保证只释放自己的锁（不误删别人）
- 可重入：Run 层复用同一锁实例，子代理不新建（D33）
- 硬超时由 Run 编排层（10 min）兜底，锁本身靠心跳保活
"""

import asyncio
import logging
import secrets
import time

from redis.asyncio import Redis

log = logging.getLogger("agent.lock")

LOCK_PREFIX = "ws_lock:"
LOCK_TTL_S = 30
LOCK_HEARTBEAT_S = 10  # ≈ TTL/3

# Lua：仅当 holder 匹配时续期 / 删除（原子，防误删别人的锁）
_RENEW_SCRIPT = (
    "if redis.call('get',KEYS[1])==ARGV[1] "
    "then return redis.call('expire',KEYS[1],ARGV[2]) else return 0 end"
)
_RELEASE_SCRIPT = (
    "if redis.call('get',KEYS[1])==ARGV[1] "
    "then return redis.call('del',KEYS[1]) else return 0 end"
)


class WsLock:
    """WS 写锁（async context manager）。

    用法::

        lock = WsLock(redis, ws_id)
        if await lock.acquire(timeout_s=30):
            try:
                ...  # Run / 写工具
            finally:
                await lock.release()
    """

    def __init__(self, redis: Redis, ws_id: int, holder: str | None = None) -> None:
        self._redis = redis
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
            ok = await self._redis.set(self._key, self._holder, nx=True, ex=LOCK_TTL_S)
            if ok:
                self._acquired = True
                self._heartbeat = asyncio.create_task(self._renew_loop())
                log.info("lock acquired ws=%s holder=%s", self._ws_id, self._holder)
                return True
            if deadline is None or time.monotonic() >= deadline:
                return False
            await asyncio.sleep(0.2)

    async def _renew_loop(self) -> None:
        try:
            while True:
                await asyncio.sleep(LOCK_HEARTBEAT_S)
                renewed = await self._redis.eval(
                    _RENEW_SCRIPT, 1, self._key, self._holder, LOCK_TTL_S
                )
                if not renewed:
                    log.warning("lock lost during heartbeat ws=%s", self._ws_id)
                    break
        except asyncio.CancelledError:
            pass

    async def release(self) -> None:
        if self._heartbeat:
            self._heartbeat.cancel()
            self._heartbeat = None
        if self._acquired:
            await self._redis.eval(_RELEASE_SCRIPT, 1, self._key, self._holder)
            self._acquired = False
            log.info("lock released ws=%s", self._ws_id)

    async def __aenter__(self) -> "WsLock":
        await self.acquire()
        return self

    async def __aexit__(self, *exc) -> None:
        await self.release()
