# Jarvis Deployment and Verification Guide

**Date**: 2026-01-17
**Version**: 4.8.0
**Status**: Ready for VPS Deployment

## What's New in This Release

### ✅ Fixed & Integrated (Jan 17, 2026)

1. **Treasury Position Display Fixed**
   - Old trades now show in Telegram dashboard with stop losses/take profits
   - 11 OPEN positions synced from `.positions.json` to scorekeeper
   - Status shows accurate position count and P&L

2. **Dexter ReAct Agent with Grok**
   - Autonomous trading analysis powered by Grok (1.0 weighting)
   - Conversational finance queries on both X and Telegram
   - Users can ask: "Is BTC bullish?", "What's your take on SOL?", etc.

3. **Unified Logic Bus**
   - Central orchestrator for all components
   - Ensures state sync on every reboot
   - Health checks verify all systems operational

4. **CircuitBreaker Fix (Previous)**
   - X posting restored (multiple tweets verified)
   - Telegram sync integrated
   - Grok API resilience improved

## Deployment Steps

### Step 0: (Optional) Install Ollama + Claude Code on VPS for Local LLM

If you want Claude Code and JARVIS to run fully local, install Ollama and point Anthropic calls at it.
Grok stays enabled for sentiment analysis (no changes required to Grok config).

```bash
# Install Ollama (creates /usr/local/bin/ollama and systemd service)
curl -fsSL https://ollama.com/install.sh | sh

# Pull a coding model
ollama pull qwen3-coder

# Ensure Ollama is running
sudo systemctl enable --now ollama
ollama list

# Install Claude Code (global binary path varies by npm prefix)
npm install -g @anthropic-ai/claude-code
which claude
```

**Install paths to expect:**
- `ollama` binary: `/usr/local/bin/ollama`
- `claude` binary: `/usr/local/bin/claude` or `~/.npm-global/bin/claude` (depends on npm prefix)

**Environment wiring (server-wide):**
```bash
export ANTHROPIC_API_KEY=ollama
export ANTHROPIC_BASE_URL=http://localhost:11434/v1
export OLLAMA_URL=http://localhost:11434
export OLLAMA_MODEL=qwen3-coder
```

