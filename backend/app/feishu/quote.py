"""引用回复与消息解析（design D39 / spec F3.1.10 / F3.1.3）。

从飞书 ``im.message.receive_v1`` 事件 JSON 提取结构化上下文：触发者 open_id、纯文本
（去 ``<at>`` 标签）、是否 @机器人、被引用消息 id（parent_id）。纯逻辑，不含网络调用
——被引用消息正文由 T4.1 client 调 ``im.message.get`` 拉取后注入。

引用 + @ 才触发（只引用不 @ 不触发，D39）。
"""

import json
import re
from dataclasses import dataclass

_AT_TAG_RE = re.compile(r"<at[^>]*>.*?</at>", re.DOTALL)
_AT_USER_RE = re.compile(r'<at\s+user_id="([^"]+)"')


@dataclass
class MessageContext:
    app_id: str
    chat_id: str
    message_id: str
    sender_open_id: str
    text: str
    at_bot: bool
    parent_id: str | None
    chat_type: str


def extract_plain_text(content: str, message_type: str) -> str:
    """从 message.content（JSON 字符串）提取纯文本，去 ``<at>`` 标签。"""
    try:
        obj = json.loads(content)
    except (json.JSONDecodeError, TypeError):
        return ""
    if message_type == "text":
        text = obj.get("text", "")
    else:
        # 富消息取 text 或 title 作降级纯文本
        text = obj.get("text", "") or obj.get("title", {})
        if isinstance(text, dict):
            text = text.get("text", "")
    return _AT_TAG_RE.sub("", text).strip()


def parse_message_event(
    data: dict, bot_open_id: str | None = None
) -> MessageContext | None:
    """解析事件 JSON → MessageContext。缺关键字段返回 None。"""
    header = data.get("header", {})
    event = data.get("event", {})
    message = event.get("message", {})
    sender = event.get("sender", {})

    app_id = header.get("app_id", "")
    chat_id = message.get("chat_id", "")
    message_id = message.get("message_id", "")
    if not app_id or not chat_id or not message_id:
        return None

    sender_open_id = (sender.get("sender_id") or {}).get("open_id", "")
    content = message.get("content", "")
    mtype = message.get("message_type", "")
    text = extract_plain_text(content, mtype)

    # @机器人：mentions 数组 + content 内 <at user_id> 双来源
    mentioned_ids = {
        m.get("id", {}).get("open_id")
        for m in message.get("mentions", [])
        if m.get("id", {}).get("open_id")
    }
    mentioned_ids |= set(_AT_USER_RE.findall(content))
    at_bot = bool(bot_open_id and bot_open_id in mentioned_ids)

    parent_id = message.get("parent_id") or message.get("root_id")
    return MessageContext(
        app_id=app_id,
        chat_id=chat_id,
        message_id=message_id,
        sender_open_id=sender_open_id,
        text=text,
        at_bot=at_bot,
        parent_id=parent_id,
        chat_type=message.get("chat_type", ""),
    )
