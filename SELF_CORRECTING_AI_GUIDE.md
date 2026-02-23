# Self-Correcting AI System - Integration Guide

## 🧠 Overview

Jarvis now has a comprehensive self-correcting AI system that enables bots to:
- **Learn** from experiences and share knowledge
- **Communicate** with each other in real-time
- **Self-adjust** parameters based on performance
- **Use local AI** (Ollama) to reduce costs

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Bot Supervisor                        │
│         (Coordinates all bot components)                 │
└───────────────────┬─────────────────────────────────────┘
                    │
        ┌───────────┼───────────┐
        │           │           │
   ┌────▼────┐ ┌───▼────┐ ┌───▼─────┐
   │ Twitter │ │Treasury│ │Telegram │
   │   Bot   │ │  Bot   │ │   Bot   │
   └────┬────┘ └───┬────┘ └───┬─────┘
        │          │           │
        └──────────┼───────────┘
                   │
    ┌──────────────┼──────────────┐
    │   Self-Correcting System    │
    │                              │
    │  ┌────────────────────────┐ │
    │  │   Shared Memory        │ │ ← All bots read/write learnings
    │  │   (Learnings DB)       │ │
    │  └────────────────────────┘ │
    │                              │
    │  ┌────────────────────────┐ │
    │  │   Message Bus          │ │ ← Real-time pub/sub
    │  │   (Inter-bot comms)    │ │
    │  └────────────────────────┘ │
    │                              │
    │  ┌────────────────────────┐ │
    │  │   Ollama Router        │ │ ← Local AI (free)
    │  │   ↓ fallback           │ │
    │  │   Claude API (paid)    │ │
    │  └────────────────────────┘ │
    │                              │
    │  ┌────────────────────────┐ │
    │  │   Self Adjuster        │ │ ← Auto-tune parameters
    │  │   (A/B testing)        │ │
    │  └────────────────────────┘ │
    └──────────────────────────────┘
```

## 📦 Components

### 1. Shared Memory
**File:** `core/self_correcting/shared_memory.py`

Centralized knowledge base that all bots can access.

**Features:**
- Persistent storage of learnings
- Search by keywords, component, type
- Success rate tracking
- Auto-pruning of outdated learnings

**Example:**
```python
from core.self_correcting import get_shared_memory, LearningType

memory = get_shared_memory()

# Store a learning
learning_id = memory.add_learning(
    component="trading_bot",
    learning_type=LearningType.SUCCESS_PATTERN,
    content="Buy SOL when RSI < 30 and volume spikes 2x",
    context={"token": "SOL", "rsi_threshold": 30},
    confidence=0.85
)

# Search for relevant learnings
learnings = memory.search_learnings(
    query="RSI trading",
    component="trading_bot",
    min_confidence=0.7
)

for learning in learnings:
    print(f"{learning.content} (confidence: {learning.confidence})")

# Mark learning as successful
memory.mark_success(learning_id)

# Get stats
stats = memory.get_component_stats("trading_bot")
print(f"Trading bot has {stats['total_learnings']} learnings")
```

### 2. Message Bus
**File:** `core/self_correcting/message_bus.py`

Real-time pub/sub system for inter-bot communication.

**Features:**
- Async message delivery
- Priority messaging
- Message filtering
- History buffer
- Dead letter queue

**Example:**
```python
from core.self_correcting import get_message_bus, MessageType, MessagePriority

bus = get_message_bus()

# Subscribe to messages
async def handle_sentiment_change(message):
    print(f"Sentiment changed for {message.data['token']}: {message.data['sentiment']}")

bus.subscribe(
    subscriber="trading_bot",
    message_types=[MessageType.SENTIMENT_CHANGED, MessageType.PRICE_ALERT],
    callback=handle_sentiment_change
)

# Publish a message
await bus.publish(
    sender="sentiment_bot",
    message_type=MessageType.SENTIMENT_CHANGED,
    data={
        "token": "SOL",
        "sentiment": "bullish",
        "score": 0.82,
        "reason": "High social media engagement"
    },
    priority=MessagePriority.HIGH
)

