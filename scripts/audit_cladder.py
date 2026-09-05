#!/usr/bin/env python3
"""Audit the locally cached official CLadder v1 balanced dataset.

Uses only the Python standard library, reads JSON members directly from the ZIP,
and creates no dataset split.
"""

from __future__ import annotations

import hashlib
import json
import math
import statistics
import zipfile
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any


SOURCE_URL = "https://github.com/causalNLP/cladder/raw/main/data/cladder-v1.zip"
ARCHIVE_PATH = Path("data/raw/cladder-v1.zip")
REPORT_PATH = Path("docs/cladder_data_audit.md")
BALANCED_MEMBER = "cladder-v1-q-balanced.json"
MODELS_MEMBER = "cladder-v1-meta-models.json"

REQUIRED_FIELDS = (
    "question_id",
    "desc_id",
    "given_info",
    "question",
    "answer",
    "meta.query_type",
    "meta.rung",
    "meta.story_id",
    "meta.graph_id",
    "meta.model_id",
    "meta.groundtruth",
)


def sha256(path: Path) -> str:
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


def is_missing(value: Any) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def is_valid(field: str, value: Any) -> bool:
    if is_missing(value):
        return False
    if field in {"given_info", "question"}:
        return isinstance(value, str)
    if field == "answer":
        return isinstance(value, str) and value.strip().casefold() in {"yes", "no"}
    if field == "meta.rung":
        return isinstance(value, int) and value in {1, 2, 3}
    if field == "meta.groundtruth":
        return isinstance(value, (str, int, float, bool)) or (
            isinstance(value, list)
            and all(isinstance(member, (str, int, float, bool)) for member in value)
        )
    if isinstance(value, bool):
        return False
    return isinstance(value, (str, int))


def key(value: Any) -> str:
    """Stable, type-aware representation for identifier counters."""
    return f"{type(value).__name__}:{value}"


def display_key(value: str) -> str:
    return value.split(":", 1)[1]


def normalize_parts(*values: Any) -> str:
    """Lowercase and collapse whitespace without otherwise changing text."""
    cleaned = [" ".join(value.split()).lower() if isinstance(value, str) else "" for value in values]
    return "\n".join(cleaned)


def text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def nearest_rank_p95(values: list[int]) -> int:
    if not values:
        return 0
    ordered = sorted(values)
    return ordered[math.ceil(0.95 * len(ordered)) - 1]


def sorted_counts(counter: Counter[str]) -> list[tuple[str, int]]:
    return sorted(counter.items(), key=lambda pair: (-pair[1], display_key(pair[0])))


def count_table(counter: Counter[str], first_heading: str) -> str:
    rows = [f"| {first_heading} | Count |", "|---|---:|"]
    rows.extend(f"| `{display_key(value)}` | {count:,} |" for value, count in sorted_counts(counter))
    return "\n".join(rows)


def distribution_table(counter: Counter[int]) -> str:
    rows = ["| Cell size | Non-empty cells |", "|---:|---:|"]
    rows.extend(f"| {size:,} | {count:,} |" for size, count in sorted(counter.items()))
    return "\n".join(rows)


