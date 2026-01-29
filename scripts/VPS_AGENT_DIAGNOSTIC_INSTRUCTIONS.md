# VPS Agent Diagnostic Instructions

## Critical Context

You are in a **container environment** with these constraints:
- PID 1 = Clawdbot supervisor (auto-restarts gateway on crash)
- Config file: `~/.clawdbot/clawdbot.json` (NOT moltbot.json)
- Gateway binds to Tailscale IP: `100.66.17.93:18789`
- RPC = WebSocket protocol
- Cannot permanently stop supervisor

## The Problem

`config.patch` RPC works → writes config correctly → triggers SIGUSR1 restart → **something overwrites the file with stripped version** → new gateway reads stripped config

**This is a RACE CONDITION, not a validation issue.**

---

## Step 1: Run the Diagnostic

```bash
# Transfer diagnostic script to VPS
scp scripts/vps_gateway_race_diagnosis.sh root@vps:/root/

# On VPS: Make executable
chmod +x /root/vps_gateway_race_diagnosis.sh

# Run diagnostic
cd /root
./vps_gateway_race_diagnosis.sh
```

**IMPORTANT**: Let the script run completely (takes ~30 seconds). Do NOT interrupt.

---

## Step 2: Review the Output

The script will show:

### Phase 1: File Monitoring
- Real-time file modification events
- File size changes with timestamps

### Phase 2: Baseline
- Current config size
- Gateway PID
- Supervisor info

### Phase 3: Test Config.Patch
- Applies a test account "diagnostic_test"
- Monitors size changes every 0.5s for 10s
- Saves snapshots when size changes

### Phase 4: Writer Identification
- Shows all MODIFY events
- Lists processes accessing the file
- Checks supervisor state

### Phase 5: Analysis
- Counts modify events
- Calculates size variance
- Identifies likely cause

### Phase 6: Fix Recommendations
- Provides specific fixes based on findings

---

## Step 3: Interpret the Results

### Scenario A: Multiple MODIFY Events (3+)

**What it means**: Race condition confirmed. Something writes AFTER config.patch but BEFORE new gateway reads.

**Example output**:
```
15:59:01.350 | Event: MODIFY | Size: 3100 bytes  ← config.patch
15:59:01.510 | Event: MODIFY | Size: 2480 bytes  ← THE CULPRIT
15:59:01.700 | Event: MODIFY | Size: 2480 bytes  ← Gateway startup
```

**Fix**: Use **FIX 1 (Atomic Write + Kill)** or **FIX 2 (Config Lock)**

### Scenario B: Size Decreased (< -100 bytes)

**What it means**: Startup validation is stripping keys.

**Example output**:
```
Before: 3100 bytes
After: 2480 bytes
Variance: -620 bytes
```

**Fix**: Use **FIX 3 (Disable Plugin Auto-Enable)** + **moltbot doctor --fix**

### Scenario C: Size Increased (> +100 bytes)

**What it means**: Config.patch worked! Accounts should exist.

**Verify**:
```bash
clawdbot gateway call config.get --params '{}' --url ws://100.66.17.93:18789 | jq '.config.accounts'
```

If accounts exist, you're done. If not, try a manual restart test.

---

## Step 4: Apply the Fix

Based on the diagnostic results, apply ONE of these fixes:

### FIX 1: Atomic Write + Kill ⭐ RECOMMENDED

**When to use**: Multiple MODIFY events detected

**How it works**: Kill gateway, immediately write config before supervisor restarts it

```bash
#!/bin/bash
# Save as: atomic_config_fix.sh

GATEWAY_URL="ws://100.66.17.93:18789"
CONFIG_FILE="$HOME/.clawdbot/clawdbot.json"

# Get current config via RPC
echo "Getting current config..."
clawdbot gateway call config.get --params '{}' --url "$GATEWAY_URL" | jq '.config' > /tmp/current_config.json

# Merge your accounts
echo "Merging accounts..."
jq '. + {
  "accounts": {
    "friday": {
      "type": "telegram",
      "chatId": "'"$FRIDAY_CHAT_ID"'",
      "token": "'"$TELEGRAM_BOT_TOKEN"'"
    },
    "jarvis": {
      "type": "telegram",
      "chatId": "'"$JARVIS_CHAT_ID"'",
      "token": "'"$TELEGRAM_BOT_TOKEN"'"
    }
  },
  "agents": {
    "list": ["main", "friday", "jarvis"]
  }
}' /tmp/current_config.json > /tmp/new_config.json

# Atomic write: kill + write in one line
echo "Applying atomic write..."
pkill -9 -f clawdbot-gateway && cat /tmp/new_config.json > "$CONFIG_FILE"

# Wait for supervisor to restart gateway
echo "Waiting for gateway restart..."
sleep 5

# Verify
echo "Verification:"
clawdbot gateway call config.get --params '{}' --url "$GATEWAY_URL" | jq '.config.accounts | keys'

echo ""
echo "If accounts appear, success! If not, check logs."
```

**Run it**:
```bash
chmod +x atomic_config_fix.sh
export FRIDAY_CHAT_ID="<your_id>"
export JARVIS_CHAT_ID="<your_id>"
export TELEGRAM_BOT_TOKEN="<your_token>"
./atomic_config_fix.sh
```

