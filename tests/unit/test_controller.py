import json
from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path

import pytest

from causalrisk.config import MethodConfig, load_config
from causalrisk.controller import (
    ControllerLimits,
    PacingPolicy,
    canary_artifact_passed,
    execute_smoke,
    logical_call_id,
)
from causalrisk.data import LabelFreeItem
from causalrisk.prompts import load_prompt_bundle
from causalrisk.providers import ProviderResponse
from causalrisk.retry import ClassifiedFailure
from causalrisk.usage import TokenUsage

ROOT = Path(__file__).resolve().parents[2]
PROMPT_BUNDLE = load_prompt_bundle(ROOT / "prompts/prompt_causal_yesno_v1.json")


@dataclass
class FakeAdapter:
    name: str = "groq"
    credential_environment_variable: str = "FAKE"
    calls: int = 0
    fail_once: bool = False
    malformed: bool = False
    usage: TokenUsage = field(default_factory=lambda: TokenUsage(100, 10, "fake"))
    actual_charge_usd: float | None = None
    requests: list = field(default_factory=list)

    def complete(self, request):
        self.calls += 1
        self.requests.append(request)
        if self.fail_once and self.calls == 1:
            raise ClassifiedFailure("provider/http_429", "rate limited", retry_after_seconds=2.5)
        return ProviderResponse(
            self.name,
            request.model_id,
            request.model_id,
            "MAYBE" if self.malformed else "YES",
            self.usage,
            1.0,
            http_status=200,
            actual_charge_usd=self.actual_charge_usd,
        )


def enabled_a1():
    values = deepcopy(load_config(ROOT / "configs/methods/A1_SINGLE_V1.yaml").values)
    return MethodConfig(values, Path("synthetic"))


def complete_pricing():
    return {
        "models": {
            "groq:openai/gpt-oss-120b": {
                "status": "priced",
                "input": 1,
                "cached_input": 0.5,
                "output": 2,
                "reasoning": 2,
            }
        }
    }


def nvidia_config():
    values = deepcopy(load_config(ROOT / "configs/methods/A1_SINGLE_V1.yaml").values)
    values["execution_enabled"] = True
    values["provider_pool"] = ["nvidia_nim"]
    values["provider_assignment"] = {"analyst": "nvidia_nim"}
    values["model_assignment"] = {"analyst": "nvidia/nemotron-3.5-lightning-30b-a3b"}
    values["model_family_assignment"] = {"analyst": "nemotron-3.5"}
    values["allow_symbolic_unpriced_provider"] = {
        "provider": "nvidia_nim",
        "source_url": "https://build.nvidia.com/nvidia/nemotron-3.5-lightning-30b-a3b",
        "effective_date": "2026-09-11",
        "reason": "free prototype endpoint has no official token list price",
    }
    return MethodConfig(values, Path("synthetic"))


def nvidia_pricing():
    return {
        "effective_date": "2026-09-11",
        "models": {
            "nvidia_nim:nvidia/nemotron-3.5-lightning-30b-a3b": {
                "status": "official_free_endpoint_unpriced",
                "input": None,
                "output": None,
                "source": "https://build.nvidia.com/nvidia/nemotron-3.5-lightning-30b-a3b",
                "billing_mode": "free_prototype",
                "normalized_list_cost_usd": None,
                "actual_charge_usd": None,
                "cached_input": None,
                "reasoning": None,
            }
        },
    }


def invoke(adapter, tmp_path, **changes):
    kwargs = {
        "split": "smoke",
        "authorized": True,
        "run_id": "test-smoke-run",
        "configs": (enabled_a1(),),
        "items": (LabelFreeItem("item-1", 1, "background", "given", "question"),),
        "adapters": {"groq": adapter},
        "pricing": complete_pricing(),
        "prompt_bundle": PROMPT_BUNDLE,
        "artifact_root": tmp_path,
        "limits": ControllerLimits(1, 4, 0),
        "pacing": PacingPolicy({}),
        "sleep": lambda _seconds: None,
        "jitter": lambda _seconds: 0,
    }
    kwargs.update(changes)
    return execute_smoke(**kwargs)


