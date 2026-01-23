# PRD: Telegram /demo Bot - Production-Ready AI Trading Assistant

## Executive Summary

Transform the Telegram /demo bot into an AI-powered trading assistant with real-time sentiment analysis, bags.fm API trading, treasury signals, self-learning AI, and advanced order management.

## User Stories

### US-001: Register Message Handler for Token Input

**As a** user
**I want to** enter a token address after selecting a buy amount
**So that** I can proceed with purchasing tokens

**Current Problem**:
```python
# tg_bot/bot.py - Missing handler!
# User taps "Buy 0.1 SOL" → awaiting_token=True → types address → NOTHING HAPPENS
# Because demo_message_handler is never registered
```

**Why Buy Buttons Exist - Detailed Explanation**:

The buy buttons (0.1 SOL, 0.5 SOL, 1 SOL, 5 SOL) serve **four critical purposes**:

1. **Risk Management Presets**
   - 0.1 SOL = Micro position ($20-25 USD) for **high-risk meme coins**
   - 0.5 SOL = Small position ($100-125) for **medium conviction plays**
   - 1 SOL = Standard position ($200-250) for **Grok AI picks with Strong sentiment**
   - 5 SOL = Large position ($1000+) for **treasury-activated signals with Exceptional scores**

2. **Psychological Guardrails**
   - Prevents FOMO over-sizing: "This token is pumping 300%!" → User forced to choose preset → cools emotional decision
   - Anchors to sensible amounts: Without presets, users type "$10,000" in excitement
   - Builds discipline: Consistent position sizing across trades improves risk-adjusted returns

3. **AI Learning Integration**
   - AI tracks which button sizes correlate with profitable vs losing trades
   - Example observation: "0.1 SOL buys on tokens with ratio < 2.0x → 73% stop-loss rate → recommend against"
   - System compresses: "For tokens with weak sentiment (ratio < 2x), larger positions (1 SOL+) have better risk/reward due to scale efficiency"
   - Next time: AI suggests "Consider 1 SOL instead of 0.1 SOL for this medium-conviction play"

4. **Treasury Alignment**
   - Treasury bot uses tiered position sizing: 0.5 SOL (test), 2 SOL (small), 5 SOL (large), 10 SOL (conviction)
   - Demo bot matches this: users learn the system treasury uses
   - When user graduates to real trading, position sizing habits transfer
   - "I made 3x on a 0.5 SOL demo trade → I'll use 0.5 SOL real money first" = smart capital preservation

**User Flow**:
```
1. User taps "Buy 0.5 SOL"
   → System sets context: buy_amount=0.5, awaiting_token=True
   → Shows: "💰 Ready to buy 0.5 SOL (~$125)

            This is a SMALL POSITION size recommended for:
            ✅ Medium-conviction plays
            ✅ Tokens with sentiment score 0.5-0.7
            ✅ Grok verdict: SLIGHTLY BULLISH or better
            ✅ Risk: Losing $125 max if stops hit

            📝 Enter token address or symbol to continue
            ❌ Cancel"

2. User types/pastes: FUhJW8uyKmaSjHZWK41v6cM8fMA5RzAVb3nWkKELpump

3. System validates:
   ✅ Valid Solana address
   ✅ Token exists on bags.fm
   ✅ Fetches current price, liquidity, sentiment
   → Shows confirmation screen (see US-004)

4. User taps "Confirm Buy"
   → execute_buy() via bags.fm API
   → Position added to .positions.json
   → Success notification with tx link
```

**Technical Implementation**:
```python
# tg_bot/bot.py - ADD THIS
from telegram.ext import MessageHandler, filters
from tg_bot.handlers.demo import demo_message_handler

# In register_handlers():
app.add_handler(
    MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        demo_message_handler
    ),
    group=1  # Process after command handlers
)
```

**Acceptance Criteria**:
- [ ] Message handler registered in `tg_bot/bot.py`
- [ ] Token address input captured when `awaiting_token` is true
- [ ] Validates Solana addresses (44 characters, Base58)
- [ ] Shows token preview before confirmation
- [ ] Invalid addresses show clear error: "❌ Invalid address. Must be 44 characters (Solana mint address)"
- [ ] Buy flow proceeds to confirmation screen
- [ ] Explanation of preset amount shown in buy prompt

**Files**:
- `tg_bot/bot.py` (add handler registration)
- `tg_bot/handlers/demo.py` (demo_message_handler already exists)

**Priority**: P0 - Blocker for all buy functionality

---

---

### US-002: Sentiment Hub - Main Dashboard

**As a** user
**I want to** see a comprehensive sentiment dashboard
**So that** I can make informed trading decisions based on AI analysis

**Why This Matters**:

The sentiment hub is the **brain of the demo bot**. It aggregates:
- Grok AI analysis of 10 trending tokens (updated every 15 minutes)
- Macro events (Federal Reserve, geopolitical risks, earnings)
- Traditional markets (DXY, S&P 500, correlation to crypto)
- Precious metals outlook (gold, silver as risk-off hedges)
- Treasury activation signals (what the real treasury bot is buying/selling)
- Bags.fm graduation monitoring (new opportunities graduating from bonding curves)

**Current Data Available** (from `bots/buy_tracker/sentiment_report.py`):

```python
@dataclass
class TokenSentiment:
    symbol: str                    # e.g. "PONKE"
    name: str                      # e.g. "Ponke the Cat"
    price_usd: float              # Current price
    change_1h: float              # % change 1h
    change_24h: float             # % change 24h
    volume_24h: float             # 24h volume in USD
    mcap: float                   # Market cap
    buys_24h: int                 # Number of buy transactions
    sells_24h: int                # Number of sell transactions
    buy_sell_ratio: float         # buys/sells ratio
    liquidity: float              # Liquidity in USD

    # Grok AI Analysis
    sentiment_score: float        # -1 to 1 composite score
    sentiment_label: str          # BULLISH/BEARISH/NEUTRAL
    grok_verdict: str             # STRONG BUY/BUY/HOLD/SELL/STRONG SELL
    grok_reasoning: str           # WHY bullish/bearish
    grok_analysis: str            # Price targets and analysis
    grade: str                    # A+, A, B, C, D, F

    # Price Targets (for TP/SL buttons)
    grok_stop_loss: str           # "$0.015"
    grok_target_safe: str         # Conservative target
    grok_target_medium: str       # Medium target
    grok_target_moon: str         # Moonshot target

    # Risk Flags
    chasing_pump: bool            # True if 40%+ pump already
    momentum_play: bool           # True if ratio >= 3.0x (override pump concerns)
    manipulation_detected: bool   # Cluster detection flagged
    low_liquidity: bool           # < $50k liquidity

    contract_address: str         # Solana mint address

@dataclass
class MacroAnalysis:
    short_term: str               # Next 24 hours outlook
    medium_term: str              # Next 3 days outlook
    long_term: str                # 1 week to 1 month
    key_events: List[str]         # ["FOMC meeting Wed", "CPI data Thu"]

@dataclass
class TraditionalMarkets:
    dxy_sentiment: str            # Dollar outlook
    dxy_direction: str            # BULLISH/BEARISH/NEUTRAL
    stocks_sentiment: str         # US stocks outlook
    stocks_direction: str         # BULLISH/BEARISH/NEUTRAL
    correlation_note: str         # "Weak dollar = crypto pump"

@dataclass
class PreciousMetalsOutlook:
    gold_direction: str           # BULLISH/BEARISH/NEUTRAL
    gold_outlook: str             # "Safe haven demand rising..."
    silver_direction: str
    silver_outlook: str

@dataclass
class MarketRegime:
    btc_trend: str                # BULLISH/BEARISH/NEUTRAL
    sol_trend: str                # BULLISH/BEARISH/NEUTRAL
    btc_change_24h: float         # -3.2%
    sol_change_24h: float         # +5.7%
    risk_level: str               # LOW/NORMAL/HIGH/EXTREME
    regime: str                   # BULL/BEAR/NEUTRAL
```

**Sentiment Hub UI** (matching screenshot):

```
━━━━━━━━━━━━━━━━━━━━━━━━━
📊 SENTIMENT HUB
Updated: 2:45 PM (15 min ago)
━━━━━━━━━━━━━━━━━━━━━━━━━

🤖 Market Regime: BULLISH
├─ BTC: +3.2% | SOL: +5.7%
├─ Risk Level: NORMAL
└─ Next Update: 3:00 PM

━━━━━━━━━━━━━━━━━━━━━━━━━
🔥 GROK TOP PICKS (10)
━━━━━━━━━━━━━━━━━━━━━━━━━

1. PONKE - A+ | STRONG BUY
   $0.47 | +12.3% (24h)
   Ratio: 3.2x | Liq: $2.1M
   🎯 Target: $0.95 (2x)
   💡 "Memecoin momentum strong,
       community active, low FDV"
   [📊 Chart] [💰 Buy]

2. RETARD - B+ | BUY
   $0.0023 | +45% (24h) ⚠️ Pump
   Ratio: 2.8x | Liq: $890K
   🎯 Target: $0.0046 (2x)
   💡 "Strong buy pressure,
       but already pumped—wait
       for pullback or micro buy"
   [📊 Chart] [💰 Buy]

3. WIF - A | BUY
   ...

[View All 10 Picks]

━━━━━━━━━━━━━━━━━━━━━━━━━
📈 MACRO & TRADITIONAL MARKETS
━━━━━━━━━━━━━━━━━━━━━━━━━

📅 Next 24h:
"FOMC minutes release 2PM EST.
Expect volatility. DXY showing
weakness → crypto positive."

📅 Next 3 days:
"CPI data Thursday. If <3%,
risk-on rally continues."

💵 DXY: BEARISH
"Dollar weakening vs EUR/JPY.
Crypto correlation: BULLISH"

📊 S&P 500: NEUTRAL
"Consolidating near ATH. Watch
for breakout or rejection."

🥇 Gold: BULLISH
"Safe haven bid rising. $2100
resistance next."

[Full Macro Report]

━━━━━━━━━━━━━━━━━━━━━━━━━
💼 TREASURY ACTIVATION
━━━━━━━━━━━━━━━━━━━━━━━━━

🟢 ACTIVE POSITIONS (3)
├─ PONKE: +$142 (+23%)
│  Entry: 2h ago | Size: 2 SOL
│  TP: $0.95 | SL: $0.38
│
├─ WIF: +$67 (+11%)
│  Entry: 6h ago | Size: 1.5 SOL
│  TP: $3.20 | SL: $2.40
│
└─ MYRO: -$23 (-8%)
   Entry: 1d ago | Size: 1 SOL
   TP: $0.18 | SL: $0.12 ⚠️ Near SL

Total PnL: +$186 (+14.3%)

🔔 Recent Signals:
├─ 2:30 PM: Bought PONKE @ $0.45
│  Reason: Grok A+ | Ratio 3.2x
│  Size: 2 SOL | SL: $0.38
│
├─ 12:15 PM: Sold RETARD @ $0.0028
│  Reason: Take profit hit (2x)
│  PnL: +$87 (+98%)
│
└─ 10:00 AM: SL Hit on SILLY @ $0.012
   PnL: -$34 (-25%)

[See All Positions]

━━━━━━━━━━━━━━━━━━━━━━━━━
🎒 BAGS.FM GRADUATIONS
━━━━━━━━━━━━━━━━━━━━━━━━━

🚨 NEW (15 min ago):
$DIAMOND graduated!
├─ Score: 78/100 (Strong)
├─ Bonding: 8.2 hr | 450 buyers
├─ Creator: @diamondhands_sol
│  (verified, 12K followers)
├─ Socials: Twitter ✅ Web ✅
└─ Liquidity: $1.2M added

💎 AI Analysis:
"Strong fundamentals. Creator
has good track record. Entry
< $0.05 reasonable."

[📊 Chart] [💰 Quick Buy 0.5 SOL]

[View All Graduations]

━━━━━━━━━━━━━━━━━━━━━━━━━
```

