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

    async def manage(
        self, messages: list[Message], system: str | None = None
    ) -> dict:
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

        before = (await self._provider.count_tokens(messages, system=system)).input_tokens
        if before < trigger1:
            return {"layer": None, "before": before, "after": before}

        # L1 clearing
        cleared = self._clear_old_tool_results(messages)
        after_l1 = (await self._provider.count_tokens(messages, system=system)).input_tokens
        log.info("context L1 clearing: %d -> %d tokens (cleared %d)", before, after_l1, cleared)
        await self._emit_span("L1", "clearing", before, after_l1, cleared_count=cleared)

        after_l2 = after_l1
        compacted = False
        info: dict = {}
        # L2 compaction（L1 后仍超 trigger2）
        if after_l1 > trigger2:
            target = int(window * self._cfg.summary_target_pct)
            info = await self._compact(messages, target)
            compacted = info.get("compacted", False)
            after_l2 = (await self._provider.count_tokens(messages, system=system)).input_tokens
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
                # L3 memory 联动提示已合并到摘要消息内部（不作为独立 user 消息，
                # 避免 agent 把提示当成新任务执行，污染用户可见回复）

        # L4 硬兜底 — 先尝试紧急截断，仍超限才 abort
        if after_l2 > hard:
            log.warning(
                "context L4: %d > %d after L1+L2, trying emergency truncation",
                after_l2, hard,
            )
            self._emergency_truncate(messages)
            after_l4 = (await self._provider.count_tokens(messages, system=system)).input_tokens
            if after_l4 <= hard:
                log.warning(
                    "context L4 emergency truncation saved run: %d -> %d",
                    after_l2, after_l4,
                )
                await self._emit_span("L4", "emergency", after_l2, after_l4)
                return {
                    "layer": "L4-emergency",
                    "before": before,
                    "after": after_l4,
                    "cleared": cleared,
                    "compacted": compacted,
                }
            log.error(
                "context L4 hard limit: %d > %d (95%% of %d) after emergency truncation; abort",
                after_l4, hard, window,
            )
            raise ContextLimitError(
                f"context still {after_l4} > {hard} (95% of {window}) after "
                f"clearing/compaction/emergency; abort run"
            )

        return {
            "layer": "L2" if compacted else "L1",
            "before": before,
            "after": after_l2,
            "cleared": cleared,
            "compacted": compacted,
            "kept_rounds": info.get("kept_rounds") if compacted else None,
        }

    async def _compact(self, messages: list[Message], target: int) -> dict:
        """L2：较早历史压成摘要，保留最近 compact_recent 轮原文 + tool_use/tool_result 配对。

        预算感知：``target`` 为 compaction 后目标总 token（含 suffix）。suffix 最多占
        ``target * 60%``，超出则递减 ``compact_recent`` 减少 retained 轮数；剩余预算
        全给摘要。``max_tokens`` 传入 LLM 调用约束输出长度。

        P3 D-CE.2: 若 ``cfg.compact_recursive`` 且前缀 token > 段预算，
        分段递归摘要（上限 3 层）；否则回退 MVP 单次摘要。

        降级策略：
        1. 优先 tool_result-based split → LLM 摘要
        2. split 失败 → fallback split（任意安全边界）
        3. 摘要失败 → 截断降级（保留首尾，中间省略）
        4. suffix 过大 → 截断 suffix 内旧 tool_result
        """
        cfg = self._cfg
        suffix_budget = int(target * 0.6)

        # 从 cfg.compact_recent 递减，直到 suffix token ≤ budget 或降为 0
        split_idx: int | None = None
        suffix_tokens = 0
        actual_recent = 0
        for recent in range(cfg.compact_recent, -1, -1):
            idx = self._find_compact_split(messages, recent)
            if idx is None:
                continue
            st = sum(len(m.content or "") // 4 for m in messages[idx:])
            split_idx = idx
            suffix_tokens = st
            actual_recent = recent
            if st <= suffix_budget or recent == 0:
                break

        # Fallback: 无 tool_result 时按安全边界 split
        if split_idx is None or split_idx == 0:
            split_idx = self._find_fallback_split(messages)
            if split_idx is None or split_idx <= 1:
                return {"compacted": False}
            suffix_tokens = sum(len(m.content or "") // 4 for m in messages[split_idx:])
            actual_recent = -1

        prefix = messages[:split_idx]
        suffix = messages[split_idx:]

        # suffix 自身过大 → 截断旧 tool_result content
        if suffix_tokens > suffix_budget:
            self._truncate_suffix_tool_results(suffix, keep=2)
            suffix_tokens = sum(len(m.content or "") // 4 for m in suffix)

        summary_budget = max(800, target - suffix_tokens)

        summary_text = None
        if cfg.compact_recursive:
            summary_text = await self._recursive_compact(
                prefix, depth=0, max_tokens=summary_budget
            )
        else:
            summary_text = await self._single_summary(prefix, max_tokens=summary_budget)

        # 摘要失败 → 截断降级（不放弃 compaction）
        if not summary_text:
            log.warning("L2 summary failed, using truncation fallback")
            summary_text = self._truncate_prefix(prefix)

        if not summary_text:
            return {"compacted": False}

        summary_msg = Message(
            role="user",
            content=f"[历史摘要]\n{summary_text}\n\n{_COMPACTION_SIGNAL}",
        )
        # in-place 替换（调用方持有的 list 对象不变）
        messages.clear()
        messages.append(summary_msg)
        messages.extend(suffix)
        return {
            "compacted": True,
            "kept_rounds": actual_recent,
            "summary_len": len(summary_text),
        }

    @staticmethod
    def _find_compact_split(
        messages: list[Message], compact_recent: int
    ) -> int | None:
        """找到 suffix 起始 index：suffix 包含最后 compact_recent 个 tool_result
        及其配对 tool_use 起的全部消息。无法分割返回 None。
        """
        tr_indices = [i for i, m in enumerate(messages) if m.role == "tool_result"]
        if len(tr_indices) <= compact_recent:
            return None
        keep_tr = tr_indices[-compact_recent:] if compact_recent > 0 else []
        min_tr_idx = keep_tr[0] if keep_tr else len(messages)
        for i in range(min_tr_idx - 1, -1, -1):
            if messages[i].tool_calls:
                return i if i > 0 else None
        return None

    @staticmethod
    def _find_fallback_split(messages: list[Message]) -> int | None:
        """无 tool_result 时的 fallback split：在安全边界处切割。

        安全边界 = 前一条消息是 user / tool_result / 无 tool_calls 的 assistant，
        确保 suffix 不会有孤立的 tool_use。
        """
        n = len(messages)
        if n <= 3:
            return None
        # 从 2/3 处往前找安全边界（保留后 1/3 作为 suffix）
        target = max(2, n * 2 // 3)
        for i in range(target, 0, -1):
            prev = messages[i - 1]
            if prev.role in ("user", "tool_result"):
                return i
            if prev.role == "assistant" and not prev.tool_calls:
                return i
        return 1

    @staticmethod
    def _truncate_prefix(prefix: list[Message]) -> str:
        """摘要失败时的降级：保留首条 user + 末尾 2 条，中间省略。"""
        if not prefix:
            return ""
        parts: list[str] = []
        if prefix[0].role == "user":
            c = (prefix[0].content or "")[:3000]
            parts.append(f"[原始任务]\n{c}")
        for m in prefix[-2:]:
            c = (m.content or "")[:2000]
            parts.append(f"[{m.role}]\n{c}")
        middle = len(prefix) - 3
        header = f"[上下文截断 — {middle} 条消息被省略]\n\n" if middle > 0 else ""
        return header + "\n\n---\n\n".join(parts)

    @staticmethod
    def _truncate_suffix_tool_results(suffix: list[Message], keep: int = 2) -> None:
        """suffix 过大时截断旧 tool_result content（保留最近 keep 个完整）。"""
        tr_indices = [i for i, m in enumerate(suffix) if m.role == "tool_result"]
        to_truncate = tr_indices[:-keep] if keep > 0 else tr_indices
        for i in to_truncate:
            content = suffix[i].content or ""
            if len(content) > 1000:
                suffix[i].content = (
                    content[:1000] + f"\n\n[... truncated ({len(content)} chars total)]"
                )

    @staticmethod
    def _emergency_truncate(messages: list[Message]) -> None:
        """L4 紧急截断：暴力裁剪以避免 abort。

        - 清除所有 tool_result content（仅保留最后 2 个）
        - 清除所有 reasoning（仅保留最后一条 assistant）
        - 所有 content 截断到 5000 字符
        - 所有 tool_call input 截断到 200 字符
        """
        tr_indices = [i for i, m in enumerate(messages) if m.role == "tool_result"]
        for i in tr_indices[:-2]:
            messages[i].content = _PLACEHOLDER

        asst_indices = [i for i, m in enumerate(messages) if m.role == "assistant"]
        last_asst = asst_indices[-1] if asst_indices else -1
        for i in asst_indices:
            if i != last_asst and messages[i].reasoning:
                messages[i].reasoning = None

        for m in messages:
            if m.content and len(m.content) > 5000:
                m.content = m.content[:5000] + "\n\n[... emergency truncated]"
            if m.tool_calls:
                for tc in m.tool_calls:
                    inp = tc.get("input", "")
                    if len(inp) > 200:
                        tc["input"] = inp[:200] + "...[truncated]"

    async def _single_summary(
        self, messages: list[Message], max_tokens: int = 4096
    ) -> str | None:
        """单次摘要，``max_tokens`` 约束 LLM 输出 + prompt 提示长度。"""
        instructions = (
            f"{self._cfg.compact_instructions}\n\n"
            f"请将摘要控制在约 {max_tokens} tokens（约 {max_tokens * 4} 字符）以内。"
        )
        try:
            summary_msgs, _ = await self._summary_provider.chat(
                messages=messages, system=instructions, max_tokens=max_tokens
            )
        except Exception:
            log.warning("L2 compaction summary call failed; skip", exc_info=True)
            return None
        return (summary_msgs[0].content or "").strip() if summary_msgs else ""

    async def _recursive_compact(
        self, messages: list[Message], depth: int = 0, max_tokens: int = 4096
    ) -> str | None:
        """D-CE.2 递归分段摘要（预算感知）。

        - 前缀 ≤ 段预算 → 单次摘要（base case）
        - 前缀 > 段预算 → 按回合分段，逐段摘要后合并
        - 合并后 > max_tokens → 再递归一层（depth+1）
        - 递归上限 3 层后仍超 → 最终收敛：对 merged 做一次单次摘要
        """
        cfg = self._cfg
        summary_window = self._summary_provider.context_window
        seg_budget = min(int(summary_window * 0.6), max_tokens * 3)

        prefix_tokens = sum(len(m.content or "") // 4 for m in messages)

        # Base case: 前缀够小，或已达递归上限
        if prefix_tokens <= seg_budget or depth >= 3:
            text = await self._single_summary(messages, max_tokens=max_tokens)
            if text and depth >= 3:
                text = text + "\n\n[递归上限已达，早期历史可能被截断]"
            return text

        # 分段摘要
        segments = self._split_by_turns(messages, seg_budget)
        seg_max = min(4096, max_tokens)
        seg_summaries: list[str] = []
        for i, seg in enumerate(segments):
            try:
                sm, _ = await self._summary_provider.chat(
                    messages=seg,
                    system=cfg.compact_instructions,
                    max_tokens=seg_max,
                )
                text = (sm[0].content or "").strip() if sm else ""
                seg_summaries.append(text if text else self._truncate_segment(seg))
            except Exception:
                log.warning("L2 segment %d summary failed; truncate", i, exc_info=True)
                seg_summaries.append(self._truncate_segment(seg))

        merged = "\n\n---\n\n".join(seg_summaries)
        if not merged.strip():
            return None

        # 合并后仍超 max_tokens → 再递归 / 最终收敛
        merged_tokens = len(merged) // 4
        if merged_tokens > max_tokens:
            if depth < 2:
                recursive_result = await self._recursive_compact(
                    [Message(role="user", content=merged)], depth + 1, max_tokens=max_tokens
                )
                return recursive_result or merged
            # 最终收敛：对 merged 做一次单次摘要压到目标
            converged = await self._single_summary(
                [Message(role="user", content=merged)], max_tokens=max_tokens
            )
            return converged or merged

        return merged

    @staticmethod
    def _split_by_turns(
        messages: list[Message], budget: int
    ) -> list[list[Message]]:
        """按回合分段，每段粗估 token ≤ budget。边界对齐到完整回合。"""
        segments: list[list[Message]] = []
        current: list[Message] = []
        current_tokens = 0
        i = 0
        while i < len(messages):
            # 一个回合 = user 消息到下一个 user 消息之前（含中间 assistant/tool_result）
            turn_end = i + 1
            while turn_end < len(messages) and messages[turn_end].role != "user":
                turn_end += 1
            turn = messages[i:turn_end]
            turn_tokens = sum(len(m.content or "") // 4 for m in turn)
            if current and current_tokens + turn_tokens > budget:
                segments.append(current)
                current = list(turn)
                current_tokens = turn_tokens
            else:
                current.extend(turn)
                current_tokens += turn_tokens
            i = turn_end
        if current:
            segments.append(current)
        return segments

    @staticmethod
    def _truncate_segment(seg: list[Message]) -> str:
        """单段摘要失败时的降级：保留首尾各 500 字符 + 中段省略提示。"""
        parts: list[str] = []
        total = 0
        for m in seg:
            c = m.content or ""
            parts.append(c)
            total += len(c)
        if total <= 1000:
            return "\n".join(parts)
        head = "\n".join(parts)[:500]
        tail = "\n".join(parts)[-500:]
        return f"{head}\n\n[中段省略]\n\n{tail}"

    def _clear_old_tool_results(self, messages: list[Message]) -> int:
        """L1：保留最近 ``clear_keep`` 个 tool_result，其余 content 替换占位。

        保留 tool_use 记录与 id 配对（只动 tool_result.content）。
        ``exclude_tools`` 命中的工具 result 不清。

        额外清理（减少 count_tokens 误计）：
        - 旧 assistant 消息的 ``reasoning`` 字段置 None（API 已替换为空串）
        - 旧 assistant 消息的 ``tool_calls[].input`` 截断到 500 字符
        """
        cfg = self._cfg
        exclude = set(cfg.exclude_tools)
        tr_indices = [i for i, m in enumerate(messages) if m.role == "tool_result"]
        asst_indices = [
            i for i, m in enumerate(messages)
            if m.role == "assistant" and (m.reasoning or m.tool_calls)
        ]

        if len(tr_indices) <= cfg.clear_keep and not asst_indices:
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

        # 清旧 assistant reasoning（仅保留最后一条）
        last_asst = asst_indices[-1] if asst_indices else -1
        for i in asst_indices:
            if i == last_asst:
                continue
            m = messages[i]
            if m.reasoning:
                m.reasoning = None
                cleared += 1
            # 截断旧 tool_call input（Write 等工具的 input 可能很大）
            if m.tool_calls:
                for tc in m.tool_calls:
                    inp = tc.get("input", "")
                    if len(inp) > 500:
                        tc["input"] = inp[:500] + f"...[truncated, was {len(inp)} chars]"
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
