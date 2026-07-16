"""Skill 广场 CRUD（api §6.1 / D11 / D15）。

- POST /skills：multipart 上传 zip（SKILL.md + resources/ + scripts/），解析 frontmatter
  校验 name（全局唯一）/ description（必填），解压到 /skills/{skill_id}/（防 zip-slip）
- GET /skills：广场列表（我的 + 全员可见，可选搜索 q）
- GET/PATCH/DELETE /skills/{id}（res owner；被引用禁删；GET 返回引用数）
"""

import io
import shutil
import zipfile

import yaml
from fastapi import APIRouter, Depends, File, Form, Response, UploadFile
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import SkillOut, SkillPatchIn
from app.core.deps import assert_res_owner, require_user
from app.core.errors import api_error
from app.db.models import Skill, User, WorkspaceSkill
from app.db.session import get_db
from app.workspace.fs import create_skill_skeleton, skill_dir

router = APIRouter(prefix="/skills", tags=["skills"])


def _skill_out(s: Skill, owner_name: str = "") -> SkillOut:
    return SkillOut(
        id=s.id,
        name=s.name,
        description=s.description,
        owner_id=s.owner_id,
        owner_name=owner_name or "",
        visibility=s.visibility,
        dir_path=s.dir_path,
    )


def _parse_frontmatter(content: str) -> dict:
    if not content.startswith("---"):
        return {}
    parts = content.split("---", 2)
    if len(parts) < 3:
        return {}
    loaded = yaml.safe_load(parts[1])
    return loaded or {}


def _safe_extract(zf: zipfile.ZipFile, target) -> None:
    """解压并防 zip-slip：成员 resolve 后须落在 target 内。"""
    target_resolved = target.resolve()
    for member in zf.namelist():
        dest = (target / member).resolve()
        if dest != target_resolved and target_resolved not in dest.parents:
            raise api_error(422, f"非法压缩包路径: {member}")
    zf.extractall(target)


@router.get("")
async def list_skills(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_user),
    q: str | None = None,
):
    stmt = select(Skill).where(
        (Skill.owner_id == user.id) | (Skill.visibility == "public")
    )
    if q:
        stmt = stmt.where(Skill.name.ilike(f"%{q}%"))
    skills = (await db.scalars(stmt.order_by(Skill.id))).all()
    # 批量解析 owner 名称
    owner_ids = {s.owner_id for s in skills}
    owner_map: dict[int, str] = {}
    if owner_ids:
        users = (
            await db.scalars(select(User).where(User.id.in_(owner_ids)))
        ).all()
        owner_map = {u.id: u.username for u in users}
    return {
        "items": [_skill_out(s, owner_name=owner_map.get(s.owner_id, "")) for s in skills],
        "total": len(skills),
    }


@router.post("", status_code=201)
async def create_skill(
    file: UploadFile = File(...),
    visibility: str = Form("private"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_user),
):
    if visibility not in ("private", "public"):
        raise api_error(422, "visibility 取值非法")
    data = await file.read()
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as e:
        raise api_error(422, "需要 zip 格式压缩包") from e

    skill_md_names = [n for n in zf.namelist() if n.endswith("SKILL.md")]
    if not skill_md_names:
        raise api_error(422, "压缩包缺少 SKILL.md")
    skill_md_name = min(skill_md_names, key=len)
    fm = _parse_frontmatter(zf.read(skill_md_name).decode("utf-8"))
    name = fm.get("name")
    description = fm.get("description")
    if not name or not description:
        raise api_error(422, "SKILL.md frontmatter 缺 name 或 description")

    if await db.scalar(select(Skill).where(Skill.name == name)):
        raise api_error(422, f"Skill name '{name}' 已存在")

    skill = Skill(
        name=name,
        description=str(description),
        owner_id=user.id,
        visibility=visibility,
        dir_path="",
    )
    db.add(skill)
    await db.commit()
    await db.refresh(skill)

    d = skill_dir(skill.id)
    create_skill_skeleton(skill.id)
    _safe_extract(zf, d)
    skill.dir_path = str(d)
    await db.commit()
    await db.refresh(skill)
    return _skill_out(skill, owner_name=user.username)


@router.get("/{skill_id}")
async def get_skill(
    skill_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_user),
):
    s = await db.get(Skill, skill_id)
    if s is None:
        raise api_error(404, "Skill 不存在")
    if s.owner_id != user.id and s.visibility != "public":
        raise api_error(404, "Skill 不存在")
    count = (
        await db.scalar(
            select(func.count())
            .select_from(WorkspaceSkill)
            .where(WorkspaceSkill.skill_id == skill_id)
        )
    ) or 0
    owner = await db.get(User, s.owner_id)
    out = _skill_out(s, owner_name=owner.username if owner else "").model_dump()
    out["mounted_count"] = count
    return out


@router.patch("/{skill_id}")
async def patch_skill(
    skill_id: int,
    body: SkillPatchIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_user),
):
    s = await db.get(Skill, skill_id)
    if s is None:
        raise api_error(404, "Skill 不存在")
    await assert_res_owner(s.owner_id, user)
    if body.description is not None:
        s.description = body.description
    if body.visibility is not None:
        s.visibility = body.visibility
    await db.commit()
    await db.refresh(s)
    return _skill_out(s, owner_name=user.username)


@router.delete("/{skill_id}", status_code=204)
async def delete_skill(
    skill_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_user),
):
    s = await db.get(Skill, skill_id)
    if s is None:
        raise api_error(404, "Skill 不存在")
    await assert_res_owner(s.owner_id, user)
    count = (
        await db.scalar(
            select(func.count())
            .select_from(WorkspaceSkill)
            .where(WorkspaceSkill.skill_id == skill_id)
        )
    ) or 0
    if count:
        raise api_error(422, f"Skill 被 {count} 个工作空间引用，请先解挂")
    d = skill_dir(s.id)
    if d.exists():
        shutil.rmtree(d)
    await db.delete(s)
    await db.commit()
    return Response(status_code=204)
