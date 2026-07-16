"""创建初始管理员账号（幂等，开发/生产共用）。

行为：
- 用户名：INIT_ADMIN_USERNAME（默认 admin）
- 密码：
  - 显式设置 INIT_ADMIN_PASSWORD → 用它（本地/生产通用）
  - 未设且为 dev/test → 自动用固定默认 admin/admin（仅供本地，打印警告）
  - 未设且为 prod → 打印告警并跳过，不阻断启动
- 同名用户已存在 → 跳过（绝不覆盖密码）

用法：
  # 本地开发（dev 默认 admin/admin，无需任何环境变量）
  uv run python scripts/init_admin.py

  # 生产（容器 entrypoint 自动调用；在 .env.prod 配 INIT_ADMIN_PASSWORD 即创建）
  INIT_ADMIN_USERNAME=admin INIT_ADMIN_PASSWORD=xxx python scripts/init_admin.py
"""

import asyncio
import os
import sys

from sqlalchemy import select

from app.config import settings
from app.core.security import hash_password
from app.db.models import User, UserStatus
from app.db.session import async_session_factory

# 仅 dev/test 环境兜底用；prod 永不使用此值。
DEV_DEFAULT_PASSWORD = "admin"


async def main() -> None:
    username = os.environ.get("INIT_ADMIN_USERNAME", "admin")
    explicit_pw = os.environ.get("INIT_ADMIN_PASSWORD")

    if explicit_pw:
        password, source = explicit_pw, "env"
    elif settings.is_prod:
        print(
            "[init_admin] INIT_ADMIN_PASSWORD 未配置（prod），跳过管理员初始化。\n"
            "            请在 .env.prod 设置后重启，或手动创建：\n"
            "            docker compose -f deploy/docker-compose.prod.yml "
            "exec -e INIT_ADMIN_PASSWORD=xxx backend python scripts/init_admin.py"
        )
        return
    else:
        # dev/test：固定默认，方便本地登录
        password, source = DEV_DEFAULT_PASSWORD, "dev_default"

    async with async_session_factory() as s:
        existing = await s.scalar(select(User).where(User.username == username))
        if existing is not None:
            print(f"[init_admin] user '{username}' 已存在 (id={existing.id})，跳过")
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
        print(f"[init_admin] 创建管理员: id={user.id} username={username}")
        if source == "dev_default":
            print(
                "[init_admin] ⚠️ 使用 dev 默认密码 'admin'，仅供本地开发。"
                "生产环境请通过 INIT_ADMIN_PASSWORD 注入强随机密码。",
                file=sys.stderr,
            )


if __name__ == "__main__":
    asyncio.run(main())
