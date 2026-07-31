"""Session / Run 模型（1 Session : 1 Run，D23 / §6.6 状态机）。

- Session：上下文单元，会话历史落 JSONL（chats/{feishu_chat_id}/sessions/{id}.jsonl）。
- Run：一次 Agent Loop 实例，1:1 绑定 Session。status 状态机见 §6.6：
  queued → running → completed / error / interrupted / timeout；
  queued → cancelled（排队中被用户取消，未启动 Agent Loop）。
- SessionSummary：Run 完成后异步生成的 session 摘要（P3 D-CE.1），1:1 附属 Session，
  用于跨 session 滑动窗口加载。摘要一旦生成不可变。
"""

import enum
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class RunStatus(enum.StrEnum):
    queued = "queued"
    running = "running"
    completed = "completed"
    error = "error"
    interrupted = "interrupted"
    timeout = "timeout"
    cancelled = "cancelled"


class Session(Base, TimestampMixin):
    __tablename__ = "sessions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    feishu_chat_id: Mapped[int] = mapped_column(
        ForeignKey("feishu_chats.id", ondelete="CASCADE"), nullable=False, index=True
    )


class Run(Base, TimestampMixin):
    __tablename__ = "runs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    # 1 Session : 1 Run（D23）—— session_id 唯一
    session_id: Mapped[int] = mapped_column(
        ForeignKey("sessions.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    workspace_id: Mapped[int] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    feishu_chat_id: Mapped[int] = mapped_column(
        ForeignKey("feishu_chats.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(
        String(32), default=RunStatus.queued.value, nullable=False, index=True
    )
    # 触发消息的飞书 message_id（兼作去重键，D38）
    trigger_message_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    error: Mapped[str | None] = mapped_column(String(1024), nullable=True)


class SessionSummary(Base):
    """Run 完成后异步生成的 session 摘要（P3 D-CE.1）。

    1:1 附属 Session（删 session 自动删摘要）；摘要一旦生成不可变。
    跨 session 滑动窗口加载时按 session.id DESC + token_count 累加预算取 N 条。
    """

    __tablename__ = "session_summaries"

    session_id: Mapped[int] = mapped_column(
        ForeignKey("sessions.id", ondelete="CASCADE"),
        primary_key=True,
    )
    summary_text: Mapped[str] = mapped_column(Text, nullable=False)
    # 摘要本身的 token 数（用于滑动窗口预算计算）
    token_count: Mapped[int] = mapped_column(Integer, nullable=False)
    # 生成摘要用的 model 名（observability / 排查用）
    summary_model: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
