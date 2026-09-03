# Reproducible Failure-Handling and Retry Protocol

## 1. Purpose and governing principle

This document defines the failure-handling and retry protocol for the LLM causal-reasoning multi-agent benchmark. Its governing principle is that retries address only transient call-delivery or empty-response failures; they must never become a mechanism for improving, repairing, or selectively replacing substantive model answers. Every benchmark configuration must apply this policy identically so that completion, accuracy, latency, token use, and cost remain reproducible and comparable.

## 2. Retry budget and retry-controller ownership

The project wrapper is the sole retry controller. SDK-level automatic retries must be disabled or configured as zero so that every generated call is observable and subject to the same accounting rules.

The fixed retry budget is `max_retries = 3`. Thus, an item may receive one initial attempt and no more than three additional attempts:

\[
\mathrm{max\_attempts} = 1 + \mathrm{max\_retries} = 4.
\]

For eligible failures, the wrapper waits 1 second before the first retry, 2 seconds before the second retry, and 4 seconds before the third retry. For HTTP 429 responses, it must respect a provider-supplied `Retry-After` value when present. The applied delay must be logged. No attempt beyond the fourth call is permitted.

## 3. Failure taxonomy and decision table

Failures are classified before any retry decision. The following table is normative.

| Failure condition | Failure layer or code | Retry eligible | Required action |
|---|---|---:|---|
| Transient network or connection failure | transport | Yes | Retry within the fixed budget and backoff schedule. |
| Timeout | transport/timeout | Yes | Retry within the fixed budget and backoff schedule. |
| HTTP 5xx | provider/http_5xx | Yes | Retry within the fixed budget and backoff schedule. |
| HTTP 429 rate limit | provider/http_429 | Yes | Respect `Retry-After` when provided; otherwise use the fixed backoff schedule. |
| Successful HTTP response with empty content | response/empty_content | Yes | Retry within the fixed budget and backoff schedule. |
| Invalid API key or authorization error | configuration/authentication | No | Stop the run safely and preserve completed records. |
| Malformed request | configuration/malformed_request | No | Stop or correct the configuration outside the run; do not retry the item. |
| Nonexistent model | configuration/nonexistent_model | No | Stop the run safely and preserve completed records. |
| Quota or budget exhaustion | configuration/quota_exhaustion | No | Stop the run safely and preserve completed records. |
| Context-window overflow | configuration/context_overflow | No | Record the failure without retry. |
| Output truncation caused by the configured output cap | configuration/output_cap_truncation | No | Record the failure without retry. |
| Safety refusal | response/safety_refusal | No | Preserve the refusal as the terminal response; do not retry. |
| Configuration drift | configuration/configuration_drift | No | Stop the run safely and preserve completed records. |
| Dataset or reference-label defect | data/data_validation_failure | No | Quarantine the item for every configuration. |
| Suspected wrong answer, low confidence, agent disagreement, invalid causal reasoning, or semantic contradiction | semantic or protocol | No | Record the applicable terminal failure; never seek a replacement answer. |

Only the five explicitly eligible classes may consume the retry budget. An eligible failure that persists through all four attempts results in `method_failure` for the item. Ineligible failures must not generate another LLM call.

## 4. Output-format and schema handling

Provider-native structured outputs or JSON Schema must be used when supported. After receipt, the wrapper may apply only deterministic local normalization that leaves semantic content unchanged:

1. trim surrounding whitespace;
2. remove a Markdown code fence;
3. extract one unambiguous JSON object; and
4. canonicalize an already-recognizable label, such as `yes` to `YES`.

No LLM may be called to repair formatting. The fixed setting is `llm_format_repair_attempts = 0`.

After permitted normalization, malformed JSON must be recorded as `parse_failure`; a structured value that violates the required schema must be recorded as `schema_failure`; an unrecognized response label must be recorded as `invalid_label`; and internally incompatible semantic fields must be recorded as `semantic_conflict`. These failures are not retry eligible. Normalization steps and the resulting disposition must be logged so that parsing decisions are auditable.

## 5. Logical, causal, and multi-agent protocol failures

Retries must not be triggered by suspected wrong answers, low confidence, disagreement between agents, logically invalid causal reasoning, or semantic contradictions. Such outcomes are part of the evaluated method behavior rather than transient infrastructure faults.

For multi-agent methods, the declared topology and deliberation schedule are immutable during a run. A failed agent must not be replaced; the number of agents must not be reduced; extra agents must not be added; and extra deliberation rounds must not be introduced. Calls omitted because of a terminal protocol failure must remain omitted and be represented explicitly in the record. A `semantic_conflict` or other logical or causal failure is recorded at the appropriate layer without an LLM repair or adjudication call beyond the method's predeclared protocol.

## 6. Dataset, scoring, and configuration-integrity failures

