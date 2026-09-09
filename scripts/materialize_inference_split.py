#!/usr/bin/env python3
"""Create a sealed, strictly label-free inference view from an audited split."""

from __future__ import annotations

import argparse
import hashlib
import json

import audit_cladder_splits as auditor
import create_cladder_splits as generator

from causalrisk.data import LabelFreeItem


def _opaque_item_id(manifest_hash: str, source_index: int) -> str:
    material = f"causalrisk-inference-v1:{manifest_hash}:{source_index}".encode()
    return hashlib.sha256(material).hexdigest()[:24]


def materialize(split: str) -> int:
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
            "background": backgrounds[model_key],
            "given_info": source["given_info"],
            "question": source["question"],
        }
        LabelFreeItem.from_mapping(record)
        records.append(record)

    output = generator.OUTPUT_DIR / "inference" / f"{split}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        with output.open("x", encoding="utf-8", newline="\n") as stream:
            json.dump(records, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
    except FileExistsError as error:
        raise FileExistsError("label-free inference view already exists; it was not overwritten") from error
    output.chmod(0o600)
    return len(records)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--split", required=True, choices=tuple(generator.SPLIT_QUOTAS))
    parser.add_argument(
        "--authorize-locked-test-materialization",
        action="store_true",
        help="required explicit gate for creating the locked-test inference view",
    )
    args = parser.parse_args()
    if args.split == "locked_test" and not args.authorize_locked_test_materialization:
        raise SystemExit("Blocked: locked-test materialization requires explicit authorization.")
    count = materialize(args.split)
    print(f"Created sealed label-free inference view with {count} items; record details suppressed.")


if __name__ == "__main__":
    main()
