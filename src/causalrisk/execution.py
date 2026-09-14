"""Amendment 008 final cross-split execution core with fail-closed R5 lineage."""

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
from causalrisk.execution_policy import (
    EXECUTION_REVISION,
    METHOD_ORDER,
    MINIMUM_INTERVAL_SECONDS,
    PROVIDER_LIMIT_SNAPSHOT_VERSION,
    SMOKE_CANARY_POLICY,
    SOURCE_MANIFEST_SHA256,
    VIEW_SCHEMA_VERSION,
    SplitExecutionPolicy,
)
from causalrisk.lineage import artifact_tree_sha256, file_sha256_bytes, verify_r4_remediation_input
from causalrisk.parsing import parse_yesno
from causalrisk.pricing import (
    UsageBreakdown,
    missing_official_prices,
    normalized_list_cost_usd,
    waiver_allows_unpriced_provider,
)
from causalrisk.prompts import PromptBundle, file_sha256, render_prompt
from causalrisk.providers import ProviderAdapter, ProviderRequest
from causalrisk.retry import RUN_BLOCKING_CODES, ClassifiedFailure, RetryEvent, call_with_retries
from causalrisk.topology import CallSpec, build_execution_plan

COMMIT_PATTERN = re.compile(r"^[0-9a-f]{40}$")
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
PROHIBITED_ARTIFACT_KEYS = frozenset(
    {"api_key", "api_token", "authorization", "access_token", "secret", "credential", "password", "bearer"}
)


@dataclass(frozen=True, slots=True)
class PacingPolicy:
    minimum_interval_seconds: dict[str, float]


@dataclass(frozen=True, slots=True)
class ExecutionLineage:
    code_commit: str
    source_manifest_sha256: str
    inference_view_sha256: str
    inference_view_schema_version: int
    selection_sha256: str | None
    config_sha256: dict[str, str]
    prompt_sha256: str
    pricing_version: str
    provider_limit_snapshot_version: str
    predecessor_gate: dict[str, Any]


def logical_call_id(split: str, config_id: str, item_id: str, position: int) -> str:
    material = f"call-v2:{EXECUTION_REVISION}:{split}:{config_id}:{item_id}:{position}".encode()
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


def _assert_resume_inventory(run_dir: Path, config_ids: frozenset[str]) -> None:
    """Reject files outside the fixed artifact layout before trusting a paused run."""

    for path in run_dir.rglob("*"):
        if not path.is_file():
            continue
        parts = path.relative_to(run_dir).parts
        allowed = parts in {("manifest.json",), ("summary.json",)}
        allowed = allowed or (
            len(parts) == 2
            and parts[0] == "configs"
            and Path(parts[1]).suffix == ".json"
            and Path(parts[1]).stem in config_ids
        )
        allowed = allowed or (
            len(parts) == 3
            and parts[0] in {"calls", "attempts"}
            and parts[1] in config_ids
            and Path(parts[2]).suffix == ".json"
        )
        allowed = allowed or (
            len(parts) == 2
            and parts[0] == "sessions"
            and re.fullmatch(r"session-[0-9]{4}\.json", parts[1]) is not None
        )
        if not allowed:
            raise RuntimeError(f"unexpected artifact blocks safe resume: {path.name}")
        _assert_no_secret_keys(_read_json(path))


def _item_set_sha256(items: tuple[LabelFreeItem, ...]) -> str:
    material = "\n".join(item.item_id for item in sorted(items, key=lambda value: value.item_id)).encode()
    return hashlib.sha256(material).hexdigest()


def _topology_manifest(policy: SplitExecutionPolicy) -> dict[str, Any]:
    return {
        "ordering": "item_major_v2",
        "method_calls": policy.expected_method_calls,
        "provider_calls": policy.expected_provider_calls,
        "c1_alias_of": "A1_SINGLE_V1",
        "c1_additional_calls": 0,
    }


def _expected_manifest(
    policy: SplitExecutionPolicy,
    configs: tuple[MethodConfig, ...],
    items: tuple[LabelFreeItem, ...],
    lineage: ExecutionLineage,
) -> dict[str, Any]:
    return {
        "schema_version": 2,
        "run_id": policy.run_id,
        "split": policy.split,
        "item_count": policy.item_count,
        "item_set_sha256": _item_set_sha256(items),
        "config_ids": [config.config_id for config in configs],
        "code_commit": lineage.code_commit,
        "execution_revision": EXECUTION_REVISION,
        "source_manifest_sha256": lineage.source_manifest_sha256,
        "inference_view_sha256": lineage.inference_view_sha256,
        "inference_view_schema_version": lineage.inference_view_schema_version,
        "selection_sha256": lineage.selection_sha256,
        "config_sha256": lineage.config_sha256,
        "prompt_sha256": lineage.prompt_sha256,
        "pricing_version": lineage.pricing_version,
        "provider_limit_snapshot_version": lineage.provider_limit_snapshot_version,
        "expected_call_topology": _topology_manifest(policy),
        "predecessor_gate": lineage.predecessor_gate,
        "limits": {
            "max_logical_calls": policy.expected_logical_calls,
            "max_transport_attempts": policy.max_transport_attempts,
            "max_terminal_errors": 0,
        },
    }


