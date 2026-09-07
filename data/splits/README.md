# Sealed CLadder splits

Everything generated below `data/splits/private/` is sensitive and ignored by Git. Do not copy manifests, split membership, item identifiers, prompts, answers, protected-family identifiers, or evaluation outputs into tracked files.

From the repository root, create the protocol-v1 splits with:

```console
python scripts/create_cladder_splits.py
```

The command refuses to replace an existing sealed directory. To deliberately reproduce and replace it from the immutable source, pass `--overwrite`. Then independently validate the sealed artifacts and regenerate the public-safe aggregate report with:

```console
python scripts/audit_cladder_splits.py
```

Both commands use only the Python 3.11 standard library, read the JSON members directly from the cached ZIP, and make no network or model calls. The audit prints no record-level data; `docs/cladder_split_audit.md` contains aggregates and manifest checksums only.
