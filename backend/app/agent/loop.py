"""Agentic Loop 主体（design §6.5 / spec F3.3）。

核心循环：调用 LLM（Provider）→ 解析 tool_use → 执行工具 → 反馈结果 → 直到最终回复。
支持流式输出（``StreamEvent`` 由调用方推飞书）、中断 / 超时检测点、最大 tool_use 轮数
兜底（F3.3.11）。

Loop 不直接感知飞书——stream 事件通过回调（``on_tool_call``、``on_text``、``on_stop``）
交给调用方（接入层）推卡片，保持 Agent 内核与接入层解耦。
"""

import asyncio
import json
import logging
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass, field

from app.providers.base import (
    Message,
    Provider,
    StreamEvent,
    ToolDef,
    Usage,
)

log = logging.getLogger("agent.loop")

_STREAM_TIMEOUT = 600
_MAX_TOOL_ROUNDS = 50


@dataclass
class ToolResult:
    """工具执行结果。"""
    content: str
    is_error: bool = False
    tool_call_id: str = ""


@dataclass
class RunContext:
    """一次 Loop 运行的上下文。"""
    system: str = ""
    messages: list[Message] = field(default_factory=list)
    tools: list[ToolDef] = field(default_factory=list)
    run_id: int | None = None
    abort: asyncio.Event = field(default_factory=asyncio.Event)


# ---- 事件回调类型 ----
OnText = Callable[[str], None]  # text_delta 片段
OnToolCall = Callable[[dict], None]  # {name, id, input}
OnToolResult = Callable[[ToolResult], None]
OnUsage = Callable[[Usage], None]
OnStop = Callable[[str], None]  # final_text


async def run_loop(
    provider: Provider,
    ctx: RunContext,
    *,
    on_text: OnText | None = None,
    on_tool_call: OnToolCall | None = None,
    on_tool_result: OnToolResult | None = None,
    on_usage: OnUsage | None = None,
    on_stop: OnStop | None = None,
) -> str:
    """Agentic Loop 入口。

    Args:
        provider: LLM Provider（Claude / mock）
        ctx: RunContext（system / messages / tools / abort event）
        on_*: 事件回调（接入层通过它们推飞书）
    """
    final_text = ""
    for round_idx in range(_MAX_TOOL_ROUNDS):
        # 中止检测
        if ctx.abort.is_set():
            raise InterruptedError("interrupted at round start")

        # 调用 LLM（流式）
        assistant_msg = Message(role="assistant", content="")
        round_tool_calls: list[dict] = []
        inp = 0
        outp = 0

        try:
            async for evt in provider.stream(
                messages=ctx.messages,
                tools=ctx.tools or None,
                system=ctx.system,
            ):
                if evt.type == "text" and evt.text:
                    assistant_msg.content = (assistant_msg.content or "") + evt.text
                    if on_text:
                        on_text(evt.text)

                elif evt.type == "tool_use_start" and evt.tool_name:
                    round_tool_calls.append({"id": "", "name": evt.tool_name, "input": evt.tool_input or "{}"})

                elif evt.type == "tool_use_end":
                    pass

                elif evt.type == "stop":
                    if evt.input_tokens is not None:
                        inp = evt.input_tokens
                    if evt.output_tokens is not None:
                        outp = evt.output_tokens
                    break

        except Exception as e:
            log.exception("LLM stream error round %d", round_idx)
            raise

        # usage
        usage = Usage(input_tokens=inp, output_tokens=outp)
        if on_usage:
            on_usage(usage)
        final_text = assistant_msg.content or ""

        # tool_use 解析（handle one round of parallel tool calls）
        if not round_tool_calls:
            # 无工具调用 → 最终回复
            if on_stop:
                on_stop(final_text)
            return final_text

        assistant_msg.tool_calls = round_tool_calls
        ctx.messages.append(assistant_msg)

        # 逐工具调用执行（D20：写工具抢锁；F3.4.6：只读工具并发）
        for tc in round_tool_calls:
            if ctx.abort.is_set():
                raise InterruptedError("interrupted during tool execution")
            if on_tool_call:
                on_tool_call(tc)

            # tool_call 回调后由调用方执行工具并返回结果
            # (此处仅为 Loop 编排，工具执行由上层 `runtool` 函数完成)
            # 执行后结果通过 on_tool_result 回调或直接塞 ctx.messages
            if on_tool_result:
                await asyncio.sleep(0)  # 占位，实际执行在 runtool 层

        log.info(
            "tool round %d: %d tools, in=%d out=%d text_len=%d",
            round_idx + 1,
            len(round_tool_calls),
            inp, outp, len(final_text),
        )

    raise RuntimeError(f"exceeded max tool rounds ({_MAX_TOOL_ROUNDS})")
