# Vanguard Standalone Validation

Vanguard is validated as a standalone runtime in this repo and does not require
`jarvis-sniper` wiring for test/perf hardening.

## Minimal Runtime Mode

Set:

```bash
JARVIS_CORE_MINIMAL_IMPORTS=1
PERPS_AI_MODE=disabled
```

This avoids loading unrelated Jarvis subsystems while testing the perps runner.

## One-Shot Smoke Test

```bash
python scripts/test_vanguard_standalone.py --runtime-seconds 12
```

Expected:
- startup JSON event
- heartbeat events
- reconciliation cycle event every 10s
- clean shutdown event

## Nonstop Loop (Watchdog)

```powershell
powershell -File scripts/start_vanguard_standalone_loop.ps1
powershell -File scripts/status_vanguard_standalone_loop.ps1
powershell -File scripts/stop_vanguard_standalone_loop.ps1
```

No Sniper dependency is required for the loop itself.

## Log Tail

```powershell
Get-Content "$env:LOCALAPPDATA\Jarvis\vanguard-standalone\watchdog.log" -Tail 100 -Wait
```
