"""飞书互动卡片渲染器（design D4 / §6.1 / spec F3.1.4）。

构造各类卡片 dict（config / header / elements），供接入层发送 / 增量更新。进度卡片
的流式 token 更新由 ``ProgressThrottler`` 节流（token 阈值，spec F3.1.9 ~200 token），
避免触发飞书卡片更新 QPS 限制。

正文统一用飞书 ``markdown`` 元素（``{"tag":"markdown","content":...}``），支持代码块 /
列表 / 加粗 / 链接等子集。飞书 markdown 元素 **不支持** GFM 表格（``|`` 语法）、
行内代码（单反引号）和引用（``>`` 语法），因此：
- GFM 表格 → 解析为飞书原生 ``table`` 卡片元素（root level，cells 为纯文本）
- 行内代码 `` `code` `` → 剥离反引号保留内容（markdown 元素和 lark_md 均不支持行内代码）
- ``>`` 引用 → 转为 ``▎`` 视觉前缀（Unicode 左竖线，近似引用效果）
- ``#`` 标题 → 转为加粗

``lark_md`` 仅支持内联富文本（加粗 / 链接 / <at>），无法渲染块级 markdown。

Plan 确认卡片按钮的 ``value`` 携带 ``action`` + ``run_id``，回调由接入层卡片回调处理。
"""

import re

_DIFF_CAP = 4000  # 卡片单元素长度限制

# 飞书 markdown 元素不支持 ATX 标题（# / ## / ###），转成加粗近似
_HEADING_RE = re.compile(r'^#{1,6}\s+(.+)$', re.MULTILINE)
# 飞书 markdown 元素不支持 > 引用，转为 ▎ 视觉前缀
_QUOTE_RE = re.compile(r'^>\s?(.*)$', re.MULTILINE)
# 飞书 markdown / lark_md 不支持行内代码（单反引号），剥离反引号保留内容
_INLINE_CODE_RE = re.compile(r'(?<!`)`([^`\n]+)`(?!`)')
_CODE_FENCE_RE = re.compile(r'```.*?```', re.DOTALL)
# GFM 表格：header 行 + separator 行 + 至少一行数据
_GFM_TABLE_RE = re.compile(
    r'(?:^[ \t]*\|.+\|[ \t]*\n)(?:^[ \t]*\|[\s\-:|]+\|[ \t]*\n)(?:^[ \t]*\|.+\|[ \t]*\n?)+',
    re.MULTILINE,
)
# 结构性行：列表 / 表格 / 分隔线等，这些行之间的单 \n 不需要加倍
_STRUCTURAL_RE = re.compile(r'^\s*(?:[-*+]\s|\d+\.\s|\||---+|===+)', re.MULTILINE)
# 中文句末标点（。！？）后紧跟 CJK 字符 → 自动断句（处理无换行符的连续中文文本）
_CJK_SENTENCE_BREAK_RE = re.compile(r'([。！？])([\u4e00-\u9fff])')


def _split_code_segments(text: str) -> list[tuple[str, bool]]:
    """将文本拆分为 [(segment, is_code)] 列表，代码块标记为 True 原样保留。"""
    out: list[tuple[str, bool]] = []
    pos = 0
    for m in _CODE_FENCE_RE.finditer(text):
        if m.start() > pos:
            out.append((text[pos : m.start()], False))
        out.append((m.group(), True))
        pos = m.end()
    if pos < len(text):
        out.append((text[pos:], False))
    return out


def _ensure_paragraph_breaks(text: str) -> str:
    """确保飞书 markdown 正文换行可读。

    两步处理（顺序重要）：
    1. 已有单 ``\\n`` 的非结构性行之间补空行（段落分隔 ``\\n\\n``）；
       列表 / 表格 / 分隔线等结构性行保持紧凑。
    2. 连续中文文本无换行符时，按句末标点（。！？）后接 CJK 字符的位置自动断句，
       插入单 ``\\n``（换行不空行，避免每句之间浪费空间）。

    先做 step 1 再做 step 2，这样 step 1 不会把 step 2 插入的单 ``\\n`` 再翻倍。
    """
    # Step 1: 已有单 \n 的非结构性行补空行
    lines = text.split('\n')
    out: list[str] = []
    for i, line in enumerate(lines):
        out.append(line)
        if i + 1 < len(lines):
            nxt = lines[i + 1]
            cur_struct = bool(_STRUCTURAL_RE.match(line))
            nxt_struct = bool(_STRUCTURAL_RE.match(nxt))
            if line.strip() and nxt.strip() and not (cur_struct and nxt_struct):
                out.append('')
    text = '\n'.join(out)
    # Step 2: 句末标点 + CJK → 单 \n 断句（换行不空行）
    text = _CJK_SENTENCE_BREAK_RE.sub(r'\1\n\2', text)
    return text


