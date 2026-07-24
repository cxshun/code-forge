"""Session/Run 管理（1 Session : 1 Run，design D23）+ Run 编排（§6.5）。

一次用户消息触发：建 Session + Run（DB）→ 抢 WS 写锁（D20）→ 构建 system prompt
（D24）+ 工具注册表 → 跑 Agentic Loop → 落盘 session JSONL → 更新 Run 状态。

异常 / 中断 / 超时都释放锁（try/finally），Run 标 error。

两个阶段被抽出复用：
- ``_create_run``：建 Session + Run（queued），供直接调用与 RunQueue 入队共用
- ``_execute_run``：抢到锁后的运行阶段（running → completed/interrupted/error），
  接受外部 ``abort`` 事件以支持 T6.3 运行中中断；锁由调用方 try/finally 释放

埋点（T9.4）：``_execute_run`` 开头 ``init_trace`` 初始化 trace 上下文，
整个 Run 包裹在 ``span("run")`` 根 span 中；结束前 ``flush_trace`` 确保 span 入库。
"""

import asyncio
import json
import logging
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select

from app.agent.context import ContextManager
from app.agent.context_config import ContextConfig
from app.agent.lock import WsLock
from app.agent.loop import RunContext, run_loop
from app.agent.prompt import build_system_prompt
from app.agent.session_summary import submit_summary_task
from app.config import settings
from app.core.redis_client import redis as redis_client
from app.db.models import Run, RunStatus, Session, SessionSummary, Workspace
from app.db.session import async_session_factory
from app.memory.loader import load_context_injections
from app.observability.buffer import span_buffer
from app.observability.tracer import clear_trace, init_trace, span
from app.providers.base import Message, Provider
from app.tools.base import ToolContext
from app.tools.registry import ToolRegistry
from app.workspace.fs import workspace_root

log = logging.getLogger("agent.run")

_SUMMARY_BUDGET_CAP = 16_000


def _sessions_dir(ws_id: int, feishu_chat_id: int) -> Path:
    return workspace_root(ws_id) / "chats" / str(feishu_chat_id) / "sessions"


def save_session_jsonl(
    ws_id: int, feishu_chat_id: int, session_id: int, messages: list[Message]
) -> Path:
    """落盘 session 历史（简化 messages 数组，供下次加载）。"""
    d = _sessions_dir(ws_id, feishu_chat_id)
    d.mkdir(parents=True, exist_ok=True)
    f = d / f"{session_id}.jsonl"
    with f.open("w", encoding="utf-8") as fh:
        for m in messages:
            row: dict = {"role": m.role, "content": m.content, "created_at": m.created_at}
            # assistant 携带模型思考（reasoning）与工具调用（tool_calls），
            # 供会话历史 / Trace 可观测展示（deepseek-v4-flash 等 thinking 模型）
            if m.role == "assistant":
                if m.reasoning:
                    row["reasoning"] = m.reasoning
                if m.tool_calls:
                    row["tool_calls"] = m.tool_calls
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    return f


async def load_chat_history(
    ws_id: int,
    feishu_chat_id: int,
    current_session_id: int,
    context_window: int = 0,
) -> list[Message]:
    """加载跨 session 上下文历史（P3 D-CE.1 滑动窗口）。

    返回 ``[摘要前缀（若有钱）] + [最近 1 session JSONL 原文]``，供 _execute_run
    与当前 user message 拼接。摘要前缀按 token 预算（``context_window *
    summary_budget_pct``）从 ``session_summaries`` 取最近 N 条。
    """
    try:
        summary_prefix = await _load_summary_prefix(
            ws_id, feishu_chat_id, current_session_id, context_window
        )
        jsonl_msgs = await _load_recent_session_jsonl(ws_id, feishu_chat_id, current_session_id)
        if summary_prefix:
            return [summary_prefix] + jsonl_msgs
        return jsonl_msgs
    except Exception:
        log.warning(
            "load_chat_history failed: ws=%s chat=%s", ws_id, feishu_chat_id,
            exc_info=True,
        )
        return []


