"""接入层消息处理（design §6.1）。

收到飞书消息后：D38 去重 → (app_id, chat_id) 路由 → @机器人识别（仅群聊）→
组装 Run 依赖（Provider / 工具注册表 / cwd / 引用块 D39）→ ``RunQueue.submit`` 入队。

卡片生命周期由 Run 回调拥有（接入层不再预发 Thinking 卡片）：
- ``on_queue`` → 排队卡片；``on_start`` → 思考中卡片
- ``on_text`` → 仅累积文本，不更新卡片（避免流式分片导致表格 / 格式解析异常）
- ``on_done`` → 一次性渲染完整正文（含 GFM 表格等完整结构） / 失败展示中断 / 取消 / 错误
"""

import logging

from app.agent.context import ContextManager
from app.agent.context_config import ContextConfig
from app.agent.queue import RunCancelled, run_queue
from app.agent.runtime import (
    build_registry,
    fetch_quote_text,
    make_provider,
    make_summary_provider,
    resolve_cwd,
)
from app.config import settings
from app.core.redis_client import redis as redis_client
from app.db.models import Workspace
from app.db.session import async_session_factory
from app.feishu.cards import (
    build_progress_card,
    build_queue_card,
)
from app.feishu.client import FeishuClient
from app.feishu.dedup import acquire
from app.feishu.quote import parse_message_event
from app.feishu.router import auto_bind_p2p_chat, resolve_feishu_chat

log = logging.getLogger("feishu.handler")

_CARD_TEXT_CAP = 6000  # 卡片单次展示文本上限（防超长回复触发飞书限制）


class FeishuRunCallbacks:
    """把 Run 事件桥接到飞书卡片（非流式：完成后一次性渲染）。"""

    def __init__(self, client: FeishuClient, chat_id: str, footer: str | None) -> None:
        self._client = client
        self._chat_id = chat_id
        self._footer = footer
        self._card_id: str | None = None
        self._full: list[str] = []

    async def _send(self, card: dict) -> None:
        try:
            self._card_id = await self._client.send_card(self._chat_id, card)
        except Exception:
            log.exception("send card failed")

    async def _update(self, text: str) -> None:
        if self._card_id is None:
            return
        try:
            await self._client.update_card(
                self._card_id, build_progress_card(text[:_CARD_TEXT_CAP], footer=self._footer)
            )
        except Exception:
            log.exception("update card failed")

    async def on_queue(self, position: int) -> None:
        await self._send(build_queue_card(position))

    async def on_start(self) -> None:
        await self._send(build_progress_card("⏳ 思考中…", footer=self._footer))

    async def on_text(self, delta: str) -> None:
        self._full.append(delta)

    async def on_tool_call(self, _tc: dict) -> None:
        # 工具调用意味着当前文本是中间过程（非最终回复），清空累积
        self._full.clear()

    async def on_done(self, exc: Exception | None) -> None:
        if exc is not None:
            if isinstance(exc, RunCancelled):
                msg = "⛔ 已取消"
            elif isinstance(exc, InterruptedError):
                msg = "⛔ 已中断"
            else:
                msg = f"❌ 执行失败：{exc}"[:200]
            if self._card_id is not None:
                await self._update(msg)
            else:
                await self._send(build_progress_card(msg, footer=self._footer))
            return
        # 成功：一次性渲染完整正文（含表格等完整结构）
        full = "".join(self._full)
        if full:
            await self._update(full)
        elif self._card_id is None:
            await self._send(build_progress_card("✅ 完成", footer=self._footer))


