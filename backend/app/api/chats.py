"""FeishuChat 绑定（api §5.2 / D8 / F3.2.3~5 / T2.3）。

- GET /workspaces/{ws_id}/chats：已绑 FeishuChat 列表
- POST /workspaces/{ws_id}/chats:check：预校验（app_id + chat_id 合法性 + 机器人在群
  + 是否已绑），不落库
- POST /workspaces/{ws_id}/chats：绑定（bot 须在群，否则 422；(app_id, chat_id) 唯一
  约束，已绑 → 409）；成功建 chats/{feishu_chat_id}/memory/ 目录（D18）
- DELETE /workspaces/{ws_id}/chats/{feishu_chat_id}：解绑

``{feishu_chat_id}`` 路径参数为 DB 内部主键；body 中 ``chat_id`` 为飞书原始群 ID。
预校验 / 绑定需引用已注册的 FeishuApp（``app_id``），且当前用户须为该 App owner
（或管理员）——避免用他人 App 凭证。
"""

from fastapi import APIRouter, Depends, Response
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import ChatCheckIn, ChatOut
from app.core.deps import require_user, require_ws_owner
from app.core.errors import api_error
from app.core.security import decrypt_secret
from app.db.models import FeishuApp, FeishuChat, User, Workspace
from app.db.session import get_db
from app.feishu.client import FeishuAPIError, FeishuClient
from app.workspace.fs import create_chat_memory_skeleton

router = APIRouter(prefix="/workspaces", tags=["chats"])


async def _resolve_app(app_id: str, user: User, db: AsyncSession) -> FeishuApp:
    """按 app_id 查 FeishuApp 并校验当前用户为 owner（或管理员）。"""
    app = await db.scalar(select(FeishuApp).where(FeishuApp.app_id == app_id))
    if app is None:
        raise api_error(422, f"飞书 App {app_id} 未注册")
    if app.owner_id != user.id and user.role != "admin":
        raise api_error(403, "无权使用该飞书 App")
    return app


async def _probe_chat(app: FeishuApp, chat_id: str) -> dict:
    """调飞书 API 探测 chat：返回 valid/bot_in_chat/chat_name。

    bot 无权限 / chat 不存在 → get_chat 返回 None（client 已合并两种情形），
    故 valid 与 bot_in_chat 在 MVP 同信号（client 行为所致，已记录）。
    """
    client = FeishuClient(app.app_id, decrypt_secret(app.app_secret_enc))
    try:
        data = await client.get_chat(chat_id)
    except FeishuAPIError as e:
        raise api_error(502, f"飞书 API 调用失败: {e}") from e
    if data is None:
        return {"valid": False, "bot_in_chat": False, "chat_name": None}
    return {"valid": True, "bot_in_chat": True, "chat_name": getattr(data, "name", None)}


@router.get("/{ws_id}/chats")
async def list_chats(
    ws: Workspace = Depends(require_ws_owner),
    db: AsyncSession = Depends(get_db),
):
    chats = (
        await db.scalars(
            select(FeishuChat)
            .where(FeishuChat.workspace_id == ws.id)
            .order_by(FeishuChat.id)
        )
    ).all()
    return {
        "items": [
            ChatOut(
                id=c.id, app_id=c.app_id, chat_id=c.chat_id,
                chat_name=c.chat_name, workspace_id=c.workspace_id,
            )
            for c in chats
        ],
        "total": len(chats),
    }


@router.post("/{ws_id}/chats:check")
async def check_chat(
    body: ChatCheckIn,
    ws: Workspace = Depends(require_ws_owner),
    user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    app = await _resolve_app(body.app_id, user, db)
    probe = await _probe_chat(app, body.chat_id)
    # 是否已绑（任意 WS）
    existing = await db.scalar(
        select(FeishuChat).where(
            FeishuChat.app_id == body.app_id, FeishuChat.chat_id == body.chat_id
        )
    )
    return {
        "valid": probe["valid"],
        "bot_in_chat": probe["bot_in_chat"],
        "chat_name": probe["chat_name"],
        "existing_binding": {
            "feishu_chat_id": existing.id,
            "workspace_id": existing.workspace_id,
            "is_this_ws": existing.workspace_id == ws.id,
        }
        if existing
        else None,
    }


@router.post("/{ws_id}/chats", status_code=201)
async def bind_chat(
    body: ChatCheckIn,
    ws: Workspace = Depends(require_ws_owner),
    user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    app = await _resolve_app(body.app_id, user, db)
    probe = await _probe_chat(app, body.chat_id)
    if not probe["bot_in_chat"]:
        raise api_error(422, "机器人不在该群或群不存在")
    chat = FeishuChat(
        workspace_id=ws.id,
        app_id=body.app_id,
        chat_id=body.chat_id,
        chat_name=probe["chat_name"],
    )
    db.add(chat)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise api_error(409, "该 (app_id, chat_id) 已绑定", "conflict") from None
    await db.refresh(chat)
    # 建 chat memory 目录骨架（D18：MEMORY.md 索引 + sessions/traces）
    create_chat_memory_skeleton(ws.id, chat.id)
    return ChatOut(
        id=chat.id, app_id=chat.app_id, chat_id=chat.chat_id,
        chat_name=chat.chat_name, workspace_id=chat.workspace_id,
    )


@router.delete("/{ws_id}/chats/{feishu_chat_id}", status_code=204)
async def unbind_chat(
    feishu_chat_id: int,
    ws: Workspace = Depends(require_ws_owner),
    db: AsyncSession = Depends(get_db),
):
    chat = await db.get(FeishuChat, feishu_chat_id)
    if chat is None or chat.workspace_id != ws.id:
        raise api_error(404, "FeishuChat 不存在")
    await db.delete(chat)
    await db.commit()
    return Response(status_code=204)
