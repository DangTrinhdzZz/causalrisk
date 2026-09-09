# Step 7 — Methods and baselines freeze

**Protocol version:** v0.1 — **Status:** frozen for the pilot; exact model identifiers, decoding settings, token caps, and JSON schema are deferred to Steps 8–9.

## 1. Purpose and scope

This step fixes the experimental *topology* used to compare a single-agent baseline family with a heterogeneous collaborative-council family on the sealed CLadder splits. It does not yet select models or implement a controller. Every configuration receives the same item prompt and must return one `yes`/`no` prediction. No configuration may access a gold label, CLadder rung/query-type metadata, retrieval, browsing, external causal tools, or a hidden chain-of-thought from another model.

The numerical suffix $k \in \{1,3,5\}$ is the number of LLM inference calls available for one item. This makes the comparison call-matched at each value of $k$. Actual billable input/output tokens, latency, completion rate, and monetary cost will still be measured and reported separately; equal call count must **not** be described as equal compute cost.

## 2. Configuration contract

| ID | Calls and model identities | Information flow | Final decision | Interpretation |
|---|---:|---|---|---|
| **A1** | One call to the primary model | No inter-call message | Its answer | One-shot single-agent baseline |
| **A3** | Three independent calls to the *same* primary model | None; each receives only the original item and same base prompt | Deterministic majority vote | Single-agent self-consistency, not a multi-agent council |
| **A5** | Five independent calls to the *same* primary model | None; each receives only the original item and same base prompt | Deterministic majority vote | Larger single-agent self-consistency baseline |
| **C1** | One call to the primary model | No inter-agent message | Its answer | Boundary control for council size 1; operationally identical to A1 |
| **C3** | Three calls to three distinct, capability-matched model families | Analyst → Critic → Adjudicator | Adjudicator's evidence-based answer | Minimal heterogeneous causal council |
| **C5** | Five calls to five distinct, capability-matched model families | Analyst → three independent specialist critics → Adjudicator | Adjudicator's evidence-based answer | Specialist heterogeneous causal council |

`A3` and `A5` still belong to the single-agent family even though they make multiple API calls: all samples use one base model, one role, no dialogue, and no model sees another sample. An odd number of samples removes vote ties. The aggregator is deterministic code, not an LLM judge.

`C1` is deliberately a **degenerate boundary case**, not a genuine multi-agent interaction. It is the same execution as `A1`; it must be run once and reported as the shared `A1/C1` condition, never as two independent observations and never as evidence that collaboration helps. Keeping this label preserves the planned $1,3,5$ council-size curve without creating a duplicate experiment.

## 3. Council execution protocol

### C3 — Analyst, Critic, Adjudicator

1. **Analyst** solves the original causal item and outputs an auditable causal evidence card: proposed answer, interpreted query type, treatment/outcome or counterfactual variables, relevant graph facts, estimand/formula, calculation or qualitative rule, and any uncertainty. It does not expose or request hidden chain-of-thought.
2. **Critic** receives the original item and the Analyst card. It applies the complete causal-audit protocol in Section 4, issues a supported or challenged verdict, and supplies a recommended answer with item-specific evidence. A challenge without a concrete fault and correction is marked unsupported.
3. **Adjudicator** receives the original item plus both cards. It independently checks the cited evidence, decides whether to retain or revise the Analyst answer, and emits the final prediction with a short resolution record. It is a decision-maker, not a JSON formatter and not a confidence-weighted voter.

### C5 — Analyst, three independent specialist critics, Adjudicator

1. The **Analyst** produces the same causal evidence card as in C3.
2. The three critics receive the original item and Analyst card but **never see one another's critique**. This star topology prevents redundant all-to-all debate, anchoring cascades, and an arbitrary critic from dominating the others.
   - **Semantic/query critic:** checks the wording, target event, treatment/outcome/evidence variables, direction of the question, and distinction among association, intervention, and counterfactual queries.
   - **Graph/identification critic:** checks stated DAG/SCM facts, causal-path direction, confounder/mediator/collider handling, admissibility of an adjustment set, and unsupported structural assumptions.
   - **Formal/numerical critic:** checks the estimand, probability identities or counterfactual consistency, use of supplied values, arithmetic, comparison rule, and final `yes`/`no` mapping.
3. The **Adjudicator** receives the original item, Analyst card, and all three critic cards. It cannot choose an answer by confidence count or simple majority. It must accept only critiques whose cited evidence is supported by the item, then retain or revise the answer.

All council messages are fixed-size, visible causal evidence cards. No role is sent a verbose private reasoning trace. Exact field names and token allocations are part of the output-schema and budget freeze in Step 9.