**Buttons**:
```
┌──────────────┬──────────────┐
│ ⚡ Insta Snipe│ 📊 AI Report │
├──────────────┼──────────────┤
│ 🦍 AI Picks  │ 🔥 Trending  │
├──────────────┴──────────────┤
│      🎒 BAGS TOP 15         │
├──────────────┬──────────────┤
│ 🔍 Search Token              │
├──────────────┼──────────────┤
│ 🟢 Buy 0.1 SOL│🟢 Buy 0.5 SOL│
├──────────────┼──────────────┤
│ 🟢 Buy 1 SOL │ 🟢 Buy 5 SOL │
├──────────────┼──────────────┤
│ ⚡ Quick Trade│ 🔬 Analyze   │
├──────────────┼──────────────┤
│ 💼 Positions │ 💰 Balance   │
├──────────────┼──────────────┤
│ 🔴 Sell All  │ 📊 PnL Report│
└──────────────┴──────────────┘
```

**Data Sources**:
- Sentiment tokens: `sentiment_report.generate_and_post_report()` → returns `List[TokenSentiment]`
- Macro: `sentiment_report.macro_analysis` → `MacroAnalysis`
- Traditional markets: `sentiment_report.traditional_markets` → `TraditionalMarkets`
- Precious metals: `sentiment_report.precious_metals_outlook` → `PreciousMetalsOutlook`
- Market regime: `sentiment_report.market_regime` → `MarketRegime`
- Treasury positions: `bots/treasury/.positions.json` → live position data
- Bags graduations: `bots/bags_intel/intel_service.py` → WebSocket stream

**Update Frequency**:
- Sentiment data: Every 15 minutes (aligned with sentiment report generation)
- Treasury positions: Real-time (WebSocket price updates every 5 seconds)
- Bags graduations: Real-time (WebSocket stream from bags.fm)
- Charts: On-demand with 5-minute cache

**Acceptance Criteria**:
- [ ] Sentiment hub shows all 10 Grok picks
- [ ] Each pick displays: symbol, grade, verdict, price, change, ratio, liquidity, targets, reasoning
- [ ] Macro section shows next 24h, 3-day, and long-term outlooks
- [ ] Traditional markets section shows DXY and S&P sentiment
- [ ] Precious metals outlook displayed
- [ ] Treasury activation shows active positions with live PnL
- [ ] Recent treasury signals displayed (last 10)
- [ ] Bags.fm graduations shown with AI analysis
- [ ] All data updates every 15 minutes automatically
- [ ] Loading indicator shown during refresh
- [ ] Timestamp shows when last updated
- [ ] Countdown to next update displayed
- [ ] Quick buy buttons on each token
- [ ] Chart buttons link to price charts
- [ ] Error handling if sentiment data unavailable (show cached data)

**Files**:
- New: `tg_bot/handlers/demo_sentiment.py` (sentiment hub UI)
- `tg_bot/handlers/demo.py` (integrate sentiment data)
- `bots/buy_tracker/sentiment_report.py` (data source)
- `bots/treasury/trading.py` (position data)
- `bots/bags_intel/intel_service.py` (graduation data)

**Priority**: P0 - Core value proposition

---

---

### US-003: AI Learning & Observation System

**As a** system
**I want to** observe user actions and market outcomes, compress learnings, and improve recommendations
**So that** the bot becomes smarter over time

**Why This Matters**:

Traditional bots are static—they follow fixed rules forever. **This bot learns**.

**Examples of What AI Learns**:

1. **Position Sizing Patterns**:
   ```
   Observation: "User bought 0.1 SOL of PONKE @ $0.45, sold @ $0.90 → +$18 profit"
   Observation: "User bought 1 SOL of WIF @ $2.50, sold @ $2.45 → -$20 loss"
   Observation: "User bought 0.5 SOL of RETARD @ $0.002, sold @ $0.004 → +$95 profit"

   Compression (hourly):
   "Smaller positions (0.1-0.5 SOL) on high-volatility memecoins have better risk/reward.
    Larger positions (1+ SOL) should be reserved for tokens with A/A+ grades and momentum_play=True.

    Data: 0.1-0.5 SOL → 67% win rate, avg +82% RoR
          1+ SOL → 40% win rate, avg +12% RoR

    Recommendation: For tokens with grade < A, suggest 0.1-0.5 SOL max."
   ```

2. **Entry Timing Insights**:
   ```
   Observation: "User bought SILLY after +120% pump, hit stop-loss → -25%"
   Observation: "User bought PONKE after +8% pump, hit take-profit → +98%"
   Observation: "User bought WIF after -12% dip, hit take-profit → +45%"

   Compression:
   "Entries after <20% pump have 78% success rate.
    Entries after >80% pump have 15% success rate.

    Red flags in reasoning:
    - 'momentum', 'pump', 'surge' mentions → 14% success
    - 'breakout', 'support', 'consolidation' → 43% success

    Recommendation: Warn users when buying tokens that pumped >50% in 24h.
    Suggest waiting for pullback or using micro position (0.1 SOL)."
   ```

3. **Sentiment Score Calibration**:
   ```
   Observation: "Grok said 'STRONG BUY' (score 0.85) on RETARD → hit SL"
   Observation: "Grok said 'BUY' (score 0.62) on PONKE → hit TP +98%"
   Observation: "Grok said 'BUY' (score 0.71) on WIF → hit TP +45%"

   Compression:
   "Grok scores >=0.70 have 0% TP rate (overconfidence trap).
    Grok scores 0.50-0.70 have 50% TP rate (sweet spot).

    Hypothesis: High scores indicate overbought conditions or hype.
    Medium scores indicate sustainable setups.

    Recommendation: Apply penalty to scores >=0.70, boost scores 0.50-0.65."
   ```

4. **User Behavior Patterns**:
   ```
   Observation: "User always sells at exactly 2x (ignores moon targets)"
   Observation: "User frequently checks positions during US trading hours (9AM-4PM EST)"
   Observation: "User prefers tokens with liquidity >$1M"

   Compression:
   "User profile: Conservative trader, 2x TP preference, avoids low-liquidity plays.

    Personalization:
    - Prioritize tokens with liq >$1M in recommendations
    - Set default TP to 2x (not 5x)
    - Send important alerts during 9AM-4PM EST window
    - Don't show moonshot targets (user ignores them)"
   ```

**Observation Collection Points**:

| Event | Data Captured | Used For |
|-------|---------------|----------|
| **Buy executed** | token, price, amount, sentiment_score, grok_verdict, reasoning, buy_sell_ratio, liquidity, time | Entry timing, position sizing, sentiment correlation |
| **Sell executed** | token, exit_price, entry_price, pnl, duration, reason (TP/SL/manual) | Outcome tracking, TP/SL effectiveness |
| **Stop-loss hit** | token, entry, exit, loss_pct, sentiment_at_entry, time_to_sl | Risk management effectiveness, early warning signals |
| **Take-profit hit** | token, entry, exit, gain_pct, tp_level (safe/medium/moon), time_to_tp | Target accuracy, holding period optimization |
| **Position viewed** | token, times_checked, pnl_at_check, user_emotion (inferred from check frequency) | Stress indicators, anxiety patterns |
| **Chart viewed** | token, timeframe, price_action, user_action_after (buy/sell/nothing) | Chart reading effectiveness |
| **Sentiment updated** | tokens, scores_before, scores_after, price_change_since_update | Sentiment predictive power |
| **Graduation event** | token, bags_score, user_action (bought/ignored), outcome_7d | Graduation quality, user selectivity |

**Compression Pipeline**:

```
1. COLLECT (continuous)
   └─> Store observations in ~/.lifeos/trading/demo_observations.jsonl
       Format: {"timestamp": "2026-01-23T14:30:00Z", "event": "buy_executed", "data": {...}}

2. COMPRESS (hourly - top of each hour)
   └─> Run compression job:
       - Load last hour of observations
       - Group by category (position_sizing, entry_timing, sentiment_correlation, etc.)
       - Calculate statistics (win_rate, avg_pnl, correlation coefficients)
       - Extract patterns using Grok:
         Prompt: "Analyze these trading outcomes. What patterns predict success vs failure?
                  Focus on: position sizing, entry timing, sentiment scores, market regime.
                  Provide actionable insights in <100 words."
       - Store compressed insight in ~/.lifeos/trading/demo_learnings.json
         Format: {"timestamp": "2026-01-23T15:00:00Z", "category": "position_sizing",
                  "insight": "...", "confidence": 0.85, "sample_size": 12}

3. APPLY (real-time)
   └─> When user attempts buy:
       - Load relevant learnings
       - Check if similar pattern exists
       - If pattern predicts failure → warn user:
         "⚠️ AI Insight: Tokens with these characteristics (grade B, >80% pump, ratio <2x)
          have only 15% success rate in past 30 days. Consider:
          • Wait for pullback
          • Use micro position (0.1 SOL)
          • Set tighter stop-loss"
       - If pattern predicts success → encourage:
         "✅ AI Insight: This setup (grade A, <20% pump, ratio 3.2x, liq >$1M) has 78%
          success rate. Treasury is also active in this token. Consider 0.5-1 SOL position."

4. EVOLVE (weekly)
   └─> Run meta-analysis:
       - Which learnings proved accurate? (actual outcomes vs predictions)
       - Which learnings were wrong? (discard or adjust confidence)
       - Detect regime changes: "Insights from last week no longer apply due to market regime shift"
       - Update compression algorithm weights
       - Store evolution log for transparency
```

**Learnings Storage Schema**:

```json
{
  "learnings": [
    {
      "id": "learning_2026_01_23_15_00_01",
      "timestamp": "2026-01-23T15:00:00Z",
      "category": "position_sizing",
      "insight": "Smaller positions (0.1-0.5 SOL) on tokens with grade B/C have better risk-adjusted returns than larger positions. Win rate: 67% vs 40%.",
      "confidence": 0.82,
      "sample_size": 18,
      "supporting_data": {
        "small_positions": {"count": 12, "wins": 8, "avg_pnl_pct": 45},
        "large_positions": {"count": 6, "wins": 2, "avg_pnl_pct": 8}
      },
      "actionable": "When user selects 1+ SOL for grade B/C token, suggest 0.1-0.5 SOL instead",
      "expires_at": "2026-02-23T15:00:00Z"  // Learnings expire after 30 days
    },
    {
      "id": "learning_2026_01_23_16_00_01",
      "timestamp": "2026-01-23T16:00:00Z",
      "category": "entry_timing",
      "insight": "Entries after >100% 24h pump have 12% success rate. Keywords 'momentum', 'pump' in Grok reasoning correlate with failures.",
      "confidence": 0.91,
      "sample_size": 25,
      "supporting_data": {
        "high_pump_entries": {"count": 17, "wins": 2},
        "momentum_keyword_entries": {"count": 14, "wins": 2}
      },
      "actionable": "Warn users when buying token with >80% 24h pump. Suggest wait or micro position.",
      "expires_at": "2026-02-23T16:00:00Z"
    }
  ]
}
```

**User-Facing Insights**:

When opening Sentiment Hub or before buy confirmation, show:

