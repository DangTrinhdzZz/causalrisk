#!/usr/bin/env python3
"""Network-gated benchmark entry point with a safe, deterministic dry-run."""

from __future__ import annotations

import argparse
import importlib
import json
from pathlib import Path
from typing import Any

from causalrisk.config import load_config
from causalrisk.controller import ControllerLimits, PacingPolicy, canary_artifact_passed, execute_smoke
from causalrisk.credentials import load_credential
from causalrisk.data import verify_inference_view
from causalrisk.dry_run import build_smoke_dry_run
from causalrisk.preflight import run_preflight
from causalrisk.pricing import load_pricing
from causalrisk.prompts import load_prompt_bundle
from causalrisk.providers.candidates import PROVIDER_CANDIDATES

METHOD_IDS = ("A1_SINGLE_V1", "A3_SINGLE_V1", "A5_SINGLE_V1", "C1_BOUNDARY_V1", "C3_COUNCIL_V1", "C5_COUNCIL_V1")


def _select_items(items, max_items):
    if max_items is None:
        return tuple(sorted(items, key=lambda item: item.item_id))
    return tuple(
        min((item for item in items if item.rung == rung), key=lambda item: item.item_id)
        for rung in (1, 2, 3)
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="validate and print a plan without creating HTTP requests",
    )
    parser.add_argument("--split", choices=("smoke",), default="smoke")
    parser.add_argument("--max-items", type=int, choices=(3,), help="use the predeclared one-item-per-rung canary")
    parser.add_argument(
        "--authorize-live-smoke",
        action="store_true",
        help="explicit acknowledgement required for future live smoke execution",
    )
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    if args.dry_run:
        if args.authorize_live_smoke:
            parser.error("--dry-run cannot be combined with --authorize-live-smoke")
        report = run_preflight(root)
        if not report.passed:
            failed = ", ".join(check.name for check in report.checks if not check.passed)
            raise SystemExit(f"Dry-run blocked by structural preflight gates: {failed}")
        print(json.dumps(build_smoke_dry_run(root, max_items=args.max_items).to_dict(), indent=2))
        return
    if not args.authorize_live_smoke:
        raise SystemExit("Live smoke blocked: explicit --authorize-live-smoke acknowledgement is required.")
    report = run_preflight(root, for_execution=True)
    if not report.passed:
        failed = ", ".join(check.name for check in report.checks if not check.passed)
        raise SystemExit(f"Benchmark execution blocked by preflight gates: {failed}")
    pricing = load_pricing(root / "configs" / "pricing_2026-09-11.json")
    configs = tuple(load_config(root / "configs/methods" / f"{config_id}.yaml") for config_id in METHOD_IDS)
    source_hash = build_smoke_dry_run(root, max_items=args.max_items).manifest_sha256
    items = _select_items(
        verify_inference_view(root / "data/splits/private/inference/smoke.json", source_hash),
        args.max_items,
    )
    artifact_root = root / "artifacts/runs"
    run_id = "cladder-smoke-canary-3" if args.max_items == 3 else "cladder-smoke-60"
    if args.max_items is None and not canary_artifact_passed(
        artifact_root, expected_items=_select_items(items, 3)
    ):
        raise SystemExit("Live smoke-60 blocked: the frozen three-item canary artifact has not passed.")
    adapters = {}
    for provider, candidate in PROVIDER_CANDIDATES.items():
        if not candidate.primary or candidate.availability != "available":
            continue
        module_name, factory_name = candidate.factory_specification.split(":", 1)
        factory: Any = getattr(importlib.import_module(module_name), factory_name)
        adapters[provider] = factory(load_credential(candidate.credential_environment_variable))
    logical_limit = 17 * len(items)
    result = execute_smoke(
        split="smoke",
        authorized=args.authorize_live_smoke,
        run_id=run_id,
        configs=configs,
        items=items,
        adapters=adapters,
        pricing=pricing,
        prompt_bundle=load_prompt_bundle(root / "prompts/prompt_causal_yesno_v1.json"),
        artifact_root=artifact_root,
        limits=ControllerLimits(logical_limit, logical_limit * 4, 0),
        pacing=PacingPolicy(
            {"groq": 2.0, "nvidia_nim": 1.0, "gemini": 1.0, "cloudflare_workers_ai": 1.0, "openai": 1.0}
        ),
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
