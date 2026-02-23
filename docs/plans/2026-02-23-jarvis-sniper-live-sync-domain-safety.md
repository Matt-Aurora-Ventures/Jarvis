# Jarvis Sniper Live Sync + Domain Safety Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Deploy only already-existing, validated Jarvis Sniper algorithm/runtime upgrades to production, keep current domain availability, add `jarvislife.cloud`, and remove unsafe connection warnings without introducing new features.

**Architecture:** Use a release-candidate branch from clean `origin/main`, selectively include only upgrades that modify existing live surfaces, run strict regression gates, then deploy via Firebase Hosting hardened flow. Handle domain safety in Firebase/DNS and app allowlists so both legacy and new domains function during cutover.

**Tech Stack:** Next.js 16 (App Router), Firebase Hosting (frameworks backend on Cloud Run), GitHub Actions, gcloud, PowerShell scripts, Phantom wallet integration

---

## Scope and Guardrails

- No net-new product features, no new dashboard sections, no schema changes.
- Only changes to existing live routes/components/configuration are allowed.
- Exclude experimental/new-surface additions from this release train (for example new folders under `jarvis-sniper/src/app/api/data/`, `jarvis-sniper/src/app/api/execution/`, and other unshipped endpoints).
- Keep legacy canonical host reachable while enabling `jarvislife.cloud`.
- Fix unsafe-access symptoms by eliminating invalid host usage (`www.kr8tiv.web.app`) and by completing SSL/domain verification.

## Acceptance Criteria

- Production deploy passes health/version checks on both the current host and `jarvislife.cloud`.
- No browser TLS warning on official URLs used by users.
- Phantom wallet connect flow works on desktop and mobile entry paths.
- All release gates pass: tests, lint, build, and smoke checks.
- Rollback instructions are validated before cutover.

### Task 1: Build Release Candidate Inventory (What ships vs what waits)

**Files:**
- Create: `docs/operations/2026-02-23-sniper-live-sync-inventory.md`
- Test: `jarvis-sniper/src/__tests__/production-hardening.test.ts`

**Step 1: Capture baseline and current production pointers**

Run:
```bash
git fetch origin --prune
git log --oneline --decorate -n 30 -- jarvis-sniper
git rev-parse origin/main
```

Expected: You have a clear production baseline SHA and recent sniper commit list.

**Step 2: List local and GitHub candidate changes touching Jarvis Sniper**

Run:
```bash
git status --short jarvis-sniper
git diff --name-status origin/main...HEAD -- jarvis-sniper
```

Expected: A concrete changed-file set including tracked modifications and untracked additions.

**Step 3: Classify each change as `ship-now` or `defer`**

- `ship-now`: bugfix/hardening/perf changes in existing live surfaces.
- `defer`: net-new feature surfaces, new API namespaces, or behavior-expanding changes.

**Step 4: Record decisions with reason + risk score**

- Populate `docs/operations/2026-02-23-sniper-live-sync-inventory.md` with:
  - file path
  - classification
  - risk level
  - validation required

**Step 5: Commit**

```bash
git add docs/operations/2026-02-23-sniper-live-sync-inventory.md
git commit -m "docs(sniper): classify live-sync release inventory"
```

### Task 2: Create Clean Release Branch and Apply Only Approved Upgrades

**Files:**
- Modify: `jarvis-sniper/src/lib/backtest-engine.ts` (only if classified `ship-now`)
- Modify: `jarvis-sniper/src/lib/strategy-selector.ts` (only if classified `ship-now`)
- Modify: `jarvis-sniper/src/hooks/useBacktest.ts` (only if classified `ship-now`)
- Test: `jarvis-sniper/src/__tests__/backtest-route-execution-realism.test.ts`

**Step 1: Create an isolated release branch from clean main**

Run:
```bash
git checkout -b release/sniper-live-sync-2026-02-23 origin/main
```

Expected: branch is clean and starts from deploy baseline.

**Step 2: Apply only approved commits/chunks**

Run (example):
```bash
git cherry-pick -x <approved_commit_sha>
```

Expected: only `ship-now` items are present in branch diff.

**Step 3: Re-check for accidental feature creep**

Run:
```bash
git diff --name-status origin/main...HEAD -- jarvis-sniper
```

