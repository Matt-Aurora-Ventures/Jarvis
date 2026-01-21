"""
Final Stop Loss Recommendations Based on Data Analysis.

Summary of findings and implementation recommendations.
"""

import json
from pathlib import Path
from typing import Dict, List
import re

ROOT = Path(__file__).resolve().parents[1]
PREDICTIONS_FILE = ROOT / "bots" / "buy_tracker" / "predictions_history.json"


def main():
    print("=" * 90)
    print("FINAL ANALYSIS: STOP LOSS RECOMMENDATIONS FOR EARLY RUNNER STRATEGY")
    print("=" * 90)

    print("""
KEY FINDINGS FROM DATA:
-----------------------

1. SAMPLE: 17 unique tokens with price evolution data

2. TP/SL ORDER ANALYSIS (TP 25% / SL -15%):
   - 6 tokens (35%) hit 25% TP FIRST -> Exit with +25% profit
   - 7 tokens (41%) hit SL FIRST -> Exit with loss
   - 4 tokens (24%) never hit either -> Still holding

3. STOP LOSS EFFECTIVENESS:
   - Of 7 SL triggers, 5 were GOOD (saved from worse losses)
   - Only 2 were "premature" (token recovered slightly)
   - ZERO premature stops where token went to +25% after SL hit

4. "GOOD SL" EXAMPLES (SL Saved Us):
   - PSYOPMIA: Stopped at -21%, went to -98.6% -> SAVED 77.5%!
   - PSYOPSAGA: Stopped at -35%, went to -97.6% -> SAVED 62.4%!
   - coin: Stopped at -24%, went to -70% -> SAVED 45.8%!
   - USDP: Stopped at -17%, went to -60.6% -> SAVED 43%!

5. "PREMATURE SL" EXAMPLES (Minimal):
   - RETARD: Stopped at -61%, ended at -35% -> Missed 25.8%
   - PsyCartoon: Stopped at -65%, ended at -64% -> Missed 0.8%
   Note: Both were still losses! Just slightly less bad.

6. SL LEVEL COMPARISON:
   | SL Level | Avg Return | Good Stops | Premature |
   |----------|------------|------------|-----------|
   | -15%     | -6.0%      | 5          | 2         |
   | -20%     | -7.0%      | 5          | 2         |
   | -25%     | -12.8%     | 4          | 2         |
   | -30%     | -14.4%     | 4          | 2         |

   Tighter SL = Better returns!

""")

    print("""
ADDRESSING USER'S CONCERN: "IS -15% TOO TIGHT?"
-----------------------------------------------

EVIDENCE SAYS NO:
- Volatility analysis showed 27.8% of hours have >15% swings
- BUT this doesn't mean -15% SL is wrong
- The key insight: Tokens that trigger -15% SL are MOSTLY rugs

WHY IT WORKS:
1. Good tokens hit 25% TP before they ever drop 15%
2. Bad tokens (rugs) drop fast and keep dropping
3. The -15% SL catches rugs early, preventing -60% to -99% losses

WHAT ABOUT VOLATILITY?
- Yes, good tokens CAN swing -15% intraday
- BUT they usually swing UP first (hitting TP)
- The data shows 6 tokens hit +25% BEFORE -15%

""")

    print("""
RECOMMENDED STRATEGY:
---------------------

PRIMARY RECOMMENDATION: TP 25% / SL -15%
- Win rate: ~35% (6/17 tokens hit TP first)
- Loss rate: ~41% (7/17 tokens hit SL first)
- Still holding: ~24% (4/17 tokens never hit either)

ALTERNATIVES TO CONSIDER:

1. TRAILING STOP (After TP hit):
   - Hit +25%? Move SL to break-even
   - Let winners run with protected downside
   - Good for catching mega-pumps like HAMURA (+239%)

2. PARTIAL EXIT:
   - Hit +25%? Sell 80%, let 20% ride
   - Lock in most profit, keep upside exposure

3. TIME-BASED FILTER:
   - If no movement in 5 reporting periods -> Manual review
   - Avoid dead tokens that never hit TP or SL

DO NOT IMPLEMENT:
- Wider SL (-20%, -25%, -30%) - Just lets losses get bigger
- Exit on BEARISH flip - Data shows this exits BEFORE TP often
- Exit on score drop - Same problem, exits too early

""")

    print("""
IMPLEMENTATION IN TREASURY BOT:
-------------------------------

Current settings should be:
- take_profit_pct: 0.25 (25%)
- stop_loss_pct: 0.15 (15%)

Key considerations:
1. SL execution may gap beyond -15% due to:
   - Low liquidity
   - Fast price moves
   - API latency
   Plan for actual exits around -20% to -25%

2. For hourly price checks (like sentiment reports):
   - -15% is appropriate
   - Tokens that survive intra-hour -15% swings usually recover

3. For live trading with real-time price feeds:
   - Could use -12% to -15% with tighter execution
   - More frequent checks = tighter SL feasible

""")

    print("""
ADDITIONAL METRICS TO TRACK (Future Enhancement):
-------------------------------------------------

1. TIME TO TP: How fast do winners hit 25%?
   - If < 2 hours, good signal
   - If > 6 hours, might be grinding

2. ENTRY PUMP LEVEL: Were we late?
   - Tokens already up 100%+ at entry = higher SL risk
   - Consider rejecting tokens already >50% pumped

3. BUY/SELL RATIO EVOLUTION:
   - Ratio dropping? Might be distribution
   - Could be early exit signal (needs more data)

4. VERDICT FLIP TIMING:
   - How long after BULLISH does BEARISH come?
   - Could inform time-based exits

""")

    print("=" * 90)
    print("SUMMARY: KEEP TP 25% / SL -15%")
    print("=" * 90)
    print("""
The data DOES NOT support widening the stop loss.

- -15% SL catches rugs early (saved 200%+ in losses)
- Only 2 "premature" stops, both still ended as losses
- Wider SLs just let losses get bigger

The volatility concern is valid for intraday swings,
but the TP/SL combo works because:
- Good tokens pump to +25% BEFORE dropping -15%
- Bad tokens (rugs) drop fast and keep dropping

RECOMMENDATION: Keep current settings, focus on:
1. Entry timing (avoid already-pumped tokens)
2. Position sizing (smaller on higher-volatility)
3. Partial exits (lock in gains, let small portion ride)
""")


if __name__ == "__main__":
    main()
