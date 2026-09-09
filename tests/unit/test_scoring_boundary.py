import json

import pytest

from causalrisk.artifacts import RunArtifactWriter
from causalrisk.schemas import EventRecord
from causalrisk.scoring import score_frozen_run
from causalrisk.scoring.core import ScoringError


def _event():
    return EventRecord(
        run_id="run-001",
        item_id="opaque-001",
        split_name="smoke",
        config_id="A1_SINGLE_V1",
        model_id="synthetic-model",
        provider="synthetic-provider",
        prompt_version="prompt_causal_yesno_v1",
        attempt_index=0,
        role_name="analyst",
        raw_output="YES",
        parsed_answer="YES",
        final_answer="YES",
        latency_ms=1,
        input_tokens=1,
        output_tokens=1,
        total_tokens=2,
        estimated_cost_usd=0,
        status="success",
        failure_type=None,
        timestamp_utc="2026-09-09T00:00:00Z",
        code_version="abc123",
        call_id="call-001",
        retry_eligible=False,
        backoff_seconds=0,
        response_id=None,
        http_status=200,
        normalization_actions=(),
        topology_position=0,
        resolution_action="accept",
        included_in_final_vote=True,
        included_in_accuracy_denominator=True,
        included_in_cost_analysis=True,
    )


def _gold(path):
    path.write_text(json.dumps([{"item_id": "opaque-001", "answer": "YES"}]), encoding="utf-8")


def test_scorer_refuses_to_load_gold_before_freeze(tmp_path):
    writer = RunArtifactWriter.create(
        tmp_path / "runs",
        "run-001",
        resolved_config={"config_id": "A1_SINGLE_V1"},
        manifest_metadata={},
    )
    gold = tmp_path / "gold.json"
    _gold(gold)
    with pytest.raises(ScoringError, match="frozen"):
        score_frozen_run(writer.run_dir, gold)


def test_scorer_uses_end_to_end_denominator_after_freeze(tmp_path):
    writer = RunArtifactWriter.create(
        tmp_path / "runs",
        "run-001",
        resolved_config={"config_id": "A1_SINGLE_V1"},
        manifest_metadata={},
    )
    writer.write_attempt(_event())
    writer.freeze()
    gold = tmp_path / "gold.json"
    _gold(gold)
    summary = score_frozen_run(writer.run_dir, gold)
    assert summary.accuracy == 1.0
    assert summary.completion_rate == 1.0


def test_scorer_rejects_frozen_but_incomplete_run(tmp_path):
    writer = RunArtifactWriter.create(
        tmp_path / "runs",
        "run-001",
        resolved_config={"config_id": "A1_SINGLE_V1"},
        manifest_metadata={},
    )
    writer.freeze(final_status="incomplete")
    gold = tmp_path / "gold.json"
    _gold(gold)
    with pytest.raises(ScoringError, match="incomplete"):
        score_frozen_run(writer.run_dir, gold)
