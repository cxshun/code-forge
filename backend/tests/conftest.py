"""全局 pytest 配置（测试库隔离）。

⚠️ 关键：必须在任何 ``app.*`` 包导入之前把 ``APP_ENV`` 置为 ``test``。

- ``app.config.settings`` 在导入时实例化（lru_cache 单例）。test 环境下
  ``database_url_effective`` 会切到独立的测试库（PostgreSQL: codeforge_test，
  SQLite: codeforge_test.db），使测试清表绝不碰 dev/prod 数据。
- ``app.db.testing.reset_all`` 另有 ``assert is_test`` 硬护栏，双保险。

session 级 fixture 负责首次创建测试库 + schema。
"""

import os

# 必须在任何 `app.*` 导入之前执行（conftest 由 pytest 在收集测试模块前先导入）
os.environ.setdefault("APP_ENV", "test")

import pytest
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine

import app.db.models  # noqa: F401  注册所有模型到 Base.metadata
from app.config import settings
from app.db.base import Base


@pytest.fixture(scope="session", autouse=True)
async def _ensure_test_database():
    """session 级：确保测试库 + 表结构存在（幂等）。"""
    url = make_url(settings.database_url_effective)

    if settings.is_postgresql:
        db_name = url.database

        # 连 maintenance postgres 库创建测试库（CREATE DATABASE 不能在事务中执行）
        # 注意：直接传 URL 对象，不能用 str(url)——SQLAlchemy 2.0 起 str(url) 会把密码
        # 渲染成 `***`，导致连接认证失败。
        maint = create_async_engine(
            url.set(database="postgres"), isolation_level="AUTOCOMMIT"
        )
        try:
            async with maint.connect() as conn:
                exists = await conn.scalar(
                    text("SELECT 1 FROM pg_database WHERE datname = :n"),
                    {"n": db_name},
                )
                if not exists:
                    await conn.execute(text(f'CREATE DATABASE "{db_name}"'))
        finally:
            await maint.dispose()

    # 建表（幂等；checkfirst）— PostgreSQL / SQLite 通用
    engine = create_async_engine(url)
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    finally:
        await engine.dispose()

    yield
