"""工作空间域模型（WS / FeishuChat / GitRepo / 挂载关联）。

对齐 §2.1 实体关系、§2.3 目录结构、D6（多 repo HTTPS clone）、D8（FeishuChat 独占
WS）、D11（N:N 挂载）、D34（WS 级上下文配置）。

- Workspace：物理隔离单元。context_config 为 WS 级上下文管理策略（D34），JSON 字段。
- FeishuChat：唯一键 (app_id, chat_id)，独占 WS（1 FeishuChat : 1 WS）。
- GitRepo：clone 状态机，token 加密存储，随 WS CASCADE。
- WorkspaceSkill / WorkspaceMcp：N:N 挂载关联表。
"""

import enum

from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class Workspace(Base, TimestampMixin):
    __tablename__ = "workspaces"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    owner_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    # 默认 cwd repo（第一个挂载 repo 根，D24 / F3.9.5）；删 repo 时置空。
    # 不设 DB 外键：git_repos.workspace_id 已反向引用 workspaces，再加 FK 会形成循环，
    # 引用完整性由应用层（WS 管理服务）保证。
    cwd_repo_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # WS 级上下文管理策略（D34）：enabled / trigger1 / trigger2 / clear_keep /
    # compact_recent / summary_provider / summary_model / compact_instructions / exclude_tools
    context_config: Mapped[dict | None] = mapped_column(JSONB, nullable=True)


class FeishuChat(Base, TimestampMixin):
    __tablename__ = "feishu_chats"
    __table_args__ = (
        # FeishuChat 唯一键 = (app_id, chat_id)，独占 WS（D8）
        UniqueConstraint("app_id", "chat_id", name="uq_feishu_chats_app_chat"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    workspace_id: Mapped[int] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    app_id: Mapped[str] = mapped_column(String(64), nullable=False)
    # 飞书原始群 ID（oc_xxx），与 app_id 组成 FeishuChat 唯一键
    chat_id: Mapped[str] = mapped_column(String(64), nullable=False)
    chat_name: Mapped[str | None] = mapped_column(String(256), nullable=True)


class CloneStatus(enum.StrEnum):
    pending = "pending"
    cloning = "cloning"
    ready = "ready"
    failed = "failed"


class GitRepo(Base, TimestampMixin):
    __tablename__ = "git_repos"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    workspace_id: Mapped[int] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    url: Mapped[str] = mapped_column(String(1024), nullable=False)
    # 可选私有仓库 token（加密存储），不入日志不回显（D6 / NF4.2.4）
    token_enc: Mapped[str | None] = mapped_column(String(512), nullable=True)
    clone_status: Mapped[str] = mapped_column(
        String(32), default=CloneStatus.pending.value, nullable=False, index=True
    )
    # clone 落地相对路径（repos/{repo_id}/）
    local_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    last_error: Mapped[str | None] = mapped_column(String(1024), nullable=True)


class WorkspaceSkill(Base, TimestampMixin):
    """WS ↔ Skill N:N 挂载关联（D11）。复合主键。"""

    __tablename__ = "workspace_skill"

    workspace_id: Mapped[int] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), primary_key=True
    )
    skill_id: Mapped[int] = mapped_column(
        ForeignKey("skills.id", ondelete="CASCADE"), primary_key=True
    )


class WorkspaceMcp(Base, TimestampMixin):
    """WS ↔ MCP N:N 挂载关联（D11）。复合主键。"""

    __tablename__ = "workspace_mcp"

    workspace_id: Mapped[int] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), primary_key=True
    )
    mcp_id: Mapped[int] = mapped_column(
        ForeignKey("mcps.id", ondelete="CASCADE"), primary_key=True
    )
