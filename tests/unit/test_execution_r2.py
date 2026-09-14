import json
from dataclasses import dataclass, field, replace
from pathlib import Path

import pytest

from causalrisk.config import load_config
from causalrisk.controller import (
    ExecutionLineage,
    PacingPolicy,
    execute_split,
    logical_call_id,
    predecessor_gate_for_policy,
    r4_canary_artifact_passed,
)
from causalrisk.data import LabelFreeItem
from causalrisk.execution import _atomic_create_json
from causalrisk.execution_policy import (
    METHOD_ORDER,
    MINIMUM_INTERVAL_SECONDS,
    SMOKE_CANARY_POLICY,
    SOURCE_MANIFEST_SHA256,
    SPLIT_POLICIES,
    SplitExecutionPolicy,
)
from causalrisk.pricing import load_pricing
from causalrisk.prompts import file_sha256, load_prompt_bundle
from causalrisk.providers import ProviderResponse
from causalrisk.retry import ClassifiedFailure
from causalrisk.usage import TokenUsage

ROOT = Path(__file__).resolve().parents[2]
PROMPT = load_prompt_bundle(ROOT / "prompts/prompt_causal_yesno_v1.json")
PRICING = load_pricing(ROOT / "configs/pricing_2026-09-11.json")
CONFIGS = tuple(load_config(ROOT / "configs/methods" / f"{config_id}.yaml") for config_id in METHOD_ORDER)


@dataclass
class R4FakeAdapter:
    name: str
    events: list = field(default_factory=list)
    truncate: bool = False
    rate_limit_once: bool = False
    calls: int = 0
    credential_environment_variable: str = "FAKE"

    def complete(self, request):
        self.calls += 1
        self.events.append((self.name, request.model_id, request.prompt))
        if self.rate_limit_once and self.calls == 1:
            raise ClassifiedFailure(
                "provider/http_429",
                "rate limited",
                http_status=429,
                retry_after_seconds=2.5,
                latency_ms=1.5,
                safe_response_headers={"retry-after": "2.5"},
            )
        if self.truncate:
            raise ClassifiedFailure(
                "configuration/output_cap_truncation",
                "truncated",
                http_status=200,
                finish_reason="length",
                latency_ms=4.5,
                response_id="truncated-response",
                input_tokens=10,
                output_tokens=request.max_output_tokens,
                reasoning_tokens=0,
                cached_input_tokens=0,
                total_tokens=10 + request.max_output_tokens,
                token_accounting_method="fake",
            )
        return ProviderResponse(
            self.name,
            request.model_id,
            request.model_id,
            "YES",
            TokenUsage(10, 4, "fake", reasoning_tokens=0, cached_input_tokens=0),
            2.5,
            response_id=f"{self.name}-response",
            http_status=200,
            finish_reason="stop",
            safe_response_headers={"x-ratelimit-remaining-requests": "99"},
        )


def policy(item_count=2, run_id="test-r4-run"):
    return SplitExecutionPolicy(
        split="smoke",
        item_count=item_count,
        run_id=run_id,
        authorization_flag="--authorize-live-smoke",
        live_authorized=True,
        predecessor_run_id="test-predecessor",
        predecessor_requirement="test-only",
        recommended_max_new_items=1,
    )


def lineage(**changes):
    base = ExecutionLineage(
        code_commit="a" * 40,
        source_manifest_sha256=SOURCE_MANIFEST_SHA256["smoke"],
        inference_view_sha256="c" * 64,
        inference_view_schema_version=2,
        selection_sha256=None,
        config_sha256={config.config_id: file_sha256(config.source) for config in CONFIGS},
        prompt_sha256=PROMPT.sha256,
        pricing_version=PRICING["version"],
        provider_limit_snapshot_version="provider_limits_2026-09-12",
        predecessor_gate={"run_id": "test-predecessor", "requirement": "test-only", "verified": True},
    )
    return replace(base, **changes)