## 4. Causal-audit protocol for every critic

Each critic must mark every check as `pass`, `fault`, or `not_applicable`, cite the item evidence that justifies a fault, and propose the minimal correction. The full checklist is:

1. Interpret the requested claim correctly, including polarity and condition/evidence.
2. Identify the causal rung and distinguish observational, interventional, and counterfactual semantics.
3. Map all named variables correctly; do not swap treatment and outcome or invent a variable.
4. Preserve the stated graph/SCM direction and all graph facts relevant to the query.
5. Test confounder, mediator, collider, and backdoor-adjustment reasoning where applicable.
6. Check counterfactual world/evidence consistency where applicable; do not mix factual and counterfactual worlds.
7. Verify that the estimand or decision rule matches the question.
8. Verify that the formula uses only supplied, valid variables/probabilities and follows from the stated causal assumptions.
9. Recheck arithmetic, inequality direction, and conversion of the result into the requested `yes`/`no` label.
10. Detect unsupported leaps, internal contradictions, missing evidence, and an answer that conflicts with the proposed formula.

The C3 Critic executes all ten checks. In C5, specialist critics emphasize their assigned blocks but must still flag a clear fault found elsewhere; this prevents specialization from becoming permission to ignore a decisive error.

## 5. Reliability and failure handling

The existing retry policy applies unchanged: an invalid or failed call has at most three retries after its initial attempt. If any required call exhausts those attempts, the configuration returns `method_failure` for that item. There is no silent substitution of another model, no extra debate round, and no fallback to the Analyst answer or majority vote when an Adjudicator fails. End-to-end accuracy treats the item as incorrect, while completion rate and failure type are reported separately.

## 6. Fairness rules and what comparisons can prove

For a given $k$, `Ak` and `Ck` use the same original item, base causal instructions, retry rule, decoding policy, sealed split, and maximum number of LLM calls. Step 8 must choose the C3/C5 role models from distinct model families with comparable standalone causal performance and a predeclared price/latency tier; no role may be deliberately assigned an obviously stronger or weaker model. `Ak` always uses the same primary model selected for the corresponding council's Analyst role.

The primary analyses are `A1/C1`, `A3` versus `C3`, and `A5` versus `C5`, plus trends across $k=1,3,5$. Because C3/C5 use heterogeneous model families whereas A3/A5 repeatedly sample one primary model, these comparisons estimate the benefit or harm of the **complete heterogeneous collaboration design** at a fixed call budget. They do **not** identify a pure causal effect of communication separate from model diversity. The report must state this limitation; no seventh control configuration is added in this pilot.

The final report will include paired per-item accuracy, correction and harm transitions, completion rate, actual input/output tokens, calls, latency, and monetary cost. A council may be declared better only when its outcome improvement is reported together with these costs; it cannot claim a general multi-agent advantage from an accuracy gain alone.

## 7. Evidence basis and design limits

The design is motivated, not guaranteed, by prior work. CRAwDAD studies causal inference on CLadder using direct heterogeneous debate and communicates concise rationale rather than full reasoning traces; it also cautions that LLM judges can introduce bias. This motivates visible, evidence-constrained cards and an Adjudicator that verifies cited facts rather than merely choosing the last or most confident speaker. S2-MAD and CortexDebate show why dense, repetitive multi-agent exchanges can inflate context/token cost and allow dominant agents to suppress useful information; the C5 star topology therefore deliberately avoids critic-to-critic debate. A controlled cost-aware comparison in *Do multi-agent LLMs improve causal identification?* reports that same-model role specialization is not reliably superior to strong single-agent prompting and incurs substantial latency/token overhead, motivating `A1/A3/A5` and mandatory cost reporting.

These sources do not prove that C3 or C5 will outperform the baselines. The pilot must retain the possibility that A3/A5 dominate on accuracy–cost or that extra critics corrupt initially correct answers.

### References

- Vamosi, F. G., & Forkert, N. (2026). *CRAwDAD: Causal Reasoning Augmentation with Dual-Agent Debate*. AAMAS 2026. https://doi.org/10.65109/DVBN4652.
- Zeng, Y. et al. (2025). *S2-MAD: Breaking the Token Barrier to Enhance Multi-Agent Debate Efficiency*. NAACL 2025, 9393–9408.
- Sun, Y. et al. (2025). *CortexDebate: Debating Sparsely and Equally for Multi-Agent Debate*. Findings of ACL 2025, 9503–9523.
- *Do multi-agent LLMs improve causal identification? A controlled, cost-aware comparison.* Supplied project paper (`Array.pdf`), consulted as methodological evidence rather than as a claim of general superiority.
