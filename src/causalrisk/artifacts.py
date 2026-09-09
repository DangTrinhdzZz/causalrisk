"""Local run-artifact creation, checksums, and logical freeze enforcement."""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from causalrisk.schemas import EventRecord


class ArtifactError(RuntimeError):
    """Raised when an artifact operation would violate immutability or safety."""


SAFE_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
SECRET_KEYS = frozenset(
    {"api_key", "authorization", "access_token", "secret", "password", "credential", "bearer"}
)


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def _utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _assert_no_secret_keys(value: Any, path: str = "root") -> None:
    if isinstance(value, dict):
        for key, member in value.items():
            if str(key).casefold() in SECRET_KEYS:
                raise ArtifactError(f"secret-bearing key is prohibited in artifacts: {path}.{key}")
            _assert_no_secret_keys(member, f"{path}.{key}")
    elif isinstance(value, list | tuple):
        for index, member in enumerate(value):
            _assert_no_secret_keys(member, f"{path}[{index}]")


def _json_bytes(value: Any) -> bytes:
    _assert_no_secret_keys(value)
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode()


def _contains_gold_metric_key(value: Any) -> bool:
    if isinstance(value, dict):
        for key, member in value.items():
            normalized = str(key).casefold()
            if any(marker in normalized for marker in ("accuracy", "correct", "gold", "label", "score")):
                return True
            if _contains_gold_metric_key(member):
                return True
    elif isinstance(value, list | tuple):
        return any(_contains_gold_metric_key(member) for member in value)
    return False


def _exclusive_write(path: Path, value: bytes) -> None:
    try:
        with path.open("xb") as stream:
            stream.write(value)
    except FileExistsError as error:
        raise ArtifactError(f"artifact already exists and cannot be overwritten: {path.name}") from error


@dataclass(slots=True)
class RunArtifactWriter:
    run_dir: Path

    @classmethod
    def create(
        cls,
        artifact_root: str | Path,
        run_id: str,
        *,
        resolved_config: dict[str, Any],
        manifest_metadata: dict[str, Any],
    ) -> RunArtifactWriter:
        if not SAFE_IDENTIFIER.fullmatch(run_id):
            raise ArtifactError("run_id contains unsafe characters")
        root = Path(artifact_root)
        run_dir = root / run_id
        try:
            run_dir.mkdir(parents=True, exist_ok=False)
        except FileExistsError as error:
            raise ArtifactError("run directory already exists; runs cannot be overwritten") from error
        for child in ("raw", "parsed", "logs"):
            (run_dir / child).mkdir()
        _exclusive_write(run_dir / "config.json", _json_bytes(resolved_config))
        manifest = {
            **manifest_metadata,
            "run_id": run_id,
            "created_at_utc": _utc_now(),
            "run_status": "in_progress",
            "freeze_state": "open",
            "frozen_at_utc": None,
            "artifact_sha256": {},
        }
        _exclusive_write(run_dir / "manifest.json", _json_bytes(manifest))
        return cls(run_dir)

    def _manifest(self) -> dict[str, Any]:
        try:
            value = json.loads((self.run_dir / "manifest.json").read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise ArtifactError("run manifest is missing or invalid") from error
        if not isinstance(value, dict):
            raise ArtifactError("run manifest root must be an object")
        return value

    def _assert_open(self) -> None:
        if self._manifest().get("freeze_state") != "open":
            raise ArtifactError("frozen run artifacts cannot be modified")

    def write_attempt(self, record: EventRecord) -> None:
        self._assert_open()
        if record.run_id != self._manifest().get("run_id"):
            raise ArtifactError("event run_id does not match the run manifest")
        if not SAFE_IDENTIFIER.fullmatch(record.call_id):
            raise ArtifactError("call_id contains unsafe characters")
        raw_bytes = b"" if record.raw_output is None else record.raw_output.encode("utf-8")
        raw_path = self.run_dir / "raw" / f"{record.call_id}.txt"
        _exclusive_write(raw_path, raw_bytes)
        parsed = {
            "call_id": record.call_id,
            "item_id": record.item_id,
            "parsed_answer": record.parsed_answer,
            "final_answer": record.final_answer,
            "failure_type": record.failure_type,
            "normalization_actions": list(record.normalization_actions),
            "raw_sha256": sha256_bytes(raw_bytes),
        }
        _exclusive_write(self.run_dir / "parsed" / f"{record.call_id}.json", _json_bytes(parsed))
        _exclusive_write(self.run_dir / "logs" / f"{record.call_id}.json", _json_bytes(record.to_dict()))

    def write_metrics_preview(self, metrics: dict[str, Any]) -> None:
        self._assert_open()
        if _contains_gold_metric_key(metrics):
            raise ArtifactError("metrics preview must remain gold-free")
        _exclusive_write(self.run_dir / "metrics_preview.json", _json_bytes(metrics))

    def freeze(self, *, final_status: str = "complete") -> dict[str, str]:
        self._assert_open()
        if final_status not in {"complete", "incomplete", "run_blocked"}:
            raise ArtifactError("invalid terminal run status")
        manifest = self._manifest()
        hashes: dict[str, str] = {}
        for path in sorted(self.run_dir.rglob("*")):
            if path.is_file() and path.name != "manifest.json":
                hashes[path.relative_to(self.run_dir).as_posix()] = sha256_file(path)
        manifest["artifact_sha256"] = hashes
        manifest["run_status"] = final_status
        manifest["freeze_state"] = "frozen"
        manifest["frozen_at_utc"] = _utc_now()
        temporary = self.run_dir / "manifest.json.tmp"
        _exclusive_write(temporary, _json_bytes(manifest))
        os.replace(temporary, self.run_dir / "manifest.json")
        return hashes
