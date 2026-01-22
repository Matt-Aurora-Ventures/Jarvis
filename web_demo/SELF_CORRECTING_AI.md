# Self-Correcting AI System

## Overview

The JARVIS Web Demo features a **self-correcting AI system** that continuously learns from trading outcomes and improves its recommendations over time.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      Web Demo Frontend                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
│  │ Swap UI      │  │ AI Insights  │  │ Price Ticker │         │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘         │
│         │                  │                  │                  │
└─────────┼──────────────────┼──────────────────┼─────────────────┘
          │                  │                  │
          ▼                  ▼                  ▼
┌─────────────────────────────────────────────────────────────────┐
│                    FastAPI Backend                               │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ Self-Correcting AI Service                               │  │
│  │                                                            │  │
│  │  ┌───────────────┐      ┌────────────────┐              │  │
│  │  │ Ollama Router │─────▶│ Claude (Cloud) │              │  │
│  │  │ (Local, Free) │      │ (Powerful)     │              │  │
│  │  └───────┬───────┘      └────────┬───────┘              │  │
│  │          │                       │                        │  │
│  │          └───────┬───────────────┘                        │  │
│  │                  │                                         │  │
│  │                  ▼                                         │  │
│  │          Recommendation                                    │  │
│  │         (Action, Confidence,                              │  │
│  │          Reasoning, Score)                                │  │
│  │                  │                                         │  │
│  │                  ▼                                         │  │
│  │          Feedback Loop  ◀─────────┐                       │  │
│  │          (Learn from   │          │                       │  │
│  │           outcomes)    │          │                       │  │
│  │                        │          │                       │  │
│  └────────────────────────┼──────────┼───────────────────────┘  │
│                            │          │                          │
│  ┌────────────────────────┼──────────┼───────────────────────┐  │
│  │ Supervisor Bridge      │          │                       │  │
│  │                        ▼          │                       │  │
│  │  Share Intelligence ───┘          │                       │  │
│  │  Publish Events                   │                       │  │
│  │  Collect Learnings ◀──────────────┘                       │  │
│  │                                                            │  │
│  └────────────────────────┬───────────────────────────────────┘  │
│                            │                                      │
└────────────────────────────┼──────────────────────────────────────┘
                             │
                             ▼
         ┌───────────────────────────────────────┐
         │    Shared State File                  │
         │  (~/.lifeos/shared_state/             │
         │   web_demo_state.json)                │
         │                                       │
         │  Accessible by all Jarvis components: │
         │  • Treasury Bot                       │
         │  • Twitter Bot                        │
         │  • Telegram Bot                       │
         │  • Bags Intel                         │
         │  • Web Demo                           │
         └───────────────────────────────────────┘
```

## Components

### 1. Self-Correcting AI Service
**File:** `backend/app/services/self_correcting_ai.py`

**Features:**
- Routes to Ollama (local, fast, free) or Claude (cloud, powerful)
- Analyzes tokens using metrics + AI reasoning
- Tracks prediction accuracy over time
- Adjusts confidence based on historical performance
- Learns from trading outcomes via feedback loop

**How It Works:**
```python
# 1. Analyze a token
recommendation = await ai_service.analyze_token({
    "address": "token_mint_address",
    "symbol": "TOKEN",
    "liquidity_usd": 500_000,
    "volume_24h": 100_000,
    "holder_count": 1_500,
    # ... more metrics
})
# Returns: {action: "buy", confidence: 0.75, reasoning: "...", score: 72}

# 2. User trades based on recommendation

# 3. Record actual outcome
await ai_service.record_outcome(TradeOutcome(
    token_address="token_mint_address",
    token_symbol="TOKEN",
    action="buy",
    entry_price=0.05,
    exit_price=0.08,
    profit_loss_pct=60.0,
    outcome="profit"
))

