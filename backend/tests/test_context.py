"""上下文管理测试（T5.10 验收：L1/L2/L3/L4 + exclude_tools + context span）。"""

import pytest

from app.agent.context import ContextLimitError, ContextManager
from app.agent.context_config import ContextConfig
from app.providers.base import Message, Provider, Usage

pytestmark = pytest.mark.asyncio


class _FakeProvider(Provider):
    """可控 token 计数 + 可选摘要文本的假 Provider（不调真实 LLM）。"""

    def __init__(
        self,
        context_window: int = 10000,
        tokens: dict | None = None,
        summary_text: str | None = None,
    ) -> None:
        self._window = context_window
        self._tokens = tokens or {}  # id(messages) -> tokens
        self._summary_text = summary_text
        self.chat_calls = 0

    @property
    def context_window(self) -> int:
        return self._window

    @property
    def model(self) -> str:
        return "fake-model"

    @property
    def name(self) -> str:
        return "fake"

    async def count_tokens(self, messages, system=None):
        return Usage(input_tokens=self._tokens.get(id(messages), 0))

    async def chat(self, messages, tools=None, system=None):
        self.chat_calls += 1
        return [Message(role="assistant", content=self._summary_text or "summary")], Usage()

    async def stream(self, messages, tools=None, system=None):
        raise NotImplementedError
        yield  # type: ignore[unreachable]


def _msgs(n_tool_results: int) -> list[Message]:
    msgs = [Message(role="user", content="q")]
    for i in range(n_tool_results):
        msgs.append(
            Message(
                role="assistant",
                content=f"step{i}",
                tool_calls=[{"id": f"t{i}", "name": "Read", "input": "{}"}],
            )
        )
        msgs.append(Message(role="tool_result", tool_call_id=f"t{i}", content="x" * 500))
    return msgs


async def test_no_clearing_below_trigger():
    msgs = _msgs(3)
    provider = _FakeProvider(context_window=10000, tokens={id(msgs): 100})
    cm = ContextManager(provider, ContextConfig(clear_keep=2))
    res = await cm.manage(msgs)
    assert res["layer"] is None


async def test_l1_clearing_old_tool_results():
    msgs = _msgs(5)
    calls = {"n": 0}

    async def fake_count(messages, system=None):
        calls["n"] += 1
        return Usage(input_tokens=6000 if calls["n"] == 1 else 2000)

    provider = _FakeProvider()
    provider.count_tokens = fake_count  # type: ignore[method-assign]
    cm = ContextManager(provider, ContextConfig(trigger1=0.5, clear_keep=2))
    res = await cm.manage(msgs)
    assert res["layer"] == "L1"
    assert res["before"] == 6000
    assert res["after"] == 2000
    tool_results = [m for m in msgs if m.role == "tool_result"]
    cleared = [m for m in tool_results if m.content.startswith("[cleared")]
    kept = [m for m in tool_results if not m.content.startswith("[cleared")]
    assert len(cleared) == 3
    assert len(kept) == 2


async def test_l4_hard_limit_aborts():
    msgs = _msgs(5)

    async def fake_count(messages, system=None):
        return Usage(input_tokens=9800)  # 恒超 95%（9500）

    provider = _FakeProvider()
    provider.count_tokens = fake_count  # type: ignore[method-assign]
    cm = ContextManager(provider, ContextConfig(clear_keep=2))
    with pytest.raises(ContextLimitError):
        await cm.manage(msgs)


async def test_l2_compaction_replaces_old_history():
    """L1 后仍超 trigger2 → L2 压缩旧历史为摘要 + L3 注入强信号。"""
    msgs = _msgs(6)

    async def fake_count(messages, system=None):
        return Usage(input_tokens=8000)  # > trigger1(5000) 且 > trigger2(7500)，< hard(9500)

    provider = _FakeProvider(summary_text="COMPACTED SUMMARY")
    provider.count_tokens = fake_count  # type: ignore[method-assign]
    cm = ContextManager(
        provider, ContextConfig(trigger1=0.5, trigger2=0.75, compact_recent=2, clear_keep=2)
    )
    res = await cm.manage(msgs)
    assert res["layer"] == "L2"
    assert res["compacted"] is True
    # 第一条被替换为摘要
    assert "[历史摘要]" in (msgs[0].content or "")
    assert "COMPACTED SUMMARY" in msgs[0].content
    # L3 强信号注入
    assert any("系统提示" in (m.content or "") for m in msgs)
    # 摘要 provider 被调一次
    assert provider.chat_calls == 1


async def test_l2_keeps_tool_use_pairing():
    """L2 压缩后保留段的 tool_use ↔ tool_result 配对完整（无孤立 tool_use）。"""
    msgs = _msgs(6)

    async def fake_count(messages, system=None):
        return Usage(input_tokens=8000)

    provider = _FakeProvider(summary_text="S")
    provider.count_tokens = fake_count  # type: ignore[method-assign]
    cm = ContextManager(provider, ContextConfig(compact_recent=2, clear_keep=2))
    await cm.manage(msgs)
    tu_ids = [tc["id"] for m in msgs if m.tool_calls for tc in m.tool_calls]
    tr_ids = [m.tool_call_id for m in msgs if m.role == "tool_result"]
    assert set(tu_ids) == set(tr_ids), "tool_use/tool_result 配对断裂"


async def test_exclude_tools_protected_from_clearing():
    """exclude_tools 命中的工具 result 不被 L1 清。"""
    msgs = _msgs(5)

    async def fake_count(messages, system=None):
        return Usage(input_tokens=6000)  # > trigger1

    provider = _FakeProvider()
    provider.count_tokens = fake_count  # type: ignore[method-assign]
    cm = ContextManager(provider, ContextConfig(clear_keep=2, exclude_tools=["Read"]))
    res = await cm.manage(msgs)
    # 全部 tool_result 来自 Read，被 exclude 保护 → cleared=0
    assert res["cleared"] == 0


async def test_context_span_noop_without_trace():
    """无 trace 上下文时 manage 正常完成（context span 走 no-op，不报错）。"""
    msgs = _msgs(5)

    async def fake_count(messages, system=None):
        return Usage(input_tokens=6000)

    provider = _FakeProvider()
    provider.count_tokens = fake_count  # type: ignore[method-assign]
    cm = ContextManager(provider, ContextConfig(clear_keep=2))
    res = await cm.manage(msgs)
    assert res["layer"] == "L1"
