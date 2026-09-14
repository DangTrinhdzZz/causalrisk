# Day 2 Runtime Readiness

**Status:** R1/R2/R3 frozen failed; cross-split R4 implemented; R4 live canary not authorized

Amendment 007 records the terminal R3 NVIDIA output-cap failure and introduces
only NVIDIA non-thinking request control. All earlier canaries remain frozen
with `run_status=failed`; their successful outputs may not be reused. R4 has
distinct run identities and may not resume or merge R1/R2/R3 artifacts.

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

## Cross-split R4 dry-run plans

Each dry-run checks its protocol-v1 sealed source manifest and v2 label-free
view, loads all six method configs in fixed order, verifies every role against
the roster, validates the provider-limit snapshot and predecessor gate, and
inspects deterministic artifact paths without writing them. C1 aliases A1 and
schedules no duplicate calls. Dry-run performs no credential load or HTTP call.

| Method | Logical API calls |
|---|---:|
| A1 | 60 |
| A3 | 180 |
| A5 | 300 |
| C1 | 0 additional (aliases A1) |
| C3 | 180 |
| C5 | 300 |
| **Total** | **1,020** |

The fixed totals are 51/204 for the three-item R4 canary, 1,020/4,080 for
smoke-60, 5,100/20,400 for calibration-300, and 10,200/40,800 for
locked-test-600, where each pair is logical calls/transport-attempt ceiling.
Per item the provider allocation is Groq 11, NVIDIA NIM 2, Gemini 1,
Cloudflare Workers AI 1, and OpenAI 2.

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
`null`. Dry-run cost remains `null` because it has no live token usage; the
versioned pricing snapshot is applied only to reported usage after a call.

## Controlled execution and phase gates

All six configs remain runtime-verified and `execution_enabled: true` under
Amendment 007. Split policy independently permits only smoke, and that does not
itself authorize an API call. The deterministic R4 three-item canary must be
separately run with `--authorize-live-smoke` and pass before smoke-60 can be
considered. A failed canary never starts smoke-60 automatically.
Calibration-300 and locked-test-600 remain `BLOCKED_NOT_AUTHORIZED` under their
separate acknowledgement flags.

The R4 canary uses run ID `cladder-smoke-canary-3-r4`, 51 logical calls, and a
204-transport-attempt ceiling. Its expected artifact root is
`artifacts/runs/cladder-smoke-canary-3-r4/`. Smoke-60 requires its frozen
complete result and a new authorization. Calibration then requires a new
amendment after smoke review; locked test requires completed calibration,
scoring, and final configuration freeze plus another amendment.

## Label-free boundary and resumable execution

The v2 views for smoke, calibration, and locked test contain exactly
`item_id`, `background`, `given_info`, and `question` per item. Item IDs remain
local controller metadata. Rung appears only in the ignored smoke selector;
labels, ground truth, reasoning, query type, protected identifiers, and split
membership never enter the view or model context.

R4 uses item-major execution and fixed run IDs. A planned
`--max-new-items N` boundary pauses only after a complete item topology and
keeps the run open. Deterministic resume skips completed logical calls.
Ambiguous attempts or lineage drift block resume; terminal complete/failed
runs are frozen and cannot be resumed or overwritten.

## Pricing snapshot

`configs/pricing_2026-09-11.json` freezes USD list prices per million tokens
effective 2026-09-11. Official sources are the Groq GPT-OSS model page, Google
Gemini API pricing page, Cloudflare Qwen model page, OpenAI GPT-5.6 Terra model
page, and NVIDIA Build model page. NVIDIA describes a free prototype endpoint
but publishes no comparable token list price, so its input/output rates remain
`null`. Amendment 003 permits execution only through an explicit, source-dated
NVIDIA waiver in each method config; all other missing official prices remain
hard blockers. Actual account charges remain a separate nullable field and
free-tier billing never forces normalized list cost to zero.

The account-limit snapshot is
`configs/provider_limits_2026-09-12.json`. Current account RPM/TPM/RPD/TPD
values are unknown and therefore remain `null`, producing explicit capacity
warnings rather than invented limits. Groq's cross-split transport-start
interval is 10 seconds. The offline planner reports known pacing floors and
empirical projections while leaving unsupported totals, charges, windows, and
days null.

| Plan | Pacing-only runtime floor | Groq-only empirical normalized-cost projection |
|---|---:|---:|
| R4 canary | 320 s | USD 0.01196158 |
| Smoke-60 | 6,590 s | USD 0.23923167 |
| Calibration-300 | 32,990 s | USD 1.19615833 |
| Locked-test-600 | 65,990 s | USD 2.39231667 |

These are lower-bound/projection fields, not full-run forecasts. The normalized
total remains `null` because four providers lack usable empirical coverage and
NVIDIA is intentionally unpriced. Groq, Gemini, Cloudflare Workers AI, and
OpenAI may incur account charges; direct actual-charge evidence is unavailable,
so `actual_charge_usd` and overall reporting coverage remain `null`.
