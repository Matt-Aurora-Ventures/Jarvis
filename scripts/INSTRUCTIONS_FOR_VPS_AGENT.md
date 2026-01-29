# Instructions for VPS Agent (ClawdMatt)

## Mission
Fix gateway config persistence, then extract and execute ALL tasks from Telegram chats in a continuous Ralph Wiggum loop.

## Step 1: Transfer Scripts to VPS

Copy these files to your VPS:
- `ralph_wiggum_gateway_fix.sh`
- `ralph_wiggum_telegram_tasks.sh`
- `master_ralph_wiggum.sh`

```bash
# On your VPS
mkdir -p /root/clawd/scripts
cd /root/clawd/scripts

# Download or create the scripts there
```

## Step 2: Set Environment Variables

Before running, export your credentials:

```bash
export TELEGRAM_BOT_TOKEN="your_main_bot_token"
export MAIN_CHAT_ID="your_main_chat_id"
export FRIDAY_CHAT_ID="friday_chat_id"
export FRIDAY_TOKEN="friday_bot_token"
export JARVIS_CHAT_ID="jarvis_chat_id"
export JARVIS_TOKEN="jarvis_bot_token"
export GATEWAY_WS_PORT="8080"
```

## Step 3: Make Scripts Executable

```bash
chmod +x /root/clawd/scripts/*.sh
```

## Step 4: Run Master Script

```bash
cd /root/clawd/scripts
./master_ralph_wiggum.sh
```

This will:
1. **Fix Gateway** (loop up to 10 times until config persists)
   - Kills gateway with SIGKILL (prevents shutdown persistence)
   - Backs up all memory/data
   - Edits config to add Friday & Jarvis accounts
   - Locks config with `chattr +i` (immutable)
   - Restarts gateway
   - Verifies accounts persist

2. **Extract All Tasks** from:
   - Telegram chats (Main, Friday, Jarvis)
   - Voice transcripts
   - Daily notes
   - Compiles into `/root/clawd/MASTER_TASK_LIST.md`

3. **Execute Tasks** in Ralph Wiggum loop:
   - Takes Task 1
   - Sends to Claude
   - Marks completed
   - Moves to Task 2
   - Repeats forever
   - Re-scans for new tasks when list is empty

## What Gets Protected

The scripts preserve:
- `/root/clawd/MEMORY.md` - Session memory
- `/root/clawd/TODO.md` - Current todos
- `/root/clawd/daily-notes/` - Daily transcripts
- `/root/clawd/voice-transcripts/` - Voice recordings
- `~/.claude/config.json` - Backed up before each attempt

Backups saved to: `/root/clawd/backups/YYYYMMDD_HHMMSS/`

## Monitoring Progress

```bash
# Watch task list
watch -n 5 cat /root/clawd/MASTER_TASK_LIST.md

# Watch completed tasks
tail -f /root/clawd/COMPLETED_TASKS.md

# Watch gateway logs
journalctl -u clawdbot-gateway -f

# Check gateway status
systemctl status clawdbot-gateway
```

## Stopping the Loop

To stop the Ralph Wiggum execution loop:

```bash
# Send SIGTERM to the script
pkill -f ralph_wiggum_telegram_tasks.sh

# Or just ctrl+C in the terminal
```

## If Gateway Fix Fails

After 10 attempts, if gateway still fails:

1. Check logs: `journalctl -u clawdbot-gateway -n 100`
2. Check process conflicts: `ps aux | grep clawdbot`
3. Check file permissions: `ls -la ~/.claude/config.json`
4. Manual unlock: `chattr -i ~/.claude/config.json`
5. Edit manually: `nano ~/.claude/config.json`
6. Relock: `chattr +i ~/.claude/config.json`
7. Restart: `systemctl restart clawdbot-gateway`

## Expected Output

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔄 RALPH WIGGUM GATEWAY FIX LOOP
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🔄 Attempt 1/10
📦 Backing up all memory and data...
✅ Backup saved to: /root/clawd/backups/20260128_145300
🔪 Killing gateway...
✅ Gateway killed
🔧 Fixing config...
✅ Config fixed and locked
🚀 Starting gateway...
✅ Gateway started
🔍 Verifying...
✅ Config is immutable
✅ Friday account exists
✅ Jarvis account exists
✅ Gateway is running
✅ WebSocket is working

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ GATEWAY FIXED SUCCESSFULLY!
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📋 RALPH WIGGUM TASK COMPILER
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📥 Extracting tasks from Telegram chats...
  📱 Processing chat: 123456789
  📱 Processing chat: 987654321
  🎤 Processing voice transcripts...
✅ Extracted 47 tasks

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔄 ENTERING RALPH WIGGUM EXECUTION LOOP
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

⚠️  Will continue until user says STOP

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📋 Task 1
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Fix the memory system to use PostgreSQL
...
```

## Notes

- The loop will run **indefinitely** until you stop it
- Tasks are re-scanned every time the list is exhausted
- All work is logged to `COMPLETED_TASKS.md`
- Gateway config is **locked** - use `chattr -i` to unlock if needed
- All memory/data is backed up before each gateway fix attempt
