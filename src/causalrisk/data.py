"""Strict label-free data boundary for benchmark inference."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class InferenceDataError(ValueError):
    """Raised when an inference record crosses the frozen data boundary."""


ALLOWED_INFERENCE_FIELDS = frozenset({"item_id", "background", "given_info", "question"})
FORBIDDEN_INFERENCE_FIELDS = frozenset(
    {
        "answer",
        "reasoning",
        "groundtruth",
        "rung",
        "query_type",
        "graph_id",
        "story_id",
        "model_id",
        "question_id",
        "split",
        "split_name",
        "family",
        "protected_family",
        "prompt_hash",
        "source_index",
    }
)


@dataclass(frozen=True, slots=True)
class LabelFreeItem:
    """Only information authorized for the inference process."""

    item_id: str
    background: str
    given_info: str
    question: str

    @classmethod
    def from_mapping(cls, value: dict[str, Any]) -> LabelFreeItem:
        keys = set(value)
        forbidden = keys & FORBIDDEN_INFERENCE_FIELDS
        unknown = keys - ALLOWED_INFERENCE_FIELDS
        missing = ALLOWED_INFERENCE_FIELDS - keys
        if forbidden or unknown or missing:
            raise InferenceDataError(
                f"inference fields mismatch; forbidden={sorted(forbidden)}, "
                f"unknown={sorted(unknown)}, missing={sorted(missing)}"
            )
        if not all(isinstance(value[field], str) for field in ALLOWED_INFERENCE_FIELDS):
            raise InferenceDataError("all inference fields must be strings")
        if not value["item_id"].strip() or not value["question"].strip():
            raise InferenceDataError("item_id and question must be non-empty")
        return cls(**{field: value[field] for field in ALLOWED_INFERENCE_FIELDS})

    def model_context(self) -> dict[str, str]:
        """Return the explicit model-facing allowlist; item_id stays local."""

        return {
            "background": self.background,
            "given_info": self.given_info,
            "question": self.question,
        }


def load_label_free_items(path: str | Path) -> tuple[LabelFreeItem, ...]:
    """Load a pre-materialized label-free JSON or JSONL inference file.

    Raw CLadder records are intentionally unsupported because they contain gold
    labels and protected metadata. A trusted preparation stage must project them
    into this strict schema before the inference runner can consume them.
    """

    source = Path(path)
    try:
        if source.suffix.casefold() == ".jsonl":
            records = [json.loads(line) for line in source.read_text(encoding="utf-8").splitlines() if line.strip()]
        else:
            records = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise InferenceDataError(f"cannot read label-free inference data: {source}") from error
    if not isinstance(records, list) or not all(isinstance(record, dict) for record in records):
        raise InferenceDataError("inference data must be a list/JSONL stream of objects")
    items = tuple(LabelFreeItem.from_mapping(record) for record in records)
    item_ids = [item.item_id for item in items]
    if len(item_ids) != len(set(item_ids)):
        raise InferenceDataError("item_id values must be unique")
    return items
