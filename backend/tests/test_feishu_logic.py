"""接入层纯逻辑测试（T4.4 路由 / T4.7 引用解析 / D38 去重）。"""

import pytest

from app.core.redis_client import redis as redis_client
from app.db.models import FeishuChat, User, Workspace
from app.db.session import async_session_factory
from app.db.testing import reset_all
from app.feishu.dedup import acquire
from app.feishu.quote import extract_plain_text, parse_message_event
from app.feishu.router import resolve_feishu_chat


@pytest.fixture(autouse=True)
async def _reset():
    await reset_all()
    await redis_client.flushdb()
    yield
    await redis_client.flushdb()


def test_extract_plain_text_strips_at():
    content = '{"text":"<at user_id=\\"ou_bot\\">bot</at> hello"}'
    assert extract_plain_text(content, "text") == "hello"


def test_parse_at_bot_and_parent():
    data = {
        "header": {"app_id": "cli_a", "event_type": "im.message.receive_v1"},
        "event": {
            "sender": {"sender_id": {"open_id": "ou_user"}},
            "message": {
                "message_id": "om_1",
                "chat_id": "oc_1",
                "chat_type": "group",
                "message_type": "text",
                "content": '{"text":"<at user_id=\\"ou_bot\\">bot</at> do it"}',
                "parent_id": "om_0",
                "mentions": [{"id": {"open_id": "ou_bot"}}],
            },
        },
    }
    ctx = parse_message_event(data, bot_open_id="ou_bot")
    assert ctx is not None
    assert ctx.at_bot is True
    assert ctx.parent_id == "om_0"
    assert ctx.text == "do it"
    assert ctx.sender_open_id == "ou_user"


def test_parse_only_quote_without_at_not_triggered():
    # 只引用不 @ → at_bot False（D39：引用 + @ 才触发）
    data = {
        "header": {"app_id": "cli_a"},
        "event": {
            "sender": {"sender_id": {"open_id": "ou_user"}},
            "message": {
                "message_id": "om_1",
                "chat_id": "oc_1",
                "message_type": "text",
                "content": '{"text":"see this"}',
                "parent_id": "om_0",
            },
        },
    }
    ctx = parse_message_event(data, bot_open_id="ou_bot")
    assert ctx.at_bot is False
    assert ctx.parent_id == "om_0"


async def test_dedup_first_then_duplicate():
    assert await acquire(redis_client, "om_x") is True
    assert await acquire(redis_client, "om_x") is False


async def test_router_resolve_bound_and_unbound():
    async with async_session_factory() as s:
        admin = User(username="a", password_hash="x", role="admin")
        s.add(admin)
        await s.commit()
        await s.refresh(admin)
        ws = Workspace(name="w", owner_id=admin.id)
        s.add(ws)
        await s.commit()
        await s.refresh(ws)
        s.add(
            FeishuChat(
                workspace_id=ws.id, app_id="cli_a", chat_id="oc_1", chat_name="g"
            )
        )
        await s.commit()
        ws_id = ws.id

    async with async_session_factory() as s:
        found = await resolve_feishu_chat(s, "cli_a", "oc_1")
        assert found is not None
        assert found.workspace_id == ws_id
        # 未绑定 chat
        assert await resolve_feishu_chat(s, "cli_a", "oc_unknown") is None
