"""Load and validate immutable method configuration records."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


class ConfigError(ValueError):
    """Raised when a method configuration violates the frozen protocol."""


TOPOLOGIES: dict[str, tuple[str, ...]] = {
    "A1_SINGLE_V1": ("analyst",),
    "A3_SINGLE_V1": ("analyst", "analyst", "analyst"),
    "A5_SINGLE_V1": ("analyst", "analyst", "analyst", "analyst", "analyst"),
    "C1_BOUNDARY_V1": ("analyst",),
    "C3_COUNCIL_V1": ("analyst", "critic", "adjudicator"),
    "C5_COUNCIL_V1": (
        "analyst",
        "semantic_query_critic",
        "graph_identification_critic",
        "formal_numerical_critic",
        "adjudicator",
    ),
}
METHOD_FAMILIES = {
    "A1_SINGLE_V1": "single_agent",
    "A3_SINGLE_V1": "single_agent",
    "A5_SINGLE_V1": "single_agent",
    "C1_BOUNDARY_V1": "boundary",
    "C3_COUNCIL_V1": "heterogeneous_council",
    "C5_COUNCIL_V1": "heterogeneous_council",
}
HASH_PATTERN = re.compile(r"^[0-9a-f]{64}$")
PLACEHOLDER_MARKERS = ("PLACEHOLDER", "PENDING", "TO_BE_FROZEN")

REQUIRED_FIELDS = {
    "schema_version",
    "config_id",
    "method_family",
    "call_budget",
    "provider_pool",
    "provider_assignment",
    "model_assignment",
    "model_family_assignment",
    "prompt_version",
    "prompt_sha256",
    "roles",
    "temperature",
    "max_output_tokens",
    "retry_policy_ref",
    "retry_policy_sha256",
    "parser_version",
    "logging_version",
    "allow_retrieval",
    "allow_web",
    "expose_gold_label",
    "expose_metadata",
    "runtime_verified",
    "execution_enabled",
}
OPTIONAL_FIELDS = {"alias_of", "seed", "notes"}


@dataclass(frozen=True, slots=True)
class MethodConfig:
    """Validated configuration plus its source path."""

    values: dict[str, Any]
    source: Path

    @property
    def config_id(self) -> str:
        return str(self.values["config_id"])


def _require_mapping(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise ConfigError(f"{field} must be a string-keyed mapping")
    return value


def _contains_placeholder(value: Any) -> bool:
    if isinstance(value, str):
        upper = value.upper()
        return any(marker in upper for marker in PLACEHOLDER_MARKERS)
    if isinstance(value, dict):
        return any(_contains_placeholder(member) for member in value.values())
    if isinstance(value, list):
        return any(_contains_placeholder(member) for member in value)
    return False


def validate_config(document: dict[str, Any], *, for_execution: bool = False) -> None:
    unknown = set(document) - REQUIRED_FIELDS - OPTIONAL_FIELDS
    missing = REQUIRED_FIELDS - set(document)
    if missing or unknown:
        raise ConfigError(f"config fields mismatch; missing={sorted(missing)}, unknown={sorted(unknown)}")
    if document["schema_version"] != 1:
        raise ConfigError("schema_version must be 1")

    config_id = document["config_id"]
    if config_id not in TOPOLOGIES:
        raise ConfigError("config_id is not one of the six frozen identifiers")
    expected_roles = TOPOLOGIES[config_id]
    if tuple(document["roles"]) != expected_roles:
        raise ConfigError(f"roles do not match the frozen topology for {config_id}")
    if document["method_family"] != METHOD_FAMILIES[config_id]:
        raise ConfigError("method_family does not match config_id")
    if document["call_budget"] != len(expected_roles):
        raise ConfigError("call_budget does not match the frozen topology")

    if config_id == "C1_BOUNDARY_V1":
        if document.get("alias_of") != "A1_SINGLE_V1":
            raise ConfigError("C1_BOUNDARY_V1 must alias A1_SINGLE_V1")
    elif "alias_of" in document:
        raise ConfigError("alias_of is allowed only for C1_BOUNDARY_V1")

    unique_roles = set(expected_roles)
    for field in ("provider_assignment", "model_assignment", "model_family_assignment"):
        mapping = _require_mapping(document[field], field)
        if set(mapping) != unique_roles or not all(isinstance(value, str) and value for value in mapping.values()):
            raise ConfigError(f"{field} must define every unique topology role exactly once")

    provider_pool = document["provider_pool"]
    if (
        not isinstance(provider_pool, list)
        or not provider_pool
        or not all(isinstance(value, str) for value in provider_pool)
    ):
        raise ConfigError("provider_pool must be a non-empty list of names")
    if not set(document["provider_assignment"].values()).issubset(set(provider_pool)):
        raise ConfigError("provider_assignment contains a provider outside provider_pool")

    if not isinstance(document["temperature"], (int, float)) or isinstance(document["temperature"], bool):
        raise ConfigError("temperature must be numeric")
    token_caps = document["max_output_tokens"]
    if isinstance(token_caps, int) and not isinstance(token_caps, bool):
        if token_caps <= 0:
            raise ConfigError("max_output_tokens must be positive")
    else:
        token_mapping = _require_mapping(token_caps, "max_output_tokens")
        if set(token_mapping) != unique_roles or not all(
            isinstance(value, int) and not isinstance(value, bool) and value > 0 for value in token_mapping.values()
        ):
            raise ConfigError("role-specific max_output_tokens must be positive integers for every role")

    for field in ("prompt_sha256", "retry_policy_sha256"):
        if not isinstance(document[field], str) or not HASH_PATTERN.fullmatch(document[field]):
            raise ConfigError(f"{field} must be a lowercase SHA-256 digest")
    if document["prompt_version"] != "prompt_causal_yesno_v1":
        raise ConfigError("prompt_version is not the frozen Day 2 bundle")
    if document["parser_version"] != "yesno_parser_v1":
        raise ConfigError("parser_version is not supported")
    if document["logging_version"] != "step9_logging_v1":
        raise ConfigError("logging_version is not supported")

    for field in ("allow_retrieval", "allow_web", "expose_gold_label", "expose_metadata"):
        if document[field] is not False:
            raise ConfigError(f"{field} must be false")
    for field in ("runtime_verified", "execution_enabled"):
        if not isinstance(document[field], bool):
            raise ConfigError(f"{field} must be boolean")

    if for_execution:
        if document["runtime_verified"] is not True or document["execution_enabled"] is not True:
            raise ConfigError("execution is blocked until runtime verification and explicit enablement")
        if _contains_placeholder(document):
            raise ConfigError("execution config contains a provisional placeholder")
        if config_id.startswith("C3_") or config_id.startswith("C5_"):
            families = document["model_family_assignment"].values()
            if len(set(families)) != len(document["model_family_assignment"]):
                raise ConfigError("heterogeneous council roles must use distinct model families")


def load_config(path: str | Path, *, for_execution: bool = False) -> MethodConfig:
    source = Path(path)
    try:
        document = yaml.safe_load(source.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        raise ConfigError(f"cannot read configuration: {source}") from error
    if not isinstance(document, dict):
        raise ConfigError("configuration root must be a mapping")
    validate_config(document, for_execution=for_execution)
    return MethodConfig(document, source)
