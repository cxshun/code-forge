"""Git clone / pull（D6），asyncio subprocess。

- token 注入 https url 的 userinfo（``x-access-token:token@host``），明文 token 不落
  DB（DB 存加密）、不入日志（命令行参数含 token 但不 log，对齐 NF4.2.4 软隔离）
- clone 到 ``repos/{repo_id}/``，状态机 pending→cloning→ready/failed 落 GitRepo 表
"""

import asyncio
import logging
import os
import shutil
from urllib.parse import urlparse, urlunparse

from sqlalchemy import update

from app.db.models import CloneStatus, GitRepo
from app.db.session import async_session_factory
from app.workspace.fs import workspace_root

log = logging.getLogger("workspace.git")

_GIT_ENV = {"GIT_TERMINAL_PROMPT": "0", "GIT_LFS_SKIP_SMUDGE": "1"}

_MAX_RETRIES = 3
_RETRY_DELAY = 2.0

_TRANSIENT_MARKERS = (
    "no user exists for uid",
    "connection timed out",
    "connection refused",
)


def inject_token(url: str, token: str) -> str:
    """把 token 注入 https/http url 的 userinfo；非 http(s) 原样返回。"""
    p = urlparse(url)
    if p.scheme not in ("http", "https") or not p.hostname:
        return url
    netloc = f"x-access-token:{token}@{p.hostname}"
    if p.port:
        netloc += f":{p.port}"
    return urlunparse(p._replace(netloc=netloc))


def _build_env() -> dict[str, str]:
    env = {**os.environ, **_GIT_ENV}
    if not env.get("HOME"):
        import pwd
        try:
            env["HOME"] = pwd.getpwuid(os.getuid()).pw_dir
        except KeyError:
            pass
    return env


def _is_transient_error(stderr: str) -> bool:
    lower = stderr.lower()
    return any(m in lower for m in _TRANSIENT_MARKERS)


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
    env = _build_env()
    scheme = urlparse(url).scheme
    log.info("clone repo %d: ws=%s scheme=%s host=%s", repo_id, ws_id, scheme, urlparse(url).hostname)

    last_error = ""
    for attempt in range(1, _MAX_RETRIES + 1):
        if attempt > 1 and target.exists():
            shutil.rmtree(target, ignore_errors=True)
        if attempt > 1:
            log.info("clone repo %d: retry %d/%d", repo_id, attempt, _MAX_RETRIES)
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
        if proc.returncode == 0:
            await _update_repo(
                repo_id, clone_status=CloneStatus.ready.value, last_error=None
            )
            log.info("clone repo %d: success (attempt %d)", repo_id, attempt)
            return {"repo_id": repo_id, "path": str(target)}

        last_error = stderr.decode("utf-8", "replace")[:1000]
        if attempt < _MAX_RETRIES and _is_transient_error(last_error):
            log.warning("clone repo %d: transient error (attempt %d): %s", repo_id, attempt, last_error[:200])
            await asyncio.sleep(_RETRY_DELAY)
            continue
        break

    await _update_repo(
        repo_id, clone_status=CloneStatus.failed.value, last_error=last_error
    )
    log.error("clone repo %d: failed after %d attempts: %s", repo_id, attempt, last_error[:300])
    raise RuntimeError(last_error[:500])


async def sync_repo(repo_id: int) -> dict:
    async with async_session_factory() as s:
        repo = await s.get(GitRepo, repo_id)
        if repo is None:
            raise RuntimeError(f"repo {repo_id} not found")
        # sync（MVP）复用已 clone 的 origin 凭证，不重注入 token
        ws_id = repo.workspace_id
    target = workspace_root(ws_id) / "repos" / str(repo_id)
    env = _build_env()
    log.info("sync repo %d: ws=%s", repo_id, ws_id)
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
        err = stderr.decode("utf-8", "replace")[:500]
        log.error("sync repo %d: failed: %s", repo_id, err[:200])
        raise RuntimeError(err)
    log.info("sync repo %d: success", repo_id)
    return {"repo_id": repo_id}
