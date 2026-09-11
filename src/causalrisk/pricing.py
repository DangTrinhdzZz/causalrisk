"""Versioned list-price loading and fail-closed normalized cost accounting."""

from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

from causalrisk.providers.candidates import PROVIDER_CANDIDATES


@dataclass(frozen=True, slots=True)
class UsageBreakdown:
    input_tokens: int
    output_tokens: int
    cached_input_tokens: int = 0
    reasoning_tokens: int = 0


class PricingError(ValueError):
    pass


def load_pricing(path: str | Path) -> dict[str, Any]:
    document = json.loads(Path(path).read_text(encoding="utf-8"))
    if (
        document.get("schema_version") != 1
        or document.get("currency") != "USD"
        or document.get("unit") != "per_1m_tokens"
        or not isinstance(document.get("effective_date"), str)
    ):
        raise PricingError("unsupported pricing snapshot")
    expected = {
        f"{candidate.provider}:{candidate.model_id}"
        for candidate in PROVIDER_CANDIDATES.values()
        if candidate.primary and candidate.availability == "available"
    }
    if set(document.get("models", {})) != expected:
        raise PricingError("pricing snapshot does not exactly match execution roster")
    return document


def missing_official_prices(document: dict[str, Any]) -> tuple[str, ...]:
    return tuple(
        sorted(
            key
            for key, price in document["models"].items()
            if price.get("status") != "priced" or price.get("input") is None or price.get("output") is None
        )
    )


def waiver_allows_unpriced_provider(document: dict[str, Any], key: str, waiver: Any) -> bool:
    if not key.startswith("nvidia_nim:") or not isinstance(waiver, dict):
        return False
    price = document["models"].get(key)
    return (
        waiver.get("provider") == "nvidia_nim"
        and price is not None
        and waiver.get("source_url") == price.get("source")
        and waiver.get("effective_date") == document.get("effective_date")
    )


def normalized_list_cost_usd(
    document: dict[str, Any],
    key: str,
    usage: UsageBreakdown,
    *,
    allow_symbolic_unpriced_provider: bool = False,
) -> Decimal | None:
    price = document["models"][key]
    if key in missing_official_prices(document):
        if allow_symbolic_unpriced_provider and key.startswith("nvidia_nim:"):
            return None
        raise PricingError(f"official token price unavailable: {key}")
    uncached = usage.input_tokens - usage.cached_input_tokens
    if uncached < 0 or usage.reasoning_tokens > usage.output_tokens:
        raise PricingError("usage breakdown is inconsistent")
    cached_rate = price.get("cached_input")
    if usage.cached_input_tokens and cached_rate is None:
        raise PricingError(f"cached-input price unavailable: {key}")
    output_non_reasoning = usage.output_tokens - usage.reasoning_tokens
    reasoning_rate = price.get("reasoning")
    if usage.reasoning_tokens and reasoning_rate is None:
        raise PricingError(f"reasoning-token price unavailable: {key}")
    total = Decimal(uncached) * Decimal(str(price["input"]))
    total += Decimal(usage.cached_input_tokens) * Decimal(str(cached_rate or 0))
    total += Decimal(output_non_reasoning) * Decimal(str(price["output"]))
    total += Decimal(usage.reasoning_tokens) * Decimal(str(reasoning_rate or 0))
    return total / Decimal(1_000_000)


def symbolic_sensitivity_cost_usd(
    priced_subtotal_usd: Decimal,
    nvidia_input_tokens: int,
    nvidia_output_tokens: int,
    assumed_input_rate: Decimal,
    assumed_output_rate: Decimal,
) -> Decimal:
    if min(nvidia_input_tokens, nvidia_output_tokens) < 0:
        raise PricingError("token counts must be non-negative")
    if min(assumed_input_rate, assumed_output_rate) < 0:
        raise PricingError("assumed rates must be non-negative")
    return priced_subtotal_usd + (
        Decimal(nvidia_input_tokens) * assumed_input_rate
        + Decimal(nvidia_output_tokens) * assumed_output_rate
    ) / Decimal(1_000_000)
