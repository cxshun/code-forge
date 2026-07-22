"""Per-WS 模型配置（P3 D-CE.6）。

``Workspace.model_config`` JSONB 字段的 schema 化解析。``None`` / 空 → 走全局
``settings`` 默认 Provider（``make_provider()`` 无参行为不变）。

api_key 存储时用 Fernet 加密（``encrypt_secret``），读取时解密（``decrypt_secret``）。
API 层不回显明文 key，仅返回 ``has_api_key`` 布尔。
"""

from __future__ import annotations

import logging

from pydantic import BaseModel, ConfigDict

from app.core.security import decrypt_secret, encrypt_secret

log = logging.getLogger("agent.model_config")


class ModelConfig(BaseModel):
    """D-CE.6 per-WS 模型配置。"""

    model_config = ConfigDict(extra="ignore")

    provider: str = "anthropic"  # "anthropic" | "openai_compatible"
    model: str | None = None
    api_base_url: str | None = None
    # 加密后的 API key（Fernet 密文）；None → 走 settings 全局 key
    api_key_enc: str | None = None

    @classmethod
    def from_ws(cls, data: dict | None) -> ModelConfig | None:
        """从容错解析 WS.model_config。``None`` / 空 → 返回 None（走全局）。"""
        if not data:
            return None
        try:
            return cls.model_validate(data)
        except Exception:
            log.warning("model_config parse failed; fallback to global", exc_info=True)
            return None

    @property
    def api_key(self) -> str | None:
        """解密 API key → 明文；未设返回 None。"""
        if not self.api_key_enc:
            return None
        try:
            return decrypt_secret(self.api_key_enc)
        except Exception:
            log.warning("model_config api_key decrypt failed", exc_info=True)
            return None

    @classmethod
    def create_encrypted(
        cls,
        provider: str = "anthropic",
        model: str | None = None,
        api_base_url: str | None = None,
        api_key: str | None = None,
    ) -> ModelConfig:
        """从明文参数构造（api_key 自动加密）。供 API 层 PATCH 用。"""
        return cls(
            provider=provider,
            model=model or None,
            api_base_url=api_base_url or None,
            api_key_enc=encrypt_secret(api_key) if api_key else None,
        )

    def to_db_dict(self) -> dict:
        """序列化为 DB 存储格式（含加密 key）。"""
        return self.model_dump(exclude_none=True)
