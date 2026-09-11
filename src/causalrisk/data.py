"""Strict label-free data boundary for benchmark inference."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class InferenceDataError(ValueError):
    """Raised when an inference record crosses the frozen data boundary."""


ALLOWED_INFERENCE_FIELDS = frozenset({"item_id", "rung", "background", "given_info", "question"})
FORBIDDEN_INFERENCE_FIELDS = frozenset(
    {
        "answer",
        "reasoning",
        "groundtruth",
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
    rung: int
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
        text_fields = ALLOWED_INFERENCE_FIELDS - {"rung"}
        if not all(isinstance(value[field], str) for field in text_fields):
            raise InferenceDataError("all inference text fields must be strings")
        if value["rung"] not in {1, 2, 3} or isinstance(value["rung"], bool):
            raise InferenceDataError("rung must be integer 1, 2, or 3")
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
            document = json.loads(source.read_text(encoding="utf-8"))
            records = document.get("items") if isinstance(document, dict) else document
    except (OSError, json.JSONDecodeError) as error:
        raise InferenceDataError(f"cannot read label-free inference data: {source}") from error
    if not isinstance(records, list) or not all(isinstance(record, dict) for record in records):
        raise InferenceDataError("inference data must be a list/JSONL stream of objects")
    items = tuple(LabelFreeItem.from_mapping(record) for record in records)
    item_ids = [item.item_id for item in items]
    if len(item_ids) != len(set(item_ids)):
        raise InferenceDataError("item_id values must be unique")
    return items


def verify_inference_view(path: str | Path, expected_source_sha256: str) -> tuple[LabelFreeItem, ...]:
    source = Path(path)
    checksum_path = source.with_suffix(".sha256.json")
    raw = source.read_bytes()
    metadata = json.loads(checksum_path.read_text(encoding="utf-8"))
    document = json.loads(raw)
    if document.get("schema_version") != 1 or document.get("view_kind") != "label_free_inference":
        raise InferenceDataError("unsupported inference-view schema")
    if document.get("split") != "smoke" or document.get("source_manifest_sha256") != expected_source_sha256:
        raise InferenceDataError("inference view does not match the sealed smoke source")
    if metadata.get("source_manifest_sha256") != expected_source_sha256:
        raise InferenceDataError("inference checksum metadata has the wrong source")
    if metadata.get("inference_view_sha256") != hashlib.sha256(raw).hexdigest():
        raise InferenceDataError("inference-view checksum mismatch")
    return load_label_free_items(source)
