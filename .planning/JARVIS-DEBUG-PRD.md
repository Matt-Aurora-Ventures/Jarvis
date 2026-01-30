# Jarvis /demo Debug PRD
Generated: 2026-01-30 20:32 UTC

## Current State
- Bot: @jarvistrades_bot
- Treasury: BFhTj4TGKC77C7s3HLnLbCiVd6dXQSqGvtD8sJY5egVR
- Balance: 1.802 SOL
- Status: ✅ Running (PID 89)

## Known Errors (from logs)
1. `TokenSignal.__init__() missing 2 required positional arguments: 'symbol' and 'name'` - signal_service.py
2. `cannot import name 'BagsClient' from 'core.trading.bags_client'` - sentiment_hub.py
3. `'solders.keypair.Keypair' object has no attribute 'to_base58_string'` - snipe.py
4. `Trade execution failed on all platforms` - buy.py
5. `no such column: position_id` - scorekeeper.py (SQLite)
6. `Swap failed: 400 Bad Request` - bags_client.py

## Button Test Matrix
| Button | Status | Error | Fixed |
|--------|--------|-------|-------|
| Positions | ❓ | | |
| Trending | ❓ | | |
| Sentiment Hub | ❓ | BagsClient import | |
| Blue Chips | ❓ | | |
| 0.1 SOL Buy | ❓ | Trade failed | |
| Wallet | ❓ | | |
| Settings | ❓ | | |
| DCA | ❓ | | |
| Watchlist | ❓ | | |
| Performance | ❓ | position_id column | |
| Quick Trade | ❓ | | |
| AI Picks | ❓ | TokenSignal args | |
| TP/SL | ❓ | | |
| Insta Snipe | ❓ | to_base58_string | |

## Success Criteria
- [ ] Zero errors in logs after /demo
- [ ] All buttons respond (no "Error" messages)
- [ ] At least ONE real TX on Solscan

---
## Phase 2 Progress Log

### Fix 1: TokenSignal missing args
- File: tg_bot/services/signal_service.py
- Status: 🔧 IN PROGRESS
