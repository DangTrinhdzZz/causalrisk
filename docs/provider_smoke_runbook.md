# Provider Synthetic-Smoke Runbook

**Status:** synthetic-smoke evidence retained; R5 CLadder canary requires separate authorization

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

For a new synthetic check, replace `openai` with exactly one active R5 provider:

- `groq`
- `gemini`
- `cloudflare_workers_ai`

NVIDIA remains visible in `--list-candidates` as
`excluded_protocol_noncompliant`, and Mistral remains visible as
`excluded_unavailable`; the script rejects both for execution.

Mistral's historical check returned HTTP 429,
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
2. Run the three other active R5 providers one at a time.
3. Preserve every success and failure report locally.
4. Do not change a model ID in place after observing CLadder results. A candidate
   replacement must happen before benchmark execution and be documented.

NVIDIA's historical authorized synthetic smoke succeeded at
`max_output_tokens=1024`: `parsed=YES`, retries 0, input tokens 55, and output
tokens 245. It must not be repeated under the final R5 protocol.

## 4. What a successful smoke does and does not prove

A pass confirms that authentication, exact model routing, the request shape,
response text extraction, deterministic YES/NO parsing, and available token
fields worked for that request. It does not establish causal-reasoning quality,
capability matching, stable quota, deterministic decoding, final pricing, or
benchmark readiness.

Do not run CLadder 60 until all primary providers pass, the runtime roster and
pricing are frozen, the controller passes integration tests, and execution
preflight passes.

## 5. Controlled CLadder canary R5

The R1, R2, R3, and R4 canary runs are frozen and failed. Do not resume,
overwrite, or reuse them. Amendment 008 defines a separate final R5 run and
enables only the smoke controller; it does not change the active-provider
synthetic-smoke commands above and
does not authorize calibration or locked test. After structural and smoke
execution preflight plus the R5 canary dry-run pass, the command that
would require a new, separate authorization is:

```powershell
uv run --env-file .env python scripts/run_benchmark.py `
  --split smoke `
  --max-items 3 `
  --authorize-live-smoke
```

Expected run ID: `cladder-smoke-canary-3-r5`. Expected artifact root:
`artifacts/runs/cladder-smoke-canary-3-r5/`.

The canary passes only when its frozen manifest is complete, all 51 logical
calls complete with zero terminal errors, provider counts are 33/9/3/6/0 for
Groq/Cloudflare/Gemini/OpenAI/NVIDIA, no more than 204 transport attempts are
recorded, every response parses to `YES` or `NO`, exact model identity and
artifact integrity hold, no NVIDIA request or credential load occurs, and
secret/accounting checks remain valid.
Failure blocks smoke-60; nothing chains to or automatically starts smoke-60.
No R5 live call is authorized merely because this command is documented. A
terminal canary failure requires reassessment; it must not start smoke-60 or
create an automatic R6.
