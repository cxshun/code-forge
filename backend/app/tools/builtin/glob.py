"""Glob 工具：按模式查找文件（D17 路径限定）。"""

from typing import ClassVar

from app.tools.base import Tool, ToolContext
from app.tools.path_guard import cwd_root

_MAX_MATCHES = 200


class GlobTool(Tool):
    name: ClassVar[str] = "Glob"
    description: ClassVar[str] = "按 glob 模式查找文件（限定工作空间 repos 子树）。"
    input_schema: ClassVar[dict] = {
        "type": "object",
        "properties": {"pattern": {"type": "string", "description": "glob 模式，如 **/*.py"}},
        "required": ["pattern"],
    }
    read_only: ClassVar[bool] = True

    async def run(self, input: dict, ctx: ToolContext) -> str:
        root = cwd_root(ctx)
        pattern = input["pattern"]
        matches = sorted(p for p in root.glob(pattern) if p.is_file())[:_MAX_MATCHES]
        if not matches:
            return "(no matches)"
        return "\n".join(str(p.relative_to(root)) for p in matches)
