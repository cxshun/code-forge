"""用户管理接口（管理员，api §2.2）。

GET/POST /users、PATCH /users/{id}、POST /users/{id}:reset-password。
"""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import ResetPasswordIn, UserCreateIn, UserOut, UserPatchIn
from app.core.deps import require_admin
from app.core.errors import api_error
from app.core.security import hash_password
from app.db.models import User, UserStatus
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
    _: User = Depends(require_admin),
):
    user = await db.get(User, user_id)
    if user is None:
        raise api_error(404, "用户不存在")
    if body.role is not None:
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
