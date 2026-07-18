"""路由层：(app_id, chat_id) → feishu_chat_id → ws_id（design §6.1）。

接入层收到消息后三级查找：飞书原始 (app_id, chat_id) → DB FeishuChat（内部主键）
→ workspace_id。未绑定的 chat 返回 None（接入层忽略或提示）。

P2 direct-chat 扩展：p2p 单聊未绑定时由 ``auto_bind_p2p_chat`` 自动建 FeishuChat
指向默认 WS（design D-DC.2 / D-DC.3）。
"""

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import FeishuChat, Workspace


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
    default_ws_id: int | None,
) -> FeishuChat | None:
    """p2p chat 未绑定时自动建 FeishuChat 指向默认 WS（D-DC.2）。

    - default_ws_id 为 None → 返回 None（未开启自动接受）
    - 默认 WS 不存在 / 已删 → 返回 None（NF2.5）
    - 唯一键冲突（并发首次消息）→ rollback 后回查既有记录
    - 其他异常 → rollback 后返回 None（不向上抛，NF2.4）
    """
    if default_ws_id is None:
        return None
    ws = await db.get(Workspace, default_ws_id)
    if ws is None:
        return None
    chat_name = f"p2p:{sender_open_id[-8:]}" if sender_open_id else None
    chat = FeishuChat(
        app_id=app_id,
        chat_id=chat_id,
        workspace_id=default_ws_id,
        chat_name=chat_name,
    )
    db.add(chat)
    try:
        await db.commit()
        await db.refresh(chat)
        return chat
    except IntegrityError:
        await db.rollback()
        return await resolve_feishu_chat(db, app_id, chat_id)
    except Exception:
        await db.rollback()
        return None
