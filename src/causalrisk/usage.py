"""Provider-neutral token accounting and frozen-price cost estimation."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class TokenUsage:
    input_tokens: int | None
    output_tokens: int | None
    accounting_method: str
    reasoning_tokens: int | None = None
    cached_input_tokens: int | None = None

    def __post_init__(self) -> None:
        for value in (self.input_tokens, self.output_tokens, self.reasoning_tokens, self.cached_input_tokens):
            if value is not None and (isinstance(value, bool) or value < 0):
                raise ValueError("token counts must be non-negative integers or null")
        if not self.accounting_method.strip():
            raise ValueError("accounting_method must be documented")
        if (
            self.reasoning_tokens is not None
            and self.output_tokens is not None
            and self.reasoning_tokens > self.output_tokens
        ):
            raise ValueError("reasoning_tokens cannot exceed output_tokens")
        if (
            self.cached_input_tokens is not None
            and self.input_tokens is not None
            and self.cached_input_tokens > self.input_tokens
        ):
            raise ValueError("cached_input_tokens cannot exceed input_tokens")

    @property
    def total_tokens(self) -> int | None:
        if self.input_tokens is None or self.output_tokens is None:
            return None
        return self.input_tokens + self.output_tokens


@dataclass(frozen=True, slots=True)
class PricePerMillion:
    input_usd: Decimal
    output_usd: Decimal
    version: str
    source: str

    def __post_init__(self) -> None:
        if self.input_usd < 0 or self.output_usd < 0:
            raise ValueError("prices must be non-negative")
        if not self.version.strip() or not self.source.strip():
            raise ValueError("pricing version and source are required")


def estimate_cost_usd(usage: TokenUsage, price: PricePerMillion) -> Decimal | None:
    if usage.input_tokens is None or usage.output_tokens is None:
        return None
    million = Decimal(1_000_000)
    return (
        Decimal(usage.input_tokens) * price.input_usd / million
        + Decimal(usage.output_tokens) * price.output_usd / million
    )
