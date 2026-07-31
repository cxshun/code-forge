"""协调后端单例（D-ZD.4）。

redis_url 非空 → RedisBackend（Redis）
redis_url 空   → MemoryBackend（纯内存）

上层代码统一使用 ``CoordinationBackend`` 接口，不感知后端类型。
"""

from app.config import settings
from app.core.coordination import CoordinationBackend, MemoryBackend

if settings.is_redis:
    from redis.asyncio import Redis

    from app.core.coordination import RedisBackend

    redis: CoordinationBackend = RedisBackend(
        Redis.from_url(settings.redis_url, decode_responses=True)
    )
else:
    redis: CoordinationBackend = MemoryBackend()

__all__ = ["redis"]
