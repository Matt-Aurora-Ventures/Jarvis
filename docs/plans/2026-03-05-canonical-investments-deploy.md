# Canonical Investments Deploy Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Deploy the canonical investments experience through `jarvis-sniper` and `services/investments`, remove non-canonical live dependencies, and leave unfinished automation off.

**Architecture:** The investments backend remains a standalone FastAPI service deployed separately from the frontend. `jarvis-sniper` proxies all `/api/investments/*` traffic to that backend, and the live UI is limited to the canonical `jarvis-sniper` investments workspace with staged-rollout controls for safe rollback.

**Tech Stack:** Next.js (`jarvis-sniper`), FastAPI (`services/investments`), Cloud Run, Firebase Hosting, Playwright smoke tests, pytest, PowerShell deployment scripts.

---

### Task 1: Baseline The Canonical Investments Surface

**Files:**
- Inspect: `jarvis-sniper/src/components/investments/InvestmentsPageClient.tsx`
- Inspect: `jarvis-sniper/src/components/investments/AlvaraBasketPanel.tsx`
- Inspect: `jarvis-sniper/src/components/investments/useInvestmentData.ts`
- Inspect: `jarvis-sniper/src/lib/investments/normalizers.ts`
- Test: `jarvis-sniper/src/app/api/investments/**`

**Step 1: Write the failing test**

Add or extend a focused UI/API contract test that verifies the live investments workspace does not expose disabled or unfinished panels when the canonical investments surface is enabled.

**Step 2: Run test to verify it fails**

Run: `npm --prefix jarvis-sniper test -- --runInBand`

Expected: a failing test that documents the current extra/unfinished live surface behavior.

**Step 3: Write minimal implementation**

Adjust the canonical `jarvis-sniper` investments workspace so the visible operator path is limited to the intended live controls and does not depend on legacy surfaces.

**Step 4: Run test to verify it passes**

Run: `npm --prefix jarvis-sniper test -- --runInBand`

Expected: PASS for the focused investments UI contract test.

**Step 5: Commit**

```bash
git add jarvis-sniper/src/components/investments jarvis-sniper/src/lib/investments
git commit -m "fix(sniper): streamline canonical investments workspace"
```

### Task 2: Harden The Investments Proxy And Rollout Gates

**Files:**
- Inspect: `jarvis-sniper/.env.example`
- Inspect: `jarvis-sniper/DEPLOYMENT.md`
- Inspect: `jarvis-sniper/src/lib/surface-availability.ts`
- Inspect: `jarvis-sniper/src/lib/investments-perps-flags.ts`
- Modify: `jarvis-sniper/src/app/api/health/route.ts`
- Modify: `jarvis-sniper/src/app/api/investments/**`
- Test: `jarvis-sniper/src/app/api/health/__tests__/route.test.ts`

**Step 1: Write the failing test**

Add tests that verify the health route and proxy layer clearly reflect whether the investments upstream is configured, healthy, and intentionally gated.

**Step 2: Run test to verify it fails**

Run: `npm --prefix jarvis-sniper test -- --runInBand`

Expected: FAIL showing missing or weak investments upstream/rollout reporting.

**Step 3: Write minimal implementation**

Update the health and investments proxy paths so production behavior is explicit:
- healthy upstream is visible in `/api/health`
- disabled surface still degrades cleanly
- admin write failures are clear and consistent

**Step 4: Run test to verify it passes**

Run: `npm --prefix jarvis-sniper test -- --runInBand`

Expected: PASS for the new proxy/health tests.

**Step 5: Commit**

```bash
git add jarvis-sniper/.env.example jarvis-sniper/DEPLOYMENT.md jarvis-sniper/src/app/api jarvis-sniper/src/lib
git commit -m "fix(sniper): harden investments rollout and proxy health"
```

### Task 3: Fix The Investments Cloud Deploy Path

**Files:**
- Modify: `scripts/deploy_investments_cloud_run.ps1`
- Inspect: `services/investments/.env.example`
- Inspect: `services/investments/config.py`
- Inspect: `services/investments/main.py`
- Test: `services/investments/tests/test_config.py`
- Test: `services/investments/tests/test_main.py`

**Step 1: Write the failing test**

