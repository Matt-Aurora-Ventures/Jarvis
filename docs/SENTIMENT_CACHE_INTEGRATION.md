# Sentiment Cache Integration Guide

This guide shows how to integrate the new sentiment caching layer into `bots/buy_tracker/sentiment_report.py`.

## Quick Start

```python
from core.caching.sentiment_cache import get_sentiment_cache
import hashlib

class SentimentReporter:
    def __init__(self):
        # ... existing init ...
        self._sentiment_cache = get_sentiment_cache()
```

## Integration Examples

### 1. Token Sentiment Caching

**Before:**
```python
async def _get_trending_tokens(self, limit: int = 10) -> List[TokenSentiment]:
    tokens = []
    # Fetch from DexScreener API
    async with self._session.get(trending_url) as resp:
        data = await resp.json()
        # Process data...
    return tokens
```

**After:**
```python
async def _get_trending_tokens(self, limit: int = 10) -> List[TokenSentiment]:
    # Try cache first
    cache_key = f"trending_{limit}"
    cached = await self._sentiment_cache.get_token_sentiment(cache_key)
    if cached:
        logger.debug(f"Cache hit for trending tokens (limit={limit})")
        return [TokenSentiment(**t) for t in cached["tokens"]]

    # Cache miss - fetch from API
    tokens = []
    async with self._session.get(trending_url) as resp:
        data = await resp.json()
        # Process data...

    # Cache results for 10 minutes
    await self._sentiment_cache.set_token_sentiment(
        cache_key,
        {"tokens": [asdict(t) for t in tokens]},
        ttl_minutes=10
    )

    return tokens
```

### 2. Grok Scores Caching (Expensive Calls)

**Before:**
```python
async def _get_grok_token_scores(self, tokens: List[TokenSentiment]) -> None:
    # Call Grok API every time
    async with self._session.post(grok_url, json=payload) as resp:
        data = await resp.json()
        # Parse and apply scores...
```

**After:**
```python
async def _get_grok_token_scores(self, tokens: List[TokenSentiment]) -> None:
    # Create hash of token list for cache key
    tokens_str = ",".join(sorted([t.symbol for t in tokens]))
    tokens_hash = hashlib.md5(tokens_str.encode()).hexdigest()

    # Check cache
    cached_scores = await self._sentiment_cache.get_grok_scores(tokens_hash)
    if cached_scores:
        logger.info(f"Using cached Grok scores ({len(tokens)} tokens)")
        # Apply cached scores
        for token in tokens:
            if token.symbol in cached_scores["scores"]:
                score_data = cached_scores["scores"][token.symbol]
                token.sentiment_score = score_data["score"]
                token.verdict = score_data["verdict"]
                token.reason = score_data["reason"]
        return

    # Cache miss - call Grok API
    logger.info(f"Fetching Grok scores for {len(tokens)} tokens")
    async with self._session.post(grok_url, json=payload) as resp:
        data = await resp.json()
        # Parse and apply scores...

    # Cache results for 15 minutes
    scores_dict = {
        t.symbol: {
            "score": t.sentiment_score,
            "verdict": t.verdict,
            "reason": t.reason
        }
        for t in tokens
    }
    await self._sentiment_cache.set_grok_scores(
        tokens_hash,
        {"scores": scores_dict},
        ttl_minutes=15
    )
```

### 3. Market Regime Caching

**Before:**
```python
async def _get_market_regime(self) -> MarketRegime:
    # Fetch BTC/SOL prices every time
    btc_data = await self._fetch_btc_price()
    sol_data = await self._fetch_sol_price()
    # Calculate regime...
    return regime
```

**After:**
```python
async def _get_market_regime(self) -> MarketRegime:
    # Check cache
    cached = await self._sentiment_cache.get_market_regime()
    if cached:
        logger.debug("Cache hit for market regime")
        return MarketRegime(**cached)

    # Cache miss - fetch fresh data
    logger.debug("Fetching fresh market regime data")
    btc_data = await self._fetch_btc_price()
    sol_data = await self._fetch_sol_price()
    # Calculate regime...

    # Cache for 30 minutes
    await self._sentiment_cache.set_market_regime(
        asdict(regime),
        ttl_minutes=30
    )

    return regime
```

### 4. Traditional Markets Caching

**Before:**
```python
async def _get_traditional_markets(self) -> TraditionalMarkets:
    # Fetch DXY, stocks data
    dxy_data = await self._fetch_dxy()
    stocks_data = await self._fetch_stocks()
    # Process...
    return markets
```

**After:**
```python
async def _get_traditional_markets(self) -> TraditionalMarkets:
    # Check cache
    cached = await self._sentiment_cache.get_traditional_markets()
    if cached:
        logger.debug("Cache hit for traditional markets")
        return TraditionalMarkets(**cached)

    # Cache miss - fetch fresh data
    dxy_data = await self._fetch_dxy()
    stocks_data = await self._fetch_stocks()
    # Process...

    # Cache for 60 minutes
    await self._sentiment_cache.set_traditional_markets(
        asdict(markets),
        ttl_minutes=60
    )

    return markets
```

### 5. Macro Analysis Caching

**Before:**
```python
async def _get_macro_analysis(self) -> MacroAnalysis:
    # Call Grok for macro events
    async with self._session.post(grok_url, json=payload) as resp:
        data = await resp.json()
        # Parse...
    return analysis
```

