# P0 Dependency Audit Note

Date: 2026-02-19
Scope: `jarvis-sniper` production dependencies only (`npm audit --omit=dev`)

## Observed Baseline

- Total: 23
- Critical: 0
- High: 19
- Moderate: 3
- Low: 1

## Gate Policy Applied

- Block on any critical vulnerabilities.
- Block if high-severity count regresses above baseline (`19`).
- Keep full-audit and prod-only-audit tracked separately.

## Actionable Runtime Chain

- Highest priority remediation remains the `@bagsfm/bags-sdk` dependency chain.
- Avoid `npm audit fix --force` on production branches due breaking upgrades; isolate through adapter and upgrade in controlled branch.

## Acceptance

- Current branch is non-regressive against the production baseline (high=19, critical=0).
