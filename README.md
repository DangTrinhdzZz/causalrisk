# CausalRisk: Risk-Adaptive Routing for LLM Causal Reasoning

CausalRisk is a research repository currently in the protocol-design stage. It is intended to support a controlled study of routing strategies for large language model reasoning under explicitly supplied causal models; the repository does not yet contain an implemented experimental system or empirical results.

## Research scope

The planned study concerns formal causal inference with supplied directed acyclic graphs (DAGs) or structural causal models (SCMs). It covers association, intervention, and counterfactual reasoning within the assumptions and semantics of the provided causal model.

## Out of scope for the pilot

The pilot excludes causal discovery, extraction of DAGs from unstructured text, user-interface development, NoisyCausal evaluation, and claims of causal validity beyond the supplied causal model.

## Current status

The repository structure has been initialized. The research protocol, model selection, data splits, and experiments have not been finalized. No experimental results are available.

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

## Technology

Python 3.11 and `uv` are planned for the project. The environment has not yet been initialized and dependencies have not yet been locked.