def _prepare_run(
    artifact_root: Path,
    *,
    policy: SplitExecutionPolicy,
    configs: tuple[MethodConfig, ...],
    items: tuple[LabelFreeItem, ...],
    lineage: ExecutionLineage,
) -> tuple[Path, dict[str, Any]]:
    run_dir = artifact_root / policy.run_id
    expected = _expected_manifest(policy, configs, items, lineage)
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

    if any(run_dir.rglob("*.tmp")):
        raise RuntimeError("stale temporary artifact blocks safe resume")
    _assert_resume_inventory(run_dir, frozenset(config.config_id for config in configs))
    manifest = _read_json(manifest_path)
    if any(manifest.get(key) != value for key, value in expected.items()):
        raise RuntimeError("existing run manifest lineage does not match the requested execution")
    if manifest.get("freeze_state") == "frozen" or manifest.get("run_status") in {"complete", "failed"}:
        raise RuntimeError("existing run is terminal and cannot be resumed or overwritten")
    if manifest.get("freeze_state") != "open" or manifest.get("run_status") != "paused":
        raise RuntimeError("only a planned paused/open run may be resumed")
    if (run_dir / "summary.json").exists():
        raise RuntimeError("non-terminal run unexpectedly contains a terminal summary")
    for config in configs:
        if _read_json(run_dir / "configs" / f"{config.config_id}.json") != config.values:
            raise RuntimeError(f"resolved config drift blocks resume: {config.config_id}")
    manifest = {**manifest, "run_status": "in_progress", "completed_at_utc": None}
    _atomic_replace_json(manifest_path, manifest)
    return run_dir, manifest


def _finish_run(run_dir: Path, manifest: dict[str, Any], *, status: str, summary: dict[str, Any]) -> None:
    if status not in {"complete", "failed"}:
        raise ValueError("terminal run status must be complete or failed")
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


def _pause_run(run_dir: Path, manifest: dict[str, Any]) -> None:
    _atomic_replace_json(
        run_dir / "manifest.json",
        {**manifest, "completed_at_utc": None, "run_status": "paused", "freeze_state": "open"},
    )


