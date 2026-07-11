"""Tracer — contextvars 零侵入 span 上下文管理器（design §7.3 / D28）。

核心机制：
- ``ContextVar`` 维护当前 span，asyncio task 自动继承（子代理天然嵌套）
- ``span()`` 上下文管理器自动 enter/exit，Agent 内核不显式传 trace_id
- 异常路径自动标 error status
- exit 时将 span 数据推入 SpanBuffer（best-effort，不阻断）

使用方式：
    span_ctx = init_trace(ws_id, feishu_chat_id, session_id, run_id)  # Run 启动
    async with span("run"):  # 根 span
        async with span("llm", model="claude-sonnet"):  # LLM 调用
            ...
        async with span("tool", tool_name="Bash"):  # 工具调用
            ...
"""

import logging
import uuid
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from app.db.models.span import SpanStatus, SpanType

log = logging.getLogger("observability.tracer")

_current_span: ContextVar["SpanContext | None"] = ContextVar("current_span", default=None)


@dataclass
class SpanContext:
    """span 运行态：在 contextvars 中传递，exit 时转为 Span 入库。

    字段对齐 ``Span`` ORM 模型（§7.2），tenant 四元组从 ``init_trace`` 注入。
    """

    span_id: str
    trace_id: str
    parent_span_id: str | None
    span_type: str
    span_order: int
    started_at: datetime

    # tenant 四元组
    workspace_id: int
    feishu_chat_id: int
    session_id: int
    run_id: int

    # LLM 元信息
    provider: str | None = None
    model: str | None = None
    stop_reason: str | None = None

    # token 计数
    input_tokens: int | None = None
    output_tokens: int | None = None
    cache_read_input_tokens: int | None = None
    cache_creation_input_tokens: int | None = None

    # 工具
    tool_name: str | None = None
    tool_input_summary: str | None = None
    tool_output_summary: str | None = None
    tool_acquired_lock: bool | None = None
    tool_path_rejected: bool | None = None

    # 成本
    cost_usd: float | None = None

    # 错误
    error_type: str | None = None
    error_message: str | None = None

    # payload
    payload_ref: str | None = None
    payload_size_bytes: int | None = None
    payload_truncated: bool = False

    # 扩展
    attributes: dict[str, Any] | None = None

    # 运行态
    status: str = SpanStatus.running.value
    ended_at: datetime | None = None
    duration_ms: int | None = None

    def set_error(self, exc: Exception) -> None:
        self.status = SpanStatus.error.value
        self.error_type = type(exc).__name__
        self.error_message = str(exc)[:2000]

    def finish(self) -> None:
        if self.status == SpanStatus.running.value:
            self.status = SpanStatus.ok.value
        self.ended_at = datetime.now(UTC)
        self.duration_ms = int(
            (self.ended_at - self.started_at).total_seconds() * 1000
        )

    def to_dict(self) -> dict:
        """转为 dict 供 SpanBuffer 批量 UPSERT。"""
        d = {
            "span_id": self.span_id,
            "trace_id": self.trace_id,
            "parent_span_id": self.parent_span_id,
            "span_order": self.span_order,
            "span_type": self.span_type,
            "status": self.status,
            "workspace_id": self.workspace_id,
            "feishu_chat_id": self.feishu_chat_id,
            "session_id": self.session_id,
            "run_id": self.run_id,
            "provider": self.provider,
            "model": self.model,
            "stop_reason": self.stop_reason,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cache_read_input_tokens": self.cache_read_input_tokens,
            "cache_creation_input_tokens": self.cache_creation_input_tokens,
            "tool_name": self.tool_name,
            "tool_input_summary": self.tool_input_summary,
            "tool_output_summary": self.tool_output_summary,
            "tool_acquired_lock": self.tool_acquired_lock,
            "tool_path_rejected": self.tool_path_rejected,
            "cost_usd": self.cost_usd,
            "error_type": self.error_type,
            "error_message": self.error_message,
            "payload_ref": self.payload_ref,
            "payload_size_bytes": self.payload_size_bytes,
            "payload_truncated": self.payload_truncated,
            "attributes": self.attributes,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "duration_ms": self.duration_ms,
        }
        return d


@dataclass
class _TraceContext:
    """Run 级 trace 上下文：tenant 四元组 + trace_id + span 计数器。

    在 ``init_trace`` 时设置，贯穿整个 Run 生命周期，所有子 span 继承。
    """

    workspace_id: int
    feishu_chat_id: int
    session_id: int
    run_id: int
    trace_id: str
    root_span_id: str
    _span_counter: int = 0

    def next_order(self) -> int:
        self._span_counter += 1
        return self._span_counter


_current_trace: ContextVar[_TraceContext | None] = ContextVar(
    "current_trace", default=None
)


