# CausalRisk: Risk-Adaptive Routing for LLM Causal Reasoning

CausalRisk is a research repository currently in the protocol-design stage. It is intended to support a controlled study of routing strategies for large language model reasoning under explicitly supplied causal models; the repository does not yet contain an implemented experimental system or empirical results.

## Research scope

The planned study concerns formal causal inference with supplied directed acyclic graphs (DAGs) or structural causal models (SCMs). It covers association, intervention, and counterfactual reasoning within the assumptions and semantics of the provided causal model.

## Out of scope for the pilot

The pilot excludes causal discovery, extraction of DAGs from unstructured text, user-interface development, NoisyCausal evaluation, and claims of causal validity beyond the supplied causal model.

## Current status

Day 1 protocol design and the sealed-split workflow are complete. The Day 2 implementation skeleton includes the six frozen method configurations, a versioned prompt bundle, deterministic parser, label-free inference boundary, provider-neutral interfaces, wrapper-owned retry policy, event validation, artifact freezing, and a physically separate gold-aware scorer. Provider/model assignments and decoding limits remain provisional and execution is deliberately blocked. No API or benchmark call and no scoring run has been made.

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

Structural preflight is expected to pass. Execution preflight is intentionally expected to fail until every exact provider/model has passed the Step 8 smoke checks and each resolved configuration has been explicitly frozen and enabled:

```console
uv run python scripts/validate_preflight.py --execution
```

Do not weaken or bypass this failure. `scripts/run_benchmark.py` uses the same execution gate and does not yet contain a benchmark controller.

## Sealed inference preparation

After the audited source archive and private manifests exist locally, a trusted preparation command can create a strict label-free view for the inference process:

```console
uv run python scripts/materialize_inference_split.py --split smoke
```

The loader accepts only `item_id`, `background`, `given_info`, and `question`; it rejects records containing labels or protected metadata. Generated views remain under the ignored `data/splits/private/` area. Locked-test materialization has an additional explicit authorization gate and is not part of initial Day 2 work.

## Provider smoke tests and scoring

`scripts/smoke_provider.py` is restricted to a non-benchmark arithmetic prompt and requires both an installed verified adapter factory and the explicit `--authorize-live-call` flag. Live provider adapters and exact model IDs are not yet frozen, so no smoke call should be attempted merely because the script exists.

Gold-aware scoring is available only through the separate `causalrisk.scoring` namespace and `scripts/score_runs.py`. The scorer checks the run manifest's frozen state before loading the gold file. Raw outputs, inference views, manifests, and run artifacts are local-only and must not be committed.
