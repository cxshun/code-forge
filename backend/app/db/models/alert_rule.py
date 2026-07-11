"""AlertRule 模型（design §7.7 / T10.3）。

每条规则属于一个 WS，定时扫描任务按规则类型计算指标值并对比阈值。
命中后经接入层推飞书卡片（best-effort）。
"""

import enum
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class RuleType(enum.StrEnum):
    error_rate = "error_rate"
    timeout_rate = "timeout_rate"
    p95_latency = "p95_latency"
    run_cost = "run_cost"
    ws_daily_cost = "ws_daily_cost"


class AlertRule(Base, TimestampMixin):
    __tablename__ = "alert_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    workspace_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(200))
    rule_type: Mapped[str] = mapped_column(String(64), index=True)
    threshold: Mapped[float] = mapped_column(Float)
    window_minutes: Mapped[int] = mapped_column(Integer, default=60)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    last_triggered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_result: Mapped[float | None] = mapped_column(Float, nullable=True)
