from decimal import Decimal

from causalrisk.usage import PricePerMillion, TokenUsage, estimate_cost_usd


def test_token_total_and_cost_are_provider_neutral():
    usage = TokenUsage(1_000, 500, "provider_reported")
    price = PricePerMillion(Decimal("2"), Decimal("6"), "2026-09-09", "provider pricing page")
    assert usage.total_tokens == 1_500
    assert estimate_cost_usd(usage, price) == Decimal("0.005")


def test_unknown_usage_remains_null_instead_of_zero():
    usage = TokenUsage(None, None, "unavailable")
    price = PricePerMillion(Decimal("2"), Decimal("6"), "v1", "source")
    assert usage.total_tokens is None
    assert estimate_cost_usd(usage, price) is None
