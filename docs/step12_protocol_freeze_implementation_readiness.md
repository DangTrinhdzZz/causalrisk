# Step 12 – Protocol Freeze and Implementation Readiness

**Status:** Day 1 protocol-level design frozen; implementation and runtime verification remain pending.

## 1. Purpose

Step 12 closes Day 1 by freezing the protocol-level research design and defining the gates for the implementation phase. The repository is ready to move from planning to coding, but it is not ready for benchmark execution. No benchmark call is authorized until provider smoke tests, configuration and parser validation, artifact safeguards, and leakage checks all pass.

“Frozen” applies to the documented methodological decisions and governance rules. It does not imply that provisional providers or model identifiers are runtime verified. A behavioral change to a frozen decision requires a documented protocol amendment before affected execution.

## 2. Scope and non-scope

This step covers cross-document consistency, the frozen-design summary, implementation readiness, blockers and pending runtime verification, anticipated next-phase files, security and leakage safeguards, and the Day 1 completion status.

It makes no API call, performs no benchmark inference or scoring, reports no statistical result, and makes no model-performance claim. It does not change a locked method, split, analysis rule, prompt contract, or run policy. Such a change requires a separate protocol amendment.

## 3. Frozen protocol summary

- **Benchmark focus:** formal causal reasoning, primarily on the sealed CLadder evaluation splits.
- **Main comparison:** controlled single-agent strategies versus heterogeneous multi-agent council orchestration.
- **Configurations:** `A1_SINGLE_V1`, `A3_SINGLE_V1`, `A5_SINGLE_V1`, `C1_BOUNDARY_V1`, `C3_COUNCIL_V1`, and `C5_COUNCIL_V1`.
- **Single-agent methods:** `A1` uses one call; `A3` and `A5` use three and five independent calls to the same primary model with deterministic majority voting.
- **Council methods:** `C3` uses Analyst, Critic, and Adjudicator roles; `C5` uses one Analyst, three independent specialist Critics, and one Adjudicator.
- **Boundary condition:** `C1_BOUNDARY_V1` is exactly the `A1_SINGLE_V1` execution. It is not rerun, counted as an independent observation, or interpreted as a multi-agent condition.
- **Primary fair comparisons:** `A3` versus `C3` and `A5` versus `C5`, because their planned method-call budgets match.
- **Evaluation principle:** accuracy alone is insufficient. Conclusions jointly consider accuracy, tokens, latency, monetary cost, calls, completion, invalid outputs, retries, and failure types.
- **Inference boundary:** labels, dataset explanations, evaluation metadata, split information, retrieval, browsing, and gold-aware outputs remain unavailable to all model-facing code.
- **Analysis boundary:** scoring begins only after inference artifacts are complete, validated, and frozen.

## 4. Protocol document map

| Step | Document | Governing subject |
|---|---|---|
| 7 | [Methods and baselines freeze](step7_methods_and_baselines.md) | Configuration topology, call budgets, role information flow, fairness, and failure behavior. |
| 8 | [Model/API Roster Protocol](step8_model_api_roster.md) | Provisional providers/models, role-assignment strategy, smoke-verification requirements, and fallback governance. |
| 9 | [Run Protocol and Execution Checklist](step9_run_protocol.md) | Run lifecycle, inference contracts, logging, artifacts, retries, validity, and reproducibility. |
| 10 | [Statistical Analysis Plan and Evaluation Decision Rules](step10_statistical_analysis_plan.md) | Metrics, paired comparisons, statistical tests, accuracy–cost analysis, and decision rules. |
| 11 | [Prompt Templates and Config Schema](step11_prompt_config_schema.md) | Prompt components, role contracts, config identifiers/schema, output parsing, and leakage-safe construction. |
| 12 | [Protocol Freeze and Implementation Readiness](step12_protocol_freeze_implementation_readiness.md) | Cross-protocol freeze, implementation gates, pending checks, and Day 1 closure. |

The [data-splitting and leakage-control protocol](data_split_protocol.md), [sealed-split audit](cladder_split_audit.md), and [retry policy](retry_policy.md) remain normative supporting documents.

## 5. Cross-protocol consistency checks

The following invariants must hold in documentation, code, configs, and run artifacts:

- [x] Configuration IDs use the exact Step 11 names for all six configurations.
- [x] Planned method-call budgets are 1, 3, and 5 for the corresponding `A` and `C` configurations; retry-generated calls are separate and fully accounted for.
- [x] `C1` aliases the `A1` execution and never creates an independent run or observation.
- [x] `A3`/`A5` retain independent same-model sampling; `C3`/`C5` retain the Step 7 council topologies.
- [x] Gold labels and protected evaluation metadata remain outside inference prompts, controllers, routing, and model-visible logs.
- [x] Retrieval and web access are disabled during benchmark inference.
- [x] Prompt/config versions are recorded and immutable once used on the locked test.
- [x] The normative retry policy is referenced unchanged; SDK retries are disabled and wrapper retries are logged.
- [x] Config and event records can provide every required Step 9 logging field.
- [x] Primary comparisons and `A1/C1` treatment match Step 10.
- [x] Provider/model choices remain provisional until the Step 8 runtime smoke tests pass.

These checks establish documentary consistency only. They must be enforced again by implementation tests before execution.

## 6. Implementation readiness checklist

The next coding phase must implement and test:

