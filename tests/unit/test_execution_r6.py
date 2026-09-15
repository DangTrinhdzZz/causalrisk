import json
import runpy
import shutil
from pathlib import Path

import pytest

from causalrisk import lineage
from causalrisk.config import load_config
from causalrisk.credentials import SecretValue
from causalrisk.execution import predecessor_gate_for_policy
from causalrisk.execution_policy import (
    METHOD_ORDER,
    R5_ARTIFACT_TREE_SHA256,
    R5_MANIFEST_SHA256,
    R5_RUN_ID,
    R5_SUMMARY_SHA256,
    SMOKE_CANARY_POLICY,
    SPLIT_POLICIES,
)
from causalrisk.prompts import file_sha256
from causalrisk.providers import ProviderRequest
from causalrisk.providers.candidates import PROVIDER_CANDIDATES
from causalrisk.topology import build_execution_plan

ROOT = Path(__file__).resolve().parents[2]


def test_exact_local_r5_lineage_and_label_free_aggregate():
    run_dir = ROOT / "artifacts/runs" / R5_RUN_ID
    before = lineage.artifact_tree_sha256(run_dir)
    aggregate = json.loads((ROOT / "docs/r5_operational_canary_forensic_aggregate.json").read_text(encoding="utf-8"))
    integrity = aggregate["artifact_integrity"]
    assert lineage.verify_r5_remediation_input(run_dir.parent)
    assert integrity["manifest_sha256"] == R5_MANIFEST_SHA256 == lineage.file_sha256_bytes(run_dir / "manifest.json")
    assert integrity["summary_sha256"] == R5_SUMMARY_SHA256 == lineage.file_sha256_bytes(run_dir / "summary.json")
    assert integrity["artifact_tree_sha256"] == R5_ARTIFACT_TREE_SHA256 == before
    assert aggregate["benchmark_result"] is aggregate["correctness_analyzed"] is False
    assert aggregate["raw_prompt_included"] is aggregate["raw_output_included"] is False
    assert aggregate["item_membership_included"] is False
    assert [a["attempt_index"] for a in aggregate["terminal_failure"]["attempt_chain"]] == [0, 1, 2, 3]
    assert all(a["http_status"] == 503 and a["provider_error_type"] == "UNAVAILABLE"
               for a in aggregate["terminal_failure"]["attempt_chain"])
    gate = predecessor_gate_for_policy(run_dir.parent, SMOKE_CANARY_POLICY)
    assert gate["verified"] and gate["summary_sha256"] == R5_SUMMARY_SHA256
    assert lineage.artifact_tree_sha256(run_dir) == before


@pytest.mark.parametrize("target", ["manifest.json", "summary.json", "configs/C5_COUNCIL_V1.json", "extra.json"])
def test_r5_byte_drift_fails_closed_without_mutating_source(tmp_path, target):
    original = ROOT / "artifacts/runs" / R5_RUN_ID
    copy = tmp_path / R5_RUN_ID
    shutil.copytree(original, copy)
    assert lineage.verify_r5_remediation_input(tmp_path)
    path = copy / target
    path.write_bytes((path.read_bytes() if path.exists() else b"{}") + b"\n")
    assert not lineage.verify_r5_remediation_input(tmp_path)
    assert not predecessor_gate_for_policy(tmp_path, SMOKE_CANARY_POLICY)["verified"]
    assert lineage.artifact_tree_sha256(original) == R5_ARTIFACT_TREE_SHA256


@pytest.mark.parametrize("constant", ["R5_MANIFEST_SHA256", "R5_SUMMARY_SHA256", "R5_ARTIFACT_TREE_SHA256"])
def test_each_exact_r5_hash_is_required(monkeypatch, constant):
    monkeypatch.setattr(lineage, constant, "0" * 64)
    assert not lineage.verify_r5_remediation_input(ROOT / "artifacts/runs")


