"""Read 工具：读文件内容（D17 路径限定）。"""

from typing import ClassVar

from app.tools.base import Tool, ToolContext
from app.tools.path_guard import resolve_tool_path

_DEFAULT_LIMIT = 2000


class ReadTool(Tool):
    name: ClassVar[str] = "Read"
    description: ClassVar[str] = (
        "读取文件内容（限定工作空间 repos 子树）。可选 offset/limit 分段读取大文件。"
    )
    input_schema: ClassVar[dict] = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "相对 cwd 的文件路径"},
            "offset": {"type": "integer", "description": "起始行（0-based），默认 0"},
            "limit": {"type": "integer", "description": "读取行数，默认 2000"},
        },
        "required": ["path"],
    }
    read_only: ClassVar[bool] = True

    async def run(self, input: dict, ctx: ToolContext) -> str:
        rel = input["path"]
        path = resolve_tool_path(rel, ctx)
        if not path.exists():
            return f"Error: file not found: {rel}"
        if not path.is_file():
            return f"Error: not a file: {rel}"
        text = path.read_text(encoding="utf-8", errors="replace")
        offset = int(input.get("offset", 0))
        limit = int(input.get("limit", _DEFAULT_LIMIT))
        lines = text.splitlines()
        total = len(lines)
        selected = lines[offset : offset + limit]
        body = "\n".join(f"{i + offset + 1}\t{line}" for i, line in enumerate(selected))
        header = f"[{rel}] {total} lines" + (
            f" (showing {offset + 1}-{min(offset + limit, total)})" if total else ""
        )
        return f"{header}\n{body}"
