"""Cost 计算引擎（design §7.2 / T10.1）。

模型定价表 + cache token 折算 → 单次 LLM 调用成本。

定价来源：Anthropic 官方定价页（per 1M tokens, USD）。
cache_read 仅为输入价的 10%，cache_creation 为输入价的 125%（prompt caching premium）。
"""

from __future__ import annotations

PRICING: dict[str, dict[str, float]] = {
    "claude-sonnet-4-20250514": {
        "input": 3.00,
        "output": 15.00,
        "cache_read": 0.30,
        "cache_creation": 3.75,
    },
    "claude-opus-4-20250514": {
        "input": 15.00,
        "output": 75.00,
        "cache_read": 1.50,
        "cache_creation": 18.75,
    },
    "claude-3-5-haiku-20241022": {
        "input": 0.80,
        "output": 4.00,
        "cache_read": 0.08,
        "cache_creation": 1.00,
    },
    "claude-3-5-sonnet-20241022": {
        "input": 3.00,
        "output": 15.00,
        "cache_read": 0.30,
        "cache_creation": 3.75,
    },
    "_default": {
        "input": 3.00,
        "output": 15.00,
        "cache_read": 0.30,
        "cache_creation": 3.75,
    },
}


def calc_cost_usd(
    model: str | None,
    input_tokens: int | None,
    output_tokens: int | None,
    cache_read_tokens: int | None = None,
    cache_creation_tokens: int | None = None,
) -> float:
    """根据模型定价 + cache 折算计算单次 LLM 调用成本（USD）。

    未知模型走 ``_default`` 定价（对齐 Sonnet 级别）。
    """
    p = PRICING.get(model or "", PRICING["_default"])
    cost = (
        (input_tokens or 0) / 1_000_000 * p["input"]
        + (output_tokens or 0) / 1_000_000 * p["output"]
        + (cache_read_tokens or 0) / 1_000_000 * p["cache_read"]
        + (cache_creation_tokens or 0) / 1_000_000 * p["cache_creation"]
    )
    return round(cost, 6)


__all__ = ["PRICING", "calc_cost_usd"]
