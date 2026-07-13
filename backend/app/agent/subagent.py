"""子代理（Agent 工具，design D33）。

主 Agent 一轮返回多个 ``Agent`` tool_use 时，Loop 的只读并发（``asyncio.gather``）
把它们并行执行；每个子代理独立上下文窗口，仅回最终消息给主 Agent。子代理复用父 Run
的 provider / 工具 / ws 锁（可重入，不重复抢；写型子代理间不二次串行，依赖主 Agent
拆分时避免写冲突）。

子代理的 registry 排除 ``Agent``（MVP 深度 1，防无限递归）。
"""

import asyncio
from typing import ClassVar

from app.agent.loop import RunContext, run_loop
from app.providers.base import Message, Provider
from app.tools.base import Tool, ToolContext
from app.tools.registry import ToolRegistry


class AgentTool(Tool):
    name: ClassVar[str] = "Agent"
    description: ClassVar[str] = (
        "委派子任务给子代理（独立上下文，仅回最终消息）。"
        "适合可并行拆分的独立子任务；存在写冲突 / 强依赖时不要并行。"
    )
    input_schema: ClassVar[dict] = {
        "type": "object",
        "properties": {"prompt": {"type": "string", "description": "子任务指令"}},
        "required": ["prompt"],
    }
    # 并发执行（Loop gather）；不单独抢锁，复用父 Run 锁（D33 可重入）
    read_only: ClassVar[bool] = True

    def __init__(
        self,
        provider: Provider,
        registry: ToolRegistry,
        semaphore: asyncio.Semaphore,
    ) -> None:
        self._provider = provider
        self._registry = registry
        self._semaphore = semaphore

    async def run(self, input: dict, ctx: ToolContext) -> str:
        prompt = input.get("prompt", "")
        # 子代理 registry 排除 Agent（深度 1，防递归）
        sub_registry = self._registry.sub_registry(exclude={"Agent"})
        sub_ctx = RunContext(
            system=ctx.system_prompt,  # 继承父 Run 的 system（WS/Repo AGENT.md + MEMORY）
            messages=[Message(role="user", content=prompt)],
            tool_ctx=ctx,  # 复用父 ws/cwd/锁
        )
        try:
            # 并行度上限（D33）：超限的子代理在 semaphore 处排队，防 fork 爆炸
            async with self._semaphore:
                return await run_loop(self._provider, sub_ctx, sub_registry)
        except Exception as e:
            return f"Error: subagent failed: {e}"
