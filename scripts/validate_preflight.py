#!/usr/bin/env python3
"""Validate structural gates, or deliberately stricter execution gates."""

from __future__ import annotations

import argparse
from pathlib import Path

from causalrisk.preflight import run_preflight


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--execution",
        action="store_true",
        help="require runtime-verified, execution-enabled configs and the frozen pricing policy",
    )
    parser.add_argument("--split", choices=("smoke", "calibration", "locked_test"), default="smoke")
    parser.add_argument("--max-new-items", type=int)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    report = run_preflight(
        root,
        for_execution=args.execution,
        split=args.split if args.execution else None,
        max_new_items=args.max_new_items,
    )
    for check in report.checks:
        print(f"{'PASS' if check.passed else 'FAIL'} {check.name}: {check.detail}")
    raise SystemExit(0 if report.passed else 1)


if __name__ == "__main__":
    main()
