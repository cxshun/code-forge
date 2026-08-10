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


def _extract_card_text(card: dict) -> str:
    """从卡片 JSON 提取纯文本（标题 + elements 文本）。

    兼容两种卡片格式：
    - 新版（cards.py 生成）：``header.title`` 为 dict，``elements`` 为扁平 list[dict]
    - 旧版（飞书原生推送）：``title`` 为纯字符串，``elements`` 为嵌套 list[list[dict]]
    """
    parts: list[str] = []
    # 标题：新版在 header.title.content，旧版在顶层 title 字符串
    header = card.get("header") or {}
    title = header.get("title")
    if isinstance(title, dict):
        t = title.get("content") or title.get("text") or ""
        if t:
            parts.append(t)
    elif isinstance(title, str) and title:
        parts.append(title)
    # 卡片顶层也可能直接有 title（旧版）
    top_title = card.get("title")
    if isinstance(top_title, str) and top_title:
        parts.append(top_title)
    for el in card.get("elements") or []:
        # 旧版 elements 是 list[list[dict]]，每个内层 list 是一行
        if isinstance(el, list):
            for sub in el:
                parts.extend(_extract_element_text(sub))
        else:
            parts.extend(_extract_element_text(el))
    return "\n".join(p for p in parts if p)


def _extract_element_text(el: dict) -> list[str]:
    """从单个卡片元素提取文本。"""
    tag = el.get("tag", "")
    if tag in ("markdown", "plain_text"):
        return [el.get("content", "")]
    if tag == "text":
        return [el.get("text", "")]
    if tag == "note":
        out: list[str] = []
        for sub in el.get("elements") or []:
            out.extend(_extract_element_text(sub))
        return out
    if tag == "table":
        out = []
        for row in el.get("rows") or []:
            out.append(" | ".join(str(v) for v in row.values()))
        return out
    if tag == "action":
        out = []
        for btn in el.get("actions") or []:
            txt = btn.get("text") or {}
            if isinstance(txt, dict):
                c = txt.get("content", "") or txt.get("text", "")
                if c:
                    out.append(c)
        return out
    if tag in ("divider", "hr", "lark_md"):
        return []
    # 未知元素：尝试 content 或 text.content
    c = el.get("content", "")
    if c:
        return [c]
    txt = el.get("text") or {}
    if isinstance(txt, dict) and txt.get("content"):
        return [txt["content"]]
    return []


def extract_plain_text(content: str, message_type: str) -> str:
    """从 message.content（JSON 字符串）提取纯文本，去 ``<at>`` 标签。"""
    try:
        obj = json.loads(content)
    except (json.JSONDecodeError, TypeError):
        return ""
    if message_type == "text":
        text = obj.get("text", "")
    elif message_type == "interactive":
        return _AT_TAG_RE.sub("", _extract_card_text(obj)).strip()
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

    sender_open_id = (sender.get("sender_id") or {}).get("open_id", "") or ""
    content = message.get("content", "") or ""
    mtype = message.get("message_type", "") or ""
    text = extract_plain_text(content, mtype)

    # @机器人：mentions 数组 + content 内 <at user_id> 双来源
    mentioned_ids = {
        m.get("id", {}).get("open_id")
        for m in message.get("mentions", [])
        if (m.get("id") or {}).get("open_id")
    }
    mentioned_ids |= set(_AT_USER_RE.findall(content))
    # bot_open_id 未知时放宽：任何 @ 都触发（MVP 验证用；接入层应获取 bot open_id 精确匹配）
    at_bot = bot_open_id in mentioned_ids if bot_open_id else bool(mentioned_ids)

    parent_id = message.get("parent_id") or message.get("root_id")
    return MessageContext(
        app_id=app_id,
        chat_id=chat_id,
        message_id=message_id,
        sender_open_id=sender_open_id,
        text=text,
        at_bot=at_bot,
        parent_id=parent_id,
        chat_type=message.get("chat_type", "") or "",
    )
