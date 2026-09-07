#!/usr/bin/env python3
"""Deterministically create sealed CLadder v1 evaluation split manifests."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import zipfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ARCHIVE_PATH = Path("data/raw/cladder-v1.zip")
OUTPUT_DIR = Path("data/splits/private")
ARCHIVE_SHA256 = "9fdae052b1ebe4ee6a19fdfb3e1eb88a381c7345df394cea524bcce97e2349b3"
BALANCED_MEMBER = "cladder-v1-q-balanced.json"
MODELS_MEMBER = "cladder-v1-meta-models.json"
PROTOCOL_VERSION = "1.0"
SEED = "20260905"
SPLIT_QUOTAS = {"smoke": 20, "calibration": 100, "locked_test": 200}
CONSISTENCY_FIELDS = ("answer", "meta.rung", "meta.query_type", "meta.graph_id", "meta.story_id")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def nested(item: dict[str, Any], field: str) -> Any:
    value: Any = item
    for part in field.split("."):
        if not isinstance(value, dict) or part not in value:
            return None
        value = value[part]
    return value


def typed_key(value: Any) -> str:
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise TypeError("Identifier has an invalid type")
    return f"{type(value).__name__}:{value}"


def normalize_parts(*values: Any) -> str:
    if not all(isinstance(value, str) for value in values):
        raise TypeError("Prompt fields must be text")
    return "\n".join(" ".join(value.split()).lower() for value in values)


def text_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def stable_rank(*parts: Any) -> str:
    material = json.dumps((SEED, *parts), ensure_ascii=False, separators=(",", ":"))
    return text_hash(material)


def numeric_question_id(item: dict[str, Any]) -> int:
    value = item.get("question_id")
    if isinstance(value, bool):
        raise TypeError("question_id must be numeric")
    try:
        return int(value)
    except (TypeError, ValueError) as error:
        raise TypeError("question_id must be numeric") from error


def load_source() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if not ARCHIVE_PATH.is_file():
        raise FileNotFoundError("Required cached CLadder archive is absent; no download was attempted")
    if sha256_file(ARCHIVE_PATH) != ARCHIVE_SHA256:
        raise ValueError("Cached archive SHA-256 does not match protocol v1.0")
    with zipfile.ZipFile(ARCHIVE_PATH) as archive:
        if BALANCED_MEMBER not in archive.namelist() or MODELS_MEMBER not in archive.namelist():
            raise KeyError("A required audited ZIP member is absent")
        with archive.open(BALANCED_MEMBER) as stream:
            items = json.load(stream)
        with archive.open(MODELS_MEMBER) as stream:
            models = json.load(stream)
    if not isinstance(items, list) or not all(isinstance(item, dict) for item in items):
        raise TypeError("Balanced member must be a JSON list of objects")
    if not isinstance(models, list) or not all(isinstance(model, dict) for model in models):
        raise TypeError("Metadata member must be a JSON list of objects")
    return items, models


def prepare(items: list[dict[str, Any]], models: list[dict[str, Any]]) -> list[dict[str, Any]]:
    backgrounds: dict[str, str] = {}
    for model in models:
        model_key = typed_key(model.get("model_id"))
        background = model.get("background")
        if not isinstance(background, str):
            raise TypeError("A required metadata background is not text")
        if model_key in backgrounds and backgrounds[model_key] != background:
            raise ValueError("Conflicting metadata backgrounds exist")
        backgrounds[model_key] = background

    prompt_hashes: list[str] = []
    prompt_members: dict[str, list[int]] = defaultdict(list)
    model_members: dict[str, list[int]] = defaultdict(list)
    for index, item in enumerate(items):
        model_key = typed_key(nested(item, "meta.model_id"))
        if model_key not in backgrounds:
            raise KeyError("A source item lacks its required metadata background")
        prompt_hash = text_hash(normalize_parts(backgrounds[model_key], item.get("given_info"), item.get("question")))
        prompt_hashes.append(prompt_hash)
        prompt_members[prompt_hash].append(index)
        model_members[model_key].append(index)

    quarantined: set[int] = set()
    canonical: set[int] = set()
    for members in prompt_members.values():
        inconsistent = any(
            len({json.dumps(nested(items[index], field), sort_keys=True, ensure_ascii=False) for index in members}) > 1
            for field in CONSISTENCY_FIELDS
        )
        if inconsistent:
            quarantined.update(members)
        else:
            canonical.add(min(members, key=lambda index: (numeric_question_id(items[index]), index)))
    if quarantined:
        raise ValueError("Inconsistent full-prompt duplicate groups found; split generation is blocked")
    if len(canonical) != 8917:
        raise ValueError("Canonical candidate-pool size differs from the audited protocol value")

    parent = list(range(len(items)))
    size = [1] * len(items)

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    def union(left: int, right: int) -> None:
        left, right = find(left), find(right)
        if left == right:
            return
        if size[left] < size[right]:
            left, right = right, left
        parent[right] = left
        size[left] += size[right]

    for groups in (model_members.values(), prompt_members.values()):
        for members in groups:
            for index in members[1:]:
                union(members[0], index)

    family_first: dict[int, int] = {}
    for index in range(len(items)):
        root = find(index)
        family_first[root] = min(family_first.get(root, index), index)

    candidates = []
    for index in sorted(canonical):
        item = items[index]
        answer = str(item.get("answer", "")).strip().casefold()
        rung = nested(item, "meta.rung")
        if answer not in {"yes", "no"} or rung not in {1, 2, 3}:
            raise ValueError("A canonical candidate has an invalid answer or rung")
        candidates.append({
            "source_index": index,
            "question_id": item["question_id"],
            "prompt_hash": prompt_hashes[index],
            "family": text_hash(f"family-v1:{family_first[find(index)]}"),
            "rung": rung,
            "answer": answer,
            "query_type": str(nested(item, "meta.query_type")),
            "graph_id": str(nested(item, "meta.graph_id")),
            "story_id": str(nested(item, "meta.story_id")),
            "tie_rank": stable_rank("candidate", index),
        })
    return candidates


def allocate(candidates: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    pool_query = Counter((c["rung"], c["query_type"]) for c in candidates)
    pool_rung = Counter(c["rung"] for c in candidates)
    selected = {name: [] for name in SPLIT_QUOTAS}
    family_owner: dict[str, str] = {}
    used_indices: set[int] = set()
    counts: Counter[tuple[str, int, str]] = Counter()
    query_counts: Counter[tuple[str, int, str]] = Counter()
    graph_counts: Counter[tuple[str, int, str]] = Counter()
    story_counts: Counter[tuple[str, int, str]] = Counter()

    slots = []
    for split, per_rung in SPLIT_QUOTAS.items():
        for rung in (1, 2, 3):
            for answer in ("yes", "no"):
                slots.extend((split, rung, answer) for _ in range(per_rung // 2))
    slots.sort(key=lambda slot: stable_rank("slot", *slot, slots[:0]))

    for step, (split, rung, answer) in enumerate(slots):
        eligible = [c for c in candidates if c["source_index"] not in used_indices and c["rung"] == rung
                    and c["answer"] == answer and family_owner.get(c["family"], split) == split]
        if not eligible:
            raise RuntimeError("Hard split constraints are infeasible; no sealed split was created")

        def score(candidate: dict[str, Any]) -> tuple[Any, ...]:
            query = candidate["query_type"]
            target = pool_query[rung, query] * SPLIT_QUOTAS[split] / pool_rung[rung]
            after_deviation = abs((query_counts[split, rung, query] + 1) - target)
            already_owned = 0 if family_owner.get(candidate["family"]) == split else 1
            graph_repeat = graph_counts[split, rung, candidate["graph_id"]]
            story_repeat = story_counts[split, rung, candidate["story_id"]]
            return (after_deviation, already_owned, graph_repeat, story_repeat,
                    candidate["tie_rank"])

        chosen = min(eligible, key=score)
        family_owner.setdefault(chosen["family"], split)
        used_indices.add(chosen["source_index"])
        selected[split].append(chosen)
        counts[split, rung, answer] += 1
        query_counts[split, rung, chosen["query_type"]] += 1
        graph_counts[split, rung, chosen["graph_id"]] += 1
        story_counts[split, rung, chosen["story_id"]] += 1

    for split, per_rung in SPLIT_QUOTAS.items():
        if len(selected[split]) != 3 * per_rung:
            raise RuntimeError("Exact split size was not achieved")
        if any(counts[split, rung, answer] != per_rung // 2 for rung in (1, 2, 3) for answer in ("yes", "no")):
            raise RuntimeError("Exact rung/label allocation was not achieved")
        selected[split].sort(key=lambda c: stable_rank("manifest-order", split, c["source_index"]))
    return selected


def manifest(split: str, candidates: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "protocol_version": PROTOCOL_VERSION,
        "seed": SEED,
        "source": {"archive_sha256": ARCHIVE_SHA256, "member": BALANCED_MEMBER},
        "split": split,
        "items": [{key: candidate[key] for key in ("source_index", "question_id", "prompt_hash", "family")}
                  for candidate in candidates],
    }


def write_splits(selected: dict[str, list[dict[str, Any]]], overwrite: bool) -> None:
    if OUTPUT_DIR.exists() and not overwrite:
        raise FileExistsError("Sealed split directory already exists; pass --overwrite to replace it")
    OUTPUT_DIR.parent.mkdir(parents=True, exist_ok=True)
    temporary = OUTPUT_DIR.parent / ".private-build"
    if temporary.exists():
        raise FileExistsError("A prior temporary split build exists; remove it only after confirming no generator is running")
    temporary.mkdir()
    try:
        for split, candidates in selected.items():
            path = temporary / f"{split}.json"
            path.write_text(json.dumps(manifest(split, candidates), ensure_ascii=False, indent=2) + "\n",
                            encoding="utf-8", newline="\n")
        if OUTPUT_DIR.exists():
            shutil.rmtree(OUTPUT_DIR)
        os.replace(temporary, OUTPUT_DIR)
    except BaseException:
        if temporary.exists():
            shutil.rmtree(temporary)
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--overwrite", action="store_true", help="replace an existing sealed split directory")
    args = parser.parse_args()
    items, models = load_source()
    selected = allocate(prepare(items, models))
    write_splits(selected, args.overwrite)
    print("Sealed CLadder splits created successfully (record-level details suppressed).")


if __name__ == "__main__":
    main()
