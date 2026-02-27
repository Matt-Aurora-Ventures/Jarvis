# Perps Top Section + Go-Live Verification Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Deliver a fully operable Perps section in `jarvis-sniper` (charts + entry/exit/TP + runner/arm controls) and run local NotebookLM pre-launch verification without integrating NotebookLM into runtime/build.

**Architecture:** Extend the existing Perps surface (`InvestmentsPageClient` + `PerpsSniperPanel` + `usePerpsData`) and add missing Next.js proxy endpoints that forward to the already-implemented upstream perps runtime endpoints. Keep all Grok/xAI secrets in environment only, and add an offline NotebookLM query workflow that writes evidence artifacts.

**Tech Stack:** Next.js App Router, TypeScript, Vitest, existing perps proxy utilities, local NotebookLM CLI (`nlm`).

---

### Task 1: Add failing route tests for missing perps control proxies

**Files:**
- Create: `jarvis-sniper/src/app/api/perps/arm/__tests__/route.test.ts`
- Create: `jarvis-sniper/src/app/api/perps/disarm/__tests__/route.test.ts`
- Create: `jarvis-sniper/src/app/api/perps/runner/start/__tests__/route.test.ts`
- Create: `jarvis-sniper/src/app/api/perps/runner/stop/__tests__/route.test.ts`
- Create: `jarvis-sniper/src/app/api/perps/limits/__tests__/route.test.ts`

**Step 1: Write failing tests**

```ts
it('forwards POST /api/perps/arm to upstream', async () => {
  process.env.PERPS_SERVICE_BASE_URL = 'http://127.0.0.1:5001';
  const mockFetch = vi.fn().mockResolvedValue(new Response(JSON.stringify({ ok: true }), { status: 200 }));
  vi.stubGlobal('fetch', mockFetch);
  const route = await import('@/app/api/perps/arm/route');
  const req = new Request('http://localhost/api/perps/arm', { method: 'POST', body: JSON.stringify({ step: 'prepare' }) });
  const res = await route.POST(req);
  expect(res.status).toBe(200);
  expect(String(mockFetch.mock.calls[0]?.[0] || '')).toContain('/api/perps/arm');
});
```

**Step 2: Run test to verify it fails**

Run: `npm -C jarvis-sniper run test -- src/app/api/perps/arm/__tests__/route.test.ts`
Expected: FAIL (route module missing)

**Step 3: Write minimal route implementations**

```ts
import { proxyPerpsPost } from '@/lib/perps/proxy';
export const runtime = 'nodejs';
export async function POST(request: Request) {
  return proxyPerpsPost('/arm', request);
}
```

**Step 4: Run tests to verify pass**

Run: `npm -C jarvis-sniper run test -- src/app/api/perps/*/__tests__/route.test.ts`
Expected: PASS

**Step 5: Commit**

```bash
git add jarvis-sniper/src/app/api/perps/**/route.ts jarvis-sniper/src/app/api/perps/**/__tests__/route.test.ts
git commit -m "feat: add perps control proxy routes for arm/disarm/runner/limits"
```

### Task 2: Add failing UI test for new perps operator controls

**Files:**
- Create: `jarvis-sniper/src/components/perps/__tests__/PerpsSniperPanel.test.tsx`
- Modify: `jarvis-sniper/src/components/perps/PerpsSniperPanel.tsx`
- Modify: `jarvis-sniper/src/components/perps/usePerpsData.ts`

**Step 1: Write failing test**

```tsx
it('renders runner + arm controls in perps panel', async () => {
  vi.mock('@/components/perps/usePerpsData', () => ({
    usePerpsData: () => ({
      prices: null, status: { runner_healthy: false, mode: 'disabled', arm: { stage: 'disarmed' } },
      positions: [], audit: [], historyMarket: 'SOL-USD', historyResolution: '5', historyCandles: [],
      loadingHistory: false, historyError: null, apiError: null, isArmed: false, isLive: false,
      setHistoryMarket: vi.fn(), setHistoryResolution: vi.fn(),
      openPosition: vi.fn(), closePosition: vi.fn(), refreshStatus: vi.fn(),
      armPrepare: vi.fn(), armConfirm: vi.fn(), disarm: vi.fn(), startRunner: vi.fn(), stopRunner: vi.fn(),
    }),
  }));
  const { PerpsSniperPanel } = await import('@/components/perps/PerpsSniperPanel');
  render(<PerpsSniperPanel />);
  expect(screen.getByRole('button', { name: /start runner/i })).toBeInTheDocument();
  expect(screen.getByRole('button', { name: /prepare arm/i })).toBeInTheDocument();
  expect(screen.getByRole('button', { name: /confirm arm/i })).toBeInTheDocument();
  expect(screen.getByRole('button', { name: /disarm/i })).toBeInTheDocument();
});
```

**Step 2: Run test to verify it fails**

Run: `npm -C jarvis-sniper run test -- src/components/perps/__tests__/PerpsSniperPanel.test.tsx`
Expected: FAIL (controls/methods missing)

