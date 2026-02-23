# Arena Protocol v2 (Noise-Filtered)

Status: Normative  
Version: 2.0.0  
Last Updated: 2026-02-23

## 1. Purpose and Non-Goals
This specification defines a deterministic, machine-checkable Arena review protocol for multi-agent refinement with optional Notebook grounding hooks.

This protocol MUST cover:
1. Arena core loop (`Planner`, `Reviewer`, `Finalizer`)
2. Deterministic verdict parsing and loop termination
3. Notebook timing hooks (`before`, `during`, `after`)
4. GSD-aligned safety constraints from `docs/ULTIMATE_MASTER_GSD_UPDATE_JAN_31_1515.md`

This protocol MUST NOT define:
1. Database schema, API routes, or worker framework internals
2. Deployment operations, billing/admin workflows, or infrastructure runbooks
3. Creative/content planning, marketing scheduling, or unrelated task workflows

## 2. Normative Language and Compliance Levels
The keywords `MUST`, `MUST NOT`, `REQUIRED`, `SHOULD`, `SHOULD NOT`, and `MAY` are normative.

Compliance levels:
1. `Compliant`: All `MUST` and `MUST NOT` requirements are satisfied.
2. `Conditionally Compliant`: All `MUST` requirements are satisfied and one or more `SHOULD` requirements are not satisfied with explicit justification.
3. `Non-Compliant`: Any `MUST` or `MUST NOT` requirement is violated.

## 3. Roles and Trust Boundaries
### 3.1 Normative Roles
1. `Planner`: Produces initial and revised drafts.
2. `Reviewer`: Critiques drafts and emits a terminal verdict line.
3. `Finalizer`: Produces final output after approval or max-round termination.
4. `Orchestrator`: Protocol state authority that enforces transitions and parsing.
5. `Notebook Service`: External evidence service queried during protocol hooks.

### 3.2 Trust Boundaries
1. `Reviewer` execution mode MUST be `read-only`.
2. `Orchestrator` MUST treat `Reviewer` output as untrusted text until parsed.
3. `Orchestrator` MUST never infer verdict intent from prose; only parsed verdict grammar is valid.
4. `Notebook Service` failures MUST be handled by explicit fallback rules in Section 9.

### 3.3 Illustrative Mapping (Non-Normative)
Example mapping in a current stack:
1. `Planner` -> Friday
2. `Reviewer` -> Arsenal
3. `Finalizer` -> Jocasta

This mapping is illustrative only and MUST NOT be treated as protocol contract.

## 4. Inputs (Canonical Contracts)
### 4.1 `ProtocolConfig`
```json
{
  "max_rounds": 5,
  "session_resume_required": true,
  "reviewer_mode": "read-only",
  "notebook_enabled": true
}
```

Constraints:
1. `max_rounds` MUST be an integer in `[1, 5]`.
2. Default `max_rounds` MUST be `5`.
3. `session_resume_required` MUST be `true`.
4. `reviewer_mode` MUST be exactly `read-only`.
5. `notebook_enabled` MUST be boolean.

### 4.2 `TaskContext`
```json
{
  "task_id": "string",
  "initial_prompt": "string",
  "session_id": "string",
  "round_history_refs": [],
  "notebook_required": false
}
```

Constraints:
1. `task_id`, `initial_prompt`, and `session_id` MUST be present.
2. `notebook_required` MUST default to `false` if omitted.
3. `round_history_refs` SHOULD contain immutable references to prior round artifacts.

### 4.3 `NotebookContext`
```json
{
  "notebook_id": "string",
  "profile": "enterprise|personal|auto",
  "tools": [
    "notebook_describe",
    "notebook_query",
    "studio_create"
  ]
}
```

Constraints:
1. If `ProtocolConfig.notebook_enabled=true`, `NotebookContext.notebook_id` MUST be provided.
2. `tools` MUST include `notebook_query`.
3. `studio_create` MAY be absent; see Section 8.3.

### 4.4 `ProtocolState`
Allowed states are exactly:
1. `INIT`
2. `SEEDING`
3. `DRAFTING`
4. `REVIEWING`
5. `REVISING`
6. `FINALIZING`
7. `TERMINATED_APPROVED`
8. `TERMINATED_MAX_ROUNDS`
9. `TERMINATED_ERROR`

