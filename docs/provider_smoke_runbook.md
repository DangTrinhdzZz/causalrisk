# Provider Synthetic-Smoke Runbook

**Status:** implementation runbook; CLadder remains blocked.

This runbook verifies transport and response compatibility using a fixed
arithmetic question. It never reads a CLadder split, a gold label, or an
evaluation artifact. Run providers one at a time so authorization, cost, and
failure handling remain explicit.

## 1. List the provisional candidates

```powershell
uv run python scripts/smoke_provider.py --list-candidates
```

This command makes no API call and does not load `.env`.

## 2. Run one explicitly authorized smoke call

Use the local ignored environment file. The acknowledgement covers one initial
request plus only the retries permitted by `docs/retry_policy.md`.

```powershell
uv run --env-file .env python scripts/smoke_provider.py `
  --provider openai `
  --authorize-live-call `
  --write-report
```

The smoke output cap defaults to 128 tokens. The direct OpenAI adapter omits
`temperature` because the selected model rejected that parameter during the
2026-09-10 pre-benchmark compatibility check. This records endpoint behavior;
it does not change another provider's decoding request or enable a benchmark
configuration.

Replace `openai` with exactly one of:

- `groq`
- `gemini`
- `cloudflare_workers_ai`
- `nvidia_nim`

Mistral remains visible in `--list-candidates` as `excluded_unavailable`, but
the script rejects it for execution. Its check returned HTTP 429,
`code=1300`, `type=rate_limited`, and a zero requests-per-minute limit.

The script prints and stores only operational metadata. It does not print the
credential, prompt, raw response, HTTP headers, or provider error body. Reports
are written under ignored `artifacts/smoke/`. The runtime-evidence validator
may accept only an exact-model HTTP 200 success parsed as `YES`; human review
and the remaining execution gates are still required.

For a failed request, only allowlisted provider fields `error.code`,
`error.type`, and `error.param` may be retained. Provider error messages and
unrecognized values are discarded. These fields distinguish an unsupported
parameter from an unavailable model without exposing request headers or secret
values.

## 3. Required order

1. Run OpenAI first to verify the newly amended Adjudicator path.
2. Run the four other primary-role providers one at a time.
3. Preserve every success and failure report locally.
4. Do not change a model ID in place after observing CLadder results. A candidate
   replacement must happen before benchmark execution and be documented.

NVIDIA's authorized synthetic smoke has already succeeded at
`max_output_tokens=1024`: `parsed=YES`, retries 0, input tokens 55, and output
tokens 245. Do not repeat it without separate authorization.

## 4. What a successful smoke does and does not prove

A pass confirms that authentication, exact model routing, the request shape,
response text extraction, deterministic YES/NO parsing, and available token
fields worked for that request. It does not establish causal-reasoning quality,
capability matching, stable quota, deterministic decoding, final pricing, or
benchmark readiness.

Do not run CLadder 60 until all primary providers pass, the runtime roster and
pricing are frozen, the controller passes integration tests, and execution
preflight passes.

## 5. Controlled CLadder canary

Amendment 004 enables only the smoke controller. It does not change the
synthetic-smoke commands above and does not authorize calibration or locked
test. After both preflights and both dry-runs pass, the separately authorized
PowerShell command is:

```powershell
uv run --env-file .env python scripts/run_benchmark.py `
  --split smoke `
  --max-items 3 `
  --authorize-live-smoke
```

Expected run ID: `cladder-smoke-canary-3`. Expected artifact root:
`artifacts/runs/cladder-smoke-canary-3/`.

The canary passes only when its frozen manifest is complete, all 51 logical
calls complete with zero terminal errors, provider counts are 33/6/3/3/6 for
Groq/NVIDIA/Gemini/Cloudflare/OpenAI, no more than 204 transport attempts are
recorded, every response parses to `YES` or `NO`, exact model identity and
artifact integrity hold, and NVIDIA/secret/accounting checks remain valid.
Failure blocks smoke-60; no command chains or automatically starts smoke-60.
