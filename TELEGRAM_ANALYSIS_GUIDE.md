# Analyzing AI Picks - 15% Win / 15% Stop Loss Strategy

## Quick Manual Check

1. Open Telegram chat: **KR8TIV AI - Jarvis Life OS** (-1003408655098)

2. Scroll back 24 hours and find messages containing:
   - "Top Picks" or trophy emoji
   - "BULLISH" or "SLIGHTLY BULLISH"
   - Entry prices for low cap tokens

3. For each pick, note:
   - Token symbol (e.g., $TOKEN)
   - Entry price
   - Date/time of recommendation

4. Check subsequent messages to see if the token:
   - Hit **+15% gain** FIRST = **WIN** ✓
   - Hit **-15% loss** FIRST = **LOSS** ✗
   - Neither yet = **PENDING**

5. Calculate:
   - Win Rate = Wins / (Wins + Losses)
   - Expected Value = (Win Rate × 15%) - ((1 - Win Rate) × 15%)

## Example Analysis

```
Pick: $RETARD @ $0.05 (9:00 AM)
High: $0.06 (+20%) at 10:30 AM
Low: $0.045 (-10%) at 10:15 AM
Result: WIN (hit +15% before -15%)
```

## Automated Export Method

To export and analyze programmatically:

1. **Export chat from Telegram Desktop:**
   - Open "KR8TIV AI - Jarvis Life OS" chat
   - Click menu (three dots)
   - Export chat history
   - Choose "Machine-readable JSON"
   - Save as `telegram_export.json`

2. **Run analysis:**
   ```bash
   python scripts/fetch_telegram_history.py
   ```

3. **Get price data:**
   For each pick, query DexScreener or Jupiter API to get:
   - Minute-by-minute price data after entry
   - Find first occurrence of +15% or -15% from entry

## What to Look For in Reports

**Low cap criteria:**
- Market cap < $10M
- Token age < 7 days
- Listed on bags.fm or pump.fun

**AI pick indicators:**
- Score >= 0.50
- Sentiment: BULLISH
- Ratio >= 1.5x (buy/sell)
- Entry timing note (e.g., "<50% pump")

## Expected Win Rate

Based on backtesting (docs/SENTIMENT_ENGINE_DATA_ANALYSIS.md):
- Tokens with score 0.5-0.7: ~50% TP rate
- Tokens with ratio >= 2.0x: ~67% TP rate
- Early entry (<50% pump): ~67% TP rate
- Late entry (>100% pump): ~29% TP rate

**Strategy Expectation:**
If following AI picks with these filters:
- Expected win rate: 40-60%
- Expected value: -2% to +10% per trade
- Need win rate > 50% to be profitable with 1:1 risk/reward

## To Improve Strategy

1. **Filter for higher quality:**
   - Only take picks with score 0.5-0.65 (avoid overconfidence)
   - Only take picks with ratio >= 2.0x
   - Only take picks early (<50% pump from launch)

2. **Adjust risk/reward:**
   - Consider 10% stop loss / 20% take profit (2:1 R/R)
   - Or trail stop loss after +10% gain

3. **Position sizing:**
   - Risk only 1-2% of portfolio per pick
   - Scale position size by confidence score
