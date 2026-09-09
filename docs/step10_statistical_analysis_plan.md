# Step 10 – Statistical Analysis Plan and Evaluation Decision Rules

**Status:** protocol-level complete; no inference, scoring, or statistical computation has been performed.

## 1. Purpose

This plan predefines how frozen benchmark outputs will be scored, compared, and interpreted after authorized execution. Precommitting the metrics, comparisons, statistical procedures, and decision rules limits post-hoc metric selection and protects the validity of conclusions about causal-reasoning accuracy and operational cost.

## 2. Scope and non-scope

This step defines primary and secondary metrics, planned comparisons, hypotheses, minimum meaningful effects, statistical tests, effect-size reporting, cost-efficiency and Pareto analyses, treatment of invalid outputs and failures, subgroup and error analyses, interpretation rules, and reporting and audit requirements.

It makes no API calls, runs no benchmark inference, executes no scoring, and makes no model-performance claim. It does not modify the sealed splits, locked methods, or provisional model roster. Any such change requires a separate protocol amendment made before the affected analysis.

## 3. Analysis populations and units

The benchmark item is the unit of paired analysis. All configurations are evaluated on the same eligible items in a split. Items uniformly quarantined for a verified data defect are excluded from every configuration before denominators are formed. Item-level method failures and terminal invalid outputs remain in the primary end-to-end accuracy denominator and contribute zero correct answers. Items never attempted because of a documented run-blocking failure are not converted into wrong answers; the incomplete run is not a valid complete-run comparison.

The smoke split is operational and is not used for confirmatory claims. Calibration results may support decisions authorized by the protocol but are reported separately from locked-test results. The locked test supplies the primary confirmatory estimates after all configurations and analysis code are frozen.

## 4. Primary metrics

| Metric | Definition |
|---|---|
| Accuracy | Correct final answers divided by all evaluable items, with terminal `INVALID` and item-level `method_failure` counted as incorrect. |
| Completion rate | Items with a successful final method output divided by all evaluable items. |
| Invalid-output rate | Evaluable items ending in a parser/schema/label-invalid disposition divided by all evaluable items. |
| Average latency per item | Arithmetic mean of end-to-end item latency, including eligible retry delays and all constituent calls. |
| Median latency per item | Median end-to-end item latency under the same accounting boundary. |
| Input tokens | Total and mean provider-reported input tokens; documented estimates are used only when provider counts are unavailable. |
| Output tokens | Total and mean provider-reported output tokens under the same rule. |
| Total tokens | Input plus output tokens, reported as totals and per-item means. |
| Estimated cost in USD | Total and per-item cost computed from the frozen provider/model pricing table and all actual calls, including retries. |
| Calls per item | Mean number of actual provider calls per evaluable item, with planned calls and retry-generated calls also reported separately. |
| Cost per correct answer | Total estimated USD cost divided by the number of correct item-level answers. Undefined when there are no correct answers. |
| Token cost per correct answer | Total input plus output tokens divided by the number of correct answers. Undefined when there are no correct answers. |

Accuracy is the primary effectiveness outcome. Cost, tokens, latency, completion, and validity are co-required operational outcomes; accuracy must not be interpreted alone.

## 5. Secondary metrics

- retry count and retry rate, separated from planned method calls;
- failure-type distribution by layer, provider/model, role, and configuration;
- parse-, schema-, and invalid-label failure rates;
- abstention, refusal, empty, or malformed-answer rates where applicable;
- role-level answer disagreement in `C3` and `C5`;
- vote margin or consensus strength for configurations with a defined vote;
- answer-flip rate between the Analyst/initial decision and final council decision;
- correction rate: initially incorrect to finally correct;
- harm rate: initially correct to finally incorrect; and
- retry overhead in tokens, latency, calls, and USD.

Council quantities are reported only when the locked topology produces the required observable fields. They must not be reconstructed from hidden reasoning.

## 6. Primary comparisons

The predeclared comparisons are:

| Comparison | Purpose |
|---|---|
| `A1` vs `A3` | Incremental value of three-call single-model self-consistency over one call. |
| `A1` vs `A5` | Incremental value of five-call single-model self-consistency over one call. |
| `A3` vs `A5` | Marginal value of increasing the single-model call budget. |
| `A1/C1` vs `C3` | Council improvement over the shared one-call boundary reference. |
| `A1/C1` vs `C5` | Larger-council improvement over the shared one-call boundary reference. |
| `A3` vs `C3` | Primary budget-matched single-agent versus heterogeneous-council comparison. |
| `A5` vs `C5` | Primary budget-matched single-agent versus heterogeneous-council comparison. |
| `C3` vs `C5` | Marginal value of expanding the council. |

`C1` is operationally identical to `A1`. It is represented once as `A1/C1`, is not counted as an independent multi-agent condition, and generates neither a duplicate observation nor a separate significance test. The two most important fairness comparisons are `A3` versus `C3` and `A5` versus `C5`, because their planned method-call budgets match.

