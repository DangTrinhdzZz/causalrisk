"""Public surface for the controlled smoke-only execution controller."""

from causalrisk.controlled_execution import (
    ControllerLimits,
    PacingPolicy,
    canary_artifact_passed,
    execute_smoke,
    logical_call_id,
)

__all__ = [
    "ControllerLimits",
    "PacingPolicy",
    "canary_artifact_passed",
    "execute_smoke",
    "logical_call_id",
]