async def _load_summary_prefix(
    ws_id: int, feishu_chat_id: int, current_session_id: int, context_window: int
) -> Message | None:
    """按 token 预算取最近 N 条 session_summaries，拼成单条 user 消息。"""
    async with async_session_factory() as db:
        ws = await db.get(Workspace, ws_id)
        if ws is None:
            return None
        cfg = ContextConfig.from_ws(ws.context_config)
        if not cfg.enabled or cfg.summary_budget_pct <= 0:
            return None
        budget = int(context_window * cfg.summary_budget_pct) if context_window > 0 else 0
        budget = min(budget, _SUMMARY_BUDGET_CAP)
        # 按 session.id DESC 取摘要（排除当前 session），累加 token_count ≤ budget
        stmt = (
            select(SessionSummary, Session.id.label("sid"))
            .join(Session, Session.id == SessionSummary.session_id)
            .where(
                Session.feishu_chat_id == feishu_chat_id,
                SessionSummary.session_id != current_session_id,
            )
            .order_by(Session.id.desc())
        )
        rows = (await db.execute(stmt)).all()
        if not rows:
            return None
        picked: list[str] = []
        total = 0
        for row in rows:
            ss = row[0]
            if budget > 0 and total + ss.token_count > budget:
                break
            picked.append(ss.summary_text)
            total += ss.token_count
        if not picked:
            return None
        # 时间顺序：旧 → 新（便于模型理解对话进展）
        picked.reverse()
        text = "\n\n---\n\n".join(picked)
        return Message(
            role="user",
            content=f"[历史会话摘要（{len(picked)} 个 session，{total} tokens）]\n\n{text}",
        )


async def _load_recent_session_jsonl(
    ws_id: int, feishu_chat_id: int, current_session_id: int
) -> list[Message]:
    """读最近 1 个已完成 session 的 JSONL 原文（过滤 tool_result）。"""
    async with async_session_factory() as db:
        stmt = (
            select(Session.id)
            .join(Run, Run.session_id == Session.id)
            .where(
                Session.feishu_chat_id == feishu_chat_id,
                Session.id != current_session_id,
                Run.status == RunStatus.completed.value,
            )
            .order_by(Session.id.desc())
            .limit(1)
        )
        prev_sid = await db.scalar(stmt)
    if prev_sid is None:
        return []
    f = _sessions_dir(ws_id, feishu_chat_id) / f"{prev_sid}.jsonl"
    if not f.exists():
        return []
    messages: list[Message] = []
    with f.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            if row.get("role") == "tool_result":
                continue
            content = row.get("content")
            if not content:
                continue
            msgs_kwargs: dict = {"role": row["role"], "content": content}
            messages.append(Message(**msgs_kwargs))
    limit = settings.chat_history_max_messages
    if len(messages) > limit:
        messages = messages[-limit:]
    return messages


async def _set_run_status(
    run_id: int, status: str, *, error: str | None = None, started: bool = False
) -> None:
    async with async_session_factory() as db:
        r = await db.get(Run, run_id)
        if r is None:
            return
        prev = r.status
        r.status = status
        if error is not None:
            r.error = error[:1000]
        if started:
            r.started_at = datetime.now(UTC)
        else:
            r.ended_at = datetime.now(UTC)
        await db.commit()
    if error:
        log.info("run %d: %s → %s (%s)", run_id, prev, status, error[:200])
    else:
        log.info("run %d: %s → %s", run_id, prev, status)


async def _create_run(
    ws_id: int, feishu_chat_id: int, trigger_message_id: str | None
) -> tuple[int, int]:
    """建 Session + Run（status=queued），返回 (session_id, run_id)。"""
    async with async_session_factory() as db:
        session = Session(feishu_chat_id=feishu_chat_id)
        db.add(session)
        await db.commit()
        await db.refresh(session)
        run = Run(
            session_id=session.id,
            workspace_id=ws_id,
            feishu_chat_id=feishu_chat_id,
            trigger_message_id=trigger_message_id,
            status=RunStatus.queued.value,
        )
        db.add(run)
        await db.commit()
        await db.refresh(run)
        return session.id, run.id


