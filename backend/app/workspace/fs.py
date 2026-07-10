"""工作空间文件系统工具（目录骨架 + 路径安全校验）。

对齐 design §2.3 目录结构与 D17（WS 内路径安全）。提供：

- 目录骨架创建：``/workspaces/{ws_id}/{repos,chats,logs}``、
  ``/skills/{skill_id}/{resources,scripts}``、FeishuChat 的 memory 目录。
- ``resolve_within``：把用户输入的相对路径 resolve 到 root 下，拒绝 ``..`` 与指向 root
  外的符号链接穿越（D5 软隔离的落点）。
"""

from pathlib import Path

from app.config import settings


class PathEscapeError(PermissionError):
    """路径越界（D17）。工具调用路径必须落在 WS 子树内。"""


def workspace_root(ws_id: int) -> Path:
    return Path(settings.workspaces_root) / str(ws_id)


def skill_dir(skill_id: int) -> Path:
    return Path(settings.skills_root) / str(skill_id)


def resolve_within(child: str | Path, root: str | Path) -> Path:
    """把 ``child`` resolve 到 ``root`` 下。

    - 绝对路径输入：直接 resolve（仍须落在 root 内）
    - 相对路径输入：相对 root 拼接后 resolve
    - resolve 会跟随符号链接，故指向 root 外的 symlink 也会被拒
    - resolved 必须等于 root 或位于 root 下，否则抛 PathEscapeError
    """
    root_path = Path(root).resolve()
    child_path = Path(child)
    candidate = child_path if child_path.is_absolute() else root_path / child_path
    resolved = candidate.resolve()
    if resolved != root_path and root_path not in resolved.parents:
        raise PathEscapeError(f"path escapes root {root_path}: {child!r}")
    return resolved


def create_workspace_skeleton(ws_id: int) -> Path:
    """创建 WS 目录骨架 ``{ws}/{repos,chats,logs}``（§2.3）。幂等。"""
    root = workspace_root(ws_id)
    for sub in ("repos", "chats", "logs"):
        (root / sub).mkdir(parents=True, exist_ok=True)
    return root


def create_chat_memory_skeleton(ws_id: int, feishu_chat_id: int) -> Path:
    """创建 FeishuChat 目录 ``{ws}/chats/{feishu_chat_id}/{memory,sessions,traces}``。

    含空 ``MEMORY.md`` 索引（D18 / §2.3，Agent Loop 启动时注入）。幂等。
    """
    chat_dir = workspace_root(ws_id) / "chats" / str(feishu_chat_id)
    for sub in ("memory", "sessions", "traces"):
        (chat_dir / sub).mkdir(parents=True, exist_ok=True)
    memory_index = chat_dir / "memory" / "MEMORY.md"
    if not memory_index.exists():
        memory_index.write_text("", encoding="utf-8")
    return chat_dir / "memory"


def create_skill_skeleton(skill_id: int) -> Path:
    """创建 Skill 目录骨架 ``/skills/{skill_id}/{resources,scripts}``（D15）。幂等。"""
    root = skill_dir(skill_id)
    for sub in ("resources", "scripts"):
        (root / sub).mkdir(parents=True, exist_ok=True)
    return root
