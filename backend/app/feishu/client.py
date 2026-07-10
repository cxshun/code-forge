"""飞书 API 客户端封装（design §3.1 / D7）。

基于 lark_oapi，用 ``asyncio.to_thread`` 包装同步 lark API。tenant_access_token 由
lark 自动获取 + 缓存刷新。封装 IM API：查 chat / 判断机器人在群 / 发文本 / 发卡片 /
更新卡片（流式进度）/ 拉消息正文（引用解析用）。
"""

import asyncio
import json

import lark_oapi as lark
from lark_oapi.api.im.v1 import (
    CreateMessageRequest,
    CreateMessageRequestBody,
    GetChatRequest,
    GetMessageRequest,
    PatchMessageRequest,
    PatchMessageRequestBody,
)


class FeishuAPIError(Exception):
    """飞书 API 调用失败。"""


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
