"""Span 查询多租户隔离（D31 / NF4.6.1）。

SQLAlchemy event listener 在 ORM 查询 ``Span`` 时自动注入 ``WHERE workspace_id = :ws_id``，
防止业务层忘记加过滤。``ws_id`` 由调用方通过 ``session.info["ws_id"]`` 传入（API 层从
路径参数取，不从客户端 body 取——D31 防越权）。

未设置 ``session.info["ws_id"]`` 时**不**注入过滤（管理后台全局视图预留，但 P0 阶段
所有 trace 查询都走 WS owner 校验路径，必然设置）。
"""

import logging

from sqlalchemy import event
from sqlalchemy.orm import Session, with_loader_criteria

from app.db.models.span import Span

log = logging.getLogger("observability.tenancy")


@event.listens_for(Session, "do_orm_execute")
def _inject_ws_filter(execute_state):
    """SELECT 查询 Span 时强制注入 workspace_id 过滤。"""
    if not execute_state.is_select:
        return
    ws_id = execute_state.session.info.get("ws_id")
    if ws_id is None:
        return
    execute_state.statement = execute_state.statement.options(
        with_loader_criteria(
            Span,
            Span.workspace_id == ws_id,
            include_aliases=True,
        )
    )
