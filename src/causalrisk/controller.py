"""Public surface for Amendment 008 final cross-split execution."""

from causalrisk.execution import (
    ExecutionLineage,
    PacingPolicy,
    execute_split,
    logical_call_id,
    predecessor_gate_for_policy,
    r5_canary_artifact_passed,
)

__all__ = [
    "ExecutionLineage",
    "PacingPolicy",
    "execute_split",
    "logical_call_id",
    "predecessor_gate_for_policy",
    "r5_canary_artifact_passed",
]