---

### FIX 2: Config Lock

**When to use**: If atomic write doesn't work

**How it works**: Make file immutable so NOTHING can overwrite it

```bash
# Apply config.patch first
clawdbot gateway call config.patch --url ws://100.66.17.93:18789 --params "{
  \"baseHash\": \"$(clawdbot gateway call config.get --params '{}' --url ws://100.66.17.93:18789 | jq -r '.hash')\",
  \"patch\": {
    \"accounts\": {
      \"friday\": {\"type\": \"telegram\", \"chatId\": \"$FRIDAY_CHAT_ID\", \"token\": \"$TELEGRAM_BOT_TOKEN\"},
      \"jarvis\": {\"type\": \"telegram\", \"chatId\": \"$JARVIS_CHAT_ID\", \"token\": \"$TELEGRAM_BOT_TOKEN\"}
    },
    \"agents\": {\"list\": [\"main\", \"friday\", \"jarvis\"]}
  }
}"

# Lock the file (makes it immutable)
chattr +i ~/.clawdbot/clawdbot.json

# Trigger restart - gateway CAN'T overwrite now
pkill -SIGUSR1 -f clawdbot-gateway

# Wait and verify
sleep 5
cat ~/.clawdbot/clawdbot.json | jq '.accounts | keys'
```

**IMPORTANT**: Leave the lock in place. The config is now immutable. To change it later:
```bash
chattr -i ~/.clawdbot/clawdbot.json  # unlock
# make changes
chattr +i ~/.clawdbot/clawdbot.json  # lock again
```

---

### FIX 3: Disable Plugin Auto-Enable

**When to use**: Size decreases on startup (validation stripping)

```bash
# Add gateway config to disable auto-enable
jq '. + {
  "gateway": {
    "pluginAutoEnable": false,
    "bind": "loopback",
    "trustedProxies": ["100.0.0.0/8"]
  },
  "tailscale": {
    "mode": "serve"
  }
}' ~/.clawdbot/clawdbot.json > /tmp/new_config.json

cat /tmp/new_config.json > ~/.clawdbot/clawdbot.json

# Restart
pkill -SIGUSR1 -f clawdbot-gateway
sleep 5

# Now apply accounts
clawdbot gateway call config.patch --url ws://100.66.17.93:18789 --params "{...}"
```

---

## Step 5: Verify Persistence

**Test 1: Manual restart**
```bash
pkill -SIGUSR1 -f clawdbot-gateway
sleep 5
clawdbot gateway call config.get --params '{}' --url ws://100.66.17.93:18789 | jq '.config.accounts | keys'
```

**Test 2: Hard kill (supervisor restarts)**
```bash
pkill -9 -f clawdbot-gateway
sleep 5
clawdbot gateway call config.get --params '{}' --url ws://100.66.17.93:18789 | jq '.config.accounts | keys'
```

**Test 3: Container restart** (if possible)
```bash
docker restart <container_name>
# OR
systemctl restart clawdbot-container
```

All three tests must show `["main", "friday", "jarvis"]` in accounts.

---

## Step 6: If Still Failing

### Last Resort: Environment Variables

Some systems support env-based account config:

```bash
# Add to /etc/environment or ~/.bashrc
export CLAWDBOT_ACCOUNTS_FRIDAY_TYPE=telegram
export CLAWDBOT_ACCOUNTS_FRIDAY_CHATID=<id>
export CLAWDBOT_ACCOUNTS_FRIDAY_TOKEN=<token>
export CLAWDBOT_ACCOUNTS_JARVIS_TYPE=telegram
export CLAWDBOT_ACCOUNTS_JARVIS_CHATID=<id>
export CLAWDBOT_ACCOUNTS_JARVIS_TOKEN=<token>
export CLAWDBOT_AGENTS_LIST=main,friday,jarvis
```

Then restart the entire container/supervisor.

---

## Success Checklist

- [ ] Diagnostic ran successfully
- [ ] Root cause identified (race condition / validation / other)
- [ ] Appropriate fix applied
- [ ] Test 1 passed (SIGUSR1 restart)
- [ ] Test 2 passed (kill -9 restart)
- [ ] Test 3 passed (container restart) OR not applicable
- [ ] Accounts persist: `["main", "friday", "jarvis"]`

---

## Report Back

After running the diagnostic and applying the fix, report:

1. **Diagnostic findings**:
   - How many MODIFY events?
   - Size variance?
   - Likely cause?

2. **Fix applied**: Which fix did you use?

3. **Test results**:
   - Test 1 result: PASS/FAIL
   - Test 2 result: PASS/FAIL
   - Test 3 result: PASS/FAIL/N/A

4. **Final verification**:
```bash
clawdbot gateway call config.get --params '{}' --url ws://100.66.17.93:18789 | jq -C '.config.accounts'
```

Paste the output.

---

## Key Insights

1. **This is NOT a config.patch bug** - the RPC works correctly
2. **This is NOT a validation bug** - the schema validates correctly
3. **This IS a race condition** - something writes during restart
4. **The fix is timing-based** - either win the race or lock the file

Do not keep trying config.patch variations. Focus on the race condition.
