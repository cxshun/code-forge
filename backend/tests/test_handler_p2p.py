"""P2 direct-chat 单聊触发测试（DC-T4 初版 / DC-T8 演进改写）。

覆盖 router.auto_bind_p2p_chat 单元路径 + handler.handle_message 的 p2p 分支：
按用户自动建 WS（D-DC.7）、owner 校验、IntegrityError 降级、表情 ack 复用。
群聊回归保护由 test_handler.py 既有用例覆盖。
"""

import json

import pytest
from sqlalchemy import func, select

from app.config import settings
from app.core.redis_client import redis as redis_client
from app.core.security import hash_password
from app.db.models import FeishuChat, GitRepo, User, UserStatus, Workspace
from app.db.session import async_session_factory
from app.db.testing import reset_all
from app.feishu import handler as handler_module
from app.feishu.router import auto_bind_p2p_chat, resolve_feishu_chat

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
    def __init__(self, user_name: str | None = "测试用户"):
        self.sent: list[dict] = []
        self.updated: list[tuple[str, dict]] = []
        self.added_reactions: list[tuple[str, str]] = []
        self.deleted_reactions: list[tuple[str, str]] = []
        self._user_name = user_name

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

    async def get_user_name(self, open_id):
        return self._user_name

    async def get_chat_member_name(self, chat_id):
        return self._user_name


async def _seed_owner() -> tuple[int, int]:
    """建 owner User + 一个已绑 FeishuChat 的 WS（供冲突测试预占）；返回 (owner_id, ws_id)。"""
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
        return u.id, ws.id


async def _count_workspaces() -> int:
    async with async_session_factory() as db:
        return await db.scalar(select(func.count()).select_from(Workspace))


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


async def test_auto_bind_returns_none_when_owner_not_configured():
    await _seed_owner()
    async with async_session_factory() as db:
        chat = await auto_bind_p2p_chat(db, "cli_a", "oc_p2p_x", "ou_user1", None)
    assert chat is None


async def test_auto_bind_returns_none_when_owner_deleted():
    owner_id, _ = await _seed_owner()
    async with async_session_factory() as db:
        chat = await auto_bind_p2p_chat(db, "cli_a", "oc_p2p_x", "ou_user1", owner_id + 999)
    assert chat is None


async def test_auto_bind_returns_none_when_owner_disabled():
    owner_id, _ = await _seed_owner()
    async with async_session_factory() as s:
        owner = await s.get(User, owner_id)
        owner.status = UserStatus.disabled.value
        await s.commit()
    async with async_session_factory() as db:
        chat = await auto_bind_p2p_chat(db, "cli_a", "oc_p2p_x", "ou_user1", owner_id)
    assert chat is None


async def test_auto_bind_creates_ws_and_chat_with_sender_suffix():
    owner_id, _ = await _seed_owner()
    ws_before = await _count_workspaces()
    async with async_session_factory() as db:
        chat = await auto_bind_p2p_chat(db, "cli_a", "oc_p2p_x", "ou_userabcdef", owner_id)
        assert chat is not None
        assert chat.chat_name == "p2p:erabcdef"
        # 新建 WS 指向 owner，命名含 sender 后 8 位
        ws = await db.get(Workspace, chat.workspace_id)
        assert ws is not None
        assert ws.owner_id == owner_id
        assert ws.name == "p2p:erabcdef"
    ws_after = await _count_workspaces()
    assert ws_after == ws_before + 1
    # 持久化可回查
    async with async_session_factory() as db:
        again = await resolve_feishu_chat(db, "cli_a", "oc_p2p_x")
        assert again is not None
        assert again.id == chat.id


async def test_auto_bind_uses_sender_name_when_provided():
    owner_id, _ = await _seed_owner()
    async with async_session_factory() as db:
        chat = await auto_bind_p2p_chat(
            db, "cli_a", "oc_p2p_x", "ou_userabcdef", owner_id, sender_name="张三"
        )
        assert chat is not None
        assert chat.chat_name == "张三"
        ws = await db.get(Workspace, chat.workspace_id)
        assert ws is not None
        assert ws.name == "张三的私聊"


