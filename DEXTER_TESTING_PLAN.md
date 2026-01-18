# 🎯 Dexter Finance Integration - Testing Plan

**Iteration**: Ralph Wiggum #2
**Date**: 2026-01-18
**Status**: 🟢 READY TO TEST
**Bot**: @Jarviskr8tivbot (Telegram)
**Live Bot**: PID 49981 on VPS

---

## How Dexter Works

### Trigger Keywords
Any question containing these keywords will trigger Dexter:

**Core Finance Keywords**:
- `token`, `price`, `sentiment`, `bullish`, `bearish`
- `buy`, `sell`, `position`, `trade`, `crypto`
- `sol`, `btc`, `eth` (specific tokens)
- `wallet`, `portfolio`, `trending`, `moon`
- `rug`, `pump`, `dump`, `volume`, `liquidity`
- `should i`, `is` (interrogative)

**Example**: "Is SOL bullish?" → Contains "is" + "bullish" → Dexter triggers ✅

---

## Test Scenarios

### Test Set 1: Basic Sentiment Questions (Easy)

| Question | Keywords | Expected | Status |
|----------|----------|----------|--------|
| "Is SOL bullish right now?" | is, bullish, sol | Dexter response with sentiment | ⏳ |
| "What's the sentiment on BTC?" | sentiment, btc | Grok sentiment score | ⏳ |
| "Is ETH trending?" | is, trending, eth | Market analysis | ⏳ |

### Test Set 2: Trading Decision Questions (Medium)

| Question | Keywords | Expected | Status |
|----------|----------|----------|--------|
| "Should I buy SOL?" | should, buy, sol | Trading recommendation | ⏳ |
| "Is it a good time to sell?" | sell, is | Risk/reward analysis | ⏳ |
| "Check liquidation levels" | liquidation | Support/resistance data | ⏳ |

### Test Set 3: Portfolio/Position Questions (Medium)

| Question | Keywords | Expected | Status |
|----------|----------|----------|--------|
| "What's my portfolio sentiment?" | portfolio, sentiment | Position analysis | ⏳ |
| "Check my position status" | position | Current holdings | ⏳ |
| "How much volume on BONK?" | volume | Trading volume data | ⏳ |

### Test Set 4: Market Analysis (Advanced)

| Question | Keywords | Expected | Status |
|----------|----------|----------|--------|
| "Is this a pump and dump?" | pump, dump | Risk detection | ⏳ |
| "What tokens are trending?" | trending, token | Top movers | ⏳ |
| "Calculate rug pull risk" | rug, risk | Security analysis | ⏳ |

### Test Set 5: Non-Finance Questions (Should NOT Trigger)

| Question | Keywords | Expected | Status |
|----------|----------|----------|--------|
| "Hello how are you?" | (none) | Standard bot response | ⏳ |
| "What's the weather?" | (none) | Standard bot response | ⏳ |
| "Tell me a joke" | (none) | Standard bot response | ⏳ |

---

## Expected Response Format

### Dexter Response Structure
```
🎯 Dexter Finance Analysis

Grok Sentiment: [75/100 bullish | 45/100 neutral | 25/100 bearish]
Market Data: [prices, volume, trends]
Analysis: [detailed reasoning from Grok]

Confidence: [XX%]
Recommendation: [ACTION - rationale]

Data Sources: Grok-powered (1.0 weighting)
```

### Example Response
```
🎯 SOL Sentiment Analysis

Grok Sentiment: 72/100 BULLISH
Current Price: $198.50 (+5.2% 24h)
Volume: Strong, on-chain activity positive

Analysis:
- Multiple bullish indicators across Grok metrics
- Support level holding at $195
- Resistance at $210 (key level to watch)

Recommendation: BUY on dip to $195, TP at $210
Confidence: 78%

Powered by Grok (1.0x weighting)
```

---

## Testing Process

### Phase 1: Readiness Check (Right Now)
- [x] Bot deployed and running
- [x] Dexter modules loaded
- [x] Keywords configured
- [x] Lock file acquired
- [ ] Send test question and monitor logs

### Phase 2: Send Test Questions (Manual)
1. **Open Telegram**: @Jarviskr8tivbot
2. **Send Question**: "Is SOL bullish right now?"
3. **Wait**: 5-10 seconds for response
4. **Monitor**: VPS logs for Dexter execution
5. **Document**: Response quality and timing

### Phase 3: Verify Responses
1. Check response format
2. Verify Grok sentiment included
3. Check confidence scores
4. Verify data sources cited
5. Look for any errors in logs

### Phase 4: Iterate on Issues
1. If error in logs → analyze
2. If slow response → check Grok API
3. If format wrong → adjust formatting
4. If confidence low → adjust prompts

---

## Log Monitoring Commands

### Real-Time Monitoring
```bash
# Watch for Dexter activity
ssh root@72.61.7.126 "tail -f /home/jarvis/Jarvis/logs/tg_bot.log" | grep -i "dexter\|finance\|grok"

# Check for errors
ssh root@72.61.7.126 "tail -f /home/jarvis/Jarvis/logs/tg_bot.log" | grep -i "error\|exception"

# Watch all activity
ssh root@72.61.7.126 "tail -f /home/jarvis/Jarvis/logs/tg_bot.log"
```

### Historical Analysis
```bash
# Find all Dexter invocations
ssh root@72.61.7.126 "grep -i 'dexter\|finance' /home/jarvis/Jarvis/logs/tg_bot.log"

# Count errors
ssh root@72.61.7.126 "grep -i 'error' /home/jarvis/Jarvis/logs/tg_bot.log | wc -l"

# Find Grok sentiment responses
ssh root@72.61.7.126 "grep -i 'grok.*sentiment' /home/jarvis/Jarvis/logs/tg_bot.log"
```

