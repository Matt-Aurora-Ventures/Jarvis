# ADR-004: Dexter ReAct Pattern for Autonomous Trading Decisions

## Status

Accepted

## Date

2026-01-15

## Context

JARVIS needs to make autonomous trading decisions based on multiple data sources. Traditional rule-based systems are:

1. **Brittle**: Hard-coded rules don't adapt to market changes
2. **Limited**: Can't synthesize information across sources
3. **Opaque**: Difficult to understand why a decision was made

We need an approach that:
- Reasons through complex market situations
- Explains its decision-making process
- Can use multiple tools/data sources
- Maintains a traceable thought process

## Decision

Implement the **ReAct (Reasoning + Acting) pattern** for the Dexter trading agent.

### ReAct Loop

```
1. OBSERVE: Gather market state
2. THINK: Reason about what information is needed
3. ACT: Use tools to gather more data
4. OBSERVE: Process tool results
5. THINK: Reason about the complete picture
6. DECIDE: Make trading decision (or continue loop)
```

### Architecture

```
core/dexter/
  agent.py          # Main ReAct agent
  scratchpad.py     # Reasoning trace storage
  context.py        # Market context builder
  tools/            # Available tools
    market_data.py
    sentiment.py
    whale_tracker.py
    technical.py
```

## Consequences

### Positive

1. **Explainability**: Every decision has a reasoning trace
2. **Adaptability**: Can reason through novel situations
3. **Tool Composition**: Dynamically selects relevant tools
4. **Transparency**: Scratchpad shows complete thought process
5. **Debuggability**: Can trace exactly why a decision was made

### Negative

1. **Latency**: Multiple LLM calls increase decision time
2. **Cost**: More tokens consumed per decision
3. **Complexity**: More complex than rule-based systems
4. **Failure Modes**: LLM errors can cascade

### Mitigations

1. **Max Iterations**: Cap at 15 iterations to prevent loops
2. **Cost Budget**: $0.50 max per decision
3. **Timeout**: 30 second decision timeout
4. **Confidence Threshold**: Only trade if >70% confident
5. **Human Override**: Admin can override any decision

## Implementation

### ReAct Agent

```python
class DexterAgent:
    """ReAct Trading Agent powered by Grok."""

    MAX_ITERATIONS = 15
    MAX_COST_USD = 0.50
    MIN_CONFIDENCE = 70.0

    async def analyze_trading_opportunity(self, symbol: str) -> ReActDecision:
        """
        Main ReAct loop:
        1. Analyze market state
        2. Grok decides what to research
        3. Gather market data
        4. Grok analyzes all signals
        5. Make trading decision if high confidence
        """
        while self.iteration_count < self.MAX_ITERATIONS:
            # THINK: What do we need to know?
            thought = await self.grok.think(self.scratchpad.get_context())
            self._log_reasoning(thought)

            # ACT: Execute a tool
            tool, args = self._parse_action(thought)
            result = await self.execute_tool(tool, args)
            self._log_action(tool, args, result)

            # DECIDE: Can we make a decision?
            if self._can_decide():
                return self._make_decision()

        return ReActDecision(decision=DecisionType.HOLD)
```

### Scratchpad

The scratchpad maintains a complete trace of reasoning:

```python
class Scratchpad:
    """Maintains reasoning trace for explainability."""

    entries: List[ScratchpadEntry]

    def add_thought(self, thought: str):
        self.entries.append(ScratchpadEntry(
            type="thought",
            content=thought,
            timestamp=datetime.now(timezone.utc)
        ))

    def add_action(self, tool: str, args: Dict, result: str):
        self.entries.append(ScratchpadEntry(
            type="action",
            tool=tool,
            args=args,
            result=result,
            timestamp=datetime.now(timezone.utc)
        ))

    def get_formatted(self) -> str:
        """Return formatted trace for debugging."""
        lines = []
        for entry in self.entries:
            if entry.type == "thought":
                lines.append(f"THINK: {entry.content}")
            elif entry.type == "action":
                lines.append(f"ACT: {entry.tool}({entry.args})")
                lines.append(f"OBSERVE: {entry.result}")
        return "\n".join(lines)
```

### Available Tools

| Tool | Description | Output |
|------|-------------|--------|
| `get_price` | Current token price | Price, 24h change |
| `get_sentiment` | Grok sentiment analysis | Score 0-100 |
| `get_whale_activity` | Large transaction activity | Whale count, direction |
| `get_technical` | Technical indicators | RSI, MACD, MA signals |
| `get_liquidity` | DEX liquidity data | Liquidity depth |
| `get_news` | Recent news/catalysts | News items |

### Decision Output

```python
@dataclass
class ReActDecision:
    decision: DecisionType  # TRADE_BUY, TRADE_SELL, HOLD, ERROR
    symbol: str
    rationale: str          # Human-readable explanation
    confidence: float       # 0-100
    tools_used: List[str]   # Tools used in reasoning
    grok_sentiment_score: float
    market_data: Dict
    iterations: int         # Number of reasoning loops
    cost_usd: float         # Total LLM cost
```

### Example Reasoning Trace

```
=== DEXTER REASONING for SOL ===

THINK: Need to assess current market sentiment for SOL

ACT: get_sentiment(symbol="SOL")
OBSERVE: Sentiment score: 78/100, Bullish signals from X/Twitter

THINK: High sentiment, should check whale activity for confirmation

ACT: get_whale_activity(symbol="SOL")
OBSERVE: 3 whale buys in last hour, total $2.5M accumulated

THINK: Strong bullish signals, check technical confirmation

ACT: get_technical(symbol="SOL")
OBSERVE: RSI: 62 (neutral), MACD: bullish crossover, MA: above 50-day

THINK: Multiple confirmations. High confidence in bullish signal.

DECISION: TRADE_BUY
  - Confidence: 85%
  - Rationale: Strong sentiment (78), whale accumulation ($2.5M),
               technical confirmation (MACD crossover)
  - Tools used: sentiment, whale_activity, technical
  - Cost: $0.12 (3 Grok calls)
```

## Configuration

```yaml
# lifeos/config/dexter.yaml
dexter:
  max_iterations: 15
  max_cost_usd: 0.50
  min_confidence: 70.0
  timeout_seconds: 30

  tools:
    sentiment:
      provider: "grok"
      weight: 1.0
    whale_activity:
      provider: "birdeye"
      weight: 0.8
    technical:
      provider: "internal"
      weight: 0.6
```

## Alternatives Considered

### Alternative 1: Rule-Based Decision Engine

- **Pros**: Fast, deterministic, low cost
- **Cons**: Brittle, can't handle novel situations
- **Decision**: Rejected - insufficient adaptability

### Alternative 2: Pure LLM (Single Call)

- **Pros**: Simple, fast
- **Cons**: No tool use, limited context
- **Decision**: Rejected - can't synthesize multiple data sources

### Alternative 3: Traditional ML Pipeline

- **Pros**: Fast inference, proven approaches
- **Cons**: Requires training data, no explainability
- **Decision**: Rejected - need interpretable decisions

## Monitoring

Track for each decision:
- Iteration count
- Cost per decision
- Tool usage frequency
- Decision accuracy (PnL outcome)
- Confidence calibration

## References

- [ReAct Paper](https://arxiv.org/abs/2210.03629)
- [Dexter Agent Implementation](../core/dexter/agent.py)
- [Scratchpad Module](../core/dexter/scratchpad.py)
- [Tool Definitions](../core/dexter/tools/)

## Review

- **Author**: JARVIS Development Team
- **Reviewed By**: Architecture Council
- **Last Updated**: 2026-01-15
