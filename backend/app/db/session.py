"""异步数据库会话。

对齐 design §3.5 db/session.py：async engine + sessionmaker；``get_db`` 作为 FastAPI
依赖。连接串来自配置（dev/prod 各自）。
"""

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings

engine = create_async_engine(
    settings.pg_dsn,
    pool_pre_ping=True,
    echo=False,
    pool_size=10,
    max_overflow=20,
)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncIterator[AsyncSession]:
    """FastAPI 依赖：提供一个 session 作用域。"""
    async with async_session_factory() as session:
        yield session
