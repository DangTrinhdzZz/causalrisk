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


def test_execution_is_blocked_while_runtime_values_are_provisional():
    with pytest.raises(ConfigError, match="execution is blocked"):
        load_config(CONFIG_DIR / "A1_SINGLE_V1.yaml", for_execution=True)


def test_config_rejects_gold_or_web_exposure():
    document = deepcopy(load_config(CONFIG_DIR / "A1_SINGLE_V1.yaml").values)
    document["expose_gold_label"] = True
    with pytest.raises(ConfigError, match="expose_gold_label"):
        validate_config(document)


def test_c1_is_an_alias_not_an_independent_condition():
    config = load_config(CONFIG_DIR / "C1_BOUNDARY_V1.yaml")
    assert config.values["alias_of"] == "A1_SINGLE_V1"
    assert config.values["call_budget"] == 1
