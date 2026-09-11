"""Validate redacted local provider-smoke reports without reading credentials."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from causalrisk.providers.candidates import PROVIDER_CANDIDATES


@dataclass(frozen=True, slots=True)
class EvidenceAudit:
    accepted: dict[str, Path]
    rejected: tuple[tuple[Path, str], ...]

    @property
    def missing_primary_providers(self) -> frozenset[str]:
        required = {
            candidate.provider
            for candidate in PROVIDER_CANDIDATES.values()
            if candidate.primary and candidate.availability == "available"
        }
        return frozenset(required - self.accepted.keys())


def _load_report(path: Path) -> dict[str, Any]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError("invalid JSON report") from error
    if not isinstance(document, dict):
        raise ValueError("report root is not an object")
    return document


def _validate_success(document: dict[str, Any]) -> str:
    provider = document.get("provider")
    if not isinstance(provider, str) or provider not in PROVIDER_CANDIDATES:
        raise ValueError("unknown provider")
    candidate = PROVIDER_CANDIDATES[provider]
    if not candidate.primary or candidate.availability != "available":
        raise ValueError("provider is not in the execution roster")
    if document.get("schema_version") != 1 or document.get("smoke_kind") != "synthetic_non_benchmark":
        raise ValueError("wrong evidence schema or smoke kind")
    if document.get("status") != "success" or document.get("parsed_answer") != "YES":
        raise ValueError("report is not a successful YES smoke")
    if document.get("http_status") != 200:
        raise ValueError("successful report must have HTTP 200")
    if document.get("requested_model_id") != candidate.model_id:
        raise ValueError("requested model does not match the roster")
    if document.get("reported_model_id") != candidate.model_id:
        raise ValueError("reported model does not match the roster")
    if document.get("contains_raw_output") is not False:
        raise ValueError("report must not contain raw output")
    for field in ("input_tokens", "output_tokens"):
        value = document.get(field)
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise ValueError(f"{field} is invalid")
    if not isinstance(document.get("latency_ms"), int | float) or document["latency_ms"] < 0:
        raise ValueError("latency_ms is invalid")
    if not isinstance(document.get("retry_events"), list):
        raise ValueError("retry_events is invalid")
    return provider


def audit_runtime_evidence(report_directory: str | Path) -> EvidenceAudit:
    directory = Path(report_directory)
    accepted: dict[str, Path] = {}
    rejected: list[tuple[Path, str]] = []
    for path in sorted(directory.glob("*.json")) if directory.is_dir() else ():
        try:
            provider = _validate_success(_load_report(path))
        except ValueError as error:
            rejected.append((path, str(error)))
        else:
            accepted[provider] = path
    return EvidenceAudit(accepted, tuple(rejected))
