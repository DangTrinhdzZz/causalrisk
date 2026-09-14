"""Deterministic, network-free planning for all sealed CLadder execution splits."""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from causalrisk.capacity import build_capacity_plan, load_provider_limits
from causalrisk.config import load_config
from causalrisk.data import select_smoke_canary, verify_inference_view
from causalrisk.execution import predecessor_gate_for_policy
from causalrisk.execution_policy import (
    EXECUTION_REVISION,
    METHOD_ORDER,
    SOURCE_MANIFEST_SHA256,
    get_execution_policy,
)
from causalrisk.lineage import file_sha256_bytes
from causalrisk.prompts import file_sha256
from causalrisk.providers.candidates import PROVIDER_CANDIDATES
from causalrisk.topology import build_execution_plan


@dataclass(frozen=True, slots=True)
class ExecutionDryRunPlan:
    run_id: str
    artifact_path: str
    split: str
    item_count: int
    source_manifest_sha256: str
    inference_view_sha256: str
    inference_view_schema_version: int
    selection_sha256: str | None
    method_calls: dict[str, int]
    provider_calls: dict[str, int]
    maximum_provider_attempts: int
    config_sha256: dict[str, str]
    prompt_sha256: str
    provider_limit_snapshot_version: str
    predecessor_gate: dict[str, Any]
    artifacts: dict[str, dict[str, str]]
    capacity: dict[str, Any]

    @property
    def logical_calls(self) -> int:
        return sum(self.method_calls.values())

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": "dry_run_no_http_no_artifacts",
            "execution_revision": EXECUTION_REVISION,
            "run_id": self.run_id,
            "artifact_path": self.artifact_path,
            "split": self.split,
            "item_count": self.item_count,
            "source_manifest_sha256": self.source_manifest_sha256,
            "inference_view_sha256": self.inference_view_sha256,
            "inference_view_schema_version": self.inference_view_schema_version,
            "selection_sha256": self.selection_sha256,
            "method_order": list(METHOD_ORDER),
            "method_calls": self.method_calls,
            "provider_calls": self.provider_calls,
            "logical_calls": self.logical_calls,
            "maximum_provider_attempts_with_retries": self.maximum_provider_attempts,
            "config_sha256": self.config_sha256,
            "prompt_sha256": self.prompt_sha256,
            "provider_limit_snapshot_version": self.provider_limit_snapshot_version,
            "predecessor_gate": self.predecessor_gate,
            "retry_policy": "one initial attempt plus at most three retries",
            "ordering": "deterministic item-major; complete an item topology before planned pause",
            "capacity": self.capacity,
            "artifacts": self.artifacts,
        }


def _verify_source_manifest(root: Path, split: str) -> str:
    path = root / "data" / "splits" / "private" / f"{split}.json"
    digest = file_sha256_bytes(path)
    if digest != SOURCE_MANIFEST_SHA256[split]:
        raise ValueError(f"sealed {split} manifest checksum differs from Amendment 005")
    return digest


def _r4_artifact_state(path: Path) -> str:
    if not path.exists():
        return "create"
    manifest_path = path / "manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"existing artifact is not safely inspectable: {path.name}") from error
    state = (manifest.get("run_status"), manifest.get("freeze_state"))
    if state == ("paused", "open"):
        return "resume_open_without_overwrite"
    if state == ("in_progress", "open"):
        raise ValueError(f"existing artifact has an ambiguous in-progress state: {path.name}")
    if state[1] == "frozen":
        return "terminal_frozen_no_resume_no_overwrite"
    raise ValueError(f"existing artifact has an invalid state: {path.name}")


def _predecessor_status(root: Path, *, split: str, canary: bool) -> dict[str, Any]:
    policy = get_execution_policy(split, canary=canary)
    return predecessor_gate_for_policy(root / "artifacts" / "runs", policy)


