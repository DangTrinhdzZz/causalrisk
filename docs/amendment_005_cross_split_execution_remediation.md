# Amendment 005 - R1 Remediation and Cross-Split Execution Revision R2

**Decision date:** 2026-09-12

**Status:** offline validation passed; R2 canary requires separate live authorization

**Supersedes:** Amendment 004 execution revision; Amendment 003 pricing waiver remains in force

## 1. R1 disposition and evidence boundary

The first operational canary, `cladder-smoke-canary-3` (R1), is a terminal,
failed run. It remains frozen and must never be resumed, overwritten, repaired
in place, or treated as a benchmark result. Its complete artifact-tree SHA-256
is `ef651c3cbda820bb39d67188f5532321206544b2fe68594542730b115959b69a`
and its manifest SHA-256 is
`1b41a9e78f999f873084ab828cecdc385e4ce54028c4f5f04e53ea6045040637`.
R2 preflight verifies both values before a successor canary is eligible.

The committed forensic record is
`docs/r1_operational_canary_forensic_aggregate.json`. It contains operational
aggregates only: no raw prompt, raw model output, item identifier, split
membership, gold label, correctness calculation, or accuracy claim.

R1 completed 27 of 51 logical calls. All 44 transport attempts were to Groq;
16 returned HTTP 429. The terminal C3 Analyst attempt returned HTTP 200 but
was classified `configuration/output_cap_truncation` at the configured
768-token output cap. This is the remediation basis, not evidence about model
quality. None of the 27 successful R1 outputs may be spliced into, merged
with, or otherwise reused by R2.

## 2. Narrow behavioral remediation

The Analyst output cap changes from 768 to 2,048 tokens in A1, A3, A5, C3,
and C5. C1 remains an exact A1 alias and therefore mirrors A1's config but
schedules no call. No other role cap, topology, prompt text, model assignment,
reasoning setting, parsing rule, or retry ceiling changes.

Any response classified as length/output-cap truncation is terminal, even if
its visible text contains a parseable `YES` or `NO`. Such a response is never
accepted as a completed logical call. Raising a non-binding output ceiling is
an operational completeness repair based on the canary; it is not accuracy
optimization. Actual token usage remains measured in separate nullable fields.

Groq's minimum interval between transport starts changes from 2 to 10 seconds
for smoke, calibration, and locked-test execution. Other provider intervals
remain unchanged. Retry-After is honored with bounded jitter under the frozen
retry policy; there are still at most three retries after the initial attempt.
An HTTP 429 is a transient transport outcome and not evidence that the static
schedule itself satisfies account limits.

## 3. Provider-limit snapshot and capacity gate

`configs/provider_limits_2026-09-12.json` is the versioned account-limit
snapshot. Every provider has nullable `RPM`, `TPM`, `RPD`, and `TPD` fields
plus a source note. An unknown account limit is recorded as `null`; it is
neither zero nor unlimited. Public generic limits are not account truth.

Offline preflight computes provider logical calls, the four-attempt transport
ceiling, minimum pacing floor, token projections only where empirical coverage
is adequate, and normalized cost only where both pricing and required usage
are present. A known projected daily-limit exceedance blocks execution unless
a declared batching/pause plan keeps each account window within its known
limit. Unknown limits remain explicit warnings and unknown estimates remain
`null`.

## 4. Cross-split engine and fixed identities

Execution revision `cross_split_execution_r2` uses one split-general engine
with the following immutable plans. C1 is always a zero-call alias of A1.

| Plan | Run ID | Items | Logical calls | Attempt ceiling |
|---|---|---:|---:|---:|
| R2 canary | `cladder-smoke-canary-3-r2` | 3 | 51 | 204 |
| Smoke | `cladder-smoke-60-r2` | 60 | 1,020 | 4,080 |
| Calibration | `cladder-calibration-300-r2` | 300 | 5,100 | 20,400 |
| Locked test | `cladder-locked-test-600-r2` | 600 | 10,200 | 40,800 |

The logical-call allocation per item is 11 Groq, 2 NVIDIA NIM, 1 Gemini,
1 Cloudflare Workers AI, and 2 OpenAI calls. Method allocation per item is
A1=1, A3=3, A5=5, C1=0, C3=3, and C5=5. Logical call identifiers, item order,
method order, and topology position are deterministic.

The manifest freezes the code commit, execution revision, view schema and
checksum, source-manifest checksum, config checksums, prompt checksums, pricing
snapshot, provider-limit snapshot, topology, run plan, and predecessor
evidence. A run from another execution revision or with any lineage drift
cannot be resumed.

## 5. Authorization and phase gates

Each split has an exact, non-interchangeable live acknowledgement:

