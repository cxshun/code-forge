"""异步任务轮询接口（api §1.7 / §10.4）。"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import TaskOut
from app.core.deps import require_user
from app.core.errors import api_error
from app.db.models import Task, User
from app.db.session import get_db

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get("/{task_id}")
async def get_task(
    task_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_user),
):
    t = await db.get(Task, task_id)
    if t is None or t.owner_id != user.id:
        raise api_error(404, "任务不存在")
    return TaskOut(
        task_id=t.id,
        type=t.task_type,
        status=t.status,
        progress=t.progress,
        result=t.result,
        error=t.error,
    )
