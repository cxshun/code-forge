"""Skill / MCP 挂载管理（api §5.3 / D11 / F3.2 / T2.4）。

- GET /workspaces/{ws_id}/skills | /mcps：已挂载列表
- POST /workspaces/{ws_id}/skills | /mcps：挂载广场资源（校验可见性 + Skill 上限 50）
- DELETE /workspaces/{ws_id}/skills/{skill_id} | /mcps/{mcp_id}：解挂

挂载私有资源需为该资源 owner（或管理员），否则 403；重复挂载 409；解挂删关联表行。
"""

from fastapi import APIRouter, Depends, Response
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import McpBrief, McpMountIn, SkillBrief, SkillMountIn
from app.core.deps import require_user, require_ws_owner
from app.core.errors import api_error
from app.db.models import (
    MCP,
    Skill,
    User,
    Workspace,
    WorkspaceMcp,
    WorkspaceSkill,
)
from app.db.session import get_db

router = APIRouter(prefix="/workspaces", tags=["mounts"])

MAX_SKILLS_PER_WS = 50  # F3.5.6


def _assert_visible_owner(resource, user: User) -> None:
    """私有资源须为 owner（或管理员），否则 403。"""
    if resource.visibility == "public":
        return
    if resource.owner_id != user.id and user.role != "admin":
        raise api_error(403, "无权挂载私有资源")


# ---------------- Skill ----------------


@router.get("/{ws_id}/skills")
async def list_mounted_skills(
    ws: Workspace = Depends(require_ws_owner),
    db: AsyncSession = Depends(get_db),
):
    skills = (
        await db.scalars(
            select(Skill)
            .join(WorkspaceSkill, WorkspaceSkill.skill_id == Skill.id)
            .where(WorkspaceSkill.workspace_id == ws.id)
            .order_by(Skill.id)
        )
    ).all()
    return {
        "items": [SkillBrief(id=s.id, name=s.name, description=s.description) for s in skills],
        "total": len(skills),
    }


@router.post("/{ws_id}/skills", status_code=201)
async def mount_skill(
    body: SkillMountIn,
    ws: Workspace = Depends(require_ws_owner),
    user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    skill = await db.get(Skill, body.skill_id)
    if skill is None:
        raise api_error(404, "Skill 不存在")
    _assert_visible_owner(skill, user)
    count = (
        await db.scalar(
            select(func.count())
            .select_from(WorkspaceSkill)
            .where(WorkspaceSkill.workspace_id == ws.id)
        )
    ) or 0
    if count >= MAX_SKILLS_PER_WS:
        raise api_error(422, f"单工作空间最多挂载 {MAX_SKILLS_PER_WS} 个 Skill")
    db.add(WorkspaceSkill(workspace_id=ws.id, skill_id=skill.id))
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise api_error(409, "该 Skill 已挂载", "conflict") from None
    return SkillBrief(id=skill.id, name=skill.name, description=skill.description)


@router.delete("/{ws_id}/skills/{skill_id}", status_code=204)
async def unmount_skill(
    skill_id: int,
    ws: Workspace = Depends(require_ws_owner),
    db: AsyncSession = Depends(get_db),
):
    row = await db.get(WorkspaceSkill, (ws.id, skill_id))
    if row is None:
        raise api_error(404, "该 Skill 未挂载")
    await db.delete(row)
    await db.commit()
    return Response(status_code=204)


# ---------------- MCP ----------------


@router.get("/{ws_id}/mcps")
async def list_mounted_mcps(
    ws: Workspace = Depends(require_ws_owner),
    db: AsyncSession = Depends(get_db),
):
    mcps = (
        await db.scalars(
            select(MCP)
            .join(WorkspaceMcp, WorkspaceMcp.mcp_id == MCP.id)
            .where(WorkspaceMcp.workspace_id == ws.id)
            .order_by(MCP.id)
        )
    ).all()
    return {
        "items": [McpBrief(id=m.id, name=m.name, type=m.type) for m in mcps],
        "total": len(mcps),
    }


@router.post("/{ws_id}/mcps", status_code=201)
async def mount_mcp(
    body: McpMountIn,
    ws: Workspace = Depends(require_ws_owner),
    user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    mcp = await db.get(MCP, body.mcp_id)
    if mcp is None:
        raise api_error(404, "MCP 不存在")
    _assert_visible_owner(mcp, user)
    db.add(WorkspaceMcp(workspace_id=ws.id, mcp_id=mcp.id))
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise api_error(409, "该 MCP 已挂载", "conflict") from None
    return McpBrief(id=mcp.id, name=mcp.name, type=mcp.type)


@router.delete("/{ws_id}/mcps/{mcp_id}", status_code=204)
async def unmount_mcp(
    mcp_id: int,
    ws: Workspace = Depends(require_ws_owner),
    db: AsyncSession = Depends(get_db),
):
    row = await db.get(WorkspaceMcp, (ws.id, mcp_id))
    if row is None:
        raise api_error(404, "该 MCP 未挂载")
    await db.delete(row)
    await db.commit()
    return Response(status_code=204)
