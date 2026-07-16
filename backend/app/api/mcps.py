"""MCP 广场 CRUD（api §6.2 / D11 / D37）。

- GET /mcps：广场列表（我的 + 全员可见）
- POST /mcps：注册 stdio / http（config 含 secret 字段加密存储）
- GET/PATCH/DELETE /mcps/{id}（res owner；被引用禁删；返回脱敏）
"""

from fastapi import APIRouter, Depends, Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import McpCreateIn, McpOut, McpPatchIn
from app.core.deps import assert_res_owner, require_user
from app.core.errors import api_error
from app.core.security import encrypt_secrets, mask_secrets
from app.db.models import MCP, User, WorkspaceMcp
from app.db.session import get_db

router = APIRouter(prefix="/mcps", tags=["mcps"])


def _mcp_out(m: MCP, owner_name: str = "") -> McpOut:
    return McpOut(
        id=m.id,
        name=m.name,
        type=m.type,
        config=mask_secrets(m.config),
        owner_id=m.owner_id,
        owner_name=owner_name or "",
        visibility=m.visibility,
        read_only=m.read_only,
    )


@router.get("")
async def list_mcps(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_user),
):
    # 广场浏览：我的 + 全员可见（D11）
    mcps = (
        await db.scalars(
            select(MCP)
            .where((MCP.owner_id == user.id) | (MCP.visibility == "public"))
            .order_by(MCP.id)
        )
    ).all()
    # 批量解析 owner 名称
    owner_ids = {m.owner_id for m in mcps}
    owner_map: dict[int, str] = {}
    if owner_ids:
        users = (
            await db.scalars(select(User).where(User.id.in_(owner_ids)))
        ).all()
        owner_map = {u.id: u.username for u in users}
    return {
        "items": [_mcp_out(m, owner_name=owner_map.get(m.owner_id, "")) for m in mcps],
        "total": len(mcps),
    }


@router.post("", status_code=201)
async def create_mcp(
    body: McpCreateIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_user),
):
    m = MCP(
        name=body.name,
        type=body.type,
        config=encrypt_secrets(body.config),
        owner_id=user.id,
        visibility=body.visibility,
        read_only=body.read_only,
    )
    db.add(m)
    await db.commit()
    await db.refresh(m)
    return _mcp_out(m, owner_name=user.username)


@router.get("/{mcp_id}")
async def get_mcp(
    mcp_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_user),
):
    m = await db.get(MCP, mcp_id)
    if m is None:
        raise api_error(404, "MCP 不存在")
    if m.owner_id != user.id and m.visibility != "public":
        raise api_error(404, "MCP 不存在")
    owner = await db.get(User, m.owner_id)
    return _mcp_out(m, owner_name=owner.username if owner else "")


@router.patch("/{mcp_id}")
async def patch_mcp(
    mcp_id: int,
    body: McpPatchIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_user),
):
    m = await db.get(MCP, mcp_id)
    if m is None:
        raise api_error(404, "MCP 不存在")
    await assert_res_owner(m.owner_id, user)
    if body.name is not None:
        m.name = body.name
    if body.config is not None:
        m.config = encrypt_secrets(body.config)
    if body.visibility is not None:
        m.visibility = body.visibility
    if body.read_only is not None:
        m.read_only = body.read_only
    await db.commit()
    await db.refresh(m)
    owner = await db.get(User, m.owner_id)
    return _mcp_out(m, owner_name=owner.username if owner else "")


@router.delete("/{mcp_id}", status_code=204)
async def delete_mcp(
    mcp_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_user),
):
    m = await db.get(MCP, mcp_id)
    if m is None:
        raise api_error(404, "MCP 不存在")
    await assert_res_owner(m.owner_id, user)
    # 被引用禁删（F3.5.5）
    count = (
        await db.scalar(
            select(func.count())
            .select_from(WorkspaceMcp)
            .where(WorkspaceMcp.mcp_id == mcp_id)
        )
    ) or 0
    if count:
        raise api_error(422, f"MCP 被 {count} 个工作空间引用，请先解挂")
    await db.delete(m)
    await db.commit()
    return Response(status_code=204)
