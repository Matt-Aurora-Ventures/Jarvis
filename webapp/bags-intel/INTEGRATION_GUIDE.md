# Bags Intel - Supervisor Integration Guide

## Overview

The Bags Intel webapp now integrates with the JARVIS supervisor for cross-component communication, AI-powered recommendations, and continuous learning from trading outcomes.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                  JARVIS Supervisor                      │
│                                                         │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────────┐ │
│  │ Treasury │←→│ Bags     │←→│ Telegram │←→│Twitter │ │
│  │ Bot      │  │ Intel    │  │ Bot      │  │ Bot    │ │
│  └──────────┘  └──────────┘  └──────────┘  └────────┘ │
│       ↑             ↑               ↑             ↑    │
│       └─────────────┴───────────────┴─────────────┘    │
│                Shared State + Feedback Loops            │
└─────────────────────────────────────────────────────────┘
                           ↓
                    ┌──────────────┐
                    │ Ollama/Claude│
                    │     AI       │
                    └──────────────┘
```

## Key Features

### 1. Intelligence Sharing
Bags Intel shares analysis of new token graduations with all other components:
- **Overall Score**: 0-100 quality rating
- **Risk Level**: Low/Medium/High/Extreme
- **Recommendation**: strong_buy/buy/hold/avoid
- **Confidence**: 0.3-0.95 based on historical accuracy
- **AI Reasoning**: Natural language explanation (if Ollama available)

### 2. Feedback Learning
Components can send feedback about outcomes, enabling self-correction:
- Track trading results (profit/loss)
- Measure prediction accuracy
- Adjust future recommendations based on outcomes
- AI-powered learning insights

### 3. Ollama/Claude AI Integration
Optional AI enhancement for better recommendations:
- Generates natural language reasoning
- Learns from feedback patterns
- Provides specific insights for improvement
- Falls back to rule-based if unavailable

---

## API Endpoints

### POST /api/bags-intel/webhook
**Purpose**: Receive new graduation events from bags_intel service

**Request**:
```json
{
  "contract_address": "ABC123...",
  "token_name": "MyToken",
  "symbol": "MTK",
  "scores": {
    "overall": 85.5,
    "bonding": 90.0,
    "creator": 80.0,
    "social": 70.0,
    "market": 88.0,
    "distribution": 85.0,
    "risk_level": "low"
  },
  "market_metrics": {
    "liquidity_sol": 150.5,
    "market_cap": 500000,
    "volume_24h": 150000,
    "price": 0.05
  },
  "bonding_metrics": {
    "buyer_count": 250,
    "duration_minutes": 45
  },
  "holder_count": 180,
  "timestamp": "2026-01-22T12:00:00Z"
}
```

**Response**:
```json
{
  "success": true,
  "message": "Event received and broadcast",
  "event_id": "ABC123...",
  "intelligence_shared": true
}
```

**What happens**:
1. Event stored in webapp database
2. Broadcast to all WebSocket clients (live feed updates)
3. **Intelligence shared with supervisor** (if available)
4. AI reasoning generated (if Ollama available)

---

### POST /api/bags-intel/feedback
**Purpose**: Receive feedback from treasury bot about trading outcomes

**Request**:
```json
{
  "contract_address": "ABC123...",
  "token_name": "MyToken",
  "symbol": "MTK",
  "our_score": 85.5,
  "action_taken": "bought",
  "action_timestamp": "2026-01-22T12:00:00Z",
  "entry_price": 0.05,
  "exit_price": 0.08,
  "outcome": "profit",
  "profit_loss_percent": 60.0,
  "notes": "Exited at 60% profit after 2 hours"
}
```

**Fields**:
- `action_taken`: "bought", "passed", "sold"
- `outcome`: "profit", "loss", "pending"
- `profit_loss_percent`: Actual P/L percentage (optional for pending)

**Response**:
```json
{
  "success": true,
  "message": "Feedback processed",
  "prediction_accuracy": 0.75,
  "total_predictions": 20
}
```

**What happens**:
1. Feedback stored and linked to original intelligence
2. Prediction accuracy recalculated
3. AI learning update triggered (if Ollama available)
4. Future recommendations adjusted based on learnings

---

### GET /api/bags-intel/supervisor/stats
**Purpose**: Check supervisor integration stats

**Response**:
```json
{
  "success": true,
  "stats": {
    "total_intelligence_shared": 50,
    "feedback_received": 20,
    "prediction_accuracy": 0.75,
    "total_predictions": 20,
    "correct_predictions": 15,
    "ollama_available": true,
    "last_intelligence": {
      "contract_address": "...",
      "recommendation": "strong_buy",
      "confidence": 0.85,
      "reasoning": "Exceptional overall score..."
    }
  }
}
```

---

## Integration Examples

### Example 1: Treasury Bot Integration

**Location**: `bots/treasury/trading.py`

```python
import requests
import asyncio
from datetime import datetime

