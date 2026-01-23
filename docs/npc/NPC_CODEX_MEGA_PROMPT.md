# NPC Harness + Control Deck Mega-PR (Codex Cloud Prompt)

This document provides a **single, one-shot Codex Cloud task** that implements the full NPC harness spine **in one PR**, including a lightweight Control Deck UI, unified action aggregation, loss-accounting hooks, and kill/budget enforcement. Use this when you want **Codex (GPT-5.2) to execute everything at once**.

## Scope (what the mega-PR delivers)

**A. Harness Spine**
- Append-only Action Journal (JSONL).
- Action schema definitions.
- Decision gate: propose → approve/reject.
- Validators and identity helpers.
- Loss accounting scaffolding.
- Budget/timeout guardrails.

**B. CLI for actions**
- `jarvis actions list|status|approve|reject|journal|kill`.
- Best-effort sync into `pending_actions.json` from the AI Supervisor.

**C. Control Deck UI (lightweight)**
- Unified view for:
  - AI Supervisor pending actions.
  - Trading approval gate pending approvals.
  - Action journal timeline.
- Approve/Reject buttons (no auto-exec).
- Kill-switch status display.

**D. Unified View + Aggregator**
- Single aggregator module that merges supervisor + trading + journal.

**E. Loss Accounting Hooks**
- LossRecord model + journal event.
- Hook points for compression/summarization (or minimal stub if not present).

## File tree additions (single PR)

**New files**
- `core/harness/__init__.py`
- `core/harness/action_schema.py`
- `core/harness/journal.py`
- `core/harness/decision_gate.py`
- `core/harness/validators.py`
- `core/harness/identity.py`
- `core/harness/loss_accounting.py`
- `core/harness/budgets.py`
- `core/harness/aggregate.py`
- `jarvis_cli/actions.py`
- `tests/unit/test_harness_journal.py`
- `tests/unit/test_decision_gate.py`
- `tests/unit/test_jarvis_actions_cli.py`
- `tests/unit/test_control_deck_api.py` (if API is added)

**Modified files**
- `jarvis_cli/main.py` (register `actions` command group)
- `env.example` (document `ACTION_JOURNAL_PATH`, kill switch env)
- `core/ai_runtime/supervisor/ai_supervisor.py` (optional: journal proposal/decision events; do not change semantics)

## PR plan (single mega-PR)

- **Branch**: `codex/npc-harness-control-deck`
- **Commit message**: `feat: npc harness + control deck spine`
- **Commit count**: 1–3 commits max
- **Acceptance criteria**:
  - `jarvis actions list` works even if AI runtime is disabled (fail-open).
  - Approve/Reject always writes to the journal.
  - No breaking changes to `jarvis up/doctor/validate/deps`.
  - Journal is append-only and path-configurable.
  - Kill switch prevents approvals when enabled.

## Codex Cloud mega-prompt (copy/paste)

