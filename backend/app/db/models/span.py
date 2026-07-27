"""Span 模型（单表自引用，§7.2）。

1 Run = 1 trace（根 span），下挂 llm / tool / skill / subagent / interrupt / error span，
支持任意嵌套（子代理内可再嵌套）。每个 span 强制带四元外键
（workspace_id / feishu_chat_id / session_id / run_id），全部 ON DELETE CASCADE
（NF4.1 物理隔离）。字段对齐 OTel GenAI semantic conventions + anthropic usage。

span_id / trace_id 用 UUID hex（String(32)），parent_span_id 自引用。
"""

import enum
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class SpanType(enum.StrEnum):
    run = "run"
    llm = "llm"
    tool = "tool"
    skill = "skill"
    subagent = "subagent"
    interrupt = "interrupt"
    error = "error"
    context = "context"  # 上下文管理事件（D34：clearing / compaction）


class SpanStatus(enum.StrEnum):
    running = "running"
    ok = "ok"
    error = "error"
    interrupted = "interrupted"
    timeout = "timeout"


class Span(Base, TimestampMixin):
    __tablename__ = "spans"

    # UUID hex（32 字符）
    span_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    trace_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    # 自引用：父 span；根 span 为 NULL
    # 不设 FK 约束 — async CM 导致子 span 先于父 span 入库，FK 会持续冲突
    parent_span_id: Mapped[str | None] = mapped_column(
        String(32), nullable=True, index=True
    )
    span_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    span_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    status: Mapped[str] = mapped_column(
        String(32), default=SpanStatus.running.value, nullable=False
    )

    # 四元租户外键（NF4.1 / §7.2 全 CASCADE）
    workspace_id: Mapped[int] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    feishu_chat_id: Mapped[int] = mapped_column(
        ForeignKey("feishu_chats.id", ondelete="CASCADE"), nullable=False, index=True
    )
    session_id: Mapped[int] = mapped_column(
        ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    run_id: Mapped[int] = mapped_column(
        ForeignKey("runs.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # LLM 调用元信息
    provider: Mapped[str | None] = mapped_column(String(64), nullable=True)
    model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    stop_reason: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # token 计数（对齐 anthropic usage）
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cache_read_input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cache_creation_input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # 工具调用摘要（全文落 payload 文件）
    tool_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    tool_input_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    tool_output_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    tool_acquired_lock: Mapped[bool | None] = mapped_column(nullable=True)
    tool_path_rejected: Mapped[bool | None] = mapped_column(nullable=True)

    # 成本（llm span 必填）
    cost_usd: Mapped[float | None] = mapped_column(Numeric(12, 6), nullable=True)

    # 错误
    error_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # payload 文件引用与截断标记（D26 / NF4.6.4）
    payload_ref: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    payload_size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    payload_truncated: Mapped[bool] = mapped_column(default=False, nullable=False)

    # 扩展属性（OTel gen_ai.* 预留）
    attributes: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # 时间与耗时
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