async def _execute_run(
    *,
    run_id: int,
    session_id: int,
    ws_id: int,
    feishu_chat_id: int,
    user_message: str,
    provider: Provider,
    registry: ToolRegistry,
    cwd: str = "",
    skill_descriptions: list[str] | None = None,
    abort: asyncio.Event | None = None,
    context_manager: ContextManager | None = None,
    on_text=None,
    on_tool_call=None,
) -> str:
    """抢到锁后的运行阶段：标 running → build prompt → run_loop → 落盘 → 标 completed。

    AGENT.md（WS + Repo 级）与 MEMORY.md 索引在此处由 ``load_context_injections``
    直接读文件注入 system prompt（D24 / §6.5，不走 Read 工具）。

    ``abort`` 被 set 时 Loop 在下一检查点抛 InterruptedError（T6.3），本函数将其标
    interrupted 并 re-raise；其余异常标 error 并 re-raise。锁的释放由调用方负责。

    埋点（T9.4）：``init_trace`` 设置 trace 上下文 → ``span("run")`` 根 span →
    ``flush_trace`` 确保 span 入库 → ``clear_trace`` 清理。
    """
    await _set_run_status(run_id, RunStatus.running.value, started=True)
    log.info("run %d started: ws=%s session=%d model=%s", run_id, ws_id, session_id, provider.model)

    trace_ctx = init_trace(ws_id, feishu_chat_id, session_id, run_id)
    try:
        async with span("run"):
            ws_agent_md, repo_agent_md, memory_index = load_context_injections(
                ws_id, feishu_chat_id, cwd
            )
            system = build_system_prompt(
                ws_agent_md,
                repo_agent_md,
                memory_index,
                skill_descriptions,
                feishu_chat_id=feishu_chat_id,
            )
            history = await load_chat_history(
                ws_id, feishu_chat_id, session_id, provider.context_window
            )
            ctx = RunContext(
                system=system,
                messages=history + [Message(role="user", content=user_message)],
                tool_ctx=ToolContext(
                    ws_id=ws_id,
                    workspaces_root=settings.workspaces_root,
                    cwd=cwd,
                    feishu_chat_id=feishu_chat_id,
                    system_prompt=system,
                ),
                run_id=run_id,
                abort=abort or asyncio.Event(),
            )

            final = await run_loop(
                provider, ctx, registry, on_text=on_text, on_tool_call=on_tool_call,
                context_manager=context_manager,
            )

            save_session_jsonl(ws_id, feishu_chat_id, session_id, ctx.messages)
            await _set_run_status(run_id, RunStatus.completed.value)
            log.info(
                "run %d completed: %d msgs, %d chars reply",
                run_id, len(ctx.messages), len(final or ""),
            )
            # P3 D-CE.1: 异步生成 session 摘要（不阻塞返回，失败仅 log）
            submit_summary_task(session_id, ws_id, feishu_chat_id)
            return final

    except InterruptedError as e:
        await _set_run_status(run_id, RunStatus.interrupted.value, error=str(e))
        raise
    except Exception as e:
        # 状态在此设定；日志由调用方（start_run / RunQueue）记录，避免双重日志
        await _set_run_status(run_id, RunStatus.error.value, error=str(e))
        raise
    finally:
        # 确保 trace 数据落库（§7.4：Run 结束前 flush 本 trace）
        try:
            await span_buffer.flush_trace(trace_ctx.trace_id)
        except Exception:
            log.warning("flush trace failed for run %d", run_id, exc_info=True)
        clear_trace()


async def start_run(
    *,
    ws_id: int,
    feishu_chat_id: int,
    user_message: str,
    provider: Provider,
    registry: ToolRegistry,
    cwd: str = "",
    skill_descriptions: list[str] | None = None,
    trigger_message_id: str | None = None,
    context_manager: ContextManager | None = None,
    on_text=None,
    on_tool_call=None,
    lock_timeout_s: float = 30,
) -> str:
    """同步入口（测试 / 直接调用）：建 Run → 抢锁 → 跑 → 落盘。返回最终回复。

    不经排队、不可外部中断；需要排队 / 中断能力请走 ``RunQueue.submit``。
    """
    session_id, run_id = await _create_run(ws_id, feishu_chat_id, trigger_message_id)

    # 抢 WS 写锁（D20）
    lock = WsLock(redis_client, ws_id)
    if not await lock.acquire(timeout_s=lock_timeout_s):
        log.warning("run %d: lock acquire timeout (ws=%s, %ss)", run_id, ws_id, lock_timeout_s)
        await _set_run_status(run_id, RunStatus.error.value, error="lock acquire timeout")
        raise RuntimeError("lock acquire timeout")

    try:
        return await _execute_run(
            run_id=run_id,
            session_id=session_id,
            ws_id=ws_id,
            feishu_chat_id=feishu_chat_id,
            user_message=user_message,
            provider=provider,
            registry=registry,
            cwd=cwd,
            skill_descriptions=skill_descriptions,
            context_manager=context_manager,
            on_text=on_text,
            on_tool_call=on_tool_call,
        )
    except Exception:
        log.exception("run %d failed", run_id)
        raise
    finally:
        await lock.release()


__all__ = ["_create_run", "_execute_run", "load_chat_history", "save_session_jsonl", "start_run"]
