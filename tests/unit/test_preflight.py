from pathlib import Path

from causalrisk.lineage import verify_r4_remediation_input
from causalrisk.preflight import run_preflight

ROOT = Path(__file__).resolve().parents[2]


def test_structural_preflight_passes():
    report = run_preflight(ROOT)
    assert report.passed, [check for check in report.checks if not check.passed]


def test_execution_preflight_passes_after_controlled_enablement():
    assert verify_r4_remediation_input(ROOT / "artifacts/runs")
    report = run_preflight(ROOT, for_execution=True, split="smoke")
    assert report.passed, [check for check in report.checks if not check.passed]
    pricing_check = next(check for check in report.checks if check.name == "official_pricing_policy")
    assert pricing_check.passed
    provider_check = next(check for check in report.checks if check.name == "provider_availability_policy")
    assert provider_check.passed
    lineage_check = next(check for check in report.checks if check.name == "r4_immutable_remediation_lineage")
    assert lineage_check.passed


def test_calibration_and_locked_execution_preflights_fail_closed():
    for split in ("calibration", "locked_test"):
        report = run_preflight(ROOT, for_execution=True, split=split)
        authorization = next(check for check in report.checks if check.name == "split_live_authorization_state")
        assert not report.passed
        assert not authorization.passed
        assert authorization.detail == "BLOCKED_NOT_AUTHORIZED"
