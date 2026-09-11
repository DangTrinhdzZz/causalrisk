"""Deterministic, network-free planning for the sealed CLadder smoke split."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from causalrisk.config import load_config
from causalrisk.providers.candidates import PROVIDER_CANDIDATES
from causalrisk.topology import build_execution_plan

SMOKE_ITEM_COUNT = 60
SMOKE_MANIFEST_SHA256 = "e53e151258e0d71e0f0360e5c8bdd7e1a2e8defa76a34f2774d0f2999776afe9"
METHOD_ORDER = (
    "A1_SINGLE_V1",
    "A3_SINGLE_V1",
    "A5_SINGLE_V1",
    "C1_BOUNDARY_V1",
    "C3_COUNCIL_V1",
    "C5_COUNCIL_V1",
)


@dataclass(frozen=True, slots=True)
class DryRunPlan:
    split: str
    item_count: int
    manifest_sha256: str
    method_calls: dict[str, int]
    provider_calls: dict[str, int]
    maximum_provider_attempts: int
    artifacts: dict[str, dict[str, str]]

    @property
    def logical_calls(self) -> int:
        return sum(self.method_calls.values())

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": "dry_run_no_http",
            "split": self.split,
            "item_count": self.item_count,
            "manifest_sha256": self.manifest_sha256,
            "method_order": list(METHOD_ORDER),
            "method_calls": self.method_calls,
            "provider_calls": self.provider_calls,
            "logical_calls": self.logical_calls,
            "maximum_provider_attempts_with_retries": self.maximum_provider_attempts,
            "retry_policy": "maximum 3 retries / 4 attempts per logical call; failures remain observable",
            "parse_policy": "deterministic yesno_parser_v1; INVALID is never imputed",
            "metadata": {
                "token_usage": "provider-reported input/output/total or null",
                "latency_ms": "measured per attempt or null",
                "estimated_cost_usd": None,
                "cost_note": "null until a versioned pricing configuration is frozen",
            },
            "artifacts": self.artifacts,
        }


def _manifest(path: Path) -> tuple[dict[str, Any], str]:
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if digest != SMOKE_MANIFEST_SHA256:
        raise ValueError("sealed smoke manifest checksum differs from protocol v1")
    document = json.loads(raw)
    if not isinstance(document, dict) or document.get("split") != "smoke":
        raise ValueError("sealed manifest is not the smoke split")
    items = document.get("items")
    if not isinstance(items, list) or len(items) != SMOKE_ITEM_COUNT:
        raise ValueError("sealed smoke split must contain exactly 60 items")
    source_indices = [item.get("source_index") for item in items if isinstance(item, dict)]
    if len(source_indices) != SMOKE_ITEM_COUNT or len(set(source_indices)) != SMOKE_ITEM_COUNT:
        raise ValueError("sealed smoke split entries are invalid or duplicated")
    return document, digest


def _artifact_state(path: Path) -> str:
    if not path.exists():
        return "create"
    manifest_path = path / "manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"existing artifact is not resumable: {path.name}") from error
    state = manifest.get("freeze_state")
    if state == "open":
        return "resume_open_without_overwrite"
    if state == "frozen":
        return "reuse_frozen_without_overwrite"
    raise ValueError(f"existing artifact has an invalid freeze state: {path.name}")


def build_smoke_dry_run(repo_root: str | Path) -> DryRunPlan:
    root = Path(repo_root).resolve()
    _document, digest = _manifest(root / "data" / "splits" / "private" / "smoke.json")
    method_calls: dict[str, int] = {}
    provider_counts: Counter[str] = Counter()
    artifacts: dict[str, dict[str, str]] = {}
    artifact_root = root / "artifacts" / "runs"

    for config_id in METHOD_ORDER:
        config = load_config(root / "configs" / "methods" / f"{config_id}.yaml")
        plan = build_execution_plan(config)
        count = len(plan.calls) * SMOKE_ITEM_COUNT
        method_calls[config_id] = count
        for call in plan.calls:
            provider = config.values["provider_assignment"][call.role]
            candidate = PROVIDER_CANDIDATES.get(provider)
            if candidate is None or not candidate.primary or candidate.availability != "available":
                raise ValueError(f"{config_id} maps {call.role} to an ineligible provider")
            if config.values["model_assignment"][call.role] != candidate.model_id:
                raise ValueError(f"{config_id} model mapping differs from the provider roster")
            if config.values["model_family_assignment"][call.role] != candidate.model_family:
                raise ValueError(f"{config_id} model-family mapping differs from the provider roster")
            provider_counts[provider] += SMOKE_ITEM_COUNT
        run_id = "cladder-smoke-" + config_id.casefold().replace("_", "-")
        run_path = artifact_root / run_id
        if plan.alias_of:
            alias_id = "cladder-smoke-" + plan.alias_of.casefold().replace("_", "-")
            artifacts[config_id] = {"path": str(artifact_root / alias_id), "action": "alias_existing_a1"}
        else:
            artifacts[config_id] = {"path": str(run_path), "action": _artifact_state(run_path)}

    return DryRunPlan(
        split="smoke",
        item_count=SMOKE_ITEM_COUNT,
        manifest_sha256=digest,
        method_calls=method_calls,
        provider_calls=dict(sorted(provider_counts.items())),
        maximum_provider_attempts=sum(method_calls.values()) * 4,
        artifacts=artifacts,
    )