async def test_auto_bind_integrity_error_falls_back_to_resolve():
    owner_id, ws_id = await _seed_owner()
    ws_before = await _count_workspaces()
    # 预占唯一键 → 后续 INSERT 触发 IntegrityError
    async with async_session_factory() as db:
        existing = FeishuChat(
            app_id="cli_a", chat_id="oc_p2p_x", workspace_id=ws_id, chat_name="manual"
        )
        db.add(existing)
        await db.commit()

    async with async_session_factory() as db:
        chat = await auto_bind_p2p_chat(db, "cli_a", "oc_p2p_x", "ou_userabcdef", owner_id)
        # 降级回查 → 返回既有记录（而非 None / 抛异常）
        assert chat is not None
        assert chat.id == existing.id
        assert chat.chat_name == "manual"  # 未覆盖既有命名
    # 冲突时新建的 WS 一并 rollback，不产生重复 WS
    ws_after = await _count_workspaces()
    assert ws_after == ws_before


async def test_auto_bind_without_sender_uses_anonymous_ws_name():
    owner_id, _ = await _seed_owner()
    async with async_session_factory() as db:
        chat = await auto_bind_p2p_chat(db, "cli_a", "oc_p2p_x", "", owner_id)
        assert chat is not None
        assert chat.chat_name is None
        ws = await db.get(Workspace, chat.workspace_id)
        assert ws.name == "p2p:anonymous"


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
    owner_id, ws_id = await _seed_owner()
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


async def test_handle_p2p_unbound_auto_creates_ws_and_submits(monkeypatch):
    owner_id, _ = await _seed_owner()
    monkeypatch.setattr(settings, "p2p_workspace_owner_id", owner_id)
    ws_before = await _count_workspaces()

    fake_client = _FakeClient(user_name="张三")
    monkeypatch.setattr(handler_module, "FeishuClient", lambda *a, **k: fake_client)
    captured = await _patch_submit_capture(monkeypatch)

    await handler_module.handle_message(_p2p_event(), "cli_a", "secret", "ou_bot")

    # 自动建 WS + FeishuChat 并提交到新 WS
    new_ws_id = captured["ws_id"]
    async with async_session_factory() as db:
        chat = await resolve_feishu_chat(db, "cli_a", "oc_p2p_1")
        assert chat is not None
        assert chat.workspace_id == new_ws_id
        assert chat.chat_name == "张三"
        ws = await db.get(Workspace, new_ws_id)
        assert ws is not None
        assert ws.owner_id == owner_id
        assert ws.name == "张三的私聊"
    ws_after = await _count_workspaces()
    assert ws_after == ws_before + 1


async def test_handle_p2p_unbound_name_lookup_fails_uses_suffix_fallback(monkeypatch):
    owner_id, _ = await _seed_owner()
    monkeypatch.setattr(settings, "p2p_workspace_owner_id", owner_id)

    fake_client = _FakeClient(user_name=None)
    monkeypatch.setattr(handler_module, "FeishuClient", lambda *a, **k: fake_client)
    captured = await _patch_submit_capture(monkeypatch)

    await handler_module.handle_message(_p2p_event(), "cli_a", "secret", "ou_bot")

    new_ws_id = captured["ws_id"]
    async with async_session_factory() as db:
        ws = await db.get(Workspace, new_ws_id)
        assert ws is not None
        # name 拉取失败 → 回退到 p2p:{open_id 后 8 位}
        assert ws.name == "p2p:erabcdef"


async def test_handle_p2p_unbound_owner_not_configured_ignored(monkeypatch):
    await _seed_owner()
    # p2p_workspace_owner_id 保持 None（fixture 默认）

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
    owner_id, _ = await _seed_owner()
    monkeypatch.setattr(settings, "p2p_workspace_owner_id", owner_id)

    fake_client = _FakeClient()
    monkeypatch.setattr(handler_module, "FeishuClient", lambda *a, **k: fake_client)
    await _patch_submit_capture(monkeypatch)

    await handler_module.handle_message(_p2p_event(), "cli_a", "secret", "ou_bot")

    # 入口添加表情
    assert ("om_p2p_1", "OnIt") in fake_client.added_reactions
    # on_done 触发后表情被移除
    assert any(msg_id == "om_p2p_1" for msg_id, _ in fake_client.deleted_reactions)


async def test_handle_unknown_chat_type_ignored(monkeypatch):
    await _seed_owner()
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
