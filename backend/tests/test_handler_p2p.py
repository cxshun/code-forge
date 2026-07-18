"""P2 direct-chat 单聊触发测试（DC-T4）。

覆盖 router.auto_bind_p2p_chat 单元路径 + handler.handle_message 的 p2p 分支：
自动绑定、默认 WS 校验、IntegrityError 降级、表情 ack 复用。群聊回归保护由
test_handler.py 既有用例覆盖。
"""

import json

import pytest
from sqlalchemy.exc import IntegrityError

from app.config import settings
from app.core.redis_client import redis as redis_client
from app.core.security import hash_password
from app.db.models import FeishuChat, GitRepo, User, Workspace
from app.db.session import async_session_factory
from app.db.testing import reset_all
from app.feishu import handler as handler_module
from app.feishu.router import auto_bind_p2p_chat, resolve_feishu_chat

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
async def _isolated(tmp_path_factory, monkeypatch):
    monkeypatch.setattr(settings, "data_dir", str(tmp_path_factory.mktemp("cf_data")))
    monkeypatch.setattr(settings, "anthropic_api_key", "sk-test")
    monkeypatch.setattr(settings, "default_p2p_workspace_id", None)
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
        return None

    async def add_reaction(self, message_id, emoji_type="OnIt"):
        rid = f"r_{len(self.added_reactions) + 1}"
        self.added_reactions.append((message_id, emoji_type))
        return rid

    async def delete_reaction(self, message_id, reaction_id):
        self.deleted_reactions.append((message_id, reaction_id))


async def _seed_workspace() -> int:
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
        return ws.id


def _p2p_event(chat_id="oc_p2p_1", text="hi", sender="ou_userabcdef", message_id="om_p2p_1"):
    return {
        "header": {"app_id": "cli_a"},
        "event": {
            "sender": {"sender_id": {"open_id": sender}},
            "message": {
                "chat_id": chat_id,
                "message_id": message_id,
                "message_type": "text",
                "chat_type": "p2p",
                "content": json.dumps({"text": text}),
            },
        },
    }


# --------------------------------------------------------------------------- #
# auto_bind_p2p_chat 单元测试
# --------------------------------------------------------------------------- #


async def test_auto_bind_returns_none_when_default_ws_not_configured():
    ws_id = await _seed_workspace()
    async with async_session_factory() as db:
        chat = await auto_bind_p2p_chat(db, "cli_a", "oc_p2p_x", "ou_user1", None)
    assert chat is None


async def test_auto_bind_returns_none_when_default_ws_deleted():
    ws_id = await _seed_workspace()
    async with async_session_factory() as db:
        chat = await auto_bind_p2p_chat(db, "cli_a", "oc_p2p_x", "ou_user1", ws_id + 999)
    assert chat is None


async def test_auto_bind_creates_chat_with_sender_suffix():
    ws_id = await _seed_workspace()
    async with async_session_factory() as db:
        chat = await auto_bind_p2p_chat(db, "cli_a", "oc_p2p_x", "ou_userabcdef", ws_id)
        assert chat is not None
        assert chat.workspace_id == ws_id
        assert chat.chat_name == "p2p:erabcdef"
    # 持久化可回查
    async with async_session_factory() as db:
        again = await resolve_feishu_chat(db, "cli_a", "oc_p2p_x")
        assert again is not None
        assert again.id == chat.id


async def test_auto_bind_integrity_error_falls_back_to_resolve():
    ws_id = await _seed_workspace()
    # 预占唯一键 → 后续 INSERT 触发 IntegrityError
    async with async_session_factory() as db:
        existing = FeishuChat(
            app_id="cli_a", chat_id="oc_p2p_x", workspace_id=ws_id, chat_name="manual"
        )
        db.add(existing)
        await db.commit()

    async with async_session_factory() as db:
        chat = await auto_bind_p2p_chat(db, "cli_a", "oc_p2p_x", "ou_userabcdef", ws_id)
        # 降级回查 → 返回既有记录（而非 None / 抛异常）
        assert chat is not None
        assert chat.id == existing.id
        assert chat.chat_name == "manual"  # 未覆盖既有命名


async def test_auto_bind_without_sender_uses_null_chat_name():
    ws_id = await _seed_workspace()
    async with async_session_factory() as db:
        chat = await auto_bind_p2p_chat(db, "cli_a", "oc_p2p_x", "", ws_id)
        assert chat is not None
        assert chat.chat_name is None


