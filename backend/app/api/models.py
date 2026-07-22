"""模型元数据接口（P3 D-CE.4 / D-CE.6）。

``GET /api/admin/models`` 返回 ModelRegistry 中所有已知 model 的 context_window /
max_output_tokens，供前端「模型配置」tab 的 datalist 展示。
"""

from fastapi import APIRouter

from app.providers.registry import list_models

router = APIRouter(tags=["models"])


@router.get("/models")
async def get_models() -> list[dict]:
    """列出所有已知 model 元数据（供前端 model 选择 datalist）。"""
    return list_models()
