"""工具路径守卫（design D17 / F3.4.4）。

所有文件类工具的路径必须 resolve 后落在当前 WS 的 ``repos/`` 子树内（MVP 单 repo 活动，
cwd = ``repos/{repo_id}``）。越界抛 ``PermissionError``，由 registry 回灌 Agent。
"""

from pathlib import Path

from app.tools.base import ToolContext
from app.workspace.fs import PathEscapeError, resolve_within


def cwd_root(ctx: ToolContext) -> Path:
    """工具的工作目录根：repos/{cwd} 或 repos/。"""
    repos = Path(ctx.workspaces_root) / str(ctx.ws_id) / "repos"
    return (repos / ctx.cwd) if ctx.cwd else repos


def resolve_tool_path(rel: str, ctx: ToolContext) -> Path:
    """把工具相对路径 resolve 到 cwd_root 内；越界抛 PermissionError。"""
    root = cwd_root(ctx)
    try:
        return resolve_within(rel, root)
    except PathEscapeError as e:
        raise PermissionError(f"path escapes workspace: {rel}") from e
