"""Frozen post-stop execution policies for Amendment 009 revision R6."""

from __future__ import annotations

from dataclasses import dataclass

EXECUTION_REVISION = "cross_split_execution_r6"
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
    "cloudflare_workers_ai": 4,
    "groq": 11,
    "openai": 2,
}
MINIMUM_INTERVAL_SECONDS = {
    "cloudflare_workers_ai": 1.0,
    "groq": 10.0,
    "openai": 1.0,
}

R1_RUN_ID = "cladder-smoke-canary-3"
R1_MANIFEST_SHA256 = "1b41a9e78f999f873084ab828cecdc385e4ce54028c4f5f04e53ea6045040637"
R1_ARTIFACT_TREE_SHA256 = "ef651c3cbda820bb39d67188f5532321206544b2fe68594542730b115959b69a"
R2_RUN_ID = "cladder-smoke-canary-3-r2"
R2_MANIFEST_SHA256 = "c8b78f1ef5f853e0443cb88a6d9d596446f1490d288cdd3c5a085b035744b4ce"
R2_ARTIFACT_TREE_SHA256 = "53aa427f2941b106018bf818971985d665a7c59ee94a185277b2ddf01943422d"
R3_RUN_ID = "cladder-smoke-canary-3-r3"
R3_MANIFEST_SHA256 = "72db02ebc08a657911928ef60812da57ef3c493b2f3e0143de02ec3557df8f3e"
R3_ARTIFACT_TREE_SHA256 = "0dccb0852643e0522b1dcd3ecc1113a5170273d97a7e963923e89c80eb08cd04"
R4_RUN_ID = "cladder-smoke-canary-3-r4"
R4_MANIFEST_SHA256 = "6880469577b5b5df3b69fc2088f5f82f6d9232f81d577c31418f5232bd153a5c"
R4_ARTIFACT_TREE_SHA256 = "672f430dc96d409e9ac86000a3727a073a343c6f8297d1760fbaed7dea2c7a45"
R5_RUN_ID = "cladder-smoke-canary-3-r5"
R5_MANIFEST_SHA256 = "60475269e6b507c891b16ef02a44ba2672ba0683d7b0d64975ef9be8b4f246f6"
R5_ARTIFACT_TREE_SHA256 = "2ef7b14410349942a63cb4400bb26e347b57a961400788d83ddd1e1d5c5468d0"
R5_SUMMARY_SHA256 = "81b1db961d00368f755a554047ef1e596186941a4f4733af1f6b9bcfcdde37a1"


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
    run_id="cladder-smoke-canary-3-r6",
    authorization_flag="--authorize-live-smoke",
    live_authorized=True,
    predecessor_run_id=R5_RUN_ID,
    predecessor_requirement="frozen_failed_r5_remediation_input",
    recommended_max_new_items=None,
    canary=True,
)

SPLIT_POLICIES = {
    "smoke": SplitExecutionPolicy(
        split="smoke",
        item_count=60,
        run_id="cladder-smoke-60-r6",
        authorization_flag="--authorize-live-smoke",
        live_authorized=True,
        predecessor_run_id=SMOKE_CANARY_POLICY.run_id,
        predecessor_requirement="frozen_complete_canary_51_of_51_zero_error",
        recommended_max_new_items=3,
    ),
    "calibration": SplitExecutionPolicy(
        split="calibration",
        item_count=300,
        run_id="cladder-calibration-300-r6",
        authorization_flag="--authorize-live-calibration",
        live_authorized=False,
        predecessor_run_id="cladder-smoke-60-r6",
        predecessor_requirement="frozen_complete_smoke_operational_review",
        recommended_max_new_items=3,
    ),
    "locked_test": SplitExecutionPolicy(
        split="locked_test",
        item_count=600,
        run_id="cladder-locked-test-600-r6",
        authorization_flag="--authorize-live-locked-test",
        live_authorized=False,
        predecessor_run_id="cladder-calibration-300-r6",
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
