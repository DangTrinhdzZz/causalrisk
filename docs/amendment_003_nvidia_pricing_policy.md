# Amendment 003 - NVIDIA Symbolic Pricing Policy

**Decision date:** 2026-09-11

**Status:** approved and retained by controlled smoke enablement

**Applies before:** any CLadder smoke, calibration, or locked-test inference

## 1. Decision

NVIDIA NIM remains in the execution roster as the skeptical Critic. Its
selected endpoint is a free prototype endpoint without a comparable official
token list price. NVIDIA is therefore recorded as
`official_free_endpoint_unpriced`, with `normalized_list_cost_usd: null`,
`actual_charge_usd: null`, and `billing_mode: free_prototype`.

No normalized NVIDIA cost is set to zero and no proxy price is presented as an
official price. The roster, prompts, methods, hypotheses, call budgets, and
provider assignments are unchanged.

## 2. Explicit waiver policy

Missing official pricing remains a hard execution blocker by default. The only
exception is `nvidia_nim`, and only when every method config that assigns
NVIDIA declares `allow_symbolic_unpriced_provider` with:

- the NVIDIA source URL;
- the pricing effective date; and
- a reason documenting the free endpoint and absent comparable token price.

Preflight matches those fields against the versioned pricing snapshot. A waiver
cannot authorize another provider or an unrelated source/date.

## 3. Cost accounting

For a method containing NVIDIA calls:

- `total_normalized_cost_usd` is `null`;
- `priced_cost_subtotal_usd` includes only calls with official prices;
- `priced_call_coverage` and `priced_token_coverage` are recorded separately;
- `null` is never treated as zero.

A separate sensitivity calculation may be reported as:

`priced subtotal + NVIDIA input tokens * assumed input rate + NVIDIA output tokens * assumed output rate`

where assumed rates are explicitly supplied sensitivity assumptions, expressed
per one million tokens. They do not modify the official pricing snapshot or the
normalized total.

## 4. Execution gate

This pricing amendment does not itself authorize live API calls, CLadder
execution, calibration, or locked-test inference. Amendment 004 subsequently
sets all six method configs to `execution_enabled: true` for controlled smoke
execution only. Before any live canary, structural and execution preflight,
smoke artifact validation, and the existing runtime evidence gates must pass
under this policy. NVIDIA's normalized price and actual charge remain `null`;
neither zero nor a proxy price is permitted.
