# Change Proposal: <Title>

## 1) Summary (1–3 sentences)
What change is being proposed and why?

## 2) Motivation / Problem Statement
- What problem does this solve?
- Who benefits?
- What failure mode exists today?

## 3) Evidence (Required)
Provide *primary sources* and short summaries.
- Source 1:
  - Link:
  - Key claim:
  - Why it applies to Jarvis:
- Source 2:
  - Link:
  - Key claim:
  - Why it applies to Jarvis:

> Requirement: Every non-trivial claim must be supported by a citation.

## 4) Proposed Change (Technical)
Describe the change precisely.
- Components touched:
- New modules/interfaces:
- Config flags:
- Data model changes:

## 5) Safety & Risk Analysis (Required)
- Worst-case failure mode:
- Likely failure mode:
- Operational risks (timeouts, costs, rate limits, data quality):
- Security risks:
- How will we detect problems early?

## 6) Evaluation Plan (Required)
- Baseline:
- Metrics:
- Acceptance thresholds:
- Test datasets / fixtures:
- Repro steps:
- What would falsify the expected benefit?

## 7) Rollback Plan (Required)
- How to disable quickly (feature flag/config):
- How to revert safely:
- Data cleanup steps (if any):

## 8) Deployment Plan
- Environments:
- Incremental rollout steps:
- Monitoring / alerting:
- Owner on-call:

## 9) Status Checklist
- [ ] Evidence included (citations)
- [ ] Evaluation plan included
- [ ] Tests added/updated
- [ ] Rollback plan defined
- [ ] Feature-flagged if risky
- [ ] Security review if applicable
- [ ] Artifacts saved under `/artifacts/...` for traceability
