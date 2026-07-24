"""异步任务承载（asyncio + DB 状态机，不引入 Celery）。

对齐 design §3.1 / api §1.7 / D36。单进程内用 ``asyncio.create_task`` 跑后台任务，
状态落 ``tasks`` 表，前端轮询 ``GET /tasks/{task_id}``。启动时 ``recover_orphans``
把遗留的 pending/running 任务标 failed（D36 启动恢复的一部分）。

提交方先在 DB 建 Task 记录（拿 task_id、status=pending），再调 ``task_runner.submit``：
```

    task = Task(task_type=..., owner_id=...)
    db.add(task); await db.commit()
    task_runner.submit(task.id, _do_work(...))
```
"""

import asyncio
import logging

from sqlalchemy import update

from app.db.models import Task, TaskStatus
from app.db.session import async_session_factory

log = logging.getLogger("tasks.runner")


class TaskRunner:
    def __init__(self) -> None:
        self._bg: dict[int, asyncio.Task] = {}

    async def _update(self, task_id: int, **fields: object) -> None:
        async with async_session_factory() as s:
            await s.execute(update(Task).where(Task.id == task_id).values(**fields))
            await s.commit()

    def submit(self, task_id: int, coro):
        """提交后台任务：跑 coro，更新 tasks 表状态机。"""

        async def _run() -> None:
            await self._update(task_id, status=TaskStatus.running.value)
            log.info("task %d: running", task_id)
            try:
                result = await coro
                await self._update(
                    task_id,
                    status=TaskStatus.done.value,
                    progress=1.0,
                    result=result,
                )
                log.info("task %d: done", task_id)
            except Exception as e:
                await self._update(
                    task_id, status=TaskStatus.failed.value, error=str(e)[:1000]
                )
                log.error("task %d: failed: %s", task_id, str(e)[:300])

        self._bg[task_id] = asyncio.create_task(_run())

    async def recover_orphans(self) -> int:
        """启动恢复：遗留的 pending/running 任务标 failed（D36）。返回清理数。"""
        async with async_session_factory() as s:
            result = await s.execute(
                update(Task)
                .where(
                    Task.status.in_(
                        [TaskStatus.pending.value, TaskStatus.running.value]
                    )
                )
                .values(
                    status=TaskStatus.failed.value, error="interrupted by restart"
                )
            )
            await s.commit()
            count = result.rowcount or 0
            if count:
                log.warning("recovered %d orphaned tasks (marked failed)", count)
            return count


task_runner = TaskRunner()
