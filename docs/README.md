# Research documentation

This directory will contain the documents that define and govern the study:

- `research_charter.md`: research purpose, questions, and governance boundaries.
- `scope_and_exclusions.md`: formal scope and explicit exclusions.
- `protocol_v0.1.md`: initial study protocol and experimental design.
- `evaluation_protocol.md`: metrics, analysis procedures, and reporting rules.
- `literature_mapping.md`: structured mapping of relevant prior work.
- `decision_log.md`: dated records of protocol and design decisions.
- `step8_model_api_roster.md`: provisional model/provider roster and runtime-verification protocol.
- `step9_run_protocol.md`: benchmark run lifecycle, contracts, logging, and execution checklist.
- `step10_statistical_analysis_plan.md`: statistical tests, accuracy–cost analysis, and evaluation decision rules.
- `step11_prompt_config_schema.md`: versioned prompt structure, role contracts, and configuration schema.
- `step12_protocol_freeze_implementation_readiness.md`: Day 1 protocol freeze, implementation gates, and readiness checklist.
- `amendment_001_openai_adjudicator.md`: pre-execution amendment adding direct OpenAI API as the C3/C5 Adjudicator candidate.
- `amendment_003_nvidia_pricing_policy.md`: symbolic-null NVIDIA pricing waiver and accounting rules.
- `amendment_004_controlled_smoke_enablement.md`: smoke-only enablement, live canary sequencing, and pass gates.
- `amendment_005_cross_split_execution_remediation.md`: frozen R1 failure analysis, narrow remediation, and the cross-split R2 execution contract.
- `amendment_006_r3_output_cap_remediation.md`: frozen R2 failure lineage and the narrow R3 output-cap synchronization.
- `amendment_007_r4_nvidia_thinking_control.md`: frozen R3 failure lineage and NVIDIA-only non-thinking request control.
- `r1_operational_canary_forensic_aggregate.json`: label-free operational aggregate for the immutable failed R1 canary.
- `r2_operational_canary_forensic_aggregate.json`: label-free operational aggregate for the immutable failed R2 canary.
- `r3_operational_canary_forensic_aggregate.json`: label-free operational aggregate for the immutable failed R3 canary.
- `day2_runtime_readiness.md`: current offline readiness, capacity, and phase-gate status.
- `provider_smoke_runbook.md`: one-provider-at-a-time, non-CLadder runtime-verification procedure.

These documents will be written, reviewed, and frozen during Day 1. They are intentionally absent from the repository initialization so that provisional choices are not represented as settled protocol decisions.
