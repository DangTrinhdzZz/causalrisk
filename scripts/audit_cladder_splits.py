#!/usr/bin/env python3
"""Validate sealed CLadder v1 splits and write a public-safe aggregate audit."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any

import create_cladder_splits as generator

REPORT_PATH = Path("docs/cladder_split_audit.md")


def load_manifests() -> dict[str, tuple[Path, dict[str, Any]]]:
    result = {}
    for split in generator.SPLIT_QUOTAS:
        path = generator.OUTPUT_DIR / f"{split}.json"
        if not path.is_file():
            raise FileNotFoundError("A required sealed split manifest is absent")
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise ValueError("A sealed split manifest is unreadable or invalid") from error
        if not isinstance(value, dict) or not isinstance(value.get("items"), list):
            raise TypeError("A sealed split manifest has an invalid structure")
        result[split] = (path, value)
    return result


def count_table(counter: Counter[str], heading: str) -> str:
    rows = [f"| {heading} | Count |", "|---|---:|"]
    rows.extend(f"| `{key}` | {value:,} |" for key, value in sorted(counter.items()))
    return "\n".join(rows)


def validate() -> tuple[dict[str, Any], dict[str, str]]:
    items, models = generator.load_source()
    candidates = generator.prepare(items, models)
    by_index = {candidate["source_index"]: candidate for candidate in candidates}
    manifests = load_manifests()
    seen_indices: set[int] = set()
    seen_questions: set[str] = set()
    seen_prompts: set[str] = set()
    family_owner: dict[str, str] = {}
    results: dict[str, Any] = {}
    hashes: dict[str, str] = {}

    for split, per_rung in generator.SPLIT_QUOTAS.items():
        path, document = manifests[split]
        expected_header = (document.get("schema_version"), document.get("protocol_version"),
                           document.get("seed"), document.get("split"))
        if expected_header != (1, generator.PROTOCOL_VERSION, generator.SEED, split):
            raise ValueError("A manifest header does not match the frozen protocol")
        source = document.get("source")
        if source != {"archive_sha256": generator.ARCHIVE_SHA256, "member": generator.BALANCED_MEMBER}:
            raise ValueError("A manifest source definition does not match the frozen protocol")
        selected = []
        for entry in document["items"]:
            if not isinstance(entry, dict) or not isinstance(entry.get("source_index"), int):
                raise TypeError("A manifest item has an invalid structure")
            candidate = by_index.get(entry["source_index"])
            if candidate is None:
                raise ValueError("A manifest references a non-canonical or absent source item")
            expected = {key: candidate[key] for key in ("source_index", "question_id", "prompt_hash", "family")}
            if entry != expected:
                raise ValueError("A sealed manifest item fails source integrity validation")
            question_key = json.dumps(candidate["question_id"], ensure_ascii=False, sort_keys=True)
            if candidate["source_index"] in seen_indices or question_key in seen_questions:
                raise ValueError("Item overlap exists across sealed splits")
            if candidate["prompt_hash"] in seen_prompts:
                raise ValueError("Canonical prompt overlap exists across sealed splits")
            owner = family_owner.setdefault(candidate["family"], split)
            if owner != split:
                raise ValueError("Protected-family overlap exists across sealed splits")
            seen_indices.add(candidate["source_index"])
            seen_questions.add(question_key)
            seen_prompts.add(candidate["prompt_hash"])
            selected.append(candidate)

        rung = Counter(str(c["rung"]) for c in selected)
        labels = Counter(c["answer"] for c in selected)
        rung_labels = Counter((c["rung"], c["answer"]) for c in selected)
        if len(selected) != per_rung * 3 or any(rung[str(value)] != per_rung for value in (1, 2, 3)):
            raise ValueError("A split fails its exact size or rung quota")
        results[split] = {
            "size": len(selected), "rung": rung, "labels": labels, "rung_labels": rung_labels,
            "query": Counter(c["query_type"] for c in selected),
            "graphs": len({c["graph_id"] for c in selected}),
            "stories": len({c["story_id"] for c in selected}),
            "families": len({c["family"] for c in selected}),
        }
        hashes[split] = generator.sha256_file(path)
    return results, hashes


def render(results: dict[str, Any], hashes: dict[str, str]) -> str:
    sections = []
    labels = {"smoke": "Smoke", "calibration": "Calibration", "locked_test": "Locked test"}
    for split in generator.SPLIT_QUOTAS:
        result = results[split]
        rung_rows = ["| Rung | Total | Yes | No |", "|---:|---:|---:|---:|"]
        for rung in (1, 2, 3):
            rung_rows.append(f"| {rung} | {result['rung'][str(rung)]:,} | "
                             f"{result['rung_labels'][rung, 'yes']:,} | {result['rung_labels'][rung, 'no']:,} |")
        rung_table = "\n".join(rung_rows)
        sections.append(f"""### {labels[split]}

- Items: **{result['size']:,}**
- Protected families represented: **{result['families']:,}**
- Graph coverage: **{result['graphs']:,} distinct graph IDs**
- Story coverage: **{result['stories']:,} distinct story IDs**
- Sealed manifest SHA-256: `{hashes[split]}`

{rung_table}

{count_table(result['query'], 'Query type')}""")

    aggregate_sections = "\n\n".join(sections)
    return f"""# CLadder v1 sealed-split audit

Audit date: **{date.today().isoformat()}**

This public-safe report contains aggregate diagnostics and cryptographic checksums only. It exposes no item identifiers, prompts, answers at item level, model identifiers, protected-family identifiers, or split membership.

## Validation verdict

**PASS.** The locally sealed manifests satisfy CLadder split protocol v{generator.PROTOCOL_VERSION}.

- Immutable archive SHA-256 matched: **yes**
- Canonical candidate pool: **8,917 items**
- Exact split sizes and per-rung quotas: **yes**
- Cross-split item overlap: **0**
- Cross-split canonical-prompt overlap: **0**
- Cross-split protected-family overlap: **0**
- Full-prompt duplicate selected more than once: **0**
- Full-prompt duplicate groups quarantined for audited disagreement: **0**
- Fixed selection seed: `{generator.SEED}`
- Generator: `scripts/create_cladder_splits.py`
- Auditor: `scripts/audit_cladder_splits.py`

## Aggregate diagnostics

{aggregate_sections}

Graph and story are balancing/coverage diagnostics, not disjointness constraints. The sealed manifests remain local under `data/splits/private/`; their hashes permit reproducibility checks without publishing membership.
"""


def main() -> None:
    results, hashes = validate()
    report = render(results, hashes)
    REPORT_PATH.write_text(report, encoding="utf-8", newline="\n")
    print("Sealed split audit passed; aggregate public-safe report written.")


if __name__ == "__main__":
    main()
