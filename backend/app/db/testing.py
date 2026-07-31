"""测试用 DB 清理 helper。

全表清空（CASCADE + RESTART IDENTITY），供测试 fixture 调用。放 app 包内以便
``from app.db.testing import reset_all`` 可靠导入。

- PostgreSQL：``TRUNCATE TABLE ... RESTART IDENTITY CASCADE``
- SQLite：``DELETE FROM`` 各表 + ``DELETE FROM sqlite_sequence`` 重置自增

⚠️ 安全护栏：``reset_all`` 仅允许在 ``app_env=test`` 执行。test 环境下 ``config.py``
会把 DSN 切到独立测试库，dev/prod 数据绝不会被清。
"""

from sqlalchemy import text

from app.config import settings
from app.db.session import async_session_factory

_PG_TRUNCATE = (
    "TRUNCATE TABLE users, workspaces, feishu_chats, git_repos, skills, mcps, "
    "workspace_skill, workspace_mcp, sessions, session_summaries, runs, spans, "
    "tasks, feishu_apps, alert_rules "
    "RESTART IDENTITY CASCADE"
)

# SQLite 不支持 TRUNCATE，用 DELETE FROM 各表 + sqlite_sequence 重置自增
# 顺序：子表先删（FK 依赖），父表后删
_SQLITE_TABLES = [
    "spans",
    "tasks",
    "session_summaries",
    "runs",
    "sessions",
    "workspace_mcp",
    "workspace_skill",
    "feishu_chats",
    "feishu_apps",
    "alert_rules",
    "git_repos",
    "skills",
    "mcps",
    "workspaces",
    "users",
]


async def reset_all() -> None:
    # 硬护栏：防止误在 dev/prod 库清表（历史事故：测试连到 dev 库 TRUNCATE 了真实数据）
    assert settings.is_test, (
        "reset_all() 仅允许在 app_env=test 执行，当前环境 "
        f"{settings.app_env!r} 会清掉真实数据，已拒绝。"
    )
    async with async_session_factory() as s:
        if settings.is_postgresql:
            await s.execute(text(_PG_TRUNCATE))
        else:
            for table in _SQLITE_TABLES:
                await s.execute(text(f'DELETE FROM "{table}"'))
            # sqlite_sequence 仅在使用 AUTOINCREMENT 时存在
            has_seq = await s.scalar(
                text("SELECT name FROM sqlite_master "
                     "WHERE type='table' AND name='sqlite_sequence'")
            )
            if has_seq is not None:
                await s.execute(text("DELETE FROM sqlite_sequence"))
        await s.commit()
