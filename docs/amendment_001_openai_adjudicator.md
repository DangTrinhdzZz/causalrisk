# Amendment 001 — Direct OpenAI Adjudicator

**Decision date:** 2026-09-10

**Status:** approved at protocol level; runtime verification remains pending

**Applies before:** any CLadder smoke, calibration, or locked-test inference

## 1. Decision

The direct OpenAI API is added to the provisional provider pool. OpenAI is the
provisional Adjudicator provider for both `C3_COUNCIL_V1` and
`C5_COUNCIL_V1`. The candidate model is `gpt-5.6-terra`; the exact accessible
model identifier and effective request parameters are not runtime-frozen until
the endpoint passes the non-benchmark smoke protocol.

NVIDIA NIM remains eligible as a predeclared reserve provider but has no primary
role in the amended C3/C5 mapping. A move from OpenAI to NVIDIA after runtime
freeze is prohibited unless a new amendment is recorded before the affected
benchmark run.

OpenRouter remains discovery/emergency fallback only. This amendment does not
promote it to a primary experimental endpoint.

## 2. Amended role mapping

| Configuration role | Provisional provider | Candidate model/family |
|---|---|---|
| Analyst in A1/A3/A5/C3/C5 | Groq | `openai/gpt-oss-120b` / GPT-OSS |
| C3 Critic and C5 Graph/Identification Critic | Mistral | `mistral-large-2512` / Mistral Large |
| C5 Semantic/Query Critic | Gemini | `gemini-3.8-flash` / Gemini 3.8 |
| C5 Formal/Numerical Critic | Cloudflare Workers AI | `@cf/qwen/qwen3-30b-a3b-fp8` / Qwen3 |
| C3/C5 Adjudicator | OpenAI | `gpt-5.6-terra` / GPT-5.6 |
| Reserve only | NVIDIA NIM | `nvidia/nemotron-3.5-lightning-30b-a3b` / Nemotron 3.5 |

The mapping preserves the A-versus-C call budgets and the rule that every
council role uses a distinct model family. C3 uses the same Analyst, core Critic,
and Adjudicator families that appear in C5. The change does not add a call,
change the topology, expose a label, or alter the A1/C1 alias.

## 3. Rationale and limits

The research owner explicitly approved GPT as the shared C3/C5 Adjudicator before any
benchmark inference. A shared Adjudicator improves comparability between the two
council sizes, while retaining NVIDIA as a reserve avoids expanding C5 beyond
its frozen five-call budget.

This is an operational design decision, not evidence that the selected model is
more accurate. Capability matching remains unverified and must be assessed only
with the permitted synthetic smoke checks and calibration split. Current model
availability, pricing, quota, response schema, latency, token accounting, and
parameter support remain account- and runtime-dependent.

Official OpenAI references used for implementation and later price freezing:

- https://developers.openai.com/api/docs/models
- https://developers.openai.com/api/docs/pricing
- https://developers.openai.com/api/reference/overview

## 4. Required implementation changes

1. Add only the placeholder `OPENAI_API_KEY=` to tracked `.env.example`; the
   real value stays in the ignored local `.env` file.
2. Add a direct OpenAI Responses API adapter with provider retries disabled.
3. Update the provisional provider assignments for the two Adjudicator roles.
4. Run one explicitly authorized, non-CLadder smoke request against the exact
   model and record its response schema, reported model, token fields, latency,
   HTTP status, and any parameter incompatibility.
5. Freeze the actual pricing source and model ID only after successful runtime
   verification and before calibration inference.

## 5. Execution gate

All affected configurations retain `runtime_verified: false` and
`execution_enabled: false`. This amendment does not authorize a CLadder call.
CLadder smoke 60 remains blocked until every selected model passes synthetic
smoke verification, the controller and artifact pipeline pass integration tests,
and the resolved configs pass execution preflight.
