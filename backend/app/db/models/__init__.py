"""ORM 模型聚合。

导入即注册到 ``Base.metadata``，供 Alembic autogenerate 与多租户 listener 使用。
"""

from app.db.models.feishu_app import FeishuApp
from app.db.models.mcp import MCP
from app.db.models.session_run import Run, RunStatus, Session
from app.db.models.skill import Skill, Visibility
from app.db.models.span import Span, SpanStatus, SpanType
from app.db.models.task import Task, TaskStatus
from app.db.models.user import User, UserRole, UserStatus
from app.db.models.workspace import (
    CloneStatus,
    FeishuChat,
    GitRepo,
    Workspace,
    WorkspaceMcp,
    WorkspaceSkill,
)

__all__ = [
    "MCP",
    "CloneStatus",
    "FeishuApp",
    "FeishuChat",
    "GitRepo",
    "Run",
    "RunStatus",
    "Session",
    "Skill",
    "Span",
    "SpanStatus",
    "SpanType",
    "Task",
    "TaskStatus",
    "User",
    "UserRole",
    "UserStatus",
    "Visibility",
    "Workspace",
    "WorkspaceMcp",
    "WorkspaceSkill",
]
