"""Controlled, smoke-only live execution with fail-closed artifacts and resume."""

from __future__ import annotations

import hashlib
import json
import os
import random
import re
import time
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from causalrisk.config import MethodConfig, validate_config
from causalrisk.data import LabelFreeItem
from causalrisk.parsing import parse_yesno
from causalrisk.pricing import (
    UsageBreakdown,
    missing_official_prices,
    normalized_list_cost_usd,
    waiver_allows_unpriced_provider,
)
from causalrisk.prompts import PromptBundle, render_prompt
from causalrisk.providers import ProviderAdapter, ProviderRequest
from causalrisk.retry import RUN_BLOCKING_CODES, ClassifiedFailure, call_with_retries
from causalrisk.topology import CallSpec, build_execution_plan

RUN_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
PROHIBITED_ARTIFACT_KEYS = frozenset(
    {"api_key", "authorization", "access_token", "secret", "credential", "password", "bearer"}
)
METHOD_ORDER = (
    "A1_SINGLE_V1",
    "A3_SINGLE_V1",
    "A5_SINGLE_V1",
    "C1_BOUNDARY_V1",
    "C3_COUNCIL_V1",
    "C5_COUNCIL_V1",
)


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


def _utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _assert_no_secret_keys(value: Any, path: str = "root") -> None:
    if isinstance(value, dict):
        for key, member in value.items():
            if str(key).casefold() in PROHIBITED_ARTIFACT_KEYS:
                raise ValueError(f"secret-bearing metadata is prohibited: {path}.{key}")
            _assert_no_secret_keys(member, f"{path}.{key}")
    elif isinstance(value, list | tuple):
        for index, member in enumerate(value):
            _assert_no_secret_keys(member, f"{path}[{index}]")


def _json_bytes(value: dict[str, Any]) -> bytes:
    _assert_no_secret_keys(value)
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")