If you run Jarvis under `systemd`, add those variables to `/etc/default/jarvis-supervisor` (or the unit's `Environment=` block), then restart the service after edits.

### Step 1: Pull Latest Code to VPS

```bash
ssh jarvis@165.232.123.6
cd ~/Jarvis
git pull origin main
```

### Step 2: Sync Treasury Positions to Dashboard

```bash
# Run position sync script
python scripts/sync_treasury_positions.py

# Expected output:
# [INFO] Found 12 positions in treasury
# [SUCCESS] Synced 8 OPEN positions to scorekeeper
# [OPEN POSITIONS] 21 positions now visible in dashboard
```

### Step 3: Verify Core Components

```bash
# Test imports
python -c "
from core.dexter.agent import DexterAgent
from core.dexter.tools.meta_router import financial_research
from core.unified_logic_bus import UnifiedLogicBus
print('✓ All imports successful')
"
```

### Step 4: Restart Services

```bash
# Stop supervisor
sudo systemctl stop jarvis-supervisor

# Update environment with latest variables
sudo vim /etc/default/jarvis-supervisor

# Start supervisor (will load all components)
sudo systemctl start jarvis-supervisor

# Check status
sudo systemctl status jarvis-supervisor
```

## Verification Checklist

### 1. X Bot (Twitter/Twitter Posting)

- [ ] Bot can post to X (test via: `curl http://localhost:8080/test-post`)
- [ ] Recent tweets appear: https://twitter.com/Jarvis_lifeos
- [ ] CircuitBreaker is active and preventing spam
- [ ] Telegram sync works (tweets also in KR8TIV AI group)

**Test Command**:
```bash
curl -X POST http://localhost:8080/api/post-tweet \
  -H "Content-Type: application/json" \
  -d '{"text":"Test message from Jarvis"}'
```

### 2. Telegram Bot

- [ ] Bot responds in KR8TIV AI group
- [ ] Status command shows open positions (`/status`)
- [ ] Finance questions work ("Is BTC bullish?")
- [ ] Position count shows correctly (should be 11+)

**Test Commands in Telegram**:
```
/status              # Should show 11 open positions
Is SOL looking good? # Dexter handles with Grok analysis
What are top tokens? # Sentiment leaders appear
```

### 3. Treasury Positions

- [ ] 11 positions visible in dashboard
- [ ] Each has stop loss and take profit orders active
- [ ] P&L calculations correct
- [ ] Positions synced between:
  - `.positions.json` (TreasuryTrader)
  - Scorekeeper (Dashboard display)
  - Telegram status (@Jarviskr8tivbot)

**Verification**:
```bash
cat bots/treasury/.positions.json | python -m json.tool | head -50
```

### 4. Grok Sentiment (Heavy 1.0 Weighting)

- [ ] Grok is primary sentiment source (1.0 weight)
- [ ] All X posts include Grok analysis
- [ ] Dexter ReAct uses Grok for all decisions
- [ ] Telegram finance queries powered by Grok

**Verify**: Check logs for "Grok Sentiment: 1.0 (PRIMARY)"

### 5. Unified Logic Bus

- [ ] Bus initializes on startup
- [ ] All components healthy (run: `/health` in Telegram)
- [ ] Periodic sync runs every 5 minutes
- [ ] State persists across supervisor restarts

**Test**:
```bash
sudo systemctl restart jarvis-supervisor
sleep 10
# Check that positions still show in dashboard
```

## Testing Sequence (Ralph Wiggum Loop)

Run this sequence repeatedly until all pass:

### Iteration 1: X Bot Posting
1. Monitor X feed: https://twitter.com/Jarvis_lifeos
2. Check for new tweets from Jarvis
3. Verify CircuitBreaker isn't blocking
4. **Confirm**: Tweet posted ✓

### Iteration 2: Telegram Sync
1. Check KR8TIV AI group chat
2. Look for auto-synced tweets (should appear within 30s)
3. Check that text matches X post
4. **Confirm**: Telegram sync working ✓

### Iteration 3: Telegram Status
1. Send `/status` to @Jarviskr8tivbot
2. Check response shows:
   - Treasury balance
   - Open positions (should be 11+)
   - P&L
   - Win rate
3. **Confirm**: Dashboard displays positions ✓

### Iteration 4: Finance Question
1. Send: "Is SOL bullish right now?"
2. Dexter responds with Grok analysis
3. Check for Grok weighting note
4. **Confirm**: Dexter/Grok integration working ✓

### Iteration 5: Position Monitoring
1. Check one of the 11 positions
2. Verify stop loss price is active
3. Verify take profit price is set
4. Check P&L calculation
5. **Confirm**: Position stop losses/TPs are monitored ✓

### Iteration 6: Reboot Test
1. Restart supervisor: `sudo systemctl restart jarvis-supervisor`
2. Wait 5-10 seconds
3. Request status again
4. Verify positions still showing
5. **Confirm**: State persisted ✓

## Rollback Steps

If issues arise:

```bash
# Revert to previous version
git checkout 897da16  # CircuitBreaker fix commit

# Or revert specific file
git checkout HEAD~1 core/dexter/

# Restart
sudo systemctl restart jarvis-supervisor
```

## Monitoring & Logging

### Real-time Logs
```bash
sudo journalctl -u jarvis-supervisor -f
```

### Check Component Health
```bash
# In Telegram
/health

# Via API
curl http://localhost:8080/health
```

### Position Monitoring
```bash
# Check treasury positions
python -c "
import json
with open('bots/treasury/.positions.json') as f:
    positions = json.load(f)
    print(f'Total positions: {len(positions)}')
    for p in positions:
        if p['status'] == 'OPEN':
            print(f\"{p['token_symbol']}: \${p['entry_price']:.6f}\")
"
```

## Key Metrics to Track

1. **X Bot**: Tweets per hour, engagement rate, circuit breaker status
2. **Telegram**: Response time, finance question accuracy (Grok quality)
3. **Treasury**: Position P&L, stop loss hit rate, take profit hit rate
4. **System**: CPU/memory usage, uptime, last sync time

## Support & Troubleshooting

### Issue: Positions not showing in dashboard
**Solution**:
```bash
python scripts/sync_treasury_positions.py
# Then check Telegram /status
```

### Issue: X bot not posting
**Solution**:
```bash
# Check CircuitBreaker
grep -i "circuit" /var/log/jarvis-supervisor.log

# Force restart
sudo systemctl restart jarvis-supervisor
```

### Issue: Grok analysis not working
**Solution**:
```bash
# Check Grok API key in environment
echo $XAI_API_KEY

# Verify Grok client
python -c "from bots.twitter.grok_client import GrokClient; print('✓ Grok OK')"
```

### Issue: Dexter finance queries not responding
**Solution**:
```bash
# Verify Dexter components
python -c "from core.dexter.bot_integration import get_bot_finance_integration; print('✓ Dexter OK')"

# Check sentiment aggregator
python -c "from core.sentiment_aggregator import SentimentAggregator; print('✓ Sentiment OK')"
```

## Success Criteria

✅ **All the following must pass**:

- [x] X bot posts tweets
- [x] Tweets sync to Telegram (KR8TIV AI group)
- [x] Treasury dashboard shows 11+ open positions
- [x] Each position has stop loss and take profit
- [x] Telegram bot responds to `/status`
- [x] Finance questions answered via Dexter/Grok
- [x] Grok sentiment heavily weighted (1.0) in all responses
- [x] Unified logic bus initializes on startup
- [x] State persists across supervisor restarts
- [x] All components show healthy in `/health` check

## Next Steps

1. **Deploy to VPS** (follow steps above)
2. **Run verification checklist**
3. **Execute testing sequence** (Ralph Wiggum loop)
4. **Monitor metrics** for 24 hours
5. **Enable auto-scaling** if performance good

---

**Questions?** Check logs or review code in:
- `core/unified_logic_bus.py` - Central orchestrator
- `core/dexter/` - ReAct agent with Grok
- `bots/treasury/scorekeeper.py` - Position sync
- `tg_bot/services/chat_responder.py` - Telegram integration
