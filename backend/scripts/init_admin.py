"""创建初始管理员账号（幂等，开发/生产共用）。

应用启动时 lifespan 已自动调用 ``ensure_admin_user()``，此脚本供手动补建用
（如 PostgreSQL 迁移后未启动应用、或需指定不同用户名密码时）。

用法：
  # 本地开发（dev 默认 admin/admin，无需任何环境变量）
  uv run python scripts/init_admin.py

  # 生产（在 .env.prod 配 INIT_ADMIN_PASSWORD 即创建）
  INIT_ADMIN_USERNAME=admin INIT_ADMIN_PASSWORD=xxx uv run python scripts/init_admin.py
"""

import asyncio

from app.db.init import ensure_admin_user


async def main() -> None:
    await ensure_admin_user()


if __name__ == "__main__":
    asyncio.run(main())