### 4.5 `ReviewerVerdict`
Terminal verdict line MUST be exactly one of:
1. `VERDICT: APPROVED`
2. `VERDICT: REVISE`

### 4.6 `RoundRecord`
```json
{
  "round_index": 1,
  "planner_output_ref": "string",
  "reviewer_output_ref": "string",
  "verdict": "APPROVED|REVISE",
  "issues": [],
  "timestamp": "RFC3339"
}
```

### 4.7 `NotebookHookResult`
```json
{
  "phase": "before|during|after",
  "query": "string",
  "evidence_refs": [],
  "status": "SUCCESS|FAILED|SKIPPED_DISABLED|SKIPPED_DEGRADED"
}
```

## 5. State Model and Transitions
### 5.1 Transition Table
| From | To | Entry Condition | Exit Condition |
|---|---|---|---|
| `INIT` | `SEEDING` | Protocol starts and `notebook_enabled=true` | Before-hook completes or fails per Section 9 |
| `INIT` | `DRAFTING` | Protocol starts and `notebook_enabled=false` | Planner invocation starts |
| `SEEDING` | `DRAFTING` | Before-hook succeeds or degrades legally | Planner output is generated |
| `DRAFTING` | `REVIEWING` | Planner output exists for current round | Reviewer invocation starts |
| `REVIEWING` | `FINALIZING` | Parsed verdict is `APPROVED` | Finalizer invocation starts |
| `REVIEWING` | `REVISING` | Parsed verdict is `REVISE` | Round is recorded |
| `REVISING` | `DRAFTING` | `round_index < max_rounds` | Next planner revision starts |
| `REVISING` | `TERMINATED_MAX_ROUNDS` | `round_index == max_rounds` and verdict is `REVISE` | Finalizer receives termination context |
| Any non-terminal | `TERMINATED_ERROR` | Unrecoverable protocol error | Run is closed with error reason |
| `FINALIZING` | `TERMINATED_APPROVED` | Finalizer completes successfully | Run is closed as approved |

### 5.2 Transition Rules
1. Orchestrator MUST persist state on every transition.
2. Orchestrator MUST reject undefined transitions.
3. Terminal states (`TERMINATED_APPROVED`, `TERMINATED_MAX_ROUNDS`, `TERMINATED_ERROR`) MUST be absorbing.

## 6. Round Execution Algorithm
1. Initialize state as `INIT`, set `round_index=0`.
2. Validate `ProtocolConfig`; if invalid, transition to `TERMINATED_ERROR`.
3. If `session_resume_required=true` and no valid `session_id`, transition to `TERMINATED_ERROR`.
4. If `notebook_enabled=true`, run before-hook and transition through `SEEDING` (Section 8.1).
5. Enter `DRAFTING`; increment `round_index` by 1 for a new round.
6. Invoke `Planner` with `initial_prompt` + prior critiques + required evidence refs.
7. Persist planner artifact reference as `planner_output_ref`.
8. Enter `REVIEWING`; invoke `Reviewer` in `read-only` mode using session resume.
9. Parse verdict from reviewer output using Section 7.
10. If verdict parse fails, apply missing-verdict rule (Section 9.1).
11. Persist `RoundRecord`.
12. If verdict is `APPROVED`, transition to `FINALIZING`.
13. If verdict is `REVISE` and `round_index < max_rounds`, transition `REVISING` then next `DRAFTING`.
14. If verdict is `REVISE` and `round_index == max_rounds`, transition to `TERMINATED_MAX_ROUNDS`.
15. In `FINALIZING`, run after-hook and final output synthesis; terminate with `TERMINATED_APPROVED` on success.

## 7. Reviewer Output Grammar and Parsing Rules
### 7.1 Normative Output Contract
`Reviewer` MUST include exactly one terminal verdict line and SHOULD place it as the last non-empty line.

### 7.2 Grammar
```text
review_output = *(any_line LF) verdict_line [LF]
verdict_line  = "VERDICT: APPROVED" / "VERDICT: REVISE"
```

### 7.3 Parser Behavior (Deterministic)
1. Parser MUST scan all lines for regex `^\\s*VERDICT:\\s*(APPROVED|REVISE)\\s*$` case-insensitive.
2. If exactly one match exists, parser MUST canonicalize verdict to uppercase token.
3. If multiple matches exist, parser MUST select the last match and log `PARSER_WARNING_MULTIPLE_VERDICTS`.
4. If no match exists, parser MUST emit `PARSER_ERROR_MISSING_VERDICT`.
5. Parser MUST ignore all non-matching prose.

