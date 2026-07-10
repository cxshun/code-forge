"""AGENT.md 读写（api §5.4 / D24）。

- GET/PUT /workspaces/{ws_id}/agent-md：WS 级（可读写）
- GET /workspaces/{ws_id}/repos/{repo_id}/agent-md：Repo 级（只读，随 git 同步）；
  PUT 不定义 → FastAPI 自动返回 405

文件不存在返回空内容（200），而非 404。
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import AgentMdIn
from app.core.deps import require_ws_owner
from app.core.errors import api_error
from app.db.models import GitRepo, Workspace
from app.db.session import get_db
from app.workspace.fs import workspace_root

router = APIRouter(prefix="/workspaces", tags=["agent-md"])


@router.get("/{ws_id}/agent-md")
async def get_ws_agent_md(ws: Workspace = Depends(require_ws_owner)):
    path = workspace_root(ws.id) / "AGENT.md"
    return {"content": path.read_text(encoding="utf-8") if path.exists() else ""}


@router.put("/{ws_id}/agent-md")
async def put_ws_agent_md(
    body: AgentMdIn,
    ws: Workspace = Depends(require_ws_owner),
):
    path = workspace_root(ws.id) / "AGENT.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body.content, encoding="utf-8")
    return {"content": body.content}


@router.get("/{ws_id}/repos/{repo_id}/agent-md")
async def get_repo_agent_md(
    repo_id: int,
    ws: Workspace = Depends(require_ws_owner),
    db: AsyncSession = Depends(get_db),
):
    repo = await db.get(GitRepo, repo_id)
    if repo is None or repo.workspace_id != ws.id:
        raise api_error(404, "Repo 不存在")
    path = workspace_root(ws.id) / "repos" / str(repo_id) / "AGENT.md"
    return {"content": path.read_text(encoding="utf-8") if path.exists() else ""}