def audit(items: list[dict[str, Any]], models: list[dict[str, Any]]) -> dict[str, Any]:
    field_quality: dict[str, tuple[int, int]] = {}
    for field in REQUIRED_FIELDS:
        values = [nested(item, field) for item in items]
        missing = sum(is_missing(value) for value in values)
        invalid = sum(not is_missing(value) and not is_valid(field, value) for value in values)
        field_quality[field] = (missing, invalid)

    answers = Counter(
        str(item.get("answer", "")).strip().casefold()
        for item in items
        if not is_missing(item.get("answer"))
    )

    def meta_counter(field: str) -> Counter[str]:
        values = (nested(item, f"meta.{field}") for item in items)
        return Counter(key(value) for value in values if not is_missing(value))

    rung = meta_counter("rung")
    query = meta_counter("query_type")
    graph = meta_counter("graph_id")
    story = meta_counter("story_id")
    model = meta_counter("model_id")

    cells: Counter[tuple[str, str, str]] = Counter()
    for item in items:
        values = tuple(nested(item, f"meta.{field}") for field in ("graph_id", "query_type", "story_id"))
        if not any(is_missing(value) for value in values):
            cells[tuple(key(value) for value in values)] += 1  # type: ignore[arg-type]

    required_models = set(model)
    available_models = {
        key(entry.get("model_id"))
        for entry in models
        if isinstance(entry, dict) and not is_missing(entry.get("model_id"))
    }
    group_sizes = list(model.values())

    backgrounds: dict[str, str] = {}
    for entry in models:
        model_id = entry.get("model_id")
        if is_missing(model_id):
            continue
        background = entry.get("background")
        if not isinstance(background, str):
            raise TypeError(f"Metadata background is not text for model {model_id!r}")
        model_key = key(model_id)
        if model_key in backgrounds and backgrounds[model_key] != background:
            raise ValueError(f"Conflicting backgrounds for model {model_id!r}")
        backgrounds[model_key] = background

    question_hashes: list[str] = []
    prompt_hashes: list[str] = []
    question_members: dict[str, list[int]] = {}
    prompt_members: dict[str, list[int]] = {}
    for index, item in enumerate(items):
        model_key = key(nested(item, "meta.model_id"))
        if model_key not in backgrounds:
            raise KeyError(f"No metadata background for item {index} model_id")
        question_hash = text_hash(normalize_parts(item.get("given_info"), item.get("question")))
        prompt_hash = text_hash(
            normalize_parts(backgrounds[model_key], item.get("given_info"), item.get("question"))
        )
        question_hashes.append(question_hash)
        prompt_hashes.append(prompt_hash)
        question_members.setdefault(question_hash, []).append(index)
        prompt_members.setdefault(prompt_hash, []).append(index)

    question_duplicate_groups = [members for members in question_members.values() if len(members) > 1]
    prompt_duplicate_groups = [members for members in prompt_members.values() if len(members) > 1]
    consistency_fields = {
        "answer": "answer",
        "rung": "meta.rung",
        "query type": "meta.query_type",
        "graph ID": "meta.graph_id",
        "story ID": "meta.story_id",
    }
    prompt_inconsistent_by_field: Counter[str] = Counter()
    prompt_inconsistent_groups = 0
    for members in prompt_duplicate_groups:
        inconsistent = False
        for label, field in consistency_fields.items():
            values = {
                json.dumps(nested(items[index], field), sort_keys=True, ensure_ascii=False)
                for index in members
            }
            if len(values) > 1:
                prompt_inconsistent_by_field[label] += 1
                inconsistent = True
        prompt_inconsistent_groups += inconsistent

    prompt_model_mixed_groups = sum(
        len({key(nested(items[index], "meta.model_id")) for index in members}) > 1
        for members in prompt_duplicate_groups
    )

    def numeric_question_id(index: int) -> int:
        question_id = items[index].get("question_id")
        if isinstance(question_id, bool):
            raise TypeError(f"question_id is not numeric at item {index}")
        try:
            return int(question_id)
        except (TypeError, ValueError) as error:
            raise TypeError(f"question_id is not numeric at item {index}") from error

    # Canonical selection is computed for every consistent duplicate group. The
    # original membership remains intact below when protected families are built.
    canonical_duplicate_candidates = {
        min(members, key=lambda index: (numeric_question_id(index), index))
        for members in prompt_duplicate_groups
        if not any(
            len({
                json.dumps(nested(items[index], field), sort_keys=True, ensure_ascii=False)
                for index in members
            }) > 1
            for field in consistency_fields.values()
        )
    }
    prompt_redundant_items = sum(len(members) - 1 for members in prompt_duplicate_groups)

    parent = list(range(len(items)))
    component_size = [1] * len(items)

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    def union(left: int, right: int) -> None:
        left_root, right_root = find(left), find(right)
        if left_root == right_root:
            return
        if component_size[left_root] < component_size[right_root]:
            left_root, right_root = right_root, left_root
        parent[right_root] = left_root
        component_size[left_root] += component_size[right_root]

    first_by_model: dict[str, int] = {}
    first_by_prompt: dict[str, int] = {}
    for index, item in enumerate(items):
        model_key = key(nested(item, "meta.model_id"))
        if model_key in first_by_model:
            union(index, first_by_model[model_key])
        else:
            first_by_model[model_key] = index
        prompt_hash = prompt_hashes[index]
        if prompt_hash in first_by_prompt:
            union(index, first_by_prompt[prompt_hash])
        else:
            first_by_prompt[prompt_hash] = index

    protected_members: dict[int, list[int]] = {}
    for index in range(len(items)):
        protected_members.setdefault(find(index), []).append(index)
    protected_groups = list(protected_members.values())
    protected_sizes = [len(members) for members in protected_groups]
    protected_by_rung: Counter[str] = Counter()
    protected_by_answer: Counter[str] = Counter()
    protected_mixed_rung = 0
    protected_mixed_answer = 0
    for members in protected_groups:
        rungs = {key(nested(items[index], "meta.rung")) for index in members}
        answers_in_group = {key(str(items[index].get("answer", "")).strip().lower()) for index in members}
        protected_by_rung.update(rungs)
        protected_by_answer.update(answers_in_group)
        protected_mixed_rung += len(rungs) > 1
        protected_mixed_answer += len(answers_in_group) > 1

    protected_largest = []
    for rank, members in enumerate(sorted(protected_groups, key=lambda group: (-len(group), min(group)))[:10], 1):
        protected_largest.append(
            {
                "rank": rank,
                "size": len(members),
                "models": len({key(nested(items[index], "meta.model_id")) for index in members}),
                "prompts": len({prompt_hashes[index] for index in members}),
                "rungs": ", ".join(sorted(display_key(value) for value in {
                    key(nested(items[index], "meta.rung")) for index in members
                })),
                "answers": ", ".join(sorted(display_key(value) for value in {
                    key(str(items[index].get("answer", "")).strip().lower()) for index in members
                })),
            }
        )

    return {
        "answers": answers,
        "cells": cells,
        "cell_distribution": Counter(cells.values()),
        "question_duplicate_groups": len(question_duplicate_groups),
        "question_duplicate_items": sum(len(members) - 1 for members in question_duplicate_groups),
        "prompt_duplicate_groups": len(prompt_duplicate_groups),
        "prompt_duplicate_items": prompt_redundant_items,
        "deduplicated_candidate_pool": len(items) - prompt_redundant_items,
        "canonical_duplicate_candidates": len(canonical_duplicate_candidates),
        "prompt_inconsistent_groups": prompt_inconsistent_groups,
        "prompt_inconsistent_by_field": prompt_inconsistent_by_field,
        "prompt_model_mixed_groups": prompt_model_mixed_groups,
        "field_quality": field_quality,
        "graph": graph,
        "model": model,
        "model_group_min": min(group_sizes) if group_sizes else 0,
        "model_group_median": statistics.median(group_sizes) if group_sizes else 0,
        "model_group_max": max(group_sizes) if group_sizes else 0,
        "models_available": len(available_models),
        "models_missing": sorted(required_models - available_models),
        "query": query,
        "protected_by_answer": protected_by_answer,
        "protected_by_rung": protected_by_rung,
        "protected_group_count": len(protected_groups),
        "protected_group_min": min(protected_sizes) if protected_sizes else 0,
        "protected_group_median": statistics.median(protected_sizes) if protected_sizes else 0,
        "protected_group_p95": nearest_rank_p95(protected_sizes),
        "protected_group_max": max(protected_sizes) if protected_sizes else 0,
        "protected_largest": protected_largest,
        "protected_mixed_answer": protected_mixed_answer,
        "protected_mixed_rung": protected_mixed_rung,
        "rung": rung,
        "story": story,
        "total": len(items),
    }


