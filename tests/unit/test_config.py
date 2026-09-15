from copy import deepcopy
from pathlib import Path

import pytest

from causalrisk.config import ConfigError, load_config, validate_config

ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = ROOT / "configs" / "methods"


def test_all_six_configs_are_structurally_valid():
    configs = [load_config(path) for path in sorted(CONFIG_DIR.glob("*.yaml"))]
    assert {config.config_id for config in configs} == {
        "A1_SINGLE_V1",
        "A3_SINGLE_V1",
        "A5_SINGLE_V1",
        "C1_BOUNDARY_V1",
        "C3_COUNCIL_V1",
        "C5_COUNCIL_V1",
    }


def test_all_six_configs_are_enabled_for_controlled_execution():
    configs = [load_config(path, for_execution=True) for path in sorted(CONFIG_DIR.glob("*.yaml"))]
    assert len(configs) == 6
    assert all(config.values["runtime_verified"] is True for config in configs)
    assert all(config.values["execution_enabled"] is True for config in configs)


def test_config_rejects_gold_or_web_exposure():
    document = deepcopy(load_config(CONFIG_DIR / "A1_SINGLE_V1.yaml").values)
    document["expose_gold_label"] = True
    with pytest.raises(ConfigError, match="expose_gold_label"):
        validate_config(document)


def test_c1_is_an_alias_not_an_independent_condition():
    config = load_config(CONFIG_DIR / "C1_BOUNDARY_V1.yaml")
    assert config.values["alias_of"] == "A1_SINGLE_V1"
    assert config.values["call_budget"] == 1


def test_openai_is_the_provisional_shared_council_adjudicator():
    c3 = load_config(CONFIG_DIR / "C3_COUNCIL_V1.yaml").values
    c5 = load_config(CONFIG_DIR / "C5_COUNCIL_V1.yaml").values
    assert c3["provider_assignment"]["adjudicator"] == "openai"
    assert c5["provider_assignment"]["adjudicator"] == "openai"
    assert "openai" in c3["provider_pool"]
    assert c3["runtime_verified"] is True
    assert c5["execution_enabled"] is True


def test_cloudflare_critics_define_the_final_role_heterogeneous_councils():
    c3 = load_config(CONFIG_DIR / "C3_COUNCIL_V1.yaml").values
    c5 = load_config(CONFIG_DIR / "C5_COUNCIL_V1.yaml").values
    assert c3["provider_assignment"]["critic"] == "cloudflare_workers_ai"
    assert c5["provider_assignment"]["graph_identification_critic"] == "cloudflare_workers_ai"
    assert c5["provider_assignment"]["formal_numerical_critic"] == "cloudflare_workers_ai"
    assert set(c3["provider_assignment"].values()).issubset(set(c5["provider_assignment"].values()))
    assert "mistral" not in c3["provider_pool"]
    assert "mistral" not in c5["provider_pool"]
    assert "nvidia_nim" not in c3["provider_pool"]
    assert "nvidia_nim" not in c5["provider_pool"]
    assert c3["model_assignment"]["critic"] == "@cf/qwen/qwen3-30b-a3b-fp8"


def test_c5_cloudflare_critics_are_independent_role_and_position_calls():
    from causalrisk.topology import build_execution_plan

    config = load_config(CONFIG_DIR / "C5_COUNCIL_V1.yaml")
    calls = {
        call.role: call
        for call in build_execution_plan(config).calls
        if config.values["provider_assignment"][call.role] == "cloudflare_workers_ai"
    }
    assert set(calls) == {"semantic_query_critic", "graph_identification_critic", "formal_numerical_critic"}
    assert calls["semantic_query_critic"].position == 1
    assert calls["graph_identification_critic"].position == 2
    assert calls["formal_numerical_critic"].position == 3