```
🧠 AI INSIGHTS (Last 24h)

✅ What's Working:
├─ Tokens with ratio >2.5x: 72% TP rate
├─ Entries during BTC dips: +38% avg RoR
└─ Positions <0.5 SOL on memes: Best risk/reward

❌ What's Failing:
├─ Buying tokens after >100% pump: 12% TP rate
├─ Large positions (>1 SOL) on grade C: -18% avg RoR
└─ Ignoring low liquidity warnings: 85% SL rate

💡 Recommendation:
"Current regime is BULLISH. Grok picks with
grade A/A+ and ratio >2.5x have 68% success
rate this week. Consider 0.5-1 SOL positions."

[View Full Learning History]
```

**Acceptance Criteria**:
- [ ] Observation events logged to `demo_observations.jsonl`
- [ ] Compression job runs every hour (top of hour)
- [ ] Learnings stored in `demo_learnings.json` with confidence scores
- [ ] AI insights shown in sentiment hub
- [ ] Buy confirmation screen shows relevant warnings/encouragements
- [ ] Learning history viewable by user
- [ ] Weekly meta-analysis adjusts compression weights
- [ ] Expired learnings (>30 days) archived
- [ ] Sample size threshold: require >=10 observations before creating learning
- [ ] Confidence score calculated based on statistical significance
- [ ] User can disable AI insights (settings)

**Files**:
- New: `tg_bot/services/observation_collector.py` (log observations)
- New: `tg_bot/services/learning_compressor.py` (hourly compression)
- New: `tg_bot/services/insight_engine.py` (apply learnings to recommendations)
- New: `~/.lifeos/trading/demo_observations.jsonl` (raw observations)
- New: `~/.lifeos/trading/demo_learnings.json` (compressed insights)
- `tg_bot/handlers/demo.py` (integrate insights into UI)

**Priority**: P0 - Core differentiator

---

---

### US-004: Treasury Activation Integration

**As a** user
**I want to** see what the treasury bot is trading
**So that** I can follow its signals and learn from its execution

**Why This Matters**:

The treasury bot (`bots/treasury/trading.py`) is the "pro trader" in the system. It:
- Uses the same sentiment data
- Has real money on the line
- Executes disciplined TP/SL exits
- Tracks actual PnL

By showing treasury activity in the demo bot, users:
1. **Learn from the pro**: "Oh, treasury only buys tokens with ratio >2.5x"
2. **Gain confidence**: "Treasury is up +$450 this week → sentiment system works"
3. **Get early signals**: "Treasury just bought PONKE → I should check it out"
4. **Understand position sizing**: "Treasury uses 0.5 SOL for tests, 2 SOL for conviction"

**Treasury Position Data Structure**:

```python
# From bots/treasury/.positions.json
{
  "positions": [
    {
      "token": "PONKE",
      "mint": "FUhJW8uyKmaSjHZWK41v6cM8fMA5RzAVb3nWkKELpump",
      "entry_price": 0.45,
      "current_price": 0.587,  // Updated real-time
      "amount_sol": 2.0,
      "amount_tokens": 4444.44,
      "entry_time": "2026-01-23T14:30:00Z",
      "stop_loss": 0.38,
      "take_profit": 0.95,
      "pnl_usd": 142.50,
      "pnl_pct": 23.4,
      "status": "open",
      "sentiment_at_entry": {
        "score": 0.68,
        "verdict": "BUY",
        "grade": "A+",
        "ratio": 3.2
      },
      "exit_reason": null,
      "exit_time": null,
      "exit_price": null
    },
    {
      "token": "RETARD",
      "mint": "6ogzHhzdrQr9Pgv6hZ2MNze7UrzBMAFyBBWUYp1Fhitx",
      "entry_price": 0.0014,
      "current_price": null,  // Position closed
      "amount_sol": 1.5,
      "entry_time": "2026-01-23T10:15:00Z",
      "stop_loss": 0.0011,
      "take_profit": 0.0028,
      "pnl_usd": 87.30,
      "pnl_pct": 98.2,
      "status": "closed",
      "exit_reason": "take_profit_hit",
      "exit_time": "2026-01-23T12:15:00Z",
      "exit_price": 0.0028
    }
  ],
  "total_pnl_usd": 186.45,
  "total_pnl_pct": 14.3,
  "win_rate": 0.67,
  "total_trades": 15,
  "winning_trades": 10,
  "losing_trades": 5
}
```

**Treasury Activation UI**:

```
━━━━━━━━━━━━━━━━━━━━━━━━━
💼 TREASURY ACTIVATION
Updated: Real-time
━━━━━━━━━━━━━━━━━━━━━━━━━

📊 Performance (24h)
PnL: +$186.45 (+14.3%)
Win Rate: 67% (10W/5L)
Avg Hold Time: 4.2 hours

━━━━━━━━━━━━━━━━━━━━━━━━━

🟢 ACTIVE POSITIONS (3)

┌─ PONKE ─────────────────┐
│ Entry: $0.45 (2h ago)   │
│ Current: $0.587 (+23%)  │
│ PnL: +$142.50           │
│ Size: 2 SOL | Stop: $0.38│
│ Target: $0.95 (2.1x)    │
│                         │
│ 💡 Why bought:          │
│ "Grade A+, ratio 3.2x,  │
│  Grok verdict: BUY,     │
│  liquidity $2.1M"       │
│                         │
│ [📊 Chart] [🔔 Follow]  │
└─────────────────────────┘

┌─ WIF ───────────────────┐
│ Entry: $2.50 (6h ago)   │
│ Current: $2.78 (+11%)   │
│ PnL: +$67.20            │
│ Size: 1.5 SOL | Stop: $2.40│
│ Target: $3.20 (1.3x)    │
│ [📊 Chart] [🔔 Follow]  │
└─────────────────────────┘

┌─ MYRO ──────────────────┐
│ Entry: $0.14 (1d ago)   │
│ Current: $0.129 (-8%)   │
│ PnL: -$23.10            │
│ Size: 1 SOL | Stop: $0.12│
│ ⚠️ NEAR STOP LOSS       │
│ [📊 Chart] [🔔 Follow]  │
└─────────────────────────┘

━━━━━━━━━━━━━━━━━━━━━━━━━

🔔 RECENT SIGNALS (10)

2:30 PM │ 🟢 BOUGHT PONKE @ $0.45
        │ Reason: Grok A+ | Ratio 3.2x
        │ Size: 2 SOL | SL: $0.38 | TP: $0.95
        │ [Copy This Trade]

12:15 PM│ 🟢 SOLD RETARD @ $0.0028 ✅
        │ Reason: Take profit hit (2x target)
        │ Entry: $0.0014 | PnL: +$87 (+98%)
        │ Hold time: 2h 0m

10:00 AM│ 🔴 SOLD SILLY @ $0.012 ❌
        │ Reason: Stop loss hit
        │ Entry: $0.015 | PnL: -$34 (-25%)
        │ Hold time: 18h 45m

9:15 AM │ 🟢 BOUGHT WIF @ $2.50
        │ Reason: Grok A | Ratio 2.8x
        │ Size: 1.5 SOL | SL: $2.40 | TP: $3.20
        │ [Copy This Trade]

[View All Treasury History]

━━━━━━━━━━━━━━━━━━━━━━━━━

💡 Copy Trading:
When you tap "Copy This Trade", we'll:
1. Use the same position size (or scaled to your preference)
2. Set the same stop-loss and take-profit
3. Show you the same analysis treasury saw
4. Track if you're profitable copying treasury

Your Copy Stats (7 days):
├─ Copied 5 trades
├─ PnL: +$78 (+15.6%)
├─ Win Rate: 60% (3W/2L)
└─ vs Treasury: -1.4% underperformance
    (your entries slightly late)

[Settings: Auto-Copy Treasury Buys]

━━━━━━━━━━━━━━━━━━━━━━━━━
```

**Real-Time Price Updates**:

Treasury positions get price updates via WebSocket (every 5 seconds):

```python
# tg_bot/services/treasury_monitor.py
import asyncio
import websockets

async def monitor_treasury_positions():
    """Monitor treasury positions and update prices in real-time."""
    positions = load_positions("bots/treasury/.positions.json")
    active_mints = [p["mint"] for p in positions if p["status"] == "open"]

    # Connect to bags.fm WebSocket
    async with websockets.connect("wss://api.bags.fm/v1/stream") as ws:
        # Subscribe to price updates
        await ws.send(json.dumps({
            "action": "subscribe",
            "channel": "prices",
            "tokens": active_mints
        }))

        async for message in ws:
            data = json.loads(message)
            if data["type"] == "price_update":
                mint = data["mint"]
                new_price = data["price"]

                # Update position
                update_position_price(mint, new_price)

                # Calculate new PnL
                position = get_position_by_mint(mint)
                pnl_usd = (new_price - position["entry_price"]) * position["amount_tokens"] * SOL_PRICE
                pnl_pct = ((new_price / position["entry_price"]) - 1) * 100

                # Check if SL/TP hit
                if new_price <= position["stop_loss"]:
                    notify_telegram(f"⚠️ Treasury position {position['token']} hit STOP LOSS @ ${new_price}")
                elif new_price >= position["take_profit"]:
                    notify_telegram(f"✅ Treasury position {position['token']} hit TAKE PROFIT @ ${new_price}")

                # Update UI (if user viewing treasury panel)
                await broadcast_to_users({
                    "type": "treasury_update",
                    "position": position,
                    "pnl_usd": pnl_usd,
                    "pnl_pct": pnl_pct
                })
```

**Copy Trading Feature**:

Users can "copy" treasury trades:

1. **Manual Copy**: Tap "Copy This Trade" on a recent signal
   - Pre-fills buy screen with same token, stop-loss, take-profit
   - User can adjust size (default: same as treasury)
   - Shows: "You're copying Treasury's PONKE buy. Entry: $0.45, SL: $0.38, TP: $0.95"

2. **Auto-Copy** (optional setting):
   - Enable: "Auto-copy all treasury buys"
   - When treasury buys, demo bot auto-buys same token
   - User sets max position size and total daily allocation
   - Notification: "🤖 Auto-copied treasury: Bought 0.5 SOL of PONKE @ $0.45"

3. **Copy Performance Tracking**:
   - Track user's "copy trades" separately
   - Compare to treasury performance
   - Show slippage: "Your entry: $0.47 (treasury: $0.45) = +4.4% slippage"
   - Leaderboard: "You're copying better than 73% of demo users"

**Acceptance Criteria**:
- [ ] Treasury positions displayed with real-time PnL
- [ ] Active positions show entry, current price, stop-loss, take-profit
- [ ] Recent signals (last 10 buys/sells) displayed
- [ ] Closed positions show exit reason and PnL
- [ ] Treasury performance stats (total PnL, win rate, avg hold time)
- [ ] "Copy This Trade" button pre-fills buy screen
- [ ] Auto-copy setting available
- [ ] Copy performance tracked separately
- [ ] Real-time price updates via WebSocket
- [ ] Notifications when treasury SL/TP hit
- [ ] "Follow" button subscribes to token price alerts
- [ ] Treasury panel updates every 5 seconds (prices)
- [ ] Treasury panel refreshes every 15 minutes (new positions from sentiment report)

**Files**:
- New: `tg_bot/services/treasury_monitor.py` (monitor treasury positions)
- New: `tg_bot/handlers/demo_treasury.py` (treasury UI)
- `bots/treasury/.positions.json` (data source)
- `tg_bot/handlers/demo.py` (integrate treasury panel)

