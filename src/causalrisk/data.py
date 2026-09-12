"""Strict cross-split label-free data boundary for benchmark inference."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from causalrisk.execution_policy import VIEW_SCHEMA_VERSION


class InferenceDataError(ValueError):
    """Raised when an inference record crosses the frozen data boundary."""


ALLOWED_INFERENCE_FIELDS = frozenset({"item_id", "background", "given_info", "question"})
FORBIDDEN_INFERENCE_FIELDS = frozenset(
    {
        "answer",
        "label",
        "reasoning",
        "rung",
        "groundtruth",
        "ground_truth",
        "query_type",
        "graph_id",
        "story_id",
        "model_id",
        "question_id",
        "split",
        "split_name",
        "split_membership",
        "family",
        "protected_family",
        "prompt_hash",
        "source_index",
    }
)
INFERENCE_VIEW_FIELDS = frozenset(
    {"schema_version", "view_kind", "source_manifest_sha256", "item_count", "items"}
)
CHECKSUM_SIDECAR_FIELDS = frozenset(
    {"schema_version", "view_kind", "source_manifest_sha256", "inference_view_sha256", "item_count"}
)


@dataclass(frozen=True, slots=True)
class LabelFreeItem:
    """Only information authorized for local routing and model-context projection."""

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


@dataclass(frozen=True, slots=True)
class VerifiedInferenceView:
    items: tuple[LabelFreeItem, ...]
    schema_version: int
    source_manifest_sha256: str
    inference_view_sha256: str


@dataclass(frozen=True, slots=True)
class CanarySelection:
    items: tuple[LabelFreeItem, ...]
    selector_sha256: str


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


def verify_inference_view(
    path: str | Path,
    expected_source_sha256: str,
    *,
    expected_item_count: int,
) -> VerifiedInferenceView:
    """Verify a v2 view without accepting split membership or protected metadata."""

    source = Path(path)
    checksum_path = source.with_suffix(".sha256.json")
    try:
        raw = source.read_bytes()
        metadata = json.loads(checksum_path.read_text(encoding="utf-8"))
        document = json.loads(raw)
    except (OSError, json.JSONDecodeError) as error:
        raise InferenceDataError(f"cannot verify inference view: {source}") from error
    if not isinstance(document, dict) or set(document) != INFERENCE_VIEW_FIELDS:
        raise InferenceDataError("inference-view document fields do not match schema v2")
    if not isinstance(metadata, dict) or set(metadata) != CHECKSUM_SIDECAR_FIELDS:
        raise InferenceDataError("inference-view checksum fields do not match schema v2")
    if document.get("schema_version") != VIEW_SCHEMA_VERSION or document.get("view_kind") != "label_free_inference":
        raise InferenceDataError("unsupported inference-view schema")
    if metadata.get("schema_version") != VIEW_SCHEMA_VERSION or metadata.get("view_kind") != "label_free_inference":
        raise InferenceDataError("unsupported inference-view checksum schema")
    if document.get("source_manifest_sha256") != expected_source_sha256:
        raise InferenceDataError("inference view does not match the sealed source manifest")
    if metadata.get("source_manifest_sha256") != expected_source_sha256:
        raise InferenceDataError("inference checksum metadata has the wrong source")
    if document.get("item_count") != expected_item_count or metadata.get("item_count") != expected_item_count:
        raise InferenceDataError("inference-view item count differs from the split policy")
    view_sha256 = hashlib.sha256(raw).hexdigest()
    if metadata.get("inference_view_sha256") != view_sha256:
        raise InferenceDataError("inference-view checksum mismatch")
    items = load_label_free_items(source)
    if len(items) != expected_item_count:
        raise InferenceDataError("inference-view records differ from declared item_count")
    return VerifiedInferenceView(items, VIEW_SCHEMA_VERSION, expected_source_sha256, view_sha256)


def select_smoke_canary(view: VerifiedInferenceView, selector_path: str | Path) -> CanarySelection:
    """Apply the local controller-only rung selector without carrying rung into inference items."""

    path = Path(selector_path)
    try:
        raw = path.read_bytes()
        document = json.loads(raw)
    except (OSError, json.JSONDecodeError) as error:
        raise InferenceDataError(f"cannot verify smoke canary selector: {path}") from error
    expected_fields = {
        "schema_version",
        "selection_kind",
        "source_manifest_sha256",
        "inference_view_sha256",
        "item_count",
        "items",
    }
    if not isinstance(document, dict) or set(document) != expected_fields:
        raise InferenceDataError("smoke canary selector fields are invalid")
    if (
        document.get("schema_version") != 1
        or document.get("selection_kind") != "controller_only_one_item_per_rung"
        or document.get("source_manifest_sha256") != view.source_manifest_sha256
        or document.get("inference_view_sha256") != view.inference_view_sha256
        or document.get("item_count") != 3
    ):
        raise InferenceDataError("smoke canary selector lineage is invalid")
    selected = document.get("items")
    if not isinstance(selected, list) or len(selected) != 3:
        raise InferenceDataError("smoke canary selector must contain three entries")
    by_rung: dict[int, str] = {}
    for entry in selected:
        if not isinstance(entry, dict) or set(entry) != {"item_id", "rung"}:
            raise InferenceDataError("smoke canary selector entry is invalid")
        item_id, rung = entry["item_id"], entry["rung"]
        if not isinstance(item_id, str) or not item_id or rung not in {1, 2, 3} or isinstance(rung, bool):
            raise InferenceDataError("smoke canary selector value is invalid")
        if rung in by_rung:
            raise InferenceDataError("smoke canary selector repeats a rung")
        by_rung[rung] = item_id
    indexed = {item.item_id: item for item in view.items}
    if any(item_id not in indexed for item_id in by_rung.values()):
        raise InferenceDataError("smoke canary selector references an item outside the inference view")
    items = tuple(indexed[by_rung[rung]] for rung in (1, 2, 3))
    if len({item.item_id for item in items}) != 3:
        raise InferenceDataError("smoke canary selector repeats an item")
    return CanarySelection(items, hashlib.sha256(raw).hexdigest())
