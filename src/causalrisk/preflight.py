"""Structural and execution preflight checks for frozen benchmark configs."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from causalrisk.config import ConfigError, load_config, validate_config
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


def run_preflight(repo_root: str | Path, *, for_execution: bool = False) -> PreflightReport:
    root = Path(repo_root).resolve()
    checks: list[PreflightCheck] = []
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
