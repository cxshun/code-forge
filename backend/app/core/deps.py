"""FastAPI 依赖：require_user / require_admin / require_ws_owner / assert_res_owner。

对齐 api §1.6 / §1.8、D21（后台 owner 校验）、D31（ws_id 取自服务端）。
"""

from fastapi import Cookie, Depends, Path, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.errors import api_error
from app.core.redis_client import redis as redis_client
from app.core.session import get_session_user_id
from app.db.models import User, UserRole, UserStatus, Workspace
from app.db.session import get_db

SESSION_COOKIE = settings.session_cookie_name


def client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
    token: str | None = Cookie(default=None, alias=SESSION_COOKIE),
) -> User:
    """解析 session cookie → User；未登录或失效返回 401。"""
    user_id = await get_session_user_id(redis_client, token)
    if user_id is None:
        raise api_error(401, "未登录")
    user = await db.get(User, user_id)
    if user is None or user.status != UserStatus.active.value:
        raise api_error(401, "未登录或账号已停用")
    return user


async def require_user(user: User = Depends(get_current_user)) -> User:
    """登录用户即可。"""
    return user


async def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != UserRole.admin.value:
        raise api_error(403, "需要管理员权限")
    return user


async def require_ws_owner(
    ws_id: int = Path(),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Workspace:
    """校验当前用户是 WS owner（或管理员）。返回该 WS。"""
    ws = await db.get(Workspace, ws_id)
    if ws is None:
        raise api_error(404, "工作空间不存在")
    if ws.owner_id != user.id and user.role != UserRole.admin.value:
        raise api_error(403, "非该工作空间 owner")
    return ws


async def assert_res_owner(owner_id: int, user: User) -> None:
    """广场资源（Skill / MCP）owner 校验。路由内显式调用。"""
    if owner_id != user.id and user.role != UserRole.admin.value:
        raise api_error(403, "非该资源 owner")
