#!/usr/bin/env python3
"""Benchmark entry point intentionally blocked until execution preflight passes."""

from __future__ import annotations

from pathlib import Path

from causalrisk.preflight import run_preflight


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    report = run_preflight(root, for_execution=True)
    if not report.passed:
        failed = ", ".join(check.name for check in report.checks if not check.passed)
        raise SystemExit(f"Benchmark execution blocked by preflight gates: {failed}")
    raise SystemExit(
        "Execution configs passed, but the benchmark controller is not implemented in this Day 2 skeleton."
    )


if __name__ == "__main__":
    main()
