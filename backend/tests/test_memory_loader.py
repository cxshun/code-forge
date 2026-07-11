"""Memory / AGENT.md 加载注入测试（T7.1 / T7.2 验收）。"""

import pytest

from app.config import settings
from app.db.testing import reset_all
from app.memory.loader import load_context_injections
from app.workspace.fs import (
    create_chat_memory_skeleton,
    create_workspace_skeleton,
    workspace_root,
)

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
async def _isolated(tmp_path_factory, monkeypatch):
    monkeypatch.setattr(settings, "data_dir", str(tmp_path_factory.mktemp("cf_data")))
    await reset_all()
    yield


async def test_load_all_three_present():
    """WS AGENT.md + Repo AGENT.md + MEMORY.md 三份都在 → 全注入。"""
    create_workspace_skeleton(1)
    create_chat_memory_skeleton(1, 10)
    root = workspace_root(1)
    (root / "AGENT.md").write_text("# WS RULES\n用 ruff")
    (root / "repos" / "myrepo").mkdir(parents=True, exist_ok=True)
    (root / "repos" / "myrepo" / "AGENT.md").write_text("# REPO\npytest")
    (root / "chats" / "10" / "memory" / "MEMORY.md").write_text("- [lint](feedback_lint.md)")

    ws_md, repo_md, mem = load_context_injections(1, 10, "myrepo")
    assert "WS RULES" in ws_md
    assert "REPO" in repo_md
    assert "feedback_lint" in mem


async def test_load_missing_all_empty():
    """三份都不存在 → 全空串（不报错）。"""
    create_workspace_skeleton(1)
    ws_md, repo_md, mem = load_context_injections(1, 999, "myrepo")
    assert ws_md == "" and repo_md == "" and mem == ""


async def test_memory_cross_chat_isolation():
    """A chat 的 MEMORY 不被 B chat 读到（D18 跨 FeishuChat 隔离）。"""
    create_workspace_skeleton(1)
    create_chat_memory_skeleton(1, 10)
    create_chat_memory_skeleton(1, 20)
    root = workspace_root(1)
    (root / "chats" / "10" / "memory" / "MEMORY.md").write_text("chat-A-secret")

    _, _, mem_a = load_context_injections(1, 10, "")
    _, _, mem_b = load_context_injections(1, 20, "")
    assert "chat-A-secret" in mem_a
    assert mem_b == ""


async def test_repo_agent_md_uses_cwd_first_component():
    """cwd 嵌套时取首段定位 repo 根 AGENT.md（D24：repo 根目录那一份）。"""
    create_workspace_skeleton(1)
    root = workspace_root(1)
    (root / "repos" / "5").mkdir(parents=True, exist_ok=True)
    (root / "repos" / "5" / "AGENT.md").write_text("repo-root-md")
    (root / "repos" / "5" / "src").mkdir(exist_ok=True)

    _, repo_md, _ = load_context_injections(1, 10, "5/src/sub")
    assert repo_md == "repo-root-md"


async def test_no_repo_no_repo_md():
    """cwd 为空（无 repo）→ repo_agent_md 为空。"""
    create_workspace_skeleton(1)
    (workspace_root(1) / "AGENT.md").write_text("ws")
    ws_md, repo_md, _ = load_context_injections(1, 10, "")
    assert ws_md == "ws"
    assert repo_md == ""
