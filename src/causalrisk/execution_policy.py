"""Frozen cross-split execution policies for Amendment 005 revision R2."""

from __future__ import annotations

from dataclasses import dataclass

EXECUTION_REVISION = "cross_split_execution_r2"
PROVIDER_LIMIT_SNAPSHOT_VERSION = "provider_limits_2026-09-12"
VIEW_SCHEMA_VERSION = 2
CALLS_PER_ITEM = 17
ATTEMPTS_PER_CALL = 4
METHOD_ORDER = (
    "A1_SINGLE_V1",
    "A3_SINGLE_V1",
    "A5_SINGLE_V1",
    "C1_BOUNDARY_V1",
    "C3_COUNCIL_V1",
    "C5_COUNCIL_V1",
)
METHOD_CALLS_PER_ITEM = {
    "A1_SINGLE_V1": 1,
    "A3_SINGLE_V1": 3,
    "A5_SINGLE_V1": 5,
    "C1_BOUNDARY_V1": 0,
    "C3_COUNCIL_V1": 3,
    "C5_COUNCIL_V1": 5,
}
PROVIDER_CALLS_PER_ITEM = {
    "cloudflare_workers_ai": 1,
    "gemini": 1,
    "groq": 11,
    "nvidia_nim": 2,
    "openai": 2,
}
MINIMUM_INTERVAL_SECONDS = {
    "cloudflare_workers_ai": 1.0,
    "gemini": 1.0,
    "groq": 10.0,
    "nvidia_nim": 1.0,
    "openai": 1.0,
}

R1_RUN_ID = "cladder-smoke-canary-3"
R1_MANIFEST_SHA256 = "1b41a9e78f999f873084ab828cecdc385e4ce54028c4f5f04e53ea6045040637"
R1_ARTIFACT_TREE_SHA256 = "ef651c3cbda820bb39d67188f5532321206544b2fe68594542730b115959b69a"


@dataclass(frozen=True, slots=True)
class SplitExecutionPolicy:
    """Exact immutable identity, ceilings, authorization, and batching for one run."""

    split: str
    item_count: int
    run_id: str
    authorization_flag: str
    live_authorized: bool
    predecessor_run_id: str
    predecessor_requirement: str
    recommended_max_new_items: int | None
    canary: bool = False

    @property
    def expected_logical_calls(self) -> int:
        return self.item_count * CALLS_PER_ITEM

    @property
    def max_transport_attempts(self) -> int:
        return self.expected_logical_calls * ATTEMPTS_PER_CALL

    @property
    def expected_method_calls(self) -> dict[str, int]:
        return {method: count * self.item_count for method, count in METHOD_CALLS_PER_ITEM.items()}

    @property
    def expected_provider_calls(self) -> dict[str, int]:
        return {provider: count * self.item_count for provider, count in PROVIDER_CALLS_PER_ITEM.items()}


SMOKE_CANARY_POLICY = SplitExecutionPolicy(
    split="smoke",
    item_count=3,
    run_id="cladder-smoke-canary-3-r2",
    authorization_flag="--authorize-live-smoke",
    live_authorized=True,
    predecessor_run_id=R1_RUN_ID,
    predecessor_requirement="frozen_failed_remediation_input",
    recommended_max_new_items=None,
    canary=True,
)

SPLIT_POLICIES = {
    "smoke": SplitExecutionPolicy(
        split="smoke",
        item_count=60,
        run_id="cladder-smoke-60-r2",
        authorization_flag="--authorize-live-smoke",
        live_authorized=True,
        predecessor_run_id=SMOKE_CANARY_POLICY.run_id,
        predecessor_requirement="frozen_complete_canary_51_of_51_zero_error",
        recommended_max_new_items=3,
    ),
    "calibration": SplitExecutionPolicy(
        split="calibration",
        item_count=300,
        run_id="cladder-calibration-300-r2",
        authorization_flag="--authorize-live-calibration",
        live_authorized=False,
        predecessor_run_id="cladder-smoke-60-r2",
        predecessor_requirement="frozen_complete_smoke_operational_review",
        recommended_max_new_items=3,
    ),
    "locked_test": SplitExecutionPolicy(
        split="locked_test",
        item_count=600,
        run_id="cladder-locked-test-600-r2",
        authorization_flag="--authorize-live-locked-test",
        live_authorized=False,
        predecessor_run_id="cladder-calibration-300-r2",
        predecessor_requirement="frozen_complete_calibration_scored_final_configuration_freeze",
        recommended_max_new_items=3,
    ),
}

SOURCE_MANIFEST_SHA256 = {
    "smoke": "e53e151258e0d71e0f0360e5c8bdd7e1a2e8defa76a34f2774d0f2999776afe9",
    "calibration": "45d486f67bf631476aa856abe5a1472201795c200631718e0e6715f9926ae0ca",
    "locked_test": "e83bd0d6424a653ba42b7fefbfc6cbf59193d46d8bbb7bc58f0076770ca7f7bb",
}


def get_execution_policy(split: str, *, canary: bool = False) -> SplitExecutionPolicy:
    if split not in SPLIT_POLICIES:
        raise ValueError("split must be smoke, calibration, or locked_test")
    if canary:
        if split != "smoke":
            raise ValueError("the predeclared three-item canary exists only for smoke")
        return SMOKE_CANARY_POLICY
    return SPLIT_POLICIES[split]
