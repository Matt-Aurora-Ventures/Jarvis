# ADR-001: Using Grok over Claude for Sentiment Analysis

## Status

Accepted

## Date

2026-01-15

## Context

JARVIS requires real-time sentiment analysis for trading decisions. The system needs to analyze market sentiment, news, and social signals to inform trading algorithms. Two primary LLM options were considered:

1. **Claude (Anthropic)** - High-quality reasoning, better at nuanced analysis
2. **Grok (xAI)** - Faster inference, lower cost, integrated with X/Twitter data

### Decision Drivers

- **Cost**: Sentiment analysis runs frequently (hundreds of calls per day)
- **Latency**: Trading decisions need sub-second response times
- **Data Access**: Direct access to X/Twitter sentiment is valuable
- **Quality**: Needs to be good enough for trading signals (not perfect)

## Decision

We use **Grok** as the primary sentiment analysis engine with a **1.0 weighting** in the decision matrix.

### Rationale

| Factor | Grok | Claude |
|--------|------|--------|
| Cost per 1M tokens | ~$0.10 | ~$3.00 |
| Average latency | 200-400ms | 500-1000ms |
| X/Twitter integration | Native | None |
| Sentiment accuracy | 85-90% | 92-95% |
| Rate limits | Higher | Lower |

**Cost Analysis (Monthly):**
- 10,000 sentiment calls/day
- Average 500 tokens/call
- Grok: ~$15/month
- Claude: ~$450/month

The 5-7% accuracy difference does not justify the 30x cost increase for sentiment-specific tasks.

## Consequences

### Positive

1. **Cost Savings**: $400+/month saved on LLM costs
2. **Lower Latency**: Trading decisions are faster
3. **X Integration**: Native access to Twitter/X sentiment data
4. **Higher Throughput**: Can process more sentiment requests

### Negative

1. **Reduced Accuracy**: 5-7% lower accuracy on nuanced analysis
2. **Vendor Lock-in**: Dependency on xAI API availability
3. **Limited Reasoning**: Complex market analysis may be less thorough

### Mitigations

1. **Fallback to Claude**: For high-stakes decisions (>$1000 trades)
2. **Ensemble Approach**: Combine Grok with other sentiment sources
3. **Confidence Thresholds**: Require higher confidence (70%+) for trade execution
4. **Human Override**: Admin can override automated decisions

## Alternatives Considered

### Alternative 1: Claude Only

- **Pros**: Best accuracy, better reasoning
- **Cons**: 30x cost, slower latency
- **Decision**: Rejected due to cost

### Alternative 2: Open Source Models (Llama, Mistral)

- **Pros**: No API costs, self-hosted
- **Cons**: Requires GPU infrastructure, maintenance burden
- **Decision**: Rejected due to operational complexity

### Alternative 3: Hybrid (Grok + Claude)

- **Pros**: Best of both worlds
- **Cons**: Complexity in routing logic
- **Decision**: Partially adopted - Claude used for high-value decisions

## Implementation

```python
# core/dexter/agent.py - Grok is primary decision maker

class DexterAgent:
    """ReAct Trading Agent powered by Grok."""

    # Grok has 1.0 weighting in all financial decisions
    async def analyze_trading_opportunity(self, symbol: str) -> ReActDecision:
        # Grok sentiment drives the decision
        grok_response = await self.grok.analyze_sentiment(symbol, grok_prompt)
        sentiment_score = self._extract_sentiment_score(grok_response)
        decision.grok_sentiment_score = sentiment_score
```

## References

- [Grok API Documentation](https://x.ai/api)
- [Core Trading Engine](../core/dexter/agent.py)
- [Sentiment Aggregator](../core/sentiment_aggregator.py)

## Review

- **Author**: JARVIS Development Team
- **Reviewed By**: Architecture Council
- **Last Updated**: 2026-01-15