async def handle_message(
    event_dict: dict, app_id: str, app_secret: str, bot_open_id: str | None = None
) -> None:
    ctx = parse_message_event(event_dict, bot_open_id)
    if ctx is None:
        return

    # 触发条件（D-DC.1）：
    #   - group：必须 @ 机器人（MVP D21 / F3.1.3 不变）
    #   - p2p：直接触发（P2 direct-chat，无需 @）
    #   - 其他 chat_type：忽略
    if ctx.chat_type == "group":
        if not ctx.at_bot:
            log.info(
                "ignore group without @: %s", ctx.message_id
            )
            return
    elif ctx.chat_type != "p2p":
        log.info(
            "ignore unknown chat_type=%s: %s", ctx.chat_type, ctx.message_id
        )
        return

    # D38 去重（进 Run 队列前）
    if not await acquire(redis_client, ctx.message_id):
        log.info("duplicate dropped: %s", ctx.message_id)
        return

    # 路由 (app_id, chat_id) → FeishuChat；p2p 未绑定时自动建专属 WS（D-DC.2 / D-DC.7）
    client = FeishuClient(app_id, app_secret)
    sender_name: str | None = None
    async with async_session_factory() as db:
        chat = await resolve_feishu_chat(db, ctx.app_id, ctx.chat_id)
        if chat is None and ctx.chat_type == "p2p":
            # 优先用 chat_members API（仅需 IM 权限），fallback 到 contact API
            try:
                sender_name = await client.get_chat_member_name(ctx.chat_id)
            except Exception:
                log.warning(
                    "get_chat_member_name failed: %s", ctx.chat_id, exc_info=True
                )
            if not sender_name and ctx.sender_open_id:
                try:
                    sender_name = await client.get_user_name(ctx.sender_open_id)
                except Exception:
                    log.warning(
                        "get_user_name failed: %s",
                        ctx.sender_open_id,
                        exc_info=True,
                    )
            chat = await auto_bind_p2p_chat(
                db,
                ctx.app_id,
                ctx.chat_id,
                ctx.sender_open_id,
                settings.p2p_workspace_owner_id,
                sender_name=sender_name,
            )
        if chat is None:
            log.info("unbound chat, ignore: app=%s chat=%s", ctx.app_id, ctx.chat_id)
            return
        ws_id = chat.workspace_id
        feishu_chat_id = chat.id
        ws = await db.get(Workspace, ws_id)
        provider = make_provider(ws.model_config)
        registry, skill_descriptions, mcp_cleanup = await build_registry(db, ws_id, provider)
        cwd = await resolve_cwd(db, ws)
        ctx_cfg = ContextConfig.from_ws(ws.context_config)

    footer_label = sender_name or (
        ctx.sender_open_id[-8:] if ctx.sender_open_id else None
    )
    footer = f"sender {footer_label}" if footer_label else None

    # 收到确认：在用户消息上打「OnIt」表情（处理完成后移除）
    reaction_id = None
    try:
        reaction_id = await client.add_reaction(ctx.message_id, "OnIt")
    except Exception:
        log.warning("add_reaction failed: %s", ctx.message_id, exc_info=True)

    # 未配置任何 LLM Provider → 发错误卡，不入队
    has_llm = bool(settings.anthropic_api_key) or (
        settings.openai_compatible_api_key
        and settings.openai_compatible_base_url
        and settings.openai_compatible_model
    )
    if not has_llm:
        log.warning("未配置任何 LLM Provider，跳过 Run: %s", ctx.message_id)
        try:
            await client.send_card(
                ctx.chat_id,
                build_progress_card(
                    "❌ 未配置 LLM Provider（ANTHROPIC_API_KEY 或 OPENAI_COMPATIBLE_*）",
                    footer=footer,
                ),
            )
        except Exception:
            log.exception("error card failed")
        if reaction_id:
            try:
                await client.delete_reaction(ctx.message_id, reaction_id)
            except Exception:
                log.warning("delete_reaction failed: %s", ctx.message_id, exc_info=True)
        return

    # D39 引用回复注入（parent_id → 拉被引用正文前置为引用块）
    quote = await fetch_quote_text(client, ctx.parent_id)
    user_message = f"{quote}\n{ctx.text}" if quote else ctx.text

    callbacks = FeishuRunCallbacks(client, ctx.chat_id, footer)

    # 上下文管理（D34）：按 WS context_config 构造四道防线编排器
    cm = (
        ContextManager(provider, ctx_cfg, make_summary_provider(ctx_cfg))
        if ctx_cfg.enabled
        else None
    )

    # MCP 连接在 Run 结束后关闭（成功 / 失败 / 中断 / 取消均执行）
    orig_on_done = callbacks.on_done

    async def _on_done_with_cleanup(exc: Exception | None) -> None:
        try:
            if mcp_cleanup is not None:
                await mcp_cleanup()
        except Exception:
            log.exception("mcp cleanup failed")
        await orig_on_done(exc)

    async def _on_done_with_reaction(exc: Exception | None) -> None:
        await _on_done_with_cleanup(exc)
        if reaction_id:
            try:
                await client.delete_reaction(ctx.message_id, reaction_id)
            except Exception:
                log.warning("delete_reaction failed: %s", ctx.message_id, exc_info=True)

    run_id = await run_queue.submit(
        ws_id=ws_id,
        feishu_chat_id=feishu_chat_id,
        user_message=user_message,
        provider=provider,
        registry=registry,
        cwd=cwd,
        skill_descriptions=skill_descriptions,
        trigger_message_id=ctx.message_id,
        context_manager=cm,
        on_text=callbacks.on_text,
        on_tool_call=callbacks.on_tool_call,
        on_queue=callbacks.on_queue,
        on_start=callbacks.on_start,
        on_done=_on_done_with_reaction,
    )
    log.info(
        "submitted run %d: app=%s chat=%s ws=%s text=%r quote=%s",
        run_id, ctx.app_id, ctx.chat_id, ws_id, ctx.text[:80], bool(quote),
    )
