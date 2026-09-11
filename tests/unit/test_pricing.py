from decimal import Decimal
from pathlib import Path

import pytest

from causalrisk.pricing import (
    PricingError,
    UsageBreakdown,
    load_pricing,
    missing_official_prices,
    normalized_list_cost_usd,
)

ROOT = Path(__file__).resolve().parents[2]


def test_snapshot_matches_roster_and_fails_closed_for_nvidia():
    pricing = load_pricing(ROOT / "configs" / "pricing_2026-09-11.json")
    assert missing_official_prices(pricing) == ("nvidia_nim:nvidia/nemotron-3.5-lightning-30b-a3b",)
    with pytest.raises(PricingError, match="official token price unavailable"):
        normalized_list_cost_usd(pricing, missing_official_prices(pricing)[0], UsageBreakdown(1, 1))


def test_cost_separates_cached_and_reasoning_tokens():
    pricing = load_pricing(ROOT / "configs" / "pricing_2026-09-11.json")
    cost = normalized_list_cost_usd(
        pricing,
        "openai:gpt-5.6-terra",
        UsageBreakdown(input_tokens=100, cached_input_tokens=20, output_tokens=10, reasoning_tokens=4),
    )
    assert cost == Decimal("0.000284")
