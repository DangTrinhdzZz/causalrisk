import json

from causalrisk.runtime_evidence import audit_runtime_evidence


def write_report(path, **changes):
    report = {
        "schema_version": 1,
        "smoke_kind": "synthetic_non_benchmark",
        "status": "success",
        "provider": "groq",
        "requested_model_id": "openai/gpt-oss-120b",
        "reported_model_id": "openai/gpt-oss-120b",
        "parsed_answer": "YES",
        "latency_ms": 1.0,
        "input_tokens": 2,
        "output_tokens": 1,
        "http_status": 200,
        "retry_events": [],
        "contains_raw_output": False,
    }
    report.update(changes)
    path.write_text(json.dumps(report), encoding="utf-8")


def test_evidence_audit_accepts_exact_success_without_timestamp_dependency(tmp_path):
    write_report(tmp_path / "arbitrary-name.json")
    audit = audit_runtime_evidence(tmp_path)
    assert audit.accepted["groq"].name == "arbitrary-name.json"
    assert "groq" not in audit.missing_primary_providers


def test_evidence_audit_rejects_failures_and_model_mismatches(tmp_path):
    write_report(tmp_path / "failure.json", status="failure")
    write_report(tmp_path / "wrong-model.json", requested_model_id="wrong")
    audit = audit_runtime_evidence(tmp_path)
    assert "groq" not in audit.accepted
    assert len(audit.rejected) == 2
    assert "groq" in audit.missing_primary_providers
