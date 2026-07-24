from __future__ import annotations

import math
from decimal import ROUND_CEILING, Decimal

MICRO_USD_PER_USD = Decimal("1000000")
TOKENS_PER_MILLION = Decimal("1000000")


def estimate_tokens(value: str) -> int:
    """Conservative provider-neutral estimate without a model-specific tokenizer."""
    if not value:
        return 0
    return max(1, math.ceil(len(value.encode("utf-8")) / 3))


def estimate_cost_microusd(
    input_tokens: int,
    output_tokens: int,
    input_price_per_1m_usd: Decimal,
    output_price_per_1m_usd: Decimal,
) -> int:
    input_cost = Decimal(input_tokens) * input_price_per_1m_usd / TOKENS_PER_MILLION
    output_cost = Decimal(output_tokens) * output_price_per_1m_usd / TOKENS_PER_MILLION
    return int(((input_cost + output_cost) * MICRO_USD_PER_USD).to_integral_value(ROUND_CEILING))


def usd_to_microusd(value: Decimal) -> int:
    return int((value * MICRO_USD_PER_USD).to_integral_value(ROUND_CEILING))
