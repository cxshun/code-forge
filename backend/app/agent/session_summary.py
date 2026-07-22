"""Session 摘要生成（P3 D-CE.1）。

Run 完成后异步生成 session 摘要落 ``session_summaries`` 表，供下次 ``load_chat_history``
跨 session 滑动窗口加载。失败仅 log warning，不阻塞用户回复也不写 DB（该 session 在
历史中表现为"无摘要"，被跳过）。
"""

import asyncio
import json
import logging
from pathlib import Path

from sqlalchemy import select

from app.agent.context_config import ContextConfig
from app.agent.runtime import make_summary_provider
from app.db.models import Run, RunStatus, Session, SessionSummary, Workspace
from app.db.session import async_session_factory
from app.providers.base import Message
from app.workspace.fs import workspace_root

log = logging.getLogger("agent.session_summary")

# 摘要输入的最大 message 数（防超长 Run 把摘要 provider 窗口撑爆）
_MAX_INPUT_MESSAGES = 80


async def generate_session_summary(
    session_id: int,
    ws_id: int,
    feishu_chat_id: int,
) -> None:
    """读 JSONL → summary_provider.chat → INSERT session_summaries。

    所有异常被吞掉 + log warning（设计 D-CE.1：失败不阻塞，仅 log）。
    """
    try:
        async with async_session_factory() as db:
            ws = await db.get(Workspace, ws_id)
            if ws is None:
                log.warning("summary: ws %s 不存在", ws_id)
                return
            cfg = ContextConfig.from_ws(ws.context_config)
            # 已有摘要 → 跳过（幂等保护，防重复生成）
            existing = await db.get(SessionSummary, session_id)
            if existing is not None:
                return
            # 读 JSONL 原文（过滤 tool_result，跨 session 摘要只关心对话主线）
            messages = _read_session_jsonl(ws_id, feishu_chat_id, session_id)
            if not messages:
                log.info("summary: session %d 无可摘要内容", session_id)
                return

        provider = make_summary_provider(cfg)
        summary_msgs = _build_summary_input(messages)
        resp, usage = await provider.chat(
            messages=summary_msgs, system=cfg.compact_instructions
        )
        summary_text = "\n\n".join(
            (m.content or "") for m in resp if m.content
        ).strip()
        if not summary_text:
            log.warning("summary: session %d 生成空摘要，跳过", session_id)
            return

        token_count = usage.input_tokens + usage.output_tokens
        async with async_session_factory() as db:
            db.add(
                SessionSummary(
                    session_id=session_id,
                    summary_text=summary_text,
                    token_count=token_count,
                    summary_model=provider.model,
                )
            )
            await db.commit()
        log.info(
            "summary: session %d 生成完成 (%d tokens, model=%s)",
            session_id, token_count, provider.model,
        )
    except Exception:
        log.warning("summary: session %d 生成失败", session_id, exc_info=True)


def _read_session_jsonl(
    ws_id: int, feishu_chat_id: int, session_id: int
) -> list[Message]:
    """读 session JSONL，过滤 tool_result 与空 content。"""
    f = (
        workspace_root(ws_id)
        / "chats"
        / str(feishu_chat_id)
        / "sessions"
        / f"{session_id}.jsonl"
    )
    if not f.exists():
        return []
    out: list[Message] = []
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
            out.append(Message(role=row["role"], content=content))
    return out


def _build_summary_input(messages: list[Message]) -> list[Message]:
    """构造摘要 provider 输入：最近 N 条（防超长），拼成单条 user 消息。"""
    recent = messages[-_MAX_INPUT_MESSAGES:] if len(messages) > _MAX_INPUT_MESSAGES else messages
    lines: list[str] = []
    for m in recent:
        lines.append(f"[{m.role}]\n{m.content}")
    text = "\n\n---\n\n".join(lines)
    return [Message(role="user", content=f"以下是本次会话的完整对话记录，请生成摘要：\n\n{text}")]


def submit_summary_task(
    session_id: int, ws_id: int, feishu_chat_id: int
) -> asyncio.Task:
    """fire-and-forget 提交摘要生成任务（不阻塞 Run 返回）。"""
    return asyncio.create_task(
        generate_session_summary(session_id, ws_id, feishu_chat_id)
    )


__all__ = ["generate_session_summary", "submit_summary_task"]
