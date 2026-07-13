"""上下文管理（design D34）。

四道防线（Provider 无关 + WS 级可配）：

- **L0 源头节流**：工具层截断（Bash stdout / Read 分段，已在 builtin 工具实现）
- **L1 clearing**：``token > trigger1``（默认 limit 50%）→ 较早 ``tool_result`` content
  替换为占位，**保留 tool_use 记录与 id 配对不变量**（Anthropic 要求配对齐全）
- **L2 compaction**：``token > trigger2``（默认 75%）→ 旧历史压成结构化摘要替换，
  摘要模型 WS 级可配（可指国内模型 GLM，降本 + 规避 Claude 封禁）；保 tool 配对
- **L3 memory 联动**：compaction 后注入强信号，提示主 Agent 收口写 chat memory（D22）
- **L4 硬兜底**：三层后仍 > limit 95% → 抛 ``ContextLimitError``，Loop 中断告知

clearing / compaction 各产一条 ``context`` span（记命中层 / 前后 token / 压缩比）。
"""

import logging

from app.agent.context_config import ContextConfig
from app.db.models.span import SpanType
from app.observability.tracer import span
from app.providers.base import Message, Provider

log = logging.getLogger("agent.context")

_PLACEHOLDER = "[cleared; re-call the tool to refetch if needed]"
_HARD_PCT = 0.95  # L4 硬兜底阈值（安全边界，不 WS 可配）
_COMPACTION_SIGNAL = (
    "⚠️ [系统提示] 对话上下文已被压缩为摘要。如果本轮涉及重要的技术决策、用户偏好或"
    "未完成事项，请用 Write 工具把它们记入 memory/（MEMORY.md），以便后续 Run 复用。"
)


class ContextLimitError(Exception):
    """上下文超限（L4 兜底中断）。"""


