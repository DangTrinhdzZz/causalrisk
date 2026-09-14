# Amendment 007 - R4 NVIDIA Thinking Control

**Decision date:** 2026-09-14

**Status:** superseded by Amendment 008 after the terminal R4 canary failure

## R3 terminal result and immutable lineage

The one authorized R3 canary, `cladder-smoke-canary-3-r3`, is frozen with
`run_status=failed`: 10 of 51 logical calls completed in 12 transport attempts.
The terminal `C3_COUNCIL_V1` NVIDIA Critic call timed out once, then returned
HTTP 200 with `finish_reason=length` and 2,048 output tokens, exactly the R3
cap. The truncation remained terminal.

R3 cannot be resumed, overwritten, merged, or reused. R4 canary eligibility
requires that exact frozen/failed artifact with manifest SHA-256
`72db02ebc08a657911928ef60812da57ef3c493b2f3e0143de02ec3557df8f3e`
and artifact-tree SHA-256
`0dccb0852643e0522b1dcd3ecc1113a5170273d97a7e963923e89c80eb08cd04`.

## R4 change

Revision `cross_split_execution_r4` changes only the NVIDIA NIM request
payload. NVIDIA receives this top-level field:

```json
{"chat_template_kwargs": {"enable_thinking": false}}
```

It is not wrapped in `extra_body`, no `reasoning_budget` is sent, and Groq and
all other providers receive neither field. NVIDIA non-thinking mode is an
operational-completeness setting: the model must still produce the complete
CRITIC CARD and finish with `YES` or `NO`; its skeptical-Critic role is
unchanged.

All call-producing roles remain capped at 2,048. Prompts, provider/model
roster, topology, reasoning settings for other providers, temperature, pacing,
timeout, retry policy, parser, pricing, and call counts are unchanged.

| Phase | Fixed R4 run ID | Logical calls | Attempt ceiling | Required predecessor |
|---|---|---:|---:|---|
| Canary | `cladder-smoke-canary-3-r4` | 51 | 204 | exact frozen/failed R3 canary |
| Smoke | `cladder-smoke-60-r4` | 1,020 | 4,080 | frozen/complete R4 canary, 51/51, zero error |
| Calibration | `cladder-calibration-300-r4` | 5,100 | 20,400 | reviewed frozen/complete R4 smoke |
| Locked test | `cladder-locked-test-600-r4` | 10,200 | 40,800 | completed R4 calibration, scoring, and final freeze |

Only smoke remains enabled by split policy, and live smoke still requires
`--authorize-live-smoke`. This amendment authorizes no live call. A failed R4
canary blocks smoke-60 and never starts it automatically; calibration and
locked test remain disabled.