Expected: no unexpected new feature files in release diff.

**Step 4: Run focused regression tests for touched algo/runtime areas**

Run:
```bash
npm -C jarvis-sniper run test -- src/__tests__/backtest-route-execution-realism.test.ts
npm -C jarvis-sniper run test -- src/__tests__/bags-backtest.test.ts
```

Expected: PASS.

**Step 5: Commit**

```bash
git add jarvis-sniper
git commit -m "fix(sniper): sync approved algo/runtime upgrades for live release"
```

### Task 3: Domain Safety + Multi-Domain Compatibility Updates

**Files:**
- Modify: `jarvis-sniper/src/lib/backtest-cors.ts`
- Modify: `jarvis-sniper/scripts/autonomy/setup-hourly-scheduler.ps1`
- Modify: `.github/workflows/jarvis-sniper-firebase-deploy.yml`
- Modify: `jarvis-sniper/.env.example`
- Modify: `jarvis-sniper/DEPLOYMENT.md`
- Test: `jarvis-sniper/src/__tests__/production-hardening.test.ts`

**Step 1: Add new domain(s) to allowlists where origin checks exist**

- Add `https://jarvislife.cloud` and `https://www.jarvislife.cloud` to `ALLOWED_ORIGINS` set in `jarvis-sniper/src/lib/backtest-cors.ts`.

**Step 2: Set canonical-origin guidance to custom domain**

- Update `jarvis-sniper/.env.example` examples so `NEXT_PUBLIC_CANONICAL_ORIGIN` points to `https://jarvislife.cloud`.

**Step 3: Keep scheduler and CI smoke checks aligned with canonical host**

- Update default `BaseUrl` in `jarvis-sniper/scripts/autonomy/setup-hourly-scheduler.ps1`.
- Update CI env `CANONICAL_HOST` and smoke checks in `.github/workflows/jarvis-sniper-firebase-deploy.yml`.

**Step 4: Document TLS gotcha and official URLs**

- In `jarvis-sniper/DEPLOYMENT.md`, explicitly mark `www.kr8tiv.web.app` as invalid (cert mismatch) and publish approved entry URLs.

**Step 5: Run regression check**

Run:
```bash
npm -C jarvis-sniper run test -- src/__tests__/production-hardening.test.ts
```

Expected: PASS.

**Step 6: Commit**

```bash
git add jarvis-sniper/src/lib/backtest-cors.ts jarvis-sniper/scripts/autonomy/setup-hourly-scheduler.ps1 .github/workflows/jarvis-sniper-firebase-deploy.yml jarvis-sniper/.env.example jarvis-sniper/DEPLOYMENT.md
git commit -m "chore(sniper): align canonical host and domain safety configuration"
```

### Task 4: Firebase Domain Attachment and SSL Completion (Console + DNS)

**Files:**
- Create: `docs/operations/2026-02-23-domain-cutover-runbook.md`
- Test: `jarvis-sniper/DEPLOYMENT.md`

**Step 1: Add custom domain in Firebase Hosting**

- In Firebase Hosting for project `kr8tiv`, add:
  - `jarvislife.cloud`
  - `www.jarvislife.cloud` (redirect to apex optional but recommended)
- Keep existing Firebase domain active (do not remove current host).

**Step 2: Apply DNS records exactly as Firebase provides**

- Add TXT verification and A/AAAA records at domain provider.
- Keep TXT ownership records persistent for certificate renewal.

**Step 3: Wait for status `Connected` and cert provisioning**

- Track status in Firebase console until SSL cert includes new domains.
- Do not announce new domain as primary until status is fully connected.

**Step 4: Verify cert and response for each approved URL**

Run:
```bash
curl.exe -I --ssl-no-revoke https://jarvislife.cloud
curl.exe -I --ssl-no-revoke https://www.jarvislife.cloud
curl.exe -I --ssl-no-revoke https://kr8tiv.web.app
```

Expected: valid TLS and non-error HTTP responses on approved hosts.

**Step 5: Commit runbook**

```bash
git add docs/operations/2026-02-23-domain-cutover-runbook.md
git commit -m "docs(ops): add domain cutover and SSL verification runbook"
```

