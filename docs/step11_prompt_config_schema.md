# Step 11 – Prompt Templates and Config Schema

**Status:** protocol-level complete; implementation and runtime verification remain pending.

## 1. Purpose

This step defines the versioned structure of model-facing prompts, role instructions, configuration records, naming conventions, and leakage-safe prompt construction. It provides a reviewable contract for later implementation without embedding provider credentials, benchmark labels, or runtime results.

## 2. Scope and non-scope

This document governs prompt-template structure and versioning, configuration-ID naming, role definitions, output and parser conventions, call-budget encoding, provider/model assignment fields, and prompt/config leakage controls.

It makes no API calls, executes no benchmark item, performs no scoring, and makes no model-performance claim. It does not tune prompts on the locked test. Model selection and endpoint behavior remain provisional until the Step 8 runtime-verification requirements are satisfied.

## 3. Prompt design principles

1. Every model-facing prompt is label-free. Gold answers, dataset reasoning/ground truth, split membership, evaluation-only rung/query-type metadata, graph/template-family identifiers, protected-family identifiers, and other answer-correlated metadata must not appear.
2. Matched configurations receive the same natural-language causal question and causal context. Prompt differences are limited to the intended method, role, and authorized information flow.
3. Retrieval, web access, benchmark lookup, and cross-item context are disabled during benchmark inference.
4. Every final-decision prompt requires a final line containing exactly `YES` or `NO`. Intermediate evidence cards use their versioned schemas without requesting hidden chain-of-thought.
5. Prompt construction is deterministic from a frozen template, label-free item record, locked configuration, and authorized upstream evidence cards.
6. Prompt text and rendering code are versioned and checksummed. Once used on the locked test, they are immutable.
7. Concise, auditable causal justification may be requested, but models must not be asked to reveal private or hidden chain-of-thought.

## 4. Prompt template components

Every rendered prompt is assembled in this order from explicit components:

| Component | Contract |
|---|---|
| `system_instruction` | Common behavioral and safety boundary, including no external lookup and no invented context. |
| `role_instruction` | Configuration-specific Analyst, Critic, specialist Critic, or Adjudicator responsibilities. |
| `task_instruction` | Common causal-reasoning task and permitted evidence requirements. |
| `question_context` | Label-free benchmark background, given information, and natural-language question. |
| `output_instruction` | Versioned response schema or evidence-card format for the current role. |
| `optional_previous_responses` | Authorized prior evidence cards for sequential council roles; absent for independent `A3`/`A5` samples and independent parallel critics. |
| `final_answer_instruction` | For a final-decision call, requires one terminal line containing exactly `YES` or `NO`. |

The renderer must reject unknown components and must not accept arbitrary metadata dictionaries. Optional prior responses are treated as untrusted model text, delimited from instructions, and never augmented with gold-aware annotations.

### Template skeleton

```text
{{ system_instruction }}
{{ role_instruction }}
{{ task_instruction }}

CAUSAL QUESTION CONTEXT
{{ question_context }}

{{ optional_previous_responses }}
{{ output_instruction }}
{{ final_answer_instruction }}
```

The skeleton illustrates component order only. Exact wording and evidence-card fields must be frozen as a named prompt version before execution.

## 5. Role definitions

- **Analyst:** produces an initial causal answer and, when required by the configuration, a concise evidence card grounded only in the supplied item. In independent single-agent sampling, each Analyst call receives no other sample’s output.
- **Critic:** checks observable reasoning for semantic/query mistakes, confounding and adjustment errors, intervention/observation confusion, counterfactual-world mistakes, graph/identification faults, arithmetic faults, and incorrect answer mapping. A Critic cites concise item evidence rather than requesting hidden reasoning.
- **Specialist Critic:** in `C5`, emphasizes the semantic/query, graph/identification, or formal/numerical block assigned by Step 7. The three Critics see the original item and Analyst card but not one another’s responses.
- **Adjudicator:** independently evaluates authorized prior evidence cards and makes the final decision without gold labels, confidence voting, external lookup, or hidden metadata.
- **Parser:** a deterministic, versioned non-LLM component that preserves raw output and maps the permitted final-answer form to `YES`, `NO`, or `INVALID`.

