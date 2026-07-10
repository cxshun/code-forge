"""统一 API 错误（对齐 api.md §1.3 / §1.4）。

api_error() 返回 HTTPException，detail 形如 ``{"error": {"code", "message", ...}}``，
由 main.py 的全局异常处理器原样回写。
"""

from typing import Any

from fastapi import HTTPException

CODE_BY_STATUS: dict[int, str] = {
    400: "bad_request",
    401: "unauthorized",
    403: "forbidden",
    404: "not_found",
    405: "method_not_allowed",
    409: "conflict",
    422: "validation_failed",
    429: "rate_limited",
    500: "internal_error",
}


def api_error(
    status_code: int, message: str, code: str | None = None, details: Any = None
) -> HTTPException:
    err: dict[str, Any] = {
        "code": code or CODE_BY_STATUS.get(status_code, "error"),
        "message": message,
    }
    if details is not None:
        err["details"] = details
    return HTTPException(status_code=status_code, detail={"error": err})