### Task 5: Pre-Deploy Quality Gate (No-Break Release Gate)

**Files:**
- Test: `jarvis-sniper/src/__tests__/bags-swap-route.test.ts`
- Test: `jarvis-sniper/src/__tests__/session-wallet-portfolio-route.test.ts`
- Test: `jarvis-sniper/src/__tests__/production-hardening.test.ts`

**Step 1: Run targeted high-risk suites**

Run:
```bash
npm -C jarvis-sniper run test -- src/__tests__/bags-swap-route.test.ts
npm -C jarvis-sniper run test -- src/__tests__/session-wallet-portfolio-route.test.ts
npm -C jarvis-sniper run test -- src/__tests__/production-hardening.test.ts
```

Expected: PASS.

**Step 2: Run full release gates**

Run:
```bash
npm -C jarvis-sniper run test
npm -C jarvis-sniper run lint
npm -C jarvis-sniper run build
npm -C jarvis-sniper run check:real-data-only
```

Expected: all commands succeed.

**Step 3: Record gate evidence**

- Save command outputs and SHAs into `docs/operations/2026-02-23-sniper-live-sync-inventory.md`.

### Task 6: Production Deploy and Post-Deploy Validation

**Files:**
- Modify: `jarvis-sniper/scripts/post-deploy-cloud-run-hardening.ps1` (only if required by gate evidence)
- Test: `.github/workflows/jarvis-sniper-firebase-deploy.yml`

**Step 1: Capture rollback anchor before deploy**

Run:
```bash
gcloud run services describe ssrkr8tiv --project kr8tiv --region us-central1 --format="value(status.latestReadyRevisionName)"
```

Expected: previous revision captured for rollback.

**Step 2: Deploy using hardened production path**

Run:
```bash
npm -C jarvis-sniper run deploy:hardened
```

Expected: Hosting deploy succeeds and Cloud Run hardening script passes.

**Step 3: Smoke-check health/version and core UI routes**

Run:
```bash
curl -fsS https://jarvislife.cloud/api/health
curl -fsS https://jarvislife.cloud/api/version
curl -fsS https://kr8tiv.web.app/api/health
curl -fsS https://kr8tiv.web.app/api/version
```

Expected: successful responses from both domains.

**Step 4: Manual wallet-connect sanity check**

- Desktop: connect Phantom in app, verify no unsafe warning and successful connect.
- Mobile: open via deep-link flow and verify connect modal behavior.

### Task 7: Phantom Program Readiness Prep (No Feature Upload)

**Files:**
- Create: `jarvis-sniper/docs/phantom-program-readiness.md`
- Modify: `jarvis-sniper/README.md` (deployment URL + wallet support notes only)

**Step 1: Assemble app metadata package**

- App name, short description, icon, support contact, privacy/terms URLs.
- Official production URL set to verified domain.

**Step 2: Complete Phantom Portal operational requirements**

- Verify production domain ownership in Phantom Portal.
- Set allowed origins and redirect URLs to `https://jarvislife.cloud` (+ any required secondary domain).
- Confirm access mode plan (`PRIVATE` for staged rollout, then `PUBLIC` when approved).

**Step 3: Validate connect policy alignment**

- Confirm no private key handling server-side is accurately documented.
- Confirm wallet connection UX language matches current behavior (Phantom mode vs Session Wallet mode).

**Step 4: Commit**

```bash
git add jarvis-sniper/docs/phantom-program-readiness.md jarvis-sniper/README.md
git commit -m "docs(sniper): prepare phantom developer program submission package"
```

## Final Verification Gate

Run in order:

```bash
npm -C jarvis-sniper run test
npm -C jarvis-sniper run lint
npm -C jarvis-sniper run build
npm -C jarvis-sniper run deploy:hardened
curl -fsS https://jarvislife.cloud/api/health
curl -fsS https://kr8tiv.web.app/api/health
```

Expected: all gates pass, deployment is healthy, and both domains serve safely.

## Rollback Procedure (Must be ready before cutover)

1. Retrieve previous revision from pre-deploy notes.
2. Repoint Cloud Run traffic back to previous stable revision.
3. Re-run health checks on legacy host.
4. Announce rollback completion and root-cause follow-up ticket before retry.

