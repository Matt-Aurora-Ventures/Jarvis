# Dependency Risk Register

Last updated: 2026-02-19
Source of truth: `docs/dependency-risk-register.json` (generated from `npm -C jarvis-sniper audit --json`)

## Snapshot

- Total vulnerabilities: **42**
- Critical: **0**
- High: **32**
- Moderate: **9**
- Low: **1**
- Direct dependencies implicated: `@bagsfm/bags-sdk`, `eslint`, `eslint-config-next`, `vitest`

## Key Findings

1. `@bagsfm/bags-sdk` dependency chain carries high-severity advisories via `axios`, `@solana/spl-token`, and `bigint-buffer`.
2. Lint/tooling chain (`eslint`, `eslint-config-next`, `typescript-eslint`, `minimatch`) contributes many high findings, largely in developer tooling paths.
3. Test/build chain (`vitest`/`vite`) contributes moderate findings and requires a major upgrade to clear.
4. `npm audit fix` cannot resolve this safely without breaking major-version changes.

## Risk Classification

- Runtime-exposed risk: **Medium-High**
- Dev-only risk: **Medium**
- Immediate exploitability in production: **Context dependent** (lower for dev-only transitive packages when production image excludes dev deps)

## Priority Actions

1. **P0 (Blocker for broader public rollout)**
- Isolate and/or replace `@bagsfm/bags-sdk` path behind a narrow adapter interface.
- Build an alternate execution path (direct Jupiter/Bags HTTP or minimal SDK surface) to reduce deep transitive dependency risk.

2. **P1 (Pre-scale hardening)**
- Upgrade test stack (`vitest` + `vite`) in a dedicated branch and re-run full test/build gates.
- Keep `eslint` + `eslint-config-next` pinned to framework-compatible versions; avoid forced downgrades suggested by audit output.

3. **P1 (Deployment hygiene)**
- Ensure production container/image installs production dependencies only (`npm ci --omit=dev`).
- Add CI audit gate that fails on new criticals and tracks high-count delta over time.

4. **P2 (Ongoing governance)**
- Weekly dependency review cadence with signed risk acceptance notes.
- Maintain package-level allowlist/denylist for transitive packages with known exploit history.

## Recommended Rollout Policy

- Private/internal usage can proceed with current mitigations and auth hardening.
- External multi-user rollout should wait for P0 dependency isolation and one clean security review cycle.

## Notes on `npm audit` Suggestions

Audit output currently proposes major-version changes (including non-actionable/unsafe recommendations). These should not be applied automatically. Remediation must be validated against framework compatibility (`next@16.1.6`, React 19 stack) in an isolated branch.