> You are working in repo Matt-Aurora-Ventures/Jarvis.
>
> Deliver ONE mega PR that implements:
> A) NPC harness spine: Action Journal (append-only JSONL), schemas, decision gate, validators, identity helpers, loss accounting scaffolding, budgets/timeouts.
> B) `jarvis actions ...` CLI: list/approve/reject/status/journal/kill + best-effort sync into supervisor `pending_actions.json`.
> C) Control Deck UI: a lightweight page or API that shows pending AI supervisor actions, trading approvals, and the journal timeline; includes approve/reject controls that only record decisions.
> D) Unified view module that aggregates supervisor + trading + journal into a merged list.
> E) Loss-accounting hooks: LossRecord model and journal event; integrate into compression/summarization or add a minimal safe stub.
>
> Constraints:
> - Keep dependencies light (prefer stdlib or existing frameworks already in the repo).
> - Do not break existing `jarvis` commands: up/doctor/validate/deps.
> - Preserve fail-open AI Runtime behavior (if AI runtime disabled, UI/CLI should still work and show empty state).
> - Proposal ≠ commitment remains true (no auto-exec).
>
> Repo integration facts:
> 1) AI Supervisor persists pending actions at:
>    Path(AIRuntimeConfig.from_env().log_path).parent / "pending_actions.json"
>    (AI_LOG_PATH defaults to logs/ai_runtime.log)
> 2) AI runtime docs mention “Future: add CLI tool to list/approve actions” — you are implementing it.
> 3) Trading approval patterns exist (core/approval_gate.py); use them rather than inventing a new incompatible system.
> 4) A Control Deck / dashboard direction already exists in docs; make a minimal UI consistent with that.
>
> Branch + PR:
> - Branch: codex/npc-harness-control-deck
> - Single PR with clean commit history (1–3 commits max).
> - Update env.example for ACTION_JOURNAL_PATH and kill switch env name.
>
> ========================
> A) HARNESS SPINE
> ========================
> Create:
> - core/harness/__init__.py
> - core/harness/action_schema.py
> - core/harness/journal.py
> - core/harness/decision_gate.py
> - core/harness/validators.py
> - core/harness/identity.py
> - core/harness/loss_accounting.py
> - core/harness/budgets.py
>
> Implement:
> - ActionProposal with action_id (uuid4), source, intent, scope, payload, created_at, status, budget.
> - ActionDecision with action_id, decided_by, decision, reason/note, decided_at.
> - ActionEvent with event_id, action_id, type, actor, timestamp, data.
>
> Journal:
> - Append-only JSONL at logs/action_journal.jsonl by default.
> - Override via ACTION_JOURNAL_PATH.
> - Methods: append(event), iter_events(filter), latest(action_id), list_actions(status=), summarize_recent(n).
>
> Decision gate:
> - propose(ActionProposal) -> action_id (writes proposed event).
> - approve(action_id, actor, note) -> bool (writes approved event).
> - reject(action_id, actor, reason) -> bool (writes rejected event).
> - list_pending() -> list[ActionProposal] (derived from events).
>
> Validators:
> - validate_proposal_schema
> - validate_kill_switch (reuse existing kill switch env if found)
> - validate_budget
>
> Identity:
> - new_id(prefix="")
> - content_hash(obj) -> sha256
> - canonicalize(obj) -> stable json encoding
>
> Loss accounting:
> - LossRecord(what_removed, why_ok, recovery_pointer, source_ids, created_at)
> - record_loss() writes a journal event type="loss_recorded"
>
> Budgets:
> - Budget defaults (timeout_s=30, max_steps=20, max_cost_usd=0.05)
> - allow overrides but require explicit configuration for risky scopes (trading, self-upgrade)
>
> ========================
> B) JARVIS CLI: actions
> ========================
> Add jarvis_cli/actions.py and wire into jarvis_cli/main.py:
> - jarvis actions list
> - jarvis actions status <action_id>
> - jarvis actions approve <action_id> --note "..." --actor "user"
> - jarvis actions reject <action_id> --reason "..." --actor "user"
> - jarvis actions journal [--tail N]
> - jarvis actions kill [on|off|status] (local file flag or existing env pattern)
>
> Sync behavior:
> - If pending_actions.json exists, approving/rejecting should update that record best-effort (no crash if schema differs).
>
> ========================
> C) CONTROL DECK UI (lightweight)
> ========================
> - If a web framework is already present, add a minimal route/page there.
> - If not, add a tiny built-in server via `jarvis control-deck up --port 8787` that serves:
>   - GET /api/actions (merged list)
>   - POST /api/actions/{id}/approve
>   - POST /api/actions/{id}/reject
>   - GET / (static HTML that calls these APIs)
> - Single-page UI titled “Jarvis Control Deck” with sections:
>   - Pending AI Supervisor Actions
>   - Pending Trading Approvals
>   - Journal Timeline (tail)
> - Approve/Reject buttons call the decision gate; no auto-exec.
> - Show kill-switch status and disable approvals if kill switch is ON.
>
> ========================
> D) UNIFIED VIEW: supervisor + trading + journal
> ========================
> Add core/harness/aggregate.py:
> - read_supervisor_pending() -> list (uses AIRuntimeConfig log_path to locate pending_actions.json)
> - read_trade_pending() -> list (use core/approval_gate.py patterns)
> - read_journal_pending() -> list
> - merge into UnifiedAction objects
>
> Expose this via CLI list and UI /api/actions.
>
> ========================
> E) LOSS ACCOUNTING HOOKS
> ========================
> - If memory compression/summarization exists, wrap it to emit LossRecord with pointers to source IDs.
> - If no compression is found, add core/memory/compression.py with a safe stub `compress_events(events)` returning summary + loss record and a unit test that logs a loss_recorded event.
>
> ========================
> TESTS
> ========================
> Add unit tests:
> - tests/unit/test_harness_journal.py
> - tests/unit/test_decision_gate.py
> - tests/unit/test_jarvis_actions_cli.py
> - tests/unit/test_control_deck_api.py (if API added)
>
> ========================
> RUN + VERIFY
> ========================
> - pytest -q
> - jarvis actions list
> - jarvis control-deck up --port 8787 (if implemented)
>
> Finally output:
> - concise summary
> - file list
> - how to use CLI + UI
> - how this enforces traceability, proposal≠commitment, killability, boundedness, identity hooks, loss accounting hooks.

## Notes
- Keep this prompt as-is for a single Codex Cloud execution.
- If you add a UI endpoint, do **not** auto-execute actions. Only record decisions.
- Preserve “fail-open” behavior when AI runtime is disabled.
