# 🧪 Dexter Finance Integration - Manual Testing Guide

**Status**: ✅ BOT LIVE & READY
**Bot**: @Jarviskr8tivbot (Telegram)
**VPS**: 72.61.7.126
**PID**: 49981

---

## Quick Start: Test Dexter Now!

### Step 1: Open Telegram
- Go to Telegram app on your phone or web
- Search for: `@Jarviskr8tivbot`
- Start chat with Jarvis

### Step 2: Send a Finance Question
Copy-paste one of these questions into the chat:

```
Is SOL bullish right now?
```

**Wait 5-10 seconds for response...**

### Step 3: What Should Happen?
✅ Bot responds with Dexter analysis
✅ Response includes Grok sentiment (e.g., "72/100 bullish")
✅ Response cites data sources
✅ Includes confidence score

---

## How Dexter is Triggered

### Finance Keywords (Any ONE triggers Dexter)
```
token          price          sentiment      bullish        bearish
buy            sell           position       trade          crypto
sol            btc            eth            wallet         portfolio
should i       is             trending       moon           rug
pump           dump           volume         liquidity
```

### Examples of Questions That WILL Trigger Dexter:
✅ "Is SOL bullish?"
✅ "What's the BTC sentiment?"
✅ "Should I buy ETH?"
✅ "Check my portfolio"
✅ "Is this a pump and dump?"
✅ "What tokens are trending?"

### Examples That Will NOT Trigger Dexter:
❌ "Hi, how are you?"
❌ "Tell me a joke"
❌ "What time is it?"
❌ "Hello there"

---

## Test Scenarios (Copy-Paste These)

### Easy Tests (Start Here)

**Test 1: Basic Sentiment**
```
Is SOL bullish?
```
Expected: Sentiment score for SOL, buy/sell recommendation

**Test 2: Token Sentiment**
```
What's the sentiment on BTC?
```
Expected: BTC analysis, confidence level

**Test 3: Trend Check**
```
Is ETH trending up?
```
Expected: Trend analysis with data points

---

### Medium Tests

**Test 4: Trading Decision**
```
Should I buy BONK right now?
```
Expected: Recommendation with reasoning, risk assessment

**Test 5: Portfolio Check**
```
Check my position on SOL
```
Expected: Current position status, unrealized P&L

**Test 6: Market Analysis**
```
What are support levels for ETH?
```
Expected: Support/resistance prices, trading levels

---

### Advanced Tests

**Test 7: Risk Assessment**
```
Is this a rug pull risk?
```
Expected: Risk score, warning signs

**Test 8: Volume Analysis**
```
Check volume on trending tokens
```
Expected: Volume data, liquidity analysis

**Test 9: Multi-Token Question**
```
Which is more bullish - SOL or BTC?
```
Expected: Comparative analysis, recommendation

---

### Control Tests (Should NOT Trigger Dexter)

**Test 10: Non-Finance Question**
```
What's the weather like?
```
Expected: Normal bot response (NOT Dexter analysis)

**Test 11: Another Non-Finance**
```
Tell me a joke
```
Expected: Normal bot response (NOT Dexter analysis)

---

## What to Look For in Response

### Good Response ✅
```
🎯 SOL Sentiment Analysis

Grok Sentiment: 72/100 BULLISH
Price: $198.50 (+5.2% 24h)
Volume: Strong

Analysis:
Multiple bullish indicators detected. Support at $195,
resistance at $210.

Recommendation: BUY on dips
Confidence: 78%

Powered by Grok (1.0x weighting)
```

### Signs Something is Wrong ❌
- No response after 30 seconds
- Response doesn't mention "Grok"
- Confidence score is 0% or negative
- ERROR message appears
- Multiple bot responses
- Response format doesn't match expected

---

## Monitoring Logs While Testing

### In Another Terminal Window

**Check Bot Status:**
```bash
ssh root@72.61.7.126 "ps aux | grep tg_bot.bot | grep -v grep"
```
Expected output: 1 line with PID

**Monitor Real-Time Logs:**
```bash
ssh root@72.61.7.126 "tail -f /home/jarvis/Jarvis/logs/tg_bot.log" | grep -i "dexter\|finance\|grok\|error"
```

**Check Recent Activity:**
```bash
ssh root@72.61.7.126 "grep -i 'dexter\|finance' /home/jarvis/Jarvis/logs/tg_bot.log | tail -20"
```

**Count Dexter Invocations:**
```bash
ssh root@72.61.7.126 "grep -ic 'dexter' /home/jarvis/Jarvis/logs/tg_bot.log"
```

---

## Testing Checklist

For each test question you send, verify:

### During Test
- [ ] Question sent to @Jarviskr8tivbot
- [ ] Question contains at least 1 finance keyword
- [ ] Waiting 5-10 seconds for response

### Response Received
- [ ] Response appears in Telegram chat
- [ ] Response includes Grok sentiment
- [ ] Response format looks reasonable
- [ ] No ERROR message shown

### Log Verification
- [ ] Check logs show "Dexter" or "finance"
- [ ] No ERROR or EXCEPTION in logs
- [ ] Grok API call logged
- [ ] Response generated with confidence score

### Quality Check
- [ ] Confidence > 50%
- [ ] Recommendation is clear
- [ ] Data points make sense
- [ ] Sources cited (should mention Grok)

---

## Testing Results Template

Use this template to document your test results:

