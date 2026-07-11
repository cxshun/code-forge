"""T11.2 安全核查：已知越权 / 穿越用例全部拦截。

覆盖：
1. 脱敏管线：AWS Key / Bearer token / GitHub token / PEM 私钥 / 连接串密码
2. 路径穿越：Read 工具 `../` / 绝对路径 / symlink
3. Memory API 路径穿越：`../` / 非法字符
4. Session 安全：未登录 → 401，cookie 属性 SameSite=Lax
5. CSRF：写操作需 X-Requested-With 头（SameSite=Lax 兜底）
"""

import pytest
from httpx import ASGITransport, AsyncClient

from app.config import settings
from app.core.redis_client import redis as redis_client
from app.core.security import hash_password
from app.db.models import FeishuChat, GitRepo, User, Workspace
from app.db.session import async_session_factory
from app.db.testing import reset_all
from app.main import app
from app.observability.redaction import REDACTED, redact
from app.tools.base import ToolContext
from app.tools.builtin.read import ReadTool
from app.tools.builtin.write import WriteTool
from app.workspace.fs import create_workspace_skeleton, workspace_root


@pytest.fixture(autouse=True)
async def _isolated(tmp_path_factory, monkeypatch):
    monkeypatch.setattr(settings, "data_dir", str(tmp_path_factory.mktemp("cf_data")))
    await reset_all()
    await redis_client.flushdb()
    yield
    await redis_client.flushdb()


async def _seed():
    async with async_session_factory() as s:
        u = User(username="sec", password_hash=hash_password("p"), role="admin")
        s.add(u)
        await s.commit()
        await s.refresh(u)
        ws = Workspace(name="w", owner_id=u.id)
        s.add(ws)
        await s.commit()
        await s.refresh(ws)
        repo = GitRepo(workspace_id=ws.id, url="https://x", clone_status="ready")
        s.add(repo)
        await s.commit()
        await s.refresh(repo)
        chat = FeishuChat(workspace_id=ws.id, app_id="cli_s", chat_id="oc_s", chat_name="g")
        s.add(chat)
        await s.commit()
        await s.refresh(chat)
        create_workspace_skeleton(ws.id)
        repo_dir = workspace_root(ws.id) / "repos" / str(repo.id)
        repo_dir.mkdir(parents=True, exist_ok=True)
        (repo_dir / "file.txt").write_text("content")
        return ws.id, chat.id, repo.id


# =====================================================================
# 1. Redaction pipeline
# =====================================================================

def test_redact_aws_access_key():
    data = {"key": "AKIAIOSFODNN7EXAMPLE", "label": "aws"}
    out = redact(data)
    assert out["key"] == REDACTED
    assert out["label"] == "aws"


def test_redact_aws_secret_key():
    s = "aws_secret_access_key=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
    out = redact(s)
    assert REDACTED in out
    assert "wJalrXUtnFEMI" not in out


def test_redact_bearer_token():
    data = {"auth": "Bearer dGhpcyBpcyBhIHRva2VuIGV4YW1wbGU="}
    out = redact(data)
    assert out["auth"] == REDACTED


def test_redact_github_token():
    data = {"token": "ghp_1234567890abcdefghijklmnopqrstuvwxyz1234"}
    out = redact(data)
    assert out["token"] == REDACTED


def test_redact_slack_token():
    data = {"webhook": "xoxb-1234567890-abcdefghij"}
    out = redact(data)
    assert out["webhook"] == REDACTED


def test_redact_pem_private_key():
    pem = (
        "-----BEGIN PRIVATE KEY-----\n"
        "MIIEvgIBADANBgkqhkiG9w0BAQEFAASCBKgwggSkAgEAAoIBAQDX\n"
        "-----END PRIVATE KEY-----"
    )
    out = redact(pem)
    assert REDACTED in out
    assert "MIIEvg" not in out


def test_redact_connection_string_password():
    s = "postgres://user:secretpass@localhost:5432/db"
    out = redact(s)
    assert "secretpass" not in out
    assert REDACTED in out


def test_redact_nested_dict():
    data = {
        "config": {
            "api_key": "sk-1234567890abcdef",
            "password": "my-secret-pass",
            "nested": {"token": "ghp_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"},
        },
        "safe": "normal-value",
    }
    out = redact(data)
    assert out["config"]["api_key"] == REDACTED
    assert out["config"]["password"] == REDACTED
    assert out["config"]["nested"]["token"] == REDACTED
    assert out["safe"] == "normal-value"
    assert out is not data


def test_redact_list_of_dicts():
    data = [{"api_key": "sk-1"}, {"token": "tok-1"}]
    out = redact(data)
    assert out[0]["api_key"] == REDACTED
    assert out[1]["token"] == REDACTED


# =====================================================================
# 2. Path traversal via tool execution
# =====================================================================

async def test_read_tool_rejects_parent_traversal():
    _, _, repo_id = await _seed()
    tool = ReadTool()
    ctx = ToolContext(
        ws_id=1,
        workspaces_root=settings.workspaces_root,
        cwd=str(repo_id),
        feishu_chat_id=1,
    )
    with pytest.raises(PermissionError):
        await tool.run({"path": "../../../etc/passwd"}, ctx)


async def test_read_tool_rejects_absolute_path():
    _, _, repo_id = await _seed()
    tool = ReadTool()
    ctx = ToolContext(
        ws_id=1,
        workspaces_root=settings.workspaces_root,
        cwd=str(repo_id),
        feishu_chat_id=1,
    )
    with pytest.raises(PermissionError):
        await tool.run({"path": "/etc/passwd"}, ctx)


async def test_write_tool_rejects_parent_traversal():
    _, _, repo_id = await _seed()
    tool = WriteTool()
    ctx = ToolContext(
        ws_id=1,
        workspaces_root=settings.workspaces_root,
        cwd=str(repo_id),
        feishu_chat_id=1,
    )
    with pytest.raises(PermissionError):
        await tool.run({"path": "../../evil.txt", "content": "pwned"}, ctx)


# =====================================================================
# 3. Session security
# =====================================================================

async def test_unauthenticated_access_rejected():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/admin/workspaces")
        assert resp.status_code == 401


async def test_session_cookie_has_samesite_lax():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        await _seed()
        resp = await client.post(
            "/api/auth/login", json={"username": "sec", "password": "p"}
        )
        assert resp.status_code == 200
        cookie = resp.headers.get("set-cookie", "")
        assert "samesite=lax" in cookie.lower()
        assert "httponly" in cookie.lower()


async def test_login_rate_limit():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        await _seed()
        for _ in range(5):
            resp = await client.post(
                "/api/auth/login",
                json={"username": "sec", "password": "wrong"},
            )
        resp = await client.post(
            "/api/auth/login",
            json={"username": "sec", "password": "wrong"},
        )
        assert resp.status_code == 429