# Get recent messages
recent = await bus.get_recent_messages(
    message_type=MessageType.PRICE_ALERT,
    limit=10
)
```

### 3. Ollama Router
**File:** `core/self_correcting/ollama_router.py`

Routes AI queries to local Ollama models (free) with automatic fallback to Claude (paid).

**Features:**
- Automatic model selection
- Cost tracking
- Performance comparison
- Auto-fallback to Claude

**Recommended Ollama Models:**
- **qwen3-coder**: Code generation/analysis
- **GPT-OSS 20B**: General reasoning
- **llama3.1**: Fast chat/sentiment

**Example:**
```python
from core.self_correcting import get_ollama_router, TaskType, ModelTier

router = get_ollama_router()
await router.start()

# Simple query (will auto-select best model)
response = await router.query(
    prompt="Analyze this tweet sentiment: 'SOL to the moon! 🚀'",
    task_type=TaskType.SENTIMENT_ANALYSIS
)

print(f"Model used: {response.model_used}")
print(f"Response: {response.text}")
print(f"Cost: ${response.cost:.4f}")
print(f"Latency: {response.latency_ms:.0f}ms")

# Force local model
response = await router.query(
    prompt="Write a Python function to calculate RSI",
    task_type=TaskType.CODE_GENERATION,
    prefer_tier=ModelTier.LOCAL_ADVANCED
)

# Get stats
stats = router.get_stats()
print(f"Ollama requests: {stats['ollama_requests']}")
print(f"Claude requests: {stats['claude_requests']}")
print(f"Cost savings: ${stats['cost_savings']:.2f}")
```

### 4. Self Adjuster
**File:** `core/self_correcting/self_adjuster.py`

Automatically tunes bot parameters through A/B testing.

**Features:**
- Performance metric tracking
- A/B testing with statistical analysis
- Automatic rollback on degradation
- Learning storage

**Example:**
```python
from core.self_correcting import get_self_adjuster, Parameter, MetricType

adjuster = get_self_adjuster()
await adjuster.start()

# Register tunable parameters
adjuster.register_component("trading_bot", {
    "stop_loss_pct": Parameter(
        name="stop_loss_pct",
        current_value=5.0,  # Current 5% stop loss
        min_value=1.0,
        max_value=10.0,
        step=0.5,
        affects_metrics=[MetricType.SUCCESS_RATE, MetricType.COST]
    ),
    "take_profit_pct": Parameter(
        name="take_profit_pct",
        current_value=15.0,
        min_value=5.0,
        max_value=30.0,
        step=2.0,
        affects_metrics=[MetricType.SUCCESS_RATE]
    )
})

# Record performance metrics
adjuster.record_metric(
    component="trading_bot",
    metric_type=MetricType.SUCCESS_RATE,
    value=0.73  # 73% success rate
)

adjuster.record_metric(
    component="trading_bot",
    metric_type=MetricType.LATENCY,
    value=1250  # 1.25 seconds
)

# Get current performance
success_rate = adjuster.get_current_performance(
    component="trading_bot",
    metric_type=MetricType.SUCCESS_RATE,
    window_minutes=60
)
print(f"Last hour success rate: {success_rate:.2%}")

# The adjuster will automatically:
# 1. Run A/B tests on parameters every hour
# 2. Compare performance metrics
# 3. Keep better values, rollback worse ones
# 4. Store learnings in shared memory
```

## 🔄 Complete Integration Example

Here's how to integrate all components into a bot:

```python
"""
Example: Self-Correcting Trading Bot
"""

import asyncio
from core.self_correcting import (
    get_shared_memory,
    get_message_bus,
    get_ollama_router,
    get_self_adjuster,
    LearningType,
    MessageType,
    TaskType,
    Parameter,
    MetricType
)

