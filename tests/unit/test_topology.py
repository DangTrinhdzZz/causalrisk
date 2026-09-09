from pathlib import Path

import pytest

from causalrisk.config import load_config
from causalrisk.topology import TopologyError, build_execution_plan, majority_vote

ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = ROOT / "configs" / "methods"


def plan(config_id):
    return build_execution_plan(load_config(CONFIG_DIR / f"{config_id}.yaml"))


def test_a3_and_a5_calls_are_independent():
    for config_id, count in (("A3_SINGLE_V1", 3), ("A5_SINGLE_V1", 5)):
        calls = plan(config_id).calls
        assert len(calls) == count
        assert all(call.role == "analyst" and call.upstream_positions == () for call in calls)


def test_c1_schedules_no_duplicate_call():
    result = plan("C1_BOUNDARY_V1")
    assert result.calls == ()
    assert result.alias_of == "A1_SINGLE_V1"


def test_c5_critics_are_independent_and_adjudicator_receives_all_cards():
    calls = plan("C5_COUNCIL_V1").calls
    assert [call.upstream_positions for call in calls[1:4]] == [(0,), (0,), (0,)]
    assert calls[4].upstream_positions == (0, 1, 2, 3)


def test_majority_vote_has_no_imputation_or_tie_path():
    assert majority_vote(("YES", "NO", "YES")) == "YES"
    with pytest.raises(TopologyError):
        majority_vote(("YES", "INVALID", "NO"))
    with pytest.raises(TopologyError):
        majority_vote(("YES", "NO"))
