"""用户管理接口（管理员，api §2.2）。

GET/POST /users、PATCH /users/{id}、POST /users/{id}:reset-password。
"""

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import ResetPasswordIn, UserCreateIn, UserOut, UserPatchIn
from app.core.deps import require_admin
from app.core.errors import api_error
from app.core.security import hash_password
from app.db.models import User, UserRole, UserStatus
from app.db.session import get_db

router = APIRouter(prefix="/users", tags=["users"])


def _user_out(user: User) -> UserOut:
    return UserOut(
        id=user.id, username=user.username, role=user.role, status=user.status
    )


@router.get("")
async def list_users(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    users = (await db.scalars(select(User).order_by(User.id))).all()
    return {"items": [_user_out(u) for u in users], "total": len(users)}


@router.post("", status_code=201)
async def create_user(
    body: UserCreateIn,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    user = User(
        username=body.username,
        password_hash=hash_password(body.password),
        role=body.role,
        status=UserStatus.active.value,
    )
    db.add(user)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise api_error(409, "用户名已存在", "conflict") from None
    await db.refresh(user)
    return _user_out(user)


@router.patch("/{user_id}")
async def patch_user(
    user_id: int,
    body: UserPatchIn,
    db: AsyncSession = Depends(get_db),
    current: User = Depends(require_admin),
):
    user = await db.get(User, user_id)
    if user is None:
        raise api_error(404, "用户不存在")
    if body.role is not None and body.role != user.role:
        # 降级保护：仅 admin → user 时拦截（user → admin 升级无风险）。
        # 禁止降级自己、禁止降级最后一个管理员，避免管理后台被自锁。
        is_demotion = (
            user.role == UserRole.admin.value
            and body.role == UserRole.user.value
        )
        if is_demotion:
            if user_id == current.id:
                raise api_error(400, "不能降级自己的管理员角色")
            admin_count = await db.scalar(
                select(func.count(User.id)).where(User.role == UserRole.admin.value)
            )
            if admin_count is not None and admin_count <= 1:
                raise api_error(400, "系统至少需要保留一个管理员")
        user.role = body.role
    if body.status is not None:
        user.status = body.status
    await db.commit()
    await db.refresh(user)
    return _user_out(user)


@router.post("/{user_id}:reset-password")
async def reset_password(
    user_id: int,
    body: ResetPasswordIn,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    user = await db.get(User, user_id)
    if user is None:
        raise api_error(404, "用户不存在")
    user.password_hash = hash_password(body.new_password)
    await db.commit()
    return {"ok": True}