**Priority**: P0 - Core social proof feature

---

---

### US-005: bags.fm Buy/Sell Integration

**As a** user
**I want to** execute buys and sells via bags.fm API
**So that** trades actually work

**bags.fm API Documentation**: https://docs.bags.fm/

**API Endpoints**:

```python
# POST /v1/swap - Execute token swap
{
  "from_token": "SOL",           # or token mint address
  "to_token": "<mint_address>",  # token to buy
  "amount": 100000000,           # lamports (0.1 SOL = 100M lamports)
  "slippage": 0.01,              # 1% slippage tolerance
  "wallet_address": "<user_wallet>",
  "referral": "JARVIS_DEMO"      # optional referral code
}

# Response:
{
  "success": true,
  "transaction_hash": "5Kq...",
  "from_amount": 100000000,
  "to_amount": 245680000,        # tokens received
  "execution_price": 0.000407,   # actual price paid
  "slippage_used": 0.008,        # 0.8% slippage
  "fees": {
    "network": 5000,             # 0.000005 SOL
    "platform": 500000,          # 0.0005 SOL
    "total": 505000
  }
}

# GET /v1/token/{mint}/info - Token info
{
  "mint": "...",
  "symbol": "PONKE",
  "name": "Ponke the Cat",
  "price_usd": 0.47,
  "price_sol": 0.00235,
  "market_cap": 470000000,
  "liquidity_usd": 2100000,
  "volume_24h": 18500000,
  "holders": 12450,
  "graduated": true,           # graduated from bonding curve
  "graduation_time": "2026-01-20T10:30:00Z"
}

# GET /v1/token/{mint}/chart?interval=1h&limit=100
{
  "candles": [
    {
      "timestamp": 1706022000,
      "open": 0.45,
      "high": 0.48,
      "low": 0.44,
      "close": 0.47,
      "volume": 125000
    },
    ...
  ]
}

# GET /v1/token/{mint}/holders
{
  "total_holders": 12450,
  "top_holders": [
    {
      "address": "7xKXt...",
      "balance": 125000000,
      "percentage": 12.5,
      "is_known": true,
      "label": "Raydium LP"
    },
    ...
  ]
}

# WebSocket: wss://api.bags.fm/v1/stream
# Subscribe:
{
  "action": "subscribe",
  "channel": "prices",
  "tokens": ["mint1", "mint2", ...]
}

# Price update:
{
  "type": "price_update",
  "mint": "...",
  "price_usd": 0.47,
  "price_sol": 0.00235,
  "change_1m": 0.8,
  "change_5m": 2.1,
  "volume_5m": 25000
}

# Graduation event:
{
  "type": "graduation",
  "mint": "...",
  "symbol": "DIAMOND",
  "bonding_duration_hours": 8.2,
  "total_buyers": 450,
  "liquidity_added": 1200000,
  "creator": "...",
  "timestamp": "2026-01-23T14:45:00Z"
}
```

**Buy Flow Implementation**:

```python
# core/bags_api.py

import aiohttp
from typing import Dict, Optional

class BagsAPI:
    BASE_URL = "https://api.bags.fm/v1"
    WS_URL = "wss://api.bags.fm/v1/stream"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("BAGS_FM_API_KEY")
        self.session = None

    async def __aenter__(self):
        self.session = aiohttp.ClientSession(
            headers={"Authorization": f"Bearer {self.api_key}"}
        )
        return self

    async def __aexit__(self, *args):
        await self.session.close()

    async def swap(
        self,
        from_token: str,
        to_token: str,
        amount_lamports: int,
        wallet_address: str,
        slippage: float = 0.01
    ) -> Dict:
        """Execute a token swap."""
        payload = {
            "from_token": from_token,
            "to_token": to_token,
            "amount": amount_lamports,
            "wallet_address": wallet_address,
            "slippage": slippage,
            "referral": "JARVIS_DEMO"
        }

        async with self.session.post(f"{self.BASE_URL}/swap", json=payload) as resp:
            if resp.status != 200:
                error = await resp.json()
                raise BagsAPIError(f"Swap failed: {error.get('message', 'Unknown error')}")
            return await resp.json()

    async def get_token_info(self, mint: str) -> Dict:
        """Get token information."""
        async with self.session.get(f"{self.BASE_URL}/token/{mint}/info") as resp:
            if resp.status == 404:
                raise TokenNotFoundError(f"Token {mint} not found on bags.fm")
            return await resp.json()

    async def get_chart_data(
        self,
        mint: str,
        interval: str = "1h",
        limit: int = 100
    ) -> Dict:
        """Get price chart data."""
        params = {"interval": interval, "limit": limit}
        async with self.session.get(
            f"{self.BASE_URL}/token/{mint}/chart",
            params=params
        ) as resp:
            return await resp.json()

    async def get_holders(self, mint: str) -> Dict:
        """Get holder distribution."""
        async with self.session.get(f"{self.BASE_URL}/token/{mint}/holders") as resp:
            return await resp.json()

# Usage in demo.py:
async def execute_buy(
    token_address: str,
    amount_sol: float,
    wallet_address: str,
    slippage: float = 0.01
):
    """Execute a buy via bags.fm API."""
    amount_lamports = int(amount_sol * 1_000_000_000)  # SOL to lamports

    async with BagsAPI() as api:
        # Get token info first (price, liquidity check)
        try:
            token_info = await api.get_token_info(token_address)
        except TokenNotFoundError:
            raise ValueError("Token not found on bags.fm. Make sure it's graduated.")

        # Liquidity check
        if token_info["liquidity_usd"] < 10000:
            raise ValueError(f"Low liquidity: ${token_info['liquidity_usd']:,.0f}. "
                           "Minimum recommended: $10,000")

        # Price impact estimate
        price_impact = estimate_price_impact(amount_sol, token_info["liquidity_usd"])
        if price_impact > 0.05:  # >5% impact
            logger.warning(f"High price impact: {price_impact*100:.1f}%")

        # Execute swap
        result = await api.swap(
            from_token="SOL",
            to_token=token_address,
            amount_lamports=amount_lamports,
            wallet_address=wallet_address,
            slippage=slippage
        )

        # Store position
        position = {
            "token": token_info["symbol"],
            "mint": token_address,
            "entry_price": result["execution_price"],
            "amount_sol": amount_sol,
            "amount_tokens": result["to_amount"],
            "entry_time": datetime.now(timezone.utc).isoformat(),
            "transaction_hash": result["transaction_hash"],
            "slippage_used": result["slippage_used"],
            "fees_paid": result["fees"]["total"] / 1_000_000_000,  # lamports to SOL
            "status": "open"
        }

        save_position(position)

        return position
```

**Buy Confirmation UI**:

```
┌───────────────────────────┐
│   CONFIRM BUY             │
├───────────────────────────┤
│                           │
│ Token: PONKE              │
│ Name: Ponke the Cat       │
│ Contract: FUhJW...Lpump   │
│                           │
│ Price: $0.47              │
│ Market Cap: $470M         │
│ Liquidity: $2.1M ✅       │
│ Holders: 12,450           │
│                           │
│ ━━━━━━━━━━━━━━━━━━━━━━━  │
│                           │
│ You're buying: 0.5 SOL    │
│ Worth: ~$125 USD          │
│                           │
│ You'll get: ~265,957 PONKE│
│ Execution price: ~$0.470  │
│ Slippage: 1% (changeable) │
│ Est. fees: ~$0.25         │
│                           │
│ ━━━━━━━━━━━━━━━━━━━━━━━  │
│                           │
│ 🎯 SUGGESTED TARGETS      │
│ (from Grok AI)            │
│                           │
│ Stop Loss: $0.38 (-19%)   │
│ Take Profit: $0.95 (2x)   │
│                           │
│ [Set Custom TP/SL]        │
│                           │
│ ━━━━━━━━━━━━━━━━━━━━━━━  │
│                           │
│ 💡 AI Insight:            │
│ "This token has grade A+, │
│  ratio 3.2x, and treasury │
│  is also active. 0.5 SOL  │
│  is a good position size  │
│  for this risk level."    │
│                           │
│ ━━━━━━━━━━━━━━━━━━━━━━━  │
│                           │
│ ⚠️ Risks:                 │
│ • Memecoins are volatile  │
│ • Can lose entire position│
│ • Use only risk capital   │
│                           │
├───────────────────────────┤
│ [✅ Confirm Buy]  [❌ Cancel]│
└───────────────────────────┘
```

**Jupiter Backup Integration**:

All buys MUST include take-profit and stop-loss settings. Primary execution via bags.fm API, with Jupiter as fallback.

```python
# core/jupiter_api.py

from solders.transaction import VersionedTransaction
import base64

class JupiterAPI:
    """Jupiter aggregator backup for bags.fm failures."""
    BASE_URL = "https://quote-api.jup.ag/v6"

    async def get_quote(
        self,
        input_mint: str,      # SOL mint
        output_mint: str,     # Token mint
        amount: int,          # Lamports
        slippage_bps: int = 100  # 1% = 100 bps
    ) -> Dict:
        """Get swap quote from Jupiter."""
        params = {
            "inputMint": input_mint,
            "outputMint": output_mint,
            "amount": amount,
            "slippageBps": slippage_bps
        }
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{self.BASE_URL}/quote", params=params) as resp:
                return await resp.json()

    async def execute_swap(
        self,
        quote: Dict,
        user_public_key: str
    ) -> str:
        """Execute swap and return transaction hash."""
        payload = {
            "quoteResponse": quote,
            "userPublicKey": user_public_key,
            "wrapAndUnwrapSol": True
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(f"{self.BASE_URL}/swap", json=payload) as resp:
                swap_response = await resp.json()

                # Sign and send transaction (simplified)
                swap_transaction = swap_response["swapTransaction"]
                transaction = VersionedTransaction.from_bytes(
                    base64.b64decode(swap_transaction)
                )

                # Send to RPC (requires wallet signing in production)
                signature = await self._send_transaction(transaction)
                return signature

# Dual API execution with TP/SL defaults:

async def execute_buy_with_tpsl(
    token_address: str,
    amount_sol: float,
    wallet_address: str,
    tp_percent: float = 50.0,  # Default: 50% take profit
    sl_percent: float = 20.0   # Default: 20% stop loss
):
    """Execute buy via bags.fm (primary) or Jupiter (backup) with TP/SL."""

    # Try bags.fm first
    try:
        async with BagsAPI() as api:
            result = await api.swap(
                from_token="SOL",
                to_token=token_address,
                amount_lamports=int(amount_sol * 1_000_000_000),
                wallet_address=wallet_address
            )
            source = "bags.fm"
    except (BagsAPIError, aiohttp.ClientError, asyncio.TimeoutError) as e:
        logger.warning(f"bags.fm failed ({e}), falling back to Jupiter...")

        # Fallback to Jupiter
        jupiter = JupiterAPI()
        sol_mint = "So11111111111111111111111111111111111111112"

        quote = await jupiter.get_quote(
            input_mint=sol_mint,
            output_mint=token_address,
            amount=int(amount_sol * 1_000_000_000),
            slippage_bps=100  # 1%
        )

        tx_hash = await jupiter.execute_swap(quote, wallet_address)

        result = {
            "transaction_hash": tx_hash,
            "execution_price": float(quote["outAmount"]) / float(quote["inAmount"]),
            "to_amount": int(quote["outAmount"]),
            "slippage_used": 0.01,
            "fees": {"total": 5000}  # Estimate
        }
        source = "Jupiter"

    # Get current price for TP/SL calculation
    entry_price = result["execution_price"]

    # Calculate TP/SL prices
    tp_price = entry_price * (1 + tp_percent / 100)
    sl_price = entry_price * (1 - sl_percent / 100)

    # Store position with TP/SL metadata
    position = {
        "token_address": token_address,
        "entry_price": entry_price,
        "amount_sol": amount_sol,
        "amount_tokens": result["to_amount"],
        "entry_time": datetime.now(timezone.utc).isoformat(),
        "transaction_hash": result["transaction_hash"],
        "source": source,  # "bags.fm" or "Jupiter"
        "status": "open",

        # TP/SL settings (existing implementation already supports this!)
        "tp_percent": tp_percent,
        "sl_percent": sl_percent,
        "tp_price": tp_price,
        "sl_price": sl_price,
        "tp_triggered": False,
        "sl_triggered": False
    }

    save_position(position)

    # Start monitoring this position for TP/SL triggers
    await order_monitor.add_position(position)

    return position
```

