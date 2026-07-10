"""写工具测试（T5.6 验收）。"""

from pathlib import Path

import pytest

from app.tools.base import ToolContext
from app.tools.builtin.bash import BashTool, _check_git_boundary
from app.tools.builtin.edit import EditTool
from app.tools.builtin.write import WriteTool


@pytest.fixture
def ctx(tmp_path: Path) -> ToolContext:
    (tmp_path / "1" / "repos" / "r").mkdir(parents=True)
    return ToolContext(ws_id=1, workspaces_root=str(tmp_path), cwd="r")


async def test_write_creates_file(ctx, tmp_path):
    await WriteTool().run({"path": "a.txt", "content": "hello"}, ctx)
    assert (tmp_path / "1" / "repos" / "r" / "a.txt").read_text() == "hello"


async def test_write_path_escape_rejected(ctx):
    from app.tools.registry import ToolRegistry

    registry = ToolRegistry().register(WriteTool())
    res = await registry.execute("Write", {"path": "../../evil.txt", "content": "x"}, ctx)
    assert "rejected" in res or "Error" in res


async def test_edit_replace_unique(ctx, tmp_path):
    f = tmp_path / "1" / "repos" / "r" / "b.txt"
    f.write_text("foo bar foo")
    out = await EditTool().run(
        {"path": "b.txt", "old_string": "bar", "new_string": "baz"}, ctx
    )
    assert "replaced 1" in out
    assert f.read_text() == "foo baz foo"


async def test_edit_multiple_requires_replace_all(ctx, tmp_path):
    f = tmp_path / "1" / "repos" / "r" / "c.txt"
    f.write_text("x x x")
    out = await EditTool().run(
        {"path": "c.txt", "old_string": "x", "new_string": "y"}, ctx
    )
    assert "matches" in out
    out2 = await EditTool().run(
        {"path": "c.txt", "old_string": "x", "new_string": "y", "replace_all": True}, ctx
    )
    assert "replaced 3" in out2


def test_git_boundary_blocks_write():
    assert _check_git_boundary("git commit -m x") is not None
    assert _check_git_boundary("git push origin main") is not None


def test_git_boundary_allows_readonly():
    assert _check_git_boundary("git status") is None
    assert _check_git_boundary("git log --oneline") is None


async def test_bash_runs_and_captures(ctx):
    out = await BashTool().run({"command": "echo hello && pwd"}, ctx)
    assert "hello" in out
    assert "/r" in out


async def test_bash_git_commit_blocked(ctx):
    out = await BashTool().run({"command": "git commit -m test"}, ctx)
    assert "blocked" in out
