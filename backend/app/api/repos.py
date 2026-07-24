"""Git Repo 挂载与同步（api §5.1 / D6）。

- GET /workspaces/{ws_id}/repos：列表
- POST /workspaces/{ws_id}/repos：挂载（url + 可选 token）→ 异步 git clone（202）
- GET /workspaces/{ws_id}/repos/{repo_id}：详情（clone 状态 / cwd）
- POST /workspaces/{ws_id}/repos/{repo_id}:sync：重新 git pull（异步 202）
- DELETE /workspaces/{ws_id}/repos/{repo_id}：移除（删目录 + DB）
"""

import logging
import shutil

from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import RepoCreateIn, RepoOut
from app.core.deps import require_user, require_ws_owner
from app.core.errors import api_error
from app.core.security import decrypt_secret, encrypt_secret
from app.db.models import CloneStatus, GitRepo, Task, User, Workspace
from app.db.session import get_db
from app.tasks.runner import task_runner
from app.workspace.fs import workspace_root
from app.workspace.git import clone_repo, sync_repo

router = APIRouter(prefix="/workspaces", tags=["repos"])
log = logging.getLogger("api.repos")


def _repo_out(r: GitRepo) -> RepoOut:
    return RepoOut(
        id=r.id,
        url=r.url,
        clone_status=r.clone_status,
        local_path=r.local_path,
        last_error=r.last_error,
    )


@router.get("/{ws_id}/repos")
async def list_repos(
    ws: Workspace = Depends(require_ws_owner),
    db: AsyncSession = Depends(get_db),
):
    from sqlalchemy import select

    repos = (
        await db.scalars(select(GitRepo).where(GitRepo.workspace_id == ws.id))
    ).all()
    return {"items": [_repo_out(r) for r in repos], "total": len(repos)}


@router.post("/{ws_id}/repos", status_code=202)
async def create_repo(
    body: RepoCreateIn,
    ws: Workspace = Depends(require_ws_owner),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_user),
):
    repo = GitRepo(
        workspace_id=ws.id,
        url=body.url,
        token_enc=encrypt_secret(body.token) if body.token else None,
        clone_status=CloneStatus.pending.value,
    )
    db.add(repo)
    await db.commit()
    await db.refresh(repo)
    task = Task(task_type="git_clone", owner_id=user.id)
    db.add(task)
    await db.commit()
    await db.refresh(task)
    task_runner.submit(task.id, clone_repo(repo.id, body.url, body.token, ws.id))
    log.info("create repo %d: ws=%s task=%d url=%s", repo.id, ws.id, task.id, body.url[:80])
    return {"repo_id": repo.id, "task_id": task.id}


@router.get("/{ws_id}/repos/{repo_id}")
async def get_repo(
    repo_id: int,
    ws: Workspace = Depends(require_ws_owner),
    db: AsyncSession = Depends(get_db),
):
    repo = await db.get(GitRepo, repo_id)
    if repo is None or repo.workspace_id != ws.id:
        raise api_error(404, "Repo 不存在")
    return _repo_out(repo)


@router.post("/{ws_id}/repos/{repo_id}:sync", status_code=202)
async def sync_repo_endpoint(
    repo_id: int,
    ws: Workspace = Depends(require_ws_owner),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_user),
):
    repo = await db.get(GitRepo, repo_id)
    if repo is None or repo.workspace_id != ws.id:
        raise api_error(404, "Repo 不存在")
    task = Task(task_type="git_sync", owner_id=user.id)
    db.add(task)
    await db.commit()
    await db.refresh(task)
    task_runner.submit(task.id, sync_repo(repo.id))
    log.info("sync repo %d: ws=%s task=%d", repo_id, ws.id, task.id)
    return {"task_id": task.id}


@router.post("/{ws_id}/repos/{repo_id}:retry", status_code=202)
async def retry_repo(
    repo_id: int,
    ws: Workspace = Depends(require_ws_owner),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_user),
):
    repo = await db.get(GitRepo, repo_id)
    if repo is None or repo.workspace_id != ws.id:
        raise api_error(404, "Repo 不存在")
    if repo.clone_status not in (CloneStatus.failed.value, CloneStatus.pending.value):
        raise api_error(409, "仅 failed/pending 状态可重试")
    target = workspace_root(ws.id) / "repos" / str(repo_id)
    if target.exists():
        shutil.rmtree(target)
    repo.clone_status = CloneStatus.pending.value
    repo.last_error = None
    await db.commit()
    token = decrypt_secret(repo.token_enc) if repo.token_enc else None
    task = Task(task_type="git_clone", owner_id=user.id)
    db.add(task)
    await db.commit()
    await db.refresh(task)
    task_runner.submit(task.id, clone_repo(repo.id, repo.url, token, ws.id))
    log.info("retry repo %d: ws=%s task=%d", repo_id, ws.id, task.id)
    return {"repo_id": repo.id, "task_id": task.id}


@router.delete("/{ws_id}/repos/{repo_id}", status_code=204)
async def delete_repo(
    repo_id: int,
    ws: Workspace = Depends(require_ws_owner),
    db: AsyncSession = Depends(get_db),
):
    repo = await db.get(GitRepo, repo_id)
    if repo is None or repo.workspace_id != ws.id:
        raise api_error(404, "Repo 不存在")
    target = workspace_root(ws.id) / "repos" / str(repo_id)
    if target.exists():
        shutil.rmtree(target)
    await db.delete(repo)
    await db.commit()
    return Response(status_code=204)
