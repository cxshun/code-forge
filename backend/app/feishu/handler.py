"""接入层消息处理（design §6.1）。

收到飞书消息后：D38 去重 → (app_id, chat_id) 路由 → @机器人识别（仅群聊）→
即时 Thinking 卡片（F3.1.5）。触发 Agent Run 属 B5，此处不涉及。

引用回复解析（D39）：parse_message_event 已提取 parent_id；被引用正文拉取由
client.get_message 在此完成（parent_id 存在时），注入到 user message 的逻辑在
Agent 层（B5）实现。
"""

import logging

from app.core.redis_client import redis as redis_client
from app.db.session import async_session_factory
from app.feishu.cards import build_progress_card
from app.feishu.client import FeishuClient
from app.feishu.dedup import acquire
from app.feishu.quote import parse_message_event
from app.feishu.router import resolve_feishu_chat

log = logging.getLogger("feishu.handler")


async def handle_message(
    event_dict: dict, app_id: str, app_secret: str, bot_open_id: str | None = None
) -> None:
    ctx = parse_message_event(event_dict, bot_open_id)
    if ctx is None:
        return

    # 仅群聊 + @机器人触发（D21 / F3.1.3）
    if ctx.chat_type != "group" or not ctx.at_bot:
        log.info("ignore (chat_type=%s at_bot=%s): %s", ctx.chat_type, ctx.at_bot, ctx.message_id)
        return

    # D38 去重（进 Run 队列前）
    if not await acquire(redis_client, ctx.message_id):
        log.info("duplicate dropped: %s", ctx.message_id)
        return

    # 路由 (app_id, chat_id) → ws_id
    async with async_session_factory() as db:
        chat = await resolve_feishu_chat(db, ctx.app_id, ctx.chat_id)
    if chat is None:
        log.info("unbound chat, ignore: app=%s chat=%s", ctx.app_id, ctx.chat_id)
        return

    log.info(
        "routed: app=%s chat=%s -> ws_id=%s sender=%s text=%r parent=%s",
        ctx.app_id, ctx.chat_id, chat.workspace_id, ctx.sender_open_id,
        ctx.text[:80], ctx.parent_id,
    )

    # T4.5 即时 Thinking 反馈（收到消息 < 1s，F3.1.5）
    client = FeishuClient(app_id, app_secret)
    footer = f"sender {ctx.sender_open_id[-8:]}" if ctx.sender_open_id else None
    try:
        await client.send_card(ctx.chat_id, build_progress_card("⏳ 思考中…", footer=footer))
    except Exception:
        log.exception("thinking card failed: %s", ctx.message_id)
