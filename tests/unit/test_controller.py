from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path

import pytest

from causalrisk.config import MethodConfig, load_config
from causalrisk.controller import ControllerLimits, PacingPolicy, execute_smoke, logical_call_id
from causalrisk.data import LabelFreeItem
from causalrisk.providers import ProviderResponse
from causalrisk.retry import ClassifiedFailure
from causalrisk.usage import TokenUsage

ROOT = Path(__file__).resolve().parents[2]


@dataclass
class FakeAdapter:
    name: str = "groq"
    credential_environment_variable: str = "FAKE"
    calls: int = 0
    fail_once: bool = False
    malformed: bool = False

    def complete(self, request):
        self.calls += 1
        if self.fail_once and self.calls == 1:
            raise ClassifiedFailure("provider/http_429", "rate limited", retry_after_seconds=2.5)
        return ProviderResponse(
            self.name,
            request.model_id,
            request.model_id,
            "MAYBE" if self.malformed else "YES",
            TokenUsage(100, 10, "fake"),
            1.0,
            http_status=200,
        )


def enabled_a1():
    values = deepcopy(load_config(ROOT / "configs/methods/A1_SINGLE_V1.yaml").values)
    values["execution_enabled"] = True
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


def invoke(adapter, tmp_path, **changes):
    kwargs = {
        "split": "smoke",
        "authorized": True,
        "configs": (enabled_a1(),),
        "items": (LabelFreeItem("item-1", 1, "background", "given", "question"),),
        "adapters": {"groq": adapter},
        "pricing": complete_pricing(),
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
    disabled = load_config(ROOT / "configs/methods/A1_SINGLE_V1.yaml")
    with pytest.raises(ValueError, match="execution_enabled"):
        invoke(adapter, tmp_path, configs=(disabled,))
    for split in ("calibration", "locked_test"):
        with pytest.raises(ValueError, match="only the smoke split"):
            invoke(adapter, tmp_path, split=split)
    assert adapter.calls == 0


def test_resume_skips_a_completed_call(tmp_path):
    adapter = FakeAdapter()
    call_id = logical_call_id("smoke", "A1_SINGLE_V1", "item-1", 0)
    path = tmp_path / "A1_SINGLE_V1" / "calls" / f"{call_id}.json"
    path.parent.mkdir(parents=True)
    path.write_text(f'{{"status":"success","call_id":"{call_id}"}}', encoding="utf-8")
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
    record = next((tmp_path / "A1_SINGLE_V1" / "calls").glob("*.json")).read_text(encoding="utf-8")
    assert '"normalized_list_cost_usd": "0.00012"' in record
    assert '"actual_charge_usd": null' in record


def test_malformed_response_is_terminal(tmp_path):
    adapter = FakeAdapter(malformed=True)
    with pytest.raises(RuntimeError, match="terminal-error threshold"):
        invoke(adapter, tmp_path)
    assert adapter.calls == 1