**TP/SL Integration with Existing UI**:

The demo bot already has TP/SL functionality implemented in `tg_bot/ui/inline_buttons.py:851-886` (PositionButtons.adjust_tp_sl()), but it's not wired to callbacks. This user story ensures:

1. **All buys include TP/SL by default** (50% TP, 20% SL)
2. **Users can adjust via existing UI** (once callbacks are wired in US-033)
3. **Confirmation screen shows TP/SL targets** (already in UI mockup above)
4. **Order monitor triggers exits automatically** (10-second price check loop)

**Acceptance Criteria**:
- [ ] Buy executes via bags.fm `/v1/swap` API
- [ ] **Jupiter fallback** if bags.fm fails (timeout, error, rate limit)
- [ ] **All buys include TP/SL by default** (50% TP, 20% SL)
- [ ] **TP/SL prices calculated and stored** in position metadata
- [ ] Token validation before buy (exists, has liquidity)
- [ ] Liquidity check (warn if <$10k)
- [ ] Price impact estimate shown
- [ ] Slippage configurable (default 1%)
- [ ] Confirmation screen shows all details including TP/SL targets
- [ ] Suggested TP/SL from Grok AI
- [ ] Position saved to `.positions.json` on success with TP/SL data
- [ ] Transaction hash returned and stored
- [ ] Success notification with Solscan link
- [ ] Error handling for failed swaps
- [ ] Retry logic (3 attempts with exponential backoff)
- [ ] Sell flow mirrors buy flow (reverse swap)

**Files**:
- New: `core/bags_api.py` (bags.fm API client)
- New: `core/jupiter_api.py` (Jupiter fallback API client)
- Modified: `tg_bot/handlers/demo.py` (execute_buy_with_tpsl, execute_sell functions)
- `~/.lifeos/trading/demo_positions.json` (position storage with TP/SL metadata)

**Priority**: P0 - Blocker for all trading

---

---

### US-006: Advanced Order Types (Stop-Loss, Take-Profit, Limit)

**As a** user
**I want to** set stop-loss and take-profit orders on my positions
**So that** I can manage risk and lock in gains automatically

**Why Advanced Orders Matter**:

Manual trading is emotional:
- User sees -20% loss → panics → sells at bottom
- User sees +50% gain → gets greedy → holds → gives back all gains

Advanced orders enforce discipline:
- Stop-loss: "I will not lose more than X%"
- Take-profit: "I will take profits at X% gain"
- Limit: "I will only buy if price reaches X"

**Order Types**:

1. **Stop-Loss**: Sell when price drops to trigger
2. **Take-Profit**: Sell when price rises to trigger
3. **Trailing Stop**: Stop-loss that follows price up
4. **Limit Buy**: Buy when price drops to target
5. **Ladder Exit**: Multiple take-profit levels (e.g., 50% at 2x, 50% at 5x)

**Stop-Loss UI**:

```
┌───────────────────────────┐
│  SET STOP-LOSS: PONKE     │
├───────────────────────────┤
│                           │
│ Current Price: $0.587     │
│ Entry Price: $0.45        │
│ Current PnL: +$142 (+23%) │
│                           │
│ ━━━━━━━━━━━━━━━━━━━━━━━  │
│                           │
│ 🎯 Stop-Loss Options:     │
│                           │
│ [  5%] → $0.428 (-$44)    │
│ [ 10%] → $0.405 (-$90)    │
│ [ 15%] → $0.383 (-$134) ✅│
│ [ 25%] → $0.338 (-$224)   │
│ [Custom]                  │
│                           │
│ ━━━━━━━━━━━━━━━━━━━━━━━  │
│                           │
│ 💡 Grok Suggestion:       │
│ Stop-Loss: $0.38 (-15%)   │
│ "Based on support levels  │
│  and volatility"          │
│                           │
│ ━━━━━━━━━━━━━━━━━━━━━━━  │
│                           │
│ Selected: $0.383 (-15%)   │
│ Max Loss: $134.00         │
│                           │
│ ⚠️ If price drops to this │
│ level, position will auto-│
│ sell to prevent larger loss│
│                           │
├───────────────────────────┤
│ [✅ Set Stop] [❌ Cancel]  │
└───────────────────────────┘
```

**Take-Profit UI**:

```
┌───────────────────────────┐
│ SET TAKE-PROFIT: PONKE    │
├───────────────────────────┤
│                           │
│ Current Price: $0.587     │
│ Entry Price: $0.45        │
│                           │
│ ━━━━━━━━━━━━━━━━━━━━━━━  │
│                           │
│ 🎯 Single Take-Profit:    │
│                           │
│ [1.5x] → $0.675 (+$450)   │
│ [  2x] → $0.90 (+$900) ✅  │
│ [  5x] → $2.25 (+$3,600)  │
│ [ 10x] → $4.50 (+$8,100)  │
│ [Custom]                  │
│                           │
│ ━━━━━━━━━━━━━━━━━━━━━━━  │
│                           │
│ 💡 Grok Targets:          │
│ Safe: $0.95 (2.1x)        │
│ Medium: $1.80 (4x)        │
│ Moon: $4.50 (10x)         │
│                           │
│ ━━━━━━━━━━━━━━━━━━━━━━━  │
│                           │
│ 🔁 OR: Ladder Exit        │
│ (take profits gradually)  │
│                           │
│ 50% @ 2x → $0.90          │
│ 30% @ 5x → $2.25          │
│ 20% @ 10x → $4.50         │
│                           │
│ [Use Ladder Instead]      │
│                           │
├───────────────────────────┤
│ [✅ Set TP] [❌ Cancel]    │
└───────────────────────────┘
```

**Order Monitoring Service**:

```python
# tg_bot/services/order_monitor.py

import asyncio
import json
from pathlib import Path

ORDERS_FILE = Path.home() / ".lifeos/trading/demo_orders.json"

class OrderMonitor:
    """Monitor stop-loss, take-profit, and limit orders."""

    def __init__(self):
        self.orders = self.load_orders()
        self.running = False

    def load_orders(self):
        """Load active orders from disk."""
        if not ORDERS_FILE.exists():
            return []
        with open(ORDERS_FILE) as f:
            return json.load(f)["orders"]

    def save_orders(self):
        """Save orders to disk."""
        ORDERS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(ORDERS_FILE, "w") as f:
            json.dump({"orders": self.orders}, f, indent=2)

    def add_order(self, order: dict):
        """Add a new order."""
        order["id"] = f"order_{int(time.time())}_{random.randint(1000, 9999)}"
        order["status"] = "active"
        order["created_at"] = datetime.now(timezone.utc).isoformat()
        self.orders.append(order)
        self.save_orders()
        logger.info(f"Added order: {order['type']} for {order['token']} @ ${order['trigger_price']}")

    async def start(self):
        """Start monitoring orders."""
        self.running = True
        logger.info("Order monitor started")

        while self.running:
            await self.check_orders()
            await asyncio.sleep(10)  # Check every 10 seconds

    async def check_orders(self):
        """Check all active orders against current prices."""
        active_orders = [o for o in self.orders if o["status"] == "active"]

        for order in active_orders:
            try:
                # Get current price
                async with BagsAPI() as api:
                    token_info = await api.get_token_info(order["mint"])
                    current_price = token_info["price_usd"]

                # Check if triggered
                triggered = False

                if order["type"] == "stop_loss":
                    if current_price <= order["trigger_price"]:
                        triggered = True
                        reason = f"Stop-loss hit @ ${current_price}"

                elif order["type"] == "take_profit":
                    if current_price >= order["trigger_price"]:
                        triggered = True
                        reason = f"Take-profit hit @ ${current_price}"

                elif order["type"] == "limit_buy":
                    if current_price <= order["trigger_price"]:
                        triggered = True
                        reason = f"Limit buy triggered @ ${current_price}"

                if triggered:
                    await self.execute_order(order, current_price, reason)

            except Exception as e:
                logger.error(f"Error checking order {order['id']}: {e}")

    async def execute_order(self, order: dict, execution_price: float, reason: str):
        """Execute a triggered order."""
        logger.info(f"Executing order: {order['type']} for {order['token']} @ ${execution_price}")

        try:
            if order["type"] in ["stop_loss", "take_profit"]:
                # Sell the position
                position = get_position_by_mint(order["mint"])

                result = await execute_sell(
                    token_address=order["mint"],
                    amount_tokens=position["amount_tokens"],
                    wallet_address=position["wallet_address"]
                )

                # Calculate PnL
                entry_price = position["entry_price"]
                pnl_pct = ((execution_price / entry_price) - 1) * 100
                pnl_usd = (execution_price - entry_price) * position["amount_tokens"]

                # Update position
                position["status"] = "closed"
                position["exit_price"] = execution_price
                position["exit_time"] = datetime.now(timezone.utc).isoformat()
                position["exit_reason"] = reason
                position["pnl_usd"] = pnl_usd
                position["pnl_pct"] = pnl_pct
                save_position(position)

                # Notify user
                emoji = "✅" if pnl_usd > 0 else "❌"
                await send_telegram_notification(
                    f"{emoji} {order['type'].replace('_', ' ').title()}\n\n"
                    f"Token: {order['token']}\n"
                    f"Sold @ ${execution_price}\n"
                    f"Entry: ${entry_price}\n"
                    f"PnL: ${pnl_usd:+,.2f} ({pnl_pct:+.1f}%)\n\n"
                    f"Reason: {reason}\n"
                    f"Tx: {result['transaction_hash']}"
                )

            elif order["type"] == "limit_buy":
                # Execute buy
                position = await execute_buy(
                    token_address=order["mint"],
                    amount_sol=order["amount_sol"],
                    wallet_address=order["wallet_address"]
                )

                # Notify user
                await send_telegram_notification(
                    f"✅ Limit Buy Filled\n\n"
                    f"Token: {order['token']}\n"
                    f"Bought @ ${execution_price}\n"
                    f"Amount: {order['amount_sol']} SOL\n"
                    f"Tx: {position['transaction_hash']}"
                )

            # Mark order as filled
            order["status"] = "filled"
            order["filled_at"] = datetime.now(timezone.utc).isoformat()
            order["execution_price"] = execution_price
            self.save_orders()

            logger.info(f"Order {order['id']} executed successfully")

        except Exception as e:
            logger.error(f"Failed to execute order {order['id']}: {e}")
            order["status"] = "failed"
            order["error"] = str(e)
            self.save_orders()

            await send_telegram_notification(
                f"❌ Order Execution Failed\n\n"
                f"Type: {order['type']}\n"
                f"Token: {order['token']}\n"
                f"Error: {str(e)}\n\n"
                f"Please try manual execution."
            )

# Start monitor in background
async def start_order_monitor():
    monitor = OrderMonitor()
    await monitor.start()

# Add to supervisor.py or bot startup:
asyncio.create_task(start_order_monitor())
```