def _load_existing_records(
    run_dir: Path,
    expected_calls: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    calls_root = run_dir / "calls"
    for path in calls_root.glob("*/*.json") if calls_root.is_dir() else ():
        record = _read_json(path)
        call_id = record.get("call_id")
        if call_id != path.stem or call_id not in expected_calls:
            raise RuntimeError("unexpected call artifact blocks resume")
        expected = expected_calls[call_id]
        required = {
            "finish_reason",
            "latency_ms",
            "input_tokens",
            "output_tokens",
            "reasoning_tokens",
            "cached_input_tokens",
            "total_tokens",
            "http_status",
            "response_id",
            "retry_count",
            "attempt_index",
            "retry_events",
            "safe_response_headers",
            "normalized_list_cost_usd",
            "actual_charge_usd",
        }
        if (
            record.get("status") != "success"
            or not isinstance(record.get("raw_output"), str)
            or record.get("parsed_answer") not in {"YES", "NO"}
            or not required.issubset(record)
            or any(record.get(key) != value for key, value in expected.items())
            or record.get("reported_model_id") not in {None, expected["model_id"]}
            or not isinstance(record.get("retry_events"), list)
            or isinstance(record.get("attempt_index"), bool)
            or not isinstance(record.get("attempt_index"), int)
            or record["attempt_index"] < 0
            or isinstance(record.get("retry_count"), bool)
            or not isinstance(record.get("retry_count"), int)
            or record["retry_count"] < 0
        ):
            raise RuntimeError("terminal or incomplete call artifact blocks resume")
        if expected["provider"] == "nvidia_nim" and (
            record.get("normalized_list_cost_usd") is not None
            or record.get("actual_charge_usd") is not None
            or record.get("billing_mode") != "free_prototype"
        ):
            raise RuntimeError("NVIDIA symbolic-null accounting drift blocks resume")
        if call_id in records:
            raise RuntimeError("duplicate call artifact blocks resume")
        records[call_id] = record
    attempts_root = run_dir / "attempts"
    attempts_by_call: dict[str, list[dict[str, Any]]] = {}
    for path in attempts_root.glob("*/*.json") if attempts_root.is_dir() else ():
        attempt = _read_json(path)
        if attempt.get("status") == "started" or not attempt.get("completed_at_utc"):
            raise RuntimeError("ambiguous in-flight transport attempt blocks automatic resume")
        if attempt.get("status") not in {"success", "failure"}:
            raise RuntimeError("invalid transport-attempt state blocks resume")
        call_id = attempt.get("call_id")
        if call_id not in records:
            raise RuntimeError("transport completed without an atomic call artifact; automatic resume is blocked")
        expected = expected_calls[call_id]
        attempt_required = {
            "completed_at_utc",
            "finish_reason",
            "latency_ms",
            "input_tokens",
            "output_tokens",
            "reasoning_tokens",
            "cached_input_tokens",
            "total_tokens",
            "http_status",
            "response_id",
            "safe_response_headers",
        }
        if (
            attempt.get("run_id") != expected["run_id"]
            or attempt.get("provider") != expected["provider"]
            or attempt.get("model_id") != expected["model_id"]
            or not attempt_required.issubset(attempt)
            or isinstance(attempt.get("attempt_index"), bool)
            or not isinstance(attempt.get("attempt_index"), int)
            or attempt["attempt_index"] < 0
        ):
            raise RuntimeError("transport-attempt lineage drift blocks resume")
        attempts_by_call.setdefault(call_id, []).append(attempt)
    for call_id, record in records.items():
        attempts = attempts_by_call.get(call_id, [])
        indices = sorted(attempt["attempt_index"] for attempt in attempts)
        if indices != list(range(record.get("attempt_index", 0) + 1)):
            raise RuntimeError("attempt chain is incomplete or non-deterministic")
        final_attempt = next(attempt for attempt in attempts if attempt["attempt_index"] == indices[-1])
        if (
            final_attempt.get("status") != "success"
            or record.get("retry_count") != len(indices) - 1
            or len(record["retry_events"]) != len(indices) - 1
        ):
            raise RuntimeError("completed call retry history differs from its attempt chain")
    return records


def _output_schema(config_id: str, call: CallSpec) -> str:
    if config_id.startswith("A"):
        return "single_answer"
    if call.role == "analyst":
        return "analyst_card"
    return "adjudicator_record" if call.role == "adjudicator" else "critic_card"


def _retry_event_record(event: RetryEvent) -> dict[str, Any]:
    return {
        "attempt_index": event.attempt_index,
        "failure_code": event.failure_code,
        "http_status": event.http_status,
        "retry_eligible": event.decision.retry_eligible,
        "should_retry": event.decision.should_retry,
        "backoff_seconds": event.decision.backoff_seconds,
        "retry_after_seconds": event.retry_after_seconds,
        "resolution_action": event.decision.resolution_action,
        "provider_error_code": event.provider_error_code,
        "provider_error_type": event.provider_error_type,
        "provider_error_param": event.provider_error_param,
        "finish_reason": event.finish_reason,
        "latency_ms": event.latency_ms,
        "response_id": event.response_id,
        "input_tokens": event.input_tokens,
        "output_tokens": event.output_tokens,
        "reasoning_tokens": event.reasoning_tokens,
        "cached_input_tokens": event.cached_input_tokens,
        "total_tokens": event.total_tokens,
        "token_accounting_method": event.token_accounting_method,
        "safe_response_headers": event.safe_response_headers or {},
    }


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
            "total_normalized_cost_usd": (
                None if stats["has_null_normalized_cost"] else str(stats["priced_cost_subtotal_usd"])
            ),
            "priced_cost_subtotal_usd": str(stats["priced_cost_subtotal_usd"]),
            "priced_call_coverage": stats["priced_calls"] / successful if successful else None,
            "priced_token_coverage": stats["priced_tokens"] / known_tokens if known_tokens else None,
            "actual_charge_usd": (
                str(stats["actual_charge_subtotal_usd"])
                if successful and stats["actual_charge_reported_calls"] == successful
                else None
            ),
            "actual_charge_reporting_coverage": (
                stats["actual_charge_reported_calls"] / successful if successful else None
            ),
        }
    return summary


def _normalized_cost(
    pricing: dict[str, Any],
    pricing_key: str,
    *,
    input_tokens: int | None,
    output_tokens: int | None,
    reasoning_tokens: int | None,
    cached_input_tokens: int | None,
    waiver: Any,
) -> Decimal | None:
    if None in {input_tokens, output_tokens, reasoning_tokens, cached_input_tokens}:
        return None
    return normalized_list_cost_usd(
        pricing,
        pricing_key,
        UsageBreakdown(input_tokens, output_tokens, cached_input_tokens, reasoning_tokens),
        allow_symbolic_unpriced_provider=waiver_allows_unpriced_provider(pricing, pricing_key, waiver),
    )


