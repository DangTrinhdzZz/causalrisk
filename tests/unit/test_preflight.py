from pathlib import Path

from causalrisk.preflight import run_preflight

ROOT = Path(__file__).resolve().parents[2]


def test_structural_preflight_passes():
    report = run_preflight(ROOT)
    assert report.passed, [check for check in report.checks if not check.passed]


def test_execution_preflight_passes_after_controlled_enablement():
    report = run_preflight(ROOT, for_execution=True)
    assert report.passed, [check for check in report.checks if not check.passed]
    pricing_check = next(check for check in report.checks if check.name == "official_pricing_policy")
    assert pricing_check.passed
    provider_check = next(check for check in report.checks if check.name == "provider_availability_policy")
    assert provider_check.passed
