"""测试用 DB 清理 helper。

全表 TRUNCATE（CASCADE + RESTART IDENTITY），供测试 fixture 调用。放 app 包内以便
``from app.db.testing import reset_all`` 可靠导入。

⚠️ 安全护栏：``reset_all`` 仅允许在 ``app_env=test`` 执行。test 环境下 ``session.py``
会把 DSN 切到 ``codeforge_test`` 独立库，dev/prod 数据绝不会被清。
"""

from sqlalchemy import text

from app.config import settings
from app.db.session import async_session_factory

TRUNCATE_ALL = (
    "TRUNCATE TABLE users, workspaces, feishu_chats, git_repos, skills, mcps, "
    "workspace_skill, workspace_mcp, sessions, runs, spans, tasks, feishu_apps, "
    "alert_rules "
    "RESTART IDENTITY CASCADE"
)


async def reset_all() -> None:
    # 硬护栏：防止误在 dev/prod 库清表（历史事故：测试连到 dev 库 TRUNCATE 了真实数据）
    assert settings.is_test, (
        "reset_all() 仅允许在 app_env=test 执行，当前环境 "
        f"{settings.app_env!r} 会清掉真实数据，已拒绝。"
    )
    async with async_session_factory() as s:
        await s.execute(text(TRUNCATE_ALL))
        await s.commit()
