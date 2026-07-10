"""Git clone / pull（D6），asyncio subprocess。

- token 注入 https url 的 userinfo（``x-access-token:token@host``），明文 token 不落
  DB（DB 存加密）、不入日志（命令行参数含 token 但不 log，对齐 NF4.2.4 软隔离）
- clone 到 ``repos/{repo_id}/``，状态机 pending→cloning→ready/failed 落 GitRepo 表
"""

import asyncio
import os
from urllib.parse import urlparse, urlunparse

from sqlalchemy import update

from app.db.models import CloneStatus, GitRepo
from app.db.session import async_session_factory
from app.workspace.fs import workspace_root

_GIT_ENV = {"GIT_TERMINAL_PROMPT": "0", "GIT_LFS_SKIP_SMUDGE": "1"}


def inject_token(url: str, token: str) -> str:
    """把 token 注入 https/http url 的 userinfo；非 http(s) 原样返回。"""
    p = urlparse(url)
    if p.scheme not in ("http", "https") or not p.hostname:
        return url
    netloc = f"x-access-token:{token}@{p.hostname}"
    if p.port:
        netloc += f":{p.port}"
    return urlunparse(p._replace(netloc=netloc))


async def _update_repo(repo_id: int, **fields: object) -> None:
    async with async_session_factory() as s:
        await s.execute(update(GitRepo).where(GitRepo.id == repo_id).values(**fields))
        await s.commit()


async def clone_repo(
    repo_id: int, url: str, token: str | None, ws_id: int
) -> dict:
    target = workspace_root(ws_id) / "repos" / str(repo_id)
    target.parent.mkdir(parents=True, exist_ok=True)
    await _update_repo(
        repo_id,
        clone_status=CloneStatus.cloning.value,
        local_path=f"repos/{repo_id}",
    )
    clone_url = inject_token(url, token) if token else url
    env = {**os.environ, **_GIT_ENV}
    proc = await asyncio.create_subprocess_exec(
        "git",
        "clone",
        "--depth",
        "1",
        clone_url,
        str(target),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=env,
    )
    _, stderr = await proc.communicate()
    if proc.returncode != 0:
        msg = stderr.decode("utf-8", "replace")[:1000]
        await _update_repo(
            repo_id, clone_status=CloneStatus.failed.value, last_error=msg
        )
        raise RuntimeError(msg[:500])
    await _update_repo(repo_id, clone_status=CloneStatus.ready.value, last_error=None)
    return {"repo_id": repo_id, "path": str(target)}


async def sync_repo(repo_id: int) -> dict:
    async with async_session_factory() as s:
        repo = await s.get(GitRepo, repo_id)
        if repo is None:
            raise RuntimeError(f"repo {repo_id} not found")
        # sync（MVP）复用已 clone 的 origin 凭证，不重注入 token
        ws_id = repo.workspace_id
    target = workspace_root(ws_id) / "repos" / str(repo_id)
    env = {**os.environ, **_GIT_ENV}
    proc = await asyncio.create_subprocess_exec(
        "git",
        "-C",
        str(target),
        "pull",
        "--ff-only",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=env,
    )
    _, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(stderr.decode("utf-8", "replace")[:500])
    return {"repo_id": repo_id}