- smoke: `--authorize-live-smoke`;
- calibration: `--authorize-live-calibration`;
- locked test: `--authorize-live-locked-test`.

All dry-runs remain available without authorization and must make no HTTP
request or runtime-artifact write. Live execution is currently policy-enabled
only for smoke. Calibration and locked-test live execution fail closed even if
their acknowledgement flags are supplied; a later amendment must enable each
phase. The six method configs remain `execution_enabled: true`, but that field
does not override split policy, predecessor gates, preflight, or explicit live
authorization.

The mandatory sequence is:

1. separately authorize and pass the R2 three-item canary;
2. review and separately authorize smoke-60;
3. approve a calibration-enablement amendment;
4. complete calibration, scoring, operational review, and final configuration
   freeze;
5. approve a locked-test-enablement amendment;
6. execute locked-test inference under its distinct authorization.

No phase automatically starts its successor. A failed R2 canary blocks
smoke-60. R1 does not satisfy the R2 canary pass gate.

After calibration begins, any behavioral change supersedes the entire affected
calibration run; selective reuse is prohibited. Locked-test execution must use
the exact final frozen commit. Prompts, configs, and models cannot change once
locked inference begins, locked gold stays closed until inference is complete
and frozen, and selective reruns are prohibited. A planned same-run resume is
allowed; a terminal protocol failure invalidates the affected locked run.

## 6. Label-free views

Each split is materialized into an ignored, versioned inference view. Every
model-facing item has exactly `item_id`, `background`, `given_info`, and
`question`. Answer, label, ground truth, reasoning, rung, query type, and split
membership are forbidden. The item ID remains controller metadata and is not
rendered into a model prompt. Rung is used only by the controller-side smoke
canary selector and is stored in a separate ignored sidecar, never in the
inference view or prompt.

Preflight verifies the view schema version, source-manifest checksum, view
checksum, sidecar checksum where applicable, exact record count, and exact
field set before constructing adapters.

## 7. Artifact lifecycle and resumable batches

R2 states are `in_progress`, `paused`, `complete`, and `failed`. A planned
`--max-new-items N` boundary atomically changes an otherwise valid run to
`paused`; only `paused` is open for deterministic continuation. `complete` and
`failed` are terminal and frozen. Items execute item-major, and resume skips
every already-complete logical call without contacting its provider again.

Attempt journals are written atomically before transport. Call records,
summaries, manifests, retry histories, and state transitions are atomic. An
ambiguous in-flight attempt, orphan record, temporary-file residue, unexpected
artifact, predecessor failure, or lineage drift blocks resume. R2 never
deletes or overwrites a prior run to make a gate pass.

## 8. Observability, secrets, and accounting

Successful calls and terminal truncation failures retain nullable finish
reason, latency, input/output/reasoning/cached-input token counts, HTTP status,
provider response ID, safe allowlisted rate-limit headers, and complete retry
history when providers expose them. Missing metadata stays `null`, never zero.
Credentials, authorization values, request headers, raw credential material,
and unsafe response metadata are prohibited from artifacts.

`normalized_list_cost_usd` and `actual_charge_usd` remain distinct nullable
fields. Normalized cost is computed only from sufficient provider-reported
usage and the frozen price table. Actual charge is populated only from direct
provider billing evidence, not inferred from list price or free-tier status.

Amendment 003 remains binding for NVIDIA NIM:
`normalized_list_cost_usd=null`, `actual_charge_usd=null`, and
`billing_mode=free_prototype`. NVIDIA must never receive a zero price or proxy
price. Mistral remains `excluded_unavailable`; NVIDIA NIM remains the primary
skeptical Critic.

## 9. R2 canary pass gate

The successor canary is not authorized by this amendment alone. When separately
authorized, it passes only if the command exits successfully and the frozen
artifact proves all of the following:

1. run ID `cladder-smoke-canary-3-r2`, execution revision R2, and exact lineage;
2. `run_status=complete`, 51 of 51 logical calls, zero terminal errors, and no
   ambiguous in-flight attempt;
3. provider calls Groq 33, NVIDIA NIM 6, Gemini 3, Cloudflare 3, and OpenAI 6;
4. between 51 and 204 transport attempts, unique logical call IDs, and no C1
   transport call;
5. every accepted result normalizes to `YES` or `NO` and exact provider/model
   identity matches the frozen roster;
6. complete attempt/call artifacts and schema-valid retry, latency, finish,
   token, response-ID, HTTP, and cost metadata with nullable fields preserved;
7. no secret or authorization metadata and exact NVIDIA symbolic-null pricing.

Any failure leaves the artifact intact for diagnosis and blocks smoke-60 until
an explicit review and new decision. No automatic canary rerun is authorized.
