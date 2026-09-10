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

Replace `openai` with exactly one of:

- `groq`
- `mistral`
- `gemini`
- `cloudflare_workers_ai`
- `nvidia_nim`

The script prints and stores only operational metadata. It does not print the
credential, prompt, raw response, HTTP headers, or provider error body. Reports
are written under ignored `artifacts/smoke/` and retain
`runtime_verified: false`; human review and the remaining execution gates are
still required.

## 3. Required order

1. Run OpenAI first to verify the newly amended Adjudicator path.
2. Run the four other primary-role providers one at a time.
3. Run NVIDIA only as a reserve-candidate check; it is not part of the primary
   C5 call budget.
4. Preserve every success and failure report locally.
5. Do not change a model ID in place after observing CLadder results. A candidate
   replacement must happen before benchmark execution and be documented.

## 4. What a successful smoke does and does not prove

A pass confirms that authentication, exact model routing, the request shape,
response text extraction, deterministic YES/NO parsing, and available token
fields worked for that request. It does not establish causal-reasoning quality,
capability matching, stable quota, deterministic decoding, final pricing, or
benchmark readiness.

Do not run CLadder 60 until all primary providers pass, the runtime roster and
pricing are frozen, the controller passes integration tests, and execution
preflight passes.
