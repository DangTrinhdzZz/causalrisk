#!/usr/bin/env python3
"""Network-gated benchmark entry point with a safe, deterministic dry-run."""

from __future__ import annotations

import argparse
import importlib
import json
import subprocess
from pathlib import Path
from typing import Any

from causalrisk.config import load_config
from causalrisk.controller import ExecutionLineage, PacingPolicy, execute_split, predecessor_gate_for_policy
from causalrisk.credentials import load_credential
from causalrisk.data import select_smoke_canary, verify_inference_view
from causalrisk.dry_run import build_execution_dry_run
from causalrisk.execution_policy import METHOD_ORDER, MINIMUM_INTERVAL_SECONDS, get_execution_policy
from causalrisk.preflight import run_preflight
from causalrisk.pricing import load_pricing
from causalrisk.prompts import load_prompt_bundle
from causalrisk.providers.candidates import PROVIDER_CANDIDATES

AUTHORIZATION_FLAGS = {
    "smoke": "--authorize-live-smoke",
    "calibration": "--authorize-live-calibration",
    "locked_test": "--authorize-live-locked-test",
}


def _exact_code_commit(root: Path) -> str:
    status = subprocess.run(
        ["git", "status", "--porcelain=v1", "--untracked-files=no"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    if status.stdout.strip():
        raise SystemExit("Live execution blocked: tracked code/config changes are not committed.")
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=root, check=True, capture_output=True, text=True
    ).stdout.strip()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="validate and print a plan without creating HTTP requests",
    )
    parser.add_argument("--split", choices=("smoke", "calibration", "locked_test"), default="smoke")
    parser.add_argument("--max-items", type=int, choices=(3,), help="use the predeclared one-item-per-rung canary")
    parser.add_argument(
        "--max-new-items",
        type=int,
        help="planned session bound; the full run manifest item_count and statistical sample do not change",
    )
    parser.add_argument(
        "--authorize-live-smoke",
        action="store_true",
        help="explicit acknowledgement required for future live smoke execution",
    )
    parser.add_argument("--authorize-live-calibration", action="store_true")
    parser.add_argument("--authorize-live-locked-test", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    if args.max_items is not None and args.split != "smoke":
        parser.error("--max-items 3 is the fixed smoke canary only")
    canary = args.max_items == 3
    policy = get_execution_policy(args.split, canary=canary)
    authorization_values = {
        "smoke": args.authorize_live_smoke,
        "calibration": args.authorize_live_calibration,
        "locked_test": args.authorize_live_locked_test,
    }
    selected_authorizations = [flag for split, flag in AUTHORIZATION_FLAGS.items() if authorization_values[split]]
    if args.dry_run:
        if selected_authorizations:
            parser.error("--dry-run cannot be combined with a live authorization flag")
        report = run_preflight(root)
        if not report.passed:
            failed = ", ".join(check.name for check in report.checks if not check.passed)
            raise SystemExit(f"Dry-run blocked by structural preflight gates: {failed}")
        print(
            json.dumps(
                build_execution_dry_run(
                    root,
                    split=args.split,
                    canary=canary,
                    max_new_items=args.max_new_items,
                ).to_dict(),
                indent=2,
            )
        )
        return
    if len(selected_authorizations) != 1 or selected_authorizations[0] != policy.authorization_flag:
        raise SystemExit(f"Live execution blocked: exact {policy.authorization_flag} acknowledgement is required.")
    if not policy.live_authorized:
        raise SystemExit(f"{args.split} live execution: BLOCKED_NOT_AUTHORIZED")
    report = run_preflight(root, for_execution=True, split=args.split, max_new_items=args.max_new_items)
    if not report.passed:
        failed = ", ".join(check.name for check in report.checks if not check.passed)
        raise SystemExit(f"Benchmark execution blocked by preflight gates: {failed}")
    pricing = load_pricing(root / "configs" / "pricing_2026-09-11.json")
    configs = tuple(load_config(root / "configs/methods" / f"{config_id}.yaml") for config_id in METHOD_ORDER)
    dry_plan = build_execution_dry_run(
        root,
        split=args.split,
        canary=canary,
        max_new_items=args.max_new_items,
    )
    full_policy = get_execution_policy(args.split)
    view = verify_inference_view(
        root / "data/splits/private/inference" / f"{args.split}.v2.json",
        dry_plan.source_manifest_sha256,
        expected_item_count=full_policy.item_count,
    )
    if canary:
        selection = select_smoke_canary(view, root / "data/splits/private/inference/smoke.v2.canary.json")
        items = selection.items
        if selection.selector_sha256 != dry_plan.selection_sha256:
            raise SystemExit("Live execution blocked: canary selector checksum drifted after dry-run planning.")
    else:
        items = view.items
    artifact_root = root / "artifacts/runs"
    predecessor_gate = predecessor_gate_for_policy(artifact_root, policy)
    if not predecessor_gate["verified"]:
        raise SystemExit("Live execution blocked: the exact predecessor gate has not passed.")
    code_commit = _exact_code_commit(root)
    adapters = {}
    for provider, candidate in PROVIDER_CANDIDATES.items():
        if not candidate.primary or candidate.availability != "available":
            continue
        module_name, factory_name = candidate.factory_specification.split(":", 1)
        factory: Any = getattr(importlib.import_module(module_name), factory_name)
        adapters[provider] = factory(load_credential(candidate.credential_environment_variable))
    result = execute_split(
        policy=policy,
        authorization_flag=selected_authorizations[0],
        configs=configs,
        items=items,
        adapters=adapters,
        pricing=pricing,
        prompt_bundle=load_prompt_bundle(root / "prompts/prompt_causal_yesno_v1.json"),
        artifact_root=artifact_root,
        pacing=PacingPolicy(MINIMUM_INTERVAL_SECONDS),
        lineage=ExecutionLineage(
            code_commit=code_commit,
            source_manifest_sha256=dry_plan.source_manifest_sha256,
            inference_view_sha256=dry_plan.inference_view_sha256,
            inference_view_schema_version=dry_plan.inference_view_schema_version,
            selection_sha256=dry_plan.selection_sha256,
            config_sha256=dry_plan.config_sha256,
            prompt_sha256=dry_plan.prompt_sha256,
            pricing_version=pricing["version"],
            provider_limit_snapshot_version=dry_plan.provider_limit_snapshot_version,
            predecessor_gate=predecessor_gate,
        ),
        max_new_items=args.max_new_items,
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
