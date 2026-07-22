"""飞书 handler → run_queue.submit 端到端接线测试。

monkeypatch run_queue.submit / 工厂 / FeishuClient，断言接入层正确组装并入队 Run，
卡片回调用对象正确传递。不打真实飞书 / Anthropic。
"""

import json

import pytest

from app.config import settings
from app.core.redis_client import redis as redis_client
from app.core.security import hash_password
from app.db.models import FeishuChat, GitRepo, User, Workspace
from app.db.session import async_session_factory
from app.db.testing import reset_all
from app.feishu import handler as handler_module

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
async def _isolated(tmp_path_factory, monkeypatch):
    monkeypatch.setattr(settings, "data_dir", str(tmp_path_factory.mktemp("cf_data")))
    monkeypatch.setattr(settings, "anthropic_api_key", "sk-test")
    monkeypatch.setattr(settings, "p2p_workspace_owner_id", None)
    await reset_all()
    await redis_client.flushdb()
    yield
    await redis_client.flushdb()


class _FakeClient:
    def __init__(self):
        self.sent: list[dict] = []
        self.updated: list[tuple[str, dict]] = []
        self.added_reactions: list[tuple[str, str]] = []
        self.deleted_reactions: list[tuple[str, str]] = []

    async def send_card(self, chat_id, card):
        self.sent.append(card)
        return f"om_card_{len(self.sent)}"

    async def update_card(self, message_id, card):
        self.updated.append((message_id, card))

    async def get_message(self, parent_id):
        return None  # 无引用

    async def add_reaction(self, message_id, emoji_type="OnIt"):
        rid = f"r_{len(self.added_reactions) + 1}"
        self.added_reactions.append((message_id, emoji_type))
        return rid

    async def delete_reaction(self, message_id, reaction_id):
        self.deleted_reactions.append((message_id, reaction_id))

    async def get_user_name(self, open_id):
        return None

    async def get_chat_member_name(self, chat_id):
        return None


async def _seed():
    async with async_session_factory() as s:
        u = User(username="u", password_hash=hash_password("p"), role="admin")
        s.add(u)
        await s.commit()
        await s.refresh(u)
        ws = Workspace(name="w", owner_id=u.id)
        s.add(ws)
        await s.commit()
        await s.refresh(ws)
        repo = GitRepo(workspace_id=ws.id, url="https://x", clone_status="ready")
        s.add(repo)
        await s.commit()
        await s.refresh(repo)
        chat = FeishuChat(
            workspace_id=ws.id, app_id="cli_a", chat_id="oc_group1", chat_name="g"
        )
        s.add(chat)
        await s.commit()
        await s.refresh(chat)
        return ws.id, chat.id, chat.chat_id


def _group_event(chat_id="oc_group1", text="帮我看看代码", parent_id=None, at_bot=True):
    """构造 im.message.receive_v1 群聊事件。"""
    content = json.dumps({"text": f"<at user_id=\"ou_bot\">bot</at> {text}"})
    return {
        "header": {"app_id": "cli_a"},
        "event": {
            "sender": {"sender_id": {"open_id": "ou_sender123"}},
            "message": {
                "chat_id": chat_id,
                "message_id": "om_msg_1",
                "message_type": "text",
                "chat_type": "group",
                "content": content,
                "parent_id": parent_id,
                "mentions": [{"id": {"open_id": "ou_bot"}}] if at_bot else [],
            },
        },
    }


async def test_handle_submits_run_with_callbacks(monkeypatch):
    ws_id, chat_id, _oc_chat = await _seed()
    fake_client = _FakeClient()
    monkeypatch.setattr(handler_module, "FeishuClient", lambda *a, **k: fake_client)

    captured = {}

    async def fake_submit(**kw):
        captured.update(kw)
        return 42

    monkeypatch.setattr(handler_module.run_queue, "submit", fake_submit)

    await handler_module.handle_message(_group_event(), "cli_a", "secret", "ou_bot")

    assert captured["ws_id"] == ws_id
    assert captured["feishu_chat_id"] == chat_id
    assert captured["cwd"]  # repo 存在 → cwd 非空
    assert "帮我看看代码" in captured["user_message"]
    # 回调齐全
    for cb in ("on_text", "on_tool_call", "on_queue", "on_start", "on_done"):
        assert callable(captured[cb])
    assert captured["trigger_message_id"] == "om_msg_1"


