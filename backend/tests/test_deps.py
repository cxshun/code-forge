"""权限依赖测试（task T1.5 验收：四种权限标记覆盖）。"""

import pytest
from fastapi import HTTPException

from app.core.deps import assert_res_owner, require_admin, require_ws_owner
from app.core.security import hash_password
from app.db.models import User, Workspace
from app.db.session import async_session_factory
from app.db.testing import reset_all


@pytest.fixture(autouse=True)
async def _reset():
    await reset_all()
    yield


async def _users():
    async with async_session_factory() as s:
        admin = User(
            username="admin", password_hash=hash_password("p"), role="admin"
        )
        plain = User(
            username="alice", password_hash=hash_password("p"), role="user"
        )
        s.add_all([admin, plain])
        await s.commit()
        await s.refresh(admin)
        await s.refresh(plain)
        return admin, plain


async def test_require_admin_ok_and_forbidden():
    admin, plain = await _users()
    assert (await require_admin(user=admin)).id == admin.id
    with pytest.raises(HTTPException) as exc:
        await require_admin(user=plain)
    assert exc.value.status_code == 403


async def test_require_ws_owner_ok_and_forbidden():
    admin, plain = await _users()
    async with async_session_factory() as s:
        ws = Workspace(name="w", owner_id=admin.id)
        s.add(ws)
        await s.commit()
        await s.refresh(ws)
        # owner 自己 → 返回 ws
        got = await require_ws_owner(ws_id=ws.id, user=admin, db=s)
        assert got.id == ws.id
        # 非 owner → 403（管理员豁免见下）
        with pytest.raises(HTTPException) as exc:
            await require_ws_owner(ws_id=ws.id, user=plain, db=s)
        assert exc.value.status_code == 403
        # 管理员豁免
        admin_db = await s.get(User, admin.id)
        assert await require_ws_owner(ws_id=ws.id, user=admin_db, db=s)


async def test_require_ws_owner_not_found():
    admin, _ = await _users()
    async with async_session_factory() as s:
        with pytest.raises(HTTPException) as exc:
            await require_ws_owner(ws_id=999999, user=admin, db=s)
        assert exc.value.status_code == 404


async def test_assert_res_owner_ok_and_forbidden():
    admin, plain = await _users()
    # 资源 owner=admin，admin 访问 ok
    await assert_res_owner(owner_id=admin.id, user=admin)
    # plain 访问 admin 的资源 → 403
    with pytest.raises(HTTPException) as exc:
        await assert_res_owner(owner_id=admin.id, user=plain)
    assert exc.value.status_code == 403
    # 管理员豁免：plain 是 admin 时可访问任意
    await assert_res_owner(owner_id=999, user=admin)
