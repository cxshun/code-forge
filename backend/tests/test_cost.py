"""T10.1 Cost 计算引擎测试。

验证：模型定价表正确性、cache token 折算、未知模型 fallback。
"""

from app.observability.cost import PRICING, calc_cost_usd


def test_sonnet_pricing():
    p = PRICING["claude-sonnet-4-20250514"]
    assert p["input"] == 3.00
    assert p["output"] == 15.00
    assert p["cache_read"] == 0.30
    assert p["cache_creation"] == 3.75


def test_opus_pricing():
    p = PRICING["claude-opus-4-20250514"]
    assert p["input"] == 15.00
    assert p["output"] == 75.00


def test_haiku_pricing():
    p = PRICING["claude-3-5-haiku-20241022"]
    assert p["input"] == 0.80
    assert p["output"] == 4.00


def test_basic_cost_no_cache():
    cost = calc_cost_usd("claude-sonnet-4-20250514", 1_000_000, 500_000)
    # 1M input * $3 + 0.5M output * $15 = $3 + $7.5 = $10.5
    assert cost == 10.5


def test_cost_with_cache_read():
    cost = calc_cost_usd(
        "claude-sonnet-4-20250514",
        input_tokens=100_000,
        output_tokens=50_000,
        cache_read_tokens=900_000,
    )
    # 100k * $3/M + 50k * $15/M + 900k * $0.30/M
    # = $0.3 + $0.75 + $0.27 = $1.32
    assert abs(cost - 1.32) < 0.000001


def test_cost_with_cache_creation():
    cost = calc_cost_usd(
        "claude-sonnet-4-20250514",
        input_tokens=100_000,
        output_tokens=0,
        cache_creation_tokens=900_000,
    )
    # 100k * $3/M + 900k * $3.75/M
    # = $0.3 + $3.375 = $3.675
    assert abs(cost - 3.675) < 0.000001


def test_cost_all_token_types():
    cost = calc_cost_usd(
        "claude-opus-4-20250514",
        input_tokens=100_000,
        output_tokens=100_000,
        cache_read_tokens=200_000,
        cache_creation_tokens=100_000,
    )
    # 100k * $15/M + 100k * $75/M + 200k * $1.50/M + 100k * $18.75/M
    # = $1.5 + $7.5 + $0.3 + $1.875 = $11.175
    assert abs(cost - 11.175) < 0.000001


def test_unknown_model_falls_back_to_default():
    cost = calc_cost_usd("unknown-model", 1_000_000, 1_000_000)
    default = PRICING["_default"]
    expected = 1_000_000 / 1_000_000 * default["input"] + 1_000_000 / 1_000_000 * default["output"]
    assert cost == round(expected, 6)


def test_none_tokens_treated_as_zero():
    cost = calc_cost_usd("claude-sonnet-4-20250514", None, None, None, None)
    assert cost == 0.0


def test_zero_tokens():
    cost = calc_cost_usd("claude-sonnet-4-20250514", 0, 0, 0, 0)
    assert cost == 0.0


def test_none_model_uses_default():
    cost = calc_cost_usd(None, 1_000_000, 0)
    assert cost == 3.0  # default input price


def test_cost_precision():
    """cost_usd has 6 decimal places (Numeric(12,6))."""
    cost = calc_cost_usd("claude-3-5-haiku-20241022", 1, 1)
    # 1 token haiku: $0.80/M input + $4.00/M output
    # = 0.0000008 + 0.000004 = 0.000004.8 → round to 0.000005
    assert cost == 0.000005
