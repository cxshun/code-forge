"""多 App 飞书 WebSocket 连接池（design D7 / §6.1 / spec F3.1.1）。

每 App 一个 ``ThreadLoopClient``（lark ws.Client 子类，独立线程 + 独立事件 loop 跑
``start()``，阻塞监听，``auto_reconnect`` 断线重连）。事件回调把消息转发到业务
asyncio loop（独立线程），由 ``app.feishu.handler.handle_message`` 异步处理
（去重 / 路由 / @识别 / Thinking）。

App 增删时动态启停连接。lark ws.Client 无优雅 stop API，MVP 用 daemon 线程
（进程退出时关闭；App 删除先从池中移除，连接随进程或重启清理）。
"""

import asyncio
import threading
from collections.abc import Awaitable, Callable
from urllib.parse import parse_qs, urlparse

import lark_oapi as lark
import lark_oapi.ws.client as lark_ws_mod
import websockets
from lark_oapi.core.log import logger as lark_logger
from lark_oapi.event.dispatcher_handler import EventDispatcherHandlerBuilder
from lark_oapi.ws.exception import ClientException, ConnectionClosedException
from websockets.exceptions import InvalidHandshake

from app.core.logging import get_logger

log = get_logger("feishu.ws_pool")

# 业务消息处理回调：(event_dict, app_id, app_secret) -> Awaitable
MessageHandler = Callable[[dict, str, str], Awaitable[None]]


def _event_to_dict(data) -> dict:
    """P2ImMessageReceiveV1 对象 → 飞书事件 JSON 结构（供 quote.parse_message_event）。"""
    msg = data.event.message
    sender = data.event.sender
    mentions = []
    for m in msg.mentions or []:
        mid = getattr(m, "id", None)
        mentions.append({
            "id": {"open_id": getattr(mid, "open_id", "") or ""},
            "name": getattr(m, "name", "") or "",
        })
    return {
        "header": {"app_id": data.header.app_id},
        "event": {
            "sender": {
                "sender_id": {
                    "open_id": getattr(getattr(sender, "sender_id", None), "open_id", "") or ""
                }
            },
            "message": {
                "message_id": msg.message_id,
                "chat_id": msg.chat_id,
                "chat_type": getattr(msg, "chat_type", "") or "",
                "message_type": msg.message_type or "",
                "content": msg.content or "",
                "parent_id": getattr(msg, "parent_id", None),
                "root_id": getattr(msg, "root_id", None),
                "mentions": mentions,
            },
        },
    }


def _on_future_done(fut) -> None:
    """Future 异常回调：防止 handle_message 异常被静默吞噬。"""
    if fut.cancelled():
        return
    exc = fut.exception()
    if exc is not None:
        log.error("feishu.ws.handle_message_failed", error=str(exc), exc_info=exc)


