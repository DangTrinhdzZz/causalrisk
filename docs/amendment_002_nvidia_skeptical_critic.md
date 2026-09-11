# Amendment 002 — NVIDIA NIM Skeptical Critic

**Decision date:** 2026-09-11

**Status:** approved at protocol level; benchmark execution remains blocked

**Applies before:** any CLadder smoke, calibration, or locked-test inference

## 1. Decision

Mistral is removed from the execution roster after its synthetic provider check
returned HTTP 429 with `code=1300`, `type=rate_limited`, and
`X-RateLimit-Limit-Req-Minute=0`. It remains recorded in the candidate catalog
as `excluded_unavailable` so the failed route cannot be selected silently.

NVIDIA NIM is promoted from reserve to the primary skeptical Critic using
`nvidia/nemotron-3.5-lightning-30b-a3b`. Its authorized non-benchmark smoke at
`max_output_tokens=1024` succeeded with `parsed=YES`, zero retries, 55 input
tokens, and 245 output tokens. This transport result supports roster selection;
it does not authorize benchmark inference or by itself mark a method config
runtime-verified.

## 2. Final execution roster

| Role | Provider | Model |
|---|---|---|
| Analyst | Groq | `openai/gpt-oss-120b` |
| Skeptical Critic | NVIDIA NIM | `nvidia/nemotron-3.5-lightning-30b-a3b` |
| Semantic/Query Critic | Gemini | `gemini-3.8-flash` |
| Formal/Numerical Critic | Cloudflare Workers AI | `@cf/qwen/qwen3-30b-a3b-fp8` |
| Adjudicator | OpenAI | `gpt-5.6-terra` |

In C3, NVIDIA occupies `critic`; in C5 it occupies
`graph_identification_critic`. Thus the C3 Analyst/Critic/Adjudicator providers
remain a strict subset of the C5 roster. Call budgets, topology, prompt,
decoding policy, label boundaries, and the A1/C1 alias are unchanged.

## 3. Execution gate

All method configurations retain `runtime_verified: false` and
`execution_enabled: false`. No fallback to Mistral is permitted. Any later
provider substitution requires another amendment and the applicable smoke and
preflight checks before benchmark use.
