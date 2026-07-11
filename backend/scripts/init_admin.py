"""首次部署创建管理员账号。

用法（容器内）：
  docker compose -f deploy/docker-compose.prod.yml exec backend python scripts/init_admin.py

或在 entrypoint 后手动运行。环境变量提供凭证：
  INIT_ADMIN_USERNAME  (default: admin)
  INIT_ADMIN_PASSWORD  (required)
"""

import asyncio
import os
import sys

from sqlalchemy import select

from app.core.security import hash_password
from app.db.models import User, UserStatus
from app.db.session import async_session_factory


async def main() -> None:
    username = os.environ.get("INIT_ADMIN_USERNAME", "admin")
    password = os.environ.get("INIT_ADMIN_PASSWORD")
    if not password:
        sys.exit("INIT_ADMIN_PASSWORD env var required")

    async with async_session_factory() as s:
        existing = await s.scalar(select(User).where(User.username == username))
        if existing is not None:
            print(f"user '{username}' already exists (id={existing.id}), skipping")
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
        print(f"created admin: id={user.id} username={username}")


if __name__ == "__main__":
    asyncio.run(main())