def test_disabled_execution_and_forbidden_splits_make_zero_calls(tmp_path):
    adapter = FakeAdapter()
    values = deepcopy(load_config(ROOT / "configs/methods/A1_SINGLE_V1.yaml").values)
    values["execution_enabled"] = False
    disabled = MethodConfig(values, Path("synthetic"))
    with pytest.raises(ValueError, match="execution_enabled"):
        invoke(adapter, tmp_path, configs=(disabled,))
    for split in ("calibration", "locked_test"):
        with pytest.raises(ValueError, match="only the smoke split"):
            invoke(adapter, tmp_path, split=split)
    assert adapter.calls == 0


def test_live_authorization_is_required_before_artifacts_or_calls(tmp_path):
    adapter = FakeAdapter()
    with pytest.raises(ValueError, match="authorize-live-smoke"):
        invoke(adapter, tmp_path, authorized=False)
    assert adapter.calls == 0
    assert not (tmp_path / "test-smoke-run").exists()


def test_model_prompt_omits_item_id_and_rung(tmp_path):
    adapter = FakeAdapter()
    invoke(
        adapter,
        tmp_path,
        items=(LabelFreeItem("opaque-item-id", 3, "background-safe", "given-safe", "question-safe"),),
    )
    prompt = adapter.requests[0].prompt
    assert "opaque-item-id" not in prompt
    assert "rung" not in prompt.casefold()
    assert "background-safe" in prompt


def test_resume_skips_a_completed_call(tmp_path):
    adapter = FakeAdapter()
    call_id = logical_call_id("smoke", "A1_SINGLE_V1", "item-1", 0)
    from causalrisk.controlled_execution import _atomic_create_json, _prepare_run

    config = enabled_a1()
    items = (LabelFreeItem("item-1", 1, "background", "given", "question"),)
    limits = ControllerLimits(1, 4, 0)
    run_dir, _manifest = _prepare_run(
        tmp_path,
        "test-smoke-run",
        split="smoke",
        configs=(config,),
        items=items,
        limits=limits,
        pricing=complete_pricing(),
    )
    path = run_dir / "calls" / "A1_SINGLE_V1" / f"{call_id}.json"
    path.parent.mkdir(parents=True)
    _atomic_create_json(
        path,
        {
            "status": "success",
            "call_id": call_id,
            "config_id": "A1_SINGLE_V1",
            "item_id": "item-1",
            "provider": "groq",
            "topology_position": 0,
            "raw_output": "YES",
            "input_tokens": 100,
            "output_tokens": 10,
            "normalized_list_cost_usd": "0.00012",
            "actual_charge_usd": None,
        },
    )
    result = invoke(adapter, tmp_path)
    assert result["logical_calls"] == 0
    assert adapter.calls == 0


def test_retry_after_and_cost_metadata_are_recorded(tmp_path):
    adapter = FakeAdapter(fail_once=True)
    sleeps = []
    result = invoke(adapter, tmp_path, sleep=sleeps.append)
    assert adapter.calls == 2
    assert sleeps == [2.5]
    assert result["transport_attempts"] == 2
    record = next((tmp_path / "test-smoke-run" / "calls" / "A1_SINGLE_V1").glob("*.json")).read_text(
        encoding="utf-8"
    )
    assert '"normalized_list_cost_usd": "0.00012"' in record
    assert '"actual_charge_usd": null' in record


def test_malformed_response_is_terminal(tmp_path):
    adapter = FakeAdapter(malformed=True)
    with pytest.raises(RuntimeError, match="terminal-error threshold"):
        invoke(adapter, tmp_path)
    assert adapter.calls == 1
    record_path = next((tmp_path / "test-smoke-run" / "calls" / "A1_SINGLE_V1").glob("*.json"))
    record = json.loads(record_path.read_text(encoding="utf-8"))
    assert record["attempt_index"] == 0
    assert record["retry_count"] == 0


def test_controller_rejects_relaxed_ceilings_before_artifacts_or_calls(tmp_path):
    adapter = FakeAdapter()
    with pytest.raises(ValueError, match="zero-error ceilings"):
        invoke(adapter, tmp_path, limits=ControllerLimits(2, 8, 1))
    assert adapter.calls == 0
    assert not (tmp_path / "test-smoke-run").exists()


