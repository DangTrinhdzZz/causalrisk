"""Offline capacity and cost planning with explicit null propagation."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

from causalrisk.execution_policy import (
    MINIMUM_INTERVAL_SECONDS,
    PROVIDER_CALLS_PER_ITEM,
    PROVIDER_LIMIT_SNAPSHOT_VERSION,
    SplitExecutionPolicy,
)

LIMIT_FIELDS = ("RPM", "TPM", "RPD", "TPD")


class CapacityError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class LimitAssessment:
    violations: tuple[str, ...]
    warnings: tuple[str, ...]

    @property
    def passed(self) -> bool:
        return not self.violations


def load_provider_limits(path: str | Path) -> dict[str, Any]:
    document = json.loads(Path(path).read_text(encoding="utf-8"))
    providers = document.get("providers")
    if (
        document.get("schema_version") != 1
        or document.get("version") != PROVIDER_LIMIT_SNAPSHOT_VERSION
        or not isinstance(document.get("effective_at"), str)
        or not isinstance(document.get("scope"), str)
        or not isinstance(providers, dict)
        # The unchanged snapshot retains Gemini history; plans iterate only active providers.
        or set(providers) != set(PROVIDER_CALLS_PER_ITEM) | {"gemini"}
    ):
        raise CapacityError("provider-limit snapshot header or roster is invalid")
    for provider, limits in providers.items():
        if not isinstance(limits, dict) or set(limits) != {"source", *LIMIT_FIELDS}:
            raise CapacityError(f"provider-limit entry is invalid: {provider}")
        if not isinstance(limits["source"], str) or not limits["source"].strip():
            raise CapacityError(f"provider-limit source is invalid: {provider}")
        for field in LIMIT_FIELDS:
            value = limits[field]
            if value is not None and (isinstance(value, bool) or not isinstance(value, int) or value <= 0):
                raise CapacityError(f"provider-limit {field} must be a positive integer or null: {provider}")
    return document


def assess_provider_limits(
    policy: SplitExecutionPolicy,
    snapshot: dict[str, Any],
    *,
    projected_tokens: dict[str, int | None] | None = None,
    max_new_items: int | None = None,
) -> LimitAssessment:
    """Block known daily exceedance without a viable item-bounded pause plan."""

    violations: list[str] = []
    warnings: list[str] = []
    for provider, calls in policy.expected_provider_calls.items():
        limits = snapshot["providers"][provider]
        rpd = limits["RPD"]
        tpd = limits["TPD"]
        if rpd is None:
            warnings.append(f"{provider}:RPD_UNKNOWN")
        elif calls > rpd:
            batch_calls = None if max_new_items is None else max_new_items * PROVIDER_CALLS_PER_ITEM[provider]
            if batch_calls is None or batch_calls > rpd:
                violations.append(f"{provider}:PROJECTED_CALLS_EXCEED_RPD_WITHOUT_SAFE_BATCHING")
        if tpd is None:
            warnings.append(f"{provider}:TPD_UNKNOWN")
        else:
            projected = None if projected_tokens is None else projected_tokens.get(provider)
            if projected is None:
                warnings.append(f"{provider}:PROJECTED_DAILY_TOKENS_UNKNOWN")
            elif projected > tpd:
                per_item = projected / policy.item_count
                batch_tokens = None if max_new_items is None else math.ceil(per_item * max_new_items)
                if batch_tokens is None or batch_tokens > tpd:
                    violations.append(f"{provider}:PROJECTED_TOKENS_EXCEED_TPD_WITHOUT_SAFE_BATCHING")
    return LimitAssessment(tuple(violations), tuple(warnings))


def _project_from_empirical(total: int, observed_calls: int, target_calls: int) -> int | None:
    if observed_calls <= 0:
        return None
    return int((Decimal(total) * Decimal(target_calls) / Decimal(observed_calls)).to_integral_value())


def _project_decimal_from_empirical(total: str, observed_calls: int, target_calls: int) -> str | None:
    if observed_calls <= 0:
        return None
    projected = Decimal(total) * Decimal(target_calls) / Decimal(observed_calls)
    return str(projected.quantize(Decimal("0.00000001")))


def build_capacity_plan(
    policy: SplitExecutionPolicy,
    *,
    provider_limits: dict[str, Any],
    forensic_report: dict[str, Any],
    max_new_items: int | None = None,
) -> dict[str, Any]:
    """Build a no-network projection; absent evidence stays null."""

    empirical = forensic_report["provider_aggregates"]
    provider_plans: dict[str, Any] = {}
    for provider, calls in policy.expected_provider_calls.items():
        baseline = empirical.get(provider)
        if isinstance(baseline, dict) and baseline.get("successful_calls", 0) > 0:
            observed_calls = baseline["successful_calls"]
            tokens = baseline["tokens"]
            projected_tokens = {
                field: (
                    _project_from_empirical(tokens[field]["sum"], observed_calls, calls)
                    if tokens[field]["missing_calls"] == 0
                    else None
                )
                for field in ("input", "output", "reasoning", "cached_input")
            }
            latency_mean = baseline["successful_call_latency_ms"]["mean"]
        else:
            projected_tokens = {field: None for field in ("input", "output", "reasoning", "cached_input")}
            latency_mean = None
        if provider == "groq" and isinstance(baseline, dict):
            projected_cost = _project_decimal_from_empirical(
                forensic_report["cost"]["r1_recorded_normalized_list_cost_usd"],
                baseline["successful_calls"],
                calls,
            )
            cost_projection_method = "R1 successful-call normalized-list-cost mean scaled by logical calls"
        else:
            projected_cost = None
            cost_projection_method = None
        limits = provider_limits["providers"][provider]
        call_windows = math.ceil(calls / limits["RPM"]) if limits["RPM"] is not None else None
        call_days = math.ceil(calls / limits["RPD"]) if limits["RPD"] is not None else None
        provider_plans[provider] = {
            "logical_calls": calls,
            "transport_attempt_ceiling": calls * 4,
            "projected_tokens": projected_tokens,
            "projected_normalized_list_cost_usd": projected_cost,
            "normalized_cost_projection_method": cost_projection_method,
            "actual_charge_usd": None,
            "actual_charge_reporting_coverage": (
                forensic_report["cost"]["actual_charge_reporting_coverage"] if baseline is not None else None
            ),
            "empirical_success_latency_ms_mean": latency_mean,
            "estimated_account_limit_windows": call_windows,
            "estimated_account_limit_days": call_days,
        }
        if provider == "nvidia_nim":
            provider_plans[provider]["billing_mode"] = "free_prototype"

    spacing_horizons = [
        max(0, calls - 1) * MINIMUM_INTERVAL_SECONDS[provider]
        for provider, calls in policy.expected_provider_calls.items()
    ]
    projected_billable_tokens = {
        provider: (
            plan["projected_tokens"]["input"] + plan["projected_tokens"]["output"]
            if plan["projected_tokens"]["input"] is not None
            and plan["projected_tokens"]["output"] is not None
            else None
        )
        for provider, plan in provider_plans.items()
    }
    assessment = assess_provider_limits(
        policy,
        provider_limits,
        projected_tokens=projected_billable_tokens,
        max_new_items=max_new_items,
    )
    pacing_floor = max(spacing_horizons)
    return {
        "schema_version": 1,
        "mode": "offline_capacity_plan",
        "run_id": policy.run_id,
        "split": policy.split,
        "item_count": policy.item_count,
        "session_item_limit": max_new_items,
        "recommended_session_item_limit": policy.recommended_max_new_items,
        "logical_calls": policy.expected_logical_calls,
        "provider_calls": policy.expected_provider_calls,
        "transport_attempt_ceiling": policy.max_transport_attempts,
        "provider_limit_snapshot_version": provider_limits["version"],
        "provider_plans": provider_plans,
        "projected_total_tokens": None,
        "projected_normalized_list_cost_usd": None,
        "actual_charge_usd": None,
        "actual_charge_reporting_coverage": None,
        "providers_with_potential_actual_charge": [
            provider for provider in policy.expected_provider_calls if provider != "nvidia_nim"
        ],
        "pacing_only_runtime_floor_seconds": pacing_floor,
        "estimated_minimum_runtime_seconds": pacing_floor,
        "estimated_minimum_runtime_method": "pacing_only_lower_bound_excludes_transport_latency_and_backoff",
        "estimated_account_limit_windows": None,
        "estimated_account_limit_days": None,
        "limit_assessment": {
            "passed": assessment.passed,
            "violations": list(assessment.violations),
            "warnings": list(assessment.warnings),
        },
        "unknown_note": (
            "Cross-provider token, normalized-cost, actual-charge, window, and day totals remain null until "
            "provider-specific empirical usage and account limits are available; null is not zero."
        ),
    }
