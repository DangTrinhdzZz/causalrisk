"""Fail-closed helpers for normalizing provider response documents."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from causalrisk.retry import ClassifiedFailure


def schema_failure(detail: str) -> ClassifiedFailure:
    return ClassifiedFailure("response/schema_failure", f"provider response schema mismatch: {detail}")


def as_mapping(value: Any, detail: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise schema_failure(detail)
    return value


def as_sequence(value: Any, detail: str) -> Sequence[Any]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise schema_failure(detail)
    return value


def optional_string(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None


def optional_token(value: Any, detail: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise schema_failure(detail)
    return value


def chat_content_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    parts = as_sequence(value, "message content is neither text nor a content-part list")
    texts: list[str] = []
    for part_value in parts:
        part = as_mapping(part_value, "message content part is not an object")
        text = part.get("text")
        if isinstance(text, str):
            texts.append(text)
    if not texts:
        raise schema_failure("message contains no text content")
    return "\n".join(texts)