“Parser” is not a model role and consumes no LLM call. Deterministic majority voting for `A3` and `A5` is likewise controller logic, not an Adjudicator call.

## 6. Configuration schema

The following YAML-style example is normative at the field level; a later implementation may use JSON with equivalent types and validation. It contains placeholders, not runtime selections or secrets.

```yaml
config_id: A1_SINGLE_V1
method_family: single_agent
call_budget: 1
provider_pool:
  - PROVIDER_PLACEHOLDER
model_assignment:
  analyst: MODEL_ID_PLACEHOLDER
prompt_version: prompt_causal_yesno_v1
roles:
  - analyst
temperature: TEMPERATURE_TO_BE_FROZEN
max_output_tokens: TOKEN_LIMIT_TO_BE_FROZEN
retry_policy_ref: docs/retry_policy.md
parser_version: yesno_parser_v1
logging_version: step9_logging_v1
allow_retrieval: false
allow_web: false
expose_gold_label: false
expose_metadata: false
notes: Protocol placeholder; runtime values remain pending.
```

Field requirements:

| Field | Type and constraint |
|---|---|
| `config_id` | One allowed immutable configuration identifier. |
| `method_family` | `single_agent`, `boundary`, or `heterogeneous_council`. |
| `call_budget` | Integer exactly matching the Step 7 planned LLM-call count; retries are tracked separately. |
| `provider_pool` | Non-empty list of provisionally eligible providers; no credentials or endpoints containing secrets. |
| `model_assignment` | Role-to-exact-model-ID mapping, finalized only after runtime verification. Repeated `A3`/`A5` calls use the same model. |
| `prompt_version` | Existing immutable prompt bundle identifier and checksum reference. |
| `roles` | Ordered roles/topology compatible with the selected configuration. |
| `temperature` | Explicit numeric decoding value supported by the endpoint. |
| `max_output_tokens` | Positive integer output cap recorded per role if values differ. |
| `retry_policy_ref` | Versioned reference/checksum for the normative retry policy. |
| `parser_version` | Immutable deterministic parser identifier. |
| `logging_version` | Schema version compatible with Step 9. |
| `allow_retrieval` | Must be `false` for benchmark inference. |
| `allow_web` | Must be `false` for benchmark inference. |
| `expose_gold_label` | Must be `false` for every inference configuration. |
| `expose_metadata` | Must be `false`; only explicitly allowlisted inference fields may be rendered. |
| `notes` | Optional non-secret protocol annotation; it must not alter behavior or contain result-aware guidance. |

Resolved configuration files must also record exact role-specific providers, endpoint/model IDs, seeds when supported, decoding parameters, prompt checksums, code version, and schema versions required by Steps 8–10.

## 7. Configuration IDs

The allowed protocol identifiers are:

| Config ID | Meaning |
|---|---|
| `A1_SINGLE_V1` | One-call single-agent baseline. |
| `A3_SINGLE_V1` | Three independent calls to one primary model with deterministic majority vote. |
| `A5_SINGLE_V1` | Five independent calls to one primary model with deterministic majority vote. |
| `C1_BOUNDARY_V1` | Alias/reference for the same execution as `A1_SINGLE_V1`. |
| `C3_COUNCIL_V1` | Analyst, Critic, and Adjudicator heterogeneous council. |
| `C5_COUNCIL_V1` | Analyst, three independent specialist Critics, and Adjudicator heterogeneous council. |

`C1_BOUNDARY_V1` must resolve to the same run artifact as `A1_SINGLE_V1`; it must not initiate a second call, produce an independent observation, or be interpreted as a multi-agent condition. A suffix change denotes a new version and requires documented review rather than in-place mutation.

## 8. Locked call structures

These structures preserve Step 7 and are normative:

- **A1:** one independent Analyst call; its normalized answer is final.
- **A3:** three independent calls to the same primary model, each receiving only the original item and the same base prompt; deterministic majority vote selects the final answer.
- **A5:** five independent calls under the same conditions as `A3`; deterministic majority vote selects the final answer.
- **C1:** the exact `A1` execution, exposed only as a boundary/reference alias.
- **C3:** Analyst Agent 1 → Critic Agent 2 → Adjudicator Agent 3.
- **C5:** Analyst Agent 1 → three independent specialist Critics (Agents 2–4) → Adjudicator Agent 5. Critics do not see one another’s cards.

