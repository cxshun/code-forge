"""结构化日志（jsonl）。

基于 structlog，每行输出一个 JSON 对象，对齐 design §3.1「结构化日志 jsonl」。
默认字段：``timestamp / level / event / request_id``（request_id 由请求中间件注入
contextvars，详见 ``app.main``）。第三方库的标准 logging 也被桥接为 JSON 输出。
"""

import logging
import sys

import structlog

from app.config import settings


def configure_logging() -> None:
    """配置全局结构化日志。应在应用启动时调用一次。"""
    timestamper = structlog.processors.TimeStamper(fmt="iso", utc=True)
    level = logging.DEBUG if settings.debug else logging.INFO

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_log_level,
            timestamper,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.dict_tracebacks,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=True,
    )

    # 桥接标准 logging（uvicorn / sqlalchemy 等第三方库日志也走 JSON）
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        structlog.stdlib.ProcessorFormatter(
            processor=structlog.processors.JSONRenderer(),
            foreign_pre_chain=[
                structlog.stdlib.add_log_level,
                timestamper,
            ],
        )
    )
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level)


def get_logger(name: str | None = None):
    """获取一个结构化 logger。"""
    return structlog.get_logger(name)
