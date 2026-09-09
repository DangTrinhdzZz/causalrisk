"""Deterministic parsing for the frozen YES/NO output contract."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Literal

Answer = Literal["YES", "NO", "INVALID"]


@dataclass(frozen=True, slots=True)
class ParseResult:
    """Auditable result of deterministic, semantic-preserving normalization."""

    answer: Answer
    failure_code: str | None
    normalizations: tuple[str, ...]


def _strip_single_code_fence(text: str) -> tuple[str, bool]:
    lines = text.splitlines()
    if len(lines) >= 2 and lines[0].strip().startswith("```") and lines[-1].strip() == "```":
        return "\n".join(lines[1:-1]), True
    return text, False


def parse_yesno(raw_output: str | None) -> ParseResult:
    """Parse the last non-empty line as exactly YES or NO.

    Only surrounding whitespace, one enclosing Markdown fence, and label case are
    normalized. The function never guesses a model's intended answer.
    """

    if raw_output is None or not raw_output.strip():
        return ParseResult("INVALID", "response/empty_content", ())

    normalizations: list[str] = []
    text = raw_output.strip()
    if text != raw_output:
        normalizations.append("trim_surrounding_whitespace")

    text, fence_removed = _strip_single_code_fence(text)
    if fence_removed:
        normalizations.append("remove_markdown_code_fence")

    non_empty_lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not non_empty_lines:
        return ParseResult("INVALID", "response/empty_content", tuple(normalizations))

    final_line = non_empty_lines[-1]
    canonical = final_line.upper()
    if canonical not in {"YES", "NO"}:
        return ParseResult("INVALID", "invalid_label", tuple(normalizations))
    if final_line != canonical:
        normalizations.append("canonicalize_label_case")
    return ParseResult(canonical, None, tuple(normalizations))  # type: ignore[arg-type]


def parse_structured_yesno(raw_output: str | None, answer_field: str = "answer") -> ParseResult:
    """Parse a provider-native JSON object containing a YES/NO answer field."""

    if raw_output is None or not raw_output.strip():
        return ParseResult("INVALID", "response/empty_content", ())

    normalizations: list[str] = []
    text = raw_output.strip()
    if text != raw_output:
        normalizations.append("trim_surrounding_whitespace")
    text, fence_removed = _strip_single_code_fence(text)
    if fence_removed:
        normalizations.append("remove_markdown_code_fence")

    try:
        document = json.loads(text)
    except json.JSONDecodeError:
        return ParseResult("INVALID", "parse_failure", tuple(normalizations))
    if not isinstance(document, dict) or answer_field not in document:
        return ParseResult("INVALID", "schema_failure", tuple(normalizations))
    label = document[answer_field]
    if not isinstance(label, str) or label.strip().upper() not in {"YES", "NO"}:
        return ParseResult("INVALID", "invalid_label", tuple(normalizations))
    canonical = label.strip().upper()
    if label != canonical:
        normalizations.append("canonicalize_label_case")
    return ParseResult(canonical, None, tuple(normalizations))  # type: ignore[arg-type]
