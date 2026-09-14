# CausalRisk: Risk-Adaptive Routing for LLM Causal Reasoning

CausalRisk is a research repository currently in the protocol-design stage. It is intended to support a controlled study of routing strategies for large language model reasoning under explicitly supplied causal models; the repository does not yet contain an implemented experimental system or empirical results.

## Research scope

The planned study concerns formal causal inference with supplied directed acyclic graphs (DAGs) or structural causal models (SCMs). It covers association, intervention, and counterfactual reasoning within the assumptions and semantics of the provided causal model.

## Out of scope for the pilot

The pilot excludes causal discovery, extraction of DAGs from unstructured text, user-interface development, NoisyCausal evaluation, and claims of causal validity beyond the supplied causal model.

## Current status

Day 1 protocol design and the sealed-split workflow are complete. The frozen R1,
R2, and R3 operational canaries failed before any gold was opened and remain
immutable audit trails. Amendment 007 defines the narrow cross-split R4 NVIDIA
thinking-control revision. No live CLadder call is authorized implicitly: a
separately authorized R4 three-item canary must pass before smoke-60.
Calibration and locked-test live execution remain disabled.

## Planned methodology

After the protocol is frozen, the study is planned to compare four high-level approaches: a single-agent approach, fixed heterogeneous multi-agent collaboration, generic adaptive routing, and causal-risk routing. Their operational definitions and evaluation conditions remain subject to the protocol-freeze process.

## Reproducibility principles

- Prompts and configurations will be versioned.
- The final test set will be locked before evaluation.
- Previous experimental runs will not be overwritten.
- Token usage, model calls, and latency will be logged for each run.

## Repository structure

- `docs/` will contain the research charter, scope, protocol, evaluation plan, literature mapping, and decision log.
- `configs/` will contain versioned protocol, model, method, and experiment configurations.
- `data/` will document data provenance and contain local raw, processed, split, and schema artifacts subject to licensing constraints.
- `prompts/` will contain versioned prompts for primary, critic, revision, and baseline conditions.
- `src/` will contain the future `causalrisk` implementation after its components are designed.
- `tests/` will contain unit tests, integration tests, and non-sensitive fixtures.
- `outputs/` will contain immutable run records and derived summaries, figures, and tables.

## Roadmap

Day 1 protocol freeze → smoke test → calibration → verifier and risk routing → locked test → evaluation.

## Local setup and validation

Python 3.11 and `uv` are required. From the repository root:

```console
uv sync --dev
uv run pytest
uv run python scripts/validate_preflight.py
```

Structural and smoke execution preflight are expected to pass for the R4
controlled-smoke configuration. Missing official pricing remains blocked by
default; NVIDIA is covered only by the explicit Amendment 003 waiver:

```console
uv run python scripts/validate_preflight.py --execution --split smoke
```

Do not weaken or bypass a failed gate. Live acknowledgement flags are
split-specific; only smoke is enabled by policy. Smoke-60 is additionally
blocked until the frozen R4 three-item canary passes. Calibration and locked
test remain `BLOCKED_NOT_AUTHORIZED` even when their flags are supplied.

## Sealed inference preparation

After the audited source archive and private manifests exist locally, a trusted preparation command can create a strict label-free view for the inference process:

```console
uv run python scripts/materialize_inference_split.py --split smoke
uv run python scripts/materialize_inference_split.py --split calibration
uv run python scripts/materialize_inference_split.py --split locked_test
```

The loader accepts only `item_id`, `background`, `given_info`, and `question`;
it rejects records containing labels or protected metadata. Generated views,
checksums, and the controller-only smoke canary selector remain under the
ignored `data/splits/private/` area. Rung is absent from every inference view
and model prompt.

## Provider smoke tests and scoring

`scripts/smoke_provider.py` is restricted to a non-benchmark arithmetic prompt and requires both an installed verified adapter factory and the explicit `--authorize-live-call` flag. Existing accepted evidence must not be repeated merely because the script exists.

Preview each fixed R4 schedule without API calls or runtime-artifact writes:

```powershell
uv run python scripts/run_benchmark.py --dry-run --split smoke
uv run python scripts/run_benchmark.py --dry-run --split smoke --max-items 3
uv run python scripts/run_benchmark.py --dry-run --split calibration
uv run python scripts/run_benchmark.py --dry-run --split locked_test
```

These dry-runs create no HTTP request or runtime artifact. The live canary
command is intentionally documented in `docs/provider_smoke_runbook.md` and
must not be run without separate authorization.

Gold-aware scoring is available only through the separate `causalrisk.scoring` namespace and `scripts/score_runs.py`. The scorer checks the run manifest's frozen state before loading the gold file. Raw outputs, inference views, manifests, and run artifacts are local-only and must not be committed.
