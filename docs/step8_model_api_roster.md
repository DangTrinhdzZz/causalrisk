# Step 8 – Model/API Roster Protocol

**Status:** protocol-level complete; provider connectivity, exact model identifiers, quotas, billing limits, and runtime behavior are not yet verified.

## 1. Purpose

Step 8 provisionally defines the provider and model pool for the controlled comparison of single-agent configurations (`A1`, `A3`, and `A5`) with heterogeneous-council configurations (`C1`, `C3`, and `C5`). It records intended role assignments and operational safeguards before controller implementation. This roster is a protocol decision, not evidence that an endpoint is usable or that a model performs adequately on CLadder.

## 2. Scope and non-scope

This step covers provisional provider eligibility, candidate model roles, fairness constraints, later runtime checks, secret handling, and fallback governance. It makes no API calls, runs no benchmark items, measures no model performance, and creates no experimental output. It does not finalize model IDs, decoding settings, token caps, actual quotas, prices, billing limits, or provider-specific runtime behavior.

Benchmark execution remains blocked until the later implementation stage completes minimal smoke tests and freezes all required operational settings. Smoke tests must be operational only and must not expose gold labels or be interpreted as benchmark results.

## 3. Provisional provider/model roster

“Provisionally selected” means eligible for implementation and smoke-test evaluation. “Runtime verified” means that the exact endpoint, model ID, authentication path, quota, billing behavior, response schema, and failure behavior have been confirmed in code. No provider below is runtime verified by this document.

| Provider | Provisional status | Candidate use | Verification still required |
|---|---|---|---|
| Groq | Available candidate; free-tier quota checked only at a preliminary level | Candidate primary, specialist, or backup endpoint, subject to capability matching | Exact model ID, live availability, real quota and rate limits, billing behavior, structured output, latency, and retry behavior |
| Gemini | Available candidate; quota checked only at a preliminary level | Candidate primary or council role | Exact text model ID, live availability, quota and billing limits, structured output, latency, and retry behavior |
| Mistral | Excluded/unavailable after HTTP 429 (`code=1300`, `type=rate_limited`) and a zero requests-per-minute limit | No execution role or fallback eligibility | Reconsideration requires a later amendment and successful verification |
| Cloudflare Workers AI | Candidate provider | Candidate specialist or backup endpoint | Account binding, exact model ID, runtime availability, quota, pricing, schema support, latency, and retry behavior |
| NVIDIA NIM | Synthetic smoke passed with the selected Nemotron model | Primary skeptical Critic | Pricing and remaining runtime-freeze gates |
| OpenRouter | Discovery and emergency fallback only | Not a primary experimental endpoint | Any later use requires verification and the governance action described below |

OpenRouter is not part of the primary experimental endpoint roster. It may be promoted only through an explicit protocol amendment made before affected benchmark execution; the amendment must identify the model/provider route and preserve the same fairness and verification requirements.

## 4. Model role assignment strategy

- `A1`, `A3`, and `A5` use the same provisionally designated primary model within their matched comparison. `A3` and `A5` repeat independent calls to that model; they do not introduce additional model families.
- `C1` is operationally identical to `A1`. It is a shared boundary condition, not an independent multi-agent observation and not evidence of a collaboration effect.
- `C3` uses distinct, capability-matched model families for Analyst, Critic, and Adjudicator roles.
- `C5` uses distinct, capability-matched model families for the Analyst, three specialist critics, and Adjudicator roles.
- The council Analyst uses the primary model matched to the corresponding single-agent baseline. Other roles are assigned before evaluation according to causal-reasoning suitability, reliability, price/latency tier, and role fit—not after observing benchmark accuracy.
- NVIDIA `nvidia/nemotron-3.5-lightning-30b-a3b` is the selected skeptical Critic for C3 and the corresponding graph/identification Critic slot in C5. Mistral is excluded and unavailable.

Final role-to-model mappings must be documented and frozen after operational verification and before benchmark execution. A fallback substitution must never silently change the experimental condition.

## 5. Fairness and comparability rules