def _validate_execution_inputs(
    *,
    policy: SplitExecutionPolicy,
    authorization_flag: str | None,
    configs: tuple[MethodConfig, ...],
    items: tuple[LabelFreeItem, ...],
    pricing: dict[str, Any],
    prompt_bundle: PromptBundle,
    adapters: dict[str, ProviderAdapter],
    pacing: PacingPolicy,
    lineage: ExecutionLineage,
    max_new_items: int | None,
) -> tuple[MethodConfig, ...]:
    if not policy.live_authorized:
        raise ValueError(f"{policy.split} live execution is BLOCKED_NOT_AUTHORIZED")
    if authorization_flag != policy.authorization_flag:
        raise ValueError(f"exact split authorization is required: {policy.authorization_flag}")
    if len(items) != policy.item_count:
        raise ValueError("inference item count differs from the fixed run policy")
    if max_new_items is not None and (
        isinstance(max_new_items, bool) or not isinstance(max_new_items, int) or not 1 <= max_new_items <= len(items)
    ):
        raise ValueError("max_new_items must be a positive bound within the full run item count")
    if policy.canary and max_new_items is not None:
        raise ValueError("the fixed canary does not accept a session item bound")
    if not COMMIT_PATTERN.fullmatch(lineage.code_commit):
        raise ValueError("code_commit must be the exact 40-character Git commit")
    if lineage.source_manifest_sha256 != SOURCE_MANIFEST_SHA256[policy.split]:
        raise ValueError("source-manifest lineage differs from the frozen split")
    if not SHA256_PATTERN.fullmatch(lineage.inference_view_sha256):
        raise ValueError("inference-view lineage must be an exact SHA-256")
    if lineage.inference_view_schema_version != VIEW_SCHEMA_VERSION:
        raise ValueError("inference-view schema differs from the execution revision")
    if policy.canary != (lineage.selection_sha256 is not None):
        raise ValueError("canary selection lineage does not match the fixed run policy")
    if lineage.selection_sha256 is not None and not SHA256_PATTERN.fullmatch(lineage.selection_sha256):
        raise ValueError("canary selector lineage must be an exact SHA-256")
    if (
        not lineage.predecessor_gate.get("verified")
        or lineage.predecessor_gate.get("run_id") != policy.predecessor_run_id
        or lineage.predecessor_gate.get("requirement") != policy.predecessor_requirement
    ):
        raise ValueError("required predecessor gate is not verified")
    if lineage.pricing_version != pricing.get("version"):
        raise ValueError("pricing lineage differs from the loaded pricing snapshot")
    if lineage.provider_limit_snapshot_version != PROVIDER_LIMIT_SNAPSHOT_VERSION:
        raise ValueError("provider-limit lineage differs from the execution revision")
    if lineage.prompt_sha256 != prompt_bundle.sha256:
        raise ValueError("prompt lineage differs from the loaded prompt bundle")
    if pacing.minimum_interval_seconds != MINIMUM_INTERVAL_SECONDS:
        raise ValueError("pacing must equal the frozen Amendment 005 provider policy")
    configs = tuple(sorted(configs, key=lambda config: METHOD_ORDER.index(config.config_id)))
    if tuple(config.config_id for config in configs) != METHOD_ORDER:
        raise ValueError("execution requires the exact six-config frozen roster")
    actual_config_sha256 = {config.config_id: file_sha256(config.source) for config in configs}
    if lineage.config_sha256 != actual_config_sha256:
        raise ValueError("config checksum lineage differs from the loaded configs")
    plans = {config.config_id: build_execution_plan(config) for config in configs}
    method_counts = {key: len(plan.calls) * len(items) for key, plan in plans.items()}
    if method_counts != policy.expected_method_calls:
        raise ValueError("method-call topology differs from the execution policy")
    provider_counts: Counter[str] = Counter()
    missing_prices = missing_official_prices(pricing)
    for config in configs:
        validate_config(config.values, for_execution=True)
        if config.values["prompt_sha256"] != prompt_bundle.sha256:
            raise ValueError("prompt bundle differs from the execution config")
        for call in plans[config.config_id].calls:
            provider = config.values["provider_assignment"][call.role]
            if provider not in adapters:
                raise ValueError(f"provider adapter is unavailable: {provider}")
            pricing_key = f"{provider}:{config.values['model_assignment'][call.role]}"
            if pricing_key not in pricing.get("models", {}):
                raise ValueError(f"pricing roster does not contain execution model: {pricing_key}")
            if pricing_key in missing_prices and not waiver_allows_unpriced_provider(
                pricing, pricing_key, config.values.get("allow_symbolic_unpriced_provider")
            ):
                raise ValueError(f"official pricing unavailable without valid waiver: {pricing_key}")
            provider_counts[provider] += len(items)
    if dict(sorted(provider_counts.items())) != policy.expected_provider_calls:
        raise ValueError("provider-call topology differs from the execution policy")
    return configs


def _attempt_count(run_dir: Path) -> int:
    root = run_dir / "attempts"
    return len(list(root.glob("*/*.json"))) if root.is_dir() else 0


def _session_record(run_dir: Path, value: dict[str, Any]) -> None:
    sessions = run_dir / "sessions"
    index = len(list(sessions.glob("session-*.json"))) if sessions.is_dir() else 0
    _atomic_create_json(sessions / f"session-{index:04d}.json", value)


