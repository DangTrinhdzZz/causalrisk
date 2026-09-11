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
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    report = run_preflight(root, for_execution=args.execution)
    for check in report.checks:
        print(f"{'PASS' if check.passed else 'FAIL'} {check.name}: {check.detail}")
    raise SystemExit(0 if report.passed else 1)


if __name__ == "__main__":
    main()
