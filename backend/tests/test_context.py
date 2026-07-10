"""上下文管理测试（T5.10 验收）。"""


import pytest

from app.agent.context import ContextLimitError, ContextManager
from app.providers.base import Message, Provider, Usage

pytestmark = pytest.mark.asyncio


class _FakeProvider(Provider):
    """可控 token 计数的假 Provider（不调 LLM）。"""

    def __init__(self, context_window: int, tokens_map: dict):
        self._window = context_window
        self._tokens_map = tokens_map  # id(messages) -> tokens

    @property
    def context_window(self) -> int:
        return self._window

    async def count_tokens(self, messages, system=None):
        # 返回预设的 tokens（按 messages 对象 id 查），便于测试触发阈值
        return Usage(input_tokens=self._tokens_map.get(id(messages), 0))

    async def chat(self, messages, tools=None, system=None):
        raise NotImplementedError

    async def stream(self, messages, tools=None, system=None):
        raise NotImplementedError
        yield  # type: ignore[unreachable]


def _msgs(n_tool_results: int) -> list[Message]:
    msgs = [Message(role="user", content="q")]
    for i in range(n_tool_results):
        msgs.append(Message(role="assistant", content=f"step{i}", tool_calls=[{"id": f"t{i}", "name": "Read", "input": "{}"}]))
        msgs.append(Message(role="tool_result", tool_call_id=f"t{i}", content="x" * 500))
    return msgs


async def test_no_clearing_below_trigger():
    msgs = _msgs(3)
    provider = _FakeProvider(context_window=10000, tokens_map={id(msgs): 100})
    cm = ContextManager(provider, clear_keep=2)
    res = await cm.manage(msgs)
    assert res["layer"] is None
    # tool_result 未被清
    assert all(m.content != "[cleared; re-call the tool to refetch if needed]" for m in msgs if m.role == "tool_result")


async def test_l1_clearing_old_tool_results():
    msgs = _msgs(5)  # 5 个 tool_result
    # 首次计数超 trigger1（5000），清后计数降低
    provider = _FakeProvider(context_window=10000, tokens_map={})
    # 用副作用：count_tokens 第一次返回 6000，清后返回 2000
    calls = {"n": 0}

    async def fake_count(messages, system=None):
        calls["n"] += 1
        return Usage(input_tokens=6000 if calls["n"] == 1 else 2000)

    provider.count_tokens = fake_count  # type: ignore[method-assign]
    cm = ContextManager(provider, trigger1_pct=0.5, clear_keep=2)
    res = await cm.manage(msgs)
    assert res["layer"] == "L1"
    assert res["before"] == 6000
    assert res["after"] == 2000
    # 保留最后 2 个 tool_result 未清，前 3 个被占位
    tool_results = [m for m in msgs if m.role == "tool_result"]
    cleared = [m for m in tool_results if m.content.startswith("[cleared")]
    kept = [m for m in tool_results if not m.content.startswith("[cleared")]
    assert len(cleared) == 3
    assert len(kept) == 2


async def test_l4_hard_limit_aborts():
    msgs = _msgs(5)
    calls = {"n": 0}

    async def fake_count(messages, system=None):
        calls["n"] += 1
        # 清后仍超 95%（9500）
        return Usage(input_tokens=9800)

    provider = _FakeProvider(context_window=10000, tokens_map={})
    provider.count_tokens = fake_count  # type: ignore[method-assign]
    cm = ContextManager(provider, clear_keep=2)
    with pytest.raises(ContextLimitError):
        await cm.manage(msgs)
