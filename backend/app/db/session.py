"""异步数据库会话。

对齐 design §3.5 db/session.py：async engine + sessionmaker；``get_db`` 作为 FastAPI
依赖。连接串来自配置（dev/prod 各自）。

零外部依赖（D-ZD.1）：database_url 留空时使用 SQLite（aiosqlite），非空时使用
PostgreSQL（asyncpg）。SQLite 下启用 WAL 模式 + foreign_keys PRAGMA。
"""

import logging
from collections.abc import AsyncIterator

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings

log = logging.getLogger("db.session")

if settings.is_postgresql:
    engine = create_async_engine(
        settings.database_url_effective,
        pool_pre_ping=True,
        echo=False,
        pool_size=10,
        max_overflow=20,
    )
else:
    engine = create_async_engine(
        settings.database_url_effective,
        pool_pre_ping=True,
        echo=False,
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(engine.sync_engine, "connect")
    def _set_sqlite_pragma(dbapi_conn, _connection_record) -> None:
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()


async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

log.info(
    "storage=%s redis=%s",
    "postgresql" if settings.is_postgresql else "sqlite",
    "redis" if settings.is_redis else "memory",
)


async def get_db() -> AsyncIterator[AsyncSession]:
    """FastAPI 依赖：提供一个 session 作用域。"""
    async with async_session_factory() as session:
        yield session
