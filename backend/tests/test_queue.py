"""Run 队列 + 取消 / 中断测试（T6.2 / T6.3 验收，design §6.6）。

覆盖状态机：queued → running → completed；queued → cancelled；running → interrupted；
同 WS 并发串行 + 排队位置反馈；锁全路径释放。
"""

import asyncio

import pytest

from app.agent.lock import LOCK_PREFIX
from app.agent.queue import RunQueue
from app.config import settings
from app.core.redis_client import redis as redis_client
from app.db.models import FeishuChat, Run, RunStatus, User, Workspace
from app.db.session import async_session_factory
from app.db.testing import reset_all
from app.providers.mock_provider import MockProvider
from app.tools.base import Tool, ToolContext
from app.tools.registry import ToolRegistry
from app.workspace.fs import create_workspace_skeleton

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
async def _isolated(tmp_path_factory, monkeypatch):
    monkeypatch.setattr(settings, "data_dir", str(tmp_path_factory.mktemp("cf_data")))
    await reset_all()
    await redis_client.flushdb()
    yield
    await redis_client.flushdb()


async def _seed() -> tuple[int, int]:
    async with async_session_factory() as s:
        admin = User(username="a", password_hash="x", role="admin")
        s.add(admin)
        await s.commit()
        await s.refresh(admin)
        ws = Workspace(name="w", owner_id=admin.id)
        s.add(ws)
        await s.commit()
        await s.refresh(ws)
        chat = FeishuChat(
            workspace_id=ws.id, app_id="cli_x", chat_id="oc_x", chat_name="g"
        )
        s.add(chat)
        await s.commit()
        await s.refresh(chat)
        create_workspace_skeleton(ws.id)
        return ws.id, chat.id


async def _run_status(run_id: int) -> str:
    async with async_session_factory() as s:
        r = await s.get(Run, run_id)
        return r.status if r else ""


async def _lock_held(ws_id: int) -> bool:
    return await redis_client.get(f"{LOCK_PREFIX}{ws_id}") is not None


class _BlockingTool(Tool):
    """测试用：进入即 set started，阻塞到 gate 被 set 才返回（模拟长工具）。"""

    name = "Blocking"
    description = "test blocking tool"
    read_only = True

    def __init__(self, started: asyncio.Event, gate: asyncio.Event) -> None:
        self.started = started
        self.gate = gate

    async def run(self, input: dict, ctx: ToolContext) -> str:
        self.started.set()
        await self.gate.wait()
        return "blocked-done"


async def test_submit_runs_immediately_when_idle():
    ws_id, chat_id = await _seed()
    q = RunQueue(redis_client)
    started_seq: list[str] = []
    queue_seen: list[int] = []

    run_id = await q.submit(
        ws_id=ws_id,
        feishu_chat_id=chat_id,
        user_message="hi",
        provider=MockProvider(mock_text="ok"),
        registry=ToolRegistry(),
        on_start=lambda: started_seq.append("start"),
        on_queue=lambda n: queue_seen.append(n),
    )
    await q.join(run_id)

    assert await _run_status(run_id) == RunStatus.completed.value
    assert started_seq == ["start"]  # 立即起跑
    assert queue_seen == []  # 无排队
    assert not await _lock_held(ws_id)


