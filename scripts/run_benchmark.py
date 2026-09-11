#!/usr/bin/env python3
"""Network-gated benchmark entry point with a safe, deterministic dry-run."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from causalrisk.dry_run import build_smoke_dry_run
from causalrisk.preflight import run_preflight


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="validate and print a plan without creating HTTP requests",
    )
    parser.add_argument("--split", choices=("smoke",), default="smoke")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    if args.dry_run:
        report = run_preflight(root)
        if not report.passed:
            failed = ", ".join(check.name for check in report.checks if not check.passed)
            raise SystemExit(f"Dry-run blocked by structural preflight gates: {failed}")
        print(json.dumps(build_smoke_dry_run(root).to_dict(), indent=2))
        return
    report = run_preflight(root, for_execution=True)
    if not report.passed:
        failed = ", ".join(check.name for check in report.checks if not check.passed)
        raise SystemExit(f"Benchmark execution blocked by preflight gates: {failed}")
    raise SystemExit("Live execution is not implemented; this command made no HTTP request.")


if __name__ == "__main__":
    main()