## 7. Hypotheses and minimum meaningful effects

- **H1:** `C3` and `C5` improve accuracy over their corresponding `A3` and `A5` single-agent configurations.
- **H2:** Council configurations increase compute cost, reflected in latency, total tokens, actual calls, or estimated USD cost.
- **H3:** A council is useful only when its accuracy improvement is sufficient to justify its incremental operational cost and reliability burden.

An accuracy increase of at least **3 percentage points** is the provisional minimum practically meaningful effect for a primary accuracy comparison. An increase below **2 percentage points** is treated as unlikely to be practically meaningful unless accompanied by substantial cost reduction or a clearly documented robustness benefit. Effects from 2 to less than 3 points are borderline and must be described as such. These thresholds do not replace uncertainty intervals or cost analysis, and a statistically significant result below the practical threshold is not automatically beneficial.

“Disproportionate cost” is not assigned an arbitrary universal cutoff in advance because provider prices and latency constraints remain runtime-unverified. Conclusions must instead report the complete incremental cost vector, Pareto status, and sensitivity to the stated operational preference.

## 8. Statistical testing strategy

Because configurations evaluate the same items, all eligible comparisons are paired. For binary correctness, report the paired accuracy difference in percentage points, the discordant-pair counts, and McNemar’s test. Use the exact binomial form when discordant counts are small; otherwise the implementation may use the continuity-corrected asymptotic form if predeclared in the scoring code.

Report a 95% confidence interval for every paired accuracy difference. The default is a paired, item-level nonparametric bootstrap that resamples item pairs together, uses a fixed recorded analysis seed, and predeclares the replicate count and interval construction before locked-test scoring. A justified paired analytic interval may be added as a sensitivity analysis.

The eight predeclared accuracy-comparison p-values form one multiple-testing family and receive Benjamini–Hochberg false-discovery-rate control at `q = 0.05`. Unadjusted and adjusted values must both be labeled. `A3` versus `C3` and `A5` versus `C5` remain the prioritized comparisons, but they are not exempt from adjustment.

For latency, tokens, calls, and cost, report configuration-level distributions and paired item-level differences: count, mean, standard deviation, median, interquartile range, and appropriate quantiles. Because these measures are commonly skewed, emphasize paired medians and bootstrap confidence intervals rather than relying on normality. Any inferential test beyond this plan is exploratory and labeled accordingly.

P-values never stand alone. Every comparison includes the direction and magnitude of the effect, confidence interval, practical-threshold assessment, completion/invalid behavior, and incremental cost.

## 9. Cost-efficiency analysis

For each configuration, compute:

- cost per correct answer = total estimated USD / correct answers;
- tokens per correct answer = total tokens / correct answers;
- latency per correct answer = total accumulated item latency / correct answers;
- accuracy gain per 1,000 additional tokens = percentage-point accuracy difference / (incremental mean tokens per item / 1,000);
- accuracy gain per additional model call = percentage-point accuracy difference / incremental mean actual calls per item; and
- accuracy gain per additional cent = percentage-point accuracy difference / incremental mean cost per item in cents.

Incremental ratios use the named baseline in each comparison. When the denominator is zero or negative, the ratio is reported as undefined and the raw paired differences are used; misleading sign reversals are prohibited. Failed and retried calls remain in resource totals. A configuration is preferable only when the joint accuracy–cost trade-off is favorable for the declared use case, not merely because its raw accuracy is higher.

## 10. Pareto analysis

The primary Pareto dimensions are accuracy (higher is better), mean estimated cost per evaluable item, median end-to-end latency, and invalid-output rate (lower is better). A configuration is Pareto-dominated when another configuration has equal or higher accuracy, equal or lower values on all three burden dimensions, and a strict improvement on at least one dimension. A configuration is Pareto-preferred when no evaluated configuration dominates it under this metric set.

Report the Pareto frontier with confidence intervals and the underlying values. Secondary frontiers may substitute tokens for USD when prices are unavailable or compare completion reliability explicitly, but they must be labeled and must not replace the primary definition post hoc.

## 11. Invalid outputs and failed runs

A terminal `INVALID` answer is counted as incorrect in primary end-to-end accuracy and separately in invalid-output metrics. Under the locked retry policy, parse/schema/label failures are non-retryable after deterministic normalization; exhaustion of eligible transient retries instead produces `method_failure`, which is also counted as incorrect and lowers completion. This distinction must remain visible.

Transport and provider failures are reported separately from parsing, protocol, and model-reasoning failures. No output may be manually corrected, selectively rerun, or replaced after its content is observed. Run-blocking failures preserve completed records but prevent a complete-run claim; missing unattempted items are not silently scored as wrong. A run affected by label leakage, prohibited metadata, unauthorized retrieval, or another validity violation is excluded from scoring, with scope and reason documented before any authorized rerun.