def test_nvidia_null_cost_propagates_and_reports_coverage(tmp_path):
    adapter = FakeAdapter(name="nvidia_nim")
    result = invoke(
        adapter,
        tmp_path,
        configs=(nvidia_config(),),
        adapters={"nvidia_nim": adapter},
        pricing=nvidia_pricing(),
    )
    assert result["cost_summary"]["A1_SINGLE_V1"] == {
        "total_normalized_cost_usd": None,
        "priced_cost_subtotal_usd": "0",
        "priced_call_coverage": 0.0,
        "priced_token_coverage": 0.0,
        "actual_charge_usd": None,
        "actual_charge_reporting_coverage": 0.0,
    }
    record = next((tmp_path / "test-smoke-run" / "calls" / "A1_SINGLE_V1").glob("*.json")).read_text(
        encoding="utf-8"
    )
    assert '"normalized_list_cost_usd": null' in record
    assert '"billing_mode": "free_prototype"' in record


def test_nvidia_reported_charge_is_treated_as_billing_drift(tmp_path):
    adapter = FakeAdapter(name="nvidia_nim", actual_charge_usd=0.01)
    with pytest.raises(RuntimeError, match="run-blocking provider failure"):
        invoke(
            adapter,
            tmp_path,
            configs=(nvidia_config(),),
            adapters={"nvidia_nim": adapter},
            pricing=nvidia_pricing(),
        )
    assert adapter.calls == 1


def test_unknown_usage_stays_null_and_actual_charge_is_separate(tmp_path):
    adapter = FakeAdapter(usage=TokenUsage(None, None, "unavailable"), actual_charge_usd=0.25)
    result = invoke(adapter, tmp_path)
    summary = result["cost_summary"]["A1_SINGLE_V1"]
    assert summary["total_normalized_cost_usd"] is None
    assert summary["priced_cost_subtotal_usd"] == "0"
    assert summary["actual_charge_usd"] == "0.25"
    record = next((tmp_path / "test-smoke-run" / "calls" / "A1_SINGLE_V1").glob("*.json")).read_text(
        encoding="utf-8"
    )
    assert '"input_tokens": null' in record
    assert '"normalized_list_cost_usd": null' in record
    assert '"actual_charge_usd": 0.25' in record


def test_ambiguous_in_flight_attempt_blocks_resume_without_call(tmp_path):
    from causalrisk.controlled_execution import _atomic_create_json, _prepare_run

    adapter = FakeAdapter()
    config = enabled_a1()
    items = (LabelFreeItem("item-1", 1, "background", "given", "question"),)
    run_dir, _manifest = _prepare_run(
        tmp_path,
        "test-smoke-run",
        split="smoke",
        configs=(config,),
        items=items,
        limits=ControllerLimits(1, 4, 0),
        pricing=complete_pricing(),
    )
    call_id = logical_call_id("smoke", "A1_SINGLE_V1", "item-1", 0)
    _atomic_create_json(
        run_dir / "attempts" / "A1_SINGLE_V1" / f"{call_id}-0.json",
        {"call_id": call_id, "attempt_index": 0, "status": "started"},
    )
    with pytest.raises(RuntimeError, match="in-flight"):
        invoke(adapter, tmp_path)
    assert adapter.calls == 0


def test_canary_pass_requires_frozen_complete_zero_error_summary(tmp_path):
    from causalrisk.pricing import load_pricing

    configs = tuple(reversed([load_config(path) for path in sorted((ROOT / "configs/methods").glob("*.yaml"))]))
    adapters = {
        provider: FakeAdapter(name=provider)
        for provider in ("groq", "nvidia_nim", "gemini", "cloudflare_workers_ai", "openai")
    }
    execute_smoke(
        split="smoke",
        authorized=True,
        run_id="cladder-smoke-canary-3",
        configs=configs,
        items=tuple(LabelFreeItem(f"item-{rung}", rung, "background", "given", "question") for rung in (1, 2, 3)),
        adapters=adapters,
        pricing=load_pricing(ROOT / "configs/pricing_2026-09-11.json"),
        prompt_bundle=PROMPT_BUNDLE,
        artifact_root=tmp_path,
        limits=ControllerLimits(51, 204, 0),
        pacing=PacingPolicy({}),
        sleep=lambda _seconds: None,
        jitter=lambda _seconds: 0,
    )
    assert canary_artifact_passed(tmp_path)
    manifest = json.loads((tmp_path / "cladder-smoke-canary-3" / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["config_ids"] == [
        "A1_SINGLE_V1",
        "A3_SINGLE_V1",
        "A5_SINGLE_V1",
        "C1_BOUNDARY_V1",
        "C3_COUNCIL_V1",
        "C5_COUNCIL_V1",
    ]
