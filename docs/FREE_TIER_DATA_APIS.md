# Free-Tier APIs & Infrastructure for JARVIS

> Context Document for Financial Data Integration
> Added: 2026-01-12

## Overview

This document catalogs free-tier APIs and open-source infrastructure for financial pricing and sentiment analysis. These tools enable JARVIS to deliver real-time insights without institutional-level investment.

---

## 1. Architecture Blueprint

A modular, layered framework for reliable data flow:

| Layer | Purpose | Components |
|-------|---------|------------|
| **Symbology** | Standardize instrument identification | OpenFIGI |
| **Data Acquisition** | Fetch pricing & sentiment data | Twelve Data, EODHD, DexScreener |
| **Integration** | Consolidate streams, manage API calls | OpenBB platform |
| **Application** | User-facing bots | Telegram, X/Twitter |

---

## 2. Financial Pricing APIs

### 2.1 Twelve Data API ⭐ RECOMMENDED
**Free Tier: "Basic" Plan**

| Feature | Details |
|---------|---------|
| Assets | Stocks (US/Global), Forex, ETFs, Crypto, Commodities |
| Endpoints | Time series (OHLCV), Quote, Latest price |
| WebSocket | ✅ Real-time streaming (8 symbols, 1 connection) |
| Indicators | 100+ built-in (SMA, EMA, MACD, RSI, etc.) |
| Fundamentals | Profile, Statistics, Dividends, Splits |
| Rate Limit | ~8 requests/minute on free tier |

**Integration Example:**
```python
TWELVE_DATA_API = "https://api.twelvedata.com"

async def get_price(symbol: str, api_key: str) -> dict:
    url = f"{TWELVE_DATA_API}/quote?symbol={symbol}&apikey={api_key}"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            return await resp.json()
```

### 2.2 EODHD (EOD Historical Data)
**Free Tier: Limited requests/day**

| Feature | Details |
|---------|---------|
| Assets | Stocks, ETFs, Forex, Crypto |
| Unique Value | News, Sentiment, Word Weights endpoints |
| WebSocket | ✅ Real-time for US Stocks |

**Sentiment Endpoint (JARVIS Priority):**
```
GET /sentiments?s={symbol}
Returns: Normalized score -1 to 1
```

### 2.3 Alpha Vantage
**Free Tier: 25 requests/day (Limited)**

| Feature | Details |
|---------|---------|
| Assets | Stocks, Forex, Crypto, Commodities |
| Fundamentals | Earnings, Income statements, Balance sheets |
| Indicators | Built-in technical indicators |

**Note:** Rate limit too restrictive for production. Use as backup only.

### 2.4 CoinGecko (Crypto)
**Free Tier: Generous limits**

| Feature | Details |
|---------|---------|
| Assets | 10,000+ cryptocurrencies |
| Data | Price, volume, market cap, 24h change |
| No API Key | Public endpoints available |
| Rate Limit | ~50 requests/minute |

**Already integrated in JARVIS:** `core/data_sources/commodity_prices.py`

---

## 3. Sentiment & News APIs

### 3.1 EODHD Sentiment Endpoints ⭐ RECOMMENDED

| Endpoint | Purpose |
|----------|---------|
| `/sentiments` | Pre-calculated sentiment score (-1 to +1) |
| `/news` | Financial news headlines + articles |
| `/news-word-weights` | Weighted keywords for thematic analysis |

### 3.2 Stocktwits (Retail Sentiment)
**Free Tier: API access available**

- Exclusive finance-focused social platform
- Cashtag analysis ($AAPL, $BTC, etc.)
- Volume of posts = sentiment intensity

### 3.3 Reddit API
**Free Tier: OAuth 2.0 access**

- Register app at reddit.com/prefs/apps
- Get client_id and client_secret
- Access r/wallstreetbets, r/cryptocurrency, r/stocks

---

## 4. Symbology: OpenFIGI

