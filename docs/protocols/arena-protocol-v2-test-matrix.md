# Arena Protocol v2 Test Matrix

Status: Normative compliance suite  
Last Updated: 2026-02-23

## 1. Test Harness Assumptions
1. Protocol implementation follows `docs/protocols/arena-protocol-v2.md`.
2. Initial defaults:
   - `max_rounds=5`
   - `session_resume_required=true`
   - `reviewer_mode=read-only`
3. Test harness can force notebook success/failure and parse outcomes.
4. Every run emits full audit trail events.

## 2. Required Fixtures
1. `fixture/task_context_valid.json`
2. `fixture/notebook_context_valid.json`
3. `fixture/reviewer_outputs/` with deterministic variants
4. `fixture/session_resume/` with valid and missing resume tokens

## 3. Scenario Matrix
| ID | Scenario | Setup | Steps | Expected State Path | Pass Criteria |
|---|---|---|---|---|---|
| T01 | Happy path approve in round 1 | Notebook enabled, valid session, reviewer emits `VERDICT: APPROVED` | Run protocol once | `INIT -> SEEDING -> DRAFTING -> REVIEWING -> FINALIZING -> TERMINATED_APPROVED` | Terminal state is `TERMINATED_APPROVED`, one `RoundRecord`, all hooks recorded |
| T02 | Revise then approve in rounds 2-3 | Reviewer emits `REVISE` then `APPROVED` | Execute until approved | `INIT -> ... -> REVIEWING -> REVISING -> DRAFTING -> REVIEWING -> FINALIZING -> TERMINATED_APPROVED` | Exactly two or three rounds, final verdict approved, prior critique applied |
| T03 | Max-round termination at cap | Reviewer always emits `REVISE` | Run until cap | `INIT -> ... -> (DRAFTING/REVIEWING/REVISING x max_rounds) -> TERMINATED_MAX_ROUNDS` | Stops at configured `max_rounds`, no extra round is executed |
| T04 | Missing verdict response | Reviewer output has no verdict line twice | Execute with one retry policy | `... -> REVIEWING -> REVIEWING(retry) -> TERMINATED_ERROR` | Exactly one retry, terminal reason indicates missing verdict |
| T05 | Multiple verdict lines | Reviewer output includes two verdict lines | Parse once | `... -> REVIEWING -> (REVISING or FINALIZING)` based on last verdict | Parser warning emitted, last verdict selected deterministically |
| T06 | Non-terminal prose after verdict | Reviewer returns verdict not as last line plus extra prose | Parse and continue | `... -> REVIEWING -> (state by parsed verdict)` | Parser still resolves verdict line, ignores trailing prose |
| T07 | Notebook contradictory evidence | During hook returns evidence contradicting planner claim | Execute review pass | `... -> REVIEWING -> REVISING` (unless reviewer still approves with explicit rationale) | Review output references evidence and issue list includes contradiction |
| T08 | Notebook timeout in before/during/after | Force notebook timeout per phase | Run per phase with required/non-required variants | `INIT -> TERMINATED_ERROR` when required, else degraded flow with continuation | Required mode fails explicitly; optional mode logs `SKIPPED_DEGRADED` and proceeds |
| T09 | Session resume continuity across rounds | Valid resume token in round 1 and 2 | Run revise then approve | `... -> REVISING -> DRAFTING -> REVIEWING -> ...` | Round 2 review references unresolved items from round 1; no stateless reset |
| T10 | Parser robustness casing/whitespace | Verdict lines use mixed case and extra spaces | Run parser | `... -> REVIEWING -> (state by canonicalized verdict)` | Regex accepts whitespace/case variations, canonicalizes to `APPROVED`/`REVISE` |
| T11 | Safety check reviewer read-only | Attempt write operation from reviewer sandbox | Execute review pass | `... -> REVIEWING -> TERMINATED_ERROR` or blocked continue with violation event | Write action blocked, violation logged, protocol does not treat side-effectful output as valid review |
| T12 | Relevance filter compliance | Inject excess operational text into candidate spec inputs | Build protocol artifact from mixed inputs | N/A (artifact validation test) | Final protocol artifact contains no excluded categories and no credential-like strings |

## 4. Detailed Assertions by Scenario
### T01
1. `RoundRecord.round_index == 1`
2. `RoundRecord.verdict == "APPROVED"`
3. `NotebookHookResult` exists for `before`, `during`, `after`

### T02
1. At least one round has verdict `REVISE`
2. Final round has verdict `APPROVED`
3. Transition from `REVISING` to `DRAFTING` occurs before finalization

### T03
1. Final state is `TERMINATED_MAX_ROUNDS`
2. `round_index == max_rounds`
3. Finalizer receives unresolved-issues notice

### T04
1. Exactly one reviewer retry occurs
2. Final state is `TERMINATED_ERROR`
3. Terminal reason includes `PARSER_ERROR_MISSING_VERDICT`

### T05
1. `PARSER_WARNING_MULTIPLE_VERDICTS` is emitted
2. Last verdict line determines next state

### T06
1. Parsed verdict remains valid despite trailing prose
2. No false parser error is emitted

### T07
1. Evidence references are present in reviewer output or issues list
2. Contradiction is reflected in persisted `issues[]`

### T08
1. Required mode: run terminates with explicit notebook failure reason
2. Optional mode: run continues and logs `SKIPPED_DEGRADED`

### T09
1. Missing resume token forces `TERMINATED_ERROR` when required
2. Valid resume token preserves continuity claims across rounds

### T10
1. Input `verdict: approveD` with spaces still resolves to canonical `APPROVED`
2. No ambiguous parse when one valid match exists

### T11
1. Reviewer write attempt is blocked or rejected
2. Audit trail includes safety violation event

### T12
1. Artifact excludes infra telemetry, billing/admin chatter, and creative backlog content
2. Artifact excludes any secret/token/password-like strings

## 5. Exit Criteria for Protocol Compliance
A protocol implementation is acceptable only when:
1. All 12 scenarios pass.
2. No `MUST` requirement in the protocol spec is violated.
3. Audit trail coverage is complete for all tested runs.

