# CLadder v1 data audit

Audit date: **2026-09-05**

This is a read-only metadata audit of the official CLadder v1 balanced data. It creates no smoke, calibration, or locked-test split.

## Provenance and archive inspection

- Source URL: [https://github.com/causalNLP/cladder/raw/main/data/cladder-v1.zip](https://github.com/causalNLP/cladder/raw/main/data/cladder-v1.zip)
- Local archive: `data/raw/cladder-v1.zip` (ignored by Git)
- ZIP size: **7,168,720 bytes**
- SHA-256: `9fdae052b1ebe4ee6a19fdfb3e1eb88a381c7345df394cea524bcce97e2349b3`
- JSON access: members were read directly from the ZIP; nothing was extracted.
- Balanced member: `cladder-v1-q-balanced.json`
- Metadata member: `cladder-v1-meta-models.json`

## Dataset summary

- Total items: **10,112**
- Answer `yes`: **5,056**
- Answer `no`: **5,056**
- Other non-empty answer values: **0**

### Required-field quality

“Missing” means absent, null, or a blank string. “Present but invalid” means the value has an unexpected type; additionally, answers must be `yes`/`no` and rung must be integer 1, 2, or 3. Boolean values are not accepted as identifiers or numbers. Ground truth accepts JSON scalar values and flat lists (including an empty adjustment set).

| Field | Missing | Present but invalid |
|---|---:|---:|
| `question_id` | 0 | 0 |
| `desc_id` | 0 | 0 |
| `given_info` | 0 | 0 |
| `question` | 0 | 0 |
| `answer` | 0 | 0 |
| `meta.query_type` | 0 | 0 |
| `meta.rung` | 0 | 0 |
| `meta.story_id` | 0 | 0 |
| `meta.graph_id` | 0 | 0 |
| `meta.model_id` | 0 | 0 |
| `meta.groundtruth` | 0 | 0 |

## Attribute counts

### Rung

| Rung | Count |
|---|---:|
| `3` | 3,792 |
| `1` | 3,160 |
| `2` | 3,160 |

### Query type

| Query type | Count |
|---|---:|
| `backadj` | 1,580 |
| `marginal` | 1,580 |
| `ate` | 1,422 |
| `correlation` | 1,422 |
| `det-counterfactual` | 1,422 |
| `ett` | 1,264 |
| `nie` | 790 |
| `nde` | 316 |
| `collider_bias` | 158 |
| `exp_away` | 158 |

### Graph ID

| Graph ID | Count |
|---|---:|
| `arrowhead` | 1,264 |
| `mediation` | 1,264 |
| `chain` | 1,106 |
| `diamond` | 1,106 |
| `frontdoor` | 1,106 |
| `confounding` | 948 |
| `diamondcut` | 948 |
| `fork` | 948 |
| `IV` | 790 |
| `collision` | 632 |

### Story ID

| Story ID | Count |
|---|---:|
| `nonsense5` | 432 |
| `nonsense8` | 407 |
| `smoking_frontdoor` | 395 |
| `nonsense3` | 383 |
| `nonsense4` | 382 |
| `nonsense0` | 381 |
| `nonsense9` | 380 |
| `nonsense6` | 379 |
| `nonsense2` | 374 |
| `nonsense7` | 372 |
| `nonsense1` | 352 |
| `firing_employee` | 329 |
| `firing_squad` | 231 |
| `floor_wet` | 228 |
| `college_salary` | 220 |
| `orange_scurvy` | 217 |
| `smoking_tar_cancer` | 213 |
| `vaccine_kills` | 213 |
| `gender_pay` | 179 |
| `forest_fire` | 178 |
| `simpson_kidneystone` | 175 |
| `gender_admission_state` | 169 |
| `alarm` | 168 |
| `penguin` | 168 |
| `simpson_drug` | 166 |
| `gender_admission` | 165 |
| `simpson_vaccine` | 162 |
| `blood_pressure` | 159 |
| `obesity_mortality` | 158 |
| `smoke_birthWeight` | 157 |
| `candle` | 153 |
| `nature_vs_nurture` | 151 |
| `smoking_gene_cancer` | 150 |
| `getting_late` | 146 |
| `simpson_hospital` | 146 |
| `neg_mediation` | 145 |
| `getting_tanned` | 143 |
| `encouagement_program` | 142 |
| `price` | 136 |
| `college_wage` | 123 |
| `cholesterol` | 122 |
| `celebrity` | 119 |
| `elite_students` | 117 |
| `tax_smoke_birthWeight` | 117 |
| `water_cholera` | 111 |
| `hospitalization` | 106 |
| `man_in_relationship` | 93 |

## Protected model groups

There are **5,268** non-empty model-ID groups. Group-size statistics are: minimum **1**, median **2**, and maximum **7** items.

Ten largest model-ID groups:

| Model ID | Count |
|---|---:|
| `1026` | 7 |
| `2664` | 7 |
| `2767` | 7 |
| `2998` | 7 |
| `3105` | 7 |
| `3228` | 7 |
| `3358` | 7 |
| `3359` | 7 |
| `3361` | 7 |
| `3370` | 7 |

These are the model-only groups. The provisional atomic protected groups below also merge across model IDs when full inference prompts duplicate.

## Graph x query type x story cells

- Non-empty cells: **873**
- Items represented in non-empty cells: **10,112**
- Minimum cell size: **1**
- Maximum cell size: **64**

Exact size distribution:

| Cell size | Non-empty cells |
|---:|---:|
| 1 | 27 |
| 2 | 44 |
| 3 | 58 |
| 4 | 90 |
| 5 | 103 |
| 6 | 66 |
| 7 | 61 |
| 8 | 46 |
| 9 | 28 |
| 10 | 41 |
| 11 | 32 |
| 12 | 24 |
| 13 | 13 |
| 14 | 8 |
| 15 | 8 |
| 16 | 7 |
| 17 | 2 |
| 18 | 14 |
| 19 | 12 |
| 20 | 11 |
| 21 | 16 |
| 22 | 18 |
| 23 | 15 |
| 24 | 9 |
| 25 | 12 |
| 26 | 19 |
| 27 | 10 |
| 28 | 7 |
| 29 | 10 |
| 30 | 8 |
| 31 | 8 |
| 32 | 10 |
| 33 | 2 |
| 34 | 6 |
| 35 | 2 |
| 36 | 4 |
| 37 | 2 |
| 38 | 4 |
| 39 | 2 |
| 45 | 2 |
| 50 | 1 |
| 53 | 2 |
| 54 | 1 |
| 55 | 1 |
| 56 | 1 |
| 57 | 2 |
| 58 | 1 |
| 60 | 1 |
| 62 | 1 |
| 64 | 1 |

## Duplicate analyses

Normalization lowercases text and collapses whitespace while preserving all other semantic text. Newline separators preserve field boundaries. SHA-256 hashes of normalized text define duplicate membership. This audit removes no item.

### A. Question-level duplicates

- Normalized fields: `given_info + question`
- Duplicate items beyond the first occurrence: **1,341**
- Duplicate groups: **248**

### B. Full inference-prompt duplicates

The `background` is resolved from `cladder-v1-meta-models.json` by each item's `meta.model_id`, then `background + given_info + question` is normalized and hashed.

- Duplicate items beyond the first occurrence: **1,195**
- Duplicate groups: **366**
- Deduplicated candidate-pool size (`total items - redundant full-prompt copies`): **8,917**
- Groups spanning multiple model IDs: **366**
- Groups quarantined for disagreement on answer, rung, query type, graph ID, or story ID: **0**

| Attribute | Inconsistent duplicate groups |
|---|---:|
| answer | 0 |
| rung | 0 |
| query type | 0 |
| graph ID | 0 |
| story ID | 0 |

A full-prompt duplicate group is quarantined only when its members disagree on at least one of those five audited attributes. Model-ID disagreement does not trigger quarantine; it supplies the cross-model union relation used for protected families.

For each consistent duplicate group, future candidate preparation retains one deterministic canonical candidate: the member with the smallest numeric `question_id`. Redundant copies are excluded from the candidate pool, but every original member's `model_id` remains in the protected-family union. Canonical candidates selected across the consistent duplicate groups: **366**.

## Provisional atomic protected families

Over the full raw dataset, a protected family is a connected component under the union of two relations: equal `meta.model_id`, or equal normalized full-inference-prompt hash. Components are computed before redundant copies are excluded, preserving all cross-model links.

- Protected families: **4,112**
- Minimum size: **1**
- Median size: **2**
- P95 size (nearest-rank): **6**
- Maximum size: **83**

Counts by rung are presence-based: a mixed-rung protected family contributes once to every rung it contains.

| Rung | Count |
|---|---:|
| `1` | 2,171 |
| `3` | 2,151 |
| `2` | 1,391 |

- Mixed-rung protected families: **1,310**

Counts by answer label are likewise presence-based.

| Answer | Count |
|---|---:|
| `yes` | 2,817 |
| `no` | 2,814 |

- Mixed-answer protected families: **1,519**

Mixed-rung and mixed-answer protected families are expected consequences of the connectivity rules, not data defects.

Ten largest protected families (stable ties are ordered by earliest dataset position; no protected identifier is exposed):

| Rank | Items | Model IDs | Distinct full prompts | Rungs | Answers |
|---:|---:|---:|---:|---|---|
| 1 | 83 | 22 | 61 | 1, 2, 3 | no, yes |
| 2 | 64 | 21 | 41 | 1, 2, 3 | no, yes |
| 3 | 51 | 14 | 38 | 1, 2, 3 | no, yes |
| 4 | 50 | 20 | 27 | 1, 2, 3 | no, yes |
| 5 | 48 | 16 | 32 | 1, 2, 3 | no, yes |
| 6 | 45 | 11 | 33 | 1, 2, 3 | no, yes |
| 7 | 43 | 11 | 30 | 1, 2, 3 | no, yes |
| 8 | 43 | 10 | 31 | 1, 2, 3 | no, yes |
| 9 | 42 | 11 | 32 | 1, 2, 3 | no, yes |
| 10 | 41 | 10 | 31 | 1, 2, 3 | no, yes |

## Metadata coverage

- Do all required model IDs appear in `cladder-v1-meta-models.json`? **Yes. All 5,268 model IDs used by the balanced dataset appear in the metadata file.**
- The metadata file contains **7,064** distinct non-empty model IDs in total.

## Inference-controller boundary

The inference controller must hide these dataset fields: `answer`, `reasoning`, `meta.groundtruth`, `meta.rung`, `meta.query_type`, `meta.graph_id`, `meta.story_id`, and `meta.model_id`.

Only inference inputs intended for the evaluated system should cross that boundary; protected grouping keys and balancing attributes remain evaluation-pipeline metadata.

## Implications for split construction

- No actual split has been created.
- Hard leakage constraints are protected-family disjointness and no duplicate prompt reuse.
- A protected family may contribute selected items to only one of smoke, calibration, or locked test.
- Unused items from that family remain unused rather than being placed in another split.
- For consistent prompt duplicates, only the smallest-numeric-`question_id` canonical candidate is eligible; redundant copies remain excluded while their model-ID links remain enforced.
- Balance diagnostics are rung, answer label, query type, graph ID, and story ID; these are not family-disjointness rules.
- Graph/story disjointness remains a feasibility decision pending inspection of the resulting group structure.
- Any full-prompt duplicate group inconsistent on answer, rung, query type, graph ID, or story ID must be quarantined before split generation. Model-ID disagreement alone is not an inconsistency.

The protected-group counts do not by themselves establish that exact 60/300/600 smoke, calibration, and locked-test sizes are feasible. That requires a future group-aware allocation and balance analysis.

## Limitations

Public CLadder data may have been encountered during LLM pre-training. A future locked evaluation pipeline can control direct evaluation leakage and cross-split leakage, but this audit cannot prove the absence of pre-training contamination.