Add coverage for the production deploy/runtime assumptions that are currently stale or misleading, especially the Base-vs-Ethereum mismatch in the deploy script inputs.

**Step 2: Run test to verify it fails**

Run: `.venv-investments/Scripts/python.exe -m pytest services/investments/tests/test_config.py services/investments/tests/test_main.py -q`

Expected: FAIL due to stale deploy/runtime assumptions not matching the current investments runtime.

**Step 3: Write minimal implementation**

Update the Cloud Run deployment script to reflect the live-safe runtime:
- Ethereum naming where appropriate
- safe defaults preserved
- no accidental enabling of unfinished automation

**Step 4: Run test to verify it passes**

Run: `.venv-investments/Scripts/python.exe -m pytest services/investments/tests/test_config.py services/investments/tests/test_main.py -q`

Expected: PASS.

**Step 5: Commit**

```bash
git add scripts/deploy_investments_cloud_run.ps1 services/investments/.env.example services/investments/config.py services/investments/main.py services/investments/tests/test_config.py services/investments/tests/test_main.py
git commit -m "fix(investments): align cloud deploy path with live runtime"
```

### Task 4: Deploy The Investments Backend

**Files:**
- Inspect: `scripts/deploy_investments_cloud_run.ps1`
- Inspect: `services/investments/Dockerfile`
- Inspect: `services/investments/main.py`

**Step 1: Prepare deployment inputs**

Gather or confirm:
- database URL
- redis URL
- admin token
- dry-run flag
- runtime API keys
- basket address if live mode is intended

**Step 2: Deploy backend**

Run the deployment script with the canonical project/service values.

Run:
```powershell
powershell -ExecutionPolicy Bypass -File scripts/deploy_investments_cloud_run.ps1 ...
```

Expected: Cloud Run URL emitted successfully.

**Step 3: Verify backend health**

Run:
```powershell
curl.exe https://<investments-service>/health
curl.exe https://<investments-service>/api/investments/basket
curl.exe https://<investments-service>/api/investments/version
```

Expected: healthy responses with the canonical investments schema.

**Step 4: Commit**

No code commit required if deployment uses committed code only.

### Task 5: Wire And Deploy The Canonical Frontend

**Files:**
- Inspect: `jarvis-sniper/.env.example`
- Inspect: `jarvis-sniper/DEPLOYMENT.md`
- Inspect: `.github/workflows/jarvis-sniper-firebase-deploy.yml`

**Step 1: Set runtime env**

Set:
- `INVESTMENTS_SERVICE_BASE_URL`
- `INVESTMENTS_ADMIN_TOKEN`
- `NEXT_PUBLIC_ENABLE_INVESTMENTS=true`

Keep non-canonical or unfinished toggles disabled.

**Step 2: Deploy frontend**

Run the existing hardened deployment flow from `jarvis-sniper`.

Run:
```bash
npm --prefix jarvis-sniper run deploy:hardened
```

Expected: successful Firebase/Cloud Run deployment.

**Step 3: Verify frontend health**

Run:
```bash
curl -s https://jarvislife.cloud/api/health
curl -s https://jarvislife.cloud/api/version
```

Expected: investments upstream marked configured and healthy.

**Step 4: Commit**

No code commit required if deployment uses committed code only.

### Task 6: Run Production Smoke And Rollback Checks

**Files:**
- Inspect: `jarvis-sniper/scripts/e2e/production_smoke.py`
- Inspect: `jarvis-sniper/debug/`
- Test: live `jarvislife.cloud`

**Step 1: Write/adjust the failing smoke expectation**

Define the exact production assertions:
- investments page loads
- basket data renders
- kill switch path behaves correctly
- no dead panel or disabled overlay when investments is enabled

**Step 2: Run smoke**

Run:
```bash
python jarvis-sniper/scripts/e2e/production_smoke.py
```

Expected: PASS on the canonical investments route.

**Step 3: Verify rollback switch**

Confirm that setting `NEXT_PUBLIC_ENABLE_INVESTMENTS=false` would disable the surface cleanly without needing backend teardown.

**Step 4: Commit**

Commit any smoke-script improvements if code changed.

```bash
git add jarvis-sniper/scripts/e2e jarvis-sniper/debug
git commit -m "test(sniper): codify production investments smoke"
```
