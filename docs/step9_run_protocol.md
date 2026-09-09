# Step 9 – Run Protocol and Execution Checklist

**Status:** protocol-level complete; no benchmark inference has been executed.

## 1. Purpose

This protocol defines how CLadder benchmark runs will later be executed, logged, validated, frozen, and reproduced. It converts the locked method definitions and provisional Model/API Roster into an auditable execution contract while keeping inference strictly separated from gold-aware scoring.

## 2. Scope and non-scope

This step governs the run lifecycle, model-facing input and output contracts, prompt versioning, record and event-log schemas, retry and invalid-output handling, artifact organization, validity checks, leakage prevention, reproducibility, and the execution checklist.

This step makes no API calls, executes no CLadder items, reports no model performance, and performs no final statistical analysis. It does not change sealed dataset splits or their protocol; any split change requires a separate documented amendment. Provider/model runtime verification remains pending.

## 3. Locked configurations

The configurations remain `A1`, `A3`, `A5`, `C1`, `C3`, and `C5` as defined in Step 7. Their numeric suffix is the exact maximum number of planned LLM calls per item under normal execution, not an approximate target. Retries are separately governed and accounted for by the retry protocol.

`C1` is the same execution as `A1`. It must be stored and analyzed as the shared `A1/C1` boundary condition, never rerun as an independent observation and never interpreted as a multi-agent effect. `A3` and `A5` are repeated independent calls to one model; `C3` and `C5` use their locked heterogeneous council topologies.

## 4. Run lifecycle

Each run must proceed in this order:

1. Verify and load the intended sealed split without exposing its membership outside the authorized runner.
2. Load an immutable configuration identified by `config_id`.
3. Load the exact prompt template and role templates by recorded version.
4. Construct a label-free model-facing input and validate it against the input contract.
5. During the later implementation stage, execute the specified model call or orchestration step only after its provider/model has passed smoke verification.
6. Save each raw provider response unchanged in the sealed run artifacts.
7. Apply deterministic parsing and normalization to obtain `YES`, `NO`, or `INVALID`.
8. Apply the existing retry policy only when its failure taxonomy declares the failure retry eligible.
9. Save the raw response, parsed answer, role/call metadata, token counts, cost, latency, and failure data for every attempt.
10. Validate record completeness, topology, budgets, parsing, retry behavior, and leakage controls.
11. Freeze the complete inference artifact before loading gold labels or computing accuracy.

Partially completed runs must retain completed records and an explicit terminal status; they must not be presented as complete runs.

## 5. Input contract

Model-facing input may contain only:

- the natural-language causal question;
- causal background and other context already intended for inference in the benchmark item;
- the versioned instruction requiring a final `YES` or `NO` answer; and
- the configuration-specific role instruction and permitted upstream evidence cards defined by the locked topology.

Model-facing input must not contain:

- a gold answer or label;
- dataset-supplied reasoning, ground truth, or answer explanation;
- evaluation-only query type, rung, graph, story, model, protected-family, or duplicate-group metadata;
- source identifiers or dataset IDs that could reveal answer-family structure;
- split name, membership, allocation metadata, or data from another split;
- retrieval results, web content, benchmark lookup results, or prior gold-aware outputs; or
- messages outside the information flow authorized for the configuration.

The controller may use a non-semantic anonymized item key for local bookkeeping, but it must not expose that key to a model unless operationally necessary and demonstrated not to encode protected structure. Query semantics may be inferred from the natural-language question; ground-truth query metadata is never supplied.

## 6. Output contract

The original raw model output must be stored unchanged. A deterministic, versioned parser may perform only the normalization allowed by the retry policy. Its `parsed_answer` is exactly one of `YES`, `NO`, or `INVALID`. A successfully completed item has a normalized `final_answer` of `YES` or `NO`; `INVALID` is a recorded terminal disposition, not a scoreable answer, and may remain only after non-retryable malformed output or exhaustion of an eligible retry path.

Parsing must not call an LLM, consult a gold label, infer what the model “probably meant,” or manually correct an answer. Provider-native structured output may be used when frozen in the configuration, but the unchanged response and every normalization action remain auditable.

## 7. Retry protocol

