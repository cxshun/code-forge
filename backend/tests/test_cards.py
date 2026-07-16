"""富卡片渲染器测试（T4.6 验收）。"""

from app.feishu.cards import (
    ProgressThrottler,
    _normalize_md,
    _parse_gfm_table,
    _text_to_elements,
    build_diff_card,
    build_plan_card,
    build_progress_card,
    build_queue_card,
    build_tasklist_card,
)


def test_progress_card_structure():
    card = build_progress_card("thinking…", footer="v0.1")
    assert card["header"]["template"] == "blue"
    assert card["elements"][0]["tag"] == "markdown"
    assert card["elements"][0]["content"] == "thinking…"
    assert card["elements"][1]["tag"] == "note"


def test_queue_card_messages():
    assert "排队中" in build_queue_card(2)["elements"][0]["content"]
    assert "开始执行" in build_queue_card(0)["elements"][0]["content"]


def test_plan_card_has_action_buttons_with_run_id():
    card = build_plan_card("- step1", run_id=7)
    action = next(e for e in card["elements"] if e.get("tag") == "action")
    values = [a["value"] for a in action["actions"]]
    assert {"action": "plan_confirm", "run_id": 7} in values
    assert {"action": "plan_cancel", "run_id": 7} in values


def test_diff_card_caps_length():
    big = "+" * 10000
    card = build_diff_card(big)
    body = card["elements"][0]["content"]
    assert len(body) < 4100  # 含代码围栏


def test_tasklist_card():
    card = build_tasklist_card(
        [{"subject": "a", "done": False}, {"subject": "b", "done": True}]
    )
    content = card["elements"][0]["content"]
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


def test_gfm_table_parsed_to_feishu_element():
    md = "| Name | Age |\n|------|-----|\n| Alice | 30 |\n| Bob | 25 |"
    tbl = _parse_gfm_table(md)
    assert tbl["tag"] == "table"
    assert tbl["columns"][0] == {"name": "Name", "data_type": "lark_md"}
    assert len(tbl["rows"]) == 2
    assert tbl["rows"][0] == {"Name": "Alice", "Age": "30"}
    assert "header_style" in tbl


def test_text_with_table_splits_into_elements():
    md = "Before table\n\n| A | B |\n|---|---|\n| 1 | 2 |\n\nAfter table"
    elements = _text_to_elements(md)
    assert len(elements) == 3
    assert elements[0]["tag"] == "markdown"
    assert "Before table" in elements[0]["content"]
    assert elements[1]["tag"] == "table"
    assert elements[2]["tag"] == "markdown"
    assert "After table" in elements[2]["content"]


def test_table_inside_code_block_not_parsed():
    md = "```\n| A | B |\n|---|---|\n| 1 | 2 |\n```"
    elements = _text_to_elements(md)
    assert len(elements) == 1
    assert elements[0]["tag"] == "markdown"


def test_blockquote_converted_to_bar_prefix():
    md = "> quoted text\n> second line"
    result = _normalize_md(md)
    assert "▎quoted text" in result
    assert "▎second line" in result
    assert ">" not in result.replace("▎", "")


def test_blockquote_inside_code_block_preserved():
    md = "```\n> not a quote\n```"
    result = _normalize_md(md)
    assert "> not a quote" in result


def test_inline_code_backticks_stripped():
    md = "查 `dragon` namespace 的 `xp-dragon-base-service-boot` 服务"
    result = _normalize_md(md)
    assert "`" not in result
    assert "dragon" in result
    assert "xp-dragon-base-service-boot" in result


def test_inline_code_in_table_cell_stripped():
    md = "| 接口 | 次数 |\n|------|------|\n| `/api/foo` | `100` |"
    tbl = _parse_gfm_table(md)
    assert tbl["rows"][0]["接口"] == "/api/foo"
    assert tbl["rows"][0]["次数"] == "100"


def test_code_fence_not_affected_by_inline_stripping():
    md = "```python\nx = `not inline`\n```"
    result = _normalize_md(md)
    assert "```python" in result
    assert "`not inline`" in result