def init_trace(
    ws_id: int, feishu_chat_id: int, session_id: int, run_id: int
) -> _TraceContext:
    """Run 启动时初始化 trace 上下文，返回供 ``span()`` 使用。

    在 _execute_run 开头调用，设置 contextvars 后所有子 span 自动继承。
    """
    trace_id = uuid.uuid4().hex
    root_span_id = uuid.uuid4().hex
    ctx = _TraceContext(
        workspace_id=ws_id,
        feishu_chat_id=feishu_chat_id,
        session_id=session_id,
        run_id=run_id,
        trace_id=trace_id,
        root_span_id=root_span_id,
    )
    _current_trace.set(ctx)
    return ctx


def clear_trace() -> None:
    """Run 结束时清理 trace 上下文。"""
    _current_trace.set(None)
    _current_span.set(None)


def current_span() -> SpanContext | None:
    return _current_span.get()


def _make_span_context(span_type: str, **fields) -> SpanContext:
    """创建 SpanContext，从 _current_trace 继承 tenant 字段。"""
    trace = _current_trace.get()
    if trace is None:
        raise RuntimeError("init_trace() not called before span()")

    parent = _current_span.get()
    span_id = uuid.uuid4().hex
    parent_span_id = parent.span_id if parent else None
    order = trace.next_order()

    ctx = SpanContext(
        span_id=span_id,
        trace_id=trace.trace_id,
        parent_span_id=parent_span_id,
        span_type=span_type,
        span_order=order,
        started_at=datetime.now(UTC),
        workspace_id=trace.workspace_id,
        feishu_chat_id=trace.feishu_chat_id,
        session_id=trace.session_id,
        run_id=trace.run_id,
    )
    for k, v in fields.items():
        if v is not None:
            setattr(ctx, k, v)
    return ctx


# ---- public API ----

# 延迟导入避免循环依赖
_buffer = None


def _get_buffer():
    global _buffer
    if _buffer is None:
        from app.observability.buffer import span_buffer

        _buffer = span_buffer
    return _buffer


class _SpanCM:
    """span() 上下文管理器的异步实现。

    用对象而非 generator 以支持 async with + 手动控制 span 生命周期
    （streaming token 聚合需要中途更新 span 字段）。
    """

    __slots__ = ("_ctx", "_entered", "_token_span")

    def __init__(self, ctx: SpanContext) -> None:
        self._ctx = ctx
        self._token_span = None
        self._entered = False

    async def __aenter__(self) -> SpanContext:
        self._entered = True
        self._token_span = _current_span.set(self._ctx)
        return self._ctx

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        if not self._entered:
            return
        if exc_val is not None:
            self._ctx.set_error(exc_val)
        self._ctx.finish()
        _current_span.reset(self._token_span)
        # best-effort 推入 buffer（§7.4：tracer 异常 swallow）
        try:
            buf = _get_buffer()
            buf.put(self._ctx.to_dict())
        except Exception:
            log.warning("span buffer put failed", exc_info=True)

    @property
    def ctx(self) -> SpanContext:
        return self._ctx


class _NoopSpanCM:
    """无 trace 上下文时的 no-op span（D28 best-effort）。

    ctx 属性预置 None，使 Agent Loop 可无差别设值 / 读取（如 calc_cost_usd 读 token）。
    """

    __slots__ = ("ctx",)

    def __init__(self) -> None:
        from types import SimpleNamespace

        self.ctx = SimpleNamespace(
            provider=None,
            model=None,
            stop_reason=None,
            input_tokens=None,
            output_tokens=None,
            cache_read_input_tokens=None,
            cache_creation_input_tokens=None,
            cost_usd=None,
        )

    async def __aenter__(self):
        return self.ctx

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        pass


def span(span_type: str, **fields) -> _SpanCM | _NoopSpanCM:
    """创建一个 span 上下文管理器。

    用法::

        async with span("llm", model="claude-sonnet-4") as sctx:
            # ... 执行 LLM 调用 ...
            sctx.input_tokens = 123
            sctx.stop_reason = "end_turn"

    根 span (type="run") 使用 root_span_id 作为 span_id。

    无 trace 上下文时返回 no-op（D28：observability 不阻断 Agent Loop）。
    """
    trace = _current_trace.get()
    if trace is None:
        return _NoopSpanCM()

    if span_type == SpanType.run:
        ctx = _make_span_context(span_type, **fields)
        ctx.span_id = trace.root_span_id
    else:
        ctx = _make_span_context(span_type, **fields)
    return _SpanCM(ctx)


__all__ = [
    "SpanContext",
    "clear_trace",
    "current_span",
    "init_trace",
    "span",
]
