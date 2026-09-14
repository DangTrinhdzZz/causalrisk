# Amendment 008 - R5 Final Operational Compatibility Roster

**Decision date:** 2026-09-14

**Status:** offline validated; R5 live canary requires separate authorization

## R4 result and immutable lineage

The one authorized R4 canary, `cladder-smoke-canary-3-r4`, is frozen with
`run_status=failed`: 10 of 51 logical calls completed in 11 transport attempts.
Its terminal C3 NVIDIA Critic call returned HTTP 200 with `finish_reason=stop`,
but its output had no unambiguous terminal `YES` or `NO`; the strict parser
correctly returned `output/invalid_label`. No gold or accuracy was inspected.

R4 is an operational compatibility record, not a benchmark result. It cannot
be resumed, overwritten, merged, or reused. R5 canary eligibility requires the
exact frozen/failed R4 artifact with manifest SHA-256
`6880469577b5b5df3b69fc2088f5f82f6d9232f81d577c31418f5232bd153a5c`
and artifact-tree SHA-256
`672f430dc96d409e9ac86000a3727a073a343c6f8297d1760fbaed7dea2c7a45`.
R1-R4 remain immutable operational failures and are not benchmark results.

## Final R5 roster

The exact NVIDIA Nemotron route is permanently excluded from execution as
`excluded_protocol_noncompliant`: R2 ended at the 1,024-token cap; R3 timed out
once and then ended at the 2,048-token cap; R4 completed HTTP transport with a
stop finish but produced an ambiguous invalid label. This is an operational
protocol-compatibility decision, not a conclusion about model quality. R5 does
not load an NVIDIA credential or create an NVIDIA request. There will be no
further cap, timeout, thinking-mode, retry-format, repair-model, or parser
remediation for this route.

R5 assigns C3 Analyst/Critic/Adjudicator to Groq, Cloudflare Qwen, and OpenAI.
C5 assigns Analyst to Groq, Semantic/Query Critic to Gemini, both
Graph/Identification and Formal/Numerical Critics to Cloudflare Qwen, and
Adjudicator to OpenAI. The two Cloudflare critics are independent logical calls
at distinct role/topology positions. C5 is therefore a five-agent, four-family,
role-heterogeneous council; it is not five independent provider/model families.
C1 continues to alias A1 and creates no additional call.

Prompts and checksums, the strict parser, temperature, 2,048-token output caps,
retry policy, topology, call budget, label-free views, item-major order, atomic
writes, resume rules, and split gates remain unchanged.

## Fixed identities, gates, and capacity

| Phase | Fixed R5 run ID | Logical calls | Attempt ceiling | Required predecessor |
|---|---|---:|---:|---|
| Canary | `cladder-smoke-canary-3-r5` | 51 | 204 | exact frozen/failed R4 canary above |
| Smoke | `cladder-smoke-60-r5` | 1,020 | 4,080 | frozen/complete R5 canary, 51/51, zero error |
| Calibration | `cladder-calibration-300-r5` | 5,100 | 20,400 | reviewed frozen/complete R5 smoke |
| Locked test | `cladder-locked-test-600-r5` | 10,200 | 40,800 | completed R5 calibration, scoring, and final freeze |

Per item the active allocation is Groq 11, Cloudflare Workers AI 3, Gemini 1,
and OpenAI 2. Thus canary counts are 33/9/3/6; smoke counts are
660/180/60/120; calibration counts are 3,300/900/300/600; and locked-test
counts are 6,600/1,800/600/1,200, in that provider order. NVIDIA has zero R5
calls.

All active R5 provider/model pairs have official normalized pricing, so
normalized pricing coverage is 100% when provider usage is complete. Actual
account charge remains a separate nullable field. Amendment 003 and its
symbolic-null NVIDIA values remain binding historical accounting for R1-R4 but
are not active R5 pricing inputs.

Only smoke is enabled by split policy, and live smoke still requires
`--authorize-live-smoke`. This amendment authorizes no live call. A failed R5
canary blocks smoke-60 and triggers reassessment; it must not automatically
start smoke-60 or create an R6. Calibration and locked test remain disabled.
