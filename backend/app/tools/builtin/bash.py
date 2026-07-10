"""Bash 工具（D17 cwd 限定 + D35 git 边界 + L0 输出截断）。

- 在 cwd_root 执行命令（工作空间 repos 子树内）
- git 黑名单拦截（写 / 网络 git：commit/push/pull/fetch/merge/reset 等）
- stdout / stderr 各 cap 20K chars（D34 L0 源头节流）
"""

import asyncio
from typing import ClassVar

from app.tools.base import Tool, ToolContext
from app.tools.path_guard import cwd_root

# D35：写 / 网络 git 子命令黑名单（只读 git 允许：status/diff/log/show/branch/blame）
_GIT_BLOCKED = (
    "commit",
    "push",
    "pull",
    "fetch",
    "merge",
    "reset",
    "rebase",
    "cherry-pick",
    "stash",
    "clone",
    "init",
    "remote",
)
_STDOUT_CAP = 20000
_TIMEOUT_S = 120


def _check_git_boundary(command: str) -> str | None:
    """命中 git 写/网络子命令 → 拒绝信息；否则 None。简单文本匹配（MVP 软隔离）。"""
    lowered = command.lower()
    for sub in _GIT_BLOCKED:
        if f"git {sub}" in lowered or f"git  {sub}" in lowered:
            return f"Error: git {sub} is blocked (MVP 不支持改 git 状态，D35)"
    return None


class BashTool(Tool):
    name: ClassVar[str] = "Bash"
    description: ClassVar[str] = (
        "在 cwd 执行 shell 命令（限定工作空间 repos 子树；git 写操作被拦）。"
    )
    input_schema: ClassVar[dict] = {
        "type": "object",
        "properties": {"command": {"type": "string"}},
        "required": ["command"],
    }
    read_only: ClassVar[bool] = False

    async def run(self, input: dict, ctx: ToolContext) -> str:
        command = input["command"]
        blocked = _check_git_boundary(command)
        if blocked:
            return blocked

        cwd = str(cwd_root(ctx))
        try:
            proc = await asyncio.create_subprocess_exec(
                "sh",
                "-c",
                command,
                cwd=cwd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except FileNotFoundError as e:
            return f"Error: cannot spawn shell: {e}"

        try:
            out, err = await asyncio.wait_for(proc.communicate(), timeout=_TIMEOUT_S)
        except TimeoutError:
            proc.kill()
            await proc.wait()
            return f"Error: command timed out after {_TIMEOUT_S}s"

        out_text = out.decode("utf-8", "replace")[:_STDOUT_CAP]
        err_text = err.decode("utf-8", "replace")[:_STDOUT_CAP]
        parts = [f"exit={proc.returncode}"]
        if out_text.strip():
            parts.append(out_text)
        if err_text.strip():
            parts.append(f"[stderr]\n{err_text}")
        return "\n".join(parts)