def test_parser_prompt_retry_schema_and_topology_are_unchanged():
    expected = {
        "prompts/prompt_causal_yesno_v1.json": "1a9db03951bfd6b969a67f198310309dc24c81b6a7cc8c3f397dec1ef6b856fb",
        "docs/retry_policy.md": "78c859c8910c2f3c1179859bf8c64cab2b6a70483a53ee75dfdf2c619e893797",
        "src/causalrisk/parsing.py": "0cf1323f4c943417a9692c02fbfd6a802eba041e2fd65f0f1ab91d1a1ee6f404",
        "src/causalrisk/retry.py": "15161a70932c2326034da6d2c93a1eb25ef9ffdf733595157e14caad0d719b45",
        "src/causalrisk/schemas.py": "4158c6bc02737c6ae1fc597c1c629c4400a9b5c9c64d75dc79a84553707b45bf",
        "src/causalrisk/topology.py": "f713041cb516ace1caec65b8c39834cb0bcfd00e32360d65f71d013ce311ea69",
    }
    assert {path: file_sha256(ROOT / path) for path in expected} == expected
    for config_id in METHOD_ORDER:
        current = load_config(ROOT / "configs/methods" / f"{config_id}.yaml").values
        previous = json.loads((ROOT / "artifacts/runs" / R5_RUN_ID / "configs" / f"{config_id}.json")
                              .read_text(encoding="utf-8"))
        allowed = {"notes", "provider_pool"}
        if config_id == "C5_COUNCIL_V1":
            allowed |= {"provider_assignment", "model_assignment", "model_family_assignment"}
        assert {k: v for k, v in current.items() if k not in allowed} == {
            k: v for k, v in previous.items() if k not in allowed
        }
        assert current["temperature"] == 0.0
        assert set(current["max_output_tokens"].values()) == {2048}


def test_r6_actual_adapter_payloads_exclude_gemini_and_nvidia(monkeypatch):
    candidate = PROVIDER_CANDIDATES["gemini"]
    assert candidate.primary is False
    assert candidate.availability == "excluded_transient_unavailable_r5"
    namespace = runpy.run_path(str(ROOT / "scripts/run_benchmark.py"))
    loader = namespace["_load_execution_adapters"]
    monkeypatch.setitem(loader.__globals__, "load_credential", lambda _name: SecretValue("synthetic"))
    monkeypatch.setattr("causalrisk.providers.factories.load_credential", lambda _name: SecretValue("synthetic"))

    def prohibited(*_args, **_kwargs):
        raise AssertionError("excluded provider factory invoked")

    monkeypatch.setattr("causalrisk.providers.factories.create_gemini_adapter", prohibited)
    monkeypatch.setattr("causalrisk.providers.factories.create_nvidia_adapter", prohibited)
    adapters = loader()
    payloads = []

    class Captured(Exception):
        pass

    def capture(_self, url, _headers, payload):
        payloads.append((url, payload))
        raise Captured

    monkeypatch.setattr("causalrisk.providers.http.StdlibJsonHttpTransport.post", capture)
    for config_id in METHOD_ORDER:
        config = load_config(ROOT / "configs/methods" / f"{config_id}.yaml")
        assert not {"gemini", "nvidia_nim"} & set(config.values["provider_pool"])
        for call in build_execution_plan(config).calls:
            provider = config.values["provider_assignment"][call.role]
            request = ProviderRequest("Synthetic request. Return YES.", config.values["model_assignment"][call.role],
                                      config.values["temperature"], 2048)
            with pytest.raises(Captured):
                adapters[provider].complete(request)
    assert len(payloads) == 17
    assert not any(name in json.dumps(payloads).lower() for name in ("gemini", "googleapis", "nvidia"))


@pytest.mark.parametrize("args", [
    ["--split", "smoke", "--max-items", "3"], ["--split", "smoke"],
    ["--split", "calibration"], ["--split", "locked_test"],
])
def test_all_four_cli_dry_runs_have_no_http_credentials_or_runtime_writes(monkeypatch, capsys, args):
    before = lineage.artifact_tree_sha256(ROOT / "artifacts")

    def prohibited(*_args, **_kwargs):
        raise AssertionError("dry-run crossed the request/credential/artifact boundary")

    monkeypatch.setattr("causalrisk.providers.http.StdlibJsonHttpTransport.post", prohibited)
    monkeypatch.setattr("causalrisk.credentials.load_credential", prohibited)
    monkeypatch.setattr("causalrisk.execution._prepare_run", prohibited)
    monkeypatch.setattr("sys.argv", ["run_benchmark.py", "--dry-run", *args])
    runpy.run_path(str(ROOT / "scripts/run_benchmark.py"), run_name="__main__")
    report = json.loads(capsys.readouterr().out)
    assert report["mode"] == "dry_run_no_http_no_artifacts"
    assert report["execution_revision"] == "cross_split_execution_r6"
    assert sum(report["provider_calls"].values()) == report["item_count"] * 17
    assert report["method_calls"]["C1_BOUNDARY_V1"] == 0
    assert report["method_calls"] == {
        method: count * report["item_count"]
        for method, count in zip(METHOD_ORDER, (1, 3, 5, 0, 3, 5), strict=True)
    }
    assert set(report["capacity"]["provider_plans"]) == {"groq", "cloudflare_workers_ai", "openai"}
    assert lineage.artifact_tree_sha256(ROOT / "artifacts") == before
    assert not SPLIT_POLICIES["calibration"].live_authorized
    assert not SPLIT_POLICIES["locked_test"].live_authorized