class ThreadLoopClient(lark.ws.Client):
    """lark ws.Client 修复版：模块级全局 loop → 实例级 ``self._loop``。

    lark_oapi（1.7.1）``ws/client.py`` 在 import 时把 loop 缓存成模块级全局，
    ``start`` / ``_connect`` / ``_receive_message_loop`` 三处运行时读该全局 ——
    多 App 各自的连接线程覆盖同一全局会互相打崩（"This event loop is already
    running" / "Future attached to a different loop"，断线重连必踩）。本子类把
    这三处改为实例属性 ``self._loop``（WsPool 在连接线程里赋值为该线程独立
    loop），方法体复制自 1.7.1 ``ws/client.py``（仅 loop → self._loop；升级
    SDK 需比对这三处是否变化）。
    """

    _loop: asyncio.AbstractEventLoop  # 由 WsPool 在 start() 前绑定为连接线程的 loop

    def start(self) -> None:
        try:
            self._loop.run_until_complete(self._connect())
        except ClientException as e:
            lark_logger.error(self._fmt_log("connect failed, err: {}", e))
            raise e
        except Exception as e:
            lark_logger.error(self._fmt_log("connect failed, err: {}", e))
            self._loop.run_until_complete(self._disconnect())
            if self._auto_reconnect:
                self._loop.run_until_complete(self._reconnect())
            else:
                raise e

        self._loop.create_task(self._ping_loop())
        self._loop.run_until_complete(lark_ws_mod._select())

    async def _connect(self) -> None:
        await self._lock.acquire()
        if self._conn is not None:
            return
        try:
            conn_url = self._get_conn_url()
            u = urlparse(conn_url)
            q = parse_qs(u.query)
            conn_id = q[lark_ws_mod.DEVICE_ID][0]
            service_id = q[lark_ws_mod.SERVICE_ID][0]

            conn = await websockets.connect(conn_url, **lark_ws_mod._ws_connect_kwargs())
            self._conn = conn
            self._conn_url = conn_url
            self._conn_id = conn_id
            self._service_id = service_id

            lark_logger.info(self._fmt_log("connected to {}", conn_url))
            self._loop.create_task(self._receive_message_loop())
        except InvalidHandshake as e:
            lark_ws_mod._parse_ws_conn_exception(e)
        finally:
            self._lock.release()

    async def _receive_message_loop(self):
        try:
            while True:
                if self._conn is None:
                    raise ConnectionClosedException("connection is closed")
                msg = await self._conn.recv()
                self._loop.create_task(self._handle_message(msg))
        except Exception as e:
            lark_logger.error(self._fmt_log("receive message loop exit, err: {}", e))
            await self._disconnect()
            if self._auto_reconnect:
                await self._reconnect()
            else:
                raise e


class WsPool:
    def __init__(self) -> None:
        self._clients: dict[str, ThreadLoopClient] = {}
        self._threads: dict[str, threading.Thread] = {}
        self._business_loop: asyncio.AbstractEventLoop | None = None
        self._handler: MessageHandler | None = None

    def start(self, handler: MessageHandler) -> None:
        """注册消息处理回调，绑定调用方的事件 loop（FastAPI lifespan / 验证脚本主 loop）。

        handler 在该 loop 异步执行，与 DB engine / redis 同 loop，避免 asyncpg 跨 loop
        ``unknown protocol state`` 错误。每个 lark 连接在独立线程跑 ``start()``，事件
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
                    log.exception("feishu.ws.event_to_dict_failed", app_id=app_id)
                    return
                fut = asyncio.run_coroutine_threadsafe(
                    self._handler(event_dict, app_id, app_secret),
                    self._business_loop,
                )
                fut.add_done_callback(_on_future_done)

        builder = EventDispatcherHandlerBuilder("", "")
        handler = builder.register_p2_im_message_receive_v1(on_evt).build()
        client = ThreadLoopClient(
            app_id,
            app_secret,
            event_handler=handler,
            log_level=lark.LogLevel.INFO,
            auto_reconnect=True,
        )

        def _run() -> None:
            # 连接线程建独立 loop 并绑到 client._loop（见 ThreadLoopClient docstring：
            # 不再覆盖 lark 模块级全局 loop，多 App / 断线重连互不干扰）。
            new_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(new_loop)
            client._loop = new_loop
            try:
                client.start()
            except Exception:
                log.exception("feishu.ws.start_crashed", app_id=app_id)
            finally:
                new_loop.close()

        t = threading.Thread(target=_run, daemon=True, name=f"feishu-ws-{app_id}")
        t.start()
        self._clients[app_id] = client
        self._threads[app_id] = t
        log.info("feishu.ws.client_started", app_id=app_id)

    def remove_app(self, app_id: str) -> None:
        """从池中移除 App（连接随进程退出/重启清理，D36 启动恢复兜底）。"""
        self._clients.pop(app_id, None)
        self._threads.pop(app_id, None)
        log.info("feishu.ws.client_removed", app_id=app_id)

    @property
    def app_ids(self) -> list[str]:
        return list(self._clients)

    def stop(self) -> None:
        self._business_loop = None
        self._clients.clear()
        self._threads.clear()


ws_pool = WsPool()
