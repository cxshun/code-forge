"""Run 启动期上下文加载（design D24 / D18 / D19 / §6.5）。

后端在 Run 启动时**直接读文件注入 system prompt**（不走 Read 工具，不受 D17 路径
校验约束）：

- **WS 级 AGENT.md**：``{ws_root}/AGENT.md``（整 WS 通用规则，必加载）
- **Repo 级 AGENT.md**：``repos/{cwd 首段}/AGENT.md``（当前 cwd 所在 repo 根目录，
  多 repo 不拼接；cwd 为空则不加载）
- **MEMORY.md 索引**：``chats/{feishu_chat_id}/memory/MEMORY.md``（chat 级长期记忆
  索引，跨 FeishuChat 隔离；详情按需 Read）

文件不存在一律返回空串（不报错）。超长 AGENT.md 告警但不截断（D24 长度保护）。
"""

import logging
from pathlib import Path

from app.workspace.fs import workspace_root

log = logging.getLogger("memory.loader")

# D24 长度保护：单份 AGENT.md 建议 ≤ 2K token（约 6000 字符）。超长告警但不截断。
_AGENT_MD_WARN_CHARS = 6000


def _read_optional(path: Path) -> str:
    """文件存在则读 utf-8 文本，否则返回空串。"""
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def _repo_agent_md_path(ws_root: Path, cwd: str) -> Path | None:
    """Repo 级 AGENT.md 路径 = ``repos/{cwd 首段}/AGENT.md``（D24：repo 根目录）。

    cwd 相对 ``repos/``；取首段定位 repo 根。cwd 为空（无 repo）返回 None。
    """
    if not cwd:
        return None
    first = cwd.split("/", 1)[0]
    if not first or first in (".", ".."):
        return None
    return ws_root / "repos" / first / "AGENT.md"


def load_context_injections(
    ws_id: int, feishu_chat_id: int, cwd: str = ""
) -> tuple[str, str, str]:
    """返回 (ws_agent_md, repo_agent_md, memory_index)，缺失为空串。

    - 跨 FeishuChat 隔离：memory 索引按 ``feishu_chat_id`` 定位，A chat 读不到 B chat
    - Repo 级仅取 cwd 所在 repo 那一份（多 repo 不拼接）
    """
    ws_root = workspace_root(ws_id)

    ws_agent_md = _read_optional(ws_root / "AGENT.md")
    if ws_agent_md and len(ws_agent_md) > _AGENT_MD_WARN_CHARS:
        log.warning("WS %d AGENT.md 超长(%d chars)，仍正常加载", ws_id, len(ws_agent_md))

    repo_agent_md = ""
    repo_path = _repo_agent_md_path(ws_root, cwd)
    if repo_path is not None:
        repo_agent_md = _read_optional(repo_path)
        if repo_agent_md and len(repo_agent_md) > _AGENT_MD_WARN_CHARS:
            log.warning(
                "WS %d repo AGENT.md(%s) 超长(%d chars)，仍正常加载",
                ws_id,
                repo_path,
                len(repo_agent_md),
            )

    memory_index = _read_optional(
        ws_root / "chats" / str(feishu_chat_id) / "memory" / "MEMORY.md"
    )

    return ws_agent_md, repo_agent_md, memory_index


__all__ = ["load_context_injections"]
