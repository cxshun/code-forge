"""Agentic Loop 主体（design §6.5 / spec F3.3）。

核心循环：调用 LLM（Provider 流式）→ 解析 tool_use → 执行工具（只读并发 / 写串行，
F3.4.6）→ 反馈 tool_result → 直到最终回复（无 tool_use）。

兜底：最大 tool_use 轮数（F3.3.11，默认 50）、中止事件（T6.3 中断）。
Loop 不感知飞书——text_delta / tool 调用通过回调交给接入层推卡片，保持解耦。

埋点（§7.3 / T9.4）：每轮 LLM 调用 → llm span（含 stream token 聚合）；
每次工具调用 → tool span / skill span。trace context 由 ``run.py:_execute_run``
在 Run 启动时 ``init_trace`` 初始化。
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

from app.agent.context import ContextManager
from app.db.models.span import SpanType
from app.observability.cost import calc_cost_usd
from app.observability.tracer import span
from app.providers.base import Message, Provider, Usage
from app.tools.base import ToolContext
from app.tools.registry import ToolRegistry

log = logging.getLogger("agent.loop")

MAX_TOOL_ROUNDS = 50


@dataclass
class RunContext:
    """一次 Loop 运行的上下文。"""
    system: str = ""
    messages: list[Message] = field(default_factory=list)
    tool_ctx: ToolContext | None = None
    run_id: int | None = None
    abort: asyncio.Event = field(default_factory=asyncio.Event)


# ---- 事件回调 ----
OnText = Callable[[str], Awaitable[None] | None]
OnToolCall = Callable[[dict], Awaitable[None] | None]
OnUsage = Callable[[Usage], Awaitable[None] | None]


async def _maybe_call(cb, *args):
    if cb is None:
        return
    res = cb(*args)
    if asyncio.iscoroutine(res):
        await res


async def _stream_round(
    provider: Provider,
    ctx: RunContext,
    tools_defs,
    on_text: OnText | None,
    on_usage: OnUsage | None,
) -> tuple[Message, list[dict], Usage]:
    """流式调一轮 LLM，返回 (assistant_msg, tool_calls, usage)。

    埋点：包裹 ``span("llm")``，聚合 stream token（§7.3 streaming 聚合）。
    """
    assistant = Message(role="assistant", content="")
    tool_calls: list[dict] = []
    usage = Usage()

    async with span(SpanType.llm.value) as sctx:
        sctx.provider = provider.name
        sctx.model = provider.model
        async for evt in provider.stream(
            messages=ctx.messages,
            tools=tools_defs or None,
            system=ctx.system,
        ):
            if evt.type == "text" and evt.text:
                assistant.content = (assistant.content or "") + evt.text
                await _maybe_call(on_text, evt.text)
            elif evt.type == "tool_use_start" and evt.tool_name:
                tool_calls.append(
                    {
                        "id": "",
                        "name": evt.tool_name,
                        "input": evt.tool_input or "{}",
                    }
                )
            elif evt.type == "stop":
                if evt.input_tokens is not None:
                    usage.input_tokens = evt.input_tokens
                    sctx.input_tokens = evt.input_tokens
                if evt.output_tokens is not None:
                    usage.output_tokens = evt.output_tokens
                    sctx.output_tokens = evt.output_tokens
                if evt.cache_read_input_tokens is not None:
                    usage.cache_read_input_tokens = evt.cache_read_input_tokens
                    sctx.cache_read_input_tokens = evt.cache_read_input_tokens
                if evt.cache_creation_input_tokens is not None:
                    usage.cache_creation_input_tokens = evt.cache_creation_input_tokens
                    sctx.cache_creation_input_tokens = evt.cache_creation_input_tokens

        sctx.stop_reason = "end_turn" if not tool_calls else "tool_use"
        sctx.cost_usd = calc_cost_usd(
            sctx.model,
            sctx.input_tokens,
            sctx.output_tokens,
            sctx.cache_read_input_tokens,
            sctx.cache_creation_input_tokens,
        )

    await _maybe_call(on_usage, usage)
    return assistant, tool_calls, usage


async def _execute_tools(
    registry: ToolRegistry,
    tool_calls: list[dict],
    ctx: RunContext,
    on_tool_call: OnToolCall | None,
) -> list[Message]:
    """执行一轮 tool_calls：只读并发、写串行（F3.4.6）。

    返回 tool_result messages，已按调用顺序排列（便于配对）。
    """
    if ctx.tool_ctx is None:
        raise RuntimeError("tool_ctx not set but tools requested")

    async def _exec_one(tc: dict) -> Message:
        if ctx.abort.is_set():
            raise InterruptedError("interrupted during tool execution")
        await _maybe_call(on_tool_call, tc)
        tool_name = tc["name"]
        is_skill = tool_name.startswith("skill__")
        span_type = SpanType.skill.value if is_skill else SpanType.tool.value
        async with span(span_type, tool_name=tool_name) as sctx:
            sctx.tool_input_summary = str(tc.get("input", ""))[:2000]
            content = await registry.execute(tc["name"], tc.get("input", "{}"), ctx.tool_ctx)
            sctx.tool_output_summary = content[:2000] if content else None
            if content and content.startswith("Error: path rejected"):
                sctx.tool_path_rejected = True
        return Message(role="tool_result", tool_call_id=tc.get("id", ""), content=content)

    # 分类：只读 vs 写
    read_calls = [tc for tc in tool_calls if registry.is_readonly(tc["name"])]
    write_calls = [tc for tc in tool_calls if not registry.is_readonly(tc["name"])]

    results: dict[int, Message] = {}

    # 只读并发
    if read_calls:
        read_results = await asyncio.gather(*[_exec_one(tc) for tc in read_calls])
        for tc, msg in zip(read_calls, read_results, strict=True):
            results[id(tc)] = msg

    # 写串行（D20：抢 WS 锁由工具内部/T6.1 处理；此处保证顺序）
    for tc in write_calls:
        results[id(tc)] = await _exec_one(tc)

    # 按原 tool_calls 顺序返回（保证 tool_use ↔ tool_result 配对）
    return [results[id(tc)] for tc in tool_calls]


async def run_loop(
    provider: Provider,
    ctx: RunContext,
    registry: ToolRegistry | None = None,
    *,
    on_text: OnText | None = None,
    on_tool_call: OnToolCall | None = None,
    on_usage: OnUsage | None = None,
    context_manager: ContextManager | None = None,
) -> str:
    """Agentic Loop 入口。返回最终回复文本。

    - 无 registry 或无 tools：首轮无 tool_use 即返回
    - 中止：ctx.abort.set() → 抛 InterruptedError
    - 超过 MAX_TOOL_ROUNDS → 抛 RuntimeError（F3.3.11）
    """
    tools_defs = registry.defs() if registry else []

    for round_idx in range(MAX_TOOL_ROUNDS):
        if ctx.abort.is_set():
            raise InterruptedError("interrupted at round start")

        # 上下文管理（D34）：每轮前跑四道防线（L1 clearing / L4 兜底）
        if context_manager is not None:
            await context_manager.manage(ctx.messages)

        assistant, tool_calls, _usage = await _stream_round(
            provider, ctx, tools_defs, on_text, on_usage
        )
        ctx.messages.append(assistant)

        if not tool_calls:
            return assistant.content or ""

        if registry is None:
            # 有 tool_use 但无 registry：回灌错误让 Agent 自知
            for tc in tool_calls:
                ctx.messages.append(
                    Message(
                        role="tool_result",
                        tool_call_id=tc.get("id", ""),
                        content=f"Error: no tool registry available for {tc['name']}",
                    )
                )
            continue

        tool_result_msgs = await _execute_tools(registry, tool_calls, ctx, on_tool_call)
        ctx.messages.extend(tool_result_msgs)

        log.info(
            "round %d: %d tools (%d read / %d write)",
            round_idx + 1,
            len(tool_calls),
            sum(1 for tc in tool_calls if registry.is_readonly(tc["name"])),
            sum(1 for tc in tool_calls if not registry.is_readonly(tc["name"])),
        )

    raise RuntimeError(f"exceeded max tool rounds ({MAX_TOOL_ROUNDS})")
