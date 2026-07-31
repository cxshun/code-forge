"""数据库初始化（首次启动自动创建管理员账号）。

- dev/test：未设 INIT_ADMIN_PASSWORD 时用固定 admin/admin（仅供本地）
- prod：未设 INIT_ADMIN_PASSWORD 时跳过并告警
- 幂等：同名用户已存在则跳过，绝不覆盖密码
"""

import logging

from sqlalchemy import select

from app.config import settings
from app.core.security import hash_password
from app.db.models import User, UserStatus
from app.db.session import async_session_factory

log = logging.getLogger("db.init")

DEV_DEFAULT_PASSWORD = "admin"


async def ensure_admin_user() -> None:
    """首次启动时创建默认管理员（幂等）。"""
    username = settings.init_admin_username
    password = settings.init_admin_password

    if not password:
        if settings.is_prod:
            log.warning(
                "init_admin.skipped",
                reason="INIT_ADMIN_PASSWORD 未配置（prod），跳过管理员初始化",
            )
            return
        password = DEV_DEFAULT_PASSWORD

    async with async_session_factory() as s:
        existing = await s.scalar(select(User).where(User.username == username))
        if existing is not None:
            return

        user = User(
            username=username,
            password_hash=hash_password(password),
            role="admin",
            status=UserStatus.active.value,
        )
        s.add(user)
        await s.commit()
        await s.refresh(user)
        log.info("init_admin.created", user_id=user.id, username=username)
        if password == DEV_DEFAULT_PASSWORD:
            log.warning(
                "init_admin.dev_default_password",
                hint="生产环境请通过 INIT_ADMIN_PASSWORD 注入强随机密码",
            )