def items(count=2):
    return tuple(LabelFreeItem(f"item-{index}", f"background-{index}", "given", "question") for index in range(count))


def adapters(*, truncate_provider=None):
    events = []
    result = {
        provider: R4FakeAdapter(provider, events, truncate=provider == truncate_provider)
        for provider in ("groq", "nvidia_nim", "gemini", "cloudflare_workers_ai", "openai")
    }
    return result, events


def invoke(tmp_path, *, selected_policy=None, selected_items=None, selected_adapters=None, **changes):
    selected_policy = selected_policy or policy()
    selected_items = selected_items or items(selected_policy.item_count)
    selected_adapters = selected_adapters or adapters()[0]
    kwargs = {
        "policy": selected_policy,
        "authorization_flag": selected_policy.authorization_flag,
        "configs": CONFIGS,
        "items": selected_items,
        "adapters": selected_adapters,
        "pricing": PRICING,
        "prompt_bundle": PROMPT,
        "artifact_root": tmp_path,
        "pacing": PacingPolicy(MINIMUM_INTERVAL_SECONDS),
        "lineage": lineage(),
        "sleep": lambda _seconds: None,
        "jitter": lambda _seconds: 0,
    }
    kwargs.update(changes)
    return execute_split(**kwargs)


def test_split_specific_authorization_and_disabled_phases_make_zero_calls(tmp_path):
    fake_adapters, _events = adapters()
    with pytest.raises(ValueError, match="exact split authorization"):
        invoke(tmp_path, selected_adapters=fake_adapters, authorization_flag="--authorize-live-calibration")
    for split in ("calibration", "locked_test"):
        with pytest.raises(ValueError, match="BLOCKED_NOT_AUTHORIZED"):
            invoke(
                tmp_path,
                selected_policy=SPLIT_POLICIES[split],
                selected_items=items(SPLIT_POLICIES[split].item_count),
                selected_adapters=fake_adapters,
                authorization_flag=SPLIT_POLICIES[split].authorization_flag,
            )
    assert sum(adapter.calls for adapter in fake_adapters.values()) == 0
    assert not (tmp_path / "test-r4-run").exists()


def test_item_major_planned_pause_and_deterministic_resume_without_recalling(tmp_path):
    fake_adapters, events = adapters()
    selected_policy = policy()
    first = invoke(tmp_path, selected_policy=selected_policy, selected_adapters=fake_adapters, max_new_items=1)
    assert first["run_status"] == "paused"
    assert first["completed_logical_calls"] == 17
    manifest_path = tmp_path / selected_policy.run_id / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert (manifest["run_status"], manifest["freeze_state"], manifest["item_count"]) == ("paused", "open", 2)
    assert len(events) == 17
    assert all("background-0" in event[2] for event in events)

    second = invoke(tmp_path, selected_policy=selected_policy, selected_adapters=fake_adapters, max_new_items=1)
    assert second["run_status"] == "complete"
    assert second["completed_logical_calls"] == 34
    assert len(events) == 34
    assert all("background-1" in event[2] for event in events[17:])
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert (manifest["run_status"], manifest["freeze_state"]) == ("complete", "frozen")
    assert len(list((tmp_path / selected_policy.run_id / "sessions").glob("*.json"))) == 2


@pytest.mark.parametrize(
    "drift",
    [
        {"code_commit": "e" * 40},
        {"inference_view_sha256": "f" * 64},
        {"pricing_version": "different-pricing"},
        {"config_sha256": {config_id: "0" * 64 for config_id in METHOD_ORDER}},
    ],
)
def test_lineage_drift_blocks_paused_resume(tmp_path, drift):
    fake_adapters, _events = adapters()
    invoke(tmp_path, selected_adapters=fake_adapters, max_new_items=1)
    calls_before = sum(adapter.calls for adapter in fake_adapters.values())
    with pytest.raises((RuntimeError, ValueError), match="lineage"):
        invoke(tmp_path, selected_adapters=fake_adapters, max_new_items=1, lineage=lineage(**drift))
    assert sum(adapter.calls for adapter in fake_adapters.values()) == calls_before


