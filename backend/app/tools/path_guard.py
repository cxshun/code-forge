"""工具路径守卫（design D17 / F3.4.4 / D24 / D19）。

默认所有文件类工具的路径相对 cwd（``repos/{cwd}/`` 子树）解析。越界抛
``PermissionError``，由 registry 回灌 Agent。

**D17 例外：chat memory 子树**（D19 复用 Write/Edit 落盘 memory）：

- 以 ``memory/`` 前缀开头的路径 → 当前 chat 的 ``chats/{feishu_chat_id}/memory/``
  子树（前缀剥离后相对 memory 根解析）。跨 FeishuChat 隔离：memory 根取自
  ``ctx.feishu_chat_id``，A chat 写不到 B chat 的 memory。
- 其余路径 → ``repos/{cwd}/`` 子树（含 repo 级 ``AGENT.md``，已在 repos 内可写）

约定 ``memory/`` 前缀避免与 repo 文件路径歧义（契合 §6.4 ``memory/feedback_*.md``）。
代价：repo 内 ``memory/`` 子目录下的文件不可经工具寻址（罕见，可接受）。
"""

from pathlib import Path

from app.tools.base import ToolContext
from app.workspace.fs import PathEscapeError, resolve_within

_MEMORY_PREFIX = "memory/"


def cwd_root(ctx: ToolContext) -> Path:
    """工具的工作目录根：repos/{cwd} 或 repos/。"""
    repos = Path(ctx.workspaces_root) / str(ctx.ws_id) / "repos"
    return (repos / ctx.cwd) if ctx.cwd else repos


def memory_root(ctx: ToolContext) -> Path | None:
    """当前 chat 的 memory 目录；未绑定 chat（feishu_chat_id 为空）返回 None。

    与 ``cwd_root`` 一致用 ``ctx.workspaces_root``（而非全局 settings），保证测试
    隔离路径与 repo 路径同源。
    """
    if ctx.feishu_chat_id is None:
        return None
    return (
        Path(ctx.workspaces_root)
        / str(ctx.ws_id)
        / "chats"
        / str(ctx.feishu_chat_id)
        / "memory"
    )


def resolve_tool_path(rel: str, ctx: ToolContext) -> Path:
    """把工具相对路径 resolve 到允许区内；越界抛 PermissionError。

    - ``memory/<name>`` → 当前 chat memory 子树（D19）
    - 其余 → ``repos/{cwd}/`` 子树（D17，含 repo 级 AGENT.md）
    """
    # memory/ 前缀 → 当前 chat memory 子树
    if rel.startswith(_MEMORY_PREFIX):
        mem = memory_root(ctx)
        if mem is None:
            raise PermissionError("memory 不可用：当前未绑定 FeishuChat")
        sub = rel[len(_MEMORY_PREFIX) :]
        if not sub or sub in (".", "..") or sub.startswith("../"):
            raise PermissionError(f"invalid memory path: {rel}")
        try:
            return resolve_within(sub, mem)
        except PathEscapeError as e:
            raise PermissionError(f"memory path escapes: {rel}") from e

    # 其余 → repos/{cwd}/ 子树
    root = cwd_root(ctx)
    try:
        return resolve_within(rel, root)
    except PathEscapeError as e:
        raise PermissionError(f"path escapes workspace: {rel}") from e
