"""Edit 工具：精确字符串替换（D17 路径限定）。"""

from typing import ClassVar

from app.tools.base import Tool, ToolContext
from app.tools.path_guard import resolve_tool_path


class EditTool(Tool):
    name: ClassVar[str] = "Edit"
    description: ClassVar[str] = (
        "精确字符串替换（限定工作空间 repos 子树）。old_string 唯一时替换一处；"
        "多处需 replace_all=true。"
    )
    input_schema: ClassVar[dict] = {
        "type": "object",
        "properties": {
            "path": {"type": "string"},
            "old_string": {"type": "string"},
            "new_string": {"type": "string"},
            "replace_all": {"type": "boolean", "description": "替换全部匹配，默认 false"},
        },
        "required": ["path", "old_string", "new_string"],
    }
    read_only: ClassVar[bool] = False

    async def run(self, input: dict, ctx: ToolContext) -> str:
        rel = input["path"]
        path = resolve_tool_path(rel, ctx)
        if not path.is_file():
            return f"Error: file not found: {rel}"
        text = path.read_text(encoding="utf-8", errors="replace")
        old = input["old_string"]
        new = input["new_string"]
        if old not in text:
            return f"Error: old_string not found in {rel}"
        count = text.count(old)
        replace_all = input.get("replace_all", False)
        if count > 1 and not replace_all:
            return f"Error: {count} matches of old_string; set replace_all=true"
        new_text = text.replace(old, new) if replace_all else text.replace(old, new, 1)
        path.write_text(new_text, encoding="utf-8")
        return f"replaced {count if replace_all else 1} occurrence(s) in {rel}"
