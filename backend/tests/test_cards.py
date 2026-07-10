"""富卡片渲染器测试（T4.6 验收）。"""

from app.feishu.cards import (
    ProgressThrottler,
    build_diff_card,
    build_plan_card,
    build_progress_card,
    build_queue_card,
    build_tasklist_card,
)


def test_progress_card_structure():
    card = build_progress_card("thinking…", footer="v0.1")
    assert card["header"]["template"] == "blue"
    assert card["elements"][0]["text"]["content"] == "thinking…"
    assert card["elements"][1]["tag"] == "note"


def test_queue_card_messages():
    assert "排队中" in build_queue_card(2)["elements"][0]["text"]["content"]
    assert "开始执行" in build_queue_card(0)["elements"][0]["text"]["content"]


def test_plan_card_has_action_buttons_with_run_id():
    card = build_plan_card("- step1", run_id=7)
    action = next(e for e in card["elements"] if e.get("tag") == "action")
    values = [a["value"] for a in action["actions"]]
    assert {"action": "plan_confirm", "run_id": 7} in values
    assert {"action": "plan_cancel", "run_id": 7} in values


def test_diff_card_caps_length():
    big = "+" * 10000
    card = build_diff_card(big)
    body = card["elements"][0]["text"]["content"]
    assert len(body) < 4100  # 含代码围栏


def test_tasklist_card():
    card = build_tasklist_card(
        [{"subject": "a", "done": False}, {"subject": "b", "done": True}]
    )
    content = card["elements"][0]["text"]["content"]
    assert "⬜ a" in content
    assert "✅ b" in content


def test_throttler_accumulate_and_flush():
    th = ProgressThrottler(token_threshold=200)
    for _ in range(50):
        th.append("abcdefgh")  # 8 chars × 50 = 400 chars ≈ 100 tokens
    assert not th.should_flush()
    th.append("x" * 400)  # 再 +400 chars → ~200 tokens
    assert th.should_flush()
    flushed = th.flush()
    assert "abcdefgh" in flushed
    assert not th.has_pending
