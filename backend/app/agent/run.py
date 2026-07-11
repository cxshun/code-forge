"""Session/Run 管理（1 Session : 1 Run，design D23）+ Run 编排（§6.5）。

一次用户消息触发：建 Session + Run（DB）→ 抢 WS 写锁（D20）→ 构建 system prompt
（D24）+ 工具注册表 → 跑 Agentic Loop → 落盘 session JSONL → 更新 Run 状态。

异常 / 中断 / 超时都释放锁（try/finally），Run 标 error。

两个阶段被抽出复用：
- ``_create_run``：建 Session + Run（queued），供直接调用与 RunQueue 入队共用
- ``_execute_run``：抢到锁后的运行阶段（running → completed/interrupted/error），
  接受外部 ``abort`` 事件以支持 T6.3 运行中中断；锁由调用方 try/finally 释放
"""

import asyncio
import json
import logging
from datetime import UTC, datetime
from pathlib import Path

from app.agent.lock import WsLock
from app.agent.loop import RunContext, run_loop
from app.agent.prompt import build_system_prompt
from app.config import settings
from app.core.redis_client import redis as redis_client
from app.db.models import Run, RunStatus, Session
from app.db.session import async_session_factory
from app.memory.loader import load_context_injections
from app.providers.base import Message, Provider
from app.tools.base import ToolContext
from app.tools.registry import ToolRegistry
from app.workspace.fs import workspace_root

log = logging.getLogger("agent.run")


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
            fh.write(
                json.dumps(
                    {"role": m.role, "content": m.content}, ensure_ascii=False
                )
                + "\n"
            )
    return f


async def _set_run_status(
    run_id: int, status: str, *, error: str | None = None, started: bool = False
) -> None:
    async with async_session_factory() as db:
        r = await db.get(Run, run_id)
        if r is None:
            return
        r.status = status
        if error is not None:
            r.error = error[:1000]
        if started:
            r.started_at = datetime.now(UTC)
        else:
            r.ended_at = datetime.now(UTC)
        await db.commit()


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
    on_text=None,
    on_tool_call=None,
) -> str:
    """抢到锁后的运行阶段：标 running → build prompt → run_loop → 落盘 → 标 completed。

    AGENT.md（WS + Repo 级）与 MEMORY.md 索引在此处由 ``load_context_injections``
    直接读文件注入 system prompt（D24 / §6.5，不走 Read 工具）。

    ``abort`` 被 set 时 Loop 在下一检查点抛 InterruptedError（T6.3），本函数将其标
    interrupted 并 re-raise；其余异常标 error 并 re-raise。锁的释放由调用方负责。
    """
    await _set_run_status(run_id, RunStatus.running.value, started=True)

    try:
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
        ctx = RunContext(
            system=system,
            messages=[Message(role="user", content=user_message)],
            tool_ctx=ToolContext(
                ws_id=ws_id,
                workspaces_root=settings.workspaces_root,
                cwd=cwd,
                feishu_chat_id=feishu_chat_id,
            ),
            run_id=run_id,
            abort=abort or asyncio.Event(),
        )

        final = await run_loop(
            provider, ctx, registry, on_text=on_text, on_tool_call=on_tool_call
        )

        save_session_jsonl(ws_id, feishu_chat_id, session_id, ctx.messages)
        await _set_run_status(run_id, RunStatus.completed.value)
        return final

    except InterruptedError as e:
        await _set_run_status(run_id, RunStatus.interrupted.value, error=str(e))
        raise
    except Exception as e:
        # 状态在此设定；日志由调用方（start_run / RunQueue）记录，避免双重日志
        await _set_run_status(run_id, RunStatus.error.value, error=str(e))
        raise


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
            on_text=on_text,
            on_tool_call=on_tool_call,
        )
    except Exception:
        log.exception("run %d failed", run_id)
        raise
    finally:
        await lock.release()


__all__ = ["_create_run", "_execute_run", "save_session_jsonl", "start_run"]