def _normalize_md(text: str) -> str:
    """飞书 markdown 元素不支持 ``#`` 标题、``>`` 引用、行内代码，做转换（跳过代码块）。

    - ``#`` 标题 → ``**加粗**``
    - ``>`` 引用 → ``▎`` 前缀
    - `` `code` `` 行内代码 → 剥离反引号（飞书不支持行内代码渲染）
    - 单 ``\\n`` 扩为 ``\\n\\n`` 确保段落间有空行（飞书 markdown 需双换行才换段）
    """
    out: list[str] = []
    for segment, is_code in _split_code_segments(text):
        if is_code:
            out.append(segment)
        else:
            segment = _HEADING_RE.sub(r'**\1**', segment)
            segment = _QUOTE_RE.sub(r'▎\1', segment)
            segment = _INLINE_CODE_RE.sub(r'\1', segment)
            segment = _ensure_paragraph_breaks(segment)
            out.append(segment)
    return ''.join(out)


def _parse_gfm_table(table_text: str) -> dict:
    """将 GFM markdown 表格转为飞书 ``table`` 卡片元素。

    飞书 table 元素的 ``data_type`` 支持 ``lark_md``（内联格式：加粗 / 链接 / <at>），
    使 cell 内的 ``**bold**`` 等标记正确渲染而非原样显示。
    """
    lines = [l.strip() for l in table_text.strip().split('\n') if l.strip()]

    def _split_row(line: str) -> list[str]:
        parts = line.split('|')
        if parts and parts[0].strip() == '':
            parts = parts[1:]
        if parts and parts[-1].strip() == '':
            parts = parts[:-1]
        return [_INLINE_CODE_RE.sub(r'\1', p.strip()) for p in parts]

    headers = _split_row(lines[0])
    # lines[1] 是 separator（|---|---|），跳过
    rows: list[dict] = []
    for line in lines[2:]:
        cells = _split_row(line)
        row: dict = {}
        for i, cell in enumerate(cells):
            if i < len(headers):
                row[headers[i]] = cell
        rows.append(row)

    columns = [{"name": h, "data_type": "lark_md"} for h in headers]
    return {
        "tag": "table",
        "page_size": min(len(rows), 10),
        "row_height": "low",
        "header_style": {"text_align": "left"},
        "columns": columns,
        "rows": rows,
    }


def _code_ranges(text: str) -> list[tuple[int, int]]:
    """返回代码块的 (start, end) 区间列表。"""
    return [(m.start(), m.end()) for m in _CODE_FENCE_RE.finditer(text)]


def _text_to_elements(text: str) -> list[dict]:
    """将 markdown 文本拆分为飞书卡片元素列表（markdown 块 + table 元素）。

    GFM 表格提取为独立的飞书 ``table`` 元素（须在卡片 root level），其余文本
    经 ``_normalize_md`` 处理后包装为 ``markdown`` 元素。代码块内的表格样文本不受影响。
    """
    elements: list[dict] = []
    pos = 0

    for m in _GFM_TABLE_RE.finditer(text):
        # 跳过代码块内的表格样文本
        if any(cs <= m.start() < ce for cs, ce in _code_ranges(text)):
            continue
        if m.start() > pos:
            pre = text[pos : m.start()].strip()
            if pre:
                elements.append(_md_block(pre))
        elements.append(_parse_gfm_table(m.group()))
        pos = m.end()

    if pos < len(text):
        post = text[pos:].strip()
        if post:
            elements.append(_md_block(post))

    if not elements:
        elements.append(_md_block(text or "…"))
    return elements


def _md_block(text: str) -> dict:
    """正文 markdown 元素（GFM 子集：代码块 / 列表 / 加粗 / 链接等）。"""
    return {"tag": "markdown", "content": _normalize_md(text or "…")}


def _plain(text: str) -> dict:
    return {"tag": "plain_text", "content": text}


def _card(title: str, elements: list, template: str = "blue") -> dict:
    return {
        "config": {"wide_screen_mode": True, "update_multi": True},
        "header": {"title": _plain(title), "template": template},
        "elements": elements,
    }


def build_progress_card(text: str, footer: str | None = None) -> dict:
    elements = _text_to_elements(text)
    if footer:
        elements.append({"tag": "note", "elements": [_plain(footer)]})
    return _card("Code Forge", elements, "blue")


def build_queue_card(position: int) -> dict:
    """position<=0 表示抢到锁开始执行。"""
    msg = "▶️ 开始执行" if position <= 0 else f"⏳ 排队中，前面 {position} 个"
    return _card("Run 调度", [_md_block(msg)], "turquoise")


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
        [_md_block(plan_markdown), {"tag": "action", "actions": actions}],
        "purple",
    )


def build_diff_card(diff: str) -> dict:
    body = diff[:_DIFF_CAP]
    return _card("代码改动预览", [_md_block("```\n" + body + "\n```")], "grey")


def build_tasklist_card(tasks: list[dict]) -> dict:
    lines = [
        ("✅" if t.get("done") else "⬜") + " " + t.get("subject", "")
        for t in tasks
    ]
    return _card("TaskList", [_md_block("\n".join(lines) or "（无）")], "blue")


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
