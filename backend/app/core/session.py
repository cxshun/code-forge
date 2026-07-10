"""Session 存储与登录限流（基于 Redis）。

对齐 D32：HttpOnly Cookie session，内容存 Redis（token → user_id），带 TTL。
登录限流：同 IP 每分钟 5 次（F3.8.1 / api §10.5）。
"""

import secrets

from redis.asyncio import Redis

from app.config import settings

SESSION_PREFIX = "session:"
LOGIN_RATE_PREFIX = "login_rate:"
SESSION_TTL = settings.session_ttl_seconds


def new_session_token() -> str:
    return secrets.token_urlsafe(32)


async def create_session(redis: Redis, user_id: int) -> str:
    token = new_session_token()
    await redis.set(f"{SESSION_PREFIX}{token}", str(user_id), ex=SESSION_TTL)
    return token


async def get_session_user_id(redis: Redis, token: str | None) -> int | None:
    if not token:
        return None
    value = await redis.get(f"{SESSION_PREFIX}{token}")
    return int(value) if value is not None else None


async def delete_session(redis: Redis, token: str | None) -> None:
    if not token:
        return
    await redis.delete(f"{SESSION_PREFIX}{token}")


async def check_login_rate(
    redis: Redis, ip: str, limit: int = 5, window_s: int = 60
) -> bool:
    """同 IP 登录限流。返回是否允许（True=未超限）。"""
    key = f"{LOGIN_RATE_PREFIX}{ip}"
    count = await redis.incr(key)
    if count == 1:
        await redis.expire(key, window_s)
    return count <= limit
