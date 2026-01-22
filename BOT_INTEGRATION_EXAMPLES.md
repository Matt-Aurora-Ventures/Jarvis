# Self-Correcting AI Integration Examples

Quick examples showing how Jarvis bots can use the self-correcting AI system.

## Example 1: Treasury Bot Learning from Trades

```python
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

class TreasuryBot:
    def __init__(self):
        # Get global instances - these are singletons managed by supervisor
        self.memory = get_shared_memory()
        self.bus = get_message_bus()
        self.router = get_ollama_router()
        self.adjuster = get_self_adjuster()

        # Trading parameters
        self.stop_loss_pct = 5.0
        self.take_profit_pct = 15.0

    async def initialize(self):
        """Initialize bot with self-correcting capabilities."""
        # 1. Register tunable parameters with self-adjuster
        self.adjuster.register_component("treasury_bot", {
            "stop_loss_pct": Parameter(
                name="stop_loss_pct",
                current_value=self.stop_loss_pct,
                min_value=2.0,
                max_value=10.0,
                step=0.5,
                affects_metrics=[MetricType.SUCCESS_RATE, MetricType.COST]
            ),
            "take_profit_pct": Parameter(
                name="take_profit_pct",
                current_value=self.take_profit_pct,
                min_value=10.0,
                max_value=30.0,
                step=2.0,
                affects_metrics=[MetricType.SUCCESS_RATE]
            )
        })

        # 2. Subscribe to messages from other bots
        self.bus.subscribe(
            subscriber="treasury_bot",
            message_types=[
                MessageType.SENTIMENT_CHANGED,
                MessageType.PRICE_ALERT,
                MessageType.NEW_LEARNING
            ],
            callback=self.handle_message
        )

        # 3. Load past learnings
        past_learnings = self.memory.search_learnings(
            component="treasury_bot",
            learning_type=LearningType.SUCCESS_PATTERN,
            min_confidence=0.7
        )
        print(f"Loaded {len(past_learnings)} successful trading patterns")

    async def handle_message(self, message):
        """Handle messages from other bots."""
        if message.type == MessageType.SENTIMENT_CHANGED:
            token = message.data['token']
            sentiment = message.data['sentiment']
            score = message.data['score']

            # Search for learnings about this token
            token_learnings = self.memory.search_learnings(
                query=f"{token} trading",
                min_confidence=0.6
            )

            # Use AI to decide (will use Ollama if available, Claude fallback)
            analysis = await self.router.query(
                prompt=f"Should I trade {token}? Sentiment: {sentiment} ({score}). Past learnings: {[l.content for l in token_learnings[:3]]}",
                task_type=TaskType.REASONING
            )

            if "buy" in analysis.text.lower():
                await self.execute_trade(token, "buy", score)

    async def execute_trade(self, token: str, action: str, sentiment_score: float):
        """Execute a trade and record learnings."""
        # Execute the trade (placeholder)
        success = True  # Actual trade logic here
        pnl = 0.15  # 15% profit

        # Record metrics for self-adjuster
        self.adjuster.record_metric(
            component="treasury_bot",
            metric_type=MetricType.SUCCESS_RATE,
            value=1.0 if success else 0.0
        )

        if pnl > 0:
            # Store successful pattern
            learning_id = self.memory.add_learning(
                component="treasury_bot",
                learning_type=LearningType.SUCCESS_PATTERN,
                content=f"Bought {token} at sentiment={sentiment_score:.2f}, profit={pnl:.1%}",
                context={"token": token, "sentiment": sentiment_score, "pnl": pnl},
                confidence=min(0.9, 0.5 + (pnl / 0.3))  # Higher profit = higher confidence
            )

            # Broadcast to other bots
            await self.bus.publish(
                sender="treasury_bot",
                message_type=MessageType.NEW_LEARNING,
                data={
                    "learning_id": learning_id,
                    "content": f"Successful trade on {token}",
                    "pnl": pnl
                }
            )
        else:
            # Store failure to avoid repeating
            self.memory.add_learning(
                component="treasury_bot",
                learning_type=LearningType.FAILURE_PATTERN,
                content=f"Avoid buying {token} at sentiment={sentiment_score:.2f}, lost {abs(pnl):.1%}",
                context={"token": token, "sentiment": sentiment_score},
                confidence=0.8
            )

    async def sync_parameters(self):
        """Periodically sync parameters from self-adjuster."""
        params = self.adjuster.components.get("treasury_bot", {})
        if "stop_loss_pct" in params:
            new_value = params["stop_loss_pct"].current_value
            if new_value != self.stop_loss_pct:
                print(f"Self-adjuster optimized stop_loss: {self.stop_loss_pct}% → {new_value}%")
                self.stop_loss_pct = new_value

        if "take_profit_pct" in params:
            new_value = params["take_profit_pct"].current_value
            if new_value != self.take_profit_pct:
                print(f"Self-adjuster optimized take_profit: {self.take_profit_pct}% → {new_value}%")
                self.take_profit_pct = new_value
```

## Example 2: Twitter Bot Using Ollama for Free AI