def field_table(quality: dict[str, tuple[int, int]]) -> str:
    rows = ["| Field | Missing | Present but invalid |", "|---|---:|---:|"]
    rows.extend(f"| `{field}` | {missing:,} | {invalid:,} |" for field, (missing, invalid) in quality.items())
    return "\n".join(rows)


def inconsistency_table(counter: Counter[str]) -> str:
    rows = ["| Attribute | Inconsistent duplicate groups |", "|---|---:|"]
    for label in ("answer", "rung", "query type", "graph ID", "story ID"):
        rows.append(f"| {label} | {counter[label]:,} |")
    return "\n".join(rows)


def protected_group_table(groups: list[dict[str, Any]]) -> str:
    rows = [
        "| Rank | Items | Model IDs | Distinct full prompts | Rungs | Answers |",
        "|---:|---:|---:|---:|---|---|",
    ]
    rows.extend(
        f"| {group['rank']} | {group['size']:,} | {group['models']:,} | "
        f"{group['prompts']:,} | {group['rungs']} | {group['answers']} |"
        for group in groups
    )
    return "\n".join(rows)


def render_report(result: dict[str, Any], archive_size: int, archive_hash: str) -> str:
    median = result["model_group_median"]
    median_text = f"{median:,.1f}" if isinstance(median, float) and not median.is_integer() else f"{median:,.0f}"
    missing_models = result["models_missing"]
    model_verdict = (
        f"Yes. All {len(result['model']):,} model IDs used by the balanced dataset appear in the metadata file."
        if not missing_models
        else f"No. {len(missing_models):,} required model IDs are absent: "
        + ", ".join(f"`{display_key(value)}`" for value in missing_models)
    )
    largest = Counter(dict(sorted_counts(result["model"])[:10]))

    return f"""# CLadder v1 data audit

Audit date: **{date.today().isoformat()}**

This is a read-only metadata audit of the official CLadder v1 balanced data. It creates no smoke, calibration, or locked-test split.

## Provenance and archive inspection

- Source URL: [{SOURCE_URL}]({SOURCE_URL})
- Local archive: `data/raw/cladder-v1.zip` (ignored by Git)
- ZIP size: **{archive_size:,} bytes**
- SHA-256: `{archive_hash}`
- JSON access: members were read directly from the ZIP; nothing was extracted.
- Balanced member: `{BALANCED_MEMBER}`
- Metadata member: `{MODELS_MEMBER}`

## Dataset summary

- Total items: **{result['total']:,}**
- Answer `yes`: **{result['answers'].get('yes', 0):,}**
- Answer `no`: **{result['answers'].get('no', 0):,}**
- Other non-empty answer values: **{sum(value for label, value in result['answers'].items() if label not in {'yes', 'no'}):,}**

### Required-field quality

“Missing” means absent, null, or a blank string. “Present but invalid” means the value has an unexpected type; additionally, answers must be `yes`/`no` and rung must be integer 1, 2, or 3. Boolean values are not accepted as identifiers or numbers. Ground truth accepts JSON scalar values and flat lists (including an empty adjustment set).

{field_table(result['field_quality'])}

## Attribute counts

### Rung

{count_table(result['rung'], 'Rung')}

### Query type

{count_table(result['query'], 'Query type')}

### Graph ID

{count_table(result['graph'], 'Graph ID')}

### Story ID

{count_table(result['story'], 'Story ID')}

## Protected model groups

There are **{len(result['model']):,}** non-empty model-ID groups. Group-size statistics are: minimum **{result['model_group_min']:,}**, median **{median_text}**, and maximum **{result['model_group_max']:,}** items.

Ten largest model-ID groups:

{count_table(largest, 'Model ID')}

These are the model-only groups. The provisional atomic protected groups below also merge across model IDs when full inference prompts duplicate.

## Graph x query type x story cells

- Non-empty cells: **{len(result['cells']):,}**
- Items represented in non-empty cells: **{sum(result['cells'].values()):,}**
- Minimum cell size: **{min(result['cells'].values()) if result['cells'] else 0:,}**
- Maximum cell size: **{max(result['cells'].values()) if result['cells'] else 0:,}**

Exact size distribution:

{distribution_table(result['cell_distribution'])}

## Duplicate analyses

Normalization lowercases text and collapses whitespace while preserving all other semantic text. Newline separators preserve field boundaries. SHA-256 hashes of normalized text define duplicate membership. This audit removes no item.

### A. Question-level duplicates

- Normalized fields: `given_info + question`
- Duplicate items beyond the first occurrence: **{result['question_duplicate_items']:,}**
- Duplicate groups: **{result['question_duplicate_groups']:,}**

### B. Full inference-prompt duplicates

The `background` is resolved from `{MODELS_MEMBER}` by each item's `meta.model_id`, then `background + given_info + question` is normalized and hashed.

- Duplicate items beyond the first occurrence: **{result['prompt_duplicate_items']:,}**
- Duplicate groups: **{result['prompt_duplicate_groups']:,}**
- Deduplicated candidate-pool size (`total items - redundant full-prompt copies`): **{result['deduplicated_candidate_pool']:,}**
- Groups spanning multiple model IDs: **{result['prompt_model_mixed_groups']:,}**
- Groups quarantined for disagreement on answer, rung, query type, graph ID, or story ID: **{result['prompt_inconsistent_groups']:,}**

{inconsistency_table(result['prompt_inconsistent_by_field'])}

A full-prompt duplicate group is quarantined only when its members disagree on at least one of those five audited attributes. Model-ID disagreement does not trigger quarantine; it supplies the cross-model union relation used for protected families.

For each consistent duplicate group, future candidate preparation retains one deterministic canonical candidate: the member with the smallest numeric `question_id`. Redundant copies are excluded from the candidate pool, but every original member's `model_id` remains in the protected-family union. Canonical candidates selected across the consistent duplicate groups: **{result['canonical_duplicate_candidates']:,}**.

## Provisional atomic protected families

Over the full raw dataset, a protected family is a connected component under the union of two relations: equal `meta.model_id`, or equal normalized full-inference-prompt hash. Components are computed before redundant copies are excluded, preserving all cross-model links.

- Protected families: **{result['protected_group_count']:,}**
- Minimum size: **{result['protected_group_min']:,}**
- Median size: **{result['protected_group_median']:,.0f}**
- P95 size (nearest-rank): **{result['protected_group_p95']:,}**
- Maximum size: **{result['protected_group_max']:,}**

Counts by rung are presence-based: a mixed-rung protected family contributes once to every rung it contains.

{count_table(result['protected_by_rung'], 'Rung')}

- Mixed-rung protected families: **{result['protected_mixed_rung']:,}**

Counts by answer label are likewise presence-based.

{count_table(result['protected_by_answer'], 'Answer')}

- Mixed-answer protected families: **{result['protected_mixed_answer']:,}**

Mixed-rung and mixed-answer protected families are expected consequences of the connectivity rules, not data defects.

Ten largest protected families (stable ties are ordered by earliest dataset position; no protected identifier is exposed):

{protected_group_table(result['protected_largest'])}

## Metadata coverage

- Do all required model IDs appear in `{MODELS_MEMBER}`? **{model_verdict}**
- The metadata file contains **{result['models_available']:,}** distinct non-empty model IDs in total.

## Inference-controller boundary

The inference controller must hide these dataset fields: `answer`, `reasoning`, `meta.groundtruth`, `meta.rung`, `meta.query_type`, `meta.graph_id`, `meta.story_id`, and `meta.model_id`.

Only inference inputs intended for the evaluated system should cross that boundary; protected grouping keys and balancing attributes remain evaluation-pipeline metadata.

## Implications for split construction

- No actual split has been created.
- Hard leakage constraints are protected-family disjointness and no duplicate prompt reuse.
- A protected family may contribute selected items to only one of smoke, calibration, or locked test.
- Unused items from that family remain unused rather than being placed in another split.
- For consistent prompt duplicates, only the smallest-numeric-`question_id` canonical candidate is eligible; redundant copies remain excluded while their model-ID links remain enforced.
- Balance diagnostics are rung, answer label, query type, graph ID, and story ID; these are not family-disjointness rules.
- Graph/story disjointness remains a feasibility decision pending inspection of the resulting group structure.
- Any full-prompt duplicate group inconsistent on answer, rung, query type, graph ID, or story ID must be quarantined before split generation. Model-ID disagreement alone is not an inconsistency.

The protected-group counts do not by themselves establish that exact 60/300/600 smoke, calibration, and locked-test sizes are feasible. That requires a future group-aware allocation and balance analysis.

## Limitations

Public CLadder data may have been encountered during LLM pre-training. A future locked evaluation pipeline can control direct evaluation leakage and cross-split leakage, but this audit cannot prove the absence of pre-training contamination.
"""


