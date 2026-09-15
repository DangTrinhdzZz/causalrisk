# Provider Synthetic-Smoke Runbook

**Status:** synthetic-smoke evidence retained; R6 CLadder canary requires separate authorization

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

For a new synthetic check, replace `openai` with exactly one active R6 provider:

- `groq`
- `cloudflare_workers_ai`

NVIDIA remains visible in `--list-candidates` as
`excluded_protocol_noncompliant`, and Mistral remains visible as
`excluded_unavailable`; the script rejects both for execution. Gemini is also excluded as
`excluded_transient_unavailable_r5` after four R5 HTTP 503/UNAVAILABLE attempts.

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
2. Run the two other active R6 providers one at a time.
3. Preserve every success and failure report locally.
4. Do not change a model ID in place after observing CLadder results. A candidate
   replacement must happen before benchmark execution and be documented.

NVIDIA's historical authorized synthetic smoke succeeded at
`max_output_tokens=1024`: `parsed=YES`, retries 0, input tokens 55, and output
tokens 245. It must not be repeated under the R6 protocol.

## 4. What a successful smoke does and does not prove

A pass confirms that authentication, exact model routing, the request shape,
response text extraction, deterministic YES/NO parsing, and available token
fields worked for that request. It does not establish causal-reasoning quality,
capability matching, stable quota, deterministic decoding, final pricing, or
benchmark readiness.

Do not run CLadder 60 until all primary providers pass, the runtime roster and
pricing are frozen, the controller passes integration tests, and execution
preflight passes.

## 5. Controlled CLadder canary R6

R1-R5 are frozen/failed and immutable. Amendment 009 is the user's explicit
post-stop availability remediation after R5 failed; no gold or accuracy was
used. R6 is today's final execution revision. Failure must stop; do not
automatically create R7, resume a terminal run, or start smoke-60.

After offline validation, a separate explicit authorization for one R6 canary
is required. The command below is documentation only and has not been run.
It loads only the four active environment variables from the local simple
KEY=VALUE file, without loading Gemini or NVIDIA credentials. Do not use
`uv --env-file .env` for R6, which would load excluded credentials too.

From the repository root, after authorization:

```powershell
Get-Content -LiteralPath .env | ForEach-Object {
  if ($_ -match '^\s*(GROQ_API_KEY|CLOUDFLARE_API_TOKEN|CLOUDFLARE_ACCOUNT_ID|OPENAI_API_KEY)\s*=\s*(.*)$') {
    $r6Value = $Matches[2].Trim().Trim('"').Trim("'")
    [Environment]::SetEnvironmentVariable($Matches[1], $r6Value, 'Process')
  }
}
uv run python scripts/run_benchmark.py `
  --split smoke `
  --max-items 3 `
  --authorize-live-smoke
```

Expected run ID: `cladder-smoke-canary-3-r6`; artifact root:
`artifacts/runs/cladder-smoke-canary-3-r6/`.
The canary requires exact frozen/failed R5 manifest, summary, and canonical
tree hashes recorded in Amendment 009, plus a clean committed tracked tree.

The canary must be frozen/complete, with all 51 calls successful, zero terminal
errors, and provider counts Groq 33, Cloudflare 12, OpenAI 6, Gemini 0, NVIDIA 0,
within 204 attempts. Calls must have valid YES/NO parsing, exact model identity,
complete observability, valid accounting, and intact artifacts. C5 comprises
five agents across three model families; each of its three Cloudflare critics
has a separate role, topology position, call ID, request, and output.

Smoke-60 remains blocked until that exact R6 canary passes. Calibration and
locked-test remain live-disabled. This documentation authorizes no live call.
