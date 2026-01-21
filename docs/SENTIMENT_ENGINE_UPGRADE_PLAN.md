# Sentiment Engine Upgrade Plan

**Generated:** January 21, 2026
**Based on:** 56 calls analyzed, 9 executed trades, data from Jan 13-21, 2026

---

## Executive Summary

The data analysis revealed that the current engine makes good calls (29% hit 25%+ TP at some point), but several scoring parameters are miscalibrated. This plan addresses the gap between data findings and current implementation.

---

## Current vs Recommended Settings

| Parameter | Current | Data Shows | Recommended |
|-----------|---------|------------|-------------|
| Entry pump threshold | 50%+ = penalty | <50% pump = 67% TP rate | Lower to 40% |
| Ratio minimum for BULLISH | >= 1.5x | >= 2x = 67% TP rate | Raise to 2.0x |
| High score handling | No cap | High (>=0.7) = 0% TP rate | Penalize 0.7+ |
| Keyword detection | None | "momentum" = 14% TP rate | Add penalty |
| Report count | Not tracked | >=5 reports = better | Add bonus |

---

## Upgrade #1: Stricter Entry Timing

**File:** `bots/buy_tracker/sentiment_report.py`
**Lines:** 388-400

### Current Logic:
```python
if self.change_24h > 50:
    self.chasing_pump = True
    score -= 0.20
    confidence -= 0.2
elif self.change_24h > 30:
    self.chasing_pump = True
    score -= 0.10
    confidence -= 0.1
```

### Recommended Change:
```python
# DATA-DRIVEN: Early entry (<50% pump) = 67% TP rate
# Late entry (>=50% pump) = 29% TP rate (2x worse)
if self.change_24h > 100:
    # Extreme pump - almost never works
    self.chasing_pump = True
    score -= 0.40  # Increased from implicit
    confidence -= 0.3
elif self.change_24h > 50:
    self.chasing_pump = True
    score -= 0.30  # Increased from 0.20
    confidence -= 0.25
elif self.change_24h > 40:
    # NEW: Moderate pump threshold lowered
    self.chasing_pump = True
    score -= 0.15  # New tier
    confidence -= 0.15
elif self.change_24h > 30:
    # Caution zone but not chasing_pump flag
    score -= 0.08
    confidence -= 0.1
```

**Rationale:** Data shows 66.7% TP rate for entries <50% pump vs 28.6% for entries >=50%. Adding 40% tier catches more late entries.

---

## Upgrade #2: Stricter Ratio Requirement

**File:** `bots/buy_tracker/sentiment_report.py`
**Lines:** 576-579

### Current Logic:
```python
if self.sentiment_score > 0.55 and self.buy_sell_ratio >= 1.5 and not self.chasing_pump:
    self.sentiment_label = "BULLISH"
```

### Recommended Change:
```python
# DATA-DRIVEN: Ratio >= 2x = 67% TP rate vs Ratio < 2x = 25% TP rate
if self.sentiment_score > 0.55 and self.buy_sell_ratio >= 2.0 and not self.chasing_pump:
    self.sentiment_label = "BULLISH"
    self.grade = "A" if self.sentiment_score > 0.65 else "A-"
elif self.sentiment_score > 0.55 and self.buy_sell_ratio >= 1.5 and not self.chasing_pump:
    # Ratio 1.5-2.0 = SLIGHTLY BULLISH (not full bullish)
    self.sentiment_label = "SLIGHTLY BULLISH"
    self.grade = "B+"
```

**Rationale:** Raising BULLISH requirement from 1.5x to 2.0x would have improved TP rate from 25% to 67%.

---

## Upgrade #3: High Score Penalty (NEW)

**File:** `bots/buy_tracker/sentiment_report.py`
**After line ~573 (before grade assignment)**

### Add New Logic:
```python
# DATA-DRIVEN: High scores (>=0.7) had 0% TP rate
# The engine is overconfident on already-pumped tokens
if self.sentiment_score >= 0.70:
    # Penalize overconfidence - these calls historically fail
    overconfidence_penalty = (self.sentiment_score - 0.65) * 0.5  # Cap excess confidence
    self.sentiment_score -= overconfidence_penalty
    self.confidence -= 0.15
    logger.info(f"{self.symbol}: Overconfidence penalty applied (-{overconfidence_penalty:.2f})")
```

**Rationale:** Data shows High Score (>=0.7) had 0% TP rate. Medium scores (0.5-0.7) had 50% TP rate. The system is overconfident on tokens that have already pumped.

---

## Upgrade #4: Keyword Detection (NEW)

**File:** `bots/buy_tracker/sentiment_report.py`
**In the Grok response parsing section (~line 1046-1064)**

### Add New Logic:
```python
# DATA-DRIVEN: Keyword mentions correlate with worse outcomes
# "momentum" = 14% TP rate, "pump" = 20% TP rate
reason_lower = reason.lower()
keyword_penalty = 0.0

if "momentum" in reason_lower:
    keyword_penalty += 0.10
    token.has_momentum_mention = True
if "pump" in reason_lower and "pump.fun" not in reason_lower:
    keyword_penalty += 0.08
    token.has_pump_mention = True
if "surge" in reason_lower or "spike" in reason_lower:
    keyword_penalty += 0.05

if keyword_penalty > 0:
    token.grok_score -= keyword_penalty
    logger.info(f"{token.symbol}: Hype keyword penalty (-{keyword_penalty:.2f})")
```

