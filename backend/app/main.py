"""FastAPI 应用入口。

对齐 design §3.5：``lifespan`` 承载启动恢复（D36）与飞书多 App WebSocket 连接池起停
（D7），HTTP 中间件做请求日志。挂载 health / auth（``/api``）/ admin（``/api/admin``）
路由；全局异常处理器把错误统一为 ``{"error": {...}}``（api §1.3）。
"""

import asyncio
import time
import uuid
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import select
from starlette.exceptions import HTTPException as StarletteHTTPException

from app import __version__
from app.api.agent_md import router as agent_md_router
from app.api.auth import router as auth_router
from app.api.chats import router as chats_router
from app.api.feishu_apps import router as feishu_apps_router
from app.api.health import router as health_router
from app.api.insights import router as insights_router
from app.api.mcps import router as mcps_router
from app.api.memory import router as memory_router
from app.api.models import router as models_router
from app.api.monitoring import router as monitoring_router
from app.api.mounts import router as mounts_router
from app.api.repos import router as repos_router
from app.api.runs import router as runs_router
from app.api.skills import router as skills_router
from app.api.tasks import router as tasks_router
from app.api.traces import router as traces_router
from app.api.users import router as users_router
from app.api.workspaces import router as workspaces_router
from app.config import settings
from app.core.errors import CODE_BY_STATUS
from app.core.logging import configure_logging, get_logger
from app.core.security import decrypt_secret
from app.db.base import Base
from app.db.init import ensure_admin_user
from app.db.models import FeishuApp
from app.db.session import async_session_factory, engine
from app.feishu.handler import handle_message
from app.feishu.ws_pool import ws_pool
from app.observability.buffer import span_buffer
from app.observability.monitor import monitor_loop
from app.observability.ttl import ttl_loop
from app.tasks.runner import task_runner

# 模块导入即配置日志，确保任何入口（含测试）拿到结构化 logger。
configure_logging()
log = get_logger("app.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("app.starting", env=settings.app_env, version=__version__)
    # SQLite 模式自动建表（零依赖开箱即用）；PostgreSQL 需手动 alembic upgrade head
    if not settings.is_postgresql:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        log.info("db.tables_auto_created")
    # 首次启动自动创建管理员账号（幂等，dev 默认 admin/admin）
    await ensure_admin_user()
    # 启动恢复（D36）：遗留异步任务标 failed，避免幽灵任务
    orphans = await task_runner.recover_orphans()
    if orphans:
        log.info("app.recovered_orphan_tasks", count=orphans)
    # SpanBuffer 后台消费协程（§7.4 批量 UPSERT）
    span_buffer.start()
    # 告警监控循环（§7.7 / T10.3）
    monitor_task = asyncio.create_task(monitor_loop())
    # TTL 清理循环（§7.8 / T10.4）
    ttl_task = asyncio.create_task(ttl_loop())
    # TODO(NF4.4.4 / D36)：进一步清理孤儿 Run（标 interrupted）、强制释放残留 WS 锁。

    # 飞书多 App WebSocket 连接池（D7 / T4.2）：绑定 handler，启动恢复已注册 App。
    # TODO：connection_status 精确回写（lark ws.Client 无 on_connected 回调，当前仅 connecting）。
    ws_pool.start(handle_message)
    recovered = 0
    async with async_session_factory() as db:
        apps = (await db.scalars(select(FeishuApp))).all()
        for a in apps:
            try:
                ws_pool.add_app(a.app_id, decrypt_secret(a.app_secret_enc))
                a.connection_status = "connecting"
                recovered += 1
            except Exception:
                log.exception("feishu.ws.recover_failed", app_id=a.app_id)
        await db.commit()
    log.info("feishu.ws.recovered", count=recovered, total=len(apps))

    yield

    log.info("app.stopping")
    monitor_task.cancel()
    ttl_task.cancel()
    await span_buffer.stop()
    ws_pool.stop()


app = FastAPI(
    title="Code Forge",
    description="Cloud multi-tenant Coding Agent SaaS",
    version=__version__,
    lifespan=lifespan,
)

app.include_router(health_router)
app.include_router(auth_router, prefix="/api")
app.include_router(users_router, prefix="/api/admin")
app.include_router(tasks_router, prefix="/api/admin")
app.include_router(workspaces_router, prefix="/api/admin")
app.include_router(mcps_router, prefix="/api/admin")
app.include_router(feishu_apps_router, prefix="/api/admin")
app.include_router(agent_md_router, prefix="/api/admin")
app.include_router(repos_router, prefix="/api/admin")
app.include_router(runs_router, prefix="/api/admin")
app.include_router(memory_router, prefix="/api/admin")
app.include_router(chats_router, prefix="/api/admin")
app.include_router(mounts_router, prefix="/api/admin")
app.include_router(skills_router, prefix="/api/admin")
app.include_router(traces_router, prefix="/api/admin")
app.include_router(insights_router, prefix="/api/admin")
app.include_router(monitoring_router, prefix="/api/admin")
app.include_router(models_router, prefix="/api/admin")


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    if isinstance(exc.detail, dict) and isinstance(exc.detail.get("error"), dict):
        return JSONResponse(status_code=exc.status_code, content=exc.detail)
    code = CODE_BY_STATUS.get(exc.status_code, "error")
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": code, "message": str(exc.detail)}},
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "validation_failed",
                "message": "请求参数校验失败",
                "details": exc.errors(),
            }
        },
    )


@app.middleware("http")
async def request_logging(request: Request, call_next):
    """请求日志中间件：注入 request_id 并记录 method/path/status/耗时。"""
    request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(request_id=request_id)

    start = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        log.exception("request.error", method=request.method, path=request.url.path)
        raise

    elapsed_ms = (time.perf_counter() - start) * 1000
    response.headers["x-request-id"] = request_id
    log.info(
        "request",
        method=request.method,
        path=request.url.path,
        status=response.status_code,
        elapsed_ms=round(elapsed_ms, 2),
    )
    return response
