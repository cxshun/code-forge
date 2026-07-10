"""消息去重（design D38）：以飞书 message_id 为幂等键，Redis SETNX + 短 TTL。

接入层收到消息后、进 Run 队列前调用 ``acquire``；重连补推的重复消息返回 False 被丢弃。
"""

from redis.asyncio import Redis

DEDUP_PREFIX = "msg_dedup:"
DEDUP_TTL_SECONDS = 600  # 10 min


async def acquire(redis: Redis, message_id: str) -> bool:
    """首次见返回 True（应处理），重复返回 False（丢弃）。"""
    ok = await redis.set(
        f"{DEDUP_PREFIX}{message_id}", "1", nx=True, ex=DEDUP_TTL_SECONDS
    )
    return ok is not None