[The existing retry policy](retry_policy.md) is normative and applies unchanged. Its fixed setting is `max_retries = 3`: one initial attempt plus no more than three additional attempts. The project wrapper owns retries, provider SDK automatic retries are disabled, and every actual attempt counts toward calls, tokens, latency, and cost.

Retries are permitted only for the policy’s enumerated transient conditions: network/connection failure, timeout, HTTP 5xx, HTTP 429, or a successful response with empty content. Deterministic normalization is applied locally. Malformed JSON, schema failure, an invalid label, semantic conflict, suspected error, low confidence, or agent disagreement does not trigger a retry. Retry prompts and transport replays must never reveal the gold answer. Every attempt records its zero-based `attempt_index`, failure layer/code, eligibility decision, applied backoff, and resolution.

Retry exhaustion produces `method_failure` as defined by the retry policy. Authentication, quota, nonexistent-model, malformed-request, configuration-drift, and other run-blocking failures stop the run safely rather than causing substitution or extra calls.

## 8. Logging schema

Each inference/event record must contain the following fields. Fields unavailable from a provider are explicitly `null`, never silently replaced with zero.

| Field | Required meaning |
|---|---|
| `run_id` | Stable identifier for the complete run. |
| `item_id` | Stable anonymized local item key. |
| `split_name` | Sealed split reference; retained only in protected local artifacts. |
| `config_id` | Immutable method/configuration identifier. |
| `model_id` | Exact requested or provider-reported model identifier. |
| `provider` | Provider name and endpoint class where relevant. |
| `prompt_version` | Exact version/checksum of the effective prompt templates. |
| `attempt_index` | Zero-based initial/retry attempt index. |
| `role_name` | Single-agent, Analyst, specialist Critic, or Adjudicator role. |
| `raw_output` | Unmodified provider output, stored only in sealed artifacts. |
| `parsed_answer` | Deterministic parser result: `YES`, `NO`, or `INVALID`. |
| `final_answer` | Item-level normalized `YES`/`NO`, or `null` on incomplete/failed items. |
| `latency_ms` | End-to-end attempt latency in milliseconds. |
| `input_tokens` | Provider-reported or documented estimated input tokens. |
| `output_tokens` | Provider-reported or documented estimated output tokens. |
| `total_tokens` | Input plus output tokens under the declared accounting method. |
| `estimated_cost_usd` | Cost computed from the frozen pricing source/method. |
| `status` | Attempt, item, or run state using a controlled vocabulary. |
| `failure_type` | Canonical failure layer/code, or `null` on success. |
| `timestamp_utc` | Unambiguous UTC event timestamp. |
| `code_version` | Exact Git commit hash or equivalent immutable code version. |
| `notes` | Optional non-secret operational annotation; never gold-aware during inference. |

The implementation must also retain a unique call ID, retry eligibility, backoff duration, provider response ID and HTTP status when available, normalization actions, topology position, and inclusion flags required by the retry policy. Logs must never contain credentials or unredacted authorization data.

## 9. Artifact structure

Run artifacts are local, access-controlled, and ignored by version control. The implementation should use this structure or a schema-equivalent version fixed before execution:

```text
artifacts/
  runs/
    <run_id>/
      config.json
      manifest.json
      raw/
      parsed/
      logs/
      metrics_preview.json
```

- `config.json` is the immutable resolved configuration, including model/role mapping, decoding, budgets, retry-policy version, and prompt references.
- `manifest.json` records run identity, sealed-split reference and checksum, timestamps, code/environment versions, artifact checksums, and freeze state without copying gold labels.
- `raw/` preserves unchanged provider responses and request audit data with secrets redacted.
- `parsed/` contains deterministic label-free parsing results and normalization records.
- `logs/` contains per-call and terminal event records conforming to the logging schema.
- `metrics_preview.json` may contain operational completeness, token, latency, cost, and failure summaries only. It must contain no gold-aware accuracy result before the inference artifact is frozen.

The concrete artifact root must be added to `.gitignore` before implementation if it is not already ignored. Raw responses, split membership, and item-level answers must not be committed.

## 10. Run validity rules

A benchmark run is valid only when all of the following hold:

