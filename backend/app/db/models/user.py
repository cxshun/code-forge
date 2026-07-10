"""User 模型（自建账号密码鉴权，D32）。

角色二分（admin / user），状态二分（active / disabled）。password_hash 存 argon2
密文，不存明文。枚举列用 VARCHAR + Python Enum 值（避免 PG ENUM 迁移痛点）。
"""

import enum

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class UserRole(enum.StrEnum):
    admin = "admin"
    user = "user"


class UserStatus(enum.StrEnum):
    active = "active"
    disabled = "disabled"


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, index=True
    )
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(
        String(32), default=UserRole.user.value, nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(32), default=UserStatus.active.value, nullable=False
    )