Retries authorized by `docs/retry_policy.md` are recovery attempts and are not part of these method-call budgets. `A3`/`A5` do not use sequential self-review or revision: adding such information flow would change the locked method. `C5` does not add a second Analyst: doing so would replace one of the three locked specialist Critics.

## 9. Output contract

Raw model output is preserved byte-for-byte or as the provider-returned text field plus an integrity checksum. A final-decision prompt requires the last non-empty answer line to contain exactly one of:

```text
YES
```

```text
NO
```

The versioned deterministic parser maps a conforming answer to `YES` or `NO`. If no single valid final answer is present after the normalization allowed by the retry policy, it returns `INVALID` with the applicable parse/schema/label failure code. Step 9 governs record disposition and scoring separation; the retry policy governs whether the underlying failure is retry eligible. No LLM formatting repair or manual correction is permitted.

Concise justification may be stored only when the frozen prompt version requests it. The prompt must request an auditable summary or evidence card, never hidden chain-of-thought, and the final answer remains machine-separable from that summary.

## 10. Leakage prevention

- `expose_gold_label` is always `false` during inference and cannot be overridden by a role or provider adapter.
- `allow_retrieval` and `allow_web` are always `false` for benchmark inference.
- `expose_metadata` is `false`; answer, dataset reasoning, rung, query type, split, graph family, story/template family, source IDs, model-family grouping, and protected-family data remain outside prompts.
- The renderer consumes an explicit allowlist of label-free fields, not a raw benchmark object.
- Prior responses are passed only along edges authorized by the locked topology and contain no scorer annotations.
- Prompt templates, render snapshots using synthetic/non-benchmark inputs, and resolved configs must pass human and automated leakage review before calibration or locked-test execution.
- Logs displayed to a model contain no previous gold-aware result, other-item context, credential, or provider secret.

Any prompt/config violation invalidates every affected run. The artifacts are preserved for audit, excluded from scoring, and rerun only under the protocol-amendment and invalidation rules.

## 11. Prompt versioning

Prompt bundle names use descriptive immutable identifiers such as `prompt_causal_yesno_v1`. The bundle includes common instructions, every role template, output schema, renderer version, and content checksum. Configs reference the identifier and checksum rather than mutable “latest” content.

Calibration may motivate a new incremented prompt version before the locked-test freeze. The old version remains preserved, and the decision is documented without overwriting prior artifacts. Locked-test inputs, outputs, or labels must never tune a prompt. Once a prompt version is used on the locked test, it is immutable. A behavioral prompt change after freeze requires an explicit protocol amendment and return to calibration before any new locked-test run.

Whitespace-only or transport-wrapper changes are still versioned when they alter rendered bytes. Provider-specific wrappers may differ only where required for equivalent transport/schema behavior and must not add causal information.

## 12. Config validation checklist

- [ ] `config_id` is one of the six allowed identifiers and its version is immutable.
- [ ] `method_family`, ordered roles, model reuse, and information flow match Step 7.
- [ ] `call_budget` is exactly 1, 3, or 5 as required; retry calls are accounted for separately.
- [ ] `C1_BOUNDARY_V1` aliases the `A1_SINGLE_V1` execution rather than scheduling a duplicate run.
- [ ] `expose_gold_label`, `expose_metadata`, `allow_retrieval`, and `allow_web` are all `false`.
- [ ] The referenced prompt version and checksum exist and passed leakage review.
- [ ] The deterministic `parser_version` is recorded and tested on synthetic cases.
- [ ] The retry-policy reference/version is recorded and SDK automatic retries are disabled.
- [ ] Provider and exact model fields are present for every model role and passed Step 8 smoke verification.
- [ ] Temperature, provider seed where supported, and role-specific token limits are explicit.
- [ ] The logging schema is compatible with Step 9 and records every call and retry.
- [ ] No credential, secret-bearing endpoint, result-aware note, or unapproved metadata appears in the config.
- [ ] Config, prompts, parser, and rendered synthetic snapshots are frozen before benchmark execution.

## 13. Final status

**Step 11 is completed at protocol level. No API call, benchmark execution, scoring execution, or model performance claim has been made in this step.**
