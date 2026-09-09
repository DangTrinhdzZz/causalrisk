"""Frozen method-call graphs and deterministic single-agent aggregation."""

from __future__ import annotations

from dataclasses import dataclass

from causalrisk.config import TOPOLOGIES, MethodConfig


class TopologyError(ValueError):
    """Raised when orchestration would depart from Step 7."""


@dataclass(frozen=True, slots=True)
class CallSpec:
    position: int
    role: str
    upstream_positions: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class ExecutionPlan:
    config_id: str
    calls: tuple[CallSpec, ...]
    alias_of: str | None = None


def build_execution_plan(config: MethodConfig) -> ExecutionPlan:
    config_id = config.config_id
    if config_id == "C1_BOUNDARY_V1":
        return ExecutionPlan(config_id, (), alias_of="A1_SINGLE_V1")
    if config_id in {"A1_SINGLE_V1", "A3_SINGLE_V1", "A5_SINGLE_V1"}:
        calls = tuple(CallSpec(position, "analyst", ()) for position in range(config.values["call_budget"]))
    elif config_id == "C3_COUNCIL_V1":
        calls = (
            CallSpec(0, "analyst", ()),
            CallSpec(1, "critic", (0,)),
            CallSpec(2, "adjudicator", (0, 1)),
        )
    elif config_id == "C5_COUNCIL_V1":
        calls = (
            CallSpec(0, "analyst", ()),
            CallSpec(1, "semantic_query_critic", (0,)),
            CallSpec(2, "graph_identification_critic", (0,)),
            CallSpec(3, "formal_numerical_critic", (0,)),
            CallSpec(4, "adjudicator", (0, 1, 2, 3)),
        )
    else:
        raise TopologyError(f"unsupported config: {config_id}")
    if tuple(call.role for call in calls) != TOPOLOGIES[config_id]:
        raise TopologyError("generated plan violates the frozen role topology")
    return ExecutionPlan(config_id, calls)


def majority_vote(answers: tuple[str, ...]) -> str:
    if not answers or len(answers) % 2 == 0:
        raise TopologyError("majority vote requires a non-empty odd number of answers")
    if any(answer not in {"YES", "NO"} for answer in answers):
        raise TopologyError("INVALID or failed calls cannot be imputed into a vote")
    return "YES" if answers.count("YES") > answers.count("NO") else "NO"