**Order Dashboard UI**:

```
━━━━━━━━━━━━━━━━━━━━━━━━━
⚙️ ACTIVE ORDERS (5)
━━━━━━━━━━━━━━━━━━━━━━━━━

🛑 Stop-Loss Orders (2)

PONKE
├─ Trigger: $0.383 (-15% from entry)
├─ Current: $0.587 (+28% away)
├─ Created: 2h ago
└─ [❌ Cancel]

WIF
├─ Trigger: $2.40 (-4% from entry)
├─ Current: $2.78 (+16% away)
├─ Created: 6h ago
└─ [❌ Cancel]

━━━━━━━━━━━━━━━━━━━━━━━━━

🎯 Take-Profit Orders (2)

PONKE
├─ Trigger: $0.90 (2x from entry)
├─ Current: $0.587 (+53% away)
├─ Created: 2h ago
└─ [❌ Cancel]

WIF (Ladder)
├─ 50% @ $3.20 (1.3x) [+15% away]
├─ 30% @ $5.00 (2x) [+80% away]
├─ 20% @ $10.00 (4x) [+260% away]
├─ Created: 6h ago
└─ [❌ Cancel All]

━━━━━━━━━━━━━━━━━━━━━━━━━

💰 Limit Buy Orders (1)

RETARD
├─ Buy @ $0.0018 (waiting for pullback)
├─ Current: $0.0023 (-22% away)
├─ Size: 0.5 SOL
├─ Expires: 23h 15m
└─ [❌ Cancel]

━━━━━━━━━━━━━━━━━━━━━━━━━

📊 Order History (Last 10)

✅ FILLED: TP on RETARD @ $0.0028
   +$87 (+98%) | 3h ago

❌ FILLED: SL on SILLY @ $0.012
   -$34 (-25%) | 5h ago

✅ FILLED: TP on PONKE @ $0.95
   +$450 (+111%) | 1d ago

[View All History]

━━━━━━━━━━━━━━━━━━━━━━━━━
```

**Acceptance Criteria**:
- [ ] Stop-loss can be set on any open position
- [ ] Take-profit can be set on any open position
- [ ] Limit buy can be placed for any token
- [ ] Multiple TP levels supported (ladder exits)
- [ ] Orders stored in `demo_orders.json`
- [ ] Background monitor checks orders every 10 seconds
- [ ] Orders execute automatically when triggered
- [ ] User notified on execution (Telegram message)
- [ ] PnL calculated and stored on exit
- [ ] Order history viewable
- [ ] Orders cancellable before execution
- [ ] Expired limit orders auto-cancelled
- [ ] Trailing stop-loss supported (advanced)

**Files**:
- New: `tg_bot/services/order_monitor.py` (background monitor)
- New: `tg_bot/handlers/demo_orders.py` (order UI)
- New: `~/.lifeos/trading/demo_orders.json` (order storage)
- `tg_bot/handlers/demo.py` (integrate order buttons)
- `bots/supervisor.py` (start order monitor on bot launch)

**Priority**: P0 - Critical for risk management

---

---

### US-007: Charts Integration

**As a** user
**I want to** view price charts for tokens
**So that** I can analyze trends before buying

**Chart Types**:

1. **Price Chart**: OHLCV candlesticks
2. **Volume Chart**: Trading volume bars
3. **PnL Chart**: Portfolio value over time
4. **Holder Distribution**: Top holders pie chart

**Price Chart Generation**:

**Recommended Library**: `mplfinance` - purpose-built for financial candlestick charts

```bash
# Install: pip install mplfinance
```

```python
# tg_bot/handlers/demo_charts.py

import mplfinance as mpf
import pandas as pd
from datetime import datetime
import io
from functools import lru_cache
from datetime import timedelta

# Cache charts for 5 minutes to reduce load
@lru_cache(maxsize=100)
def _get_chart_cache_key(mint: str, interval: str, timestamp_5min: int) -> str:
    """Generate cache key rounded to 5-minute intervals."""
    return f"{mint}:{interval}:{timestamp_5min}"

async def generate_price_chart(
    mint: str,
    symbol: str,
    interval: str = "1h",
    timeframe: str = "24h"
) -> io.BytesIO:
    """Generate professional candlestick chart for a token.

    Uses mplfinance for TradingView-quality charts with proper OHLCV rendering.
    """

    # Get chart data from bags.fm
    async with BagsAPI() as api:
        data = await api.get_chart_data(mint, interval=interval, limit=100)

    candles = data["candles"]

    # Convert to pandas DataFrame (mplfinance requirement)
    df = pd.DataFrame(candles)
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s')
    df.set_index('timestamp', inplace=True)
    df = df[['open', 'high', 'low', 'close', 'volume']]
    df.columns = ['Open', 'High', 'Low', 'Close', 'Volume']

    # Calculate price change for annotation
    price_change_pct = ((df['Close'].iloc[-1] / df['Close'].iloc[0]) - 1) * 100
    change_color = 'g' if price_change_pct > 0 else 'r'

    # Create custom style (dark theme to match Telegram)
    mc = mpf.make_marketcolors(
        up='#00ff00',      # Green candles for price up
        down='#ff0000',    # Red candles for price down
        edge='inherit',
        wick='inherit',
        volume={'up':'#00ff0088', 'down':'#ff000088'},  # Semi-transparent
        alpha=0.9
    )

    s = mpf.make_mpf_style(
        marketcolors=mc,
        gridcolor='#333333',
        gridstyle=':',
        y_on_right=False,
        rc={
            'axes.facecolor': '#1e1e1e',
            'figure.facecolor': '#1e1e1e',
            'axes.edgecolor': '#666666',
            'axes.labelcolor': '#ffffff',
            'xtick.color': '#ffffff',
            'ytick.color': '#ffffff',
            'text.color': '#ffffff'
        }
    )

    # Generate chart
    buf = io.BytesIO()

    mpf.plot(
        df,
        type='candle',
        style=s,
        volume=True,
        title=f'{symbol} ({interval} candles)',
        ylabel='Price (USD)',
        ylabel_lower='Volume',
        figsize=(12, 8),
        savefig=dict(fname=buf, dpi=150, bbox_inches='tight')
    )

    buf.seek(0)
    return buf

# Usage in demo handler:
@demo_callback_handler("chart")
async def show_chart(update, context):
    query = update.callback_query
    await query.answer()

    # Parse callback data: demo:chart:{token_ref}:{timeframe}
    _, _, token_ref, timeframe = query.data.split(":")

    token_address = _resolve_token_ref(token_ref)
    token_info = await get_token_info(token_address)

    # Send "generating..." message
    msg = await query.message.reply_text("📊 Generating chart...")

    # Generate chart
    chart_buffer = await generate_price_chart(
        mint=token_address,
        symbol=token_info["symbol"],
        interval="5m" if timeframe == "1h" else "1h",
        timeframe=timeframe
    )

    # Send chart as photo
    await query.message.reply_photo(
        photo=chart_buffer,
        caption=f"📊 {token_info['symbol']} ({timeframe})\n"
                f"Price: ${token_info['price_usd']}\n"
                f"Volume 24h: ${token_info['volume_24h']:,.0f}\n"
                f"Liquidity: ${token_info['liquidity_usd']:,.0f}",
        reply_markup=InlineKeyboardMarkup([
            [
                InlineKeyboardButton("1h", callback_data=f"demo:chart:{token_ref}:1h"),
                InlineKeyboardButton("4h", callback_data=f"demo:chart:{token_ref}:4h"),
                InlineKeyboardButton("24h", callback_data=f"demo:chart:{token_ref}:24h"),
                InlineKeyboardButton("7d", callback_data=f"demo:chart:{token_ref}:7d"),
            ],
            [
                InlineKeyboardButton("💰 Buy", callback_data=f"demo:buy:{token_ref}"),
                InlineKeyboardButton("🔙 Back", callback_data="demo:sentiment"),
            ]
        ])
    )

    # Delete "generating..." message
    await msg.delete()
```

**Chart Caching**:

```python
# Cache charts for 5 minutes to reduce generation load
CHART_CACHE = {}  # {f"{mint}:{timeframe}": (timestamp, buffer)}

async def get_cached_chart(mint: str, timeframe: str):
    """Get chart from cache if fresh, otherwise generate."""
    cache_key = f"{mint}:{timeframe}"

    if cache_key in CHART_CACHE:
        cached_time, cached_buffer = CHART_CACHE[cache_key]
        age = (datetime.now() - cached_time).total_seconds()

        if age < 300:  # 5 minutes
            logger.info(f"Chart cache hit: {cache_key} (age: {age:.0f}s)")
            cached_buffer.seek(0)  # Reset buffer position
            return cached_buffer

    # Generate new chart
    logger.info(f"Chart cache miss: {cache_key}")
    chart_buffer = await generate_price_chart(mint, timeframe)

    # Cache it
    CHART_CACHE[cache_key] = (datetime.now(), chart_buffer)

    return chart_buffer
```

**Acceptance Criteria**:
- [ ] Charts available for any token
- [ ] Timeframes: 1h, 4h, 24h, 7d, 30d
- [ ] Price and volume shown
- [ ] **Professional candlestick charts with mplfinance** (not basic matplotlib)
- [ ] Dark theme matching Telegram UI
- [ ] Price change percentage displayed
- [ ] Charts cached for 5 minutes (reduce load)
- [ ] Sent as Telegram photo message
- [ ] Quick buy button on chart view
- [ ] Holder distribution chart (pie chart)
- [ ] Portfolio PnL chart over time
- [ ] **mplfinance installed** via `pip install mplfinance`

**Files**:
- New: `tg_bot/handlers/demo_charts.py` (mplfinance-based chart generation)
- Modified: `core/bags_api.py` (chart data fetching)
- `requirements.txt` (add mplfinance, pandas)

**Priority**: P1 - Important for user confidence

---

---

### US-008: 15-Minute Update Cycle

**As a** user
**I want to** have sentiment data update every 15 minutes
**So that** I always have fresh information

**Update Sources & Frequencies**:

| Data Source | Update Frequency | Method |
|-------------|------------------|--------|
| **Sentiment Tokens** | 15 minutes | Scheduled job, aligned with `sentiment_report.py` |
| **Treasury Positions** | Real-time (5s) | WebSocket price updates |
| **Bags Graduations** | Real-time | WebSocket events |
| **Charts** | On-demand | 5-minute cache |
| **User Positions** | Real-time (5s) | WebSocket price updates |
| **Macro Analysis** | 15 minutes | From sentiment report |
| **AI Learnings** | 60 minutes | Hourly compression job |

**Implementation**:

