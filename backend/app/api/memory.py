"""Memory 管理后端 API（api §8 / design D19 / spec F3.7.6 / T7.5）。

按 FeishuChat 维度管理其 ``chats/{feishu_chat_id}/memory/`` 下的 memory 文件：

- ``GET /workspaces/{ws_id}/chats/{feishu_chat_id}/memory``：列出 memory 文件
- ``GET .../memory/{filename}``：读文件内容
- ``PUT .../memory/{filename}``：写文件内容（覆盖 / 新建）
- ``DELETE .../memory/{filename}``：删除

``filename`` 严格白名单 ``[A-Za-z0-9_\\-]+\\.md``，resolve 校验落在 memory 子树
（防 ``../`` 穿越与非法字符）；chat 归属 WS 校验（D31 多租户隔离）。
"""

import re

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import MemoryFileIn
from app.core.deps import require_ws_owner
from app.core.errors import api_error
from app.db.models import FeishuChat, Workspace
from app.db.session import get_db
from app.workspace.fs import create_chat_memory_skeleton

router = APIRouter(prefix="/workspaces", tags=["memory"])

_FILENAME_RE = re.compile(r"^[A-Za-z0-9_\-]+\.md$")


class MemoryFileOut(BaseModel):
    filename: str
    size: int


async def _get_chat(
    ws_id: int, feishu_chat_id: int, db: AsyncSession
) -> FeishuChat:
    chat = await db.get(FeishuChat, feishu_chat_id)
    if chat is None or chat.workspace_id != ws_id:
        raise api_error(404, "FeishuChat 不存在")
    return chat


def _memory_dir(ws_id: int, feishu_chat_id: int):
    return create_chat_memory_skeleton(ws_id, feishu_chat_id)


def _validate_filename(filename: str) -> str:
    if not _FILENAME_RE.match(filename):
        raise api_error(422, "filename 仅允许 [A-Za-z0-9_-]+.md")
    return filename


@router.get("/{ws_id}/chats/{feishu_chat_id}/memory")
async def list_memory(
    feishu_chat_id: int,
    ws: Workspace = Depends(require_ws_owner),
    db: AsyncSession = Depends(get_db),
):
    await _get_chat(ws.id, feishu_chat_id, db)
    mem = _memory_dir(ws.id, feishu_chat_id)
    files = sorted(
        MemoryFileOut(filename=p.name, size=p.stat().st_size)
        for p in mem.glob("*.md")
        if p.is_file()
    )
    return {"files": [f.model_dump() for f in files]}


@router.get("/{ws_id}/chats/{feishu_chat_id}/memory/{filename}")
async def get_memory(
    feishu_chat_id: int,
    filename: str,
    ws: Workspace = Depends(require_ws_owner),
    db: AsyncSession = Depends(get_db),
):
    await _get_chat(ws.id, feishu_chat_id, db)
    _validate_filename(filename)
    path = _memory_dir(ws.id, feishu_chat_id) / filename
    if not path.is_file():
        raise api_error(404, "memory 文件不存在")
    return {"filename": filename, "content": path.read_text(encoding="utf-8")}


@router.put("/{ws_id}/chats/{feishu_chat_id}/memory/{filename}")
async def put_memory(
    feishu_chat_id: int,
    filename: str,
    body: MemoryFileIn,
    ws: Workspace = Depends(require_ws_owner),
    db: AsyncSession = Depends(get_db),
):
    await _get_chat(ws.id, feishu_chat_id, db)
    _validate_filename(filename)
    path = _memory_dir(ws.id, feishu_chat_id) / filename
    path.write_text(body.content, encoding="utf-8")
    return {"filename": filename, "content": body.content}


@router.delete("/{ws_id}/chats/{feishu_chat_id}/memory/{filename}")
async def delete_memory(
    feishu_chat_id: int,
    filename: str,
    ws: Workspace = Depends(require_ws_owner),
    db: AsyncSession = Depends(get_db),
):
    await _get_chat(ws.id, feishu_chat_id, db)
    _validate_filename(filename)
    path = _memory_dir(ws.id, feishu_chat_id) / filename
    if not path.is_file():
        raise api_error(404, "memory 文件不存在")
    path.unlink()
    return {"filename": filename, "deleted": True}
