from pathlib import Path

import pytest

import causalrisk.dry_run as dry_run
from causalrisk.data import CanarySelection, LabelFreeItem, VerifiedInferenceView

ROOT = Path(__file__).resolve().parents[2]


def test_smoke_dry_run_is_deterministic_and_counts_alias_once(monkeypatch, tmp_path):
    items = tuple(LabelFreeItem(f"item-{index:02d}", "b", "g", "q") for index in range(60))
    view = VerifiedInferenceView(items, 2, "0" * 64, "1" * 64)
    monkeypatch.setattr(dry_run, "_verify_source_manifest", lambda _root, _split: "0" * 64)
    monkeypatch.setattr(dry_run, "verify_inference_view", lambda *_args, **_kwargs: view)
    monkeypatch.setattr(dry_run, "_r5_artifact_state", lambda _path: "create")
    plan = dry_run.build_execution_dry_run(ROOT, split="smoke")
    assert plan.method_calls == {
        "A1_SINGLE_V1": 60,
        "A3_SINGLE_V1": 180,
        "A5_SINGLE_V1": 300,
        "C1_BOUNDARY_V1": 0,
        "C3_COUNCIL_V1": 180,
        "C5_COUNCIL_V1": 300,
    }
    assert plan.provider_calls == {
        "cloudflare_workers_ai": 180,
        "gemini": 60,
        "groq": 660,
        "openai": 120,
    }
    assert plan.logical_calls == 1020
    assert plan.maximum_provider_attempts == 4080
    assert plan.run_id == "cladder-smoke-60-r5"
    assert Path(plan.artifact_path).name == "cladder-smoke-60-r5"
    assert plan.artifacts["C1_BOUNDARY_V1"]["action"] == "alias_existing_a1"


def test_three_item_canary_has_one_item_per_rung_and_51_calls(monkeypatch):
    items = tuple(LabelFreeItem(f"item-{index:02d}", "b", "g", "q") for index in range(60))
    view = VerifiedInferenceView(items, 2, "0" * 64, "1" * 64)
    monkeypatch.setattr(dry_run, "_verify_source_manifest", lambda _root, _split: "0" * 64)
    monkeypatch.setattr(dry_run, "verify_inference_view", lambda *_args, **_kwargs: view)
    monkeypatch.setattr(
        dry_run,
        "select_smoke_canary",
        lambda *_args: CanarySelection(items[:3], "2" * 64),
    )
    monkeypatch.setattr(dry_run, "_r5_artifact_state", lambda _path: "create")
    plan = dry_run.build_execution_dry_run(ROOT, split="smoke", canary=True)
    assert plan.logical_calls == 51
    assert plan.maximum_provider_attempts == 204
    assert plan.run_id == "cladder-smoke-canary-3-r5"
    assert plan.provider_calls == {
        "cloudflare_workers_ai": 9,
        "gemini": 3,
        "groq": 33,
        "openai": 6,
    }


def test_dry_run_rejects_ambiguous_in_progress_artifact(tmp_path):
    run_dir = tmp_path / "cladder-smoke-60-r5"
    run_dir.mkdir()
    (run_dir / "manifest.json").write_text(
        '{"run_status":"in_progress","freeze_state":"open"}',
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="ambiguous in-progress"):
        dry_run._r5_artifact_state(run_dir)


@pytest.mark.parametrize(
    "run_id",
    [
        "cladder-smoke-canary-3",
        "cladder-smoke-canary-3-r2",
        "cladder-smoke-canary-3-r3",
        "cladder-smoke-canary-3-r4",
    ],
)
def test_terminal_legacy_canaries_are_never_resumed(tmp_path, run_id):
    run_dir = tmp_path / run_id
    run_dir.mkdir()
    (run_dir / "manifest.json").write_text(
        '{"run_status":"failed","freeze_state":"frozen"}',
        encoding="utf-8",
    )
    assert dry_run._r5_artifact_state(run_dir) == "terminal_frozen_no_resume_no_overwrite"
