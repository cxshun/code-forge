"""鉴权接口（D32 / api §2.1）。

- POST /auth/login：账号密码 → HttpOnly Cookie session（同 IP 5 次/分钟限流）
- POST /auth/logout：清 session
- GET /auth/me：当前用户 + 可访问 WS 列表
- POST /auth/change-password：改自己的密码
"""

from fastapi import APIRouter, Cookie, Depends, Request, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import ChangePasswordIn, LoginIn, UserOut, WorkspaceBrief
from app.config import settings
from app.core.deps import SESSION_COOKIE, client_ip, get_current_user
from app.core.errors import api_error
from app.core.redis_client import redis as redis_client
from app.core.security import hash_password, verify_password
from app.core.session import SESSION_TTL, check_login_rate, create_session, delete_session
from app.db.models import User, UserStatus, Workspace
from app.db.session import get_db

router = APIRouter(prefix="/auth", tags=["auth"])


def _user_out(user: User) -> UserOut:
    return UserOut(
        id=user.id, username=user.username, role=user.role, status=user.status
    )


@router.post("/login")
async def login(
    body: LoginIn,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    ip = client_ip(request)
    if not await check_login_rate(redis_client, ip):
        raise api_error(429, "登录尝试过于频繁，请稍后再试", "rate_limited")

    user = await db.scalar(select(User).where(User.username == body.username))
    if (
        user is None
        or user.status != UserStatus.active.value
        or not verify_password(body.password, user.password_hash)
    ):
        # 统一错误信息，避免用户名枚举
        raise api_error(401, "用户名或密码错误")

    token = await create_session(redis_client, user.id)
    response.set_cookie(
        SESSION_COOKIE,
        token,
        httponly=True,
        samesite="lax",
        secure=settings.is_prod,
        max_age=SESSION_TTL,
    )
    return {"user": _user_out(user)}


@router.post("/logout")
async def logout(
    response: Response,
    token: str | None = Cookie(default=None, alias=SESSION_COOKIE),
):
    await delete_session(redis_client, token)
    response.delete_cookie(SESSION_COOKIE)
    return {"ok": True}


@router.get("/me")
async def me(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    workspaces = (
        await db.scalars(
            select(Workspace).where(Workspace.owner_id == user.id)
        )
    ).all()
    return {
        "user": _user_out(user),
        "workspaces": [WorkspaceBrief(id=w.id, name=w.name) for w in workspaces],
    }


@router.post("/change-password")
async def change_password(
    body: ChangePasswordIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not verify_password(body.old_password, user.password_hash):
        raise api_error(401, "原密码错误")
    user.password_hash = hash_password(body.new_password)
    await db.commit()
    return {"ok": True}
