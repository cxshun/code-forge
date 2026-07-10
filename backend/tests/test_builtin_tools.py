"""内置只读工具测试（T5.5 验收）。"""

from pathlib import Path

import pytest

from app.tools.base import ToolContext
from app.tools.builtin.glob import GlobTool
from app.tools.builtin.read import ReadTool
from app.tools.registry import ToolRegistry


@pytest.fixture
def ctx(tmp_path: Path) -> ToolContext:
    # 构造 WS repos/{cwd} 目录 + 测试文件
    repo = tmp_path / "1" / "repos" / "myrepo"
    (repo / "src").mkdir(parents=True)
    (repo / "src" / "a.py").write_text("line1\nline2\nimport os\n")
    (repo / "src" / "b.py").write_text("print('hi')\n")
    (repo / "README.md").write_text("# demo\n")
    return ToolContext(ws_id=1, workspaces_root=str(tmp_path), cwd="myrepo")


async def test_read_tool(ctx):
    out = await ReadTool().run({"path": "src/a.py"}, ctx)
    assert "line1" in out and "line2" in out
    assert "import os" in out


async def test_read_not_found(ctx):
    out = await ReadTool().run({"path": "nope.py"}, ctx)
    assert "not found" in out


async def test_read_path_escape_rejected(ctx):
    # 越界到 repos 之外 → PermissionError → registry 回灌
    registry = ToolRegistry().register(ReadTool())
    res = await registry.execute(
        "Read", {"path": "../../etc/passwd"}, ctx
    )
    assert "rejected" in res or "Error" in res


async def test_glob_tool(ctx):
    out = await GlobTool().run({"pattern": "**/*.py"}, ctx)
    assert "src/a.py" in out
    assert "src/b.py" in out
    assert "README.md" not in out


async def test_registry_defs_include_readonly(ctx):
    registry = ToolRegistry().register(ReadTool()).register(GlobTool())
    defs = registry.defs()
    names = {d.name for d in defs}
    assert names == {"Read", "Glob"}
    assert registry.is_readonly("Read")
