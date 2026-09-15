# Amendment 009 - R6 Post-Stop Operational Availability Remediation

**Decision date:** 2026-09-15

**Status:** offline preparation only; separate authorization required for live R6 canary.

## Explicit post-stop decision

The user explicitly requested this single post-stop operational availability
remediation after the R5 canary failed. It supersedes Amendment 008's stop on
automatic R6 creation only for this requested revision. No gold labels,
accuracy, causal-reasoning results, or prompt-quality evidence informed it.
Removing Gemini is an availability decision, not a model-quality conclusion.

R6 is the final execution revision for today's session. A failed R6 canary
must stop and remain frozen; do not automatically create R7, start smoke-60,
retry the frozen run, or change the prompt, parser, retry policy, or roster.
This amendment authorizes no live call, synthetic smoke, scoring, calibration,
or locked-test execution.

## Immutable R5 operational lineage

Local R5 artifacts were inspected at code commit
`ff197cc27cbf3fa672c746a1ec9546518d939ba7`, with a clean tracked working tree.
`cladder-smoke-canary-3-r5` / `cross_split_execution_r5` is frozen/failed.
It expected 51 calls and stopped after 30 successes plus one terminal failure,
using 34 transport attempts.

Failed call `c265b9d6eb558b1a25de9ae393bdb0d9` is C5
`semantic_query_critic`, Gemini `gemini-3.8-flash`. Attempts 0, 1, 2, and 3
all returned HTTP 503, provider code `503`, provider type `UNAVAILABLE`,
classified `provider/http_5xx`; retry_count=3. The model ID is valid.
Backoff 1/2/4 seconds plus jitter already matches the frozen retry policy.

| Exact R5 input | SHA-256 |
|---|---|
| Manifest | `60475269e6b507c891b16ef02a44ba2672ba0683d7b0d64975ef9be8b4f246f6` |
| Artifact tree | `2ef7b14410349942a63cb4400bb26e347b57a961400788d83ddd1e1d5c5468d0` |
| Summary | `81b1db961d00368f755a554047ef1e596186941a4f4733af1f6b9bcfcdde37a1` |

The tree hash uses the unchanged canonical `artifact_tree_sha256` function.
The label-free aggregate is
[r5_operational_canary_forensic_aggregate.json](r5_operational_canary_forensic_aggregate.json);
it contains no item membership, raw prompt/output, gold, secret, or accuracy data.
R6 eligibility requires all three hashes and the exact frozen/failed state.
The execution core rechecks the on-disk gate before any runtime-artifact write.
The verified predecessor hashes are retained in R6 execution lineage.

R1-R5 remain immutable operational failures, never benchmark results. Do not
resume, overwrite, delete, merge, score, or reuse their successful outputs.

## R6 roster and topology

`execution_revision = cross_split_execution_r6`.

Gemini remains available only for historical audit, with `primary=false` and
`availability=excluded_transient_unavailable_r5`; its reason records all four
R5 HTTP 503/UNAVAILABLE attempts. R6 does not load `GEMINI_API_KEY`, construct
a Gemini adapter request, or produce a Gemini payload. NVIDIA remains excluded
under Amendment 008. There is no per-call provider fallback.

| Method / role | Provider / model |
|---|---|
| A1, A3, A5 analysts | Groq / `openai/gpt-oss-120b` |
| C3 analyst | Groq / `openai/gpt-oss-120b` |
| C3 critic | Cloudflare / `@cf/qwen/qwen3-30b-a3b-fp8` |
| C3 adjudicator | OpenAI / `gpt-5.6-terra` |
| C5 analyst | Groq / `openai/gpt-oss-120b` |
| C5 semantic/query critic | Cloudflare / `@cf/qwen/qwen3-30b-a3b-fp8` |
| C5 graph/identification critic | Cloudflare / `@cf/qwen/qwen3-30b-a3b-fp8` |
| C5 formal/numerical critic | Cloudflare / `@cf/qwen/qwen3-30b-a3b-fp8` |
| C5 adjudicator | OpenAI / `gpt-5.6-terra` |

C5 is a five-agent, three-model-family, role-heterogeneous council. It does not
have five independent providers/models. Its three Cloudflare critics are
independent calls at topology positions 1, 2, and 3, each receiving the analyst
card. Their outputs are never reused across critic roles; the adjudicator
receives all three cards. C1 aliases A1 and creates zero calls.

## Fixed runs and exact budgets

| Phase / fixed run ID | Calls | Maximum attempts | Groq | Cloudflare | OpenAI |
|---|---:|---:|---:|---:|---:|
| Canary-3 / `cladder-smoke-canary-3-r6` | 51 | 204 | 33 | 12 | 6 |
| Smoke-60 / `cladder-smoke-60-r6` | 1,020 | 4,080 | 660 | 240 | 120 |
| Calibration-300 / `cladder-calibration-300-r6` | 5,100 | 20,400 | 3,300 | 1,200 | 600 |
| Locked-test-600 / `cladder-locked-test-600-r6` | 10,200 | 40,800 | 6,600 | 2,400 | 1,200 |

Per item: Groq 11, Cloudflare 4, OpenAI 2, Gemini 0, NVIDIA 0; total 17.
Method calls per item stay A1/A3/A5/C1/C3/C5 = 1/3/5/0/3/5.

Smoke-60 requires an exact R6 frozen/complete canary with 51/51 calls, zero
terminal errors, correct provider counts, valid independent call/attempt
artifacts, and its R5 predecessor lineage intact. Missing, failed, incomplete,
or tampered canaries block smoke-60 before any request or runtime write.
Nothing automatically starts the next phase. Calibration and locked test
remain live-disabled even if their acknowledgement flags are supplied.

## Unchanged protocol and accounting

CLadder selections and label-free inference views, prompt text and checksum,
output schemas, strict YES/NO parser, temperature, max_output_tokens=2048,
initial plus at most three retries, backoff 1/2/4 seconds plus jitter,
max_terminal_errors=0, item-major ordering, 17 calls/item, topology, pacing,
atomic writes, immutable artifacts, resume safety, and label-free execution
remain unchanged. No gold or scoring is accessed during R6 preparation.

The existing `configs/pricing_2026-09-11.json` entries remain unchanged.
All three active R6 provider/model pairs have normalized list prices: 100%
active-roster coverage. Full realized call/token cost coverage still requires
reported token usage. `actual_charge_usd` is a separate nullable field and is
never substituted for normalized cost. Gemini and NVIDIA prices are retained
historical data, not R6 execution-pricing inputs.

## Offline checks and authorization boundary

Run pytest, Ruff, structural preflight, smoke execution preflight, all four
phase dry-runs, and `git diff --check`. Dry-runs create zero HTTP requests and
zero runtime artifacts. Keep the six untracked patches and README.pdf untouched.
Create one atomic commit; do not push.

See [provider_smoke_runbook.md](provider_smoke_runbook.md#5-controlled-cladder-canary-r6)
for the exact future PowerShell command. The remaining live-canary gate after
offline validation is explicit user authorization for that single R6 canary.
