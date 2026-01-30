# Bulletproof TP/SL System

**Status: DEPLOYED** ✅

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      LAYER 1: JARVIS                         │
│                   Primary Monitor (30s)                      │
│                                                              │
│  • Runs inside Jarvis bot (demo_orders.py)                  │
│  • Checks every 30 seconds                                   │
│  • Updates heartbeat in Redis                                │
│  • Syncs positions to Redis                                  │
│  • Uses execution locks to prevent double-sells              │
│  • Auto-executes TP/SL via bags.fm swap API                 │
├─────────────────────────────────────────────────────────────┤
│                      LAYER 2: CLAWDBOT CRON                  │
│                   Backup Monitor (2min)                      │
│                                                              │
│  • Runs independently via Clawdbot cron                     │
│  • Checks if primary is alive via Redis heartbeat           │
│  • If primary dead → takes over monitoring                   │
│  • Uses same execution locks (no double-sells)              │
│  • Alerts to Telegram if TP/SL triggered                    │
├─────────────────────────────────────────────────────────────┤
│                      REDIS: Shared State                     │
│                                                              │
│  • jarvis:positions:{user_id} → Position data               │
│  • jarvis:trailing_stops:{user_id} → Trailing stops         │
│  • jarvis:exec_lock:{pos_id} → Execution locks (60s TTL)    │
│  • jarvis:monitor_heartbeat:primary → Primary health        │
│  • jarvis:monitor_heartbeat:backup → Backup health          │
└─────────────────────────────────────────────────────────────┘
```

## Files

| File | Purpose |
|------|---------|
| `tg_bot/core/position_store.py` | Redis persistence layer |
| `tg_bot/handlers/demo/demo_orders.py` | Primary monitor (updated) |
| `scripts/backup-tpsl-monitor.py` | Layer 2 backup monitor |
| `scripts/tpsl-status.sh` | Quick health check |

## Commands

### Check Status
```bash
/root/clawd/Jarvis/scripts/tpsl-status.sh
```

### Test Backup Monitor
```bash
cd /root/clawd/Jarvis && python3 scripts/backup-tpsl-monitor.py
# Add --force to check even if primary is alive
```

### View Redis State
```bash
redis-cli KEYS "jarvis:*"
redis-cli GET "jarvis:monitor_heartbeat:primary"
redis-cli GET "jarvis:monitor_heartbeat:backup"
```

## Failure Modes

| Scenario | What Happens |
|----------|--------------|
| Jarvis crashes | Backup monitor takes over in <2min |
| VPS reboots | Redis persistence + backup monitor covers |
| Backup cron fails | Primary still running independently |
| Both fail | Positions persist in Redis until restart |
| Double trigger | Execution lock prevents duplicate sells |

## Cron Job

The backup monitor runs via Clawdbot cron:
- **Name:** TP/SL Backup Monitor
- **Interval:** Every 2 minutes
- **Mode:** Silent unless issues detected

## TODO (Future Enhancements)

- [ ] External watchdog (BetterStack/Cronitor) for Layer 3
- [ ] SMS alerts for critical failures
- [ ] Jupiter limit orders for post-graduation tokens (on-chain TP/SL)
- [ ] Jito bundles for guaranteed execution
