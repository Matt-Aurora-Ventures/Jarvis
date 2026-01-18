# Performance Optimization Roadmap

This document outlines current bottlenecks, optimization opportunities, and planned improvements for the Jarvis trading system.

## Current Bottlenecks

### 1. External API Calls (Highest Impact)

| Component | Current | Target | Notes |
|-----------|---------|--------|-------|
| Jupiter Quote | ~150-200ms | <200ms | External dependency, limited optimization |
| Jupiter Swap | ~200-300ms | <300ms | On-chain transaction |
| CoinGlass API | ~150-200ms | <150ms | Liquidation data |
| Birdeye Price | ~100-150ms | <100ms | Token price lookups |

**Optimization Strategies:**
- Implement request caching with TTL
- Parallel API calls where data is independent
- Connection pooling for HTTP clients
- Consider WebSocket for real-time data

### 2. Signal Detection (~50ms target)

| Sub-phase | Current | Target |
|-----------|---------|--------|
| Liquidation Analysis | ~20ms | <20ms |
| MA Calculation | ~15ms | <15ms |
| Sentiment Scoring | ~25ms | <25ms |
| Decision Matrix | ~5ms | <5ms |

**Optimization Strategies:**
- Cache recent MA calculations
- Batch sentiment requests
- Pre-compute decision thresholds

### 3. Database Queries

| Query Type | Current | Target |
|------------|---------|--------|
| Position lookups | ~20ms | <10ms |
| Trade history | ~30ms | <20ms |
| Log queries | ~50ms | <30ms |

**Optimization Strategies:**
- Add indexes (see `scripts/optimize_queries.py`)
- Query result caching
- Limit result sets with pagination

## Optimization Opportunities

### Short-term (1-2 weeks)

1. **Connection Pooling**
   - Implement aiohttp session reuse for API calls
   - Pool database connections
   - Expected improvement: 10-20% latency reduction

2. **Request Batching**
   - Batch multiple token price lookups
   - Combine API requests where possible
   - Expected improvement: 30-50% fewer API calls

3. **Index Optimization**
   - Run `scripts/optimize_queries.py` to identify missing indexes
   - Add suggested indexes to database
   - Expected improvement: 50%+ query speedup

### Medium-term (1-2 months)

4. **Caching Layer**
   - Redis/memcached for hot data
   - Cache Jupiter quotes for 1-2 seconds
   - Cache token metadata for 5 minutes
   - Expected improvement: 40-60% API call reduction

5. **Async Improvements**
   - Convert remaining sync code to async
   - Use `asyncio.gather()` for parallel operations
   - Expected improvement: 20-30% overall speedup

6. **Query Optimization**
   - Denormalize frequently accessed data
   - Use materialized views for reports
   - Expected improvement: 30-50% query speedup

### Long-term (3+ months)

7. **WebSocket Migration**
   - Replace polling with WebSocket for prices
   - Real-time liquidation updates
   - Expected improvement: 90% reduction in price lookup latency

8. **Data Pipeline**
   - Background data ingestion
   - Pre-computed signals
   - Expected improvement: Instant signal availability

9. **Edge Computing**
   - Move time-critical computations closer to exchange
   - Reduce network latency
   - Expected improvement: 20-50ms latency reduction

## Profiling Tools

### Available Scripts

```bash
# Profile trading flow
python scripts/profile_trading_flow.py --html --iterations 10

# Analyze query performance
python scripts/optimize_queries.py --html

# Run benchmarks
python scripts/benchmark.py
```

### Programmatic Profiling

```python
from core.performance import profile_block, profile_performance

# Context manager
with profile_block("trading.execute_trade"):
    await execute_trade(token, amount)

# Decorator
@profile_performance
async def analyze_sentiment(token: str):
    ...
```

### Metrics Collection

```python
from core.performance import get_metrics_collector

collector = get_metrics_collector()
collector.record_api_latency("jupiter.quote", duration_ms)
collector.record_query_time("SELECT * FROM positions", duration_ms)
```

## Performance Baselines

Baselines are stored in `config/performance_baselines.json`:

| Operation | Target (ms) | Type |
|-----------|-------------|------|
| Signal Detection | 50 | Internal |
| Position Sizing | 10 | Internal |
| Risk Checks | 5 | Internal |
| Jupiter Quote | 200 | External |
| Full Trade | 400 | Mixed |

Regression detection alerts when actual performance exceeds baseline by >10%.

## Monitoring

### Key Metrics to Track

1. **Latency**
   - P50, P95, P99 for all API endpoints
   - Trade execution time distribution
   - Signal detection time

2. **Throughput**
   - Trades per minute capacity
   - API calls per second
   - Database queries per second

3. **Resources**
   - Memory usage over time
   - CPU utilization
   - Network bandwidth

### Dashboards

Performance metrics are exported to `data/performance/metrics.jsonl` in JSONL format for easy ingestion into monitoring tools (Grafana, Prometheus, etc.).

## Testing Performance

```bash
# Unit tests for performance module
pytest tests/unit/test_performance.py -v

# Load testing
pytest tests/load/ -v --benchmark

# Regression testing
python scripts/profile_trading_flow.py --baselines config/performance_baselines.json
```

## Contributing

When optimizing code:

1. **Measure First** - Profile before and after changes
2. **Document** - Update this roadmap with improvements
3. **Test** - Ensure no regressions in functionality
4. **Baseline** - Update baselines when improvements are verified
