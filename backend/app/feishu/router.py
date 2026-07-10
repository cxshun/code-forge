"""路由层：(app_id, chat_id) → feishu_chat_id → ws_id（design §6.1）。

接入层收到消息后三级查找：飞书原始 (app_id, chat_id) → DB FeishuChat（内部主键）
→ workspace_id。未绑定的 chat 返回 None（接入层忽略或提示）。
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import FeishuChat


async def resolve_feishu_chat(
    db: AsyncSession, app_id: str, chat_id: str
) -> FeishuChat | None:
    """(app_id, chat_id) → FeishuChat 记录；未绑定返回 None。"""
    return await db.scalar(
        select(FeishuChat).where(
            FeishuChat.app_id == app_id, FeishuChat.chat_id == chat_id
        )
    )
