# Amendment 006 - R3 Output-Cap Remediation

**Decision date:** 2026-09-14

**Status:** superseded by Amendment 007 after the terminal R3 canary failure

## R2 terminal result and immutable lineage

The one authorized R2 canary, `cladder-smoke-canary-3-r2`, is frozen with
`run_status=failed`: 10 of 51 logical calls completed in 11 transport attempts.
Its terminal `C3_COUNCIL_V1` NVIDIA Critic attempt returned HTTP 200 with
`finish_reason=length` and 1,024 output tokens, exactly the configured cap, and
was correctly classified as `configuration/output_cap_truncation`.

R2 remains immutable and cannot be resumed, overwritten, merged, or reused.
R3 canary eligibility requires that exact frozen/failed artifact with manifest
SHA-256 `c8b78f1ef5f853e0443cb88a6d9d596446f1490d288cdd3c5a085b035744b4ce`
and artifact-tree SHA-256
`53aa427f2941b106018bf818971985d665a7c59ee94a185277b2ddf01943422d`.
The label-free forensic record is `r2_operational_canary_forensic_aggregate.json`.

## R3 change

Revision `cross_split_execution_r3` changes only `max_output_tokens`: every
call-producing Analyst, Critic, and Adjudicator role now uses 2,048. A1/A3/A5
were already 2,048; C3 and C5 roles are synchronized to that cap. C1 still
mirrors A1 and creates zero calls. Output-cap truncation remains terminal even
when truncated text contains `YES` or `NO`.

Prompts, provider/model roster, topology, reasoning settings, parser,
temperature, pricing, pacing, retry and terminal-error ceilings, and call
counts are unchanged. Amendment 003 continues to require NVIDIA normalized
list cost and actual charge to remain `null` with `billing_mode=free_prototype`.

| Phase | Fixed R3 run ID | Logical calls | Attempt ceiling | Required predecessor |
|---|---|---:|---:|---|
| Canary | `cladder-smoke-canary-3-r3` | 51 | 204 | exact frozen/failed R2 canary |
| Smoke | `cladder-smoke-60-r3` | 1,020 | 4,080 | frozen/complete R3 canary, 51/51, zero error |
| Calibration | `cladder-calibration-300-r3` | 5,100 | 20,400 | reviewed frozen/complete R3 smoke |
| Locked test | `cladder-locked-test-600-r3` | 10,200 | 40,800 | completed R3 calibration, scoring, and final freeze |

Only smoke remains enabled by split policy, and every live smoke invocation
still requires `--authorize-live-smoke`. This amendment does not authorize the
R3 canary or any other live call. A failed R3 canary blocks smoke-60 and never
starts it automatically; calibration and locked test remain disabled.
