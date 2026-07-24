"""Model 元数据注册表（P3 D-CE.4）。

内置常见 LLM model 的 ``context_window`` / ``max_output_tokens`` 元数据，供 Provider
构造时查询真实窗口大小（替代硬编码 fallback）。未知 model 走 provider 的 fallback 值。

- 纯内存 dict，零运维成本，不引入 DB / 网络调用
- 支持 ``MODEL_OVERRIDES`` 环境变量（JSON）覆盖内置 registry
- ``get_model_meta(model_name)`` 查询，返回 ``ModelMeta | None``
"""

import json
import logging
from dataclasses import dataclass

from app.config import settings

log = logging.getLogger("providers.registry")


@dataclass(frozen=True)
class ModelMeta:
    """单 model 的元数据。"""

    context_window: int
    max_output_tokens: int


# 内置常见 model 元数据（context_window / max_output_tokens）
# 来源：各厂商官方文档 2026-07
_BUILTIN_REGISTRY: dict[str, ModelMeta] = {
    # Anthropic Claude
    "claude-sonnet-5-20250710": ModelMeta(context_window=200_000, max_output_tokens=16_384),
    "claude-sonnet-4-20250514": ModelMeta(context_window=200_000, max_output_tokens=16_384),
    "claude-opus-4-20250514": ModelMeta(context_window=200_000, max_output_tokens=32_000),
    "claude-3-5-haiku-20241022": ModelMeta(context_window=200_000, max_output_tokens=8_192),
    "claude-3-7-sonnet-20250219": ModelMeta(context_window=200_000, max_output_tokens=16_384),
    # OpenAI
    "gpt-4o": ModelMeta(context_window=128_000, max_output_tokens=16_384),
    "gpt-4o-mini": ModelMeta(context_window=128_000, max_output_tokens=16_384),
    "gpt-4-turbo": ModelMeta(context_window=128_000, max_output_tokens=4_096),
    "o1": ModelMeta(context_window=200_000, max_output_tokens=100_000),
    "o1-mini": ModelMeta(context_window=128_000, max_output_tokens=65_536),
    # 智谱 GLM
    "glm-4-plus": ModelMeta(context_window=128_000, max_output_tokens=4_096),
    "glm-4-air": ModelMeta(context_window=128_000, max_output_tokens=4_096),
    "glm-4-flash": ModelMeta(context_window=128_000, max_output_tokens=4_096),
    "glm-4.6": ModelMeta(context_window=200_000, max_output_tokens=131_072),
    "glm-4.7": ModelMeta(context_window=200_000, max_output_tokens=131_072),
    # DeepSeek
    "deepseek-chat": ModelMeta(context_window=64_000, max_output_tokens=8_192),
    "deepseek-reasoner": ModelMeta(context_window=64_000, max_output_tokens=32_768),
    "deepseek-v4-flash": ModelMeta(context_window=64_000, max_output_tokens=8_192),
    # 通义千问
    "qwen-plus": ModelMeta(context_window=131_072, max_output_tokens=8_192),
    "qwen-turbo": ModelMeta(context_window=1_000_000, max_output_tokens=8_192),
    # Moonshot
    "moonshot-v1-8k": ModelMeta(context_window=8_192, max_output_tokens=4_096),
    "moonshot-v1-32k": ModelMeta(context_window=32_768, max_output_tokens=4_096),
    "moonshot-v1-128k": ModelMeta(context_window=131_072, max_output_tokens=4_096),
}


def _build_registry() -> dict[str, ModelMeta]:
    """合并内置 registry + ``MODEL_OVERRIDES`` 环境变量。"""
    registry = dict(_BUILTIN_REGISTRY)
    overrides_raw = getattr(settings, "model_overrides", None)
    if overrides_raw:
        try:
            overrides = json.loads(overrides_raw) if isinstance(overrides_raw, str) else overrides_raw
            for name, meta in overrides.items():
                registry[name] = ModelMeta(
                    context_window=int(meta["context_window"]),
                    max_output_tokens=int(meta.get("max_output_tokens", 4096)),
                )
            log.info("MODEL_OVERRIDES loaded: %d models", len(overrides))
        except Exception:
            log.warning("MODEL_OVERRIDES parse failed; ignoring", exc_info=True)
    return registry


# 模块级单例（import 时构建一次）
MODEL_REGISTRY: dict[str, ModelMeta] = _build_registry()


def get_model_meta(model_name: str | None) -> ModelMeta | None:
    """查 model 元数据；未知 model 返回 None（调用方走 fallback）。"""
    if not model_name:
        return None
    return MODEL_REGISTRY.get(model_name)


def list_models() -> list[dict]:
    """列出所有已知 model（供 ``GET /api/models`` 前端 datalist 用）。"""
    return [
        {"name": name, "context_window": meta.context_window, "max_output_tokens": meta.max_output_tokens}
        for name, meta in sorted(MODEL_REGISTRY.items())
    ]
