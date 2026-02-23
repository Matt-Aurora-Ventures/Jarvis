# Ralph Wiggum Parallel Loop Operations

This loop is standalone and does not require `jarvis-sniper` integration.

## Standalone Smoke Test

```powershell
python scripts/test_vanguard_standalone.py --runtime-seconds 12
```

This executes a dry-run runner in isolated runtime state under
`.runtime/vanguard-standalone`.

## Start

```powershell
powershell -File scripts/start_ralph_wiggum_parallel_loop.ps1
```

Defaults:
- dry-run enabled
- unlimited runtime
- micro + macro + execution consumer + reconciliation loops in parallel
- AI bridge disabled by default in wrapper
- reconciliation interval: 10s
- heartbeat enabled

## Status

```powershell
powershell -File scripts/status_ralph_wiggum_parallel_loop.ps1
```

## Stop

```powershell
powershell -File scripts/stop_ralph_wiggum_parallel_loop.ps1
```

## Log Tail Helper

```powershell
Get-Content "$env:LOCALAPPDATA\Jarvis\ralph_wiggum\watchdog.log" -Tail 100 -Wait
```
