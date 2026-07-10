"""Grep 工具：ripgrep 搜索文件内容（D17 路径限定）。"""

import asyncio
from typing import ClassVar

from app.tools.base import Tool, ToolContext
from app.tools.path_guard import cwd_root

_MAX_OUTPUT = 20000


class GrepTool(Tool):
    name: ClassVar[str] = "Grep"
    description: ClassVar[str] = (
        "用 ripgrep 搜索文件内容（正则，限定工作空间 repos 子树）。"
    )
    input_schema: ClassVar[dict] = {
        "type": "object",
        "properties": {
            "pattern": {"type": "string", "description": "正则模式"},
            "path": {"type": "string", "description": "相对 cwd 的子目录，默认 cwd 根"},
        },
        "required": ["pattern"],
    }
    read_only: ClassVar[bool] = True

    async def run(self, input: dict, ctx: ToolContext) -> str:
        root = cwd_root(ctx)
        sub = input.get("path")
        search_root = root / sub if sub else root
        if not search_root.exists():
            return f"Error: path not found: {sub}"
        pattern = input["pattern"]
        _ = root  # 保留以备未来相对路径化输出
        proc = await asyncio.create_subprocess_exec(
            "rg",
            "--line-number",
            "--no-heading",
            "--color=never",
            "-S",
            pattern,
            str(search_root),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        out, _err = await proc.communicate()
        text = out.decode("utf-8", "replace")
        if not text.strip():
            return "(no matches)"
        # L0 源头节流（D34）：截断超长输出
        return text[:_MAX_OUTPUT]