class TreasuryTrader:
    def __init__(self):
        self.bags_intel_url = "http://localhost:5000"

    async def check_bags_intel_recommendation(self, contract_address: str):
        """Check if Bags Intel recommends this token."""
        # Get intelligence from supervisor shared state
        intel = self.supervisor_state.get("bags_intel", {}).get("intelligence", [])

        # Find recommendation for this token
        token_intel = next(
            (i for i in intel if i["contract_address"] == contract_address),
            None
        )

        if token_intel:
            recommendation = token_intel["recommendation"]
            confidence = token_intel["confidence"]
            reasoning = token_intel["reasoning"]

            logger.info(f"Bags Intel: {recommendation} ({confidence:.0%}) - {reasoning}")

            return recommendation in ["buy", "strong_buy"] and confidence >= 0.70

        return False

    async def send_trade_feedback(
        self,
        contract_address: str,
        token_name: str,
        entry_price: float,
        exit_price: float,
        profit_loss_percent: float
    ):
        """Send trading outcome feedback to Bags Intel."""
        outcome = "profit" if profit_loss_percent > 0 else "loss"

        feedback = {
            "contract_address": contract_address,
            "token_name": token_name,
            "our_score": 85.0,  # From original intel
            "action_taken": "bought",
            "action_timestamp": datetime.now().isoformat(),
            "entry_price": entry_price,
            "exit_price": exit_price,
            "outcome": outcome,
            "profit_loss_percent": profit_loss_percent,
            "notes": f"Treasury bot trade result"
        }

        try:
            resp = requests.post(
                f"{self.bags_intel_url}/api/bags-intel/feedback",
                json=feedback,
                timeout=5
            )

            if resp.status_code == 200:
                result = resp.json()
                logger.info(
                    f"Feedback sent - Accuracy: {result.get('prediction_accuracy', 0):.1%}"
                )
        except Exception as e:
            logger.error(f"Failed to send feedback: {e}")
```

---

### Example 2: Telegram Bot Integration

**Location**: `tg_bot/handlers/treasury.py`

```python
from telegram import Update
from telegram.ext import ContextTypes

