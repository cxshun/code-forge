"""飞书 App 注册（api §3 / D7）。

每个 App 对应一条独立飞书 WebSocket 长连接（T4.2）。app_secret 加密存储
（app_secret_enc），列表 / 详情脱敏；完整 secret 仅创建时返回一次。删除前需解绑
所有 FeishuChat。
"""

import logging

from fastapi import APIRouter, Depends, Response
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import FeishuAppCreateIn, FeishuAppOut, FeishuAppPatchIn
from app.core.deps import assert_res_owner, require_user
from app.core.errors import api_error
from app.core.security import decrypt_secret, encrypt_secret, mask_secret
from app.db.models import FeishuApp, FeishuChat, User
from app.db.session import get_db
from app.feishu.ws_pool import ws_pool

log = logging.getLogger("api.feishu_apps")

router = APIRouter(prefix="/feishu-apps", tags=["feishu-apps"])


def _app_out(a: FeishuApp, owner_name: str = "") -> FeishuAppOut:
    return FeishuAppOut(
        id=a.id,
        app_id=a.app_id,
        app_secret_masked=mask_secret(decrypt_secret(a.app_secret_enc)),
        name=a.name,
        owner_id=a.owner_id,
        owner_name=owner_name or "",
        connection_status=a.connection_status,
    )


@router.get("")
async def list_apps(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_user),
):
    apps = (
        await db.scalars(
            select(FeishuApp).where(FeishuApp.owner_id == user.id).order_by(FeishuApp.id)
        )
    ).all()
    return {"items": [_app_out(a, owner_name=user.username) for a in apps], "total": len(apps)}


@router.post("", status_code=201)
async def create_app(
    body: FeishuAppCreateIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_user),
):
    app = FeishuApp(
        app_id=body.app_id,
        app_secret_enc=encrypt_secret(body.app_secret),
        name=body.name,
        owner_id=user.id,
        connection_status="connecting",
    )
    db.add(app)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise api_error(409, "app_id 已存在", "conflict") from None
    await db.refresh(app)
    # 启动飞书 WS 长连接（D7 / T4.2）
    try:
        ws_pool.add_app(app.app_id, body.app_secret)
    except Exception:
        log.exception("feishu.ws.add_failed", app_id=app.app_id)
    # 完整 secret 仅创建时返回一次（api §3）
    out = _app_out(app, owner_name=user.username).model_dump()
    out["app_secret"] = body.app_secret
    return out


@router.get("/{app_pk}")
async def get_app(
    app_pk: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_user),
):
    a = await db.get(FeishuApp, app_pk)
    if a is None:
        raise api_error(404, "飞书 App 不存在")
    await assert_res_owner(a.owner_id, user)
    return _app_out(a, owner_name=user.username)


@router.patch("/{app_pk}")
async def patch_app(
    app_pk: int,
    body: FeishuAppPatchIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_user),
):
    a = await db.get(FeishuApp, app_pk)
    if a is None:
        raise api_error(404, "飞书 App 不存在")
    await assert_res_owner(a.owner_id, user)
    if body.name is not None:
        a.name = body.name
    if body.app_secret is not None:
        a.app_secret_enc = encrypt_secret(body.app_secret)
        a.connection_status = "connecting"
        # secret 变更，重建 WS 连接
        ws_pool.remove_app(a.app_id)
        try:
            ws_pool.add_app(a.app_id, body.app_secret)
        except Exception:
            log.exception("feishu.ws.add_failed", app_id=a.app_id)
    await db.commit()
    await db.refresh(a)
    return _app_out(a, owner_name=user.username)


@router.delete("/{app_pk}", status_code=204)
async def delete_app(
    app_pk: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_user),
):
    a = await db.get(FeishuApp, app_pk)
    if a is None:
        raise api_error(404, "飞书 App 不存在")
    await assert_res_owner(a.owner_id, user)
    # 删除前需解绑所有 FeishuChat（api §3）
    count = (
        await db.scalar(
            select(func.count())
            .select_from(FeishuChat)
            .where(FeishuChat.app_id == a.app_id)
        )
    ) or 0
    if count:
        raise api_error(422, f"该 App 绑定了 {count} 个 FeishuChat，请先解绑")
    # 从连接池移除（连接随 daemon 线程退出清理）
    ws_pool.remove_app(a.app_id)
    await db.delete(a)
    await db.commit()
    return Response(status_code=204)
