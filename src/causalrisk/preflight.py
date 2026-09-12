"""Structural and execution preflight checks for frozen benchmark configs."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

from causalrisk.capacity import CapacityError, build_capacity_plan, load_provider_limits
from causalrisk.config import ConfigError, load_config, validate_config
from causalrisk.execution_policy import MINIMUM_INTERVAL_SECONDS, get_execution_policy
from causalrisk.lineage import verify_r1_remediation_input
from causalrisk.pricing import PricingError, load_pricing, missing_official_prices, waiver_allows_unpriced_provider
from causalrisk.prompts import file_sha256, load_prompt_bundle
from causalrisk.providers.candidates import PROVIDER_CANDIDATES
from causalrisk.runtime_evidence import audit_runtime_evidence

EXPECTED_CREDENTIAL_TEMPLATE = {
    "GROQ_API_KEY",
    "GEMINI_API_KEY",
    "MISTRAL_API_KEY",
    "CLOUDFLARE_ACCOUNT_ID",
    "CLOUDFLARE_API_TOKEN",
    "NVIDIA_API_KEY",
    "OPENAI_API_KEY",
}


@dataclass(frozen=True, slots=True)
class PreflightCheck:
    name: str
    passed: bool
    detail: str


@dataclass(frozen=True, slots=True)
class PreflightReport:
    checks: tuple[PreflightCheck, ...]

    @property
    def passed(self) -> bool:
        return all(check.passed for check in self.checks)


def _git_ignored(repo_root: Path, relative_path: str) -> bool:
    result = subprocess.run(
        ["git", "check-ignore", "-q", relative_path],
        cwd=repo_root,
        check=False,
        capture_output=True,
    )
    return result.returncode == 0


def _credential_template_is_safe(path: Path) -> bool:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return False
    assignments: dict[str, str] = {}
    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            return False
        name, value = line.split("=", 1)
        assignments[name] = value
    return set(assignments) == EXPECTED_CREDENTIAL_TEMPLATE and all(value == "" for value in assignments.values())


def run_preflight(
    repo_root: str | Path,
    *,
    for_execution: bool = False,
    split: str | None = None,
    max_new_items: int | None = None,
) -> PreflightReport:
    root = Path(repo_root).resolve()
    checks: list[PreflightCheck] = []
    if split is not None and split not in {"smoke", "calibration", "locked_test"}:
        raise ValueError("split must be smoke, calibration, or locked_test")
    try:
        pricing = load_pricing(root / "configs" / "pricing_2026-09-11.json")
        missing_prices = missing_official_prices(pricing)
        checks.append(PreflightCheck("pricing_snapshot", True, pricing["version"]))
    except (OSError, ValueError, PricingError) as error:
        pricing = None
        missing_prices = ()
        checks.append(PreflightCheck("pricing_snapshot", False, str(error)))
    evidence = audit_runtime_evidence(root / "artifacts" / "smoke")
    missing_evidence = sorted(evidence.missing_primary_providers)
    checks.append(
        PreflightCheck(
            "runtime_evidence",
            not missing_evidence,
            (
                f"accepted all 5 execution providers; rejected {len(evidence.rejected)} non-qualifying reports"
                if not missing_evidence
                else f"missing valid evidence for: {', '.join(missing_evidence)}"
            ),
        )
    )
    prompt_path = root / "prompts" / "prompt_causal_yesno_v1.json"
    try:
        prompt = load_prompt_bundle(prompt_path)
        checks.append(PreflightCheck("prompt_bundle", True, prompt.sha256))
    except (OSError, ValueError) as error:
        checks.append(PreflightCheck("prompt_bundle", False, str(error)))
        prompt = None

    retry_path = root / "docs" / "retry_policy.md"
    retry_hash = file_sha256(retry_path) if retry_path.is_file() else None
    config_dir = root / "configs" / "methods"
    configs = sorted(config_dir.glob("*.yaml"))
    expected_count = 6
    checks.append(
        PreflightCheck("six_method_configs", len(configs) == expected_count, f"found {len(configs)} method configs")
    )
    loaded_configs = {}
    for path in configs:
        try:
            config = load_config(path)
            values = config.values
            loaded_configs[config.config_id] = values
            if for_execution:
                validate_config(values, for_execution=True)
            if prompt is None or values["prompt_sha256"] != prompt.sha256:
                raise ConfigError("prompt checksum does not match the referenced bundle")
            if retry_hash is None or values["retry_policy_sha256"] != retry_hash:
                raise ConfigError("retry-policy checksum does not match the normative document")
            checks.append(PreflightCheck(path.stem, True, "valid"))
        except (OSError, ValueError) as error:
            checks.append(PreflightCheck(path.stem, False, str(error)))

    analyst_caps_match = bool(loaded_configs) and all(
        values["max_output_tokens"]["analyst"] == 2048
        for values in loaded_configs.values()
        if "analyst" in values.get("max_output_tokens", {})
    )
    other_caps_match = bool(
        loaded_configs.get("C3_COUNCIL_V1")
        and loaded_configs["C3_COUNCIL_V1"]["max_output_tokens"]
        == {"analyst": 2048, "critic": 1024, "adjudicator": 768}
        and loaded_configs.get("C5_COUNCIL_V1")
        and loaded_configs["C5_COUNCIL_V1"]["max_output_tokens"]
        == {
            "analyst": 2048,
            "semantic_query_critic": 1024,
            "graph_identification_critic": 1024,
            "formal_numerical_critic": 1024,
            "adjudicator": 768,
        }
    )
    checks.append(
        PreflightCheck(
            "analyst_output_cap",
            analyst_caps_match and other_caps_match,
            "all analyst mirrors use 2048; every non-analyst cap is unchanged",
        )
    )
    checks.append(
        PreflightCheck(
            "groq_pacing_policy",
            MINIMUM_INTERVAL_SECONDS.get("groq") == 10.0,
            "Groq minimum start interval is 10.0 seconds for every split",
        )
    )

    try:
        provider_limits = load_provider_limits(root / "configs/provider_limits_2026-09-12.json")
        checks.append(PreflightCheck("provider_limit_snapshot", True, provider_limits["version"]))
    except (OSError, CapacityError) as error:
        provider_limits = None
        checks.append(PreflightCheck("provider_limit_snapshot", False, str(error)))

    if for_execution:
        execution_split = split or "smoke"
        policy = get_execution_policy(execution_split)
        session_bound_valid = max_new_items is None or (
            not isinstance(max_new_items, bool)
            and isinstance(max_new_items, int)
            and 1 <= max_new_items <= policy.item_count
        )
        checks.append(
            PreflightCheck(
                "session_item_limit",
                session_bound_valid,
                "full-run session" if max_new_items is None else f"max_new_items={max_new_items}",
            )
        )
        checks.append(
            PreflightCheck(
                "split_live_authorization_state",
                policy.live_authorized,
                "AUTHORIZED_BY_POLICY_GATE" if policy.live_authorized else "BLOCKED_NOT_AUTHORIZED",
            )
        )
        if provider_limits is not None:
            forensic = json.loads(
                (root / "docs/r1_operational_canary_forensic_aggregate.json").read_text(encoding="utf-8")
            )
            capacity = build_capacity_plan(
                policy,
                provider_limits=provider_limits,
                forensic_report=forensic,
                max_new_items=max_new_items if session_bound_valid else None,
            )
            assessment = capacity["limit_assessment"]
            detail = ", ".join(assessment["violations"] or assessment["warnings"]) or "within declared limits"
            checks.append(PreflightCheck("projected_provider_capacity", assessment["passed"], detail))
        else:
            checks.append(PreflightCheck("projected_provider_capacity", False, "provider limits unavailable"))
        if execution_split == "smoke":
            r1_intact = verify_r1_remediation_input(root / "artifacts/runs")
            checks.append(
                PreflightCheck(
                    "r1_immutable_remediation_lineage",
                    r1_intact,
                    "R1 frozen failed tree checksum matches Amendment 005" if r1_intact else "R1 lineage mismatch",
                )
            )
        waiver_failures = []
        for key in missing_prices:
            provider = key.split(":", 1)[0]
            matching_configs = [
                values
                for values in loaded_configs.values()
                if provider in values.get("provider_assignment", {}).values()
            ]
            if provider != "nvidia_nim" or not matching_configs or not all(
                waiver_allows_unpriced_provider(pricing, key, values.get("allow_symbolic_unpriced_provider"))
                for values in matching_configs
            ):
                waiver_failures.append(key)
        checks.append(
            PreflightCheck(
                "official_pricing_policy",
                pricing is not None and not waiver_failures,
                (
                    "all roster models priced"
                    if not missing_prices
                    else "explicit NVIDIA symbolic-pricing waiver accepted"
                    if not waiver_failures
                    else f"missing official prices without valid waiver: {', '.join(waiver_failures)}"
                ),
            )
        )

    a1 = loaded_configs.get("A1_SINGLE_V1")
    c1 = loaded_configs.get("C1_BOUNDARY_V1")
    if a1 is not None and c1 is not None:
        ignored_fields = {"config_id", "method_family", "alias_of", "notes"}
        a1_behavior = {key: value for key, value in a1.items() if key not in ignored_fields}
        c1_behavior = {key: value for key, value in c1.items() if key not in ignored_fields}
        alias_matches = c1_behavior == a1_behavior
    else:
        alias_matches = False
    checks.append(
        PreflightCheck(
            "c1_alias_equivalence",
            alias_matches,
            "C1 behavior equals A1" if alias_matches else "C1 and A1 behavior differ",
        )
    )

    c3 = loaded_configs.get("C3_COUNCIL_V1")
    c5 = loaded_configs.get("C5_COUNCIL_V1")
    primary_providers = {
        candidate.provider
        for candidate in PROVIDER_CANDIDATES.values()
        if candidate.primary and candidate.availability == "available"
    }
    roster_matches = bool(
        c3
        and c5
        and c3["provider_assignment"]["analyst"] == c5["provider_assignment"]["analyst"]
        and c3["provider_assignment"]["critic"] == c5["provider_assignment"]["graph_identification_critic"]
        and c3["provider_assignment"]["adjudicator"] == c5["provider_assignment"]["adjudicator"]
        and set(c3["provider_assignment"].values()).issubset(set(c5["provider_assignment"].values()))
        and set(c5["provider_assignment"].values()) == primary_providers
    )
    checks.append(
        PreflightCheck(
            "amended_roster_consistency",
            roster_matches,
            "C3 core roles are nested in the five-family C5 roster" if roster_matches else "roster mapping differs",
        )
    )
    mistral = PROVIDER_CANDIDATES.get("mistral")
    nvidia = PROVIDER_CANDIDATES.get("nvidia_nim")
    provider_policy_matches = bool(
        mistral
        and mistral.primary is False
        and mistral.availability == "excluded_unavailable"
        and nvidia
        and nvidia.primary is True
        and nvidia.availability == "available"
        and nvidia.intended_role == "skeptical_critic"
    )
    checks.append(
        PreflightCheck(
            "provider_availability_policy",
            provider_policy_matches,
            (
                "Mistral excluded_unavailable; NVIDIA NIM primary skeptical_critic"
                if provider_policy_matches
                else "provider availability or role policy differs"
            ),
        )
    )

    ignored = _git_ignored(root, "artifacts/runs/preflight-probe")
    checks.append(
        PreflightCheck("artifact_root_ignored", ignored, "artifacts/runs is ignored" if ignored else "not ignored")
    )
    smoke_ignored = _git_ignored(root, "artifacts/smoke/preflight-probe.json")
    checks.append(
        PreflightCheck(
            "smoke_artifact_ignored",
            smoke_ignored,
            "artifacts/smoke is ignored" if smoke_ignored else "not ignored",
        )
    )
    env_ignored = _git_ignored(root, ".env")
    checks.append(PreflightCheck("real_env_ignored", env_ignored, ".env is ignored" if env_ignored else "not ignored"))
    template_safe = _credential_template_is_safe(root / ".env.example")
    checks.append(
        PreflightCheck(
            "credential_template",
            template_safe,
            ".env.example contains only empty approved variables" if template_safe else ".env.example is unsafe",
        )
    )
    return PreflightReport(tuple(checks))