def execute_split(
    *,
    policy: SplitExecutionPolicy,
    authorization_flag: str | None,
    configs: tuple[MethodConfig, ...],
    items: tuple[LabelFreeItem, ...],
    adapters: dict[str, ProviderAdapter],
    pricing: dict[str, Any],
    prompt_bundle: PromptBundle,
    artifact_root: Path,
    pacing: PacingPolicy,
    lineage: ExecutionLineage,
    max_new_items: int | None = None,
    sleep: Callable[[float], None] = time.sleep,
    jitter: Callable[[float], float] = lambda seconds: random.uniform(0, seconds * 0.25),
) -> dict[str, Any]:
    configs = _validate_execution_inputs(
        policy=policy,
        authorization_flag=authorization_flag,
        configs=configs,
        items=items,
        pricing=pricing,
        prompt_bundle=prompt_bundle,
        adapters=adapters,
        pacing=pacing,
        lineage=lineage,
        max_new_items=max_new_items,
    )
    sorted_items = tuple(sorted(items, key=lambda item: item.item_id))
    plans = {config.config_id: build_execution_plan(config) for config in configs}
    expected_calls = {
        logical_call_id(policy.split, config.config_id, item.item_id, call.position): {
            "run_id": policy.run_id,
            "item_id": item.item_id,
            "config_id": config.config_id,
            "provider": config.values["provider_assignment"][call.role],
            "model_id": config.values["model_assignment"][call.role],
            "role": call.role,
            "topology_position": call.position,
        }
        for item in sorted_items
        for config in configs
        for call in plans[config.config_id].calls
    }
    run_dir, manifest = _prepare_run(
        artifact_root,
        policy=policy,
        configs=configs,
        items=sorted_items,
        lineage=lineage,
    )
    completed = _load_existing_records(run_dir, expected_calls)
    attempt_count = _attempt_count(run_dir)
    provider_calls: Counter[str] = Counter(record["provider"] for record in completed.values())
    stats_by_config = _new_cost_stats(configs)
    for record in completed.values():
        _accumulate_cost(stats_by_config[record["config_id"]], record)

    calls_by_item = {
        item.item_id: frozenset(
            logical_call_id(policy.split, config.config_id, item.item_id, call.position)
            for config in configs
            for call in plans[config.config_id].calls
        )
        for item in sorted_items
    }
    incomplete_items = tuple(
        item for item in sorted_items if not calls_by_item[item.item_id].issubset(completed.keys())
    )
    if any(calls_by_item[item.item_id] & completed.keys() for item in incomplete_items):
        raise RuntimeError("partial item topology blocks deterministic planned-pause resume")
    selected_items = incomplete_items[:max_new_items] if max_new_items is not None else incomplete_items
    session_started = _utc_now()
    last_call_at: dict[str, float] = {}
    session_new_calls = 0
    session_new_items = 0

    for item in selected_items:
        outputs: dict[tuple[str, int], str] = {}
        for config in configs:
            for call in plans[config.config_id].calls:
                call_id = logical_call_id(policy.split, config.config_id, item.item_id, call.position)
                prior_record = completed.get(call_id)
                if prior_record is not None:
                    if (
                        prior_record.get("config_id") != config.config_id
                        or prior_record.get("item_id") != item.item_id
                        or prior_record.get("topology_position") != call.position
                    ):
                        raise RuntimeError("completed call metadata does not match the deterministic plan")
                    outputs[(config.config_id, call.position)] = prior_record["raw_output"]
                    continue

                if len(completed) + session_new_calls + 1 > policy.expected_logical_calls:
                    raise RuntimeError("maximum logical-call threshold exceeded")
                provider = config.values["provider_assignment"][call.role]
                request = ProviderRequest(
                    render_prompt(
                        prompt_bundle,
                        item=item,
                        role=call.role,
                        output_schema=_output_schema(config.config_id, call),
                        previous_responses=tuple(
                            outputs[(config.config_id, position)] for position in call.upstream_positions
                        ),
                        final_decision=True,
                    ),
                    config.values["model_assignment"][call.role],
                    config.values["temperature"],
                    config.values["max_output_tokens"][call.role],
                    config.values.get("seed"),
                )
                retry_events: list[RetryEvent] = []

                def attempt(
                    attempt_index: int,
                    *,
                    selected_provider: str = provider,
                    selected_config_id: str = config.config_id,
                    selected_call_id: str = call_id,
                    selected_request: ProviderRequest = request,
                    selected_adapter: ProviderAdapter = adapters[provider],
                ):
                    nonlocal attempt_count
                    interval = pacing.minimum_interval_seconds[selected_provider]
                    elapsed = time.monotonic() - last_call_at.get(selected_provider, 0.0)
                    if elapsed < interval:
                        sleep(interval - elapsed)
                    attempt_count += 1
                    if attempt_count > policy.max_transport_attempts:
                        raise RuntimeError("maximum transport-attempt threshold exceeded")
                    attempt_path = (
                        run_dir / "attempts" / selected_config_id / f"{selected_call_id}-{attempt_index}.json"
                    )
                    attempt_record = {
                        "run_id": policy.run_id,
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
                            raise ClassifiedFailure(
                                "response/empty_content",
                                "provider returned empty content",
                                http_status=response.http_status,
                                finish_reason=response.finish_reason,
                                latency_ms=response.latency_ms,
                                response_id=response.response_id,
                                input_tokens=response.usage.input_tokens,
                                output_tokens=response.usage.output_tokens,
                                reasoning_tokens=response.usage.reasoning_tokens,
                                cached_input_tokens=response.usage.cached_input_tokens,
                                total_tokens=response.usage.total_tokens,
                                token_accounting_method=response.usage.accounting_method,
                                actual_charge_usd=response.actual_charge_usd,
                                safe_response_headers=response.safe_response_headers,
                            )
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
                                "finish_reason": failure.finish_reason,
                                "latency_ms": failure.latency_ms,
                                "response_id": failure.response_id,
                                "input_tokens": failure.input_tokens,
                                "output_tokens": failure.output_tokens,
                                "reasoning_tokens": failure.reasoning_tokens,
                                "cached_input_tokens": failure.cached_input_tokens,
                                "total_tokens": failure.total_tokens,
                                "token_accounting_method": failure.token_accounting_method,
                                "actual_charge_usd": failure.actual_charge_usd,
                                "retry_after_seconds": failure.retry_after_seconds,
                                "safe_response_headers": failure.safe_response_headers,
                            },
                        )
                        raise
                    _atomic_replace_json(
                        attempt_path,
                        {
                            **attempt_record,
                            "completed_at_utc": _utc_now(),
                            "status": "success",
                            "failure_code": None,
                            "http_status": response.http_status,
                            "response_id": response.response_id,
                            "finish_reason": response.finish_reason,
                            "latency_ms": response.latency_ms,
                            "input_tokens": response.usage.input_tokens,
                            "output_tokens": response.usage.output_tokens,
                            "reasoning_tokens": response.usage.reasoning_tokens,
                            "cached_input_tokens": response.usage.cached_input_tokens,
                            "total_tokens": response.usage.total_tokens,
                            "token_accounting_method": response.usage.accounting_method,
                            "actual_charge_usd": response.actual_charge_usd,
                            "retry_after_seconds": None,
                            "safe_response_headers": response.safe_response_headers,
                        },
                    )
                    return response

                response = None
                try:
                    response = call_with_retries(
                        attempt,
                        on_retry_event=retry_events.append,
                        sleep=lambda seconds: sleep(seconds + jitter(seconds)),
                    )
                    parsed = parse_yesno(response.text)
                    if parsed.answer == "INVALID":
                        raise ClassifiedFailure(
                            "invalid_label",
                            "terminal malformed response",
                            http_status=response.http_status,
                            finish_reason=response.finish_reason,
                            latency_ms=response.latency_ms,
                            response_id=response.response_id,
                            input_tokens=response.usage.input_tokens,
                            output_tokens=response.usage.output_tokens,
                            reasoning_tokens=response.usage.reasoning_tokens,
                            cached_input_tokens=response.usage.cached_input_tokens,
                            total_tokens=response.usage.total_tokens,
                            token_accounting_method=response.usage.accounting_method,
                            actual_charge_usd=response.actual_charge_usd,
                            safe_response_headers=response.safe_response_headers,
                        )
                    pricing_key = f"{provider}:{request.model_id}"
                    cost = _normalized_cost(
                        pricing,
                        pricing_key,
                        input_tokens=response.usage.input_tokens,
                        output_tokens=response.usage.output_tokens,
                        reasoning_tokens=response.usage.reasoning_tokens,
                        cached_input_tokens=response.usage.cached_input_tokens,
                        waiver=config.values.get("allow_symbolic_unpriced_provider"),
                    )
                    record = {
                        "run_id": policy.run_id,
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
                        "input_tokens": response.usage.input_tokens,
                        "output_tokens": response.usage.output_tokens,
                        "reasoning_tokens": response.usage.reasoning_tokens,
                        "cached_input_tokens": response.usage.cached_input_tokens,
                        "total_tokens": response.usage.total_tokens,
                        "token_accounting_method": response.usage.accounting_method,
                        "latency_ms": response.latency_ms,
                        "finish_reason": response.finish_reason,
                        "http_status": response.http_status,
                        "response_id": response.response_id,
                        "retry_count": len(retry_events),
                        "attempt_index": len(retry_events),
                        "retry_events": [_retry_event_record(event) for event in retry_events],
                        "safe_response_headers": response.safe_response_headers,
                        "normalized_list_cost_usd": None if cost is None else str(cost),
                        "actual_charge_usd": response.actual_charge_usd,
                    }
                    if provider == "nvidia_nim":
                        record["billing_mode"] = "free_prototype"
                    _atomic_create_json(run_dir / "calls" / config.config_id / f"{call_id}.json", record)
                    outputs[(config.config_id, call.position)] = response.text
                    _accumulate_cost(stats_by_config[config.config_id], record)
                    provider_calls[provider] += 1
                    session_new_calls += 1
                except ClassifiedFailure as failure:
                    retry_records = [_retry_event_record(event) for event in retry_events]
                    last_attempt_index = retry_events[-1].attempt_index if retry_events else 0
                    failure_record = {
                        "run_id": policy.run_id,
                        "call_id": call_id,
                        "item_id": item.item_id,
                        "config_id": config.config_id,
                        "status": "failure",
                        "provider": provider,
                        "model_id": request.model_id,
                        "reported_model_id": None,
                        "role": call.role,
                        "topology_position": call.position,
                        "raw_output": response.text if response is not None else None,
                        "parsed_answer": "INVALID" if response is not None else None,
                        "normalization_actions": [],
                        "failure_type": failure.failure_code,
                        "finish_reason": failure.finish_reason,
                        "latency_ms": failure.latency_ms,
                        "http_status": failure.http_status,
                        "response_id": failure.response_id,
                        "input_tokens": failure.input_tokens,
                        "output_tokens": failure.output_tokens,
                        "reasoning_tokens": failure.reasoning_tokens,
                        "cached_input_tokens": failure.cached_input_tokens,
                        "total_tokens": failure.total_tokens,
                        "token_accounting_method": failure.token_accounting_method,
                        "retry_count": sum(event.decision.should_retry for event in retry_events),
                        "attempt_index": last_attempt_index,
                        "retry_events": retry_records,
                        "safe_response_headers": failure.safe_response_headers,
                        "normalized_list_cost_usd": None,
                        "actual_charge_usd": failure.actual_charge_usd,
                    }
                    if provider == "nvidia_nim":
                        failure_record["billing_mode"] = "free_prototype"
                    _atomic_create_json(run_dir / "calls" / config.config_id / f"{call_id}.json", failure_record)
                    _session_record(
                        run_dir,
                        {
                            "started_at_utc": session_started,
                            "ended_at_utc": _utc_now(),
                            "status": "failed",
                            "new_items_completed": session_new_items,
                            "new_logical_calls_completed": session_new_calls,
                            "transport_attempts_total": attempt_count,
                        },
                    )
                    summary = {
                        "run_id": policy.run_id,
                        "expected_logical_calls": policy.expected_logical_calls,
                        "completed_logical_calls": len(completed) + session_new_calls,
                        "transport_attempts": attempt_count,
                        "terminal_errors": 1,
                        "failure_type": failure.failure_code,
                    }
                    _finish_run(run_dir, manifest, status="failed", summary=summary)
                    if failure.failure_code in RUN_BLOCKING_CODES:
                        raise RuntimeError(f"run-blocking provider failure: {failure.failure_code}") from None
                    raise RuntimeError("terminal-error threshold exceeded") from None
        session_new_items += 1

    completed_total = len(completed) + session_new_calls
    remaining_items = len(incomplete_items) - len(selected_items)
    if completed_total < policy.expected_logical_calls:
        _session_record(
            run_dir,
            {
                "started_at_utc": session_started,
                "ended_at_utc": _utc_now(),
                "status": "planned_pause",
                "new_items_completed": session_new_items,
                "new_logical_calls_completed": session_new_calls,
                "completed_logical_calls_total": completed_total,
                "remaining_items": remaining_items,
                "transport_attempts_total": attempt_count,
            },
        )
        _pause_run(run_dir, manifest)
        return {
            "run_id": policy.run_id,
            "artifact_path": str(run_dir),
            "run_status": "paused",
            "completed_logical_calls": completed_total,
            "expected_logical_calls": policy.expected_logical_calls,
            "transport_attempts": attempt_count,
            "remaining_items": remaining_items,
        }

    if provider_calls != Counter(policy.expected_provider_calls):
        raise RuntimeError("completed provider counts differ from the execution policy")
    summary = {
        "run_id": policy.run_id,
        "expected_logical_calls": policy.expected_logical_calls,
        "completed_logical_calls": completed_total,
        "transport_attempts": attempt_count,
        "terminal_errors": 0,
        "provider_calls": dict(sorted(provider_calls.items())),
        "cost_summary": _cost_summary(stats_by_config),
    }
    _session_record(
        run_dir,
        {
            "started_at_utc": session_started,
            "ended_at_utc": _utc_now(),
            "status": "complete",
            "new_items_completed": session_new_items,
            "new_logical_calls_completed": session_new_calls,
            "completed_logical_calls_total": completed_total,
            "transport_attempts_total": attempt_count,
        },
    )
    _finish_run(run_dir, manifest, status="complete", summary=summary)
    return {**summary, "artifact_path": str(run_dir), "run_status": "complete"}