async def show_bags_intel_recommendations(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show recent Bags Intel recommendations to admin."""
    try:
        resp = requests.get("http://localhost:5000/api/bags-intel/supervisor/stats")
        stats = resp.json()["stats"]

        last_intel = stats.get("last_intelligence")
        if last_intel:
            message = f"""
📊 **Bags Intel - Latest Recommendation**

Token: {last_intel['token_name']}
Score: {last_intel['overall_score']:.1f}/100
Recommendation: {last_intel['recommendation'].upper()}
Confidence: {last_intel['confidence']:.0%}

Reasoning:
{last_intel['reasoning']}

**System Stats**:
Accuracy: {stats['prediction_accuracy']:.1%} ({stats['correct_predictions']}/{stats['total_predictions']})
Intelligence Shared: {stats['total_intelligence_shared']}
            """
            await update.message.reply_text(message, parse_mode='Markdown')
        else:
            await update.message.reply_text("No recent intelligence available.")

    except Exception as e:
        await update.message.reply_text(f"Error fetching intel: {e}")
```

---

### Example 3: Supervisor Registration

**Location**: `bots/supervisor.py`

```python
from webapp.bags_intel import websocket_server

async def start_bags_intel_server():
    """Start Bags Intel webapp as supervised component."""
    # Run Flask-SocketIO server
    websocket_server.socketio.run(
        websocket_server.app,
        host='0.0.0.0',
        port=5000,
        debug=False,
        allow_unsafe_werkzeug=True
    )

# In main():
supervisor = BotSupervisor()

# Register components
supervisor.register("bags_intel", start_bags_intel_server)
supervisor.register("treasury", treasury_bot.start)
supervisor.register("telegram_bot", telegram_bot.start)

await supervisor.run_forever()
```

---

## Ollama/Claude AI Setup

### 1. Install Ollama
```bash
# Download from https://ollama.ai or use package manager
curl -fsSL https://ollama.com/install.sh | sh

# Pull Claude-compatible model
ollama pull llama3.1:70b
```

### 2. Configure Anthropic API Proxy

Create `~/.bashrc` or environment config:
```bash
# Point Anthropic SDK to local Ollama
export ANTHROPIC_BASE_URL="http://localhost:11434/v1"
export ANTHROPIC_API_KEY="ollama"  # Dummy key for local
```

### 3. Verify Integration
```bash
# Check Ollama is running
curl http://localhost:11434/api/tags

# Check Bags Intel can reach it
curl http://localhost:5000/api/bags-intel/supervisor/stats | jq '.stats.ollama_available'
```

**Expected**: `"ollama_available": true`

---

## Shared State Structure

The supervisor maintains a shared state dictionary accessible to all components:

```python
shared_state = {
    "bags_intel": {
        "intelligence": [
            {
                "contract_address": "ABC123...",
                "token_name": "MyToken",
                "symbol": "MTK",
                "overall_score": 85.5,
                "risk_level": "low",
                "recommendation": "strong_buy",
                "confidence": 0.85,
                "reasoning": "Exceptional overall score...",
                "timestamp": "2026-01-22T12:00:00"
            },
            # ... more intelligence entries
        ]
    },
    "learnings": [
        {
            "timestamp": "2026-01-22T12:30:00",
            "insight": "Tokens with creator_score > 80 have 90% success rate",
            "accuracy": 0.75
        },
        # ... AI-generated learnings
    ]
}
```

Access from any component:
```python
# Get latest intelligence
intel = shared_state.get("bags_intel", {}).get("intelligence", [])
latest = intel[0] if intel else None

# Get learnings
learnings = shared_state.get("learnings", [])
```

---

## Feedback Loop Best Practices

### 1. Send Feedback Immediately After Outcome
```python
# ✅ GOOD: Send right after exit
if position.exited:
    await send_trade_feedback(position)

# ❌ BAD: Wait or batch
await asyncio.sleep(3600)  # Don't wait!
```

### 2. Include Detailed Notes
```python
feedback = {
    ...,
    "notes": f"Exited at 60% profit after 2h due to: resistance hit, volume spike, Grok signal"
}
```

### 3. Track "Passed" Decisions Too
```python
# If you didn't buy despite high score, report it
if score > 80 and not bought:
    feedback = {
        "action_taken": "passed",
        "outcome": "pending",  # Can update later if it mooned
        "notes": "Skipped due to: low liquidity, new creator"
    }
```

### 4. Update "Pending" Outcomes
```python
# When position closes, update the feedback
if original_feedback["outcome"] == "pending":
    await send_trade_feedback(updated_feedback)
```

---

## Monitoring & Debugging

### Check System Health
```bash
curl http://localhost:5000/api/health
```

Expected:
```json
{
  "status": "healthy",
  "events_count": 50,
  "timestamp": "2026-01-22T12:00:00",
  "websocket": "enabled",
  "supervisor": true
}
```

### Monitor Prediction Accuracy
```bash
curl http://localhost:5000/api/bags-intel/supervisor/stats | jq '.stats.prediction_accuracy'
```

### Check Ollama Connection
```bash
# From bags intel server logs
grep "Ollama" /var/log/jarvis/bags_intel.log

# Should see:
# [INFO] Ollama available at: http://localhost:11434/v1
```

### View AI Learnings
```python
import requests

resp = requests.get("http://localhost:5000/api/bags-intel/supervisor/stats")
learnings = resp.json()["stats"].get("learnings", [])

for learning in learnings[-5:]:  # Last 5 learnings
    print(f"[{learning['timestamp']}] {learning['insight']}")
```

---

## Troubleshooting

### Issue: Intelligence not being shared
**Symptoms**: `intelligence_shared: false` in webhook response

**Solutions**:
1. Check supervisor_integration.py is imported: `grep "supervisor_integration" websocket_server.py`
2. Verify shared_state is accessible: Check supervisor initialization
3. Look for errors: `grep "Supervisor" /var/log/jarvis/bags_intel.log`

### Issue: Ollama not available
**Symptoms**: `ollama_available: false` in stats

**Solutions**:
1. Start Ollama: `ollama serve`
2. Verify proxy URL: `echo $ANTHROPIC_BASE_URL`
3. Test connection: `curl $ANTHROPIC_BASE_URL/api/tags`
4. Restart webapp: Supervisor will auto-restart

### Issue: Low prediction accuracy
**Symptoms**: `prediction_accuracy < 0.50` after 20+ predictions

**Actions**:
1. Review feedback data quality
2. Check if treasury bot is following recommendations
3. Look at AI learnings for insights
4. Consider adjusting score thresholds

---

## Future Enhancements

1. **Real-Time Recommendation Updates**
   - Push updated recommendations to treasury bot
   - Alert when accuracy improves

2. **Multi-Model AI Support**
   - Compare Ollama vs GPT-4 vs Claude
   - Ensemble recommendations

3. **Advanced Pattern Detection**
   - Time-of-day patterns
   - Creator success rates
   - Market conditions correlation

4. **Backtesting**
   - Test recommendations against historical data
   - Measure theoretical P/L

---

## Support

For issues or questions about Bags Intel integration:
- Check logs: `/var/log/jarvis/bags_intel.log`
- Review shared state: `supervisor.shared_state["bags_intel"]`
- Test endpoints: Use curl or Postman
- Contact: JARVIS development team