- the source split is sealed, audited, and checksum-verified;
- the configuration and role topology are locked;
- exact prompt versions are recorded;
- gold labels and protected metadata are inaccessible throughout inference;
- every provider/model endpoint used has passed the required smoke verification;
- both raw and parsed outputs are preserved for every completed response;
- configured calls and all retry attempts follow the locked budgets and retry policy;
- no answer is manually corrected, selectively rerun, or silently substituted;
- all required records pass schema and cross-artifact integrity validation; and
- inference artifacts are frozen before gold-aware scoring begins.

A failed condition blocks execution or invalidates the affected run. It must not be repaired in place after results are observed.

## 11. Leakage prevention

Gold labels are loaded only by a separate scoring process after inference artifacts have been frozen. The inference controller operates exclusively on label-free records and cannot import or query the gold-aware scoring layer. Logs or evidence shown to a model must never include previous scoring output, another item’s answer, or evaluation metadata.

Calibration data may support predeclared prompt and configuration decisions. Locked-test inputs and outputs must not be inspected or used for tuning before the configuration freeze, and locked-test labels remain unavailable until its complete inference artifact is frozen. Retrieval, browsing, external benchmark lookup, and cross-split context are prohibited during inference.

Any label exposure, protected-metadata exposure, unauthorized retrieval, cross-split contamination, or premature gold-aware scoring is a protocol violation and invalidates every affected run. The incident must be documented before any authorized rerun.

## 12. Reproducibility

- Use the fixed split-selection seed and sealed manifest checksums established by the split protocol. Record any other sampling or provider seed exactly; record `null` when a provider offers no effective seed.
- Version and checksum all base, role, retry, and formatting prompts.
- Store an immutable resolved configuration for every `config_id`.
- Record the exact Git commit, provider, endpoint, model ID, and UTC timestamps.
- Record the runtime, operating-system, SDK/dependency, and schema versions used by the implementation.
- Preserve request parameters, parser version, retry events, token-accounting method, and pricing version/source.
- Generate checksums for the complete run manifest and constituent artifacts.
- Once frozen, artifacts are immutable. Corrections create a new run ID and documented supersession record; they never overwrite the original.

Reproducibility metadata must not weaken secret handling or disclose sealed split membership in tracked files.

## 13. Execution checklist

### A. Before running the benchmark

- [ ] Confirm that every intended provider/model passed minimal smoke API verification.
- [ ] Verify the sealed split audit and manifest checksum.
- [ ] Freeze `config_id`, exact model/role mapping, prompt versions, parser/schema, decoding settings, call/token budgets, and retry-policy version.
- [ ] Record the Git commit and implementation environment.
- [ ] Confirm local credentials are available without printing or logging them.
- [ ] Disable SDK automatic retries and enable wrapper-level event accounting.
- [ ] Validate that model-facing records contain no labels, protected metadata, split metadata, retrieval, or web content.
- [ ] Create a unique `run_id` and protected artifact directory; confirm it is ignored by Git.
- [ ] Verify available quota and the predeclared monetary stopping limit.

### B. During benchmark execution

- [ ] Preserve identical benchmark input and comparable base prompting across matched configurations.
- [ ] Execute only the calls and information flow authorized by the locked configuration.
- [ ] Save every raw response before parsing and record every actual call.
- [ ] Apply only the deterministic parser and allowed normalization.
- [ ] Apply retries solely to eligible failures and log attempt index, classification, backoff, tokens, latency, and cost.
- [ ] Stop safely on authentication, quota, configuration drift, or another run-blocking failure.
- [ ] Do not inspect gold labels, score partial output, tune prompts, replace failed models, or manually repair answers.

### C. After benchmark execution

- [ ] Validate record schemas, item coverage, topology, budgets, retry events, and raw/parsed correspondence.
- [ ] Reconfirm that all completed answers normalize to `YES` or `NO` and terminal failures are explicit.
- [ ] Compute and record artifact checksums, completion state, and freeze timestamp.
- [ ] Make the inference artifact immutable before loading labels.
- [ ] Run scoring only through the separate gold-aware scorer after freeze.
- [ ] Retain failures and retries in all operational and cost accounting.
- [ ] Produce only approved aggregate reports; keep item-level records and membership sealed.
- [ ] Document invalidations, supersessions, or protocol amendments without overwriting frozen artifacts.

## 14. Final status

**Step 9 is completed at protocol level. No benchmark inference has been executed in this step.** Implementation, provider/model smoke verification, configuration freeze, and all benchmark runs remain pending.
