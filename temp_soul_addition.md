

## Crash Recovery & Session Continuity

### On Startup (ALWAYS DO THIS FIRST)

1. **Check if you just crashed:**
   - Look at `/home/lucid/.clawdbot/logs/` for recent errors
   - Run: `journalctl --user -u clawdbot --since '5 minutes ago' | grep -i 'error\|fail\|crash'`
   - If you find crash logs, **diagnose and report the issue**

2. **Check your last session:**
   - Review recent session files in `/home/lucid/.clawdbot/agents/main/sessions/`
   - Find the most recent `.jsonl` file
   - Read the last few entries to understand what you were doing

3. **Resume or report:**
   - If there was an incomplete task, **continue it immediately**
   - If you crashed due to a network error, check connectivity first
   - Tell Matt: "I just restarted. I was working on [X] and will continue now."

### Network Resilience

If you encounter network errors (especially with Telegram):
1. Don't panic - the system will restart you
2. After restart, check: `curl -s https://api.telegram.org/botTOKEN/getMe`
3. If Telegram is blocked, inform Matt that Norton VPN may be interfering

### State Persistence

**Before doing important work:**
- Log your current task to memory
- Save checkpoints for long-running operations
- Use the learnings.db to track progress

**After crashes:**
- You may have lost the last 1-2 minutes of context
- Check learnings.db and session logs to recover state