```python
# tg_bot/services/sentiment_updater.py

import asyncio
from datetime import datetime

class SentimentUpdater:
    """Update sentiment data every 15 minutes."""

    def __init__(self):
        self.running = False
        self.last_update = None
        self.sentiment_data = None

    async def start(self):
        """Start the update loop."""
        self.running = True
        logger.info("Sentiment updater started")

        while self.running:
            try:
                await self.update_sentiment()

                # Sleep until next 15-minute mark
                now = datetime.now()
                next_update = now.replace(minute=(now.minute // 15 + 1) * 15, second=0, microsecond=0)
                sleep_seconds = (next_update - now).total_seconds()

                logger.info(f"Next sentiment update in {sleep_seconds:.0f}s @ {next_update:%H:%M}")
                await asyncio.sleep(sleep_seconds)

            except Exception as e:
                logger.error(f"Sentiment update failed: {e}")
                await asyncio.sleep(60)  # Retry in 1 minute

    async def update_sentiment(self):
        """Fetch latest sentiment data."""
        logger.info("Updating sentiment data...")

        # Import sentiment report generator
        from bots.buy_tracker.sentiment_report import SentimentReportBot

        # Generate report (this also posts to Telegram, but we just want the data)
        report_bot = SentimentReportBot()

        # Get the latest sentiment data (don't post, just fetch)
        self.sentiment_data = await report_bot.fetch_sentiment_data()
        self.last_update = datetime.now()

        logger.info(f"Sentiment updated: {len(self.sentiment_data.get('tokens', []))} tokens")

        # Notify active demo users
        await self.notify_users()

    async def notify_users(self):
        """Notify users viewing sentiment hub of update."""
        # Get users currently viewing sentiment hub
        active_users = get_users_on_sentiment_page()

        for user_id in active_users:
            try:
                await send_telegram_message(
                    chat_id=user_id,
                    text="🔄 Sentiment data updated! Tap Refresh to see latest."
                )
            except Exception as e:
                logger.error(f"Failed to notify user {user_id}: {e}")

    def get_data(self):
        """Get cached sentiment data."""
        return self.sentiment_data, self.last_update

# Start updater on bot launch
sentiment_updater = SentimentUpdater()
asyncio.create_task(sentiment_updater.start())
```

**UI Update Indicator**:

```
━━━━━━━━━━━━━━━━━━━━━━━━━
📊 SENTIMENT HUB
Updated: 2:45 PM (14 min ago)
Next Update: 3:00 PM (1 min)
━━━━━━━━━━━━━━━━━━━━━━━━━

[Auto-refreshing in 60s...]

[🔄 Refresh Now]
```

**Auto-Refresh**:

Users viewing sentiment hub get auto-refresh option:

```python
async def show_sentiment_hub(update, context):
    """Show sentiment hub with auto-refresh."""

    # Get sentiment data
    sentiment_data, last_update = sentiment_updater.get_data()

    # Calculate time until next update
    time_since_update = (datetime.now() - last_update).total_seconds() / 60
    next_update_in = 15 - time_since_update

    # Build message
    message = build_sentiment_hub_message(sentiment_data)
    message += f"\n\n📍 Updated: {last_update:%H:%M} ({time_since_update:.0f} min ago)"
    message += f"\n⏰ Next Update: {next_update_in:.0f} min"

    # Keyboard
    keyboard = [
        [InlineKeyboardButton("🔄 Refresh Now", callback_data="demo:refresh_sentiment")],
        [InlineKeyboardButton("🔙 Back to Menu", callback_data="demo:main")],
    ]

    await update.message.reply_text(
        message,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML"
    )

    # Enable auto-refresh (optional)
    if context.user_data.get("auto_refresh_sentiment"):
        # Schedule refresh in next_update_in minutes
        context.job_queue.run_once(
            refresh_sentiment_for_user,
            when=next_update_in * 60,
            data={"chat_id": update.effective_chat.id}
        )
```

**Acceptance Criteria**:
- [ ] Sentiment data updates every 15 minutes
- [ ] Updates aligned with sentiment report generation
- [ ] Last update timestamp shown
- [ ] Countdown to next update shown
- [ ] Manual refresh button available
- [ ] Auto-refresh option (user can enable)
- [ ] Update notification for users viewing sentiment hub
- [ ] Failed updates retry after 1 minute
- [ ] Update status logged

**Files**:
- New: `tg_bot/services/sentiment_updater.py`
- `tg_bot/handlers/demo.py` (integrate update indicator)
- `bots/buy_tracker/sentiment_report.py` (data source)

**Priority**: P0 - Core feature requirement

---

---

### US-009: Wallet Initialization
- Auto-create wallet on first /demo use
- Environment variable: `DEMO_WALLET_PASSWORD`
- Show QR code for funding
- Balance display

---

### US-010: Beautiful Menu UI
- Match screenshot design
- Clean button layouts with emojis
- Status indicators (🟢🔴🟡)
- Monospace tables
- Max 3-level depth

---

### US-011: Insta Snipe
- Quick buy from trending list
- One-tap execution with default size
- Skip confirmation for speed
- Show post-buy summary

---

### US-012: AI Picks
- Grok's top 10 tokens
- Sorted by grade (A+ first)
- Quick buy buttons
- Target/SL suggestions

---

### US-013: Trending Tokens
- Top gainers 24h
- Volume leaders
- New graduations
- Quick charts

---

### US-014: Bags Top 15
- Latest 15 graduations
- Bags intel scores
- Quick analysis
- One-tap buy

---

### US-015: Search Token
- Search by symbol or address
- Autocomplete suggestions
- Show full token card
- Buy/chart buttons

---

### US-016: Quick Trade
- Last traded token quick access
- Repeat last trade
- Average up/down

---

### US-017: Analyze Token
- Deep dive: holders, liquidity, volume
- Grok analysis
- Risk assessment
- Social links

---

### US-018: Positions Dashboard
- All open positions
- Real-time PnL
- Quick actions (sell %, set orders)
- Performance stats

---

### US-019: Balance View
- SOL balance
- Token holdings
- Total portfolio value
- PnL vs initial

---

### US-020: Sell All
- Emergency exit button
- Confirmation required
- Batch execution
- Summary of closures

---

### US-021: PnL Report
- Daily/weekly/monthly/all-time
- Win rate, avg RoR
- Best/worst trades
- Export CSV

---

### US-022: Fee Stats
- Total fees paid
- Breakdown by token
- Network vs platform fees
- Savings from referrals

---

### US-023: AI Trending
- AI-detected trending tokens
- Social sentiment analysis
- Early signal detection

---

### US-024: AI New Pairs
- Newly listed tokens
- AI quality filter
- Risk scores

---

### US-025: Learning Dashboard
- AI insights history
- What's working/failing
- Personalized tips

---

### US-026: Performance Analytics
- Sharpe ratio
- Max drawdown
- ROI over time
- Benchmark vs SOL hold

---

### US-027: Watchlist
- Save tokens to watch
- Price alerts
- Quick buy when ready

---

### US-028: DCA (Dollar Cost Average)
- Recurring buys
- Schedule (daily/weekly)
- Auto-execute

---

### US-029: Alerts System
- Price alerts
- TP/SL notifications
- Treasury signal alerts
- Graduation alerts

---

### US-030: Settings
- Slippage tolerance
- Auto-copy treasury
- Notification preferences
- Tutorial reset

---

---

### US-031: Custom Buy Amount Input

**As a** user
**I want to** enter a custom SOL amount for buying
**So that** I'm not limited to preset buttons and can buy any increment I choose

**User Quote**: *"add any increment to the buys in another button so we don't tell people how much they have to buy"*

**Rationale**:

Preset buy buttons (0.1, 0.5, 1, 5 SOL) serve important purposes (risk management, psychology, AI learning), but advanced users may want custom amounts:

- Buy 0.25 SOL instead of 0.1 or 0.5
- Buy 3 SOL instead of 1 or 5
- Buy 0.05 SOL for micro testing
- Buy 10+ SOL for conviction plays

**UI Flow**:

```
┌───────────────────────────┐
│   BUY TOKEN               │
├───────────────────────────┤
│ Select Amount:            │
│                           │
│ [0.1 SOL] [0.5 SOL]       │
│ [1 SOL]   [5 SOL]         │
│                           │
│ [💰 Custom Amount]        │  ← NEW
│                           │
│ [🔙 Back]                 │
└───────────────────────────┘

User taps "Custom Amount" →

┌───────────────────────────┐
│   ENTER CUSTOM AMOUNT     │
├───────────────────────────┤
│                           │
│ How much SOL to buy?      │
│                           │
│ Min: 0.01 SOL             │
│ Max: 50.0 SOL (balance)   │
│                           │
│ 💡 Suggested sizes:       │
│ • 0.1-0.5 = High risk     │
│ • 1-2 = Medium risk       │
│ • 5+ = Low risk/conviction│
│                           │
│ ━━━━━━━━━━━━━━━━━━━━━━━  │
│                           │
│ Type amount (e.g., "0.75"):│
│                           │
│ [Cancel]                  │
└───────────────────────────┘

User types "0.75" and sends message →

Bot validates:
- Is it a number?
- Is it >= 0.01 SOL?
- Is it <= user's balance?
- Will it cause >5% price impact?

If valid → Show confirmation screen (same as preset amounts)
If invalid → Show error and ask again
```

**Implementation**:

```python
# tg_bot/handlers/demo.py

@demo_callback_handler("buy_custom")
async def buy_custom_amount(update, context):
    """Prompt user for custom buy amount."""
    query = update.callback_query
    await query.answer()

    # Extract token reference from callback
    # demo:buy_custom:{token_ref}
    _, _, token_ref = query.data.split(":")

    # Store token ref in context for message handler
    context.user_data['awaiting_custom_amount'] = token_ref

    await query.message.reply_text(
        "💰 <b>Enter Custom Buy Amount</b>\n\n"
        "How much SOL do you want to buy?\n\n"
        "<b>Limits:</b>\n"
        "• Minimum: 0.01 SOL (~$2.50)\n"
        "• Maximum: 50 SOL (~$12,500)\n\n"
        "💡 <b>Suggested Position Sizes:</b>\n"
        "• 0.1-0.5 SOL = High risk tokens\n"
        "• 1-2 SOL = Medium conviction\n"
        "• 5+ SOL = Strong conviction\n\n"
        "Type your amount (e.g., 0.75) or tap Cancel:",
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("❌ Cancel", callback_data="demo:sentiment")]
        ])
    )


async def demo_message_handler(update: Update, context: CallbackContext):
    """Handle text messages in demo bot (token addresses, custom amounts)."""
    user_data = context.user_data

    # Check if we're waiting for custom amount
    if 'awaiting_custom_amount' in user_data:
        token_ref = user_data.pop('awaiting_custom_amount')
        amount_text = update.message.text.strip()

        # Validate amount
        try:
            amount_sol = float(amount_text)
        except ValueError:
            await update.message.reply_text(
                "❌ Invalid amount. Please enter a number (e.g., 0.75).",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("Try Again", callback_data=f"demo:buy_custom:{token_ref}")],
                    [InlineKeyboardButton("Cancel", callback_data="demo:sentiment")]
                ])
            )
            return

        # Range validation
        if amount_sol < 0.01:
            await update.message.reply_text(
                "❌ Amount too small. Minimum: 0.01 SOL",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("Try Again", callback_data=f"demo:buy_custom:{token_ref}")],
                    [InlineKeyboardButton("Cancel", callback_data="demo:sentiment")]
                ])
            )
            return

        if amount_sol > 50.0:
            await update.message.reply_text(
                f"❌ Amount too large. Maximum: 50 SOL\n"
                f"(You entered {amount_sol} SOL)",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("Try Again", callback_data=f"demo:buy_custom:{token_ref}")],
                    [InlineKeyboardButton("Cancel", callback_data="demo:sentiment")]
                ])
            )
            return

        # Success - proceed to confirmation
        token_address = _resolve_token_ref(token_ref)

        # Show confirmation screen (same as preset amounts)
        await show_buy_confirmation(
            update,
            context,
            token_address=token_address,
            amount_sol=amount_sol,
            source="custom"  # Track that this was custom amount
        )
```

