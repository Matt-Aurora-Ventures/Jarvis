# Jarvis Sniper Hook Audit Report

Date: 2026-02-11
Auditor: Scout Agent
Scope: All hooks in jarvis-sniper/src/hooks/

## Executive Summary

Total Files Audited: 9
Critical Issues: 5
Major Issues: 8
Minor Issues: 10

---

## Critical Issues

### 1. useAutomatedRiskManagement.ts - Line 40-42
Missing initialized handler causes race condition

handleTriggerRef initialized with no-op function, not updated until line 361.
If worker sends trigger before effect runs, it is silently ignored.

Impact: Risk management triggers (SL/TP) may be silently dropped.
Severity: CRITICAL
Fix: Initialize with defensive handler that queues triggers

---

### 2. useSnipeExecutor.ts - Line 98-106
Unhandled session wallet load errors

If load functions throw, entire snipe() crashes without cleanup.
Mint stays in pendingRef forever.

Impact: One corrupted wallet file blocks all future snipes.
Severity: CRITICAL
Fix: Wrap in try/catch with proper error logging

---

### 3. useSnipeExecutor.ts - Line 264-267
NaN/Infinity in conviction multiplier

If getConvictionMultiplier returns NaN/Infinity, sizeFactor becomes NaN.
This causes positionSol=NaN.

Impact: Silent swap failures or zero-size positions.
Severity: CRITICAL
Fix: Add validation for Number.isFinite and > 0

---

### 4. useAutomatedRiskManagement.ts - Line 77-81
Worker message handler type safety

Type assertions without validation. Malformed worker messages cause runtime errors.

Impact: Worker sends wrong types, app crashes.
Severity: MAJOR
Fix: Add runtime validation before type assertions

---

### 5. useTheme.ts - Line 15-18
SSR crash: localStorage undefined on server

If Next.js SSR renders this hook, localStorage is undefined and crashes.

Impact: Server-side rendering fails.
Severity: CRITICAL (if SSR enabled)
Fix: Add typeof window !== undefined check

---

## Major Issues

### 6. useBacktest.ts - Line 290
Unhandled JSON parse error in poll loop

If response is not JSON, res.json() throws and stops polling permanently.

Severity: MAJOR
Fix: Wrap in try/catch and return null

---

### 7. useBacktest.ts - Line 458
Missing error handling in success path

Success response JSON parse is not wrapped. If server returns non-JSON on success, hook crashes.

Severity: MAJOR
Fix: Wrap data = await res.json() in try/catch

---

### 8. usePhantomWallet.tsx - Line 199-204
Infinite reconnect loop

If accountChanged(null) fires repeatedly and connect() keeps failing, creates infinite loop.

Severity: MAJOR
Fix: Add debounce or reconnect attempt counter

---

### 9. useSnipeExecutor.ts - Line 464-467
Position created with entryPrice=0

If all price resolution fails, entryPrice=0. SL/TP won't trigger until deferred resolution succeeds.

Impact: Position is unprotected for up to 75 seconds.
Severity: MAJOR
Fix: Add price pending badge in UI or block position creation

---

### 10. useBacktest.ts - Line 225-232
Race condition in polling

If startPolling is called twice rapidly, clearInterval may not finish before new interval is set.

Impact: Memory leak and duplicate API calls.
Severity: MINOR
Fix: Call stopPolling() before starting new poll

---

## Minor Issues (10 total)

11. useAutomatedRiskManagement - Line 268: Undefined amountLamports check
12. usePhantomWallet - Line 102: Silent eager connect failures
13. usePnlTracker - Line 52: Silent batch failures
14. useSnipeExecutor - Line 185: Circuit breaker reset race
15. useSnipeExecutor - Line 394: Strategy epoch check race
16. useSnipeExecutor - Line 554: No timeout for deferred price resolution
17. useTabNotifications - Line 64: Missing type guard for event types
18. usePhantomWallet - Line 249: Excessive approval timeout (180s)
19. useTVScreener - Line 121: Polling interval drift
20. useBacktest - Line 500: Type safety bypassed with as any

---

## Summary Table

| File | Critical | Major | Minor |
|------|----------|-------|-------|
| useAutomatedRiskManagement.ts | 2 | 1 | 1 |
| useBacktest.ts | 0 | 3 | 2 |
| useMacroData.ts | 0 | 0 | 0 |
| usePhantomWallet.tsx | 0 | 1 | 2 |
| usePnlTracker.ts | 0 | 0 | 1 |
| useSnipeExecutor.ts | 2 | 1 | 3 |
| useTabNotifications.ts | 0 | 0 | 1 |
| useTheme.ts | 1 | 0 | 0 |
| useTVScreener.ts | 0 | 0 | 1 |

---

## Priority Fixes

Immediate (Critical):
1. useSnipeExecutor: Wrap session wallet loads in try/catch (line 98)
2. useSnipeExecutor: Validate conviction multiplier (line 264)
3. useAutomatedRiskManagement: Add runtime validation for worker messages (line 77)
4. useTheme: Add SSR check for localStorage (line 15)
5. useAutomatedRiskManagement: Fix no-op handler initialization (line 40)

High Priority (Major):
6. useBacktest: Wrap all res.json() in try/catch (lines 290, 458)
7. usePhantomWallet: Add debounce for reconnect loop (line 199)
8. useSnipeExecutor: Block position creation if entryPrice=0 (line 464)

Medium Priority (Minor):
9. useSnipeExecutor: Add manual price retry button
10. useTabNotifications: Use enum for event types
11. usePnlTracker: Add console.warn for batch errors

---

End of Report
