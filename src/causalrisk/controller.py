"""Fail-closed smoke-only live controller; tests inject fake provider adapters."""

from __future__ import annotations

import hashlib
import json
import os
import random
import time
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from causalrisk.config import MethodConfig, validate_config
from causalrisk.data import LabelFreeItem
from causalrisk.parsing import parse_yesno
from causalrisk.pricing import UsageBreakdown, missing_official_prices, normalized_list_cost_usd
from causalrisk.providers import ProviderAdapter, ProviderRequest
from causalrisk.retry import ClassifiedFailure, call_with_retries
from causalrisk.topology import build_execution_plan


@dataclass(frozen=True, slots=True)
class ControllerLimits:
    max_logical_calls: int
    max_transport_attempts: int
    max_terminal_errors: int


@dataclass(frozen=True, slots=True)
class PacingPolicy:
    minimum_interval_seconds: dict[str, float]


def logical_call_id(split: str, config_id: str, item_id: str, position: int) -> str:
    material = f"call-v1:{split}:{config_id}:{item_id}:{position}".encode()
    return hashlib.sha256(material).hexdigest()[:32]


def _atomic_json(path: Path, value: dict) -> None:
    prohibited = {"api_key", "authorization", "secret", "credential", "password", "bearer"}
    if prohibited & {str(key).casefold() for key in value}:
        raise ValueError("secret-bearing metadata is prohibited")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def completed_call_ids(artifact_root: Path) -> frozenset[str]:
    completed = set()
    for path in artifact_root.glob("*/calls/*.json") if artifact_root.is_dir() else ():
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if value.get("status") == "success" and value.get("call_id") == path.stem:
            completed.add(path.stem)
    return frozenset(completed)


def execute_smoke(
    *,
    split: str,
    authorized: bool,
    configs: tuple[MethodConfig, ...],
    items: tuple[LabelFreeItem, ...],
    adapters: dict[str, ProviderAdapter],
    pricing: dict,
    artifact_root: Path,
    limits: ControllerLimits,
    pacing: PacingPolicy,
    sleep: Callable[[float], None] = time.sleep,
    jitter: Callable[[float], float] = lambda seconds: random.uniform(0, seconds * 0.25),
) -> dict:
    if split != "smoke":
        raise ValueError("live controller permits only the smoke split")
    if not authorized:
        raise ValueError("explicit --authorize-live-smoke acknowledgement is required")
    for config in configs:
        validate_config(config.values, for_execution=True)
    missing_prices = missing_official_prices(pricing)
    if missing_prices:
        raise ValueError(f"official pricing unavailable: {', '.join(missing_prices)}")

    completed = completed_call_ids(artifact_root)
    logical_count = attempt_count = terminal_errors = 0
    provider_calls: Counter[str] = Counter()
    last_call_at: dict[str, float] = {}
    outputs: dict[tuple[str, str, int], str] = {}

    for config in configs:
        plan = build_execution_plan(config)
        for item in sorted(items, key=lambda member: member.item_id):
            for call in plan.calls:
                call_id = logical_call_id(split, config.config_id, item.item_id, call.position)
                if call_id in completed:
                    continue
                logical_count += 1
                if logical_count > limits.max_logical_calls:
                    raise RuntimeError("maximum logical-call threshold exceeded")
                provider = config.values["provider_assignment"][call.role]
                adapter = adapters[provider]
                interval = pacing.minimum_interval_seconds.get(provider, 0.0)
                elapsed = time.monotonic() - last_call_at.get(provider, 0.0)
                if elapsed < interval:
                    sleep(interval - elapsed)
                previous = tuple(
                    outputs[(config.config_id, item.item_id, position)] for position in call.upstream_positions
                )
                prompt = "\n\n".join((*item.model_context().values(), *previous))
                request = ProviderRequest(
                    prompt,
                    config.values["model_assignment"][call.role],
                    config.values["temperature"],
                    config.values["max_output_tokens"][call.role],
                    config.values.get("seed"),
                )
                retry_events = []

                def attempt(
                    _attempt_index: int,
                    *,
                    selected_provider: str = provider,
                    selected_adapter: ProviderAdapter = adapter,
                    selected_request: ProviderRequest = request,
                ):
                    nonlocal attempt_count
                    attempt_count += 1
                    if attempt_count > limits.max_transport_attempts:
                        raise RuntimeError("maximum transport-attempt threshold exceeded")
                    last_call_at[selected_provider] = time.monotonic()
                    return selected_adapter.complete(selected_request)

                try:
                    response = call_with_retries(
                        attempt,
                        on_retry_event=retry_events.append,
                        sleep=lambda seconds: sleep(seconds + jitter(seconds)),
                    )
                    parsed = parse_yesno(response.text)
                    if parsed.answer == "INVALID":
                        raise ClassifiedFailure("invalid_label", "terminal malformed response")
                    usage = UsageBreakdown(
                        response.usage.input_tokens or 0,
                        response.usage.output_tokens or 0,
                        response.usage.cached_input_tokens or 0,
                        response.usage.reasoning_tokens or 0,
                    )
                    cost = normalized_list_cost_usd(pricing, f"{provider}:{request.model_id}", usage)
                    outputs[(config.config_id, item.item_id, call.position)] = response.text
                    record = {
                        "call_id": call_id,
                        "item_id": item.item_id,
                        "config_id": config.config_id,
                        "status": "success",
                        "provider": provider,
                        "model_id": request.model_id,
                        "role": call.role,
                        "topology_position": call.position,
                        "input_tokens": response.usage.input_tokens,
                        "output_tokens": response.usage.output_tokens,
                        "reasoning_tokens": response.usage.reasoning_tokens,
                        "cached_input_tokens": response.usage.cached_input_tokens,
                        "total_tokens": response.usage.total_tokens,
                        "latency_ms": response.latency_ms,
                        "finish_reason": response.finish_reason,
                        "retry_count": len(retry_events),
                        "attempt_index": len(retry_events),
                        "retry_events": [
                            {
                                "attempt_index": event.attempt_index,
                                "failure_code": event.failure_code,
                                "http_status": event.http_status,
                                "retry_eligible": event.decision.retry_eligible,
                                "backoff_seconds": event.decision.backoff_seconds,
                            }
                            for event in retry_events
                        ],
                        "normalized_list_cost_usd": str(cost),
                        "actual_charge_usd": response.actual_charge_usd,
                    }
                    _atomic_json(artifact_root / config.config_id / "calls" / f"{call_id}.json", record)
                    provider_calls[provider] += 1
                except ClassifiedFailure as failure:
                    terminal_errors += 1
                    _atomic_json(
                        artifact_root / config.config_id / "calls" / f"{call_id}.json",
                        {
                            "call_id": call_id,
                            "item_id": item.item_id,
                            "config_id": config.config_id,
                            "status": "failure",
                            "provider": provider,
                            "model_id": request.model_id,
                            "role": call.role,
                            "topology_position": call.position,
                            "failure_type": failure.failure_code,
                            "retry_count": len(retry_events),
                            "attempt_index": len(retry_events),
                            "normalized_list_cost_usd": None,
                            "actual_charge_usd": None,
                        },
                    )
                    if terminal_errors > limits.max_terminal_errors:
                        raise RuntimeError("terminal-error threshold exceeded") from None
    return {
        "logical_calls": logical_count,
        "transport_attempts": attempt_count,
        "terminal_errors": terminal_errors,
        "provider_calls": dict(provider_calls),
    }