- [ ] validated configuration files for `A1`, `A3`, `A5`, `C1`, `C3`, and `C5`;
- [ ] immutable, named prompt-template bundles and role-specific evidence-card schemas;
- [ ] a deterministic `YES`/`NO`/`INVALID` parser with synthetic unit tests;
- [ ] a provider abstraction that normalizes requests, responses, usage fields, and failures without changing method behavior;
- [ ] local credential loading from environment variables with redaction and fail-closed behavior;
- [ ] a minimal non-benchmark provider smoke-test script;
- [ ] an allowlist-based, label-free sealed-split loader for inference;
- [ ] a separate gold-aware scoring component that cannot be imported by the inference controller;
- [ ] an immutable run-artifact writer with checksums and freeze state;
- [ ] schema validators for configs, prompts, inference records, and event logs;
- [ ] the wrapper-owned retry controller and normative failure taxonomy;
- [ ] consistent token, call, latency, and estimated-cost collection;
- [ ] topology tests, including `A1/C1` aliasing and independent `A3`/`A5` samples;
- [ ] automated prompt/config leakage checks using synthetic inputs;
- [ ] README instructions for later smoke testing and authorized benchmark execution; and
- [ ] a preflight command that blocks execution unless all required validations pass.

Completion of code alone does not authorize benchmark execution. The runtime-verification and preflight gates below must also pass.

## 7. Runtime verification still pending

- [ ] Finalize and record exact provider model IDs, including the Gemini text model and every role-specific assignment.
- [ ] Verify provider authentication using local environment variables without printing or persisting credential values.
- [ ] Run a minimal non-benchmark smoke test for every intended provider/model endpoint.
- [ ] Confirm actual availability, rate limits, quota, billing limits, price sources, and stopping behavior.
- [ ] Reconcile provider-reported token accounting and document any estimation method.
- [ ] Validate a consistent end-to-end latency measurement boundary.
- [ ] Exercise timeout, rate-limit, empty, invalid, and malformed-output behavior against the frozen taxonomy.
- [ ] Confirm structured-output support and deterministic parser compatibility where applicable.
- [ ] Confirm that provider adapters and logs redact authorization data and potentially sensitive error payloads.
- [ ] Confirm with Git checks and secret scanning that no API key or credential is tracked.
- [ ] Freeze the verified roster, resolved configs, prompt/parser versions, runtime environment, and monetary limits.

Preliminary account creation or quota inspection is not runtime verification. A provider/model failing any required check remains ineligible for benchmark execution.

## 8. Security and leakage safeguards

API keys and other credentials must never be committed, embedded in code or documentation, printed, included in prompts, or retained in logs. Only placeholder variable names may appear in a tracked `.env.example`. Any real `.env` file remains local and ignored by Git; implementation must fail safely when required credentials are missing.

The inference controller receives only allowlisted, label-free records. It cannot load gold answers, dataset reasoning, split allocation metadata, or protected evaluation metadata. Retrieval, browsing, benchmark lookup, and prior scoring context are prohibited during inference. The gold-aware scorer is a separate component and may run only after the complete inference artifact has been validated and frozen.

Raw model output is preserved unchanged. Deterministic parsing and normalization follow the frozen policy; manual correction, answer imputation, selective reruns, silent provider replacement, and LLM-based format repair are prohibited. Any credential exposure, gold leakage, metadata leakage, unauthorized retrieval, configuration drift, or other protocol violation invalidates every affected run and must be documented before an authorized rerun.

## 9. Required next-phase files

The following are recommended implementation targets. They are not represented as existing or complete merely by appearing in this plan:

```text
configs/
  methods/
    A1_SINGLE_V1.yaml
    A3_SINGLE_V1.yaml
    A5_SINGLE_V1.yaml
    C1_BOUNDARY_V1.yaml
    C3_COUNCIL_V1.yaml
    C5_COUNCIL_V1.yaml
prompts/
  prompt_causal_yesno_v1.md
scripts/
  smoke_provider.py
  run_benchmark.py
  score_runs.py
src/
  causalrisk/
tests/
```

Likely supporting modules include config/prompt loaders, provider adapters, retry and parsing components, schemas, artifact writers, cost accounting, and preflight validation. Exact filenames may be refined during implementation if the responsibilities and protocol references remain explicit. Creating these targets does not itself establish correctness or authorize execution.

## 10. Benchmark execution gates

Benchmark execution remains blocked until all of the following are evidenced by local validation:

1. Every selected provider/model has passed the required minimal smoke test.
2. All resolved configs validate against the frozen schema and exact role topology.
3. Prompt renderers and synthetic snapshots pass version, comparability, and leakage checks.
4. The parser, retry controller, logging validator, and artifact freeze mechanism pass their tests.
5. The sealed split audit and manifest checksums pass without exposing membership.
6. The inference/scoring separation is verified and labels are inaccessible to the runner.
7. The artifact root and real environment files are ignored, and secret scanning passes.
8. Exact code, config, prompt, model, provider, environment, quota, pricing, and budget versions are recorded.

A failed gate blocks execution. Constraints must not be relaxed silently, and failures must not be bypassed by substituting an unverified fallback.

## 11. Day 1 completion statement

Day 1 is complete at protocol level. The research topology, evaluation controls, provisional roster governance, run contract, analysis plan, and prompt/config schema are sufficiently defined to begin implementation. The repository is not ready for benchmark execution until provider smoke tests, config validation, parser validation, security checks, and leakage/preflight checks complete successfully.

## 12. Final status

**Step 12 is completed at protocol level. Day 1 protocol planning is closed. No API call, benchmark inference, scoring execution, or model performance claim has been made in this step.**
