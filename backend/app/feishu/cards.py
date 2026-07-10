"""飞书互动卡片渲染器（design D4 / §6.1 / spec F3.1.4）。

构造各类卡片 dict（config / header / elements），供接入层发送 / 增量更新。进度卡片
的流式 token 更新由 ``ProgressThrottler`` 节流（token 阈值，spec F3.1.9 ~200 token），
避免触发飞书卡片更新 QPS 限制。

Plan 确认卡片按钮的 ``value`` 携带 ``action`` + ``run_id``，回调由接入层卡片回调处理。
"""

_DIFF_CAP = 4000  # 卡片单元素长度限制


def _md(text: str) -> dict:
    return {"tag": "lark_md", "content": text}


def _plain(text: str) -> dict:
    return {"tag": "plain_text", "content": text}


def _card(title: str, elements: list, template: str = "blue") -> dict:
    return {
        "config": {"wide_screen_mode": True, "update_multi": True},
        "header": {"title": _plain(title), "template": template},
        "elements": elements,
    }


def build_progress_card(text: str, footer: str | None = None) -> dict:
    elements: list = [{"tag": "div", "text": _md(text or "…")}]
    if footer:
        elements.append({"tag": "note", "elements": [_plain(footer)]})
    return _card("Code Forge", elements, "blue")


def build_queue_card(position: int) -> dict:
    """position<=0 表示抢到锁开始执行。"""
    msg = "▶️ 开始执行" if position <= 0 else f"⏳ 排队中，前面 {position} 个"
    return _card("Run 调度", [{"tag": "div", "text": _md(msg)}], "turquoise")


def build_plan_card(plan_markdown: str, run_id: int) -> dict:
    actions = [
        {
            "tag": "button",
            "text": _plain("✅ 确认执行"),
            "value": {"action": "plan_confirm", "run_id": run_id},
            "type": "primary",
        },
        {
            "tag": "button",
            "text": _plain("❌ 取消"),
            "value": {"action": "plan_cancel", "run_id": run_id},
            "type": "danger",
        },
    ]
    return _card(
        "Plan 确认",
        [{"tag": "div", "text": _md(plan_markdown)}, {"tag": "action", "actions": actions}],
        "purple",
    )


def build_diff_card(diff: str) -> dict:
    body = diff[:_DIFF_CAP]
    return _card("代码改动预览", [{"tag": "div", "text": _md("```\n" + body + "\n```")}], "grey")


def build_tasklist_card(tasks: list[dict]) -> dict:
    lines = [
        ("✅" if t.get("done") else "⬜") + " " + t.get("subject", "")
        for t in tasks
    ]
    return _card("TaskList", [{"tag": "div", "text": _md("\n".join(lines) or "（无）")}], "blue")


class ProgressThrottler:
    """流式 token 节流器：累计达 token 阈值才应更新卡片（F3.1.9）。

    token 粗估 = chars / 4。
    """

    def __init__(self, token_threshold: int = 200) -> None:
        self._token_threshold = token_threshold
        self._buf: list[str] = []
        self._chars = 0

    def append(self, delta: str) -> None:
        self._buf.append(delta)
        self._chars += len(delta)

    def should_flush(self) -> bool:
        return self._chars // 4 >= self._token_threshold

    def flush(self) -> str:
        text = "".join(self._buf)
        self._buf = []
        self._chars = 0
        return text

    @property
    def has_pending(self) -> bool:
        return bool(self._buf)
