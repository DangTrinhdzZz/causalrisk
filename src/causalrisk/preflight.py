"""Structural and execution preflight checks for frozen benchmark configs."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from causalrisk.config import ConfigError, load_config, validate_config
from causalrisk.prompts import file_sha256, load_prompt_bundle


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


def run_preflight(repo_root: str | Path, *, for_execution: bool = False) -> PreflightReport:
    root = Path(repo_root).resolve()
    checks: list[PreflightCheck] = []
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

    ignored = _git_ignored(root, "artifacts/runs/preflight-probe")
    checks.append(
        PreflightCheck("artifact_root_ignored", ignored, "artifacts/runs is ignored" if ignored else "not ignored")
    )
    env_ignored = _git_ignored(root, ".env")
    checks.append(PreflightCheck("real_env_ignored", env_ignored, ".env is ignored" if env_ignored else "not ignored"))
    return PreflightReport(tuple(checks))