def main() -> None:
    if not ARCHIVE_PATH.is_file():
        raise FileNotFoundError(
            f"Required cached archive is absent: {ARCHIVE_PATH}. This audit does not download data."
        )
    archive_hash = sha256(ARCHIVE_PATH)
    archive_size = ARCHIVE_PATH.stat().st_size

    with zipfile.ZipFile(ARCHIVE_PATH) as archive:
        names = set(archive.namelist())
        for member in (BALANCED_MEMBER, MODELS_MEMBER):
            if member not in names:
                raise KeyError(f"Required ZIP member is absent: {member}")
        with archive.open(BALANCED_MEMBER) as stream:
            items = json.load(stream)
        with archive.open(MODELS_MEMBER) as stream:
            models = json.load(stream)

    if not isinstance(items, list) or not all(isinstance(item, dict) for item in items):
        raise TypeError("Balanced dataset must be a JSON list of objects")
    if not isinstance(models, list) or not all(isinstance(item, dict) for item in models):
        raise TypeError("Meta-models dataset must be a JSON list of objects")

    report = render_report(audit(items, models), archive_size, archive_hash)
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    report_changed = not REPORT_PATH.exists() or REPORT_PATH.read_text(encoding="utf-8") != report
    if report_changed:
        REPORT_PATH.write_text(report, encoding="utf-8", newline="\n")
    print(f"Archive reused: {ARCHIVE_PATH}")
    print(f"SHA-256: {archive_hash}")
    action = "written" if report_changed else "unchanged"
    print(f"Report {action}: {REPORT_PATH}")


if __name__ == "__main__":
    main()
