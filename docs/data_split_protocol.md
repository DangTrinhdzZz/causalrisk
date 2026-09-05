# CLadder v1 Data-Splitting and Leakage-Control Protocol

Protocol version: **1.0**

## 1. Purpose and scope

This protocol governs the division of CLadder v1 for the CausalRisk pilot study of formal causal reasoning with known causal models. The resulting datasets are intended for evaluation and calibration only. They must not be used to fine-tune a model, update model weights, or otherwise train model parameters.

This document specifies future split construction and leakage controls. It is not a split manifest, and no split is created by this protocol.

## 2. Immutable source dataset

The immutable source is defined by all of the following:

- Archive: `data/raw/cladder-v1.zip`
- SHA-256: `9fdae052b1ebe4ee6a19fdfb3e1eb88a381c7345df394cea524bcce97e2349b3`
- Audited balanced archive member: `cladder-v1-q-balanced.json`
- Total raw items: **10,112**
- Label counts: **5,056** `yes` and **5,056** `no`
- Canonical candidate pool after full-prompt deduplication: **8,917 items**
- Canonical representative of each consistent full-prompt duplicate group: the item with the smallest numeric `question_id`

The archive, archive hash, source member, and associated source definition may be changed only through a new, documented protocol amendment. Substitution without an amendment invalidates comparability with results governed by this version.

## 3. Duplicate handling and protected families

The full inference prompt is the ordered concatenation `background + given_info + question`. Before comparison, each field is lowercased and its whitespace is normalized while all other semantic text is preserved; field boundaries remain explicit.

The audit identified **366 full-prompt duplicate groups**. All groups agree internally on answer, rung, query type, graph ID, and story ID. They may span multiple model IDs. These consistent groups are not quarantined. Candidate preparation retains one canonical representative per group and excludes the redundant copies, while preserving the union of every original member's `model_id`.

A protected family is a connected component constructed over the full raw dataset. Two items are joined when they share either the same `meta.model_id` or the same normalized full inference prompt. Connectivity is transitive and must be preserved even after canonical representatives have been selected.

A protected family may contribute selected items to at most one of smoke, calibration, or locked test. Any unused item from a contributing family must remain unused; it may not be assigned to another split.

If a future audit finds a full-prompt duplicate group that disagrees on answer, rung, query type, graph ID, or story ID, the entire duplicate group must be quarantined and the incident documented before split generation. Model-ID disagreement alone is not grounds for quarantine.

## 4. Split roles and exact rung quotas

| Split | Purpose | Total items | Per-rung quota |
|---|---|---:|---:|
| Smoke | Engineering and cost smoke test | 60 | 20 per rung |
| Calibration | Select pre-specified configuration and operating decisions | 300 | 100 per rung |
| Locked test | Final confirmatory evaluation | 600 | 200 per rung |

Rung is evaluation-only metadata. Neither the inference controller nor the evaluated agent may receive ground-truth rung information.

## 5. Selection algorithm and fixed seed

The fixed split-selection seed is **`20260905`**. The generator must be fully deterministic conditional on the archive hash, protocol version, and this seed. It must not read model outputs, experiment results, costs, accuracy measurements, or results from any benchmark.

Hard constraints, in priority order, are:

1. Use only the 8,917 canonical candidates.
2. Meet the exact 60/300/600 split sizes and exact per-rung quotas.
3. Permit no protected-family, canonical-prompt, or item overlap across splits.

Soft optimization objectives, in priority order, are:

1. Minimize `yes`/`no` imbalance within every rung of every split, targeting 50/50 where feasible.
2. Make the `query_type` distribution within each rung as close as possible to the corresponding candidate-pool distribution.
3. Preserve diverse graph and story coverage when this does not conflict with a hard constraint.

Splits must not be hand-edited, generated with a different seed, or reselected after performance has been observed. If the algorithm cannot satisfy every hard constraint, it must emit a feasibility report and create no purported valid split; constraints must not be relaxed silently.

## 6. Leakage controls at inference time

The agent or controller may receive only the fields required to solve an item:

- `background`
- `given_info`
- `question`
- A non-semantic `item_id`, if operational logging requires one

The prompt and model context must not contain:

- `answer`
- `reasoning`
- `groundtruth`
- `rung`
- `query_type`
- `graph_id`
- `story_id`
- `model_id`
- Split name or membership
- Metadata or results from any other item

The model may infer the causal-query category from natural-language wording, but it must not be supplied with ground-truth metadata.

## 7. Public versus sealed artifacts

The public repository may contain only:

- This protocol
- The source hash
- Split-generator source code
- Non-sensitive aggregate audit reports
- Code and configuration versions and checksums

Before evaluation is complete, the public repository must not contain:

- Split manifests
- `question_id` membership
- Prompts
- Answers or labels
- Locked-test outputs

Sensitive artifacts must be stored locally in an ignored or sealed area. Local hashes or checksums must be recorded to support reproducibility without disclosing their contents.

## 8. Required validation before any experiment

Before any experiment starts, a local validation audit must confirm that:

- The archive SHA-256 matches the immutable source definition.
- The split sizes are exactly 60, 300, and 600.
- Every split meets its exact per-rung quota.
- No item, canonical prompt, or protected family overlaps across splits.
- No full-prompt duplicate is selected more than once.
- Label balance, query-type distribution, and graph/story coverage have been reported.
- Local manifest hashes have been generated.
- The public audit reveals neither locked-test membership nor labels.

Failure of any required check blocks experimentation.

## 9. Protocol freeze and amendments

The smoke split may be used to correct operational or code defects, but it must not be reselected or altered in response to accuracy. The calibration split may be used to fix the configuration and operating decisions before the locked test.

Before locked-test execution, the following must be frozen: commit hash, prompts, schemas, retry policy, model identifiers, token budget, and split manifests.

A mechanical error that violates this protocol during locked testing requires all affected locked-test outputs to be discarded. Every experimental arm must then be rerun after the defect is corrected. Selective reuse of unaffected-looking outputs is prohibited.

Any change that alters methodological behavior requires a documented protocol amendment and a return to calibration before locked testing.

## 10. Next implementation step

The next step is to implement the deterministic split generator and its local validation audit under this protocol. That step must not run a model or create research results. Split generation itself remains a separate, explicitly authorized operation.
