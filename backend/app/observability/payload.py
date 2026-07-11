"""Payload 文件写入 + 截断（design §7.5 / D26 / D29）。

payload 落 ``chats/{feishu_chat_id}/traces/{trace_id}/`` 目录：
- ``{span_id}.request.json``  — LLM 请求（≤5MB）
- ``{span_id}.response.jsonl`` — LLM 流式响应（≤10MB）
- ``{span_id}.tool.json``     — 工具输入输出（≤1MB）
- ``{span_id}.skill.json``    — Skill 加载（≤200KB）

写入前过 ``redaction.redact()`` 脱敏管线（D30）。
用 ``asyncio.to_thread`` 避免阻塞 event loop（§7.4 aiodisk 线程池）。
"""

import asyncio
import json
import logging
from pathlib import Path

from app.config import settings
from app.observability.redaction import redact
from app.workspace.fs import workspace_root

log = logging.getLogger("observability.payload")

# 截断上限（bytes，§7.5）
MAX_REQUEST = 5 * 1024 * 1024
MAX_RESPONSE = 10 * 1024 * 1024
MAX_TOOL = 1 * 1024 * 1024
MAX_SKILL = 200 * 1024


def _trace_dir(ws_id: int, feishu_chat_id: int, trace_id: str) -> Path:
    return (
        workspace_root(ws_id)
        / "chats"
        / str(feishu_chat_id)
        / "traces"
        / trace_id
    )


async def write_payload(
    ws_id: int,
    feishu_chat_id: int,
    trace_id: str,
    span_id: str,
    suffix: str,
    data,
    max_bytes: int,
) -> tuple[str | None, int, bool]:
    """写入 payload 文件，返回 (payload_ref, size_bytes, truncated)。

    失败时返回 (None, 0, False)，不抛异常（best-effort，§7.4 降级矩阵）。
    """
    redacted = redact(data)
    raw = json.dumps(redacted, ensure_ascii=False, default=str).encode("utf-8")
    truncated = False
    if len(raw) > max_bytes:
        raw = raw[:max_bytes]
        truncated = True

    dir_path = _trace_dir(ws_id, feishu_chat_id, trace_id)
    file_path = dir_path / f"{span_id}.{suffix}"

    try:
        def _write():
            dir_path.mkdir(parents=True, exist_ok=True)
            with file_path.open("wb") as f:
                f.write(raw)
        await asyncio.to_thread(_write)
    except Exception:
        log.warning("payload write failed: %s", file_path, exc_info=True)
        return None, 0, False

    ref = str(file_path.relative_to(Path(settings.data_dir)))
    return ref, len(raw), truncated


async def append_response_delta(
    ws_id: int,
    feishu_chat_id: int,
    trace_id: str,
    span_id: str,
    delta: str,
) -> None:
    """流式追加 LLM 响应 delta 到 response.jsonl。

    超过 MAX_RESPONSE 后停止追加（§7.5 截断策略），不抛异常。
    """
    file_path = _trace_dir(ws_id, feishu_chat_id, trace_id) / f"{span_id}.response.jsonl"
    try:
        line = json.dumps({"delta": delta}, ensure_ascii=False) + "\n"
        raw = line.encode("utf-8")

        def _append():
            file_path.parent.mkdir(parents=True, exist_ok=True)
            with file_path.open("ab") as f:
                # 检查文件大小，超过上限则停止追加
                if f.tell() + len(raw) > MAX_RESPONSE:
                    return
                f.write(raw)
        await asyncio.to_thread(_append)
    except Exception:
        log.warning("response delta append failed: %s", file_path, exc_info=True)


async def read_payload(
    ws_id: int, feishu_chat_id: int, trace_id: str, span_id: str, suffix: str
) -> bytes | None:
    """读取 payload 文件内容（API 层调用）。

    返回 None 表示文件不存在。
    """
    file_path = _trace_dir(ws_id, feishu_chat_id, trace_id) / f"{span_id}.{suffix}"
    try:
        def _read():
            return file_path.read_bytes()
        return await asyncio.to_thread(_read)
    except FileNotFoundError:
        return None
    except Exception:
        log.warning("payload read failed: %s", file_path, exc_info=True)
        return None


__all__ = [
    "MAX_REQUEST",
    "MAX_RESPONSE",
    "MAX_SKILL",
    "MAX_TOOL",
    "append_response_delta",
    "read_payload",
    "write_payload",
]
