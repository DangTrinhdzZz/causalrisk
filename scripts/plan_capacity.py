#!/usr/bin/env python3
"""Print an offline cross-split capacity plan without loading credentials or making HTTP requests."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from causalrisk.capacity import build_capacity_plan, load_provider_limits
from causalrisk.execution_policy import get_execution_policy


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--split", required=True, choices=("smoke", "calibration", "locked_test"))
    parser.add_argument("--canary", action="store_true", help="plan the fixed three-item smoke R4 canary")
    parser.add_argument("--max-new-items", type=int, help="declared per-session item bound")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    policy = get_execution_policy(args.split, canary=args.canary)
    if args.max_new_items is not None and (
        args.canary or not 1 <= args.max_new_items <= policy.item_count
    ):
        parser.error("--max-new-items must bound a non-canary session within the fixed run")
    limits = load_provider_limits(root / "configs/provider_limits_2026-09-12.json")
    forensic = json.loads((root / "docs/r1_operational_canary_forensic_aggregate.json").read_text(encoding="utf-8"))
    print(
        json.dumps(
            build_capacity_plan(
                policy,
                provider_limits=limits,
                forensic_report=forensic,
                max_new_items=args.max_new_items,
            ),
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
