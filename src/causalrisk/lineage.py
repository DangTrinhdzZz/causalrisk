"""Immutable artifact checksums and remediation-lineage checks."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from causalrisk.execution_policy import (
    R1_ARTIFACT_TREE_SHA256,
    R1_MANIFEST_SHA256,
    R1_RUN_ID,
    R2_ARTIFACT_TREE_SHA256,
    R2_MANIFEST_SHA256,
    R2_RUN_ID,
)


def file_sha256_bytes(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def artifact_tree_sha256(run_dir: str | Path) -> str:
    root = Path(run_dir)
    digest = hashlib.sha256()
    for path in sorted(member for member in root.rglob("*") if member.is_file()):
        relative = path.relative_to(root).as_posix()
        digest.update(relative.encode())
        digest.update(b"\0")
        digest.update(hashlib.sha256(path.read_bytes()).hexdigest().encode())
        digest.update(b"\n")
    return digest.hexdigest()


def verify_r1_remediation_input(artifact_root: str | Path) -> bool:
    run_dir = Path(artifact_root) / R1_RUN_ID
    manifest_path = run_dir / "manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return bool(
        manifest.get("run_id") == R1_RUN_ID
        and manifest.get("freeze_state") == "frozen"
        and manifest.get("run_status") == "failed"
        and file_sha256_bytes(manifest_path) == R1_MANIFEST_SHA256
        and artifact_tree_sha256(run_dir) == R1_ARTIFACT_TREE_SHA256
    )


def verify_r2_remediation_input(artifact_root: str | Path) -> bool:
    run_dir = Path(artifact_root) / R2_RUN_ID
    manifest_path = run_dir / "manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return bool(
        manifest.get("run_id") == R2_RUN_ID
        and manifest.get("execution_revision") == "cross_split_execution_r2"
        and manifest.get("freeze_state") == "frozen"
        and manifest.get("run_status") == "failed"
        and file_sha256_bytes(manifest_path) == R2_MANIFEST_SHA256
        and artifact_tree_sha256(run_dir) == R2_ARTIFACT_TREE_SHA256
    )
