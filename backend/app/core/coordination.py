"""协调后端抽象层（D-ZD.4）。

提供 ``CoordinationBackend`` 抽象接口，``MemoryBackend``（纯内存）和
``RedisBackend``（Redis）两种实现。上层代码（lock / queue / dedup / session）
只依赖接口，不感知后端类型。

- ``redis_url`` 非空 → ``RedisBackend``（委托 ``redis.asyncio.Redis``）
- ``redis_url`` 空   → ``MemoryBackend``（进程内 dict + asyncio.Lock）

MemoryBackend 的 TTL 采用惰性清理（访问时检查过期），sorted set 不设 TTL
（队列 / 序列由调用方手动 zrem 清理）。
"""

import asyncio
import time
from abc import ABC, abstractmethod


class CoordinationBackend(ABC):
    """协调后端接口：KV + 计数 + sorted set + pub/sub。

    方法签名与 ``redis.asyncio.Redis`` 的对应命令一致，返回值语义也一致。
    """

    # ---- KV with TTL ----

    @abstractmethod
    async def set(self, key: str, value: str, *, ex: int | None = None, nx: bool = False) -> bool:
        """SET key value [EX seconds] [NX]。返回是否成功设置。"""

    @abstractmethod
    async def get(self, key: str) -> str | None:
        """GET key。不存在返回 None。"""

    @abstractmethod
    async def delete(self, key: str) -> int:
        """DEL key。返回删除的 key 数量（0 或 1）。"""

    # ---- 计数 ----

    @abstractmethod
    async def incr(self, key: str) -> int:
        """INCR key。返回递增后的值。"""

    @abstractmethod
    async def expire(self, key: str, seconds: int) -> bool:
        """EXPIRE key seconds。返回是否成功设置（key 不存在返回 False）。"""

    # ---- Sorted set ----

    @abstractmethod
    async def zadd(self, key: str, mapping: dict[str, int]) -> int:
        """ZADD key mapping。返回新增元素数（不含更新）。"""

    @abstractmethod
    async def zrank(self, key: str, member: str) -> int | None:
        """ZRANK key member。返回 0-based 排名，不存在返回 None。"""

    @abstractmethod
    async def zrem(self, key: str, *members: str) -> int:
        """ZREM key members。返回删除的元素数。"""

    # ---- Pub/sub ----

    @abstractmethod
    async def publish(self, channel: str, message: str) -> int:
        """PUBLISH channel message。返回接收者数量（MemoryBackend 恒为 0）。"""

    @abstractmethod
    async def flushdb(self) -> None:
        """清空所有数据（测试用）。"""


class MemoryBackend(CoordinationBackend):
    """纯内存协调后端（单进程，D-ZD.4）。

    数据结构：
    - KV：``dict[str, tuple[str, float | None]]``（value + expire_at）
    - Sorted set：``dict[str, dict[str, float]]``（key → {member: score}）
    - 原子性：``asyncio.Lock`` 保护所有 check-then-act 操作

    TTL 过期采用惰性清理：``get`` / ``set(nx=True)`` 时检查 key 是否过期，
    过期则删除并视为不存在。不做定期扫描（单实例内存增长可接受）。
    """

    def __init__(self) -> None:
        self._kv: dict[str, tuple[str, float | None]] = {}
        self._zset: dict[str, dict[str, float]] = {}
        self._lock = asyncio.Lock()

    def _is_expired(self, key: str) -> bool:
        entry = self._kv.get(key)
        if entry is None:
            return True
        _, expire_at = entry
        if expire_at is not None and time.monotonic() >= expire_at:
            del self._kv[key]
            return True
        return False

    async def set(self, key: str, value: str, *, ex: int | None = None, nx: bool = False) -> bool:
        expire_at = time.monotonic() + ex if ex else None
        async with self._lock:
            exists = not self._is_expired(key)
            if nx and exists:
                return False
            self._kv[key] = (value, expire_at)
            return True

    async def get(self, key: str) -> str | None:
        async with self._lock:
            if self._is_expired(key):
                return None
            return self._kv[key][0]

    async def delete(self, key: str) -> int:
        async with self._lock:
            if key in self._kv:
                del self._kv[key]
                return 1
            return 0

    async def incr(self, key: str) -> int:
        async with self._lock:
            entry = self._kv.get(key)
            if entry is None or (entry[1] is not None and time.monotonic() >= entry[1]):
                self._kv[key] = ("1", None)
                return 1
            val = int(entry[0]) + 1
            self._kv[key] = (str(val), entry[1])
            return val

    async def expire(self, key: str, seconds: int) -> bool:
        async with self._lock:
            entry = self._kv.get(key)
            if entry is None or (entry[1] is not None and time.monotonic() >= entry[1]):
                return False
            self._kv[key] = (entry[0], time.monotonic() + seconds)
            return True

    async def zadd(self, key: str, mapping: dict[str, int]) -> int:
        async with self._lock:
            zset = self._zset.setdefault(key, {})
            added = 0
            for member, score in mapping.items():
                if member not in zset:
                    added += 1
                zset[member] = float(score)
            return added

    async def zrank(self, key: str, member: str) -> int | None:
        async with self._lock:
            zset = self._zset.get(key)
            if zset is None or member not in zset:
                return None
            # rank = 比 member score 小的元素个数
            score = zset[member]
            return sum(1 for s in zset.values() if s < score)

    async def zrem(self, key: str, *members: str) -> int:
        async with self._lock:
            zset = self._zset.get(key)
            if zset is None:
                return 0
            removed = 0
            for m in members:
                if m in zset:
                    del zset[m]
                    removed += 1
            if not zset:
                del self._zset[key]
            return removed

    async def publish(self, channel: str, message: str) -> int:
        # 单进程：queue 通过 asyncio.Condition 通知，pub/sub 无消费者
        return 0

    async def flushdb(self) -> None:
        async with self._lock:
            self._kv.clear()
            self._zset.clear()


class RedisBackend(CoordinationBackend):
    """Redis 协调后端（委托 ``redis.asyncio.Redis``）。"""

    def __init__(self, redis) -> None:
        self._redis = redis

    async def set(self, key: str, value: str, *, ex: int | None = None, nx: bool = False) -> bool:
        result = await self._redis.set(key, value, ex=ex, nx=nx)
        return bool(result)

    async def get(self, key: str) -> str | None:
        return await self._redis.get(key)

    async def delete(self, key: str) -> int:
        return await self._redis.delete(key)

    async def incr(self, key: str) -> int:
        return await self._redis.incr(key)

    async def expire(self, key: str, seconds: int) -> bool:
        return bool(await self._redis.expire(key, seconds))

    async def zadd(self, key: str, mapping: dict[str, int]) -> int:
        return await self._redis.zadd(key, mapping)

    async def zrank(self, key: str, member: str) -> int | None:
        return await self._redis.zrank(key, member)

    async def zrem(self, key: str, *members: str) -> int:
        return await self._redis.zrem(key, *members)

    async def publish(self, channel: str, message: str) -> int:
        return await self._redis.publish(channel, message)

    async def flushdb(self) -> None:
        await self._redis.flushdb()


__all__ = ["CoordinationBackend", "MemoryBackend", "RedisBackend"]
