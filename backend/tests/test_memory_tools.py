"""Memory 路径白名单测试（T7.3 验收：D19 memory 子树可写 + 跨 chat 隔离）。"""

from pathlib import Path

import pytest

from app.tools.base import ToolContext
from app.tools.builtin.edit import EditTool
from app.tools.builtin.read import ReadTool
from app.tools.builtin.write import WriteTool
from app.tools.path_guard import resolve_tool_path
from app.tools.registry import ToolRegistry


def _ctx(tmp_path: Path, *, feishu_chat_id: int | None = 10) -> ToolContext:
    """构造 WS：repos/{cwd} + chats/{chat}/memory/。"""
    root = tmp_path / "1"
    (root / "repos" / "myrepo").mkdir(parents=True)
    (root / "repos" / "myrepo" / "hello.txt").write_text("world")
    (root / "chats" / "10" / "memory").mkdir(parents=True)
    (root / "chats" / "10" / "memory" / "MEMORY.md").write_text("- [lint](feedback_lint.md)")
    return ToolContext(
        ws_id=1,
        workspaces_root=str(tmp_path),
        cwd="myrepo",
        feishu_chat_id=feishu_chat_id,
    )


def test_memory_prefix_resolves_to_chat_memory(tmp_path: Path):
    ctx = _ctx(tmp_path)
    p = resolve_tool_path("memory/feedback_lint.md", ctx)
    assert p == (tmp_path / "1" / "chats" / "10" / "memory" / "feedback_lint.md").resolve()


def test_memory_root_isolated_per_chat(tmp_path: Path):
    """ctx.feishu_chat_id 决定 memory 根：chat 20 的 memory/ 落 chat 20 目录。"""
    (tmp_path / "1" / "chats" / "20" / "memory").mkdir(parents=True)
    ctx = _ctx(tmp_path, feishu_chat_id=20)
    p = resolve_tool_path("memory/foo.md", ctx)
    assert p == (tmp_path / "1" / "chats" / "20" / "memory" / "foo.md").resolve()
    # 不落到 chat 10
    assert "chats/10" not in str(p)


def test_memory_escape_rejected(tmp_path: Path):
    ctx = _ctx(tmp_path)
    with pytest.raises(PermissionError):
        resolve_tool_path("memory/../../../etc/passwd", ctx)


def test_memory_without_chat_rejected(tmp_path: Path):
    """未绑定 chat（feishu_chat_id=None）→ memory/ 前缀拒绝。"""
    ctx = _ctx(tmp_path, feishu_chat_id=None)
    with pytest.raises(PermissionError):
        resolve_tool_path("memory/foo.md", ctx)


def test_repo_path_still_works(tmp_path: Path):
    """非 memory/ 前缀照旧走 repos/{cwd}/。"""
    ctx = _ctx(tmp_path)
    p = resolve_tool_path("hello.txt", ctx)
    assert p == (tmp_path / "1" / "repos" / "myrepo" / "hello.txt").resolve()


async def test_write_to_memory_via_tool(tmp_path: Path):
    ctx = _ctx(tmp_path)
    registry = ToolRegistry().register(WriteTool()).register(ReadTool())
    res = await registry.execute("Write", {"path": "memory/feedback_lint.md", "content": "用 ruff"}, ctx)
    assert "wrote" in res
    # 落盘到 chat memory 目录
    written = tmp_path / "1" / "chats" / "10" / "memory" / "feedback_lint.md"
    assert written.read_text() == "用 ruff"
    # Read 回来
    out = await registry.execute("Read", {"path": "memory/feedback_lint.md"}, ctx)
    assert "用 ruff" in out


async def test_edit_memory_index(tmp_path: Path):
    """Edit memory/MEMORY.md（追加索引行）。"""
    ctx = _ctx(tmp_path)
    registry = ToolRegistry().register(EditTool())
    res = await registry.execute(
        "Edit",
        {
            "path": "memory/MEMORY.md",
            "old_string": "- [lint](feedback_lint.md)",
            "new_string": "- [lint](feedback_lint.md)\n- [fmt](fmt.md)",
        },
        ctx,
    )
    assert "replaced" in res
    body = (tmp_path / "1" / "chats" / "10" / "memory" / "MEMORY.md").read_text()
    assert "fmt.md" in body


async def test_write_memory_escape_rejected_via_tool(tmp_path: Path):
    ctx = _ctx(tmp_path)
    registry = ToolRegistry().register(WriteTool())
    res = await registry.execute(
        "Write", {"path": "memory/../../etc/passwd", "content": "x"}, ctx
    )
    assert "Error" in res or "rejected" in res or "escape" in res
    assert not (tmp_path / "etc" / "passwd").exists()