## 8. Notebook Timing Hooks
### 8.1 Before Loop (`phase=before`)
If `notebook_enabled=true`, `Planner` MUST perform context seeding using equivalent intent of:
1. `notebook_describe`
2. `notebook_query`

Output MUST be recorded as `NotebookHookResult` with `phase=before`.

### 8.2 During Loop (`phase=during`)
If `notebook_enabled=true`, `Reviewer` MUST cross-check material claims against notebook evidence before emitting verdict.

Requirements:
1. At least one evidence query per review pass.
2. Evidence references MUST be included in review output or issue list.
3. Hook output MUST be recorded as `NotebookHookResult` with `phase=during`.

### 8.3 After Loop (`phase=after`)
If `notebook_enabled=true`, `Finalizer` MUST perform a drift-check query before final output.

Optional behavior:
1. `Finalizer` MAY call `studio_create` for artifact generation.
2. If `studio_create` is unavailable, protocol MUST continue without failure unless explicitly required by task policy.

## 9. Failure Modes and Deterministic Fallbacks
### 9.1 Missing Verdict Line
1. On `PARSER_ERROR_MISSING_VERDICT`, orchestrator MUST retry reviewer invocation once.
2. If retry still has no valid verdict, transition to `TERMINATED_ERROR`.

### 9.2 Multiple Verdict Lines
1. Last matched verdict MUST be used.
2. Parser warning MUST be logged.

### 9.3 Endless Revise Cycle
1. If `round_index` reaches `max_rounds` with verdict `REVISE`, transition to `TERMINATED_MAX_ROUNDS`.
2. Finalizer SHOULD still produce best-effort output with unresolved-issues notice.

### 9.4 Notebook Unavailable
1. If `notebook_required=false`, orchestrator MAY continue in degraded mode and log `SKIPPED_DEGRADED`.
2. If `notebook_required=true`, orchestrator MUST transition to `TERMINATED_ERROR` with explicit reason.

### 9.5 Session Resume Missing
1. If `session_resume_required=true` and resume context is missing, protocol MUST hard-fail to `TERMINATED_ERROR`.
2. Stateless re-review MUST NOT be used as substitute.

## 10. Safety and GSD Guardrails
The following are REQUIRED guardrails:
1. Non-destructive operation only (`MUST NOT` include deletion/reset semantics in protocol actions).
2. No breaking changes to active dependencies implied by protocol behavior.
3. No secrets in protocol artifacts, logs, or examples.
4. Reviewer execution MUST remain `read-only`.
5. Notebook integration MUST use MCP/CLI semantics and MUST NOT depend on custom unofficial API wrappers.
6. Protocol decisions MUST prefer integration-safe behavior when equivalent utility exists.
7. All fallback paths MUST be explicit and auditable.

## 11. Audit Trail Requirements
Orchestrator MUST persist an auditable run record containing:
1. Effective `ProtocolConfig`
2. Full state transition history with timestamps
3. All `RoundRecord` entries in order
4. All `NotebookHookResult` entries for `before|during|after`
5. Parser warnings/errors
6. Terminal state and terminal reason

Minimum required events:
1. `RUN_STARTED`
2. `STATE_TRANSITION`
3. `ROUND_RECORDED`
4. `HOOK_EXECUTED`
5. `PARSER_WARNING` or `PARSER_ERROR` when applicable
6. `RUN_TERMINATED`

## 12. Conformance Checklist
A run is protocol-conformant only if all checks pass:
1. `ProtocolConfig` satisfies Section 4.1 constraints.
2. All states are in the allowed `ProtocolState` enum.
3. All transitions follow Section 5.1.
4. Reviewer mode is enforced as `read-only`.
5. Verdict parsing follows Section 7.3 exactly.
6. Missing verdict handling uses exactly one retry.
7. `max_rounds` cap is enforced.
8. Session resume is enforced when required.
9. Notebook hooks execute for enabled phases.
10. After-hook includes mandatory drift-check query.
11. `studio_create` is optional, not mandatory.
12. Audit trail contains all required events and records.
13. No prohibited excess content is introduced into protocol artifacts.