# 4. AI learns from this outcome
# - Updates prediction accuracy
# - Adjusts future confidence levels
# - Generates insights about what worked/failed
# - Shares learnings with other components
```

### 2. Bags API Integration
**File:** `backend/app/services/bags_service.py`

**Features:**
- Connects to `bags-swap-api` server (from gitignore)
- Get swap quotes with route optimization
- Create transactions for user signing
- Track usage stats (admin)

**Endpoints:**
```python
# Get quote
quote = await bags.get_quote(
    input_mint="So11111111111111111111111111111111111111112",  # SOL
    output_mint="EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",  # USDC
    amount=1_000_000_000,  # 1 SOL
    slippage_bps=50  # 0.5%
)

# Create swap transaction
tx = await bags.create_swap_transaction(
    quote_response=quote,
    user_public_key="9WzDXw..."
)
# User signs tx with their wallet
```

### 3. Supervisor Bridge
**File:** `backend/app/services/supervisor_bridge.py`

**Features:**
- Bidirectional communication with Jarvis supervisor
- Shared state file for cross-component data
- Event publishing/subscription
- Learning sharing across ecosystem

**Usage:**
```python
bridge = get_supervisor_bridge()

# Publish event
bridge.publish_event(
    event_type="ai_recommendation",
    data={"token": "SOL", "action": "buy", "confidence": 0.75}
)

# Share learning
bridge.share_learning(
    insight="Tokens with <10 SOL liquidity often rugpull within 24h",
    category="risk",
    confidence=0.85
)

# Get learnings from other components
learnings = bridge.get_learnings(category="trading", min_confidence=0.7)
```

## Continuous Improvement Loop

### Flow

```
1. AI Analyzes Token
   ├─ Calculates base score from metrics
   ├─ Generates AI reasoning (Ollama or Claude)
   ├─ Adjusts confidence based on historical accuracy
   └─ Returns recommendation

2. Recommendation Shared
   ├─ Stored in AI service
   ├─ Published to supervisor bridge
   └─ Sent to frontend

3. User Acts on Recommendation
   ├─ Executes trade (or skips)
   └─ Records entry price

4. Outcome Recorded
   ├─ User reports final outcome (profit/loss/pending)
   ├─ AI evaluates if prediction was correct
   └─ Updates prediction accuracy

5. Learning Extraction
   ├─ AI analyzes what went right/wrong
   ├─ Generates actionable insights
   ├─ Stores learning in shared state
   └─ Adjusts future recommendations

6. Ecosystem Benefits
   ├─ Other components read learnings
   ├─ Collective intelligence improves
   └─ Loop repeats
```

### Self-Correction Mechanisms

**1. Confidence Adjustment**
```python
if prediction_accuracy < 0.6:
    confidence *= 0.75  # Reduce confidence if accuracy is low

if prediction_accuracy > 0.75:
    confidence *= 1.1  # Boost confidence if accuracy is high
```

**2. Learning from Mistakes**
```python
if outcome == "loss" and recommendation == "buy":
    insight = "Avoid similar tokens with these characteristics in future"
    store_learning(insight, category="risk", confidence=0.8)
```

**3. Pattern Recognition**
```python
# AI extracts patterns from outcomes
if multiple_losses_on_low_liquidity_tokens:
    increase_liquidity_weight_in_scoring()
