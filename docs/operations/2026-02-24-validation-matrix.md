# Validation Matrix (Phase 1-4 Rollout)

This matrix is the required verification set before merge or production deploy.

## Local Verification Commands

1. Python algorithm and integration suites (blocking)

```bash
pytest core/open_claw/tests core/backtest/data_ingestion/tests bots/tradfi_sniper/tests core/intel/tests tests/backtesting -q
```

Pass criteria:
- Exit code `0`
- No failed tests

1. Legacy Python unit suite (advisory / non-blocking)

```bash
pytest tests/unit -q
```

Pass criteria:
- Results are captured for remediation.
- Current baseline legacy API mismatches are tracked separately and do not block Phase 1-4 rollout deploy.

2. Jarvis Sniper lint

```bash
npm -C jarvis-sniper run lint
```

Pass criteria:
- Exit code `0`
- No lint errors

3. Jarvis Sniper test suite

```bash
npm -C jarvis-sniper run test
```

Pass criteria:
- Exit code `0`
- All tests pass

4. Jarvis Sniper production build

```bash
npm -C jarvis-sniper run build
```

Pass criteria:
- Exit code `0`
- Next.js build succeeds without fatal error

5. Real-data-only backtest gate

```bash
npm -C jarvis-sniper run check:real-data-only
```

Pass criteria:
- Exit code `0`
- Gate test confirms no mock-only backtest path is treated as production-valid

## CI Workflow Mapping

- `.github/workflows/python-testing.yml`
  - Must run Python blocking command from step (1).
  - Must run advisory legacy command from step (1) in non-blocking mode.
- `.github/workflows/ci.yml`
  - Must run steps (2), (3), (4), and (5) in `jarvis-sniper-readiness`.

## Release Blockers

Release is blocked if any of the following are true:

1. Any command above fails.
2. Production deploy workflow cannot execute when staging job is conditionally skipped.
3. Health endpoint does not return valid JSON for official domains.
4. Backtest transport regresses to raw HTML payload leakage in UI.
