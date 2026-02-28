# Bot Stabilization Exhaustive Validation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Validate and stabilize bot/task execution surfaces, fix discovered breakages, and commit all tracked local changes.

**Architecture:** Use a fail-first verification loop: collect baseline diffs, run broad test/health commands, isolate failing components, apply minimal fixes, and verify with fresh reruns before commit. Prioritize root-cause fixes over symptom patches and preserve unrelated user changes.

**Tech Stack:** Python (`pytest`, project scripts), Node/Next.js (`npm test`, `npm build` where relevant), Docker Compose config validation, Git.

---

### Task 1: Baseline And Scope

**Files:**
- Modify: `docs/plans/2026-02-27-bot-stabilization-exhaustive-validation.md`
- Inspect: `core/safe_subprocess.py`
- Inspect: `tests/test_safe_subprocess.py`
- Inspect: `docker/clawdbot-gateway/docker-compose.yml`

**Step 1: Capture current diff and deleted files**

Run: `git status --short`
Expected: list of tracked changes and notebook deletions.

**Step 2: Inspect changed tracked files**

Run: `git diff -- core/safe_subprocess.py tests/test_safe_subprocess.py docker/clawdbot-gateway/docker-compose.yml`
Expected: only intended deltas for safe subprocess and gateway config.

### Task 2: Exhaustive Validation Pass

**Files:**
- Inspect: `run_full_test_suite.py`
- Inspect: `pyproject.toml`

**Step 1: Run project-level Python tests**

Run: `python -m pytest tests/test_safe_subprocess.py -v`
Expected: all tests pass.

**Step 2: Run broader bot health scripts**

Run: `python run_full_test_suite.py`
Expected: report generated with pass/fail details per script.

**Step 3: Validate JS runtime surfaces**

Run: `npm -C jarvis-sniper run test -- src/components/investments/__tests__/InvestmentsPageClient.test.tsx src/components/perps/__tests__/PerpsSniperPanel.test.tsx src/lib/__tests__/investments-perps-flags.test.ts`
Expected: tests pass.

### Task 3: Troubleshoot Any Failures

**Files:**
- Modify: `core/safe_subprocess.py` (if needed)
- Modify: `tests/test_safe_subprocess.py` (if needed)
- Modify: `docker/clawdbot-gateway/docker-compose.yml` (if needed)

**Step 1: Reproduce failure with exact command**

Run failing command directly and capture stderr/exit code.

**Step 2: Apply minimal fix at root cause**

Patch only affected files; avoid broad refactors.

**Step 3: Re-run failing command + regression command**

Expected: failure resolved and no regression in nearby tests.

### Task 4: Commit All Tracked Changes

**Files:**
- Modify: tracked files from status output

**Step 1: Final verification rerun**

Run full set of commands used for validation.

**Step 2: Stage tracked changes**

Run: `git add -u`

**Step 3: Commit**

Run: `git commit -m "Stabilize bot execution surfaces and refresh local validation artifacts"`

**Step 4: Confirm commit**

Run: `git log -1 --oneline`
Expected: new commit hash and message.
