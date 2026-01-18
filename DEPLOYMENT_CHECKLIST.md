# Jarvis Dexter Deployment Checklist

**Status**: Ready for final verification and testing
**Last Updated**: 2026-01-18
**Iteration**: Ralph Wiggum Iteration 2 (Dexter Testing)

---

## Pre-Deployment Verification (✅ COMPLETE)

- [x] Bot lock system deployed
- [x] Dexter framework integrated
- [x] Finance keywords configured (25+)
- [x] Grok sentiment integration ready (1.0x weighting)
- [x] Local testing framework passing (6/6 tests)
- [x] KR8TIV report deployed to Telegram
- [x] Health check tools created
- [x] Recovery scripts prepared
- [x] Documentation complete

---

## When VPS Access Restored: Quick Start (5 minutes)

### Step 1: Verify VPS Connectivity
```bash
ssh -i ~/.ssh/id_ed25519 root@72.61.7.126 "echo 'SSH OK'"
```
**Expected**: SSH connection succeeds

### Step 2: Run Bot Recovery Script
```bash
bash scripts/recover_bot_on_vps.sh
```
**Expected**:
- Stops any existing bot processes
- Cleans lock files
- Restarts bot with fresh process
- Shows bot PID (should be running)
- Recent logs show no errors

### Step 3: Verify Bot Health
```bash
PYTHONIOENCODING=utf-8 ./.venv/Scripts/python.exe health_check_bot.py
```
**Expected**: All checks pass

### Step 4: Run Full Test Suite
```bash
PYTHONIOENCODING=utf-8 ./.venv/Scripts/python.exe run_full_test_suite.py
```
**Expected**: All tests pass, report saved to test_results.json

---

## Iteration 2: Manual Testing (30 minutes)

### Test Suite Setup

Open Telegram: `@Jarviskr8tivbot`

### Test Group 1: Easy (Finance Detection)

Send each question, wait 5-10 seconds for response:

1. **"Is SOL bullish?"**
   - Expected: Dexter triggers with SOL sentiment
   - Check: Grok sentiment score present (e.g., "72/100 BULLISH")
   - Check: Price and volume data included
   - Result: [PASS/FAIL]

2. **"What's the BTC sentiment?"**
   - Expected: Dexter triggers with BTC analysis
   - Check: Confidence score included
   - Check: Recommendation (BUY/HOLD/SELL)
   - Result: [PASS/FAIL]

3. **"Is ETH trending up?"**
   - Expected: Dexter triggers with ETH trend analysis
   - Check: Volume indicators present
   - Check: Support/resistance levels mentioned
   - Result: [PASS/FAIL]

### Test Group 2: Medium (Position Analysis)

4. **"Check my portfolio sentiment"**
   - Expected: Dexter routes to portfolio analyzer
   - Check: Multi-asset sentiment aggregation
   - Result: [PASS/FAIL]

5. **"Should I buy BONK right now?"**
   - Expected: Dexter provides trading recommendation
   - Check: Risk assessment present
   - Check: Entry/exit levels suggested
   - Result: [PASS/FAIL]

### Test Group 3: Control (Should NOT Trigger Dexter)

6. **"Hi, how are you?"**
   - Expected: Normal bot response (NOT Dexter)
   - Check: No Grok sentiment score
   - Result: [PASS/FAIL]

7. **"Tell me a joke"**
   - Expected: Normal bot response (NOT Dexter)
   - Check: No financial analysis
   - Result: [PASS/FAIL]

---

## Real-Time Log Monitoring

While running tests, in another terminal:

```bash
ssh -i ~/.ssh/id_ed25519 root@72.61.7.126 \
  "tail -f /home/jarvis/Jarvis/logs/tg_bot.log | grep -i 'dexter\|finance\|grok\|error'"
```

**What to watch for**:
- `[Dexter]` log entries when triggering
- `process_finance_question` calls
- `Grok sentiment` scores
- Any ERROR or EXCEPTION messages
- Response times (should be <10s)

---

## Performance Metrics to Track

| Metric | Target | Actual |
|--------|--------|--------|
| Response Time (avg) | <10s | ? |
| Dexter Trigger Rate | >80% | ? |
| Grok Score Format | Always present | ? |
| Confidence Score | >50% | ? |
| Control Test Non-Trigger | 100% | ? |
| Error Rate | 0% | ? |

---

## Success Criteria

