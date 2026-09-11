#!/usr/bin/env python3
"""Create a sealed, strictly label-free inference view from an audited split."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

import audit_cladder_splits as auditor
import create_cladder_splits as generator

from causalrisk.data import LabelFreeItem


def _opaque_item_id(manifest_hash: str, source_index: int) -> str:
    material = f"causalrisk-inference-v1:{manifest_hash}:{source_index}".encode()
    return hashlib.sha256(material).hexdigest()[:24]


def _canonical_bytes(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode()


def materialize(split: str) -> tuple[int, str, str]:
    if split != "smoke":
        raise ValueError("Day 2B materialization permits only the smoke split")
    _results, manifest_hashes = auditor.validate()
    manifests = auditor.load_manifests()
    manifest = manifests[split][1]
    items, models = generator.load_source()
    backgrounds = {generator.typed_key(model["model_id"]): model["background"] for model in models}

    records = []
    for entry in manifest["items"]:
        source_index = entry["source_index"]
        source = items[source_index]
        model_key = generator.typed_key(generator.nested(source, "meta.model_id"))
        record = {
            "item_id": _opaque_item_id(manifest_hashes[split], source_index),
            "rung": source["meta"]["rung"],
            "background": backgrounds[model_key],
            "given_info": source["given_info"],
            "question": source["question"],
        }
        LabelFreeItem.from_mapping(record)
        records.append(record)

    document = {
        "schema_version": 1,
        "view_kind": "label_free_inference",
        "split": split,
        "source_manifest_sha256": manifest_hashes[split],
        "items": records,
    }
    output = generator.OUTPUT_DIR / "inference" / f"{split}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = _canonical_bytes(document)
    view_hash = hashlib.sha256(payload).hexdigest()
    checksum_path = output.with_suffix(".sha256.json")
    if output.exists() or checksum_path.exists():
        if output.is_file() and output.read_bytes() == payload:
            return len(records), manifest_hashes[split], view_hash
        raise FileExistsError("label-free inference view exists with different content")
    temporary = Path(str(output) + ".tmp")
    checksum_temporary = Path(str(checksum_path) + ".tmp")
    temporary.write_bytes(payload)
    checksum_temporary.write_bytes(
        _canonical_bytes(
            {
                "schema_version": 1,
                "source_manifest_sha256": manifest_hashes[split],
                "inference_view_sha256": view_hash,
            }
        )
    )
    os.replace(temporary, output)
    os.replace(checksum_temporary, checksum_path)
    output.chmod(0o600)
    return len(records), manifest_hashes[split], view_hash


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--split", required=True, choices=("smoke",))
    args = parser.parse_args()
    count, source_hash, view_hash = materialize(args.split)
    print(f"Verified label-free smoke view: items={count}, source_sha256={source_hash}, view_sha256={view_hash}.")


if __name__ == "__main__":
    main()
