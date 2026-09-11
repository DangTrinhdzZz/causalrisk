"""Provider-neutral request/response contract with no automatic retries."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from causalrisk.usage import TokenUsage


@dataclass(frozen=True, slots=True)
class ProviderRequest:
    prompt: str
    model_id: str
    temperature: float
    max_output_tokens: int
    seed: int | None = None

    def __post_init__(self) -> None:
        if not self.prompt.strip() or not self.model_id.strip():
            raise ValueError("prompt and model_id must be non-empty")
        if isinstance(self.temperature, bool) or not isinstance(self.temperature, (int, float)):
            raise ValueError("temperature must be numeric")
        if isinstance(self.max_output_tokens, bool) or self.max_output_tokens <= 0:
            raise ValueError("max_output_tokens must be a positive integer")


@dataclass(frozen=True, slots=True)
class ProviderResponse:
    provider: str
    requested_model_id: str
    reported_model_id: str | None
    text: str
    usage: TokenUsage
    latency_ms: float
    response_id: str | None = None
    http_status: int | None = None
    finish_reason: str | None = None
    actual_charge_usd: float | None = None

    def __post_init__(self) -> None:
        if not self.provider.strip() or not self.requested_model_id.strip():
            raise ValueError("provider and requested_model_id must be non-empty")
        if not isinstance(self.text, str):
            raise TypeError("provider response text must be a string")
        if self.latency_ms < 0:
            raise ValueError("latency_ms must be non-negative")
        if self.actual_charge_usd is not None and (
            isinstance(self.actual_charge_usd, bool)
            or not isinstance(self.actual_charge_usd, int | float)
            or self.actual_charge_usd < 0
        ):
            raise ValueError("actual_charge_usd must be non-negative or null")


@runtime_checkable
class ProviderAdapter(Protocol):
    """One transport attempt; wrapper code owns every retry."""

    name: str
    credential_environment_variable: str

    def complete(self, request: ProviderRequest) -> ProviderResponse:
        """Perform exactly one provider call with SDK retries disabled."""