def test_ambiguous_attempt_blocks_paused_resume(tmp_path):
    selected_policy = policy()
    fake_adapters, _events = adapters()
    invoke(tmp_path, selected_policy=selected_policy, selected_adapters=fake_adapters, max_new_items=1)
    next_item = items()[1]
    call_id = logical_call_id("smoke", "A1_SINGLE_V1", next_item.item_id, 0)
    _atomic_create_json(
        tmp_path / selected_policy.run_id / "attempts/A1_SINGLE_V1" / f"{call_id}-0.json",
        {"call_id": call_id, "attempt_index": 0, "status": "started"},
    )
    with pytest.raises(RuntimeError, match="in-flight"):
        invoke(tmp_path, selected_policy=selected_policy, selected_adapters=fake_adapters, max_new_items=1)


def test_completed_call_artifact_drift_blocks_resume_without_recalling(tmp_path):
    fake_adapters, _events = adapters()
    selected_policy = policy()
    invoke(tmp_path, selected_policy=selected_policy, selected_adapters=fake_adapters, max_new_items=1)
    calls_before = sum(adapter.calls for adapter in fake_adapters.values())
    call_path = next((tmp_path / selected_policy.run_id / "calls/A1_SINGLE_V1").glob("*.json"))
    record = json.loads(call_path.read_text(encoding="utf-8"))
    record["provider"] = "openai"
    call_path.write_text(json.dumps(record), encoding="utf-8")
    with pytest.raises(RuntimeError, match="call artifact"):
        invoke(
            tmp_path,
            selected_policy=selected_policy,
            selected_adapters=fake_adapters,
            max_new_items=1,
        )
    assert sum(adapter.calls for adapter in fake_adapters.values()) == calls_before


def test_output_cap_is_terminal_and_failure_keeps_observability(tmp_path):
    fake_adapters, _events = adapters(truncate_provider="groq")
    with pytest.raises(RuntimeError, match="terminal-error threshold"):
        invoke(tmp_path, selected_adapters=fake_adapters)
    run_dir = tmp_path / "test-r4-run"
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    call = json.loads(next((run_dir / "calls/A1_SINGLE_V1").glob("*.json")).read_text(encoding="utf-8"))
    attempt = json.loads(next((run_dir / "attempts/A1_SINGLE_V1").glob("*.json")).read_text(encoding="utf-8"))
    assert (manifest["run_status"], manifest["freeze_state"]) == ("failed", "frozen")
    assert call["finish_reason"] == "length"
    assert call["input_tokens"] == 10
    assert call["retry_events"][0]["finish_reason"] == "length"
    assert attempt["finish_reason"] == "length"
    assert attempt["latency_ms"] == 4.5
    with pytest.raises(RuntimeError, match="terminal"):
        invoke(tmp_path, selected_adapters=adapters()[0])


def test_success_artifacts_have_observability_and_nvidia_null_policy(tmp_path):
    invoke(tmp_path)
    run_dir = tmp_path / "test-r4-run"
    attempts = [json.loads(path.read_text(encoding="utf-8")) for path in run_dir.glob("attempts/*/*.json")]
    calls = [json.loads(path.read_text(encoding="utf-8")) for path in run_dir.glob("calls/*/*.json")]
    required = {
        "finish_reason",
        "latency_ms",
        "input_tokens",
        "output_tokens",
        "reasoning_tokens",
        "cached_input_tokens",
        "total_tokens",
        "http_status",
        "response_id",
        "safe_response_headers",
    }
    assert all(required.issubset(record) for record in attempts)
    assert all(required.issubset(record) for record in calls)
    nvidia = [record for record in calls if record["provider"] == "nvidia_nim"]
    assert nvidia
    assert all(
        record["normalized_list_cost_usd"] is None
        and record["actual_charge_usd"] is None
        and record["billing_mode"] == "free_prototype"
        for record in nvidia
    )
    assert not list(run_dir.rglob("*.tmp"))