A dataset defect, including an invalid item or unreliable reference label, is a `data_validation_failure`. The affected item must be quarantined consistently for every benchmark configuration. An LLM must never be retried to compensate for or solve a dataset defect.

Invalid API keys, authorization errors, malformed requests, nonexistent models, quota or budget exhaustion, and configuration drift indicate that the intended run cannot continue faithfully. They are run-blocking configuration, authentication, or quota failures. The runner must stop safely, preserve all completed records, and leave unfinished items unscored rather than treating them as wrong answers. Context-window overflow and output truncation caused by the configured output cap are also non-retryable configuration-bound outcomes and must be recorded without changing the configuration mid-run.

## 7. Accounting and denominator rules

Every call generated by a retry counts toward call volume, token use, latency, and cost. If all eligible retries are exhausted, the item receives final status `method_failure`. It remains in the denominator of both end-to-end accuracy and completion rate; it contributes no correct answer and is not completed successfully.

Run-blocking failures are treated differently from item-level method failures. Completed records remain valid, but unfinished items are not classified as wrong answers and are excluded from item-level scoring denominators because their intended calls were not completed. Quarantined `data_validation_failure` items are excluded consistently for every configuration before denominators are formed.

For the set \(E\) of evaluable items remaining after uniform data-validation quarantine, let \(C\) be the subset with a successfully completed method output. Completion rate is

\[
\mathrm{completion\ rate} = \frac{|C|}{|E|}.
\]

Because an exhausted item-level failure belongs to \(E\) but not \(C\), it lowers completion rate. End-to-end accuracy uses the same \(|E|\) denominator, with `method_failure` contributing zero correct answers.

## 8. Required event-log fields

The event log must contain one record for every actual provider call, including the initial call and every retry-generated call. It must also support terminal records for failures that prevent a call. At minimum, each applicable record must include:

| Field | Required interpretation |
|---|---|
| `run_id` | Stable identifier for the benchmark run. |
| `item_id` | Stable dataset-item identifier. |
| `configuration` | Immutable benchmark and method configuration identifier or serialized reference. |
| `call_id` | Unique identifier for the wrapper-level call. |
| `attempt_index` | Zero-based attempt number: 0 for the initial attempt and 1--3 for retries. |
| `failure_layer` | Layer at which failure was classified, such as transport, provider, response, parsing, schema, semantic, protocol, data, or configuration. |
| `failure_code` | Canonical code for the observed failure, or null on success. |
| `retry_eligible` | Boolean decision under this policy. |
| `backoff_seconds` | Delay applied before this attempt, with 0 for the initial attempt. |
| `http_status` | HTTP status when available. |
| `provider_model_id` | Exact provider-reported or requested model identifier. |
| `response_id` | Provider response identifier when available. |
| `input_tokens` | Input tokens attributed to the call. |
| `output_tokens` | Output tokens attributed to the call. |
| `latency_ms` | End-to-end latency for the call in milliseconds. |
| `resolution_action` | Action taken, such as retry, accept, normalize, fail item, quarantine item, or stop run. |
| `included_in_final_vote` | Whether the response contributed to the method's final vote or aggregation. |
| `included_in_accuracy_denominator` | Whether the item is included in the end-to-end accuracy denominator. |
| `included_in_cost_analysis` | Whether the call is included in cost analysis; all actual calls must be true. |
| `final_status` | Terminal item or run status when known, including success, `method_failure`, `data_validation_failure`, or run-blocking failure. |

Null values must distinguish genuinely unavailable fields from zero-valued measurements. The log should additionally retain timestamps, the effective `Retry-After` value, normalization actions, provider error identifiers, and computed monetary cost when available.

## 9. Operational metrics

Operational reporting must separate initial attempts from retries and stratify failures by layer, code, provider model, configuration, and attempt index. Let \(N_{\mathrm{initial}}\) be the number of initial calls and \(N_{\mathrm{retry}}\) the number of retry-generated calls. Retry rate is

\[
\mathrm{retry\ rate} = \frac{N_{\mathrm{retry}}}{N_{\mathrm{initial}}}.
\]

Let \(t^{\mathrm{in}}_a\) and \(t^{\mathrm{out}}_a\) be the input and output tokens for attempt \(a\), where \(a=0\) is the initial attempt. Retry token overhead is

\[
\mathrm{retry\ token\ overhead}
= \sum_{a=1}^{\mathrm{max\_attempts}-1}
\left(t^{\mathrm{in}}_a + t^{\mathrm{out}}_a\right),
\]

with the sum taken only over retry attempts that actually occurred. Reports must also include completion rate, end-to-end accuracy, method-failure rate, failure counts by taxonomy, retries per item, retry latency overhead, and retry cost overhead. All metrics must be derivable from the event log without reconstructing undocumented provider or SDK behavior.