```python
from core.self_correcting import get_ollama_router, TaskType

class TwitterBot:
    def __init__(self):
        self.router = get_ollama_router()

    async def generate_tweet(self, market_data):
        """Generate tweet using Ollama (free) with Claude fallback."""
        prompt = f"""Generate an engaging crypto tweet about current market conditions:
        - SOL price: ${market_data['sol_price']}
        - Trending tokens: {', '.join(market_data['trending'])}
        - Market sentiment: {market_data['sentiment']}

        Keep it under 280 chars, use emojis, no hashtags."""

        # Will use local Ollama (free) if available, Claude API if not
        response = await self.router.query(
            prompt=prompt,
            task_type=TaskType.TEXT_GENERATION
        )

        print(f"Model used: {response.model_used}")
        print(f"Cost: ${response.cost:.4f}")
        print(f"Latency: {response.latency_ms:.0f}ms")

        return response.text
```

## Example 3: Sentiment Bot Broadcasting to Others

```python
from core.self_correcting import get_message_bus, MessageType, MessagePriority

class SentimentBot:
    def __init__(self):
        self.bus = get_message_bus()

    async def analyze_and_broadcast(self, token: str, social_data):
        """Analyze sentiment and broadcast to other bots."""
        # Analyze sentiment (placeholder)
        sentiment = "bullish"
        score = 0.85

        # Broadcast to all subscribed bots
        await self.bus.publish(
            sender="sentiment_bot",
            message_type=MessageType.SENTIMENT_CHANGED,
            data={
                "token": token,
                "sentiment": sentiment,
                "score": score,
                "reason": "High social media engagement",
                "volume_spike": True
            },
            priority=MessagePriority.HIGH if score > 0.8 else MessagePriority.NORMAL
        )

        print(f"Broadcasted {sentiment} sentiment for {token} to all bots")
```

## Example 4: Buy Bot Learning from Patterns

```python
from core.self_correcting import get_shared_memory, LearningType

class BuyBot:
    def __init__(self):
        self.memory = get_shared_memory()

    async def should_buy(self, token_address: str, token_data):
        """Decide whether to buy based on past learnings."""
        # Search for past experiences with similar tokens
        learnings = self.memory.search_learnings(
            query=f"graduated token {token_data['market_cap']}M mcap",
            learning_type=LearningType.SUCCESS_PATTERN,
            min_confidence=0.6,
            limit=5
        )

        # Check for explicit failures with this token
        failures = self.memory.search_learnings(
            query=f"token {token_address}",
            learning_type=LearningType.FAILURE_PATTERN,
            min_confidence=0.5
        )

        if failures:
            print(f"Avoiding {token_address} - found {len(failures)} past failures")
            return False

        # Use learnings to inform decision
        if learnings:
            print(f"Found {len(learnings)} successful patterns:")
            for l in learnings:
                print(f"  - {l.content} (confidence: {l.confidence:.2f})")

        return True  # Buy decision

    async def record_outcome(self, token_address: str, bought: bool, outcome: dict):
        """Record trade outcome for future learning."""
        if outcome['profit'] > 0.1:  # 10% profit
            self.memory.add_learning(
                component="buy_bot",
                learning_type=LearningType.SUCCESS_PATTERN,
                content=f"Graduated token at {outcome['mcap']}M mcap, {outcome['profit']:.1%} profit in {outcome['hours']}h",
                context={
                    "token": token_address,
                    "mcap": outcome['mcap'],
                    "profit": outcome['profit'],
                    "hold_time_hours": outcome['hours']
                },
                confidence=0.8
            )
        elif outcome['profit'] < -0.05:  # -5% loss
            self.memory.add_learning(
                component="buy_bot",
                learning_type=LearningType.FAILURE_PATTERN,
                content=f"Lost {abs(outcome['profit']):.1%} on graduated token at {outcome['mcap']}M mcap",
                context={
                    "token": token_address,
                    "mcap": outcome['mcap']
                },
                confidence=0.9
            )
```

## Best Practices

1. **Always use singleton getters**: Call `get_*()` functions, don't create new instances
2. **Store learnings immediately**: Don't batch - store right after success/failure
3. **Mark learning success/failure**: Call `mark_success()` or `mark_failure()` when you apply a learning
4. **Use appropriate learning types**: SUCCESS_PATTERN, FAILURE_PATTERN, OPTIMIZATION, etc.
5. **Subscribe selectively**: Only subscribe to messages your bot needs
6. **Let self-adjuster run**: Record metrics consistently, let it optimize over time
7. **Use Ollama for simple tasks**: Sentiment analysis, text generation - save Claude for complex reasoning
8. **Broadcast important events**: Other bots benefit from your discoveries

## Integration Checklist

For each bot that uses the self-correcting system:

- [ ] Import `get_*` functions from `core.self_correcting`
- [ ] Call getters in `__init__` or `initialize()`
- [ ] Register tunable parameters with self-adjuster
- [ ] Subscribe to relevant message types
- [ ] Load past learnings on startup
- [ ] Store learnings after important events
- [ ] Broadcast discoveries to other bots
- [ ] Record metrics for self-adjuster
- [ ] Periodically sync parameters from self-adjuster

## Monitoring

Check the supervisor startup logs:
```
==========================================================
  INITIALIZING SELF-CORRECTING AI SYSTEM
==========================================================
  Shared Memory: 15 learnings
  Message Bus: Ready for inter-bot communication
  Ollama Router: AVAILABLE
  Self Adjuster: Ready for parameter optimization
==========================================================
```

Query stats programmatically:
```python
memory = get_shared_memory()
stats = memory.get_global_stats()
print(f"Total learnings: {stats['active_learnings']}")
print(f"Success rate: {stats['successful_applications'] / (stats['successful_applications'] + stats['failed_applications']):.1%}")

router = get_ollama_router()
stats = router.get_stats()
print(f"Cost savings: ${stats['cost_savings']:.2f}")
```