async def test_handle_no_anthropic_key_sends_error_card(monkeypatch):
    monkeypatch.setattr(settings, "anthropic_api_key", "")
    # 同时清除 openai_compatible 配置，模拟无任何 LLM Provider 可用的场景
    monkeypatch.setattr(settings, "openai_compatible_api_key", "")
    monkeypatch.setattr(settings, "openai_compatible_base_url", "")
    monkeypatch.setattr(settings, "openai_compatible_model", "")
    await _seed()
    fake_client = _FakeClient()
    monkeypatch.setattr(handler_module, "FeishuClient", lambda *a, **k: fake_client)

    submitted = False

    async def fake_submit(**kw):
        nonlocal submitted
        submitted = True

    monkeypatch.setattr(handler_module.run_queue, "submit", fake_submit)
    await handler_module.handle_message(_group_event(), "cli_a", "secret", "ou_bot")
    assert not submitted
    # 错误卡正文（elements[0].content，markdown 元素）含提示
    texts = [e["elements"][0]["content"] for e in fake_client.sent]
    assert any("LLM Provider" in t for t in texts)


async def test_handle_unbound_chat_no_submit(monkeypatch):
    await _seed()  # 绑定 oc_group1；用 oc_other 触发
    fake_client = _FakeClient()
    monkeypatch.setattr(handler_module, "FeishuClient", lambda *a, **k: fake_client)
    submitted = False

    async def fake_submit(**kw):
        nonlocal submitted
        submitted = True

    monkeypatch.setattr(handler_module.run_queue, "submit", fake_submit)
    await handler_module.handle_message(
        _group_event(chat_id="oc_other"), "cli_a", "secret", "ou_bot"
    )
    assert not submitted


async def test_handle_p2p_without_owner_ignored(monkeypatch):
    """p2p 单聊在未配置 owner 时按未绑定忽略（D-DC.2 / D-DC.3 / D-DC.7）。"""
    await _seed()
    submitted = False
    monkeypatch.setattr(settings, "p2p_workspace_owner_id", None)
    monkeypatch.setattr(handler_module, "FeishuClient", lambda *a, **k: _FakeClient())

    async def fake_submit(**kw):
        nonlocal submitted
        submitted = True

    monkeypatch.setattr(handler_module.run_queue, "submit", fake_submit)
    evt = _group_event(chat_id="oc_p2p_unbound")  # 未绑定 chat
    evt["event"]["message"]["chat_type"] = "p2p"
    await handler_module.handle_message(evt, "cli_a", "secret", "ou_bot")
    assert not submitted


async def test_callbacks_stream_and_finalize(monkeypatch):
    """非流式：on_text 仅累积不更新卡片，on_done 一次性渲染完整正文。"""
    fake_client = _FakeClient()
    monkeypatch.setattr(handler_module, "FeishuClient", lambda *a, **k: fake_client)
    cb = handler_module.FeishuRunCallbacks(fake_client, "oc_g", footer="sender abcd1234")
    await cb.on_start()
    assert fake_client.sent  # thinking 卡片已发

    # 非流式：推送文本不触发卡片更新（避免流式分片导致表格/格式解析异常）
    await cb.on_text("x" * 900)
    assert not fake_client.updated  # on_text 不更新卡片

    await cb.on_text("结尾")
    await cb.on_done(None)  # 成功 finalize：一次性渲染累积正文
    assert fake_client.updated  # on_done 才 update_card
    final_text = fake_client.updated[-1][1]["elements"][0]["content"]
    assert "结尾" in final_text


async def test_callbacks_done_error_shows_failure(monkeypatch):
    fake_client = _FakeClient()
    monkeypatch.setattr(handler_module, "FeishuClient", lambda *a, **k: fake_client)
    cb = handler_module.FeishuRunCallbacks(fake_client, "oc_g", footer=None)
    await cb.on_start()
    await cb.on_done(RuntimeError("boom"))
    final_text = fake_client.updated[-1][1]["elements"][0]["content"]
    assert "执行失败" in final_text and "boom" in final_text
