from pathlib import Path

from causalrisk.preflight import run_preflight

ROOT = Path(__file__).resolve().parents[2]


def test_structural_preflight_passes():
    report = run_preflight(ROOT)
    assert report.passed, [check for check in report.checks if not check.passed]


def test_execution_preflight_stays_blocked_before_runtime_freeze():
    report = run_preflight(ROOT, for_execution=True)
    assert not report.passed
    failed_names = {check.name for check in report.checks if not check.passed}
    assert "A1_SINGLE_V1" in failed_names
    assert "C5_COUNCIL_V1" in failed_names
    config_failures = [check for check in report.checks if check.name.endswith("_V1") and not check.passed]
    assert config_failures
    assert all(check.detail == "execution is blocked because execution_enabled is false" for check in config_failures)