class SelfCorrectingTradingBot:
    def __init__(self):
        # Get global instances
        self.memory = get_shared_memory()
        self.bus = get_message_bus()
        self.router = get_ollama_router()
        self.adjuster = get_self_adjuster()

        # Bot configuration
        self.stop_loss_pct = 5.0
        self.take_profit_pct = 15.0

    async def start(self):
        # 1. Start Ollama router
        await self.router.start()

        # 2. Register tunable parameters with self-adjuster
        self.adjuster.register_component("trading_bot", {
            "stop_loss_pct": Parameter(
                name="stop_loss_pct",
                current_value=self.stop_loss_pct,
                min_value=1.0,
                max_value=10.0,
                step=0.5,
                affects_metrics=[MetricType.SUCCESS_RATE, MetricType.COST]
            ),
            "take_profit_pct": Parameter(
                name="take_profit_pct",
                current_value=self.take_profit_pct,
                min_value=5.0,
                max_value=30.0,
                step=2.0,
                affects_metrics=[MetricType.SUCCESS_RATE]
            )
        })

        await self.adjuster.start()

        # 3. Subscribe to relevant messages
        self.bus.subscribe(
            subscriber="trading_bot",
            message_types=[
                MessageType.SENTIMENT_CHANGED,
                MessageType.PRICE_ALERT,
                MessageType.NEW_LEARNING
            ],
            callback=self.handle_message
        )

        # 4. Load past learnings
        learnings = self.memory.search_learnings(
            component="trading_bot",
            learning_type=LearningType.SUCCESS_PATTERN,
            min_confidence=0.7
        )
        print(f"Loaded {len(learnings)} past learnings")

    async def handle_message(self, message):
        """Handle messages from other bots."""
        if message.type == MessageType.SENTIMENT_CHANGED:
            token = message.data['token']
            sentiment = message.data['sentiment']
            score = message.data['score']

            # Use learning: only trade if sentiment strong
            if score > 0.8 and sentiment == "bullish":
                await self.consider_buy(token, score)

        elif message.type == MessageType.NEW_LEARNING:
            # Another bot learned something - check if relevant
            print(f"New learning from {message.sender}: {message.data['content']}")

    async def consider_buy(self, token: str, sentiment_score: float):
        """Consider buying a token."""
        # 1. Search for past learnings about this token
        past_learnings = self.memory.search_learnings(
            query=f"{token} trading",
            min_confidence=0.6
        )

        # 2. Use AI to analyze (will use Ollama if available)
        analysis = await self.router.query(
            prompt=f"Should I buy {token}? Sentiment score: {sentiment_score}. "
                  f"Past learnings: {[l.content for l in past_learnings[:3]]}",
            task_type=TaskType.REASONING
        )

        decision = "buy" in analysis.text.lower()

        # 3. Execute trade
        if decision:
            success = await self.execute_buy(token, sentiment_score)

            # 4. Record metrics
            self.adjuster.record_metric(
                component="trading_bot",
                metric_type=MetricType.SUCCESS_RATE,
                value=1.0 if success else 0.0
            )

            # 5. Store learning if successful
            if success:
                learning_id = self.memory.add_learning(
                    component="trading_bot",
                    learning_type=LearningType.SUCCESS_PATTERN,
                    content=f"Bought {token} with sentiment {sentiment_score} - successful",
                    context={"token": token, "sentiment": sentiment_score},
                    confidence=0.8
                )

                # 6. Broadcast to other bots
                await self.bus.publish(
                    sender="trading_bot",
                    message_type=MessageType.NEW_LEARNING,
                    data={
                        "learning_id": learning_id,
                        "content": f"Successful buy on {token}",
                        "confidence": 0.8
                    }
                )

    async def execute_buy(self, token: str, sentiment_score: float) -> bool:
        """Execute buy order (placeholder)."""
        print(f"Executing buy for {token} (sentiment: {sentiment_score})")
        # Actual trading logic here
        return True

    async def run_forever(self):
        """Main loop."""
        while True:
            await asyncio.sleep(60)

            # Periodically sync parameters from self-adjuster
            params = self.adjuster.components.get("trading_bot", {})
            if "stop_loss_pct" in params:
                self.stop_loss_pct = params["stop_loss_pct"].current_value
            if "take_profit_pct" in params:
                self.take_profit_pct = params["take_profit_pct"].current_value

