"""工作空间 CRUD（api §4 / D8）。

- GET /workspaces：当前用户的 WS 列表
- POST /workspaces：创建 + 建物理目录骨架（§2.3）
- GET /workspaces/{ws_id}：详情（repos / chats / skills / mcps 概览）
- PATCH /workspaces/{ws_id}：改名 / context_config（D34）
- DELETE /workspaces/{ws_id}：删除前校验已解绑 FeishuChat + 解除广场引用；
  通过后异步级联删 DB（CASCADE）+ 物理目录（202 + task_id）
"""

import shutil

from fastapi import APIRouter, Depends
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import (
    ChatBrief,
    McpBrief,
    RepoBrief,
    SkillBrief,
    WorkspaceCreateIn,
    WorkspaceDetail,
    WorkspaceOut,
    WorkspacePatchIn,
)
from app.core.deps import require_user, require_ws_owner
from app.core.errors import api_error
from app.db.models import (
    MCP,
    FeishuChat,
    GitRepo,
    Skill,
    Task,
    User,
    Workspace,
    WorkspaceMcp,
    WorkspaceSkill,
)
from app.db.session import async_session_factory, get_db
from app.tasks.runner import task_runner
from app.workspace.fs import create_workspace_skeleton, workspace_root

router = APIRouter(prefix="/workspaces", tags=["workspaces"])


def _ws_out(ws: Workspace, owner_name: str = "") -> WorkspaceOut:
    return WorkspaceOut(
        id=ws.id,
        name=ws.name,
        owner_id=ws.owner_id,
        owner_name=owner_name or "",
        context_config=ws.context_config,
        cwd_repo_id=ws.cwd_repo_id,
    )


@router.get("")
async def list_workspaces(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_user),
):
    wss = (
        await db.scalars(
            select(Workspace)
            .where(Workspace.owner_id == user.id)
            .order_by(Workspace.id)
        )
    ).all()
    return {
        "items": [_ws_out(w, owner_name=user.username) for w in wss],
        "total": len(wss),
    }


@router.post("", status_code=201)
async def create_workspace(
    body: WorkspaceCreateIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_user),
):
    ws = Workspace(
        name=body.name, owner_id=user.id, context_config=body.context_config
    )
    db.add(ws)
    await db.commit()
    await db.refresh(ws)
    # 建物理目录骨架（repos / chats / logs）
    create_workspace_skeleton(ws.id)
    return _ws_out(ws, owner_name=user.username)


@router.get("/{ws_id}")
async def get_workspace(
    ws: Workspace = Depends(require_ws_owner),
    db: AsyncSession = Depends(get_db),
):
    owner: User | None = await db.get(User, ws.owner_id)
    owner_name = owner.username if owner else ""
    repos = (
        await db.scalars(select(GitRepo).where(GitRepo.workspace_id == ws.id))
    ).all()
    chats = (
        await db.scalars(select(FeishuChat).where(FeishuChat.workspace_id == ws.id))
    ).all()
    skills = (
        await db.scalars(
            select(Skill)
            .join(WorkspaceSkill, WorkspaceSkill.skill_id == Skill.id)
            .where(WorkspaceSkill.workspace_id == ws.id)
        )
    ).all()
    mcps = (
        await db.scalars(
            select(MCP)
            .join(WorkspaceMcp, WorkspaceMcp.mcp_id == MCP.id)
            .where(WorkspaceMcp.workspace_id == ws.id)
        )
    ).all()
    return WorkspaceDetail(
        **_ws_out(ws, owner_name=owner_name).model_dump(),
        repos=[RepoBrief(id=r.id, url=r.url, clone_status=r.clone_status) for r in repos],
        chats=[ChatBrief(id=c.id, app_id=c.app_id, chat_name=c.chat_name) for c in chats],
        skills=[SkillBrief(id=s.id, name=s.name, description=s.description) for s in skills],
        mcps=[McpBrief(id=m.id, name=m.name, type=m.type) for m in mcps],
    )


@router.patch("/{ws_id}")
async def patch_workspace(
    body: WorkspacePatchIn,
    ws: Workspace = Depends(require_ws_owner),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_user),
):
    if body.name is not None:
        ws.name = body.name
    if body.context_config is not None:
        ws.context_config = body.context_config
    await db.commit()
    await db.refresh(ws)
    return _ws_out(ws, owner_name=user.username)


async def _cascade_delete(ws_id: int) -> dict:
    """异步级联删除：DB（CASCADE 删 repos/chats/sessions/runs/spans）+ 物理目录。"""
    async with async_session_factory() as s:
        await s.execute(delete(Workspace).where(Workspace.id == ws_id))
        await s.commit()
    root = workspace_root(ws_id)
    if root.exists():
        shutil.rmtree(root)
    return {"workspace_id": ws_id}


@router.delete("/{ws_id}", status_code=202)
async def delete_workspace(
    ws: Workspace = Depends(require_ws_owner),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_user),
):
    # 删除前校验：已解绑所有 FeishuChat + 解除广场引用（F3.2.5）
    chat_count = (
        await db.scalar(
            select(func.count())
            .select_from(FeishuChat)
            .where(FeishuChat.workspace_id == ws.id)
        )
    ) or 0
    if chat_count:
        raise api_error(422, f"请先解绑 {chat_count} 个 FeishuChat 再删除")
    skill_count = (
        await db.scalar(
            select(func.count())
            .select_from(WorkspaceSkill)
            .where(WorkspaceSkill.workspace_id == ws.id)
        )
    ) or 0
    mcp_count = (
        await db.scalar(
            select(func.count())
            .select_from(WorkspaceMcp)
            .where(WorkspaceMcp.workspace_id == ws.id)
        )
    ) or 0
    if skill_count or mcp_count:
        raise api_error(422, "请先解除 Skill / MCP 广场引用再删除")

    task = Task(task_type="ws_delete", owner_id=user.id)
    db.add(task)
    await db.commit()
    await db.refresh(task)
    task_runner.submit(task.id, _cascade_delete(ws.id))
    return {"task_id": task.id}
