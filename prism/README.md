# Prism-Grade Jarvis (Auditable Agent Workflow)

This module implements **Prism-inspired** capabilities for Jarvis:

- Artifact Registry (versioned artifacts + links)
- Decision Ledger + Journal (structured, reproducible records)
- Policy Engine (materiality + transaction cost with HOLD vs EXECUTE)
- Risk/Compliance gatekeeper
- Executor (approved steps only)
- Auditor (post-run compliance report)

## Structure

```
prism/
  package.json
  tsconfig.json
  core/
    ledger.ts
    persistence.ts
    state.ts
    workflow.ts
  agents/
    auditor.ts
    executor.ts
    framework.ts
    journal_writer.ts
    research.ts
    risk_officer.ts
  policy/
    cost_model.ts
    materiality.ts
    policy_engine.ts
  artifacts/
    registry.ts
  schemas/
    audit.ts
    framework.ts
    journal.ts
  examples/
    demo_run.ts
```

## How to run the example

```
cd prism
npm install
npm run demo
```

## How HOLD decisions work

The `PolicyEngine` rejects actions when:

- materiality is below threshold,
- transaction costs exceed expected benefit,
- regime/constraints do not allow the action.

It returns structured reasons and thresholds checked for auditing.

## Replayability & Logs

All workflow steps are persisted through the `PersistenceLayer` interface.
The `DecisionLedger` stores journal + audit records for each run.