def _write_temporary(path: Path, value: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    try:
        with temporary.open("xb") as stream:
            stream.write(_json_bytes(value))
    except FileExistsError as error:
        raise RuntimeError(f"stale temporary artifact blocks safe write: {temporary.name}") from error
    return temporary


def _atomic_create_json(path: Path, value: dict[str, Any]) -> None:
    if path.exists():
        raise RuntimeError(f"artifact already exists and cannot be overwritten: {path.name}")
    temporary = _write_temporary(path, value)
    if path.exists():
        temporary.unlink(missing_ok=True)
        raise RuntimeError(f"artifact already exists and cannot be overwritten: {path.name}")
    os.replace(temporary, path)


def _atomic_replace_json(path: Path, value: dict[str, Any]) -> None:
    if not path.is_file():
        raise RuntimeError(f"artifact required for atomic update is missing: {path.name}")
    temporary = _write_temporary(path, value)
    os.replace(temporary, path)


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError(f"artifact is missing or invalid: {path}") from error
    if not isinstance(value, dict):
        raise RuntimeError(f"artifact root is not an object: {path}")
    return value


def _item_set_sha256(items: tuple[LabelFreeItem, ...]) -> str:
    material = "\n".join(item.item_id for item in sorted(items, key=lambda value: value.item_id)).encode()
    return hashlib.sha256(material).hexdigest()


def _prepare_run(
    artifact_root: Path,
    run_id: str,
    *,
    split: str,
    configs: tuple[MethodConfig, ...],
    items: tuple[LabelFreeItem, ...],
    limits: ControllerLimits,
    pricing: dict[str, Any],
) -> tuple[Path, dict[str, Any]]:
    if not RUN_ID_PATTERN.fullmatch(run_id):
        raise ValueError("run_id contains unsafe characters")
    run_dir = artifact_root / run_id
    expected = {
        "schema_version": 1,
        "run_id": run_id,
        "split": split,
        "item_count": len(items),
        "item_set_sha256": _item_set_sha256(items),
        "config_ids": [config.config_id for config in configs],
        "pricing_version": pricing.get("version"),
        "limits": {
            "max_logical_calls": limits.max_logical_calls,
            "max_transport_attempts": limits.max_transport_attempts,
            "max_terminal_errors": limits.max_terminal_errors,
        },
    }
    manifest_path = run_dir / "manifest.json"
    if not run_dir.exists():
        run_dir.mkdir(parents=True)
        manifest = {
            **expected,
            "created_at_utc": _utc_now(),
            "completed_at_utc": None,
            "run_status": "in_progress",
            "freeze_state": "open",
        }
        _atomic_create_json(manifest_path, manifest)
        for config in configs:
            _atomic_create_json(run_dir / "configs" / f"{config.config_id}.json", config.values)
        return run_dir, manifest

    manifest = _read_json(manifest_path)
    if any(manifest.get(key) != value for key, value in expected.items()):
        raise RuntimeError("existing run manifest does not match the requested execution")
    if manifest.get("freeze_state") != "open" or manifest.get("run_status") != "in_progress":
        raise RuntimeError("existing run is terminal and cannot be resumed or overwritten")
    for config in configs:
        if _read_json(run_dir / "configs" / f"{config.config_id}.json") != config.values:
            raise RuntimeError(f"resolved config drift blocks resume: {config.config_id}")
    return run_dir, manifest


def _finish_run(run_dir: Path, manifest: dict[str, Any], *, status: str, summary: dict[str, Any]) -> None:
    _atomic_create_json(run_dir / "summary.json", summary)
    _atomic_replace_json(
        run_dir / "manifest.json",
        {
            **manifest,
            "completed_at_utc": _utc_now(),
            "run_status": status,
            "freeze_state": "frozen",
        },
    )


def canary_artifact_passed(
    artifact_root: Path, *, expected_items: tuple[LabelFreeItem, ...] | None = None
) -> bool:
    run_dir = artifact_root / "cladder-smoke-canary-3"
    try:
        manifest = _read_json(run_dir / "manifest.json")
        summary = _read_json(run_dir / "summary.json")
        expected_provider_calls = {
            "cloudflare_workers_ai": 3,
            "gemini": 3,
            "groq": 33,
            "nvidia_nim": 6,
            "openai": 6,
        }
        if not (
            manifest.get("run_id") == "cladder-smoke-canary-3"
            and manifest.get("split") == "smoke"
            and manifest.get("item_count") == 3
            and manifest.get("config_ids") == list(METHOD_ORDER)
            and manifest.get("run_status") == "complete"
            and manifest.get("freeze_state") == "frozen"
            and summary.get("terminal_errors") == 0
            and summary.get("completed_logical_calls") == 51
            and summary.get("expected_logical_calls") == 51
            and summary.get("provider_calls") == expected_provider_calls
            and isinstance(summary.get("transport_attempts"), int)
            and 51 <= summary["transport_attempts"] <= 204
        ):
            return False
        if expected_items is not None and manifest.get("item_set_sha256") != _item_set_sha256(expected_items):
            return False
        configs = {
            config_id: _read_json(run_dir / "configs" / f"{config_id}.json")
            for config_id in manifest.get("config_ids", [])
        }
        records = [_read_json(path) for path in (run_dir / "calls").glob("*/*.json")]
        attempts = [_read_json(path) for path in (run_dir / "attempts").glob("*/*.json")]
        if len(records) != 51 or len(attempts) != summary["transport_attempts"]:
            return False
        for record in records:
            config = configs[record["config_id"]]
            role = record["role"]
            expected_provider = config["provider_assignment"][role]
            expected_model = config["model_assignment"][role]
            if (
                record.get("status") != "success"
                or record.get("parsed_answer") not in {"YES", "NO"}
                or record.get("provider") != expected_provider
                or record.get("model_id") != expected_model
                or record.get("reported_model_id") not in {None, expected_model}
                or record.get("call_id")
                != logical_call_id(
                    "smoke", record["config_id"], record["item_id"], record["topology_position"]
                )
            ):
                return False
            if expected_provider == "nvidia_nim" and (
                record.get("normalized_list_cost_usd") is not None
                or record.get("actual_charge_usd") is not None
                or record.get("billing_mode") != "free_prototype"
            ):
                return False
            _assert_no_secret_keys(record)
        if any(attempt.get("status") not in {"success", "failure"} for attempt in attempts):
            return False
        for value in (manifest, summary, *configs.values(), *attempts):
            _assert_no_secret_keys(value)
    except (KeyError, RuntimeError, TypeError, ValueError):
        return False
    return True


def _output_schema(config_id: str, call: CallSpec) -> str:
    if config_id.startswith("A"):
        return "single_answer"
    if call.role == "analyst":
        return "analyst_card"
    return "adjudicator_record" if call.role == "adjudicator" else "critic_card"


def _load_existing_records(run_dir: Path, expected_call_ids: frozenset[str]) -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    calls_root = run_dir / "calls"
    for path in calls_root.glob("*/*.json") if calls_root.is_dir() else ():
        record = _read_json(path)
        call_id = record.get("call_id")
        if call_id != path.stem or call_id not in expected_call_ids:
            raise RuntimeError("unexpected call artifact blocks resume")
        if record.get("status") != "success" or not isinstance(record.get("raw_output"), str):
            raise RuntimeError("terminal or incomplete call artifact blocks resume")
        if call_id in records:
            raise RuntimeError("duplicate call artifact blocks resume")
        records[call_id] = record
    attempts_root = run_dir / "attempts"
    for path in attempts_root.glob("*/*.json") if attempts_root.is_dir() else ():
        attempt = _read_json(path)
        if attempt.get("status") == "started":
            raise RuntimeError("ambiguous in-flight transport attempt blocks automatic resume")
        if attempt.get("call_id") not in records:
            raise RuntimeError("transport completed without an atomic call artifact; automatic resume is blocked")
    return records


def _new_cost_stats(configs: tuple[MethodConfig, ...]) -> dict[str, dict[str, Any]]:
    return {
        config.config_id: {
            "successful_calls": 0,
            "priced_calls": 0,
            "priced_tokens": 0,
            "known_tokens": 0,
            "priced_cost_subtotal_usd": Decimal("0"),
            "has_null_normalized_cost": False,
            "actual_charge_reported_calls": 0,
            "actual_charge_subtotal_usd": Decimal("0"),
        }
        for config in configs
    }


def _accumulate_cost(stats: dict[str, Any], record: dict[str, Any]) -> None:
    stats["successful_calls"] += 1
    input_tokens = record.get("input_tokens")
    output_tokens = record.get("output_tokens")
    tokens = input_tokens + output_tokens if isinstance(input_tokens, int) and isinstance(output_tokens, int) else None
    if tokens is not None:
        stats["known_tokens"] += tokens
    normalized = record.get("normalized_list_cost_usd")
    if normalized is None:
        stats["has_null_normalized_cost"] = True
    else:
        stats["priced_calls"] += 1
        stats["priced_cost_subtotal_usd"] += Decimal(str(normalized))
        if tokens is not None:
            stats["priced_tokens"] += tokens
    actual = record.get("actual_charge_usd")
    if actual is not None:
        stats["actual_charge_reported_calls"] += 1
        stats["actual_charge_subtotal_usd"] += Decimal(str(actual))


def _cost_summary(stats_by_config: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    summary: dict[str, dict[str, Any]] = {}
    for config_id, stats in stats_by_config.items():
        successful = stats["successful_calls"]
        known_tokens = stats["known_tokens"]
        summary[config_id] = {
            "total_normalized_cost_usd": None
            if stats["has_null_normalized_cost"]
            else str(stats["priced_cost_subtotal_usd"]),
            "priced_cost_subtotal_usd": str(stats["priced_cost_subtotal_usd"]),
            "priced_call_coverage": stats["priced_calls"] / successful if successful else None,
            "priced_token_coverage": stats["priced_tokens"] / known_tokens if known_tokens else None,
            "actual_charge_usd": str(stats["actual_charge_subtotal_usd"])
            if successful and stats["actual_charge_reported_calls"] == successful
            else None,
            "actual_charge_reporting_coverage": stats["actual_charge_reported_calls"] / successful
            if successful
            else None,
        }
    return summary


def execute_smoke(
    *,
    split: str,
    authorized: bool,
    run_id: str,
    configs: tuple[MethodConfig, ...],
    items: tuple[LabelFreeItem, ...],
    adapters: dict[str, ProviderAdapter],
    pricing: dict[str, Any],
    prompt_bundle: PromptBundle,
    artifact_root: Path,
    limits: ControllerLimits,
    pacing: PacingPolicy,
    sleep: Callable[[float], None] = time.sleep,
    jitter: Callable[[float], float] = lambda seconds: random.uniform(0, seconds * 0.25),
) -> dict[str, Any]:
    if split != "smoke":
        raise ValueError("live controller permits only the smoke split")
    if not authorized:
        raise ValueError("explicit --authorize-live-smoke acknowledgement is required")
    if not items:
        raise ValueError("smoke execution requires at least one label-free item")
    if len({config.config_id for config in configs}) != len(configs):
        raise ValueError("duplicate method config is prohibited")
    configs = tuple(sorted(configs, key=lambda config: METHOD_ORDER.index(config.config_id)))
    for config in configs:
        validate_config(config.values, for_execution=True)
        if config.values["prompt_sha256"] != prompt_bundle.sha256:
            raise ValueError("prompt bundle differs from the execution config")

    plans = {config.config_id: build_execution_plan(config) for config in configs}
    expected_calls = sum(len(plans[config.config_id].calls) * len(items) for config in configs)
    if (
        limits.max_logical_calls != expected_calls
        or limits.max_transport_attempts != expected_calls * 4
        or limits.max_terminal_errors != 0
    ):
        raise ValueError("controller limits must equal the frozen logical, retry, and zero-error ceilings")
    if any(
        isinstance(value, bool) or not isinstance(value, int | float) or value < 0
        for value in pacing.minimum_interval_seconds.values()
    ):
        raise ValueError("provider pacing intervals must be non-negative")

    missing_prices = missing_official_prices(pricing)
    for config in configs:
        for role, provider in config.values["provider_assignment"].items():
            if provider not in adapters:
                raise ValueError(f"provider adapter is unavailable: {provider}")
            key = f"{provider}:{config.values['model_assignment'][role]}"
            if key not in pricing.get("models", {}):
                raise ValueError(f"pricing roster does not contain execution model: {key}")
            if key in missing_prices and not waiver_allows_unpriced_provider(
                pricing, key, config.values.get("allow_symbolic_unpriced_provider")
            ):
                raise ValueError(f"official pricing unavailable without valid waiver: {key}")

    sorted_items = tuple(sorted(items, key=lambda member: member.item_id))
    expected_ids = frozenset(
        logical_call_id(split, config.config_id, item.item_id, call.position)
        for config in configs
        for item in sorted_items
        for call in plans[config.config_id].calls
    )
    run_dir, manifest = _prepare_run(
        artifact_root,
        run_id,
        split=split,
        configs=configs,
        items=sorted_items,
        limits=limits,
        pricing=pricing,
    )
    completed = _load_existing_records(run_dir, expected_ids)
    attempts_root = run_dir / "attempts"
    attempt_count = len(list(attempts_root.glob("*/*.json"))) if attempts_root.is_dir() else 0
    logical_count = terminal_errors = 0
    provider_calls: Counter[str] = Counter()
    last_call_at: dict[str, float] = {}
    outputs: dict[tuple[str, str, int], str] = {}
    stats_by_config = _new_cost_stats(configs)

    for config in configs:
        plan = plans[config.config_id]
        for item in sorted_items:
            for call in plan.calls:
                call_id = logical_call_id(split, config.config_id, item.item_id, call.position)
                prior_record = completed.get(call_id)
                if prior_record is not None:
                    if (
                        prior_record.get("config_id") != config.config_id
                        or prior_record.get("item_id") != item.item_id
                        or prior_record.get("topology_position") != call.position
                    ):
                        raise RuntimeError("completed call metadata does not match the deterministic plan")
                    outputs[(config.config_id, item.item_id, call.position)] = prior_record["raw_output"]
                    _accumulate_cost(stats_by_config[config.config_id], prior_record)
                    provider_calls[prior_record["provider"]] += 1
                    continue

                logical_count += 1
                if logical_count > limits.max_logical_calls:
                    raise RuntimeError("maximum logical-call threshold exceeded")
                provider = config.values["provider_assignment"][call.role]
                adapter = adapters[provider]
                previous = tuple(
                    outputs[(config.config_id, item.item_id, position)] for position in call.upstream_positions
                )
                prompt = render_prompt(
                    prompt_bundle,
                    item=item,
                    role=call.role,
                    output_schema=_output_schema(config.config_id, call),
                    previous_responses=previous,
                    final_decision=True,
                )
                request = ProviderRequest(
                    prompt,
                    config.values["model_assignment"][call.role],
                    config.values["temperature"],
                    config.values["max_output_tokens"][call.role],
                    config.values.get("seed"),
                )
                retry_events = []

                def attempt(
                    attempt_index: int,
                    *,
                    selected_provider: str = provider,
                    selected_config_id: str = config.config_id,
                    selected_call_id: str = call_id,
                    selected_request: ProviderRequest = request,
                    selected_adapter: ProviderAdapter = adapter,
                ):
                    nonlocal attempt_count
                    interval = pacing.minimum_interval_seconds.get(selected_provider, 0.0)
                    elapsed = time.monotonic() - last_call_at.get(selected_provider, 0.0)
                    if elapsed < interval:
                        sleep(interval - elapsed)
                    attempt_count += 1
                    if attempt_count > limits.max_transport_attempts:
                        raise RuntimeError("maximum transport-attempt threshold exceeded")
                    attempt_path = (
                        run_dir / "attempts" / selected_config_id / f"{selected_call_id}-{attempt_index}.json"
                    )
                    attempt_record = {
                        "call_id": selected_call_id,
                        "attempt_index": attempt_index,
                        "provider": selected_provider,
                        "model_id": selected_request.model_id,
                        "started_at_utc": _utc_now(),
                        "status": "started",
                    }
                    _atomic_create_json(attempt_path, attempt_record)
                    last_call_at[selected_provider] = time.monotonic()
                    try:
                        response = selected_adapter.complete(selected_request)
                        if response.provider != selected_provider:
                            raise ClassifiedFailure("configuration/configuration_drift", "provider identity drift")
                        if response.requested_model_id != selected_request.model_id or (
                            response.reported_model_id is not None
                            and response.reported_model_id != selected_request.model_id
                        ):
                            raise ClassifiedFailure(
                                "configuration/configuration_drift", "provider model identity drift"
                            )
                        if selected_provider == "nvidia_nim" and response.actual_charge_usd is not None:
                            raise ClassifiedFailure(
                                "configuration/configuration_drift", "NVIDIA free-prototype billing mode drift"
                            )
                        if not response.text.strip():
                            raise ClassifiedFailure("response/empty_content", "provider returned empty content")
                    except ClassifiedFailure as failure:
                        _atomic_replace_json(
                            attempt_path,
                            {
                                **attempt_record,
                                "completed_at_utc": _utc_now(),
                                "status": "failure",
                                "failure_code": failure.failure_code,
                                "http_status": failure.http_status,
                                "provider_error_code": failure.provider_error_code,
                                "provider_error_type": failure.provider_error_type,
                                "provider_error_param": failure.provider_error_param,
                            },
                        )
                        raise
                    _atomic_replace_json(
                        attempt_path,
                        {
                            **attempt_record,
                            "completed_at_utc": _utc_now(),
                            "status": "success",
                            "http_status": response.http_status,
                            "response_id": response.response_id,
                            "input_tokens": response.usage.input_tokens,
                            "output_tokens": response.usage.output_tokens,
                            "reasoning_tokens": response.usage.reasoning_tokens,
                            "cached_input_tokens": response.usage.cached_input_tokens,
                            "actual_charge_usd": response.actual_charge_usd,
                        },
                    )
                    return response

                try:
                    response = call_with_retries(
                        attempt,
                        on_retry_event=retry_events.append,
                        sleep=lambda seconds: sleep(seconds + jitter(seconds)),
                    )
                    parsed = parse_yesno(response.text)
                    if parsed.answer == "INVALID":
                        raise ClassifiedFailure("invalid_label", "terminal malformed response")

                    input_tokens = response.usage.input_tokens
                    output_tokens = response.usage.output_tokens
                    pricing_key = f"{provider}:{request.model_id}"
                    waiver = config.values.get("allow_symbolic_unpriced_provider")
                    if input_tokens is None or output_tokens is None:
                        cost = None
                    else:
                        cost = normalized_list_cost_usd(
                            pricing,
                            pricing_key,
                            UsageBreakdown(
                                input_tokens,
                                output_tokens,
                                response.usage.cached_input_tokens or 0,
                                response.usage.reasoning_tokens or 0,
                            ),
                            allow_symbolic_unpriced_provider=waiver_allows_unpriced_provider(
                                pricing, pricing_key, waiver
                            ),
                        )
                    outputs[(config.config_id, item.item_id, call.position)] = response.text
                    record = {
                        "call_id": call_id,
                        "item_id": item.item_id,
                        "config_id": config.config_id,
                        "status": "success",
                        "provider": provider,
                        "model_id": request.model_id,
                        "reported_model_id": response.reported_model_id,
                        "role": call.role,
                        "topology_position": call.position,
                        "raw_output": response.text,
                        "parsed_answer": parsed.answer,
                        "normalization_actions": list(parsed.normalizations),
                        "input_tokens": input_tokens,
                        "output_tokens": output_tokens,
                        "reasoning_tokens": response.usage.reasoning_tokens,
                        "cached_input_tokens": response.usage.cached_input_tokens,
                        "total_tokens": response.usage.total_tokens,
                        "token_accounting_method": response.usage.accounting_method,
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
                                "provider_error_code": event.provider_error_code,
                                "provider_error_type": event.provider_error_type,
                                "provider_error_param": event.provider_error_param,
                            }
                            for event in retry_events
                        ],
                        "normalized_list_cost_usd": None if cost is None else str(cost),
                        "actual_charge_usd": response.actual_charge_usd,
                    }
                    if pricing_key in missing_prices:
                        record["billing_mode"] = pricing["models"][pricing_key].get("billing_mode")
                    _atomic_create_json(run_dir / "calls" / config.config_id / f"{call_id}.json", record)
                    _accumulate_cost(stats_by_config[config.config_id], record)
                    provider_calls[provider] += 1
                except ClassifiedFailure as failure:
                    terminal_errors += 1
                    last_attempt_index = retry_events[-1].attempt_index if retry_events else 0
                    retry_count = sum(1 for event in retry_events if event.decision.should_retry)
                    _atomic_create_json(
                        run_dir / "calls" / config.config_id / f"{call_id}.json",
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
                            "retry_count": retry_count,
                            "attempt_index": last_attempt_index,
                            "normalized_list_cost_usd": None,
                            "actual_charge_usd": None,
                        },
                    )
                    summary = {
                        "run_id": run_id,
                        "expected_logical_calls": expected_calls,
                        "completed_logical_calls": len(completed) + logical_count - 1,
                        "transport_attempts": attempt_count,
                        "terminal_errors": terminal_errors,
                        "failure_type": failure.failure_code,
                    }
                    _finish_run(run_dir, manifest, status="failed", summary=summary)
                    if failure.failure_code in RUN_BLOCKING_CODES:
                        raise RuntimeError(f"run-blocking provider failure: {failure.failure_code}") from None
                    raise RuntimeError("terminal-error threshold exceeded") from None

    result = {
        "run_id": run_id,
        "artifact_path": str(run_dir),
        "logical_calls": logical_count,
        "completed_logical_calls": len(completed) + logical_count,
        "expected_logical_calls": expected_calls,
        "transport_attempts": attempt_count,
        "terminal_errors": terminal_errors,
        "provider_calls": dict(sorted(provider_calls.items())),
        "cost_summary": _cost_summary(stats_by_config),
    }
    _finish_run(run_dir, manifest, status="complete", summary=result)
    return result
