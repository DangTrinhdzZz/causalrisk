import ast
import json
from pathlib import Path

from causalrisk.capacity import assess_provider_limits, build_capacity_plan, load_provider_limits
from causalrisk.config import load_config
from causalrisk.dry_run import build_execution_dry_run
from causalrisk.execution_policy import METHOD_ORDER, MINIMUM_INTERVAL_SECONDS, SMOKE_CANARY_POLICY, SPLIT_POLICIES

ROOT = Path(__file__).resolve().parents[2]


def test_exact_cross_split_counts_run_ids_and_authorization_matrix():
    assert (SMOKE_CANARY_POLICY.expected_logical_calls, SMOKE_CANARY_POLICY.max_transport_attempts) == (51, 204)
    expected = {
        "smoke": (60, 1020, 4080, "cladder-smoke-60-r2", True, "--authorize-live-smoke"),
        "calibration": (
            300,
            5100,
            20400,
            "cladder-calibration-300-r2",
            False,
            "--authorize-live-calibration",
        ),
        "locked_test": (
            600,
            10200,
            40800,
            "cladder-locked-test-600-r2",
            False,
            "--authorize-live-locked-test",
        ),
    }
    for split, values in expected.items():
        policy = SPLIT_POLICIES[split]
        assert (
            policy.item_count,
            policy.expected_logical_calls,
            policy.max_transport_attempts,
            policy.run_id,
            policy.live_authorized,
            policy.authorization_flag,
        ) == values
        assert policy.expected_provider_calls == {
            "cloudflare_workers_ai": policy.item_count,
            "gemini": policy.item_count,
            "groq": 11 * policy.item_count,
            "nvidia_nim": 2 * policy.item_count,
            "openai": 2 * policy.item_count,
        }
    assert len({policy.authorization_flag for policy in SPLIT_POLICIES.values()}) == 3
    assert "--authorize-live" not in {policy.authorization_flag for policy in SPLIT_POLICIES.values()}


def test_analyst_cap_and_groq_pacing_are_cross_split_invariants():
    configs = [load_config(ROOT / "configs/methods" / f"{config_id}.yaml") for config_id in METHOD_ORDER]
    assert all(config.values["max_output_tokens"]["analyst"] == 2048 for config in configs)
    assert MINIMUM_INTERVAL_SECONDS["groq"] == 10.0


def test_all_three_split_dry_runs_are_no_write_plans():
    artifact_root = ROOT / "artifacts/runs"
    before = sorted(path.name for path in artifact_root.iterdir())
    plans = {split: build_execution_dry_run(ROOT, split=split) for split in SPLIT_POLICIES}
    after = sorted(path.name for path in artifact_root.iterdir())
    assert before == after
    assert {split: plan.logical_calls for split, plan in plans.items()} == {
        "smoke": 1020,
        "calibration": 5100,
        "locked_test": 10200,
    }
    assert all(plan.to_dict()["mode"] == "dry_run_no_http_no_artifacts" for plan in plans.values())


def test_known_daily_limit_exceedance_blocks_without_safe_batching(tmp_path):
    document = json.loads((ROOT / "configs/provider_limits_2026-09-12.json").read_text(encoding="utf-8"))
    document["providers"]["groq"]["RPD"] = 10
    path = tmp_path / "limits.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    snapshot = load_provider_limits(path)
    assessment = assess_provider_limits(SMOKE_CANARY_POLICY, snapshot)
    assert not assessment.passed
    assert assessment.violations == ("groq:PROJECTED_CALLS_EXCEED_RPD_WITHOUT_SAFE_BATCHING",)


def test_known_daily_token_limit_exceedance_blocks_when_projection_is_available(tmp_path):
    document = json.loads((ROOT / "configs/provider_limits_2026-09-12.json").read_text(encoding="utf-8"))
    document["providers"]["groq"]["TPD"] = 100
    path = tmp_path / "limits.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    snapshot = load_provider_limits(path)
    assessment = assess_provider_limits(
        SMOKE_CANARY_POLICY,
        snapshot,
        projected_tokens={"groq": 101},
    )
    assert "groq:PROJECTED_TOKENS_EXCEED_TPD_WITHOUT_SAFE_BATCHING" in assessment.violations


def test_known_daily_limit_requires_the_declared_session_bound(tmp_path):
    document = json.loads((ROOT / "configs/provider_limits_2026-09-12.json").read_text(encoding="utf-8"))
    document["providers"]["groq"]["RPD"] = 100
    path = tmp_path / "limits.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    snapshot = load_provider_limits(path)
    assert not assess_provider_limits(SPLIT_POLICIES["smoke"], snapshot).passed
    assert assess_provider_limits(SPLIT_POLICIES["smoke"], snapshot, max_new_items=3).passed


def test_capacity_plan_uses_only_supported_empirical_projection_and_preserves_nulls():
    limits = load_provider_limits(ROOT / "configs/provider_limits_2026-09-12.json")
    forensic = json.loads((ROOT / "docs/r1_operational_canary_forensic_aggregate.json").read_text(encoding="utf-8"))
    plan = build_capacity_plan(SMOKE_CANARY_POLICY, provider_limits=limits, forensic_report=forensic)
    assert plan["estimated_minimum_runtime_seconds"] == 320.0
    assert plan["provider_plans"]["groq"]["projected_normalized_list_cost_usd"] == "0.01196158"
    assert plan["provider_plans"]["nvidia_nim"]["projected_normalized_list_cost_usd"] is None
    assert plan["provider_plans"]["nvidia_nim"]["actual_charge_usd"] is None
    assert plan["provider_plans"]["nvidia_nim"]["billing_mode"] == "free_prototype"
    assert plan["projected_normalized_list_cost_usd"] is None
    assert plan["estimated_account_limit_windows"] is None


def test_inference_runner_cannot_import_gold_or_scoring_modules():
    tree = ast.parse((ROOT / "scripts/run_benchmark.py").read_text(encoding="utf-8"))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    assert "causalrisk.scoring" not in imported
    assert "scripts.create_cladder_splits" not in imported
    assert "scripts.audit_cladder_splits" not in imported
    assert "create_cladder_splits" not in imported
    assert "audit_cladder_splits" not in imported