# --------------------------------------------------------------------------- #
# handler.handle_message p2p 分支集成
# --------------------------------------------------------------------------- #


async def _patch_submit_capture(monkeypatch) -> dict:
    captured = {}

    async def fake_submit(**kw):
        captured.update(kw)
        # 触发 on_done 回调链（模拟 Run 立即成功完成）以验证 reaction 清理
        await kw["on_done"](None)
        return 42

    monkeypatch.setattr(handler_module.run_queue, "submit", fake_submit)
    return captured


async def test_handle_p2p_bound_chat_submits_run(monkeypatch):
    ws_id = await _seed_workspace()
    async with async_session_factory() as db:
        db.add(
            FeishuChat(
                app_id="cli_a", chat_id="oc_p2p_1", workspace_id=ws_id, chat_name="manual"
            )
        )
        await db.commit()

    fake_client = _FakeClient()
    monkeypatch.setattr(handler_module, "FeishuClient", lambda *a, **k: fake_client)
    captured = await _patch_submit_capture(monkeypatch)

    await handler_module.handle_message(_p2p_event(), "cli_a", "secret", "ou_bot")

    assert captured["ws_id"] == ws_id
    assert "hi" in captured["user_message"]
    assert captured["trigger_message_id"] == "om_p2p_1"


async def test_handle_p2p_unbound_auto_binds_to_default_ws(monkeypatch):
    ws_id = await _seed_workspace()
    monkeypatch.setattr(settings, "default_p2p_workspace_id", ws_id)

    fake_client = _FakeClient()
    monkeypatch.setattr(handler_module, "FeishuClient", lambda *a, **k: fake_client)
    captured = await _patch_submit_capture(monkeypatch)

    await handler_module.handle_message(_p2p_event(), "cli_a", "secret", "ou_bot")

    # 自动建 FeishuChat 并提交到默认 WS
    assert captured["ws_id"] == ws_id
    async with async_session_factory() as db:
        chat = await resolve_feishu_chat(db, "cli_a", "oc_p2p_1")
        assert chat is not None
        assert chat.workspace_id == ws_id
        assert chat.chat_name == "p2p:erabcdef"


async def test_handle_p2p_unbound_default_ws_deleted_ignored(monkeypatch):
    ws_id = await _seed_workspace()
    monkeypatch.setattr(settings, "default_p2p_workspace_id", ws_id + 999)

    fake_client = _FakeClient()
    monkeypatch.setattr(handler_module, "FeishuClient", lambda *a, **k: fake_client)
    submitted = False

    async def fake_submit(**kw):
        nonlocal submitted
        submitted = True

    monkeypatch.setattr(handler_module.run_queue, "submit", fake_submit)

    await handler_module.handle_message(_p2p_event(), "cli_a", "secret", "ou_bot")

    assert not submitted
    # 未建 FeishuChat 记录
    async with async_session_factory() as db:
        assert await resolve_feishu_chat(db, "cli_a", "oc_p2p_1") is None


async def test_handle_p2p_reaction_ack_and_cleanup_on_done(monkeypatch):
    ws_id = await _seed_workspace()
    monkeypatch.setattr(settings, "default_p2p_workspace_id", ws_id)

    fake_client = _FakeClient()
    monkeypatch.setattr(handler_module, "FeishuClient", lambda *a, **k: fake_client)
    await _patch_submit_capture(monkeypatch)

    await handler_module.handle_message(_p2p_event(), "cli_a", "secret", "ou_bot")

    # 入口添加表情
    assert ("om_p2p_1", "OnIt") in fake_client.added_reactions
    # on_done 触发后表情被移除
    assert any(msg_id == "om_p2p_1" for msg_id, _ in fake_client.deleted_reactions)


async def test_handle_unknown_chat_type_ignored(monkeypatch):
    await _seed_workspace()
    fake_client = _FakeClient()
    monkeypatch.setattr(handler_module, "FeishuClient", lambda *a, **k: fake_client)
    submitted = False

    async def fake_submit(**kw):
        nonlocal submitted
        submitted = True

    monkeypatch.setattr(handler_module.run_queue, "submit", fake_submit)

    evt = _p2p_event()
    evt["event"]["message"]["chat_type"] = "unknown_type"
    await handler_module.handle_message(evt, "cli_a", "secret", "ou_bot")
    assert not submitted