def build_execution_dry_run(
    repo_root: str | Path,
    *,
    split: str,
    canary: bool = False,
    max_new_items: int | None = None,
) -> ExecutionDryRunPlan:
    root = Path(repo_root).resolve()
    policy = get_execution_policy(split, canary=canary)
    if max_new_items is not None and (
        isinstance(max_new_items, bool)
        or not isinstance(max_new_items, int)
        or not 1 <= max_new_items <= policy.item_count
        or policy.canary
    ):
        raise ValueError("max_new_items must bound a non-canary session within the fixed run")
    source_digest = _verify_source_manifest(root, split)
    view = verify_inference_view(
        root / "data" / "splits" / "private" / "inference" / f"{split}.v2.json",
        source_digest,
        expected_item_count=get_execution_policy(split).item_count,
    )
    selection_sha256 = None
    items = view.items
    if canary:
        selection = select_smoke_canary(
            view,
            root / "data" / "splits" / "private" / "inference" / "smoke.v2.canary.json",
        )
        items = selection.items
        selection_sha256 = selection.selector_sha256
    if len(items) != policy.item_count:
        raise ValueError("selected inference item count differs from execution policy")

    method_calls: dict[str, int] = {}
    provider_counts: Counter[str] = Counter()
    artifacts: dict[str, dict[str, str]] = {}
    config_sha256: dict[str, str] = {}
    artifact_root = root / "artifacts" / "runs"
    run_path = artifact_root / policy.run_id
    run_action = _r4_artifact_state(run_path)
    for config_id in METHOD_ORDER:
        path = root / "configs" / "methods" / f"{config_id}.yaml"
        config = load_config(path, for_execution=True)
        config_sha256[config_id] = file_sha256(path)
        plan = build_execution_plan(config)
        method_calls[config_id] = len(plan.calls) * len(items)
        for call in plan.calls:
            provider = config.values["provider_assignment"][call.role]
            candidate = PROVIDER_CANDIDATES.get(provider)
            if candidate is None or not candidate.primary or candidate.availability != "available":
                raise ValueError(f"{config_id} maps {call.role} to an ineligible provider")
            if config.values["model_assignment"][call.role] != candidate.model_id:
                raise ValueError(f"{config_id} model mapping differs from the provider roster")
            if config.values["model_family_assignment"][call.role] != candidate.model_family:
                raise ValueError(f"{config_id} model-family mapping differs from the provider roster")
            provider_counts[provider] += len(items)
        artifacts[config_id] = {
            "path": str(run_path / "calls" / (plan.alias_of or config_id)),
            "action": "alias_existing_a1" if plan.alias_of else run_action,
        }
    if (
        method_calls != policy.expected_method_calls
        or dict(sorted(provider_counts.items())) != policy.expected_provider_calls
    ):
        raise ValueError("computed call topology differs from the split execution policy")

    provider_limits = load_provider_limits(root / "configs/provider_limits_2026-09-12.json")
    forensic = json.loads((root / "docs/r1_operational_canary_forensic_aggregate.json").read_text(encoding="utf-8"))
    capacity = build_capacity_plan(
        policy,
        provider_limits=provider_limits,
        forensic_report=forensic,
        max_new_items=max_new_items,
    )
    return ExecutionDryRunPlan(
        run_id=policy.run_id,
        artifact_path=str(run_path),
        split=split,
        item_count=len(items),
        source_manifest_sha256=source_digest,
        inference_view_sha256=view.inference_view_sha256,
        inference_view_schema_version=view.schema_version,
        selection_sha256=selection_sha256,
        method_calls=method_calls,
        provider_calls=dict(sorted(provider_counts.items())),
        maximum_provider_attempts=policy.max_transport_attempts,
        config_sha256=config_sha256,
        prompt_sha256=file_sha256(root / "prompts/prompt_causal_yesno_v1.json"),
        provider_limit_snapshot_version=provider_limits["version"],
        predecessor_gate=_predecessor_status(root, split=split, canary=canary),
        artifacts=artifacts,
        capacity=capacity,
    )


def build_smoke_dry_run(repo_root: str | Path, *, max_items: int | None = None) -> ExecutionDryRunPlan:
    if max_items not in {None, 3}:
        raise ValueError("the only predeclared canary size is 3 items")
    return build_execution_dry_run(repo_root, split="smoke", canary=max_items == 3)
