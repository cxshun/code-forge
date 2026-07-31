"""MemoryBackend 单元测试（T9 验收，D-ZD.4）。

覆盖 KV + TTL + NX 语义、incr / expire、sorted set（zadd / zrank / zrem）、
flushdb、publish（no-op）。
"""

import asyncio

import pytest

from app.core.coordination import MemoryBackend

pytestmark = pytest.mark.asyncio


@pytest.fixture
def b() -> MemoryBackend:
    return MemoryBackend()


# ---- KV ----


async def test_set_get(b: MemoryBackend):
    assert await b.set("k1", "v1") is True
    assert await b.get("k1") == "v1"


async def test_get_missing(b: MemoryBackend):
    assert await b.get("nope") is None


async def test_delete(b: MemoryBackend):
    await b.set("k1", "v1")
    assert await b.delete("k1") == 1
    assert await b.get("k1") is None
    assert await b.delete("k1") == 0  # 已不存在


async def test_set_nx(b: MemoryBackend):
    assert await b.set("k1", "v1", nx=True) is True
    assert await b.set("k1", "v2", nx=True) is False  # 已存在，NX 失败
    assert await b.get("k1") == "v1"  # 值未被覆盖


async def test_set_nx_on_expired_key(b: MemoryBackend):
    """过期的 key 应被视为不存在，NX 可以设置。"""
    await b.set("k1", "v1", ex=1)
    await asyncio.sleep(1.1)
    assert await b.set("k1", "v2", nx=True) is True
    assert await b.get("k1") == "v2"


# ---- TTL ----


async def test_set_with_ttl(b: MemoryBackend):
    await b.set("k1", "v1", ex=1)
    assert await b.get("k1") == "v1"
    await asyncio.sleep(1.1)
    assert await b.get("k1") is None  # 已过期


async def test_set_overwrite_removes_ttl(b: MemoryBackend):
    """不带 ex 的 set 覆盖带 TTL 的 key，TTL 应被清除。"""
    await b.set("k1", "v1", ex=1)
    await b.set("k1", "v2")  # 无 ex
    await asyncio.sleep(1.1)
    assert await b.get("k1") == "v2"  # 仍在


# ---- incr ----


async def test_incr_new_key(b: MemoryBackend):
    assert await b.incr("counter") == 1
    assert await b.incr("counter") == 2
    assert await b.incr("counter") == 3


async def test_incr_with_ttl(b: MemoryBackend):
    """incr 不影响已有 TTL。"""
    await b.set("counter", "5", ex=10)
    assert await b.incr("counter") == 6


async def test_incr_expired_key(b: MemoryBackend):
    await b.set("counter", "5", ex=1)
    await asyncio.sleep(1.1)
    assert await b.incr("counter") == 1  # 过期后从 1 开始


# ---- expire ----


async def test_expire(b: MemoryBackend):
    await b.set("k1", "v1")
    assert await b.expire("k1", 1) is True
    assert await b.get("k1") == "v1"
    await asyncio.sleep(1.1)
    assert await b.get("k1") is None


async def test_expire_missing_key(b: MemoryBackend):
    assert await b.expire("nope", 10) is False


# ---- Sorted set ----


async def test_zadd_zrank(b: MemoryBackend):
    assert await b.zadd("q", {"a": 1}) == 1  # 新增
    assert await b.zadd("q", {"b": 2}) == 1
    assert await b.zadd("q", {"a": 1}) == 0  # 已存在（更新 score，不计新增）
    assert await b.zrank("q", "a") == 0
    assert await b.zrank("q", "b") == 1
    assert await b.zrank("q", "c") is None  # 不存在


async def test_zrem(b: MemoryBackend):
    await b.zadd("q", {"a": 1, "b": 2, "c": 3})
    assert await b.zrem("q", "a", "b") == 2
    assert await b.zrank("q", "a") is None
    assert await b.zrank("q", "c") == 0  # 只剩 c


async def test_zrem_missing_member(b: MemoryBackend):
    await b.zadd("q", {"a": 1})
    assert await b.zrem("q", "nope") == 0


async def test_zrank_empty_zset(b: MemoryBackend):
    assert await b.zrank("nope", "a") is None


# ---- flushdb ----


async def test_flushdb(b: MemoryBackend):
    await b.set("k1", "v1")
    await b.zadd("q", {"a": 1})
    await b.incr("c")
    await b.flushdb()
    assert await b.get("k1") is None
    assert await b.zrank("q", "a") is None
    assert await b.incr("c") == 1  # 从头开始


# ---- publish ----


async def test_publish_noop(b: MemoryBackend):
    assert await b.publish("ch", "msg") == 0