def test_retry_after_and_backoff_history_are_preserved(tmp_path):
    fake_adapters, _events = adapters()
    fake_adapters["groq"].rate_limit_once = True
    sleeps = []
    invoke(tmp_path, selected_adapters=fake_adapters, sleep=sleeps.append)
    run_dir = tmp_path / "test-r4-run"
    groq_calls = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in run_dir.glob("calls/*/*.json")
        if json.loads(path.read_text(encoding="utf-8"))["provider"] == "groq"
    ]
    retried = next(record for record in groq_calls if record["retry_count"] == 1)
    event = retried["retry_events"][0]
    assert event["failure_code"] == "provider/http_429"
    assert event["retry_after_seconds"] == 2.5
    assert event["backoff_seconds"] == 2.5
    assert event["safe_response_headers"] == {"retry-after": "2.5"}
    assert 2.5 in sleeps


def test_only_exact_complete_r4_canary_opens_smoke_gate(tmp_path):
    fake_adapters, _events = adapters()
    canary_items = items(3)
    canary_lineage = lineage(
        selection_sha256="9" * 64,
        predecessor_gate={
            "run_id": SMOKE_CANARY_POLICY.predecessor_run_id,
            "requirement": SMOKE_CANARY_POLICY.predecessor_requirement,
            "verified": True,
        },
    )
    invoke(
        tmp_path,
        selected_policy=SMOKE_CANARY_POLICY,
        selected_items=canary_items,
        selected_adapters=fake_adapters,
        lineage=canary_lineage,
    )
    assert r4_canary_artifact_passed(tmp_path)
    assert not (tmp_path / "cladder-smoke-canary-3-r3").exists()


@pytest.mark.parametrize(
    "legacy_run_id",
    ["cladder-smoke-canary-3", "cladder-smoke-canary-3-r2", "cladder-smoke-canary-3-r3"],
)
def test_prior_or_nonmatching_r3_artifact_cannot_open_the_r4_canary_gate(tmp_path, legacy_run_id):
    legacy = tmp_path / legacy_run_id
    legacy.mkdir()
    (legacy / "manifest.json").write_text(
        json.dumps({"run_id": legacy_run_id, "run_status": "failed", "freeze_state": "frozen"}),
        encoding="utf-8",
    )
    (legacy / "summary.json").write_text(
        json.dumps({"expected_logical_calls": 51, "completed_logical_calls": 10, "terminal_errors": 1}),
        encoding="utf-8",
    )
    gate = predecessor_gate_for_policy(tmp_path, SMOKE_CANARY_POLICY)
    assert gate["run_id"] == "cladder-smoke-canary-3-r3"
    assert not gate["verified"]


def test_wrong_predecessor_lineage_blocks_r4_canary_before_any_call(tmp_path):
    fake_adapters, _events = adapters()
    bad_lineage = lineage(
        selection_sha256="9" * 64,
        predecessor_gate={
            "run_id": "cladder-smoke-canary-3",
            "requirement": "frozen_failed_remediation_input",
            "verified": True,
        },
    )
    with pytest.raises(ValueError, match="predecessor gate"):
        invoke(
            tmp_path,
            selected_policy=SMOKE_CANARY_POLICY,
            selected_items=items(3),
            selected_adapters=fake_adapters,
            lineage=bad_lineage,
        )
    assert sum(adapter.calls for adapter in fake_adapters.values()) == 0
    assert not (tmp_path / SMOKE_CANARY_POLICY.run_id).exists()


def test_artifact_writer_rejects_secret_or_authorization_keys(tmp_path):
    with pytest.raises(ValueError, match="secret-bearing"):
        _atomic_create_json(tmp_path / "bad.json", {"authorization": "must-not-write"})
    assert not (tmp_path / "bad.json").exists()