class ContextManager:
    """四道防线编排（Provider 无关，D34 关键）。"""

    def __init__(
        self,
        provider: Provider,
        cfg: ContextConfig | None = None,
        summary_provider: Provider | None = None,
    ) -> None:
        self._provider = provider
        self._cfg = cfg or ContextConfig()
        self._summary_provider = summary_provider or provider

    async def manage(self, messages: list[Message]) -> dict:
        """运行四道防线（in-place 改 messages）。返回 ``{layer, before, after, ...}``。

        - 未超 trigger1：``{layer: None}``
        - L1 命中：``{layer: "L1", before, after, cleared}``
        - L2 命中：``{layer: "L2", ..., compacted: True}``
        - L4 命中（三层后仍超 hard）：抛 ``ContextLimitError``
        """
        window = self._provider.context_window
        trigger1 = int(window * self._cfg.trigger1)
        trigger2 = int(window * self._cfg.trigger2)
        hard = int(window * _HARD_PCT)

        before = (await self._provider.count_tokens(messages)).input_tokens
        if before < trigger1:
            return {"layer": None, "before": before, "after": before}

        # L1 clearing
        cleared = self._clear_old_tool_results(messages)
        after_l1 = (await self._provider.count_tokens(messages)).input_tokens
        log.info("context L1 clearing: %d -> %d tokens (cleared %d)", before, after_l1, cleared)
        await self._emit_span("L1", "clearing", before, after_l1, cleared_count=cleared)

        after_l2 = after_l1
        compacted = False
        # L2 compaction（L1 后仍超 trigger2）
        if after_l1 > trigger2:
            info = await self._compact(messages)
            compacted = info.get("compacted", False)
            after_l2 = (await self._provider.count_tokens(messages)).input_tokens
            if compacted:
                log.info("context L2 compaction: %d -> %d tokens", after_l1, after_l2)
                await self._emit_span(
                    "L2",
                    "compaction",
                    after_l1,
                    after_l2,
                    kept_rounds=info.get("kept_rounds"),
                    summary_len=info.get("summary_len", 0),
                    summary_provider=self._summary_provider.name,
                )
                # L3 强信号注入（D34：提示主 Agent 收口写 chat memory）
                messages.append(Message(role="user", content=_COMPACTION_SIGNAL))

        # L4 硬兜底
        if after_l2 > hard:
            raise ContextLimitError(
                f"context still {after_l2} > {hard} (95% of {window}) after "
                f"clearing/compaction; abort run"
            )

        return {
            "layer": "L2" if compacted else "L1",
            "before": before,
            "after": after_l2,
            "cleared": cleared,
            "compacted": compacted,
        }

    async def _compact(self, messages: list[Message]) -> dict:
        """L2：较早历史压成摘要，保留最近 compact_recent 轮原文 + tool_use/tool_result 配对。

        分段：保留最后 ``compact_recent`` 个 tool_result 及其配对 tool_use 起的全部后缀；
        前缀（结束于完整回合，不会留下孤立 tool_use）整体替换为一条摘要 user 消息。
        """
        cfg = self._cfg
        tr_indices = [i for i, m in enumerate(messages) if m.role == "tool_result"]
        if len(tr_indices) <= cfg.compact_recent:
            return {"compacted": False}
        # 保留最后 compact_recent 个 tool_result；定位最早保留 result 对应的 tool_use
        keep_tr = tr_indices[-cfg.compact_recent:] if cfg.compact_recent > 0 else []
        min_tr_idx = keep_tr[0] if keep_tr else len(messages)
        keep_from = 0
        for i in range(min_tr_idx - 1, -1, -1):
            if messages[i].tool_calls:
                keep_from = i
                break
        if keep_from == 0:
            return {"compacted": False}  # 前缀为空，无可压
        prefix = messages[:keep_from]
        suffix = messages[keep_from:]
        try:
            summary_msgs, _ = await self._summary_provider.chat(
                messages=prefix, system=cfg.compact_instructions
            )
        except Exception:
            log.warning("L2 compaction summary call failed; skip", exc_info=True)
            return {"compacted": False}
        summary_text = (summary_msgs[0].content or "").strip() if summary_msgs else ""
        if not summary_text:
            return {"compacted": False}
        summary_msg = Message(role="user", content=f"[历史摘要]\n{summary_text}")
        # in-place 替换（调用方持有的 list 对象不变）
        messages.clear()
        messages.append(summary_msg)
        messages.extend(suffix)
        return {
            "compacted": True,
            "kept_rounds": cfg.compact_recent,
            "summary_len": len(summary_text),
        }

    def _clear_old_tool_results(self, messages: list[Message]) -> int:
        """L1：保留最近 ``clear_keep`` 个 tool_result，其余 content 替换占位。

        保留 tool_use 记录与 id 配对（只动 tool_result.content）。``exclude_tools``
        命中的工具 result 不清。
        """
        cfg = self._cfg
        exclude = set(cfg.exclude_tools)
        tr_indices = [i for i, m in enumerate(messages) if m.role == "tool_result"]
        if len(tr_indices) <= cfg.clear_keep:
            return 0
        keep = cfg.clear_keep
        to_clear = tr_indices[:-keep] if keep > 0 else tr_indices
        cleared = 0
        for i in to_clear:
            name = self._tool_name_for_result(messages, i)
            if name and name in exclude:
                continue
            messages[i].content = _PLACEHOLDER
            cleared += 1
        return cleared

    @staticmethod
    def _tool_name_for_result(messages: list[Message], tr_idx: int) -> str | None:
        """tool_result → 对应 tool_use 的工具名（向前匹配 tool_call_id）。"""
        tid = messages[tr_idx].tool_call_id
        if not tid:
            return None
        for m in messages[:tr_idx]:
            if m.tool_calls:
                for tc in m.tool_calls:
                    if tc.get("id") == tid:
                        return tc.get("name")
        return None

    async def _emit_span(
        self, layer: str, event_type: str, before: int, after: int, **extra
    ) -> None:
        """best-effort 记一条 context event span（D34）。无 trace 上下文时 no-op。"""
        attrs: dict = {
            "layer": layer,
            "event_type": event_type,
            "before_tokens": before,
            "after_tokens": after,
        }
        if before > 0:
            attrs["ratio"] = round(after / before, 3)
        attrs.update({k: v for k, v in extra.items() if v is not None})
        try:
            async with span(SpanType.context.value) as sctx:
                sctx.attributes = attrs
        except Exception:
            log.debug("context span emit failed", exc_info=True)
