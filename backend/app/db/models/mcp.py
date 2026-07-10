"""MCP 模型（全局广场顶层实体，D11 / D37）。

MCP 是外部工具服务（stdio 子进程 / http 远程）。config 为 JSON：
- stdio：{command, args, env}
- http：{endpoint, headers}
secret 字段（token / header 凭证）加密存储。read_only=True 时豁免抢 WS 锁（D37）。
"""

import enum

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin
from app.db.models.skill import Visibility


class MCPType(enum.StrEnum):
    stdio = "stdio"
    http = "http"


class MCP(Base, TimestampMixin):
    __tablename__ = "mcps"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    type: Mapped[str] = mapped_column(String(32), nullable=False)
    # 配置（含可能的加密 secret 字段），结构因 type 而异
    config: Mapped[dict] = mapped_column(JSONB, nullable=False)
    owner_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    visibility: Mapped[str] = mapped_column(
        String(32), default=Visibility.private.value, nullable=False
    )
    # D37：已知无副作用的 MCP 可标 read_only 豁免 WS 锁
    read_only: Mapped[bool] = mapped_column(default=False, nullable=False)