## 12. Subgroup analysis

After inference artifacts are frozen, the scoring layer may join evaluation metadata that was hidden during inference. Predeclared descriptive subgroup analyses include:

- causal rung: associational, interventional, and counterfactual;
- query type;
- graph family;
- template or story family;
- question difficulty, only if defined and frozen using calibration data;
- items on which the single-agent and council outputs disagree;
- council corrections from initially incorrect to finally correct; and
- council harms from initially correct to finally incorrect.

For each sufficiently populated subgroup, report item count, accuracy and paired difference, completion, invalid rate, and uncertainty. Small groups must be clearly flagged; no unsupported confirmatory claim is made from sparse cells. Multiplicity-adjusted subgroup inference is exploratory unless the exact subgroup hypothesis and testing family were frozen before locked-test scoring.

Subgroup metadata is never exposed to model-facing prompts or routing during benchmark inference. Locked-test subgroup findings are descriptive or predeclared and cannot be used to retune prompts, configs, role assignments, or routing thresholds.

## 13. Error analysis protocol

Quantitative error analysis reports counts and rates under a frozen, mutually documented coding scheme. The planned categories are confounding errors; backdoor/front-door identification errors; intervention-versus-observation confusion; counterfactual reasoning errors; arithmetic errors; prompt/format errors; overconfident wrong consensus; debate-induced answer degradation; majority-vote failure; and Adjudicator failure.

Qualitative review uses a predeclared sample selected without provider/model favoritism and preserves configuration blinding where practical. Reviewers cite observable response evidence, may assign multiple documented categories, and record disagreements and adjudication. They must not rewrite outputs or alter primary scores. Dataset defects are handled through the uniform quarantine rule rather than attributed to a model. Examples published from sealed data require a separate disclosure review.

## 14. Decision rules for interpreting results

1. A council is considered beneficial only if its paired accuracy improvement reaches at least 3 percentage points, its confidence interval and adjusted inference are reported, and its additional cost is not disproportionate under the declared operational use case.
2. If an accuracy gain is below 2 points and resource use is materially higher, prefer the lower-cost single-agent configuration unless a predeclared robustness benefit changes the decision.
3. Effects from 2 to less than 3 points are inconclusive on practical benefit and require explicit cost and uncertainty discussion.
4. If `C5` improves only marginally over `C3` while strongly increasing tokens, latency, calls, or USD cost, prefer `C3`.
5. If `A3` or `A5` matches or outperforms its call-matched council at lower cost, the conclusion must favor the optimized single-agent strategy for that operating point.
6. If council gains are concentrated in stable, predeclared subgroups, the conclusion should motivate a future separately validated adaptive-routing study rather than always-on council inference. Locked-test findings must not be used to fit that router.
7. A configuration that is Pareto-dominated cannot be called generally preferable. A Pareto-preferred configuration is not automatically best; selection still depends on the declared accuracy/cost preference.
8. Null, harmful, or operationally unfavorable findings must be reported. The design estimates the complete heterogeneous orchestration effect and does not isolate communication from model diversity.

## 15. Reporting template

| `config_id` | Provider/model set | Calls/item | Accuracy | Δ accuracy vs `A1` | Δ accuracy vs budget-matched baseline | Completion rate | Invalid rate | Mean latency (ms) | Median latency (ms) | Mean total tokens | Estimated cost (USD) | Cost/correct | Notes |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| _To be populated only after valid execution and scoring_ | — | — | — | — | — | — | — | — | — | — | — | — | — |

Each result table must identify the split and analysis population, show numerator/denominator counts, distinguish planned calls from retries, and link to confidence intervals and adjusted comparison results. `A1/C1` occupies one row. Monetary results state the currency, price source/version, and whether token counts were reported or estimated.

## 16. Reproducibility and audit requirements

- Analyze frozen, checksum-verified run artifacts only.
- Record the exact Git commit, prompt version/checksum, resolved configuration version, parser version, and scoring-script version.
- Record provider names, exact model IDs, UTC execution timestamps, seeds, runtime/dependency versions, and pricing sources.
- Preserve immutable raw outputs, parsed outputs, event logs, failure records, and scoring outputs in their authorized sealed locations.
- Record analysis seeds and all confidence-interval, testing, multiplicity, subgroup, and missing-data settings.
- Generate checksums for analysis inputs and outputs and retain an auditable link from each aggregate result to its frozen run.
- Never overwrite a frozen artifact. Corrections create a new version/run ID with a documented supersession or protocol amendment.
- Keep credentials, item-level answers, split membership, and protected metadata out of tracked reports.

## 17. Final status

**Step 10 is completed at protocol level. No benchmark inference, scoring execution, or model performance claim has been made in this step.**
