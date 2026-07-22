"""WS 级上下文管理策略（design D34）。

``Workspace.context_config`` JSONB 字段的 schema 化解析，对齐 design.md:857-865 的
9 个 key。``from_ws`` 容错：``None`` / 空 → 默认值；未知 key 忽略；非法值回退默认。
"""

from pydantic import BaseModel, ConfigDict

# coding 场景默认摘要指令（design D34 L2）
_DEFAULT_COMPACT_INSTRUCTIONS = (
    "你是对话历史压缩器。请把以下对话压缩为结构化摘要，务必保留：代码片段与文件路径、"
    "变量/函数/类名、关键技术决策与理由、当前任务状态与进度、未完成的 todo、"
    "用户明确表达的偏好。丢弃：寒暄/冗余对话、已处理完毕的大段工具输出。"
    "输出一份简洁的 markdown 摘要。"
)


class ContextConfig(BaseModel):
    """D34 上下文管理 WS 级配置（落 ``workspaces.context_config`` JSONB）。

    P3 新增字段：
    - ``summary_budget_pct``：跨 session 摘要占 context_window 的预算百分比（D-CE.1）
    - ``compact_recursive``：L2 是否启用递归分段摘要（D-CE.2）
    """

    model_config = ConfigDict(extra="ignore")

    enabled: bool = True
    trigger1: float = 0.5  # L1 clearing 阈值（context_window 百分比）
    trigger2: float = 0.75  # L2 compaction 阈值
    clear_keep: int = 6  # L1 保留最近 N 个 tool_result 不清
    compact_recent: int = 6  # L2 保留最近 M 轮原文不压
    summary_provider: str = "anthropic"  # "anthropic" | "openai_compatible"
    summary_model: str | None = None  # 留空用 provider 默认
    compact_instructions: str = _DEFAULT_COMPACT_INSTRUCTIONS
    exclude_tools: list[str] = []  # L1 不清的工具 result（按工具名）
    # P3 D-CE.1: 跨 session 摘要预算（占 context_window 百分比）
    summary_budget_pct: float = 0.25
    # P3 D-CE.2: L2 递归分段摘要开关（False 回退 MVP 单次摘要行为）
    compact_recursive: bool = True

    @classmethod
    def from_ws(cls, data: dict | None) -> "ContextConfig":
        """从容错解析 WS.context_config（None/空/非法 → 默认；未知 key 忽略）。"""
        if not data:
            return cls()
        try:
            return cls.model_validate(data)
        except Exception:
            return cls()
