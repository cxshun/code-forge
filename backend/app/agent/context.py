"""上下文管理（design D34）。

四道防线（MVP 实现 L0 / L1 / L4；L2 compaction、L3 memory 联动预留）：

- **L0 源头节流**：工具层截断（Bash stdout / Read 分段，已在 builtin 工具实现）
- **L1 clearing**：``token > trigger1``（默认 limit 50%）→ 把较早的 ``tool_result``
  content 替换为占位，**保留 tool_use 记录与 id 配对不变量**（Anthropic 要求配对齐全）
- **L4 硬兜底**：clearing 后仍 > limit 95% → 抛 ``ContextLimitError``，Loop 中断告知
"""

import logging

from app.providers.base import Message, Provider

log = logging.getLogger("agent.context")

_PLACEHOLDER = "[cleared; re-call the tool to refetch if needed]"


class ContextLimitError(Exception):
    """上下文超限（L4 兜底中断）。"""


class ContextManager:
    """四道防线编排（Provider 无关，D34 关键）。"""

    def __init__(
        self,
        provider: Provider,
        trigger1_pct: float = 0.5,
        hard_pct: float = 0.95,
        clear_keep: int = 6,
    ) -> None:
        self._provider = provider
        self._trigger1_pct = trigger1_pct
        self._hard_pct = hard_pct
        self._clear_keep = clear_keep

    async def manage(self, messages: list[Message]) -> dict:
        """运行防线。返回 ``{layer, before, after, cleared?}``。

        - 未超 trigger1：``{layer: None}``
        - L1 命中：``{layer: "L1", before, after, cleared}``
        - L4 命中（clearing 后仍超 hard）：抛 ``ContextLimitError``
        """
        window = self._provider.context_window
        trigger1 = int(window * self._trigger1_pct)
        hard = int(window * self._hard_pct)

        before = (await self._provider.count_tokens(messages)).input_tokens
        if before < trigger1:
            return {"layer": None, "before": before, "after": before}

        cleared = self._clear_old_tool_results(messages)
        after = (await self._provider.count_tokens(messages)).input_tokens
        log.info(
            "context L1 clearing: %d -> %d tokens (cleared %d tool_results)",
            before,
            after,
            cleared,
        )

        if after > hard:
            raise ContextLimitError(
                f"context still {after} > {hard} (95% of {window}) after clearing; abort run"
            )

        return {
            "layer": "L1",
            "before": before,
            "after": after,
            "cleared": cleared,
        }

    def _clear_old_tool_results(self, messages: list[Message]) -> int:
        """保留最近 ``clear_keep`` 个 tool_result，其余 content 替换为占位。

        保留 tool_use 记录与 id 配对（只动 tool_result.content，不删消息、不改 id）。
        """
        tr_indices = [i for i, m in enumerate(messages) if m.role == "tool_result"]
        if len(tr_indices) <= self._clear_keep:
            return 0
        keep = self._clear_keep
        to_clear = tr_indices[:-keep] if keep > 0 else tr_indices
        for i in to_clear:
            messages[i].content = _PLACEHOLDER
        return len(to_clear)
