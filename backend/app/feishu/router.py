"""路由层：(app_id, chat_id) → feishu_chat_id → ws_id（design §6.1）。

接入层收到消息后三级查找：飞书原始 (app_id, chat_id) → DB FeishuChat（内部主键）
→ workspace_id。未绑定的 chat 返回 None（接入层忽略或提示）。

P2 direct-chat 扩展（D-DC.7）：p2p 单聊未绑定时由 ``auto_bind_p2p_chat`` 自动新建
专属 Workspace + FeishuChat（一人一个 WS），owner 由 ``P2P_WORKSPACE_OWNER_ID`` 指定。
"""

import logging

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import FeishuChat, User, UserStatus, Workspace
from app.workspace.fs import create_workspace_skeleton

log = logging.getLogger("feishu.router")


async def resolve_feishu_chat(
    db: AsyncSession, app_id: str, chat_id: str
) -> FeishuChat | None:
    """(app_id, chat_id) → FeishuChat 记录；未绑定返回 None。"""
    return await db.scalar(
        select(FeishuChat).where(
            FeishuChat.app_id == app_id, FeishuChat.chat_id == chat_id
        )
    )


async def auto_bind_p2p_chat(
    db: AsyncSession,
    app_id: str,
    chat_id: str,
    sender_open_id: str,
    owner_id: int | None,
    sender_name: str | None = None,
) -> FeishuChat | None:
    """p2p chat 未绑定时自动建专属 WS + FeishuChat（D-DC.2 / D-DC.7）；失败返回 None。

    - owner_id 为 None → 返回 None（未开启自动接受）
    - owner User 不存在 / 已停用 → 返回 None（NF2.5）
    - sender_name 提供时用作 WS 名 + chat_name（与群聊一致，仅触发方式不同）
    - 唯一键冲突（并发首次消息）→ rollback（含新建 WS）后回查既有记录
    - 其他异常 → rollback 后返回 None（不向上抛，NF2.4）
    """
    if owner_id is None:
        log.info("auto_bind skipped: p2p_workspace_owner_id 未配置")
        return None
    owner = await db.get(User, owner_id)
    if owner is None:
        log.warning(
            "auto_bind skipped: owner_id=%s 的用户不存在", owner_id
        )
        return None
    if owner.status != UserStatus.active.value:
        log.warning(
            "auto_bind skipped: owner_id=%s 状态为 %s，需要 active",
            owner_id, owner.status,
        )
        return None

    if sender_name:
        ws_name = f"{sender_name}的私聊"
        chat_name = sender_name
    elif sender_open_id:
        ws_name = f"p2p:{sender_open_id[-8:]}"
        chat_name = ws_name
    else:
        ws_name = "p2p:anonymous"
        chat_name = None
    ws = Workspace(name=ws_name, owner_id=owner_id)
    db.add(ws)
    await db.flush()  # 拿到 ws.id 再建 FeishuChat
    chat = FeishuChat(
        app_id=app_id,
        chat_id=chat_id,
        workspace_id=ws.id,
        chat_name=chat_name,
    )
    db.add(chat)
    try:
        await db.commit()
        await db.refresh(ws)
        await db.refresh(chat)
    except IntegrityError:  # 唯一键冲突 = 并发首次消息，对方已建记录
        await db.rollback()
        return await resolve_feishu_chat(db, app_id, chat_id)
    except Exception:
        log.exception("auto_bind_p2p_chat failed: app=%s chat=%s", app_id, chat_id)
        await db.rollback()
        return None

    try:
        create_workspace_skeleton(ws.id)  # commit 后建目录，失败仅 log（DB 已落地）
    except Exception:
        log.exception("create_workspace_skeleton failed: ws_id=%s", ws.id)
    return chat
