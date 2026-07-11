"""测试用 DB 清理 helper。

全表 TRUNCATE（CASCADE + RESTART IDENTITY），供测试 fixture 调用。放 app 包内以便
``from app.db.testing import reset_all`` 可靠导入。
"""

from sqlalchemy import text

from app.db.session import async_session_factory

TRUNCATE_ALL = (
    "TRUNCATE TABLE users, workspaces, feishu_chats, git_repos, skills, mcps, "
    "workspace_skill, workspace_mcp, sessions, runs, spans, tasks, feishu_apps, "
    "alert_rules "
    "RESTART IDENTITY CASCADE"
)


async def reset_all() -> None:
    async with async_session_factory() as s:
        await s.execute(text(TRUNCATE_ALL))
        await s.commit()