### Iteration 2 PASSES When:
- ✅ Send 3+ test questions
- ✅ All responses include Grok sentiment
- ✅ Response time <10 seconds consistently
- ✅ Confidence scores present (>50%)
- ✅ Control tests don't trigger Dexter
- ✅ No ERROR messages in logs
- ✅ Bot stays stable (uptime >1 hour)

### Iteration 2 FAILS If:
- ❌ No response to finance questions (>30s timeout)
- ❌ Conflict errors reappear
- ❌ Multiple bot instances spawn
- ❌ Grok sentiment missing
- ❌ ERROR or EXCEPTION in logs
- ❌ Bot crashes

---

## If Issues Occur

### Issue: Bot Not Responding

1. Check process:
   ```bash
   ssh -i ~/.ssh/id_ed25519 root@72.61.7.126 \
     "ps aux | grep tg_bot.bot | grep -v grep"
   ```

2. Check logs:
   ```bash
   ssh -i ~/.ssh/id_ed25519 root@72.61.7.126 \
     "tail -50 /home/jarvis/Jarvis/logs/tg_bot.log"
   ```

3. Restart bot:
   ```bash
   bash scripts/recover_bot_on_vps.sh
   ```

### Issue: Dexter Not Triggering

1. Verify keywords are correct (check FINANCE_KEYWORDS in test_dexter_locally.py)
2. Check chat_responder.py is calling _try_dexter_finance_response()
3. Verify Dexter modules are loaded

### Issue: Grok Sentiment Missing

1. Check XAI_API_KEY is valid in tg_bot/.env
2. Verify Grok integration in core/dexter/tools/meta_router.py
3. Check for API errors in logs

---

## Documentation References

- **Overall Status**: `RALPH_WIGGUM_STATUS_REPORT.md`
- **Testing Plan**: `DEXTER_TESTING_PLAN.md`
- **Manual Guide**: `DEXTER_MANUAL_TEST_GUIDE.md`
- **Live Tracker**: `ITERATION_2_LIVE_TRACKER.md`
- **Local Testing**: Run `test_dexter_locally.py`

---

## Completion Criteria

Once all tests pass:

1. [ ] Document results in ITERATION_2_LIVE_TRACKER.md
2. [ ] Update git log with test results
3. [ ] Mark Iteration 2 as COMPLETE
4. [ ] Plan Iteration 3 improvements
5. [ ] Create handoff document

---

## Post-Testing: Iteration 3 Roadmap

### Optimization (If time allows)
- Response time optimization (<5s target)
- Prompt refinement for better analysis
- Multi-token parallel analysis
- Advanced risk scoring

### Reliability
- Fallback to secondary sentiment sources
- Error recovery automation
- Alert system for failures

### Features
- Portfolio tracking
- Price alerts
- Position monitoring
- Risk calculations

---

## Quick Commands Reference

```bash
# Recovery
bash scripts/recover_bot_on_vps.sh

# Health check
PYTHONIOENCODING=utf-8 ./.venv/Scripts/python.exe health_check_bot.py

# Local testing
PYTHONIOENCODING=utf-8 ./.venv/Scripts/python.exe test_dexter_locally.py

# Full test suite
PYTHONIOENCODING=utf-8 ./.venv/Scripts/python.exe run_full_test_suite.py

# Real-time logs
ssh -i ~/.ssh/id_ed25519 root@72.61.7.126 \
  "tail -f /home/jarvis/Jarvis/logs/tg_bot.log | grep -i dexter"

# Check bot status
ssh -i ~/.ssh/id_ed25519 root@72.61.7.126 \
  "ps aux | grep tg_bot.bot | grep -v grep"

# Count Dexter invocations
ssh -i ~/.ssh/id_ed25519 root@72.61.7.126 \
  "grep -ic dexter /home/jarvis/Jarvis/logs/tg_bot.log"
```

---

## Estimated Timeline

- **Step 1-4 (VPS verification)**: 5 min
- **Test Group 1 (Easy)**: 5 min
- **Test Group 2 (Medium)**: 5 min
- **Test Group 3 (Control)**: 5 min
- **Documentation**: 5 min
- **Total**: ~25 minutes

---

## Sign-Off

**When ALL items completed**:

```
Iteration 2: COMPLETE ✅
Date: [When verified]
Tests Passed: [#/#]
Status: READY FOR PRODUCTION
Next: Iteration 3 Planning
```

---

**Prepared by**: Ralph Wiggum Loop Session
**Date**: 2026-01-18
**Ready**: YES ✅
**Confidence**: HIGH