```

## API Endpoints

### AI Analysis

**POST `/api/v1/ai/analyze`**
```json
{
  "token_address": "...",
  "token_symbol": "TOKEN",
  "liquidity_usd": 500000,
  "volume_24h": 100000,
  "holder_count": 1500,
  "use_ai": true
}
```

**Response:**
```json
{
  "action": "buy",
  "confidence": 0.75,
  "reasoning": "Strong liquidity and holder base...",
  "score": 72.5,
  "model_used": "ollama",
  "prediction_accuracy": 0.682
}
```

**POST `/api/v1/ai/record-outcome`**
```json
{
  "token_address": "...",
  "token_symbol": "TOKEN",
  "action": "buy",
  "entry_price": 0.05,
  "exit_price": 0.08,
  "profit_loss_pct": 60.0,
  "outcome": "profit"
}
```

**Response:**
```json
{
  "status": "recorded",
  "prediction_accuracy": 0.697,
  "total_predictions": 58,
  "message": "Outcome recorded. AI will learn from this result."
}
```

**GET `/api/v1/ai/stats`**
```json
{
  "ai": {
    "total_recommendations": 125,
    "total_outcomes": 58,
    "prediction_accuracy": 0.697,
    "preferred_model": "ollama",
    "ollama_available": true,
    "claude_available": true
  },
  "supervisor": {
    "total_events": 342,
    "total_learnings": 28,
    "shared_keys": ["ai_recommendations", "events", "learnings"]
  }
}
```

### Bags Trading

**POST `/api/v1/bags/quote`**
**POST `/api/v1/bags/swap`**
**GET `/api/v1/bags/tokens/popular`**
**GET `/api/v1/bags/health`**

## Environment Variables

```bash
# AI Provider (choose one or both)
ANTHROPIC_API_KEY=sk-ant-...           # Claude (cloud, powerful)
OLLAMA_ANTHROPIC_BASE_URL=http://localhost:11434/v1  # Ollama (local, free)

# Bags API
BAGS_API_URL=http://localhost:3000     # bags-swap-api service
BAGS_API_KEY=your-bags-api-key         # For admin stats

# Supervisor Integration
JARVIS_STATE_DIR=~/.lifeos/shared_state  # Shared state location
```

## Deployment

### With Ollama (Local, Free)

1. Start Ollama with Anthropic API proxy:
```bash
cd bags-swap-api
npm install
BAGS_API_KEY=your-key npm start
```

2. Configure Ollama proxy:
```bash
# In .env
OLLAMA_ANTHROPIC_BASE_URL=http://localhost:11434/v1
```

3. Start web demo:
```bash
docker-compose up -d
```

### With Claude (Cloud, Powerful)

```bash
# In .env
ANTHROPIC_API_KEY=sk-ant-...

docker-compose up -d
```

## Metrics & Monitoring

**Key Metrics:**
- Prediction accuracy (% of correct predictions)
- Total recommendations made
- Total outcomes recorded
- Model preference (Ollama vs Claude usage)
- Learnings generated
- Events published to supervisor

**Access:**
```bash
curl http://localhost:8000/api/v1/ai/stats
```

## Integration with Jarvis Ecosystem

The web demo integrates with the full Jarvis supervisor ecosystem:

**Shared Intelligence:**
- Treasury bot receives AI recommendations for trading decisions
- Twitter bot gets market insights for tweet generation
- Telegram bot accesses AI stats for user queries
- All components contribute learnings back to the pool

**Event Stream:**
- `ai_recommendation` - New token analysis completed
- `trade_outcome` - Actual trading result recorded
- `quote_requested` - Swap quote generated
- `swap_initiated` - Transaction created

**Learnings:**
- Risk patterns ("avoid tokens with X characteristic")
- Success patterns ("tokens with Y metric perform well")
- Market conditions ("high volatility periods need caution")

## Future Enhancements

1. **Advanced Learning:**
   - Pattern recognition across token categories
   - Market regime detection
   - Multi-token correlation analysis

2. **Enhanced Routing:**
   - Auto-switch between Ollama and Claude based on complexity
   - Cost optimization
   - Latency-based selection

3. **Collective Intelligence:**
   - Learn from outcomes across all Jarvis users
   - Share anonymized patterns
   - Federated learning

4. **Real-Time Adaptation:**
   - Intra-day accuracy tracking
   - Dynamic confidence adjustment
   - Live market condition integration

## Security Notes

- AI analysis happens server-side (Rule #2)
- User inputs are validated (Rule #1)
- Recommendations are suggestions, not guarantees
- Users always confirm transactions in their wallet
- Private keys never leave the user's wallet
