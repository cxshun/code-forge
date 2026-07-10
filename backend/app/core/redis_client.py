"""Redis 客户端（session / 限流 / 任务队列 / 事件总线 / 缓存）。

对齐 design §3.3。async 客户端，decode_responses=True（直接拿 str）。
"""

from redis.asyncio import Redis

from app.config import settings

redis: Redis = Redis.from_url(settings.redis_url, decode_responses=True)