async def test_same_ws_serializes_with_queue_feedback():
    ws_id, chat_id = await _seed()
    q = RunQueue(redis_client)

    started_a = asyncio.Event()
    gate_a = asyncio.Event()
    order: list[str] = []
    b_positions: list[int] = []

    rid_a = await q.submit(
        ws_id=ws_id,
        feishu_chat_id=chat_id,
        user_message="a",
        provider=MockProvider(mock_tool_name="Blocking", mock_text="a-final"),
        registry=ToolRegistry().register(_BlockingTool(started_a, gate_a)),
        on_start=lambda: order.append("a-start"),
        on_queue=lambda n: order.append(f"a-queue-{n}"),
    )
    await started_a.wait()  # A 持锁运行中
    assert q.get_state(rid_a) == "running"
    assert await _lock_held(ws_id)

    rid_b = await q.submit(
        ws_id=ws_id,
        feishu_chat_id=chat_id,
        user_message="b",
        provider=MockProvider(mock_text="b-final"),
        registry=ToolRegistry(),
        on_start=lambda: order.append("b-start"),
        on_queue=lambda n: b_positions.append(n),
    )
    await asyncio.sleep(0.05)  # 让 B 进入 _wait_turn
    assert q.get_state(rid_b) == "queued"
    assert b_positions == [1]  # 前面 1 个
    assert await _lock_held(ws_id)  # 仍被 A 持有

    gate_a.set()  # 释放 A
    await q.join(rid_a)
    await q.join(rid_b)

    assert await _run_status(rid_a) == RunStatus.completed.value
    assert await _run_status(rid_b) == RunStatus.completed.value
    # A 先于 B 起跑；A 无排队反馈
    assert order.index("a-start") < order.index("b-start")
    assert not any(s.startswith("a-queue") for s in order)
    assert not await _lock_held(ws_id)


async def test_cancel_queued():
    ws_id, chat_id = await _seed()
    q = RunQueue(redis_client)

    started_a = asyncio.Event()
    gate_a = asyncio.Event()
    b_started: list[int] = []

    rid_a = await q.submit(
        ws_id=ws_id,
        feishu_chat_id=chat_id,
        user_message="a",
        provider=MockProvider(mock_tool_name="Blocking", mock_text="a-final"),
        registry=ToolRegistry().register(_BlockingTool(started_a, gate_a)),
    )
    await started_a.wait()

    rid_b = await q.submit(
        ws_id=ws_id,
        feishu_chat_id=chat_id,
        user_message="b",
        provider=MockProvider(mock_text="b-final"),
        registry=ToolRegistry(),
        on_start=lambda: b_started.append(1),
    )
    await asyncio.sleep(0.05)
    assert q.get_state(rid_b) == "queued"

    ok = await q.cancel(rid_b)
    assert ok is True
    await q.join(rid_b)  # 等取消处理完成（_drive 写 DB + 出队 + pop）
    assert q.get_state(rid_b) is None

    gate_a.set()
    await q.join(rid_a)

    assert await _run_status(rid_a) == RunStatus.completed.value
    assert await _run_status(rid_b) == RunStatus.cancelled.value
    assert b_started == []  # B 从未起跑
    assert not await _lock_held(ws_id)


async def test_interrupt_running():
    ws_id, chat_id = await _seed()
    q = RunQueue(redis_client)

    started = asyncio.Event()
    gate = asyncio.Event()

    run_id = await q.submit(
        ws_id=ws_id,
        feishu_chat_id=chat_id,
        user_message="x",
        provider=MockProvider(mock_tool_name="Blocking", mock_text="final"),
        registry=ToolRegistry().register(_BlockingTool(started, gate)),
    )
    await started.wait()
    assert q.get_state(run_id) == "running"
    assert await _lock_held(ws_id)

    ok = await q.interrupt(run_id)
    assert ok is True

    gate.set()  # 让工具返回 → 下一轮检查点命中 abort → InterruptedError
    await q.join(run_id)

    assert await _run_status(run_id) == RunStatus.interrupted.value
    assert not await _lock_held(ws_id)


async def test_cancel_only_for_queued_interrupt_only_for_running():
    ws_id, chat_id = await _seed()
    q = RunQueue(redis_client)

    started = asyncio.Event()
    gate = asyncio.Event()
    rid = await q.submit(
        ws_id=ws_id,
        feishu_chat_id=chat_id,
        user_message="x",
        provider=MockProvider(mock_tool_name="Blocking", mock_text="final"),
        registry=ToolRegistry().register(_BlockingTool(started, gate)),
    )
    await started.wait()

    # 运行中：cancel 不适用（返回 False），interrupt 适用
    assert await q.cancel(rid) is False
    assert await q.interrupt(rid) is True

    gate.set()
    await q.join(rid)
    assert await _run_status(rid) == RunStatus.interrupted.value

    # 未知 run_id：两者均 False
    assert await q.cancel(999_999) is False
    assert await q.interrupt(999_999) is False
    assert not await _lock_held(ws_id)
