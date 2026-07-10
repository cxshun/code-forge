"""Write 工具：写文件（D17 路径限定，D20 写工具 → Run 层持锁内执行）。"""

from typing import ClassVar

from app.tools.base import Tool, ToolContext
from app.tools.path_guard import resolve_tool_path


class WriteTool(Tool):
    name: ClassVar[str] = "Write"
    description: ClassVar[str] = (
        "写入文件（覆盖；限定工作空间 repos 子树）。自动创建父目录。"
    )
    input_schema: ClassVar[dict] = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "相对 cwd 的文件路径"},
            "content": {"type": "string", "description": "文件内容"},
        },
        "required": ["path", "content"],
    }
    read_only: ClassVar[bool] = False

    async def run(self, input: dict, ctx: ToolContext) -> str:
        rel = input["path"]
        path = resolve_tool_path(rel, ctx)
        path.parent.mkdir(parents=True, exist_ok=True)
        content = input["content"]
        path.write_text(content, encoding="utf-8")
        return f"wrote {len(content)} chars to {rel}"
