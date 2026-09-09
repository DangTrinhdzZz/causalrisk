import json
from dataclasses import replace

import pytest

from causalrisk.artifacts import ArtifactError, RunArtifactWriter
from causalrisk.schemas import EventRecord, SchemaError


def event(**changes):
    record = EventRecord(
        run_id="run-001",
        item_id="opaque-001",
        split_name="smoke",
        config_id="A1_SINGLE_V1",
        model_id="synthetic-model",
        provider="synthetic-provider",
        prompt_version="prompt_causal_yesno_v1",
        attempt_index=0,
        role_name="analyst",
        raw_output="Evidence\r\nYES",
        parsed_answer="YES",
        final_answer="YES",
        latency_ms=12.5,
        input_tokens=20,
        output_tokens=5,
        total_tokens=25,
        estimated_cost_usd=0.001,
        status="success",
        failure_type=None,
        timestamp_utc="2026-09-09T00:00:00Z",
        code_version="abc123",
        call_id="call-001",
        retry_eligible=False,
        backoff_seconds=0,
        response_id="response-001",
        http_status=200,
        normalization_actions=(),
        topology_position=0,
        resolution_action="accept",
        included_in_final_vote=True,
        included_in_accuracy_denominator=True,
        included_in_cost_analysis=True,
        notes=None,
    )
    return replace(record, **changes)


def test_event_schema_checks_token_arithmetic():
    with pytest.raises(SchemaError, match="total_tokens"):
        event(total_tokens=99)


def test_event_schema_requires_utc_and_matching_role_position():
    with pytest.raises(SchemaError, match="UTC"):
        event(timestamp_utc="2026-09-09T07:00:00+07:00")
    with pytest.raises(SchemaError, match="role_name"):
        event(config_id="C3_COUNCIL_V1", role_name="critic", topology_position=0)


def test_artifact_writer_preserves_raw_bytes_and_freezes(tmp_path):
    writer = RunArtifactWriter.create(
        tmp_path,
        "run-001",
        resolved_config={"config_id": "A1_SINGLE_V1"},
        manifest_metadata={"split_sha256": "0" * 64},
    )
    record = event()
    writer.write_attempt(record)
    assert (writer.run_dir / "raw" / "call-001.txt").read_bytes() == record.raw_output.encode("utf-8")
    hashes = writer.freeze()
    assert "raw/call-001.txt" in hashes
    manifest = json.loads((writer.run_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["freeze_state"] == "frozen"
    with pytest.raises(ArtifactError, match="frozen"):
        writer.write_attempt(event(call_id="call-002"))


def test_metrics_preview_rejects_gold_aware_fields(tmp_path):
    writer = RunArtifactWriter.create(
        tmp_path,
        "run-001",
        resolved_config={"config_id": "A1_SINGLE_V1"},
        manifest_metadata={},
    )
    with pytest.raises(ArtifactError, match="gold-free"):
        writer.write_metrics_preview({"accuracy": 1.0})


def test_artifacts_reject_secret_bearing_keys(tmp_path):
    with pytest.raises(ArtifactError, match="secret-bearing"):
        RunArtifactWriter.create(
            tmp_path,
            "run-001",
            resolved_config={"api_key": "should-never-be-written"},
            manifest_metadata={},
        )


def test_artifact_writer_rejects_cross_run_event(tmp_path):
    writer = RunArtifactWriter.create(
        tmp_path,
        "run-001",
        resolved_config={"config_id": "A1_SINGLE_V1"},
        manifest_metadata={},
    )
    with pytest.raises(ArtifactError, match="run_id"):
        writer.write_attempt(event(run_id="different-run"))
