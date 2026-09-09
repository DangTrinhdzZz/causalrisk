"""Strict Step 9 event-record schema and validation."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any

from causalrisk.config import TOPOLOGIES


class SchemaError(ValueError):
    """Raised when an inference/event record violates Step 9."""


ALLOWED_STATUSES = frozenset(
    {"success", "failure", "method_failure", "run_blocked", "data_validation_failure", "incomplete"}
)


@dataclass(frozen=True, slots=True)
class EventRecord:
    run_id: str
    item_id: str
    split_name: str
    config_id: str
    model_id: str
    provider: str
    prompt_version: str
    attempt_index: int
    role_name: str
    raw_output: str | None
    parsed_answer: str
    final_answer: str | None
    latency_ms: float | None
    input_tokens: int | None
    output_tokens: int | None
    total_tokens: int | None
    estimated_cost_usd: float | None
    status: str
    failure_type: str | None
    timestamp_utc: str
    code_version: str
    call_id: str
    retry_eligible: bool
    backoff_seconds: float
    response_id: str | None
    http_status: int | None
    normalization_actions: tuple[str, ...]
    topology_position: int
    resolution_action: str
    included_in_final_vote: bool
    included_in_accuracy_denominator: bool
    included_in_cost_analysis: bool
    notes: str | None = None

    def __post_init__(self) -> None:
        for field in (
            "run_id",
            "item_id",
            "split_name",
            "model_id",
            "provider",
            "prompt_version",
            "call_id",
            "code_version",
        ):
            if not getattr(self, field).strip():
                raise SchemaError(f"{field} must be non-empty")
        if self.config_id not in TOPOLOGIES:
            raise SchemaError("unknown frozen config_id")
        if self.parsed_answer not in {"YES", "NO", "INVALID"}:
            raise SchemaError("parsed_answer must be YES, NO, or INVALID")
        if self.final_answer not in {"YES", "NO", None}:
            raise SchemaError("final_answer must be YES, NO, or null")
        if not 0 <= self.attempt_index <= 3:
            raise SchemaError("attempt_index must be in the range 0..3")
        if not 0 <= self.topology_position < len(TOPOLOGIES[self.config_id]):
            raise SchemaError("topology_position is outside the configured call structure")
        if TOPOLOGIES[self.config_id][self.topology_position] != self.role_name:
            raise SchemaError("role_name does not match topology_position")
        if self.status not in ALLOWED_STATUSES:
            raise SchemaError("status is outside the controlled vocabulary")
        if self.latency_ms is not None and self.latency_ms < 0:
            raise SchemaError("latency_ms must be non-negative or null")
        for field in ("input_tokens", "output_tokens", "total_tokens"):
            value = getattr(self, field)
            if value is not None and (not isinstance(value, int) or isinstance(value, bool) or value < 0):
                raise SchemaError(f"{field} must be non-negative or null")
        if self.input_tokens is not None and self.output_tokens is not None:
            expected = self.input_tokens + self.output_tokens
            if self.total_tokens != expected:
                raise SchemaError("total_tokens must equal input_tokens + output_tokens")
        if self.estimated_cost_usd is not None and self.estimated_cost_usd < 0:
            raise SchemaError("estimated_cost_usd must be non-negative or null")
        if self.backoff_seconds < 0:
            raise SchemaError("backoff_seconds must be non-negative")
        try:
            timestamp = datetime.fromisoformat(self.timestamp_utc.replace("Z", "+00:00"))
        except ValueError as error:
            raise SchemaError("timestamp_utc must be an ISO-8601 timestamp") from error
        if timestamp.tzinfo is None or timestamp.utcoffset() is None or timestamp.utcoffset().total_seconds() != 0:
            raise SchemaError("timestamp_utc must include a UTC offset")
        if self.raw_output is None and self.status == "success":
            raise SchemaError("successful call must preserve raw_output")
        if self.failure_type is None and self.parsed_answer == "INVALID":
            raise SchemaError("INVALID parsed_answer requires failure_type")

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["normalization_actions"] = list(self.normalization_actions)
        return value
