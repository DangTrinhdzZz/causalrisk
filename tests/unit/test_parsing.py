import pytest

from causalrisk.parsing import parse_structured_yesno, parse_yesno


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
