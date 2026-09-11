# Day 2 Runtime Readiness

**Status:** exact-model synthetic evidence accepted; live smoke-60 remains disabled

## Runtime evidence

The validator scans all local redacted JSON reports under `artifacts/smoke/`.
It does not depend on filenames or timestamps and never reads `.env`, headers,
prompts, raw responses, or credentials. A report qualifies only when its
provider and requested/reported model exactly match the primary roster, its
kind is `synthetic_non_benchmark`, status is `success`, HTTP status is 200,
`parsed_answer` is `YES`, raw output is absent, and latency/token metadata is
well formed.

Qualifying evidence exists for Groq `openai/gpt-oss-120b`, NVIDIA NIM
`nvidia/nemotron-3.5-lightning-30b-a3b`, Gemini `gemini-3.8-flash`, Cloudflare
Workers AI `@cf/qwen/qwen3-30b-a3b-fp8`, and OpenAI `gpt-5.6-terra`. Earlier
failure reports and all Mistral reports are rejected as runtime evidence.
Mistral remains `excluded_unavailable`.

## Smoke-60 dry-run plan

The dry-run checks the protocol-v1 sealed smoke manifest checksum and exact
60-item size, loads all six method configs in a fixed order, verifies every
role's provider/model/family against the roster, and inspects deterministic
artifact paths without writing them. C1 aliases A1 and schedules no duplicate
calls.

| Method | Logical API calls |
|---|---:|
| A1 | 60 |
| A3 | 180 |
| A5 | 300 |
| C1 | 0 additional (aliases A1) |
| C3 | 180 |
| C5 | 300 |
| **Total** | **1,020** |

| Provider | Logical API calls |
|---|---:|
| Groq | 660 |
| NVIDIA NIM | 120 |
| Gemini | 60 |
| Cloudflare Workers AI | 60 |
| OpenAI | 120 |

The retry ceiling is three retries after the initial attempt, so the absolute
worst-case transport-attempt ceiling is 4,080. This is a safety bound, not a
budget forecast. Token and latency fields will use provider-reported values or
`null`. Estimated cost remains `null` until a versioned pricing configuration
with sources is frozen; no price is inferred here.

## Remaining gate

All six configs are runtime-verified, but `execution_enabled` remains `false`.
The deterministic label-free smoke view is materialized locally and checksum
verified. Live smoke-60 requires an explicit enablement decision, completion
of the NVIDIA official-pricing field, and `--authorize-live-smoke`; dry-run
does not grant any of these.

## Pricing snapshot

`configs/pricing_2026-09-11.json` freezes USD list prices per million tokens
effective 2026-09-11. Official sources are the Groq GPT-OSS model page, Google
Gemini API pricing page, Cloudflare Qwen model page, OpenAI GPT-5.6 Terra model
page, and NVIDIA Build model page. NVIDIA describes a free prototype endpoint
but publishes no comparable token list price, so its input/output rates remain
`null` and execution fails closed. Actual account charges remain a separate
nullable field and free-tier billing never forces normalized list cost to zero.
