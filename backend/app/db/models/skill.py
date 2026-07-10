"""Skill 模型（全局广场顶层实体，D11 / D15）。

一个 Skill = 一个目录（SKILL.md + resources + scripts），落全局广场
``/skills/{skill_id}/``。默认 owner 私有，可设全员可见。frontmatter 的 name 全局
唯一、description 必填（注入 system prompt）。引用计数运行时由 workspace_skill 关联
表 COUNT 得出（被引用禁删，F3.5.5）。
"""

import enum

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class Visibility(enum.StrEnum):
    private = "private"
    public = "public"


class Skill(Base, TimestampMixin):
    __tablename__ = "skills"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(
        String(128), unique=True, nullable=False, index=True
    )
    description: Mapped[str] = mapped_column(String(512), nullable=False)
    owner_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    visibility: Mapped[str] = mapped_column(
        String(32), default=Visibility.private.value, nullable=False
    )
    # 落地目录：/skills/{skill_id}/
    dir_path: Mapped[str] = mapped_column(String(512), nullable=False)
