"""工具注册表（design §5）。

注册工具实例、暴露 ToolDef 列表给 Provider、按 name 执行。执行分类（只读/写）供
Loop 编排并发（F3.4.6：只读 asyncio.gather 并发，写串行）。
"""

import json
import logging

from app.providers.base import ToolDef
from app.tools.base import Tool, ToolContext

log = logging.getLogger("tools.registry")


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> "ToolRegistry":
        if not tool.name:
            raise ValueError("tool.name is empty")
        self._tools[tool.name] = tool
        return self

    def defs(self) -> list[ToolDef]:
        return [t.to_def() for t in self._tools.values()]

    def names(self) -> list[str]:
        return list(self._tools)

    def sub_registry(self, exclude: set[str] | None = None) -> "ToolRegistry":
        """复制一份，排除指定 name（子代理用：去掉 Agent 防无限递归）。"""
        exclude = exclude or set()
        r = ToolRegistry()
        for name, t in self._tools.items():
            if name not in exclude:
                r.register(t)
        return r

    def is_readonly(self, name: str) -> bool:
        tool = self._tools.get(name)
        return bool(tool and tool.read_only)

    async def execute(self, name: str, raw_input: str | dict, ctx: ToolContext) -> str:
        """执行工具。raw_input 为 JSON 字符串（LLM tool_use.input）或 dict。

        工具异常 / 未知工具不抛——作为 is_error 文本回灌 Agent 自主决策（F3.3.12）。
        """
        tool = self._tools.get(name)
        if tool is None:
            return f"Error: unknown tool '{name}'"

        if isinstance(raw_input, str):
            try:
                input_dict = json.loads(raw_input) if raw_input.strip() else {}
            except json.JSONDecodeError as e:
                return f"Error: invalid tool input JSON: {e}"
        else:
            input_dict = raw_input

        try:
            return await tool.run(input_dict, ctx)
        except PermissionError as e:
            # D17 路径越界：告知 Agent 被拒（F3.4.4）
            log.info("tool %s path rejected: %s", name, e)
            return f"Error: path rejected ({e})"
        except Exception as e:
            log.exception("tool %s failed", name)
            return f"Error executing {name}: {e}"