**After:**
```python
async def _get_macro_analysis(self) -> MacroAnalysis:
    # Check cache
    cached = await self._sentiment_cache.get_macro_analysis()
    if cached:
        logger.debug("Cache hit for macro analysis")
        return MacroAnalysis(**cached)

    # Cache miss - call Grok
    async with self._session.post(grok_url, json=payload) as resp:
        data = await resp.json()
        # Parse...

    # Cache for 4 hours (macro events change slowly)
    await self._sentiment_cache.set_macro_analysis(
        asdict(analysis),
        ttl_minutes=240
    )

    return analysis
```

## Cache Invalidation

### On New Data Arrival

```python
async def generate_and_post_report(self):
    """Main report generation with cache invalidation."""

    # Check if we have significantly new data
    new_btc_price = await self._fetch_btc_price()
    if abs(new_btc_price - self._last_btc_price) > 1000:  # $1K change
        logger.info("Significant BTC price change - invalidating market regime cache")
        self._sentiment_cache.invalidate_market_regime()
        self._last_btc_price = new_btc_price

    # Get data (uses cache when available)
    regime = await self._get_market_regime()
    tokens = await self._get_trending_tokens()
    await self._get_grok_token_scores(tokens)

    # Generate report...
```

### Scheduled Invalidation

```python
async def _invalidate_stale_caches(self):
    """Invalidate caches on schedule (e.g., market open/close)."""
    now = datetime.now(timezone.utc)

    # Invalidate traditional markets at market open (9:30 AM ET)
    if now.hour == 13 and now.minute == 30:  # UTC
        logger.info("Market open - invalidating traditional markets cache")
        self._sentiment_cache.invalidate_on_new_data("market")

    # Invalidate macro analysis daily at midnight
    if now.hour == 0 and now.minute == 0:
        logger.info("Daily reset - invalidating macro analysis")
        await self._sentiment_cache.set_macro_analysis(None)  # Force refresh
```

## Monitoring Cache Performance

### Log Metrics Periodically

```python
async def _log_cache_metrics(self):
    """Log cache performance metrics."""
    metrics = self._sentiment_cache.get_metrics()

    logger.info("=== Sentiment Cache Performance ===")
    logger.info(f"Token Hit Rate: {metrics['token_sentiment']['hit_rate']:.2%}")
    logger.info(f"Market Hit Rate: {metrics['market_regime']['hit_rate']:.2%}")
    logger.info(f"Grok Hit Rate: {metrics['grok_analysis']['hit_rate']:.2%}")
    logger.info(f"Overall Hit Rate: {metrics['overall']['hit_rate']:.2%}")
    logger.info(f"Total Invalidations: {metrics['overall']['invalidations']}")

    # Can also use built-in logging
    self._sentiment_cache.log_metrics()
```

### Add to Telegram Report

```python
async def _post_cache_stats_to_telegram(self):
    """Post cache performance to Telegram for monitoring."""
    metrics = self._sentiment_cache.get_metrics()

    message = f"""
📊 **Cache Performance**

Token Sentiment: {metrics['token_sentiment']['hit_rate']:.1%} hit rate
Market Regime: {metrics['market_regime']['hit_rate']:.1%} hit rate
Grok API: {metrics['grok_analysis']['hit_rate']:.1%} hit rate
Overall: {metrics['overall']['hit_rate']:.1%} hit rate

Grok Savings: {metrics['grok_analysis']['hits']} cached calls
(~${metrics['grok_analysis']['hits'] * 0.01:.2f} saved)
"""

    await self.telegram_bot.send_message(
        chat_id=ADMIN_CHAT_ID,
        text=message,
        parse_mode="Markdown"
    )
```

## Expected Performance Improvements

### Grok API Call Reduction
- **Before**: 1 call per report (every 30 minutes)
- **After**: 1 call per 15 minutes (cached)
- **Savings**: ~50% reduction in Grok API costs

### DexScreener API Calls
- **Before**: 1 call per report + per token
- **After**: 1 call per 10 minutes (cached)
- **Savings**: ~67% reduction in API calls

### Overall Latency
- **Before**: 500-1000ms for Grok + DexScreener calls
- **After**: <1ms for cache hits
- **Improvement**: 500-1000x faster for cached data

## Migration Checklist

- [ ] Import `get_sentiment_cache()` in `SentimentReporter.__init__`
- [ ] Wrap `_get_trending_tokens` with token sentiment cache
- [ ] Wrap `_get_grok_token_scores` with Grok scores cache
- [ ] Wrap `_get_market_regime` with market regime cache
- [ ] Wrap `_get_traditional_markets` with traditional markets cache
- [ ] Wrap `_get_macro_analysis` with macro analysis cache
- [ ] Add cache invalidation on significant price changes
- [ ] Add periodic cache metrics logging
- [ ] Add cache stats to Telegram admin reports
- [ ] Monitor hit rates for 24 hours
- [ ] Adjust TTLs based on observed patterns

## Testing

Run sentiment cache tests:
```bash
pytest tests/unit/test_sentiment_cache.py -v
```

All 26 tests should pass.

## Troubleshooting

### Low Hit Rates
If hit rates are low (<30%), check:
- Are token lists changing frequently? (Use consistent ordering in hash)
- Are TTLs too short? (Increase for less volatile data)
- Is invalidation too aggressive? (Only invalidate on significant changes)

### Stale Data
If data seems stale:
- Check TTL values are appropriate for data volatility
- Ensure invalidation triggers on significant events
- Consider lowering TTL for highly volatile data

### High Memory Usage
If cache grows too large:
- MultiLevelCache has LRU eviction (10,000 items by default)
- Reduce max_memory_items in config
- Check for cache key leaks (unbounded keys)
