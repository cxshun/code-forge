"""全局 pytest 配置（测试库隔离）。

⚠️ 关键：必须在任何 ``app.*`` 包导入之前把 ``APP_ENV`` 置为 ``test``。

- ``app.config.settings`` 在导入时实例化（lru_cache 单例）。test 环境下
  ``pg_dsn_effective`` 会切到独立的 ``codeforge_test`` 库，使测试 TRUNCATE
  绝不碰 dev/prod 数据。
- ``app.db.testing.reset_all`` 另有 ``assert is_test`` 硬护栏，双保险。

session 级 fixture 负责首次创建 ``codeforge_test`` 库 + schema。
"""

import os

# 必须在任何 `app.*` 导入之前执行（conftest 由 pytest 在收集测试模块前先导入）
os.environ.setdefault("APP_ENV", "test")

import pytest  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlalchemy.engine import make_url  # noqa: E402
from sqlalchemy.ext.asyncio import create_async_engine  # noqa: E402

import app.db.models  # noqa: E402,F401  注册所有模型到 Base.metadata
from app.config import settings  # noqa: E402
from app.db.base import Base  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
async def _ensure_test_database():
    """session 级：确保 codeforge_test 库 + 表结构存在（幂等）。"""
    url = make_url(settings.pg_dsn_effective)  # test 环境已切到 codeforge_test
    db_name = url.database

    # 连 maintenance postgres 库创建测试库（CREATE DATABASE 不能在事务中执行）
    maint = create_async_engine(
        str(url.set(database="postgres")), isolation_level="AUTOCOMMIT"
    )
    try:
        async with maint.connect() as conn:
            exists = await conn.scalar(
                text("SELECT 1 FROM pg_database WHERE datname = :n"), {"n": db_name}
            )
            if not exists:
                await conn.execute(text(f'CREATE DATABASE "{db_name}"'))
    finally:
        await maint.dispose()

    # 建表（幂等；checkfirst）
    engine = create_async_engine(str(url))
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    finally:
        await engine.dispose()

    yield
