"""WS 写锁测试（T6.1 验收）。"""

import asyncio

import pytest

from app.agent.lock import WsLock
from app.core.redis_client import redis as redis_client
from app.db.testing import reset_all  # noqa: F401  仅复用 fixture 习惯


@pytest.fixture(autouse=True)
async def _clean():
    await redis_client.flushdb()
    yield
    await redis_client.flushdb()


async def test_acquire_release():
    lock = WsLock(redis_client, ws_id=1)
    assert await lock.acquire() is True
    assert lock.acquired is True
    # 第二把锁（不同 holder）应抢不到
    lock2 = WsLock(redis_client, ws_id=1)
    assert await lock2.acquire() is False
    await lock.release()
    assert not lock.acquired
    # 释放后可重新获取
    assert await lock2.acquire() is True
    await lock2.release()


async def test_concurrent_second_waits():
    lock1 = WsLock(redis_client, ws_id=2)
    await lock1.acquire()

    lock2 = WsLock(redis_client, ws_id=2)

    async def try_acquire():
        return await lock2.acquire(timeout_s=2)

    # 并发：lock2 等待 lock1 释放
    task = asyncio.create_task(try_acquire())
    await asyncio.sleep(0.3)  # lock2 正在等
    assert not lock2.acquired
    await lock1.release()
    got = await task
    assert got is True
    await lock2.release()


async def test_release_on_exception():
    lock = WsLock(redis_client, ws_id=3)
    await lock.acquire()
    try:
        with pytest.raises(RuntimeError):
            try:
                raise RuntimeError("boom")
            finally:
                await lock.release()
    finally:
        pass
    assert not lock.acquired
    # 锁已释放，可被他人获取
    other = WsLock(redis_client, ws_id=3)
    assert await other.acquire() is True
    await other.release()
