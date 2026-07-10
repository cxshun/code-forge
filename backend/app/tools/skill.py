"""Skill 工具（design D15 / D16）。

每个挂载的 Skill 包装为 ``skill__{name}`` 工具：启动时仅注入 name + description 到
system prompt（元信息层）；Agent 调用时读完整 ``SKILL.md`` 作 tool_result（内容层）。
``scripts/`` 走 Bash、``resources/`` 走 Read（依赖层，Agent 自主驱动）。
"""

from pathlib import Path
from typing import ClassVar

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Skill, WorkspaceSkill
from app.tools.base import Tool, ToolContext
from app.workspace.fs import skill_dir


class SkillTool(Tool):
    """skill__{name}：invoke 时返回完整 SKILL.md 内容（D16 阶段 2）。"""

    # 基类类属性占位；实例在 __init__ 覆盖为动态 name
    read_only: ClassVar[bool] = True

    def __init__(self, skill_name: str, description: str, md_path: Path) -> None:
        self.name = f"skill__{skill_name}"
        self.description = description or f"Skill: {skill_name}"
        self.input_schema = {"type": "object", "properties": {}}
        self._md_path = md_path

    async def run(self, input: dict, ctx: ToolContext) -> str:
        if not self._md_path.exists():
            return f"Error: SKILL.md not found at {self._md_path}"
        return self._md_path.read_text(encoding="utf-8", errors="replace")


async def build_skill_tools(db: AsyncSession, ws_id: int) -> list[SkillTool]:
    """查 WS 挂载的 Skills，构造 SkillTool 列表（D16 阶段 1 的 description 注入由 prompt 层）。"""
    skills = (
        await db.scalars(
            select(Skill)
            .join(WorkspaceSkill, WorkspaceSkill.skill_id == Skill.id)
            .where(WorkspaceSkill.workspace_id == ws_id)
        )
    ).all()
    return [
        SkillTool(s.name, s.description, skill_dir(s.id) / "SKILL.md") for s in skills
    ]