**Acceptance Criteria**:
- [ ] "Custom Amount" button added to buy menu
- [ ] Input validation (numeric, min 0.01, max 50)
- [ ] Clear error messages for invalid input
- [ ] Suggested position sizes shown
- [ ] Same confirmation flow as preset amounts
- [ ] Cancel button returns to sentiment hub
- [ ] AI learning tracks custom vs preset amounts
- [ ] Custom amounts saved in observations for AI analysis

**Files**:
- Modified: `tg_bot/handlers/demo.py` (buy_custom_amount callback, message handler validation)
- Modified: `tg_bot/ui/inline_buttons.py` (add "Custom Amount" button to buy menu)

**Priority**: P1 - User requested feature

---

---

### US-032: Loading States & Clean Menu Transitions

**As a** user
**I want to** see clear loading indicators and smooth menu navigation
**So that** I know the bot is working and can easily navigate back to main menu

**User Quote**: *"everything must work, it must return a nice UI with a processing and completion, each menu must slide back up into the main menu cleanly"*

**Existing Infrastructure** (already implemented):

1. **MenuNavigator** (`tg_bot/ui/interactive_menus.py:309-457`):
   - Breadcrumb tracking system
   - `navigate_to(menu_name, user_id)` - Push to stack
   - `go_back(user_id)` - Pop from stack
   - Currently NOT used consistently in demo bot

2. **Error Templates** (`tg_bot/error_handler.py`):
   - FriendlyError class with emoji, title, message, suggestions
   - ErrorCategory enum (TOKEN_NOT_FOUND, API_ERROR, RATE_LIMITED, etc.)
   - User-friendly error formatting already exists

**Implementation Requirements**:

```python
# Loading indicators for all async operations:

async def execute_buy_with_loading(token_address, amount_sol, chat_id, message_id):
    """Execute buy with loading indicator."""

    # Show loading state
    loading_msg = await bot.edit_message_text(
        chat_id=chat_id,
        message_id=message_id,
        text="⏳ <b>Processing Buy Order...</b>\n\n"
             "• Validating token\n"
             "• Checking liquidity\n"
             "• Executing swap\n\n"
             "<i>This may take 5-10 seconds...</i>",
        parse_mode='HTML'
    )

    try:
        # Execute the buy
        position = await execute_buy_with_tpsl(token_address, amount_sol, wallet)

        # Success state
        await bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=f"✅ <b>Buy Successful!</b>\n\n"
                 f"Token: {position['token']}\n"
                 f"Amount: {amount_sol} SOL\n"
                 f"Tokens: {position['amount_tokens']:,.0f}\n"
                 f"Entry: ${position['entry_price']:.6f}\n\n"
                 f"Take Profit: ${position['tp_price']:.6f} (+{position['tp_percent']:.0f}%)\n"
                 f"Stop Loss: ${position['sl_price']:.6f} (-{position['sl_percent']:.0f}%)\n\n"
                 f"📊 <a href='https://solscan.io/tx/{position['transaction_hash']}'>View on Solscan</a>",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📈 View Position", callback_data=f"demo:position:{position['id']}")],
                [InlineKeyboardButton("🔙 Back to Main", callback_data="demo:main")],
            ])
        )

    except Exception as e:
        # Error state
        await bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=f"❌ <b>Buy Failed</b>\n\n"
                 f"Error: {str(e)}\n\n"
                 f"💡 <b>What to try:</b>\n"
                 f"• Check token address is correct\n"
                 f"• Ensure token has liquidity (>$10k)\n"
                 f"• Try again in a few seconds\n"
                 f"• Contact support if issue persists",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 Retry", callback_data=f"demo:buy:{token_address}:{amount_sol}")],
                [InlineKeyboardButton("🔙 Back to Main", callback_data="demo:main")],
            ])
        )
```

**MenuNavigator Integration**:

```python
# Wire MenuNavigator into all handlers:

menu_nav = MenuNavigator()

@demo_callback_handler("sentiment")
async def show_sentiment_hub(update, context):
    """Show sentiment hub - track navigation."""
    user_id = update.effective_user.id

    # Track navigation
    menu_nav.navigate_to("sentiment_hub", user_id)

    # ... existing sentiment hub code ...

    # All buttons should include "Back to Main"
    keyboard = [
        [InlineKeyboardButton("📊 Charts", callback_data="demo:charts")],
        [InlineKeyboardButton("💰 Buy", callback_data="demo:buy_menu")],
        [InlineKeyboardButton("🔙 Main Menu", callback_data="demo:main")],  # Always include
    ]


@demo_callback_handler("main")
async def show_main_menu(update, context):
    """Main menu - clear navigation stack."""
    user_id = update.effective_user.id

    # Clear stack when returning to main
    menu_nav._user_states[user_id] = []

    # Show main menu
    await update.callback_query.message.edit_text(
        "🏠 <b>Main Menu</b>",
        reply_markup=main_menu_keyboard()
    )
```

**Acceptance Criteria**:
- [ ] Loading indicators for ALL async operations (buy, sell, chart generation, API calls)
- [ ] Three states: Loading → Success/Error → Actionable buttons
- [ ] MenuNavigator used in ALL demo handlers
- [ ] Every submenu has "🔙 Back to Main" button
- [ ] Navigation stack cleared when returning to main menu
- [ ] Error messages use FriendlyError templates
- [ ] Retry buttons on failed operations
- [ ] Success screens include "View Position" + "Back to Main"
- [ ] Loading messages show estimated time (e.g., "5-10 seconds")
- [ ] Chart generation shows "📊 Generating chart..." message

**Files**:
- Modified: `tg_bot/handlers/demo.py` (add loading indicators, wire MenuNavigator)
- Modified: `tg_bot/ui/interactive_menus.py` (ensure MenuNavigator is exported)
- Modified: All demo callback handlers (add breadcrumb tracking)

**Priority**: P0 - Critical for UX (user explicitly requested)

---

---

### US-033: Critical Bug Fixes

**As a** user
**I want** all existing bugs fixed
**So that** the demo bot actually works for public launch

**User Quote**: *"and make sure it does not stop until everything is fixed"*

**Bugs Discovered** (from Scout agent analysis of error logs):

#### Bug 1: `safe_symbol` NameError (CRITICAL)
- **Error**: `NameError: name 'safe_symbol' is not defined`
- **Location**: `tg_bot/handlers/demo.py` in Bags.fm buy flow
- **Impact**: Bags.fm buy flow completely broken
- **Occurrences**: 3 times in last hour
- **Root Cause**: Missing import or undefined function

**Fix**:
```python
# tg_bot/handlers/demo.py

# Add this helper function (or import if it exists elsewhere):
def safe_symbol(symbol: str) -> str:
    """Sanitize token symbol for display (remove special characters)."""
    if not symbol:
        return "UNKNOWN"
    # Remove special chars, limit length
    return ''.join(c for c in symbol if c.isalnum() or c in ['_', '-'])[:10].upper()
```

#### Bug 2: `amount` KeyError (CRITICAL)
- **Error**: `KeyError: 'amount'`
- **Location**: `tg_bot/handlers/demo.py` in sell position handler
- **Impact**: Cannot sell positions
- **Occurrences**: 3 times in last hour
- **Root Cause**: Position dict missing 'amount' key, or using wrong key name

**Fix**:
```python
# tg_bot/handlers/demo.py

# BEFORE (broken):
amount_sol = pos["amount"]

# AFTER (fixed with safe default):
amount_sol = pos.get("amount_sol", pos.get("amount", 0))

# Even better - standardize position keys:
position = {
    "amount_sol": amount_sol,  # Always use this key
    "amount_tokens": tokens_received,
    # ... other fields
}
```

#### Bug 3: Bot Instance Conflicts (HIGH)
- **Error**: `telegram.error.Conflict: terminated by other getUpdates request`
- **Impact**: Bot misses updates, users see no responses
- **Frequency**: Every ~35 seconds
- **Root Cause**: Multiple bot instances running simultaneously

**Fix**:
```python
# bots/supervisor.py

import fcntl
import os

def ensure_single_instance(name: str):
    """Ensure only one instance of this bot is running."""
    lock_file = f"/tmp/{name}.lock"

    try:
        lock_fd = os.open(lock_file, os.O_CREAT | os.O_EXCL | os.O_RDWR)
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except (OSError, IOError):
        raise RuntimeError(f"Another instance of {name} is already running. "
                          f"Lock file: {lock_file}")

    return lock_fd


# At bot startup:
lock = ensure_single_instance("telegram_demo_bot")

# ... run bot ...

# On shutdown:
os.close(lock)
```

#### Bug 4: TP/SL UI Not Wired (HIGH)
- **Issue**: PositionButtons.adjust_tp_sl() exists but callbacks aren't registered
- **Location**: `tg_bot/ui/inline_buttons.py:851-886`
- **Impact**: Users can't adjust TP/SL after opening position
- **Root Cause**: Callbacks `adj_tp`, `adj_sl`, `adj_save`, `adj_cancel` not registered

**Fix**:
```python
# tg_bot/handlers/demo.py

@demo_callback_handler("adj_tp")
async def adjust_take_profit(update, context):
    """Adjust take-profit percentage."""
    query = update.callback_query
    await query.answer()

    # Parse: demo:adj_tp:{position_id}:{delta}
    _, _, position_id, delta = query.data.split(":")
    delta = float(delta)

    # Load position
    pos = load_position(position_id)
    pos["tp_percent"] += delta
    pos["tp_price"] = pos["entry_price"] * (1 + pos["tp_percent"] / 100)

    # Save and refresh UI
    save_position(pos)

    await query.message.edit_text(
        f"Take Profit: {pos['tp_percent']:.0f}% (${pos['tp_price']:.6f})",
        reply_markup=PositionButtons.adjust_tp_sl(
            position_id,
            pos["tp_percent"],
            pos["sl_percent"]
        )
    )


@demo_callback_handler("adj_sl")
async def adjust_stop_loss(update, context):
    """Adjust stop-loss percentage."""
    # Similar to adj_tp


@demo_callback_handler("adj_save")
async def save_tp_sl_adjustments(update, context):
    """Save TP/SL changes and return to position view."""
    query = update.callback_query
    await query.answer("✅ TP/SL updated!")

    _, _, position_id = query.data.split(":")

    # Return to position view
    await show_position_details(update, context, position_id)


@demo_callback_handler("adj_cancel")
async def cancel_tp_sl_adjustments(update, context):
    """Cancel TP/SL changes and return to position view."""
    query = update.callback_query
    await query.answer("❌ Changes discarded")

    _, _, position_id = query.data.split(":")

    # Return to position view (without saving)
    await show_position_details(update, context, position_id)
```

**Acceptance Criteria**:
- [ ] `safe_symbol` function defined or imported (fix NameError)
- [ ] Position dict uses consistent keys (fix KeyError)
- [ ] Single instance enforcement (fix Conflict error)
- [ ] TP/SL adjustment callbacks registered and working
- [ ] All 4 callbacks wired: adj_tp, adj_sl, adj_save, adj_cancel
- [ ] Position view shows "Adjust TP/SL" button
- [ ] TP/SL adjustments save correctly to position storage
- [ ] Error logs show 0 occurrences of fixed bugs after deployment
- [ ] Integration test for each fixed bug

**Files**:
- Modified: `tg_bot/handlers/demo.py` (fix all 4 bugs, add callbacks)
- Modified: `bots/supervisor.py` (single instance enforcement)
- New: `tests/test_demo_bug_fixes.py` (regression tests)

**Priority**: P0 - BLOCKER for public launch

---

---

