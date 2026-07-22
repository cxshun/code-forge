"""飞书 API 客户端封装（design §3.1 / D7）。

基于 lark_oapi，用 ``asyncio.to_thread`` 包装同步 lark API。tenant_access_token 由
lark 自动获取 + 缓存刷新。封装 IM API：查 chat / 判断机器人在群 / 发文本 / 发卡片 /
更新卡片（流式进度）/ 拉消息正文（引用解析用）。
"""

import asyncio
import json
import logging

import lark_oapi as lark
from lark_oapi.api.contact.v3 import GetUserRequest
from lark_oapi.api.im.v1 import (
    CreateMessageReactionRequest,
    CreateMessageReactionRequestBody,
    CreateMessageRequest,
    CreateMessageRequestBody,
    DeleteMessageReactionRequest,
    GetChatMembersRequest,
    GetChatRequest,
    GetMessageRequest,
    PatchMessageRequest,
    PatchMessageRequestBody,
)
from lark_oapi.api.im.v1.model.emoji import Emoji


class FeishuAPIError(Exception):
    """飞书 API 调用失败。"""


log = logging.getLogger("feishu.client")


def _check(resp) -> None:
    if not resp.success():
        raise FeishuAPIError(f"code={resp.code} msg={resp.msg}")


class FeishuClient:
    def __init__(self, app_id: str, app_secret: str) -> None:
        self._app_id = app_id
        self._client = (
            lark.Client.builder().app_id(app_id).app_secret(app_secret).build()
        )

    async def get_chat(self, chat_id: str):
        """查 chat 信息。bot 无权限 / chat 不存在返回 None。"""
        req = GetChatRequest.builder().chat_id(chat_id).build()
        resp = await asyncio.to_thread(self._client.im.v1.chat.get, req)
        if not resp.success():
            # 230002: chat not found / 无权限
            if resp.code in (230002, 99991663):
                return None
            raise FeishuAPIError(f"get_chat code={resp.code} msg={resp.msg}")
        return resp.data

    async def is_bot_in_chat(self, chat_id: str) -> bool:
        """bot 能访问 chat（在群 / 有权限）即视为在群（MVP）。"""
        return await self.get_chat(chat_id) is not None

    async def get_user_name(self, open_id: str) -> str | None:
        """查用户展示名（contact v3）；无权限 / 用户不存在返回 None。

        需飞书应用授予 ``contact:contact.base:readonly``（或同级 contact 读权限）。
        """
        req = (
            GetUserRequest.builder()
            .user_id(open_id)
            .user_id_type("open_id")
            .build()
        )
        resp = await asyncio.to_thread(self._client.contact.v3.user.get, req)
        if not resp.success():
            log.warning(
                "get_user_name failed: open_id=%s code=%s msg=%s",
                open_id, resp.code, resp.msg,
            )
            return None
        user = getattr(resp.data, "user", None)
        name = getattr(user, "name", None) if user is not None else None
        return name or None

    async def get_chat_member_name(self, chat_id: str) -> str | None:
        """查 chat 对方展示名（im.v1.chat_members）；仅 IM 权限，无需通讯录权限。

        p2p chat 的成员列表只含对方用户（不含 bot），取第一个成员的 name。
        """
        req = (
            GetChatMembersRequest.builder()
            .chat_id(chat_id)
            .member_id_type("open_id")
            .page_size(20)
            .build()
        )
        resp = await asyncio.to_thread(self._client.im.v1.chat_members.get, req)
        if not resp.success():
            log.warning(
                "get_chat_member_name failed: chat_id=%s code=%s msg=%s",
                chat_id, resp.code, resp.msg,
            )
            return None
        items = getattr(resp.data, "items", None) or []
        for m in items:
            name = getattr(m, "name", None)
            if name:
                return name
        return None

    async def send_text(self, chat_id: str, text: str) -> str:
        body = (
            CreateMessageRequestBody.builder()
            .receive_id(chat_id)
            .msg_type("text")
            .content(json.dumps({"text": text}))
            .build()
        )
        req = (
            CreateMessageRequest.builder()
            .receive_id_type("chat_id")
            .request_body(body)
            .build()
        )
        resp = await asyncio.to_thread(self._client.im.v1.message.create, req)
        _check(resp)
        return resp.data.message_id

    async def send_card(self, chat_id: str, card: dict) -> str:
        body = (
            CreateMessageRequestBody.builder()
            .receive_id(chat_id)
            .msg_type("interactive")
            .content(json.dumps(card))
            .build()
        )
        req = (
            CreateMessageRequest.builder()
            .receive_id_type("chat_id")
            .request_body(body)
            .build()
        )
        resp = await asyncio.to_thread(self._client.im.v1.message.create, req)
        _check(resp)
        return resp.data.message_id

    async def update_card(self, message_id: str, card: dict) -> None:
        body = PatchMessageRequestBody.builder().content(json.dumps(card)).build()
        req = (
            PatchMessageRequest.builder()
            .message_id(message_id)
            .request_body(body)
            .build()
        )
        resp = await asyncio.to_thread(self._client.im.v1.message.patch, req)
        _check(resp)

    async def get_message(self, message_id: str):
        """拉消息正文（引用回复解析用，D39）。失败返回 None。"""
        req = GetMessageRequest.builder().message_id(message_id).build()
        resp = await asyncio.to_thread(self._client.im.v1.message.get, req)
        if not resp.success():
            return None
        return resp.data

    async def add_reaction(self, message_id: str, emoji_type: str = "OnIt") -> str:
        """在消息上添加表情，返回 reaction_id。"""
        body = (
            CreateMessageReactionRequestBody.builder()
            .reaction_type(Emoji.builder().emoji_type(emoji_type).build())
            .build()
        )
        req = (
            CreateMessageReactionRequest.builder()
            .message_id(message_id)
            .request_body(body)
            .build()
        )
        resp = await asyncio.to_thread(
            self._client.im.v1.message_reaction.create, req
        )
        _check(resp)
        return resp.data.reaction_id

    async def delete_reaction(self, message_id: str, reaction_id: str) -> None:
        """移除消息上的表情。"""
        req = (
            DeleteMessageReactionRequest.builder()
            .message_id(message_id)
            .reaction_id(reaction_id)
            .build()
        )
        resp = await asyncio.to_thread(
            self._client.im.v1.message_reaction.delete, req
        )
        _check(resp)
