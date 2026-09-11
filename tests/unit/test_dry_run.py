from pathlib import Path

import causalrisk.dry_run as dry_run
from causalrisk.data import LabelFreeItem

ROOT = Path(__file__).resolve().parents[2]


def test_smoke_dry_run_is_deterministic_and_counts_alias_once(monkeypatch, tmp_path):
    monkeypatch.setattr(dry_run, "_manifest", lambda _path: ({"split": "smoke"}, "0" * 64))
    items = tuple(LabelFreeItem(f"item-{index:02d}", index % 3 + 1, "b", "g", "q") for index in range(60))
    monkeypatch.setattr(dry_run, "verify_inference_view", lambda _path, _digest: items)
    monkeypatch.setattr(dry_run, "_artifact_state", lambda _path: "create")
    plan = dry_run.build_smoke_dry_run(ROOT)
    assert plan.method_calls == {
        "A1_SINGLE_V1": 60,
        "A3_SINGLE_V1": 180,
        "A5_SINGLE_V1": 300,
        "C1_BOUNDARY_V1": 0,
        "C3_COUNCIL_V1": 180,
        "C5_COUNCIL_V1": 300,
    }
    assert plan.provider_calls == {
        "cloudflare_workers_ai": 60,
        "gemini": 60,
        "groq": 660,
        "nvidia_nim": 120,
        "openai": 120,
    }
    assert plan.logical_calls == 1020
    assert plan.maximum_provider_attempts == 4080
    assert plan.artifacts["C1_BOUNDARY_V1"]["action"] == "alias_existing_a1"


def test_three_item_canary_has_one_item_per_rung_and_51_calls(monkeypatch):
    monkeypatch.setattr(dry_run, "_manifest", lambda _path: ({"split": "smoke"}, "0" * 64))
    items = tuple(LabelFreeItem(f"item-{index:02d}", index % 3 + 1, "b", "g", "q") for index in range(60))
    monkeypatch.setattr(dry_run, "verify_inference_view", lambda _path, _digest: items)
    monkeypatch.setattr(dry_run, "_artifact_state", lambda _path: "create")
    plan = dry_run.build_smoke_dry_run(ROOT, max_items=3)
    assert plan.logical_calls == 51
    assert plan.maximum_provider_attempts == 204
    assert plan.provider_calls == {
        "cloudflare_workers_ai": 3,
        "gemini": 3,
        "groq": 33,
        "nvidia_nim": 6,
        "openai": 6,
    }