# Usage
async def main():
    bot = SelfCorrectingTradingBot()
    await bot.start()
    await bot.run_forever()

if __name__ == "__main__":
    asyncio.run(main())
```

## 🚀 Ollama Setup

### Install Ollama
```bash
# Linux/Mac
curl -fsSL https://ollama.com/install.sh | sh

# Windows
# Download from https://ollama.com/download
```

### Pull Recommended Models
```bash
# Code generation/analysis
ollama pull qwen3-coder

# General reasoning
ollama pull gpt-oss-20b

# Fast sentiment/chat
ollama pull llama3.1
```

### Start Ollama Server
```bash
ollama serve
```

### Test Integration
```python
from core.self_correcting import get_ollama_router, TaskType

router = get_ollama_router()
await router.start()

# Should use local Ollama (free!)
response = await router.query(
    prompt="Analyze sentiment: SOL is pumping! 🚀",
    task_type=TaskType.SENTIMENT_ANALYSIS
)

print(f"Cost: ${response.cost}")  # Should be $0.00
```

## 📊 Monitoring

### Check Shared Memory Stats
```python
memory = get_shared_memory()
stats = memory.get_global_stats()

print(f"Total learnings: {stats['active_learnings']}")
print(f"Successful applications: {stats['successful_applications']}")
print(f"Failed applications: {stats['failed_applications']}")
```

### Check Message Bus Stats
```python
bus = get_message_bus()
stats = bus.get_stats()

print(f"Total messages: {stats['total_messages']}")
print(f"Active subscriptions: {stats['active_subscriptions']}")
print(f"Failed deliveries: {stats['failed_deliveries']}")
```

### Check Ollama Router Stats
```python
router = get_ollama_router()
stats = router.get_stats()

print(f"Ollama available: {stats['ollama_available']}")
print(f"Ollama requests: {stats['ollama_requests']}")
print(f"Claude requests: {stats['claude_requests']}")
print(f"Total cost: ${stats['total_cost']:.2f}")
print(f"Cost savings: ${stats['cost_savings']:.2f}")
```

### Check Self-Adjuster Stats
```python
adjuster = get_self_adjuster()
stats = adjuster.get_global_stats()

print(f"Active tests: {stats['active_tests']}")
print(f"Completed tests: {stats['completed_tests']}")
print(f"Successful optimizations: {stats['successful_optimizations']}")

# Component-specific
comp_stats = adjuster.get_component_stats("trading_bot")
print(f"Recent metrics: {comp_stats['recent_metrics']}")
```

## 🎯 Best Practices

### 1. Learning Storage
- Store learnings when you discover something new
- Update success rate when you apply a learning
- Prune old learnings periodically

### 2. Message Bus
- Subscribe only to relevant messages
- Use priority for urgent messages
- Handle messages asynchronously

### 3. Ollama Router
- Use local models for simple tasks (sentiment, chat)
- Fall back to Claude for complex reasoning
- Monitor cost savings

### 4. Self Adjuster
- Register all tunable parameters
- Record metrics consistently
- Let it run for a few days to gather data

## 🔮 Future Enhancements

- **Semantic Search**: Upgrade shared memory to use embeddings
- **Multi-Agent Coordination**: Complex task delegation between bots
- **Reinforcement Learning**: Learn optimal strategies from outcomes
- **Anomaly Detection**: Auto-detect when something is wrong
- **Auto-Scaling**: Adjust bot resources based on load

---

Built with 🧠 for Jarvis. Self-improving AI that gets better over time!
