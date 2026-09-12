#!/usr/bin/env python3
"""Create a sealed, strictly label-free inference view from an audited split."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import zipfile
from pathlib import Path

import create_cladder_splits as generator

from causalrisk.data import LabelFreeItem
from causalrisk.execution_policy import SOURCE_MANIFEST_SHA256, SPLIT_POLICIES, VIEW_SCHEMA_VERSION

GOLD_FIELDS = frozenset({"answer", "reasoning", "groundtruth", "ground_truth"})


def _opaque_item_id(manifest_hash: str, source_index: int) -> str:
    material = f"causalrisk-inference-v2:{manifest_hash}:{source_index}".encode()
    return hashlib.sha256(material).hexdigest()[:24]


def _canonical_bytes(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode()


def _discard_gold_fields(value: dict) -> dict:
    """Drop gold-bearing keys during JSON decoding; their values are never used."""

    return {key: member for key, member in value.items() if key not in GOLD_FIELDS}


def _load_projection_source() -> tuple[list[dict], list[dict]]:
    if generator.sha256_file(generator.ARCHIVE_PATH) != generator.ARCHIVE_SHA256:
        raise ValueError("cached archive SHA-256 does not match protocol v1.0")
    with zipfile.ZipFile(generator.ARCHIVE_PATH) as archive:
        with archive.open(generator.BALANCED_MEMBER) as stream:
            items = json.load(stream, object_hook=_discard_gold_fields)
        with archive.open(generator.MODELS_MEMBER) as stream:
            models = json.load(stream, object_hook=_discard_gold_fields)
    if not isinstance(items, list) or not all(isinstance(item, dict) for item in items):
        raise TypeError("redacted source projection must be a list of objects")
    if not isinstance(models, list) or not all(isinstance(model, dict) for model in models):
        raise TypeError("model metadata must be a list of objects")
    return items, models


def _sealed_manifest(split: str) -> tuple[dict, str]:
    path = generator.OUTPUT_DIR / f"{split}.json"
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if digest != SOURCE_MANIFEST_SHA256[split]:
        raise ValueError("sealed split manifest checksum differs from Amendment 005")
    manifest = json.loads(raw)
    expected_count = SPLIT_POLICIES[split].item_count
    if (
        not isinstance(manifest, dict)
        or manifest.get("split") != split
        or not isinstance(manifest.get("items"), list)
        or len(manifest["items"]) != expected_count
    ):
        raise ValueError("sealed split manifest shape differs from the frozen protocol")
    indices = [entry.get("source_index") for entry in manifest["items"] if isinstance(entry, dict)]
    if len(indices) != expected_count or any(not isinstance(index, int) for index in indices):
        raise ValueError("sealed split contains an invalid source index")
    if len(indices) != len(set(indices)):
        raise ValueError("sealed split source indices are duplicated")
    return manifest, digest


def _write_immutable(path: Path, payload: bytes) -> None:
    if path.exists():
        if path.is_file() and path.read_bytes() == payload:
            return
        raise FileExistsError(f"local sealed artifact exists with different content: {path.name}")
    temporary = Path(str(path) + ".tmp")
    if temporary.exists():
        raise FileExistsError(f"stale temporary artifact blocks materialization: {temporary.name}")
    temporary.write_bytes(payload)
    os.replace(temporary, path)
    path.chmod(0o600)


def materialize(split: str) -> tuple[int, str, str, str | None]:
    if split not in SPLIT_POLICIES:
        raise ValueError("split must be smoke, calibration, or locked_test")
    manifest, manifest_hash = _sealed_manifest(split)
    items, models = _load_projection_source()
    backgrounds = {generator.typed_key(model["model_id"]): model["background"] for model in models}

    records = []
    selector_candidates = []
    for entry in manifest["items"]:
        source_index = entry["source_index"]
        source = items[source_index]
        model_key = generator.typed_key(generator.nested(source, "meta.model_id"))
        record = {
            "item_id": _opaque_item_id(manifest_hash, source_index),
            "background": backgrounds[model_key],
            "given_info": source["given_info"],
            "question": source["question"],
        }
        LabelFreeItem.from_mapping(record)
        records.append(record)
        rung = generator.nested(source, "meta.rung")
        if rung not in {1, 2, 3} or isinstance(rung, bool):
            raise ValueError("controller-only canary selector encountered an invalid rung")
        selector_candidates.append({"item_id": record["item_id"], "rung": rung})

    document = {
        "schema_version": VIEW_SCHEMA_VERSION,
        "view_kind": "label_free_inference",
        "source_manifest_sha256": manifest_hash,
        "item_count": len(records),
        "items": records,
    }
    output = generator.OUTPUT_DIR / "inference" / f"{split}.v2.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = _canonical_bytes(document)
    view_hash = hashlib.sha256(payload).hexdigest()
    checksum_path = output.with_suffix(".sha256.json")
    checksum_payload = _canonical_bytes(
        {
            "schema_version": VIEW_SCHEMA_VERSION,
            "view_kind": "label_free_inference",
            "source_manifest_sha256": manifest_hash,
            "inference_view_sha256": view_hash,
            "item_count": len(records),
        }
    )
    _write_immutable(output, payload)
    _write_immutable(checksum_path, checksum_payload)

    selector_hash = None
    if split == "smoke":
        selected = [
            min(
                (candidate for candidate in selector_candidates if candidate["rung"] == rung),
                key=lambda candidate: candidate["item_id"],
            )
            for rung in (1, 2, 3)
        ]
        selector_payload = _canonical_bytes(
            {
                "schema_version": 1,
                "selection_kind": "controller_only_one_item_per_rung",
                "source_manifest_sha256": manifest_hash,
                "inference_view_sha256": view_hash,
                "item_count": 3,
                "items": selected,
            }
        )
        selector_path = output.with_suffix(".canary.json")
        _write_immutable(selector_path, selector_payload)
        selector_hash = hashlib.sha256(selector_payload).hexdigest()
    return len(records), manifest_hash, view_hash, selector_hash


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--split", required=True, choices=tuple(SPLIT_POLICIES))
    args = parser.parse_args()
    count, source_hash, view_hash, selector_hash = materialize(args.split)
    result = f"Verified label-free v2 view: items={count}, source_sha256={source_hash}, view_sha256={view_hash}"
    if selector_hash is not None:
        result += f", controller_selector_sha256={selector_hash}"
    print(result + ".")


if __name__ == "__main__":
    main()