1. At each controlled call budget, matched configurations receive the same causal question input and comparable base instructions. `A1/C1` is executed once as a shared condition.
2. Every model-facing final answer is normalized to exactly `YES` or `NO`. Invalid or missing outputs are handled under the frozen retry policy and recorded rather than repaired using gold information.
3. Gold answers and evaluation-only metadata—including rung, query type, graph ID, story ID, model ID, protected-family information, and split membership—must remain outside agents, prompts, controllers, and other model-facing code.
4. Benchmark inference must use no retrieval, web browsing, benchmark lookup, cross-item context, or metadata-derived hints.
5. Call budgets and retry rules are held constant for matched comparisons. Equal call count is not described as equal compute: token usage, latency, monetary cost, completion rate, invalid-output rate, retry count, and failure type are measured separately.
6. Council models must be drawn from distinct, reasonably capability-matched families and predeclared price/latency tiers. Models must not be assigned strategically after benchmark outcomes are known.
7. Provider-specific prompt wrappers may implement equivalent transport or schema requirements but must not add condition-specific causal information.

## 6. Runtime verification plan

During the later coding stage, minimal non-benchmark smoke tests will verify each proposed endpoint before any benchmark run:

1. Resolve and record the exact provider, endpoint, and immutable model identifier where available.
2. Confirm local authentication without logging or displaying secret values.
3. Verify endpoint availability, request/response compatibility, deterministic parsing, and normalization to `YES`/`NO`.
4. Measure observed token-accounting fields, latency reporting, pricing inputs, quota/rate-limit behavior, and billing constraints.
5. Exercise timeout, malformed-output, refusal, rate-limit, and retry handling using non-benchmark inputs.
6. Confirm that prompt construction contains only permitted inference fields and that logs redact secrets and protected benchmark data.
7. Record the verified roster and freeze role assignments, prompt/schema versions, decoding parameters, token caps, retry policy, and cost accounting before benchmark execution.

Failure of any required smoke test keeps benchmark execution blocked. Preliminary account or quota checks do not satisfy runtime verification.

## 7. API key and secret-handling policy

API keys and credentials must remain local, outside version control, and must never be written to documentation, source code, tracked configuration, command output, prompts, reports, or logs. Real `.env` files must not be created or committed as part of this step. If configuration documentation is later needed, only `.env.example` may be updated, using clearly fictitious placeholder variable names and no secret-like values.

Implementation must read credentials from an approved local secret source, redact authentication headers and provider error payloads where necessary, and fail safely when a credential is absent. Keys must not be inferred, reconstructed, tested, or transmitted except through the intended provider client during an explicitly authorized later smoke test.

## 8. Failure and fallback policy

The frozen retry policy governs transient failures and invalid outputs. Exhausted retries produce a recorded method failure; they do not authorize extra calls, silent provider substitution, answer imputation, or fallback to another council member. Completion rate, invalid-output rate, retry count, latency, cost, and failure type must remain visible in aggregate reporting.

A provider or model that fails runtime verification is excluded or replaced before the roster is frozen. The replacement must be documented, capability- and cost-matched where feasible, and reverified. A post-freeze provider change requires a protocol amendment and, where applicable, a return to calibration. OpenRouter remains discovery/emergency fallback only and cannot become a primary endpoint without an explicit protocol amendment.

## 9. Final status

**Step 8 is complete only at the protocol level.** The provider/model roster and its governance rules are provisionally defined, but no provider is declared fully runtime verified here. No API or benchmark call has been made by this step. Benchmark execution is prohibited until the pending smoke tests pass and the operational roster is frozen.

## 10. Completion and pending-verification checklist

Completed in Step 8:

- [x] Defined the execution provider pool: Groq, NVIDIA NIM, Gemini, Cloudflare Workers AI, and OpenAI.
- [x] Restricted OpenRouter to discovery/emergency fallback status.
- [x] Recorded Mistral as excluded/unavailable and NVIDIA NIM as the primary skeptical Critic.
- [x] Defined role-assignment, fairness, comparability, leakage-control, secret-handling, and fallback rules.
- [x] Preserved `C1` as the shared `A1/C1` boundary condition.
- [x] Blocked benchmark execution pending operational verification.

Pending for the later implementation stage:

- [ ] Verify every intended provider endpoint with minimal non-benchmark smoke tests.
- [ ] Finalize exact model IDs, including the Gemini text model.
- [ ] Verify real quota, rate limits, billing limits, prices, and account availability.
- [ ] Verify token accounting, latency, normalized output parsing, retries, and failure classification.
- [ ] Confirm secret redaction and the model-facing data boundary in implementation.
- [ ] Select and freeze the final role-to-model mapping and all runtime settings.
- [ ] Document any provider replacement or OpenRouter promotion through a protocol amendment before use.
