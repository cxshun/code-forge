"""健康检查接口。

``GET /healthz`` 挂在根路径（不在 ``/api/admin`` 下），供 Docker Compose 健康探测
与运维监控使用。对齐 task T0.1 验收。
"""

from fastapi import APIRouter

from app import __version__
from app.config import settings

router = APIRouter(tags=["health"])


@router.get("/healthz")
async def healthz() -> dict:
    return {"status": "ok", "version": __version__, "env": settings.app_env}
