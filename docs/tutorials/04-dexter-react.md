# Tutorial: Understanding Dexter ReAct Agent

Learn how JARVIS makes autonomous trading decisions using the ReAct pattern.

## What is Dexter?

Dexter is JARVIS's autonomous trading decision engine. It uses the **ReAct (Reasoning + Acting)** pattern to:

1. Reason through market situations
2. Use tools to gather data
3. Synthesize information
4. Make trading decisions
5. Explain its reasoning

## The ReAct Pattern

### Traditional vs ReAct

**Traditional Rule-Based:**
```
IF sentiment > 70 AND volume > avg THEN buy
```

Problems:
- Rigid, doesn't adapt
- Can't handle edge cases
- No explanation

**ReAct Approach:**
```
THINK: Sentiment is high (78), but let me check whale activity
ACT: get_whale_activity(SOL)
OBSERVE: Whales are accumulating
THINK: Both signals confirm. High confidence in bullish case.
DECIDE: BUY with 85% confidence
```

Benefits:
- Adaptive to context
- Can handle novel situations
- Full explainability

## How Dexter Works

### Step 1: Observation

Dexter starts by observing the request:

```
User asks: "Should I buy SOL?"

Dexter observes:
- Token: SOL
- Current price: $105
- User context: Moderate risk tolerance
```

### Step 2: Reasoning Loop

Dexter thinks about what information it needs:

```
THINK: To make a good decision, I need:
1. Sentiment analysis (Grok)
2. Whale activity
3. Technical indicators
4. Liquidity check
```

### Step 3: Tool Execution

Dexter uses tools to gather data:

```
ACT: get_sentiment("SOL")
OBSERVE: Score 78/100, Bullish trend

ACT: get_whale_activity("SOL")
OBSERVE: 3 large buys, $2.5M accumulated

ACT: get_technical("SOL")
OBSERVE: RSI 62, MACD bullish crossover

ACT: get_liquidity("SOL")
OBSERVE: $45M liquidity, sufficient for trade
```

### Step 4: Synthesis

Dexter synthesizes all information:

```
THINK: Let me analyze all signals:
- Sentiment: 78/100 (bullish)
- Whale activity: Accumulation (bullish)
- Technical: MACD crossover (bullish)
- Liquidity: $45M (safe to trade)

All signals align. High confidence in bullish case.
```

### Step 5: Decision

Dexter makes a final decision:

```
DECIDE: TRADE_BUY
- Confidence: 85%
- Rationale: Strong sentiment (78), whale accumulation ($2.5M),
             technical confirmation (MACD crossover)
- Suggested entry: $105
- Take profit: $126 (+20%)
- Stop loss: $94.50 (-10%)
```

## The Scratchpad

Dexter maintains a "scratchpad" that records its reasoning:

```
=== DEXTER SCRATCHPAD for SOL ===

[10:30:01] THINK: Need to assess current market sentiment
[10:30:02] ACT: get_sentiment("SOL")
[10:30:03] OBSERVE: Sentiment score: 78/100, Bullish trend
[10:30:04] THINK: High sentiment, should check whale activity
[10:30:05] ACT: get_whale_activity("SOL")
[10:30:06] OBSERVE: 3 whale buys, $2.5M accumulated
[10:30:07] THINK: Strong bullish signals, check technical
[10:30:08] ACT: get_technical("SOL")
[10:30:09] OBSERVE: RSI 62, MACD bullish crossover
[10:30:10] THINK: Multiple confirmations. High confidence.
[10:30:11] DECIDE: TRADE_BUY (85% confidence)
```

You can view this with:

```
/dexter trace SOL
```

## Available Tools

Dexter has access to these tools:

### Market Data Tools

| Tool | Description | Output |
|------|-------------|--------|
| `get_price` | Current token price | Price, 24h change |
| `get_volume` | Trading volume | 24h volume, trend |
| `get_liquidity` | DEX liquidity | Depth, safety |
| `get_market_cap` | Market capitalization | Cap, rank |

### Analysis Tools

| Tool | Description | Output |
|------|-------------|--------|
| `get_sentiment` | Grok AI analysis | Score 0-100 |
| `get_technical` | Technical indicators | RSI, MACD, MA |
| `get_whale_activity` | Large transactions | Count, direction |
| `get_news` | Recent news | Headlines, sentiment |

