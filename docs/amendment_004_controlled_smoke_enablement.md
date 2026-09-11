# Amendment 004 - Controlled Smoke Execution Enablement

**Decision date:** 2026-09-12

**Status:** configuration execution enabled; live canary pending separate authorization

**Applies to:** the sealed CLadder smoke split only

## 1. Decision

All six frozen method configs set `execution_enabled: true` only so the
smoke-only controller can execute the predeclared three-item canary and, after
that canary passes, smoke-60. This setting does not authorize a call by itself.
Live execution still requires `--authorize-live-smoke`, execution preflight,
the exact sealed label-free smoke view, the frozen provider/model roster, and
the fixed controller ceilings.

Calibration-300 and locked-test-600 remain unauthorized. The controller and
CLI continue to reject every split other than `smoke`.

## 2. Mandatory sequence

The live canary is exactly three smoke items: the deterministic lowest opaque
item ID from each rung. It has run ID `cladder-smoke-canary-3`, 51 logical
calls, at most 204 transport attempts, and a zero-terminal-error ceiling.

The canary must run and pass before any smoke-60 live run. The controller never
starts smoke-60 automatically. Smoke-60 has a separate run ID and is blocked
unless the frozen canary manifest and summary prove all 51 logical calls
completed with zero terminal errors.

If the canary fails, is incomplete, has an ambiguous in-flight attempt, or
produces an invalid artifact, smoke-60 remains blocked. There is no automatic
retry of a terminal canary and no provider substitution.

## 3. Preserved safety and accounting rules

- C1 remains an alias of A1 and schedules no additional call.
- Items and configs execute in deterministic order; logical call IDs remain a
  deterministic function of split, config ID, opaque local item ID, and
  topology position.
- Models receive only the frozen rendered question context and authorized
  upstream evidence cards. Item IDs, rung, labels, ground truth, and protected
  metadata stay outside prompts.
- Wrapper retries remain capped at three after the initial attempt. Pacing is
  applied before every transport attempt, including retries.
- Attempt journals are created atomically before transport. Completed call
  records, summaries, and manifest transitions are atomic and never overwrite
  terminal artifacts. An ambiguous in-flight marker blocks automatic resume.
- Artifacts contain no credentials or authorization metadata. Raw model output
  is local-only under the ignored run root.
- Input, output, reasoning, and cached-input usage remain separate nullable
  fields. Missing usage is not converted to zero for cost estimation.
- `normalized_list_cost_usd` and provider-reported `actual_charge_usd` remain
  separate. NVIDIA retains `normalized_list_cost_usd: null`,
  `actual_charge_usd: null`, and `billing_mode: free_prototype` under Amendment
  003; no zero or proxy NVIDIA price is permitted.

## 4. Canary pass gate

Before smoke-60 can be separately authorized, all of the following must hold:

1. The canary command exits successfully and produces the expected run ID.
2. Its manifest is `frozen` with `run_status: complete`.
3. Its summary records 51 expected and completed logical calls and zero
   terminal errors.
4. Provider counts are Groq 33, NVIDIA NIM 6, Gemini 3, Cloudflare Workers AI
   3, and OpenAI 6; transport attempts do not exceed 204.
5. Every call has an exact provider/model identity, a terminal `YES` or `NO`,
   and an auditable attempt record with valid retry accounting.
6. NVIDIA accounting remains symbolic-null, no secret-bearing artifact exists,
   and all artifact/resume integrity checks pass.

Any failed criterion blocks smoke-60 pending explicit review and a new decision.