**Purpose:** Standardize financial instrument identification across data sources.

**Why It Matters:**
- Same security may have different tickers across providers
- FIGI creates universal mapping
- Ensures data integrity when fusing sources

**Integration:**
```python
OPENFIGI_API = "https://api.openfigi.com/v3/mapping"

async def get_figi(ticker: str) -> str:
    payload = [{"idType": "TICKER", "idValue": ticker}]
    async with aiohttp.ClientSession() as session:
        async with session.post(OPENFIGI_API, json=payload) as resp:
            data = await resp.json()
            return data[0]["data"][0]["figi"]
```

---

## 5. Integration Platform: OpenBB

**What:** Open-source "connect once, consume everywhere" data platform

**Value:**
- Abstracts data provider complexity
- Easy to swap providers without code changes
- Reduces vendor lock-in
- GitHub: github.com/OpenBB-finance/OpenBB

---

## 6. JARVIS Integration Status

### Currently Integrated:
| Source | Status | File |
|--------|--------|------|
| CoinGecko | ✅ Active | `core/data_sources/commodity_prices.py` |
| DexScreener | ✅ Active | `bots/buy_tracker/monitor.py` |
| Jupiter Price API | ✅ Active | `bots/treasury/jupiter.py` |
| Birdeye | ✅ Active | `tg_bot/services/signal_service.py` |
| Grok (xAI) | ✅ Active | `bots/buy_tracker/sentiment_report.py` |

### Recommended Additions:
| Source | Priority | Use Case |
|--------|----------|----------|
| Twelve Data | HIGH | Traditional markets, WebSocket streaming |
| EODHD Sentiment | HIGH | Pre-calculated sentiment scores |
| OpenFIGI | MEDIUM | Cross-provider symbol mapping |
| Stocktwits | LOW | Retail sentiment backup |

---

## 7. Rate Limiting Strategy

**Circuit Breaker Pattern (Per Guide):**
```python
class CircuitBreaker:
    def __init__(self, failure_threshold=5, timeout=60):
        self.failure_count = 0
        self.threshold = failure_threshold
        self.timeout = timeout
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
        self.last_failure_time = None

    async def call(self, func, *args):
        if self.state == "OPEN":
            if time.time() - self.last_failure_time > self.timeout:
                self.state = "HALF_OPEN"
            else:
                raise CircuitOpenError("Circuit breaker is open")

        try:
            result = await func(*args)
            if self.state == "HALF_OPEN":
                self.state = "CLOSED"
                self.failure_count = 0
            return result
        except Exception as e:
            self.failure_count += 1
            if self.failure_count >= self.threshold:
                self.state = "OPEN"
                self.last_failure_time = time.time()
            raise
```

---

## 8. Free Tier Limitations

| Provider | Limit | Workaround |
|----------|-------|------------|
| Twelve Data | 8 symbols/WebSocket | Rotate symbols, use REST for others |
| Alpha Vantage | 25 req/day | Use as backup only |
| CoinGecko | 50 req/min | Implement caching |
| EODHD | Varies | Batch requests |

**Data Latency Warning:**
- Free tiers often have 15-minute delay
- Use for end-of-day analysis, not real-time trading
- DexScreener and Birdeye provide faster crypto data

---

## 9. Implementation Priority

### Phase 1: Add Twelve Data (Traditional Markets)
- Add to `core/data_sources/stock_prices.py`
- WebSocket for real-time streaming
- Built-in indicators reduce computation

### Phase 2: Add EODHD Sentiment
- Add to `core/data_sources/sentiment_feeds.py`
- Cross-reference with Grok sentiment
- News keyword analysis

### Phase 3: OpenFIGI Integration
- Add to `core/data_sources/symbology.py`
- Map tickers to universal identifiers
- Ensure data fusion integrity

---

*Document maintained as part of JARVIS development context*
*Last updated: 2026-01-12*
