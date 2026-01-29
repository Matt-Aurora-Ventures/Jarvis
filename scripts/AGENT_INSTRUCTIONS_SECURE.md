# Secure Instructions for VPS Agent (ClawdMatt)

## Critical Discovery

Your agent found the **root cause**:
- Gateway validates config on startup (server.impl.js line 87, 106)
- Strips "unknown" keys during validation
- accounts/agents.list/bindings get removed
- This is why config keeps getting wiped

## Correct Fix Method

**DO NOT** use `chattr +i` or file editing. That won't work.

**CORRECT METHOD:**
1. Fix WebSocket binding (bind to 127.0.0.1, not Tailscale IP)
2. Use `config.apply` RPC to add accounts properly
3. Verify persistence across restart

## Security Requirements

✅ **Before starting:**
- All data backed up with SHA256 checksums
- Environment variables validated
- Credentials are real tokens (not placeholders)
- File permissions restricted (chmod 600/700)

✅ **During execution:**
- Commands sanitized (no `;`, `|`, `` ` ``, `$()`)
- Dangerous commands blocked (rm -rf, dd, wget|sh, etc.)
- Timeouts on all operations (300s max)
- Consecutive failure detection (pause after 3 fails)

✅ **After completion:**
- Config validated via RPC
- Persistence verified via restart test
- Checksums verified on all backups

## Step-by-Step Execution

### 1. Export Environment (Security)

```bash
# REQUIRED: Replace with real values
export TELEGRAM_BOT_TOKEN="<your_real_token_min_20_chars>"
export MAIN_CHAT_ID="<main_chat_id>"
export FRIDAY_CHAT_ID="<friday_chat_id>"
export JARVIS_CHAT_ID="<jarvis_chat_id>"

# Verify (security check)
echo "Token length: ${#TELEGRAM_BOT_TOKEN}"  # Should be 40+
```

### 2. Transfer Secure Scripts

```bash
mkdir -p /root/clawd/scripts
cd /root/clawd/scripts

# Copy the new secure scripts:
# - ralph_wiggum_secure_gateway_fix.sh
# - ralph_wiggum_secure_tasks.sh

chmod +x *.sh
```

### 3. Run Gateway Fix (Secure)

```bash
cd /root/clawd/scripts
./ralph_wiggum_secure_gateway_fix.sh
```

This will:
- ✅ Backup all data with checksums
- ✅ Validate credentials (security)
- ✅ Fix WebSocket binding to 127.0.0.1
- ✅ Add accounts via RPC (not file edit)
- ✅ Test persistence across restart
- ✅ Loop up to 10 times until working

Expected output:
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔒 SECURE RALPH WIGGUM GATEWAY FIX
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🔄 SECURE ATTEMPT 1/10
🔒 SECURITY: Backing up all data...
✅ Backup saved: /root/clawd/backups/secure_20260128_145300
🔒 Checksums: checksums.txt

🔒 SECURITY: Validating environment...
✅ Environment validated

🔧 Fixing WebSocket binding...
✅ Fixed binding to 127.0.0.1
✅ WebSocket accessible on 127.0.0.1:8080

🔧 Adding accounts via RPC...
✅ Accounts added via RPC

🔍 Verifying accounts persist across restart...
✅ Friday account exists before restart
🔄 Restarting gateway (graceful)...
✅ Friday account PERSISTED after restart
✅ Jarvis account PERSISTED after restart

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ GATEWAY FIXED SECURELY!
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🔒 Security Status:
  ✅ All data backed up with checksums
  ✅ Credentials validated
  ✅ WebSocket bound to loopback (127.0.0.1)
  ✅ Accounts added via RPC (not file edit)
  ✅ Accounts persist across restart
```

### 4. Run Task Extraction (Secure)

```bash
cd /root/clawd/scripts
./ralph_wiggum_secure_tasks.sh
```

This will:
- ✅ Validate Telegram credentials
- ✅ Extract tasks from ALL channels (Main + Friday + Jarvis)
- ✅ Include voice transcripts
- ✅ Sanitize all commands (security)
- ✅ Block dangerous commands
- ✅ Execute in Ralph Wiggum loop
- ✅ Re-scan for new tasks when done

Extracts from:
- **Main Channel** (you're admin) - High priority
- **Friday Channel** (you're member) - Normal priority
- **Jarvis Channel** (you're member) - Normal priority
- Voice transcripts (last 30 days) - High priority

Expected output:
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📋 SECURE RALPH WIGGUM TASK SYSTEM
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🔒 SECURITY: Validating Telegram credentials...
✅ Credentials validated

🔒 Initializing secure task system...
✅ Secure initialization complete

📥 Extracting tasks from ALL Telegram channels...

  📱 Processing: Main (Role: admin)
     Chat ID: 123456789
     ✅ Processed Main

  📱 Processing: Friday (Role: member)
     Chat ID: 987654321
     ✅ Processed Friday

  📱 Processing: Jarvis (Role: member)
     Chat ID: 111222333
     ✅ Processed Jarvis

  🎤 Scanning voice transcripts...

✅ Extracted 87 tasks total from all channels

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📋 TASK COMPILATION COMPLETE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Press ENTER to start Ralph Wiggum loop...
```

Then it will execute forever:
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔄 RALPH WIGGUM EXECUTION LOOP (SECURE)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

⚠️  Will run indefinitely until you say STOP
🔒 Security: Commands sanitized, credentials validated

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📋 Task 1
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Fix the memory system...

🤖 Executing with Claude (timeout: 300s)...
✅ Task 1 completed

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📋 Task 2
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
...
```

## Security Features

### ✅ Command Sanitization
Blocks: `rm -rf`, `dd if=`, `:(){:`, `wget|sh`, `curl|bash`, `nc -`, `mkfs`

### ✅ Input Validation
- Token min 20 chars
- Token not placeholder
- Chat IDs present
- JSON validation

### ✅ Execution Safety
- 300s timeout per task
- Pause after 3 consecutive fails
- Log file permissions (600)
- Archive permissions (700)

### ✅ Data Protection
- All backups with SHA256 checksums
- Verify checksums before/after
- Restricted permissions (600/700)

## Monitoring

```bash
# Watch tasks
watch -n 5 cat /root/clawd/MASTER_TASK_LIST.md

# Watch completed
tail -f /root/clawd/COMPLETED_TASKS.md

# Watch gateway
journalctl -u clawdbot-gateway -f

# Verify checksums
cd /root/clawd/backups/secure_<timestamp>
sha256sum -c checksums.txt
```

## Stopping

```bash
# Stop task loop
pkill -f ralph_wiggum_secure_tasks

# Or Ctrl+C in terminal
```

## What's Protected

All critical files backed up with checksums:
- `/root/clawd/MEMORY.md`
- `/root/clawd/TODO.md`
- `/root/clawd/daily-notes/`
- `/root/clawd/voice-transcripts/`
- `~/.claude/config.json`

Backups at: `/root/clawd/backups/secure_<timestamp>/`

## If Something Goes Wrong

```bash
# 1. Check gateway
systemctl status clawdbot-gateway
curl http://127.0.0.1:8080/health

# 2. Check WebSocket binding
netstat -tlnp | grep 8080

# 3. Restore from backup
cd /root/clawd/backups
ls -lt | head -5  # Find latest
cp -r secure_<timestamp>/* /root/clawd/

# 4. Verify checksums
cd secure_<timestamp>
sha256sum -c checksums.txt
```
