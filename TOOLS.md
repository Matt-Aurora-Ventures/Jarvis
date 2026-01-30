# TOOLS.md - Jarvis Local Notes

Skills define *how* tools work. This file is for *your* specifics.

## Network
- **VPS Tailscale**: 100.66.17.93
- **Windows Desktop**: 100.102.41.120 (SSH via lucid@)

## API Keys Location
- Main keys: `/root/clawd/Jarvis/secrets/keys.json`
- Jarvis keys: `/root/clawd/Jarvis/secrets/jarvis-keys.json`
- Windows backup: `C:\Users\lucid\OneDrive\Desktop\Projects\Jarvis\secrets\keys.json`

## Chrome CDP (Browser Control)
- SSH tunnel: `ssh -L 9222:127.0.0.1:9222 lucid@100.102.41.120`
- Control: `ws://127.0.0.1:9222`
- **NEVER mention Chrome extension** — use CDP only

## Solana RPC
- Helius mainnet (from keys.json)
- Jupiter for swaps (public API)
- Birdeye for token data

## Telegram Bot
- Token in `.env` or `secrets/jarvis-keys.json`
- Admin: Matt (8527130908)
- Broadcast group: -1003408655098

## Skills Directory
- `/root/clawd/Jarvis/skills/` — symlinked from /root/.clawdbot/skills/
- Same 106 skills as ClawdMatt

---
*Add environment-specific notes as you work*