```
TEST #1: Is SOL bullish?
├─ Sent: 2026-01-18 09:15:00
├─ Response Received: YES / NO (⏱️ __ seconds)
├─ Includes Grok Sentiment: YES / NO
├─ Confidence Score: __/100
├─ Recommendation: [quote response]
├─ Log Status: ✓ Clean / ❌ Errors
└─ Result: PASS / FAIL

Notes:
[Any observations about response quality, timing, format]
```

---

## Troubleshooting

### Problem: No Response After 30 Seconds

**Check 1: Did Keywords Match?**
- Reread the finance keywords list
- Your question MUST contain at least one
- "Is SOL bullish?" ✅ (contains "is" + "bullish")
- "Hello" ❌ (no keywords)

**Check 2: Is Bot Running?**
```bash
ssh root@72.61.7.126 "ps aux | grep tg_bot.bot | grep -v grep"
```
Should see: 1 line with process

**Check 3: Check Recent Logs**
```bash
ssh root@72.61.7.126 "tail -50 /home/jarvis/Jarvis/logs/tg_bot.log"
```
Look for: "Received message", "Dexter", or errors

**Check 4: Restart Bot**
```bash
ssh root@72.61.7.126 << 'EOF'
pkill -9 -f tg_bot.bot
sleep 2
rm -f /home/jarvis/Jarvis/data/locks/*.lock
nohup /home/jarvis/Jarvis/venv/bin/python -m tg_bot.bot >> /home/jarvis/Jarvis/logs/tg_bot.log 2>&1 &
sleep 3
ps aux | grep tg_bot.bot | grep -v grep
EOF
```

### Problem: Response Doesn't Include Grok Sentiment

Check that bot.py is using the instance lock utility:
```bash
ssh root@72.61.7.126 "grep -n 'acquire_instance_lock' /home/jarvis/Jarvis/tg_bot/bot.py | head -3"
```

Check that Dexter bot_integration is loaded:
```bash
ssh root@72.61.7.126 "grep -n 'process_finance_question' /home/jarvis/Jarvis/tg_bot/services/chat_responder.py | head -3"
```

### Problem: Bot Keeps Restarting (Conflict Errors Return)

This should NOT happen with the lock fix deployed. If it does:

```bash
ssh root@72.61.7.126 "tail -100 /home/jarvis/Jarvis/logs/tg_bot.log | grep -i conflict"
```

If Conflict errors appear, run:
```bash
ssh root@72.61.7.126 << 'EOF'
pkill -9 -f tg_bot.bot
sleep 2
rm -f /home/jarvis/Jarvis/data/locks/*.lock
nohup /home/jarvis/Jarvis/venv/bin/python -m tg_bot.bot >> /home/jarvis/Jarvis/logs/tg_bot.log 2>&1 &
EOF
```

---

## Success Metrics

### Iteration 2 Passes When:
✅ **Functionality**: Dexter responds to finance questions
✅ **Accuracy**: Responses include Grok sentiment
✅ **Speed**: Response within 5-10 seconds
✅ **Format**: Response includes confidence and data
✅ **Stability**: No Conflict errors in logs
✅ **Control**: Non-finance questions don't trigger Dexter

### Iteration 2 Fails If:
❌ No response to finance questions (>30 seconds)
❌ Conflict errors in logs
❌ Multiple bot instances spawn
❌ Grok sentiment not included
❌ ERROR or EXCEPTION in logs
❌ Bot crashes on Dexter questions

---

## Iteration 2 Complete When:

- [x] Test plan created
- [x] Monitoring scripts ready
- [x] Bot deployed and running
- [ ] Send 3+ test questions
- [ ] Verify responses in Telegram
- [ ] Confirm no errors in logs
- [ ] Document results
- [ ] Iterate on any issues found
- [ ] Sign off on stability

---

## Next Steps

### RIGHT NOW:
1. Open Telegram: @Jarviskr8tivbot
2. Send test question: "Is SOL bullish?"
3. Monitor response (5-10 seconds)
4. Check logs for Dexter activity
5. Document result

### AFTER FIRST TEST:
1. Send 2-3 more test questions
2. Try questions of different difficulty
3. Test non-finance control questions
4. Monitor for any errors
5. Iterate on improvements

### WHEN ALL TESTS PASS:
1. Ralph Wiggum Iteration 2 COMPLETE
2. Document learnings
3. Prepare for next iteration
4. Consider production hardening

---

## Test Results Log

Document your test results here:

| # | Question | Time (s) | Grok Included | Confidence | Status |
|---|----------|----------|---------------|-----------|--------|
| 1 | Is SOL bullish? | ⏳ | ⏳ | ⏳ | ⏳ |
| 2 | What's BTC sentiment? | ⏳ | ⏳ | ⏳ | ⏳ |
| 3 | Should I buy ETH? | ⏳ | ⏳ | ⏳ | ⏳ |
| 4 | Hi, how are you? (control) | ⏳ | ⏳ | ⏳ | ⏳ |

---

## Support

**If stuck**: Check the DEXTER_TESTING_PLAN.md for comprehensive guide
**If errors**: Check logs: `tail -100 /home/jarvis/Jarvis/logs/tg_bot.log`
**If bot down**: Restart with commands in "Restart Bot" section
**Questions**: Review bot_integration.py for Dexter logic

---

**Status**: 🟢 READY FOR MANUAL TESTING

**Next**: Send first test question to @Jarviskr8tivbot!
