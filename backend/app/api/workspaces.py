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
    UserRole,
    Workspace,
    WorkspaceMcp,
    WorkspaceSkill,
)
from app.db.session import async_session_factory, get_db
from app.tasks.runner import task_runner
from app.workspace.fs import create_workspace_skeleton, workspace_root

router = APIRouter(prefix="/workspaces", tags=["workspaces"])


def _ws_out(ws: Workspace, owner_name: str = "") -> WorkspaceOut:
    # P3 D-CE.6: model_config 不回显 api_key_enc，仅返回 has_model_api_key 布尔
    mc = dict(ws.model_config) if ws.model_config else None
    has_key = bool(mc and mc.get("api_key_enc"))
    if mc:
        mc.pop("api_key_enc", None)
    return WorkspaceOut(
        id=ws.id,
        name=ws.name,
        owner_id=ws.owner_id,
        owner_name=owner_name or "",
        context_config=ws.context_config,
        model_cfg=mc,
        has_model_api_key=has_key,
        cwd_repo_id=ws.cwd_repo_id,
    )


@router.get("")
async def list_workspaces(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_user),
):
    if user.role == UserRole.admin.value:
        # admin 看全部 WS（含 p2p 自动建的），join User 取真实 owner_name
        rows = (
            await db.execute(
                select(Workspace, User.username)
                .join(User, User.id == Workspace.owner_id)
                .order_by(Workspace.id)
            )
        ).all()
        items = [_ws_out(ws, owner_name=owner_name) for ws, owner_name in rows]
    else:
        wss = (
            await db.scalars(
                select(Workspace)
                .where(Workspace.owner_id == user.id)
                .order_by(Workspace.id)
            )
        ).all()
        items = [_ws_out(w, owner_name=user.username) for w in wss]
    return {"items": items, "total": len(items)}


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
    if body.model_cfg is not None:
        # P3 D-CE.6: 加密 api_key 后存 DB；空串 = 清除已有 key
        from app.agent.model_config import ModelConfig
        from app.core.security import encrypt_secret

        mc_data = dict(body.model_cfg)
        raw_key = mc_data.pop("api_key", None)
        existing = dict(ws.model_config) if ws.model_config else {}
        if raw_key:
            mc_data["api_key_enc"] = encrypt_secret(raw_key)
        elif "api_key" in body.model_cfg:
            # 显式传空串 → 清除已有 key
            mc_data.pop("api_key_enc", None)
        else:
            # 未传 api_key 字段 → 保留已有加密 key
            if "api_key_enc" in existing:
                mc_data["api_key_enc"] = existing["api_key_enc"]
        ws.model_config = mc_data or None
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
    # 统计关联数据用于前端提示；均有 ondelete=CASCADE，删 WS 时自动级联清理
    chat_count = (
        await db.scalar(
            select(func.count())
            .select_from(FeishuChat)
            .where(FeishuChat.workspace_id == ws.id)
        )
    ) or 0
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

    task = Task(task_type="ws_delete", owner_id=user.id)
    db.add(task)
    await db.commit()
    await db.refresh(task)
    task_runner.submit(task.id, _cascade_delete(ws.id))
    return {
        "task_id": task.id,
        "unbound_chats": chat_count,
        "unbound_skills": skill_count,
        "unbound_mcps": mcp_count,
    }
