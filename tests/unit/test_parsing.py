import json
from pathlib import Path

import pytest

from causalrisk.parsing import parse_structured_yesno, parse_yesno

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize(
    ("raw", "answer", "failure"),
    [
        ("YES", "YES", None),
        (" no \n", "NO", None),
        ("Concise evidence.\nYES", "YES", None),
        ("```text\nNO\n```", "NO", None),
        ("YES because the claim holds", "INVALID", "invalid_label"),
        ("", "INVALID", "response/empty_content"),
        (None, "INVALID", "response/empty_content"),
    ],
)
def test_parse_yesno(raw, answer, failure):
    result = parse_yesno(raw)
    assert result.answer == answer
    assert result.failure_code == failure


def test_structured_parser_distinguishes_failure_types():
    assert parse_structured_yesno('{"answer": "yes"}').answer == "YES"
    assert parse_structured_yesno("not json").failure_code == "parse_failure"
    assert parse_structured_yesno('{"other": "YES"}').failure_code == "schema_failure"
    assert parse_structured_yesno('{"answer": "MAYBE"}').failure_code == "invalid_label"


def test_strict_parser_rejects_the_immutable_r4_raw_output_without_label_inference():
    run_dir = ROOT / "artifacts/runs/cladder-smoke-canary-3-r4"
    failed = next(
        record
        for path in (run_dir / "calls").glob("*/*.json")
        if (record := json.loads(path.read_text(encoding="utf-8"))).get("status") == "failure"
    )
    result = parse_yesno(failed["raw_output"])
    assert result.answer == "INVALID"
    assert result.failure_code == "invalid_label"
