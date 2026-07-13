"""工具基类与执行上下文（design §5 / D17 / D20）。

所有内置工具 / Skill 工具 / MCP 工具实现 ``Tool`` 接口。``read_only`` 标记决定是否
抢 WS 写锁（D20 表）：只读工具不抢锁、可并发；写工具抢锁、串行。
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import ClassVar

from app.providers.base import ToolDef


@dataclass
class ToolContext:
    """工具执行上下文：路径根、cwd、租户标识（D17 路径校验 / D20 锁 key）。"""
    ws_id: int
    workspaces_root: str
    cwd: str = ""
    feishu_chat_id: int | None = None
    # 父 Run 的 system prompt（子代理继承 WS/Repo AGENT.md + MEMORY 索引，design D33）
    system_prompt: str = ""
    # 动态 todos（TaskList 工具用，Run 内）
    todos: list[dict] = field(default_factory=list)


class Tool(ABC):
    """工具接口。子类设 name/description/input_schema/read_only，实现 run。"""
    name: ClassVar[str] = ""
    description: ClassVar[str] = ""
    input_schema: ClassVar[dict] = {}
    read_only: ClassVar[bool] = True  # 默认只读不抢锁（D20）

    @abstractmethod
    async def run(self, input: dict, ctx: ToolContext) -> str:
        """执行工具，返回文本结果（进 tool_result）。出错抛异常由 registry 兜底回灌。"""
        ...

    def to_def(self) -> ToolDef:
        return ToolDef(
            name=self.name,
            description=self.description,
            input_schema=self.input_schema,
        )
