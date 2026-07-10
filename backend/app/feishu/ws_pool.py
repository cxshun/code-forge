"""多 App 飞书 WebSocket 连接池（design D7 / §6.1 / spec F3.1.1）。

每 App 一个 ``lark_oapi.ws.Client``（独立线程跑 ``start()``，阻塞监听，``auto_reconnect``
断线重连）。事件回调把消息转发到业务 asyncio loop（独立线程），由
``app.feishu.handler.handle_message`` 异步处理（去重 / 路由 / @识别 / Thinking）。

App 增删时动态启停连接。lark ws.Client 无优雅 stop API，MVP 用 daemon 线程
（进程退出时关闭；App 删除先从池中移除，连接随进程或重启清理）。
"""

import asyncio
import logging
import threading
from collections.abc import Awaitable, Callable

import lark_oapi as lark
from lark_oapi.event.dispatcher_handler import EventDispatcherHandlerBuilder

log = logging.getLogger("feishu.ws_pool")

# 业务消息处理回调：(event_dict, app_id, app_secret) -> Awaitable
MessageHandler = Callable[[dict, str, str], Awaitable[None]]


def _event_to_dict(data) -> dict:
    """P2ImMessageReceiveV1 对象 → 飞书事件 JSON 结构（供 quote.parse_message_event）。"""
    msg = data.event.message
    sender = data.event.sender
    mentions = []
    for m in msg.mentions or []:
        mid = getattr(m, "id", None)
        mentions.append({"id": {"open_id": getattr(mid, "open_id", "")}, "name": getattr(m, "name", "")})
    return {
        "header": {"app_id": data.header.app_id},
        "event": {
            "sender": {
                "sender_id": {"open_id": getattr(getattr(sender, "sender_id", None), "open_id", "")}
            },
            "message": {
                "message_id": msg.message_id,
                "chat_id": msg.chat_id,
                "chat_type": getattr(msg, "chat_type", ""),
                "message_type": msg.message_type,
                "content": msg.content,
                "parent_id": getattr(msg, "parent_id", None),
                "root_id": getattr(msg, "root_id", None),
                "mentions": mentions,
            },
        },
    }


class WsPool:
    def __init__(self) -> None:
        self._clients: dict[str, lark.ws.Client] = {}
        self._threads: dict[str, threading.Thread] = {}
        self._business_loop: asyncio.AbstractEventLoop | None = None
        self._handler: MessageHandler | None = None

    def start(self, handler: MessageHandler) -> None:
        """注册消息处理回调，绑定调用方的事件 loop（FastAPI lifespan / 验证脚本主 loop）。

        handler 在该 loop 异步执行，与 DB engine / redis 同 loop，避免 asyncpg 跨 loop
        ``unknown protocol state`` 错误。lark ws.Client 在独立线程跑 ``start()``，事件
        回调通过 ``run_coroutine_threadsafe`` 转发到本 loop。
        """
        self._handler = handler
        self._business_loop = asyncio.get_running_loop()

    def add_app(self, app_id: str, app_secret: str) -> None:
        """为 App 启动一条 WS 连接（已存在则跳过）。"""
        if app_id in self._clients:
            return

        def on_evt(data) -> None:
            if self._handler and self._business_loop:
                try:
                    event_dict = _event_to_dict(data)
                except Exception:
                    log.exception("event_to_dict failed")
                    return
                asyncio.run_coroutine_threadsafe(
                    self._handler(event_dict, app_id, app_secret),
                    self._business_loop,
                )

        builder = EventDispatcherHandlerBuilder("", "")
        handler = builder.register_p2_im_message_receive_v1(on_evt).build()
        client = lark.ws.Client(
            app_id,
            app_secret,
            event_handler=handler,
            log_level=lark.LogLevel.INFO,
            auto_reconnect=True,
        )
        t = threading.Thread(target=client.start, daemon=True, name=f"feishu-ws-{app_id}")
        t.start()
        self._clients[app_id] = client
        self._threads[app_id] = t
        log.info("ws client started: app_id=%s", app_id)

    def remove_app(self, app_id: str) -> None:
        """从池中移除 App（连接随进程退出/重启清理，D36 启动恢复兜底）。"""
        self._clients.pop(app_id, None)
        self._threads.pop(app_id, None)
        log.info("ws client removed: app_id=%s", app_id)

    @property
    def app_ids(self) -> list[str]:
        return list(self._clients)

    def stop(self) -> None:
        self._business_loop = None
        self._clients.clear()
        self._threads.clear()


ws_pool = WsPool()