**Step 3: Implement minimal hook + panel changes**

- Add methods in `usePerpsData`:
  - `startRunner()` -> POST `/api/perps/runner/start`
  - `stopRunner()` -> POST `/api/perps/runner/stop`
  - `armPrepare()` -> POST `/api/perps/arm` `{ step: 'prepare' }`
  - `armConfirm(challenge)` -> POST `/api/perps/arm` `{ step: 'confirm', challenge }`
  - `disarm()` -> POST `/api/perps/disarm`
- Add top control strip + action state display in `PerpsSniperPanel`.

**Step 4: Run test to verify pass**

Run: `npm -C jarvis-sniper run test -- src/components/perps/__tests__/PerpsSniperPanel.test.tsx`
Expected: PASS

**Step 5: Commit**

```bash
git add jarvis-sniper/src/components/perps/usePerpsData.ts jarvis-sniper/src/components/perps/PerpsSniperPanel.tsx jarvis-sniper/src/components/perps/__tests__/PerpsSniperPanel.test.tsx
git commit -m "feat: add perps runner and arm/disarm operator controls"
```

### Task 3: Make Perps explicit top section in Investments surface

**Files:**
- Modify: `jarvis-sniper/src/components/investments/InvestmentsPageClient.tsx`
- Modify: `jarvis-sniper/src/components/investments/__tests__/InvestmentsPageClient.test.tsx`

**Step 1: Write failing test**

```tsx
expect(html).toContain('Perps');
```

**Step 2: Run test to verify it fails**

Run: `npm -C jarvis-sniper run test -- src/components/investments/__tests__/InvestmentsPageClient.test.tsx`
Expected: FAIL (new section text absent)

**Step 3: Implement minimal UI change**

- Add a visible section heading/label at top of perps area (without changing gating behavior).

**Step 4: Run test to verify pass**

Run: `npm -C jarvis-sniper run test -- src/components/investments/__tests__/InvestmentsPageClient.test.tsx`
Expected: PASS

**Step 5: Commit**

```bash
git add jarvis-sniper/src/components/investments/InvestmentsPageClient.tsx jarvis-sniper/src/components/investments/__tests__/InvestmentsPageClient.test.tsx
git commit -m "feat: make perps top section explicit in investments UI"
```

### Task 4: Configure Grok-by-default trading env + local NotebookLM go-live verification

**Files:**
- Modify: `core/jupiter_perps/.env.example`
- Create: `temp/notebooklm_perps_golive_questions_20260227.json`
- Create: `temp/notebooklm_perps_golive_check_20260227.py`
- Create: `docs/operations/2026-02-27-notebooklm-perps-golive-check.md`

**Step 1: Write failing execution script expectations**

- Script should load 50 questions from JSON, call local NotebookLM CLI per question, persist structured results JSON/MD.
- It should fail fast with clear message if CLI/auth/profile is missing.

**Step 2: Run script to verify expected initial failure (if local auth absent)**

Run: `python temp/notebooklm_perps_golive_check_20260227.py`
Expected: FAIL with actionable setup message, or PASS with results artifact.

**Step 3: Implement script + question set + env example update**

- Set `PERPS_AI_LLM_PROVIDERS=xai` and `PERPS_AI_XAI_MODEL=grok-4-latest` in example config comments/defaults.
- Keep `XAI_API_KEY` out of tracked files; local-only env injection.

**Step 4: Re-run script and save evidence**

Run: `python temp/notebooklm_perps_golive_check_20260227.py`
Expected: `temp/notebooklm_perps_golive_results_20260227.json` generated (or explicit blocked reason recorded).

**Step 5: Commit non-secret assets**

```bash
git add core/jupiter_perps/.env.example temp/notebooklm_perps_golive_questions_20260227.json temp/notebooklm_perps_golive_check_20260227.py docs/operations/2026-02-27-notebooklm-perps-golive-check.md
git commit -m "chore: add grok-default perps env hints and local notebooklm go-live verifier"
```

### Task 5: Final verification gate

**Files:**
- Verify only.

**Step 1: Run focused tests**

Run:
```bash
npm -C jarvis-sniper run test -- src/app/api/perps/*/__tests__/route.test.ts src/components/perps/__tests__/PerpsSniperPanel.test.tsx src/components/investments/__tests__/InvestmentsPageClient.test.tsx
```
Expected: PASS

**Step 2: Run build**

Run: `npm -C jarvis-sniper run build`
Expected: PASS

**Step 3: Optional runtime smoke**

Run local dev and verify:
- Perps section visible at top.
- Charts render.
- Runner/arm/disarm buttons call endpoints and show responses.
- Open/close and TP/SL controls still work.

**Step 4: Record verification evidence**

- Add command outputs + timestamp to `docs/operations/2026-02-27-notebooklm-perps-golive-check.md`.

**Step 5: Commit verification note**

```bash
git add docs/operations/2026-02-27-notebooklm-perps-golive-check.md
git commit -m "docs: record perps go-live verification evidence"
```