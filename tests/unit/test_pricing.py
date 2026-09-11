import json
from decimal import Decimal
from pathlib import Path

import pytest

from causalrisk.pricing import (
    PricingError,
    UsageBreakdown,
    load_pricing,
    missing_official_prices,
    normalized_list_cost_usd,
    symbolic_sensitivity_cost_usd,
    waiver_allows_unpriced_provider,
)

ROOT = Path(__file__).resolve().parents[2]


def test_snapshot_matches_roster_and_fails_closed_for_nvidia():
    pricing = load_pricing(ROOT / "configs" / "pricing_2026-09-11.json")
    assert missing_official_prices(pricing) == ("nvidia_nim:nvidia/nemotron-3.5-lightning-30b-a3b",)
    with pytest.raises(PricingError, match="official token price unavailable"):
        normalized_list_cost_usd(pricing, missing_official_prices(pricing)[0], UsageBreakdown(1, 1))
    key = missing_official_prices(pricing)[0]
    waiver = {
        "provider": "nvidia_nim",
        "source_url": pricing["models"][key]["source"],
        "effective_date": pricing["effective_date"],
        "reason": "free prototype endpoint has no official token list price",
    }
    assert waiver_allows_unpriced_provider(pricing, key, waiver)
    assert normalized_list_cost_usd(
        pricing, key, UsageBreakdown(55, 245), allow_symbolic_unpriced_provider=True
    ) is None


@pytest.mark.parametrize(
    ("field", "value"),
    [("input", 0), ("normalized_list_cost_usd", 0), ("billing_mode", "paid")],
)
def test_snapshot_rejects_nvidia_zero_or_proxy_pricing(tmp_path, field, value):
    source = ROOT / "configs" / "pricing_2026-09-11.json"
    document = json.loads(source.read_text(encoding="utf-8"))
    key = "nvidia_nim:nvidia/nemotron-3.5-lightning-30b-a3b"
    document["models"][key][field] = value
    path = tmp_path / "pricing.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(PricingError, match="NVIDIA symbolic pricing policy"):
        load_pricing(path)


def test_cost_separates_cached_and_reasoning_tokens():
    pricing = load_pricing(ROOT / "configs" / "pricing_2026-09-11.json")
    cost = normalized_list_cost_usd(
        pricing,
        "openai:gpt-5.6-terra",
        UsageBreakdown(input_tokens=100, cached_input_tokens=20, output_tokens=10, reasoning_tokens=4),
    )
    assert cost == Decimal("0.000284")


def test_symbolic_sensitivity_adds_assumed_nvidia_rates_without_changing_subtotal():
    assert symbolic_sensitivity_cost_usd(Decimal("0.001"), 1000, 500, Decimal("2"), Decimal("4")) == Decimal("0.005")
