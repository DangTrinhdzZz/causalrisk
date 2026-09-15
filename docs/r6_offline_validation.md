# R6 Offline Validation Record

Date: 2026-09-15. Base commit: `ff197cc27cbf3fa672c746a1ec9546518d939ba7`.
The atomic R6 commit containing this report is the prepared execution revision;
no live run is included and no push is authorized.

## Final checks

Validation used `UV_OFFLINE=true` and a temporary Python audit guard outside
the repository. The guard rejected socket connections/DNS, access to source or
gold data, and writes to repository runtime artifacts. Provider executions in
unit tests use synthetic items and fake transports in temporary test directories.
No live HTTP request, benchmark scoring, or real gold-label read occurred.

| Command | Final result |
|---|---|
| `uv run pytest` | PASS: 161 tests (27.49 s) |
| `uv run ruff check .` | PASS: all checks |
| `uv run python scripts/validate_preflight.py` | PASS: 20 checks |
| `uv run python scripts/validate_preflight.py --execution --split smoke` | PASS: 25 checks |
| `uv run python scripts/run_benchmark.py --dry-run --split smoke --max-items 3` | PASS |
| `uv run python scripts/run_benchmark.py --dry-run --split smoke` | PASS |
| `uv run python scripts/run_benchmark.py --dry-run --split calibration` | PASS |
| `uv run python scripts/run_benchmark.py --dry-run --split locked_test` | PASS |
| `git -c core.safecrlf=false diff --check` | PASS |

The final Git whitespace check is repeated after adding this report and staging
the reviewed files. PowerShell parsed the future canary command successfully;
the command was not executed.

Smoke execution preflight accepts all three active providers and verifies exact
R5 manifest/tree/summary lineage. Capacity checks pass with the existing
RPD/TPD unknown warnings for Groq, Cloudflare, and OpenAI; no account limits,
full-run costs, or actual charges were invented. No quota or live availability
check was performed.

## R5 immutable lineage

| Artifact | SHA-256 |
|---|---|
| Manifest | `60475269e6b507c891b16ef02a44ba2672ba0683d7b0d64975ef9be8b4f246f6` |
| Canonical artifact tree | `2ef7b14410349942a63cb4400bb26e347b57a961400788d83ddd1e1d5c5468d0` |
| Summary | `81b1db961d00368f755a554047ef1e596186941a4f4733af1f6b9bcfcdde37a1` |

R5 has 74 files, 30 successful calls, one terminal failure, and 34 attempts.
Its failure chain contains exactly attempts 0-3, all HTTP 503/UNAVAILABLE.
The label-free [aggregate](r5_operational_canary_forensic_aggregate.json) records
the operational metadata.

The complete existing `artifacts/runs` tree remains byte-identical at
`3ad205082c9f96ff22def825f25891de5b003d34ba73755850be8d66eeedeb98`.
No R6 runtime directory was created. R1-R5 remain immutable and cannot be
resumed, overwritten, deleted, merged, scored, or counted as benchmark results.
The six untracked patches and README.pdf remain byte-identical and untracked.
All existing inference JSON, prompt/parser/retry/schema/topology files, and
the pricing snapshot also remain byte-identical.

## Exact R6 counts

| Phase | Calls | Maximum attempts | Groq | Cloudflare | OpenAI | Gemini | NVIDIA |
|---|---:|---:|---:|---:|---:|---:|---:|
| Canary-3 | 51 | 204 | 33 | 12 | 6 | 0 | 0 |
| Smoke-60 | 1,020 | 4,080 | 660 | 240 | 120 | 0 | 0 |
| Calibration-300 | 5,100 | 20,400 | 3,300 | 1,200 | 600 | 0 | 0 |
| Locked-test-600 | 10,200 | 40,800 | 6,600 | 2,400 | 1,200 | 0 | 0 |

| Phase | A1 | A3 | A5 | C1 | C3 | C5 |
|---|---:|---:|---:|---:|---:|---:|
| Canary-3 | 3 | 9 | 15 | 0 | 9 | 15 |
| Smoke-60 | 60 | 180 | 300 | 0 | 180 | 300 |
| Calibration-300 | 300 | 900 | 1,500 | 0 | 900 | 1,500 |
| Locked-test-600 | 600 | 1,800 | 3,000 | 0 | 1,800 | 3,000 |

All phases retain 17 calls/item and C1 aliases A1 without a new call.
C3 is Groq analyst, Cloudflare critic, OpenAI adjudicator. C5 is five agents
across three model families: Groq analyst, three independent Cloudflare critics,
and OpenAI adjudicator. Tests verify separate critic prompts/call IDs/positions,
distinct outputs delivered to the adjudicator, and no critic-output reuse.

## Pricing and gates

Normalized pricing covers **3/3 active provider/model pairs (100%)** using the
unchanged existing prices. Gemini and NVIDIA remain historical entries only.
Actual charge is separate and nullable; it is not normalized cost. Realized
call/token pricing coverage depends on reported usage and is not measured by
this offline preparation.

The R6 canary dry-run verifies its R5 predecessor. Smoke-60's predecessor gate
is false because no R6 canary has run. Calibration and locked-test are still
live-disabled. Tests also reject policy overrides for fixed run IDs, forged
verified lineage, changed R5 bytes/hashes, and missing/failed/incomplete R6
canaries. The strict parser, prompt and retry checksums, 2048-token cap,
temperature, zero-terminal-error policy, and same-provider retries remain fixed.
No fallback provider is used.

The sole remaining protocol authorization before a live R6 canary is explicit
user approval for that one run. The exact future PowerShell command, which
loads only active credentials, is in the
[runbook](provider_smoke_runbook.md#5-controlled-cladder-canary-r6).
R6 is today's final revision. A failure must stop; no automatic R7.

## Files changed

- `README.md`
- `configs/methods/A1_SINGLE_V1.yaml`
- `configs/methods/A3_SINGLE_V1.yaml`
- `configs/methods/A5_SINGLE_V1.yaml`
- `configs/methods/C1_BOUNDARY_V1.yaml`
- `configs/methods/C3_COUNCIL_V1.yaml`
- `configs/methods/C5_COUNCIL_V1.yaml`
- `docs/README.md`
- `docs/amendment_009_r6_post_stop_availability_remediation.md`
- `docs/day2_runtime_readiness.md`
- `docs/provider_smoke_runbook.md`
- `docs/r5_operational_canary_forensic_aggregate.json`
- `docs/r6_offline_validation.md`
- `scripts/plan_capacity.py`
- `src/causalrisk/capacity.py`
- `src/causalrisk/config.py`
- `src/causalrisk/controller.py`
- `src/causalrisk/dry_run.py`
- `src/causalrisk/execution.py`
- `src/causalrisk/execution_policy.py`
- `src/causalrisk/lineage.py`
- `src/causalrisk/preflight.py`
- `src/causalrisk/pricing.py`
- `src/causalrisk/providers/candidates.py`
- `tests/unit/test_config.py`
- `tests/unit/test_controller.py`
- `tests/unit/test_dry_run.py`
- `tests/unit/test_execution_policy.py`
- `tests/unit/test_execution_r2.py`
- `tests/unit/test_execution_r6.py`
- `tests/unit/test_live_provider_adapters.py`
- `tests/unit/test_preflight.py`
- `tests/unit/test_pricing.py`