### Risk Tools

| Tool | Description | Output |
|------|-------------|--------|
| `check_liquidity` | Can we trade safely? | Yes/No, max size |
| `check_concentration` | Top holder % | Risk score |
| `check_contract` | Smart contract safety | Audit status |

## Configuration

### Iteration Limits

Dexter has limits to prevent infinite loops:

```yaml
dexter:
  max_iterations: 15      # Max reasoning steps
  max_cost_usd: 0.50      # Max LLM cost per decision
  timeout_seconds: 30     # Max time for decision
```

### Confidence Threshold

Dexter only trades if confidence exceeds threshold:

```yaml
dexter:
  min_confidence: 70.0    # Only trade if >70% confident
```

### Tool Weights

Each tool has a weight in the decision:

```yaml
dexter:
  tools:
    sentiment:
      weight: 1.0         # Primary signal
    whale_activity:
      weight: 0.8
    technical:
      weight: 0.7
    volume:
      weight: 0.5
```

## Viewing Dexter Decisions

### View Last Decision

```
/dexter last
```

**Response:**

```
DEXTER LAST DECISION

Token: SOL
Decision: TRADE_BUY
Confidence: 85%
Time: 2 minutes ago

Reasoning Summary:
- Sentiment: 78/100 (bullish)
- Whale activity: Accumulation
- Technical: MACD crossover

Tools Used: sentiment, whale_activity, technical
Iterations: 4
Cost: $0.12

[View Full Trace]
```

### View Decision Trace

```
/dexter trace SOL
```

Shows the full scratchpad with all reasoning steps.

### View Decision Stats

```
/dexter stats
```

**Response:**

```
DEXTER STATISTICS

Decisions (30 days): 150

By Outcome:
- TRADE_BUY: 85 (57%)
- TRADE_SELL: 25 (17%)
- HOLD: 40 (26%)

Accuracy:
- BUY decisions: 72% profitable
- SELL decisions: 68% correct

Average:
- Iterations per decision: 4.2
- Cost per decision: $0.11
- Time per decision: 3.2 seconds
```

## Error Handling

### Low Confidence

If Dexter can't reach high confidence:

```
DECISION: HOLD
Reason: Insufficient confidence (55%)
Recommendation: Wait for clearer signals
```

### Conflicting Signals

If signals conflict:

```
THINK: Sentiment is bullish (75) but whales are selling.
       These signals conflict. Cannot make high-confidence decision.
DECISION: HOLD
Reason: Conflicting signals (sentiment vs whale)
```

### Tool Failure

If a tool fails:

```
ACT: get_whale_activity("SOL")
OBSERVE: ERROR - API timeout

THINK: Whale data unavailable. Proceeding with available signals.
       Reducing confidence due to missing data.
```

## Manual Override

Admins can override Dexter:

```
/dexter override SOL BUY
```

This executes a trade regardless of Dexter's recommendation.

**Warning**: Use sparingly. Overrides bypass risk checks.

## Training Dexter

Dexter learns from outcomes:

1. **Positive Feedback**: Profitable trades increase tool weights
2. **Negative Feedback**: Losing trades decrease tool weights
3. **Pattern Learning**: Successful patterns are remembered

View learning progress:

```
/dexter learning
```

**Response:**

```
DEXTER LEARNING PROGRESS

Algorithm Improvements:
- Sentiment: +5% accuracy (last 30 days)
- Technical: +3% accuracy
- Whale: -2% accuracy (reducing weight)

Patterns Learned:
1. MACD crossover + whale accumulation = high win rate
2. High sentiment alone = unreliable
3. Volume surge + sentiment = strong signal

Next Improvements:
- Consider adding time-of-day factor
- Whale detection needs refinement
```

## Summary

Dexter provides:
1. **Explainable decisions** via scratchpad
2. **Multi-tool reasoning** for better accuracy
3. **Adaptive learning** from outcomes
4. **Configurable thresholds** for risk management
5. **Full transparency** in decision-making

## Next Steps

- [Security Best Practices](./05-security.md)
- [Fee Structure](./06-revenue.md)
- [ADR-004: ReAct Pattern](../adr/ADR-004-dexter-react-pattern.md)

---

**Last Updated**: 2026-01-18