def r5_canary_artifact_passed(artifact_root: Path) -> bool:
    run_dir = artifact_root / SMOKE_CANARY_POLICY.run_id
    try:
        manifest = _read_json(run_dir / "manifest.json")
        summary = _read_json(run_dir / "summary.json")
        if not (
            manifest.get("schema_version") == 2
            and manifest.get("run_id") == SMOKE_CANARY_POLICY.run_id
            and manifest.get("execution_revision") == EXECUTION_REVISION
            and manifest.get("split") == "smoke"
            and manifest.get("item_count") == 3
            and manifest.get("config_ids") == list(METHOD_ORDER)
            and manifest.get("run_status") == "complete"
            and manifest.get("freeze_state") == "frozen"
            and summary.get("terminal_errors") == 0
            and summary.get("completed_logical_calls") == 51
            and summary.get("expected_logical_calls") == 51
            and summary.get("provider_calls") == SMOKE_CANARY_POLICY.expected_provider_calls
            and isinstance(summary.get("transport_attempts"), int)
            and 51 <= summary["transport_attempts"] <= 204
        ):
            return False
        _assert_resume_inventory(run_dir, frozenset(METHOD_ORDER))
        configs = {
            config_id: _read_json(run_dir / "configs" / f"{config_id}.json")
            for config_id in manifest["config_ids"]
        }
        for config in configs.values():
            validate_config(config, for_execution=True)
        raw_records = [_read_json(path) for path in (run_dir / "calls").glob("*/*.json")]
        item_ids = {record.get("item_id") for record in raw_records if isinstance(record.get("item_id"), str)}
        if (
            len(item_ids) != 3
            or hashlib.sha256("\n".join(sorted(item_ids)).encode()).hexdigest()
            != manifest.get("item_set_sha256")
        ):
            return False
        expected_calls = {
            logical_call_id("smoke", config_id, item_id, call.position): {
                "run_id": SMOKE_CANARY_POLICY.run_id,
                "item_id": item_id,
                "config_id": config_id,
                "provider": config["provider_assignment"][call.role],
                "model_id": config["model_assignment"][call.role],
                "role": call.role,
                "topology_position": call.position,
            }
            for item_id in item_ids
            for config_id, config in configs.items()
            for call in build_execution_plan(MethodConfig(config, run_dir / "configs" / f"{config_id}.json")).calls
        }
        if {record.get("call_id") for record in raw_records} != set(expected_calls):
            return False
        records = list(_load_existing_records(run_dir, expected_calls).values())
        attempts = [_read_json(path) for path in (run_dir / "attempts").glob("*/*.json")]
        if len(records) != 51 or len(attempts) != summary["transport_attempts"]:
            return False
        if len({record.get("call_id") for record in records}) != 51:
            return False
        for record in records:
            config = configs[record["config_id"]]
            role = record["role"]
            provider = config["provider_assignment"][role]
            model = config["model_assignment"][role]
            required = {
                "finish_reason",
                "latency_ms",
                "input_tokens",
                "output_tokens",
                "reasoning_tokens",
                "cached_input_tokens",
                "total_tokens",
                "http_status",
                "response_id",
                "retry_events",
                "normalized_list_cost_usd",
                "actual_charge_usd",
            }
            if (
                record.get("status") != "success"
                or record.get("parsed_answer") not in {"YES", "NO"}
                or record.get("provider") != provider
                or record.get("model_id") != model
                or record.get("reported_model_id") not in {None, model}
                or not required.issubset(record)
                or record.get("call_id")
                != logical_call_id("smoke", record["config_id"], record["item_id"], record["topology_position"])
            ):
                return False
            if provider == "nvidia_nim" and (
                record.get("normalized_list_cost_usd") is not None
                or record.get("actual_charge_usd") is not None
                or record.get("billing_mode") != "free_prototype"
            ):
                return False
            _assert_no_secret_keys(record)
        attempt_required = {
            "status",
            "completed_at_utc",
            "finish_reason",
            "latency_ms",
            "input_tokens",
            "output_tokens",
            "reasoning_tokens",
            "cached_input_tokens",
            "total_tokens",
            "http_status",
            "response_id",
            "safe_response_headers",
        }
        if any(
            attempt.get("status") not in {"success", "failure"} or not attempt_required.issubset(attempt)
            for attempt in attempts
        ):
            return False
        for value in (manifest, summary, *configs.values(), *attempts):
            _assert_no_secret_keys(value)
    except (KeyError, RuntimeError, TypeError, ValueError):
        return False
    return True


def predecessor_gate_for_policy(artifact_root: Path, policy: SplitExecutionPolicy) -> dict[str, Any]:
    if policy.canary:
        verified = verify_r4_remediation_input(artifact_root)
        run_dir = artifact_root / policy.predecessor_run_id
        return {
            "run_id": policy.predecessor_run_id,
            "requirement": policy.predecessor_requirement,
            "artifact": f"artifacts/runs/{policy.predecessor_run_id}",
            "artifact_tree_sha256": artifact_tree_sha256(run_dir) if verified else None,
            "manifest_sha256": file_sha256_bytes(run_dir / "manifest.json") if verified else None,
            "verified": verified,
        }
    predecessor = artifact_root / policy.predecessor_run_id
    verified = r5_canary_artifact_passed(artifact_root) if policy.split == "smoke" else False
    return {
        "run_id": policy.predecessor_run_id,
        "requirement": policy.predecessor_requirement,
        "artifact": f"artifacts/runs/{policy.predecessor_run_id}",
        "artifact_tree_sha256": artifact_tree_sha256(predecessor) if verified else None,
        "manifest_sha256": file_sha256_bytes(predecessor / "manifest.json") if verified else None,
        "verified": verified,
    }