**Rationale:** "momentum" mentions had 14% TP rate vs 42.9% without. "pump" mentions had 20% TP rate vs 33% without. Hype words correlate with already-moved tokens.

---

## Upgrade #5: Multi-Sighting Bonus (NEW)

**File:** `bots/buy_tracker/sentiment_report.py`
**In `calculate_sentiment()` or where report count is available**

### Add New Logic:
```python
# DATA-DRIVEN: Multiple reports (>=5) = 36.4% TP rate vs Few (<5) = 0% TP rate
# Track number of times we've seen this token across reports
if hasattr(self, 'report_count') and self.report_count >= 5:
    score += 0.08
    confidence += 0.1
    logger.info(f"{self.symbol}: Multi-sighting bonus (+0.08)")
elif hasattr(self, 'report_count') and self.report_count < 3:
    # First or second sighting - be cautious
    score -= 0.05
    confidence -= 0.1
```

**Rationale:** Tokens seen in >=5 reports had 36.4% TP rate. Tokens seen in <5 reports had 0% TP rate. Persistence is a real signal.

---

## Upgrade #6: Top 10 Picks Criteria

**File:** `bots/buy_tracker/sentiment_report.py`
**Lines:** ~2807-2842 (Grok conviction picks prompt)**

### Update the Prompt:
```python
prompt = f"""Analyze these assets and provide your TOP 10 conviction picks.

DATA-DRIVEN ENTRY CRITERIA (based on backtested patterns):
- CRITICAL: Only pick tokens NOT already pumped >40% in 24h (late entries fail 71% of the time)
- CRITICAL: Only pick tokens with buy/sell ratio >= 2.0x (ratio >=2x wins 67% of the time)
- AVOID tokens with extreme score confidence - medium conviction works better
- PREFER tokens seen across multiple data sources (consistency signal)

REJECT IF:
- Already pumped >50% in 24h (chasing)
- Buy/sell ratio < 1.5x (no buying pressure)
- Only appeared in 1-2 reports (unconfirmed)
- Mentions "momentum" or "pump" in reasoning (already moved)

QUALITY REQUIREMENTS:
- ONLY recommend tokens with $50K+ liquidity and $500K+ market cap
- NEVER recommend pump.fun launches, honeypots, or tokens < 24h old
- AVOID tokens that pumped >500% with no catalyst (manipulation)
- PREFER established tokens with real community and utility

{asset_summary}
{learnings_section}

OPTIMAL POSITION SIZING:
- High ratio (>=3x) + Early entry (<20% pump): Full position
- Medium ratio (2-3x) + Moderate entry: 75% position
- Lower ratio (1.5-2x): 50% position or skip

TIMEFRAME GUIDANCE:
- Meme tokens: TP 25%, SL 15% (short timeframe)
- Stock tokens: TP 10%, SL 4% (medium timeframe)
- Blue chips: TP 18%, SL 12% (longer timeframe)

For each pick, provide:
1. SYMBOL - The asset symbol
2. ASSET_CLASS - token/stock/index
3. CONVICTION - Score from 1-100 (avoid extreme 90+ scores - overconfidence fails)
4. REASONING - Brief explanation (mention liquidity/mcap, ratio, pump level)
5. TARGET - Target price (approximate % gain)
6. STOP - Stop loss (approximate % loss)
7. TIMEFRAME - short (1-7 days), medium (1-4 weeks), long (1-3 months)

Format EXACTLY as:
PICK|SYMBOL|ASSET_CLASS|CONVICTION|REASONING|TARGET_PCT|STOP_PCT|TIMEFRAME
```

---

## Summary of All Changes

| # | File | Change | Impact |
|---|------|--------|--------|
| 1 | sentiment_report.py:388-400 | Lower pump threshold to 40%, increase penalties | Catch more late entries |
| 2 | sentiment_report.py:576-579 | Raise ratio minimum to 2.0x for BULLISH | Filter weak buy pressure |
| 3 | sentiment_report.py:~573 | Add high score penalty (>=0.7) | Prevent overconfidence |
| 4 | sentiment_report.py:~1046 | Add keyword detection for "momentum"/"pump" | Filter hype signals |
| 5 | sentiment_report.py:calculate_sentiment | Add multi-sighting bonus | Reward persistence |
| 6 | sentiment_report.py:~2807 | Update Top 10 prompt with data-driven criteria | Better picks |

---

## Expected Improvements

Based on the data analysis, implementing these changes should:

1. **Reduce false bullish calls** - Stricter ratio and pump thresholds
2. **Improve TP rate** - From ~29% to estimated 45-55%
3. **Avoid overconfident traps** - High score penalty catches pumped tokens
4. **Filter hype** - Keyword detection catches FOMO entries
5. **Better Top 10** - Data-driven selection criteria

---

## Implementation Priority

1. **HIGH**: Ratio upgrade (2.0x threshold) - Immediate impact
2. **HIGH**: Pump threshold (40%) - Catches more late entries
3. **MEDIUM**: Keyword detection - New signal
4. **MEDIUM**: High score penalty - New signal
5. **LOW**: Multi-sighting bonus - Requires tracking infrastructure

---

## Testing Plan

After implementation:
1. Run backtester on historical predictions: `scripts/backtesting.py`
2. Compare TP/SL rates with old parameters
3. Monitor next 20 bullish calls for improvement
4. Track max gain achieved vs opportunity captured

---

*Generated by Jarvis Data Analysis Engine*
