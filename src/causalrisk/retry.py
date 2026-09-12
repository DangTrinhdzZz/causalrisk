"""Wrapper-owned retry policy matching docs/retry_policy.md."""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import TypeVar

T = TypeVar("T")

MAX_RETRIES = 3
MAX_ATTEMPTS = 4
BACKOFF_SECONDS = {1: 1.0, 2: 2.0, 3: 4.0}
RETRY_ELIGIBLE_CODES = frozenset(
    {
        "transport",
        "transport/timeout",
        "provider/http_5xx",
        "provider/http_429",
        "response/empty_content",
    }
)
RUN_BLOCKING_CODES = frozenset(
    {
        "configuration/authentication",
        "configuration/malformed_request",
        "configuration/nonexistent_model",
        "configuration/quota_exhaustion",
        "configuration/configuration_drift",
    }
)


class ClassifiedFailure(RuntimeError):
    """A provider-neutral failure already mapped to the frozen taxonomy."""

    def __init__(
        self,
        failure_code: str,
        safe_message: str,
        *,
        http_status: int | None = None,
        retry_after_seconds: float | None = None,
        provider_error_code: str | None = None,
        provider_error_type: str | None = None,
        provider_error_param: str | None = None,
        finish_reason: str | None = None,
        latency_ms: float | None = None,
        response_id: str | None = None,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
        reasoning_tokens: int | None = None,
        cached_input_tokens: int | None = None,
        total_tokens: int | None = None,
        token_accounting_method: str | None = None,
        actual_charge_usd: float | None = None,
        safe_response_headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(safe_message)
        self.failure_code = failure_code
        self.safe_message = safe_message
        self.http_status = http_status
        self.retry_after_seconds = retry_after_seconds
        self.provider_error_code = provider_error_code
        self.provider_error_type = provider_error_type
        self.provider_error_param = provider_error_param
        self.finish_reason = finish_reason
        self.latency_ms = latency_ms
        self.response_id = response_id
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.reasoning_tokens = reasoning_tokens
        self.cached_input_tokens = cached_input_tokens
        self.total_tokens = total_tokens
        self.token_accounting_method = token_accounting_method
        self.actual_charge_usd = actual_charge_usd
        self.safe_response_headers = dict(safe_response_headers or {})


class RetryExhausted(ClassifiedFailure):
    """Raised after the fourth failed eligible attempt."""


@dataclass(frozen=True, slots=True)
class RetryDecision:
    retry_eligible: bool
    should_retry: bool
    next_attempt_index: int | None
    backoff_seconds: float
    resolution_action: str


@dataclass(frozen=True, slots=True)
class RetryEvent:
    attempt_index: int
    failure_code: str
    http_status: int | None
    decision: RetryDecision
    provider_error_code: str | None = None
    provider_error_type: str | None = None
    provider_error_param: str | None = None
    retry_after_seconds: float | None = None
    finish_reason: str | None = None
    latency_ms: float | None = None
    response_id: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    reasoning_tokens: int | None = None
    cached_input_tokens: int | None = None
    total_tokens: int | None = None
    token_accounting_method: str | None = None
    safe_response_headers: dict[str, str] | None = None


def decide_retry(failure: ClassifiedFailure, attempt_index: int) -> RetryDecision:
    if attempt_index < 0 or attempt_index >= MAX_ATTEMPTS:
        raise ValueError("attempt_index must be in the range 0..3")
    eligible = failure.failure_code in RETRY_ELIGIBLE_CODES
    should_retry = eligible and attempt_index < MAX_ATTEMPTS - 1
    next_attempt = attempt_index + 1 if should_retry else None
    backoff = 0.0
    if should_retry and next_attempt is not None:
        if failure.failure_code == "provider/http_429" and failure.retry_after_seconds is not None:
            if failure.retry_after_seconds < 0:
                raise ValueError("Retry-After must be non-negative")
            backoff = failure.retry_after_seconds
        else:
            backoff = BACKOFF_SECONDS[next_attempt]
    if should_retry:
        action = "retry"
    elif eligible:
        action = "fail_item"
    elif failure.failure_code in RUN_BLOCKING_CODES:
        action = "stop_run"
    elif failure.failure_code == "data/data_validation_failure":
        action = "quarantine_item"
    else:
        action = "record_failure"
    return RetryDecision(eligible, should_retry, next_attempt, backoff, action)


def call_with_retries(
    operation: Callable[[int], T],
    *,
    on_retry_event: Callable[[RetryEvent], None],
    sleep: Callable[[float], None] = time.sleep,
) -> T:
    """Execute one logical call with at most four fully observable attempts."""

    for attempt_index in range(MAX_ATTEMPTS):
        try:
            return operation(attempt_index)
        except ClassifiedFailure as failure:
            decision = decide_retry(failure, attempt_index)
            on_retry_event(
                RetryEvent(
                    attempt_index,
                    failure.failure_code,
                    failure.http_status,
                    decision,
                    failure.provider_error_code,
                    failure.provider_error_type,
                    failure.provider_error_param,
                    failure.retry_after_seconds,
                    failure.finish_reason,
                    failure.latency_ms,
                    failure.response_id,
                    failure.input_tokens,
                    failure.output_tokens,
                    failure.reasoning_tokens,
                    failure.cached_input_tokens,
                    failure.total_tokens,
                    failure.token_accounting_method,
                    failure.safe_response_headers,
                )
            )
            if not decision.should_retry:
                if decision.retry_eligible:
                    raise RetryExhausted(
                        failure.failure_code,
                        "eligible failure exhausted the fixed retry budget",
                        http_status=failure.http_status,
                        provider_error_code=failure.provider_error_code,
                        provider_error_type=failure.provider_error_type,
                        provider_error_param=failure.provider_error_param,
                        retry_after_seconds=failure.retry_after_seconds,
                        finish_reason=failure.finish_reason,
                        latency_ms=failure.latency_ms,
                        response_id=failure.response_id,
                        input_tokens=failure.input_tokens,
                        output_tokens=failure.output_tokens,
                        reasoning_tokens=failure.reasoning_tokens,
                        cached_input_tokens=failure.cached_input_tokens,
                        total_tokens=failure.total_tokens,
                        token_accounting_method=failure.token_accounting_method,
                        actual_charge_usd=failure.actual_charge_usd,
                        safe_response_headers=failure.safe_response_headers,
                    ) from failure
                raise
            sleep(decision.backoff_seconds)
    raise AssertionError("unreachable retry state")
