"""文件系统目录工具与路径安全测试（task T1.3 验收）。"""


import pytest

from app.config import settings
from app.workspace.fs import (
    PathEscapeError,
    create_chat_memory_skeleton,
    create_skill_skeleton,
    create_workspace_skeleton,
    resolve_within,
    workspace_root,
)


@pytest.fixture(autouse=True)
def _tmp_data_dir(tmp_path, monkeypatch):
    """把 settings.data_dir 指向临时目录，隔离测试副作用。"""
    monkeypatch.setattr(settings, "data_dir", str(tmp_path))


def test_resolve_within_ok():
    root = create_workspace_skeleton(1)
    r = resolve_within("repos/a/b.txt", root)
    assert r.is_relative_to(root)


def test_resolve_within_root_itself():
    root = create_workspace_skeleton(1)
    assert resolve_within(".", root) == root.resolve()


def test_resolve_within_reject_dotdot():
    root = create_workspace_skeleton(1)
    with pytest.raises(PathEscapeError):
        resolve_within("../../etc/passwd", root)


def test_resolve_within_reject_symlink_escape(tmp_path):
    root = create_workspace_skeleton(1)
    # 在 root 内建一个 symlink 指向 root 外文件
    outside = tmp_path / "outside_secret.txt"
    outside.write_text("x")
    link = root / "escape_link"
    link.symlink_to(outside)
    with pytest.raises(PathEscapeError):
        resolve_within("escape_link", root)


def test_resolve_within_reject_absolute_outside():
    root = create_workspace_skeleton(1)
    with pytest.raises(PathEscapeError):
        resolve_within("/etc/passwd", root)


def test_create_workspace_skeleton_dirs():
    root = create_workspace_skeleton(42)
    assert root.is_dir()
    for sub in ("repos", "chats", "logs"):
        assert (root / sub).is_dir()


def test_create_chat_memory_skeleton_creates_memory_index():
    create_workspace_skeleton(7)
    memory_dir = create_chat_memory_skeleton(7, 100)
    assert (memory_dir / "MEMORY.md").is_file()
    assert (workspace_root(7) / "chats" / "100" / "sessions").is_dir()
    assert (workspace_root(7) / "chats" / "100" / "traces").is_dir()


def test_create_skill_skeleton():
    d = create_skill_skeleton(5)
    assert d.is_dir()
    assert (d / "resources").is_dir()
    assert (d / "scripts").is_dir()
