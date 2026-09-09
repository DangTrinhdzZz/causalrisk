"""Score only complete, frozen inference artifacts against explicit gold labels."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


class ScoringError(RuntimeError):
    """Raised when scoring would violate the frozen inference/scoring boundary."""


@dataclass(frozen=True, slots=True)
class ScoreSummary:
    run_id: str
    evaluable_items: int
    completed_items: int
    correct_items: int
    accuracy: float
    completion_rate: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ScoringError(f"cannot read required scoring input: {path}") from error


def _load_gold(path: Path) -> dict[str, str]:
    document = _load_json(path)
    if not isinstance(document, list):
        raise ScoringError("gold file must be a list of item_id/answer records")
    gold: dict[str, str] = {}
    for record in document:
        if not isinstance(record, dict) or set(record) != {"item_id", "answer"}:
            raise ScoringError("each gold record must contain only item_id and answer")
        item_id, answer = record["item_id"], record["answer"]
        if not isinstance(item_id, str) or answer not in {"YES", "NO"} or item_id in gold:
            raise ScoringError("gold records contain an invalid or duplicate item")
        gold[item_id] = answer
    return gold


def score_frozen_run(run_dir: str | Path, gold_path: str | Path) -> ScoreSummary:
    run = Path(run_dir)
    manifest = _load_json(run / "manifest.json")
    if not isinstance(manifest, dict) or manifest.get("freeze_state") != "frozen":
        raise ScoringError("inference artifacts must be frozen before gold labels are loaded")
    if manifest.get("run_status") != "complete":
        raise ScoringError("incomplete or run-blocked inference artifacts cannot be scored as a complete run")
    run_id = manifest.get("run_id")
    if not isinstance(run_id, str) or not run_id:
        raise ScoringError("frozen manifest has no valid run_id")

    # Gold loading deliberately occurs only after the freeze-state gate above.
    gold = _load_gold(Path(gold_path))
    predictions: dict[str, str | None] = {}
    for path in sorted((run / "parsed").glob("*.json")):
        record = _load_json(path)
        if not isinstance(record, dict):
            raise ScoringError("parsed artifact must be an object")
        item_id = record.get("item_id")
        final_answer = record.get("final_answer")
        if not isinstance(item_id, str) or final_answer not in {"YES", "NO", None}:
            raise ScoringError("parsed artifact contains an invalid item or final answer")
        if item_id in predictions and final_answer is not None:
            raise ScoringError("multiple final answers exist for one item")
        if final_answer is not None or item_id not in predictions:
            predictions[item_id] = final_answer

    unknown = set(predictions) - set(gold)
    if unknown:
        raise ScoringError("prediction artifacts contain item IDs absent from the gold file")
    completed = sum(predictions.get(item_id) in {"YES", "NO"} for item_id in gold)
    correct = sum(predictions.get(item_id) == answer for item_id, answer in gold.items())
    evaluable = len(gold)
    if evaluable == 0:
        raise ScoringError("gold file contains no evaluable items")
    return ScoreSummary(
        run_id=run_id,
        evaluable_items=evaluable,
        completed_items=completed,
        correct_items=correct,
        accuracy=correct / evaluable,
        completion_rate=completed / evaluable,
    )