---

## Checklist: Test a Single Question

When you test a question, verify:

- [ ] **Question Sent**: ✓ Sent to @Jarviskr8tivbot in Telegram
- [ ] **Keywords Match**: ✓ Question contains finance keywords
- [ ] **Bot Received**: ✓ Check "Received message" in logs
- [ ] **Dexter Triggered**: ✓ Look for "Dexter handled" in logs
- [ ] **Grok Called**: ✓ Look for "grok.*api" in logs
- [ ] **Response Generated**: ✓ Check for sentiment/analysis in logs
- [ ] **Response Sent**: ✓ Telegram shows response
- [ ] **No Errors**: ✓ No ERROR or Exception in logs
- [ ] **Confidence High**: ✓ Confidence score > 60%
- [ ] **Format Correct**: ✓ Includes Grok attribution

---

## Success Criteria

### Test Passes If:
✅ Bot responds to finance questions within 5-10 seconds
✅ Responses include Grok sentiment scores
✅ Responses cite data sources
✅ No ERROR or EXCEPTION in logs
✅ Confidence scores reasonable (>50%)
✅ Format matches expected template
✅ Non-finance questions NOT triggered
✅ Supervisor doesn't respawn bot

### Test Fails If:
❌ No response after 30 seconds
❌ ERROR or EXCEPTION in logs
❌ Conflict errors reappear
❌ Response format incorrect
❌ Grok not credited
❌ Confidence < 20%
❌ Multiple bot instances spawn

---

## Quick Test Questions (Copy-Paste Ready)

Send these to @Jarviskr8tivbot one at a time, waiting 10 seconds between each:

### Easy (Good starters)
```
Is SOL bullish?
```

```
What's the BTC sentiment?
```

```
Is ETH trending up?
```

### Medium
```
Should I buy BONK right now?
```

```
Check liquidation levels for SOL
```

```
What's my portfolio sentiment?
```

### Hard
```
Is this a pump and dump opportunity?
```

```
Calculate rug pull risk for new token
```

```
What tokens are trending today?
```

### Control (should NOT trigger Dexter)
```
Hi, how are you?
```

```
What's the weather like?
```

```
Tell me a joke
```

---

## Monitoring Dashboard Setup

### Create Local Monitoring Script
```bash
#!/bin/bash
# monitor_dexter.sh

echo "Starting Dexter monitoring..."
echo "Watching for: DEXTER | FINANCE | GROK | ERROR"
echo ""

ssh root@72.61.7.126 << 'EOFCOMMANDS'
echo "=== Recent Bot Status ==="
ps aux | grep "tg_bot.bot" | grep -v grep

echo ""
echo "=== Recent Dexter Activity ==="
tail -100 /home/jarvis/Jarvis/logs/tg_bot.log | grep -i "dexter\|finance\|grok"

echo ""
echo "=== Recent Errors ==="
tail -100 /home/jarvis/Jarvis/logs/tg_bot.log | grep -i "ERROR\|EXCEPTION" || echo "(none found)"

echo ""
echo "=== Last 10 Log Lines ==="
tail -10 /home/jarvis/Jarvis/logs/tg_bot.log
EOFCOMMANDS
```

---

## Iteration Plan

### Iteration 2.1: Basic Testing
1. Send 3 easy questions
2. Verify responses appear in Telegram
3. Monitor logs for Dexter execution
4. Check for errors

### Iteration 2.2: Format Verification
1. Verify all responses include Grok sentiment
2. Check confidence scores present
3. Verify data sources cited
4. Validate response structure

### Iteration 2.3: Edge Cases
1. Test non-finance questions (should NOT trigger)
2. Test ambiguous questions
3. Test multi-token questions
4. Test rapid-fire questions

### Iteration 2.4: Performance Testing
1. Measure response time
2. Monitor Grok API usage
3. Check token efficiency
4. Optimize if needed

### Iteration 2.5: Production Hardening
1. Add error recovery
2. Implement retries
3. Add monitoring alerts
4. Document for team

---

## Troubleshooting

### If No Response After Sending Question

**Check 1: Bot Running?**
```bash
ssh root@72.61.7.126 "ps aux | grep tg_bot.bot | grep -v grep"
```
Expected: 1 process with PID

**Check 2: Keywords Matched?**
Reread finance keywords list above. Your question must contain at least one.

**Check 3: Check Recent Logs**
```bash
ssh root@72.61.7.126 "tail -50 /home/jarvis/Jarvis/logs/tg_bot.log"
```
Look for: "Received message", "Dexter", "ERROR"

**Check 4: Restart Bot**
```bash
ssh root@72.61.7.126 "pkill -9 -f tg_bot.bot && sleep 2 && \
nohup /home/jarvis/Jarvis/venv/bin/python -m tg_bot.bot >> /home/jarvis/Jarvis/logs/tg_bot.log 2>&1 &"
```

---

## Success Metrics

| Metric | Target | Pass |
|--------|--------|------|
| **Response Time** | <10 seconds | ✓ When achieved |
| **Grok Sentiment Included** | 100% of responses | ✓ When achieved |
| **Error Rate** | 0% | ✓ When achieved |
| **Confidence Score Avg** | >70% | ✓ When achieved |
| **Uptime** | 99%+ | ✓ When achieved |
| **Data Source Attribution** | 100% of responses | ✓ When achieved |

---

## Next Steps

1. **NOW**: Send first test question to @Jarviskr8tivbot
2. **MONITOR**: Watch logs for Dexter response
3. **VERIFY**: Check response quality and format
4. **DOCUMENT**: Record results in this checklist
5. **ITERATE**: Send more test questions and refine

---

**Status: READY FOR TESTING - Send First Question Now!**
