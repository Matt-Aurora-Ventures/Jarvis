# JARVIS - System Architecture

**Last Updated:** 2026-01-26
**Version:** V1.0 Production
**Status:** Production Ready

---

## Table of Contents

1. [System Overview](#system-overview)
2. [High-Level Architecture](#high-level-architecture)
3. [Component Details](#component-details)
4. [Data Flow](#data-flow)
5. [Infrastructure](#infrastructure)
6. [Deployment Architecture](#deployment-architecture)
7. [Scalability & Performance](#scalability--performance)

---

## System Overview

JARVIS is an autonomous trading assistant built on a microservices-inspired architecture with the following design principles:

- **Resilience First:** Circuit breakers, failover, retry logic
- **Explainability:** Full reasoning chains for AI decisions
- **Modularity:** Loosely coupled components
- **Observability:** Comprehensive logging, metrics, tracing
- **Security:** Defense in depth with multiple layers

---

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         USER INTERFACES                          │
├──────────────┬───────────────┬──────────────┬───────────────────┤
│   Telegram   │   Web Demo    │  Twitter/X   │  Voice (STT/TTS) │
│     Bot      │   Frontend    │     Bot      │                   │
└──────┬───────┴───────┬───────┴──────┬───────┴─────────┬─────────┘
       │               │              │                 │
       └───────────────┴──────────────┴─────────────────┘
                              │
┌─────────────────────────────▼─────────────────────────────────┐
│                     API LAYER (FastAPI)                        │
├────────────────────────────────────────────────────────────────┤
│  • Authentication & Authorization                              │
│  • Rate Limiting (Redis)                                       │
│  • Request Validation                                          │
│  • Circuit Breakers                                            │
└────────────────────────────┬───────────────────────────────────┘
                             │
┌────────────────────────────▼───────────────────────────────────┐
│                    BUSINESS LOGIC LAYER                        │
├──────────────┬──────────────┬──────────────┬──────────────────┤
│   Trading    │  Sentiment   │   Risk Mgmt  │   AI Decision    │
│   Engine     │   Analysis   │   Engine     │   Engine         │
│              │              │              │   (Bull/Bear)    │
└──────┬───────┴──────┬───────┴──────┬───────┴────────┬─────────┘
       │              │              │                │
┌──────▼──────────────▼──────────────▼────────────────▼─────────┐
│                   EXECUTION LAYER                              │
├──────────────┬──────────────┬──────────────┬──────────────────┤
│   Jupiter    │   bags.fm    │  TWAP/VWAP   │   Order Router   │
│   Client     │   Client     │  Algorithms  │                  │
└──────┬───────┴──────┬───────┴──────┬───────┴──────────┬───────┘
       │              │              │                  │
┌──────▼──────────────▼──────────────▼──────────────────▼───────┐
│                   SOLANA INFRASTRUCTURE                        │
├──────────────┬──────────────┬──────────────┬──────────────────┤
│   RPC Pool   │   Geyser     │  Priority    │   Transaction    │
│  (Failover)  │  Streaming   │  Fees        │   Simulator      │
└──────┬───────┴──────┬───────┴──────┬───────┴──────────┬───────┘
       │              │              │                  │
┌──────▼──────────────▼──────────────▼──────────────────▼───────┐
│                      DATA LAYER                                │
├──────────────┬──────────────┬──────────────┬──────────────────┤
│  PostgreSQL  │  TimescaleDB │    Redis     │   File Storage   │
│   (Core)     │ (Analytics)  │   (Cache)    │   (Backups)      │
└──────────────┴──────────────┴──────────────┴──────────────────┘
```

---

## Component Details

### 1. User Interfaces

#### Telegram Bot (`tg_bot/`)
- **Purpose:** Primary user interface
- **Framework:** python-telegram-bot
- **Features:**
  - FSM-based conversation flows
  - Inline keyboards for trade confirmation
  - Voice message support (Whisper STT)
  - Real-time position updates
  - Admin-only commands

**Key Files:**
- `tg_bot/bot.py` - Main bot initialization
- `tg_bot/handlers/` - Command handlers
- `tg_bot/fsm/` - Finite State Machine
- `tg_bot/handlers/voice.py` - Voice interface

#### Web Demo (`web_demo/`)
- **Purpose:** Web-based trading interface
- **Stack:** React + FastAPI
- **Features:**
  - Live position tracking
  - Chart integration
  - One-click trading
  - Portfolio analytics

#### Twitter/X Bot (`bots/twitter/`)
- **Purpose:** Social sentiment and autonomous posting
- **Features:**
  - Market updates via Grok AI
  - Sentiment-driven tweets
  - CLI command execution (admin only)
  - Circuit breaker (anti-spam)

---

### 2. API Layer (`api/`)

**Framework:** FastAPI
**Port:** 8000 (default)

**Middleware Stack:**
```python
FastAPI Application
  ├─ CORS Middleware
  ├─ Rate Limiting Middleware (Redis)
  ├─ Authentication Middleware (JWT)
  ├─ Request Validation (Pydantic)
  ├─ Error Handling Middleware
  └─ Logging Middleware
```

**Key Endpoints:**
```
POST   /api/v1/trade/buy          - Execute buy order
POST   /api/v1/trade/sell         - Execute sell order
GET    /api/v1/positions          - Get open positions
GET    /api/v1/portfolio          - Get portfolio summary
POST   /api/v1/analyze            - Run sentiment analysis
GET    /api/v1/health             - Health check
```

**Rate Limits:**
```
Global: 100 req/min
Per-user: 10 req/min
Per-endpoint: Varies (trading: 5/min, analytics: 20/min)
```

---

### 3. Business Logic Layer

#### Trading Engine (`bots/treasury/trading.py`)

**Responsibilities:**
- Trade execution orchestration
- Position management
- PnL tracking
- Audit logging

**Flow:**
```
User Command → Validation → Risk Check → Execution → Position Update → Notification
```

**Key Classes:**
```python
class TreasuryTrader:
    def __init__(self, wallet, jupiter_client, bags_client):
        self.wallet = wallet
        self.jupiter = jupiter_client
        self.bags = bags_client
        self.risk_mgr = RiskManager()
        self.positions = PositionManager()

    async def execute_buy(self, token, amount_usd, tp_pct, sl_pct):
        # 1. Pre-trade checks
        await self.risk_mgr.validate_trade(amount_usd)

        # 2. Execute via bags.fm (or Jupiter fallback)
        result = await self.bags.buy(token, amount_usd)

        # 3. Open position with TP/SL
        position = await self.positions.open(
            token=token,
            amount=result.amount,
            entry_price=result.price,
            tp_pct=tp_pct,
            sl_pct=sl_pct
        )

        # 4. Start monitoring
        await self.exit_monitor.start_monitoring(position.id)

        return position
```

#### Sentiment Analysis (`bots/buy_tracker/sentiment_report.py`)

**Data Sources:**
- Grok AI (primary)
- EODHD Sentiment API
- Reddit sentiment (planned)
- Twitter sentiment (planned)

**Scoring Algorithm:**
```python
def compute_sentiment(sources: List[SentimentSource]) -> float:
    """
    Weighted average of sentiment sources.

    Weights:
    - Grok AI: 50% (most comprehensive)
    - EODHD: 30% (financial focus)
    - Social: 20% (retail sentiment)
    """
    weighted_sum = sum(s.score * s.weight for s in sources)
    total_weight = sum(s.weight for s in sources)
    return weighted_sum / total_weight
```

#### Risk Management Engine (`core/treasury/risk.py`)

**Rules:**
- Max position size: $500 USD
- Max daily loss: $1000 USD
- Max open positions: 50
- Mandatory TP/SL on every trade
- Correlation limits (max 5 correlated positions)

**Position Sizing:**
```python
def calculate_position_size(
    available_capital: float,
    risk_per_trade: float,  # 2% default
    stop_loss_pct: float
) -> float:
    """
    Kelly Criterion-inspired position sizing.
    """
    max_loss = available_capital * (risk_per_trade / 100)
    position_size = max_loss / (stop_loss_pct / 100)
    return min(position_size, 500.0)  # Cap at $500
```

#### AI Decision Engine (`core/ai/debate_orchestrator.py`)

**Architecture:**
```
                    ┌─────────────┐
                    │   Signal    │
                    │  (BUY SOL)  │
                    └──────┬──────┘
                           │
                  ┌────────▼────────┐
                  │  Bull Persona   │◄───── Market Data
                  │   (Grok API)    │
                  └────────┬────────┘
                           │
                    Bull Analysis
                    "Strong uptrend,
                     high volume"
                           │
                  ┌────────▼────────┐
                  │   Synthesizer   │◄───── Bear Analysis
                  │                 │       "Overbought,
                  └────────┬────────┘        pullback risk"
                           │
                    ┌──────▼──────┐
                    │ Trade       │
                    │ Decision    │
                    │ (BUY, 72%)  │
                    └─────────────┘
```

**Cost Control:**
```python
DEBATE_COST_LIMITS = {
    "per_debate": 0.50,      # $0.50 max per debate
    "daily_total": 10.0,     # $10 daily limit
    "emergency_stop": 50.0   # $50 hard limit (kill switch)
}
```

---

### 4. Execution Layer

#### Jupiter Client (`core/clients/jupiter.py`)

**Capabilities:**
- Token swaps via Jupiter Aggregator
- Slippage configuration
- Priority fee integration
- Transaction simulation
- Retry logic with exponential backoff

**Usage:**
```python
from core.clients.jupiter import JupiterClient

client = JupiterClient(wallet, rpc_client)

# Get quote
quote = await client.get_quote(
    input_mint="SOL",
    output_mint="USDC",
    amount=1_000_000_000,  # 1 SOL (lamports)
    slippage_bps=100       # 1% slippage
)

# Execute swap
tx_signature = await client.execute_swap(quote, priority_fee_lamports=1000)
```

#### bags.fm Client (`core/treasury/bags_integration.py`)

**Advantages over Jupiter:**
- Lower fees (0.1% vs 0.25%)
- Direct access to bags.fm liquidity
- Graduation monitoring
- Early token discovery

**Fallback Logic:**
```python
async def execute_trade(token, amount):
    try:
        # Try bags.fm first
        result = await bags_client.buy(token, amount)
    except BagsAPIError as e:
        logger.warning(f"bags.fm failed: {e}, falling back to Jupiter")
        result = await jupiter_client.buy(token, amount)
    return result
```

#### TWAP/VWAP Algorithms (`core/execution/algorithms.py`)

**Algorithm Selection:**
```python
def select_algorithm(order_size_usd: float, pool_liquidity_usd: float) -> str:
    impact_pct = (order_size_usd / pool_liquidity_usd) * 100

    if impact_pct < 1.0:
        return "MARKET"       # Single order
    elif impact_pct < 5.0:
        return "TWAP"         # 5 slices
    elif impact_pct < 10.0:
        return "VWAP"         # 10 slices
    else:
        return "ICEBERG"      # 20+ slices
```

---

### 5. Solana Infrastructure

#### RPC Pool with Failover (`core/solana/rpc_health.py`)

**Provider Tiers:**
```
Tier 1 (Primary):
  - Helius (mainnet-beta)
  - QuickNode

Tier 2 (Secondary):
  - Alchemy
  - Triton

Tier 3 (Fallback):
  - Public RPC (https://api.mainnet-beta.solana.com)
```

**Health Metrics:**
```python
@dataclass
class ProviderHealth:
    name: str
    endpoint: str
    latency_ms: float
    success_rate: float  # 0.0-1.0
    last_error: Optional[str]
    is_healthy: bool

    def calculate_score(self) -> float:
        """
        Combined score for provider selection.
        Lower is better.
        """
        return (latency_ms * 0.3) + ((1 - success_rate) * 1000)
```

**Failover Algorithm:**
```python
async def get_rpc_client(self) -> AsyncClient:
    """
    Get best available RPC client.
    """
    healthy_providers = [
        p for p in self.providers if p.is_healthy
    ]

    if not healthy_providers:
        logger.error("No healthy RPC providers!")
        return self.fallback_client

    # Sort by score (lower = better)
    best = min(healthy_providers, key=lambda p: p.calculate_score())
    return best.client
```

#### Geyser Streaming (`core/streaming/geyser_client.py`)

**Connection:**
```
Client → gRPC → Yellowstone Geyser Plugin → Solana Validator
```

**Subscription Types:**
```python
# Account subscription
await geyser.subscribe_accounts([
    "TokenProgramId...",
    "JupiterProgramId..."
])

# Program subscription (all accounts owned by program)
await geyser.subscribe_program("RaydiumProgramId...")

# Slot subscription (block updates)
await geyser.subscribe_slots()
```

**Update Handler:**
```python
async def handle_geyser_update(update: AccountUpdate):
    """
    Process real-time account updates.
    """
    if update.account.owner == JUPITER_PROGRAM_ID:
        # Price feed update
        await price_cache.update(update.account.pubkey, update.account.data)
    elif update.account.owner == RAYDIUM_PROGRAM_ID:
        # Liquidity pool update
        await liquidity_monitor.process(update.account.data)
```

#### Priority Fee Estimation (`core/solana/priority_fees.py`)

**Helius API Integration:**
```python
async def get_priority_fee(urgency: float = 0.5) -> Tuple[int, str]:
    """
    Get recommended priority fee based on network congestion.

    Args:
        urgency: 0.0 (low) to 1.0 (ultra high)

    Returns:
        (fee_lamports, tier_name)
    """
    fees = await helius_client.get_recent_priority_fees()

    if urgency < 0.3:
        return fees.p25, "LOW"      # 25th percentile
    elif urgency < 0.6:
        return fees.p50, "MEDIUM"   # 50th percentile
    elif urgency < 0.9:
        return fees.p75, "HIGH"     # 75th percentile
    else:
        return fees.p95, "ULTRA"    # 95th percentile
```

---

### 6. Data Layer

#### PostgreSQL (Core Database)

**Schema:** `jarvis_core.db`

**Tables:**
```sql
-- Users
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    telegram_id BIGINT UNIQUE NOT NULL,
    wallet_address VARCHAR(44),
    created_at TIMESTAMP DEFAULT NOW(),
    is_admin BOOLEAN DEFAULT FALSE
);

-- Positions
CREATE TABLE positions (
    id UUID PRIMARY KEY,
    user_id INT REFERENCES users(id),
    token_mint VARCHAR(44) NOT NULL,
    amount NUMERIC(20, 9),
    entry_price NUMERIC(20, 9),
    stop_loss_pct NUMERIC(5, 2),
    take_profit_pct NUMERIC(5, 2),
    status VARCHAR(20),  -- OPEN, CLOSED, STOPPED_OUT
    opened_at TIMESTAMP DEFAULT NOW(),
    closed_at TIMESTAMP
);

-- Trades
CREATE TABLE trades (
    id UUID PRIMARY KEY,
    position_id UUID REFERENCES positions(id),
    side VARCHAR(4),  -- BUY, SELL
    amount NUMERIC(20, 9),
    price NUMERIC(20, 9),
    fee_usd NUMERIC(10, 2),
    signature VARCHAR(88),
    executed_at TIMESTAMP DEFAULT NOW()
);

-- Audit Log
CREATE TABLE audit_log (
    id SERIAL PRIMARY KEY,
    user_id INT,
    action VARCHAR(50),
    details JSONB,
    ip_address INET,
    timestamp TIMESTAMP DEFAULT NOW()
);
```

#### TimescaleDB (Analytics)

**Hypertables:**
```sql
-- Performance metrics (1-day chunks)
CREATE TABLE performance_metrics (
    time TIMESTAMPTZ NOT NULL,
    metric_name VARCHAR(50),
    value NUMERIC,
    labels JSONB
);

SELECT create_hypertable('performance_metrics', 'time', chunk_time_interval => INTERVAL '1 day');

-- Token prices (1-hour chunks)
CREATE TABLE token_prices (
    time TIMESTAMPTZ NOT NULL,
    token_mint VARCHAR(44),
    price_usd NUMERIC(20, 9),
    volume_24h NUMERIC(20, 2),
    liquidity_usd NUMERIC(20, 2)
);

SELECT create_hypertable('token_prices', 'time', chunk_time_interval => INTERVAL '1 hour');

-- Sentiment scores (1-hour chunks)
CREATE TABLE sentiment_scores (
    time TIMESTAMPTZ NOT NULL,
    token_symbol VARCHAR(10),
    sentiment_score NUMERIC(5, 2),
    source VARCHAR(20),
    confidence NUMERIC(5, 2)
);

SELECT create_hypertable('sentiment_scores', 'time', chunk_time_interval => INTERVAL '1 hour');
```

**Compression Policy:**
```sql
-- Compress data older than 7 days
SELECT add_compression_policy('performance_metrics', INTERVAL '7 days');
SELECT add_compression_policy('token_prices', INTERVAL '7 days');
SELECT add_compression_policy('sentiment_scores', INTERVAL '7 days');
```

#### Redis (Cache + Sessions)

**Key Patterns:**
```
# Price cache
price:<token_mint> → {"price": 100.0, "timestamp": 1706234400}
TTL: 5 seconds

# Session state
session:<user_id>:state → "AWAITING_AMOUNT"
session:<user_id>:data → {"token": "SOL", "amount": null}
TTL: 3600 seconds (1 hour)

# Rate limit buckets
rate_limit:user:<user_id>:<endpoint> → <tokens_remaining>
TTL: 60 seconds

# Circuit breaker state
circuit:<service_name> → {"state": "OPEN", "failures": 5}
TTL: 300 seconds (5 minutes)
```

**Connection Pool:**
```python
REDIS_CONFIG = {
    "host": "localhost",
    "port": 6379,
    "db": 0,
    "max_connections": 50,
    "socket_keepalive": True,
    "socket_connect_timeout": 5,
    "retry_on_timeout": True
}
```

---

## Data Flow

### Trade Execution Flow

```
┌─────────────────────────────────────────────────────────────────┐
│ 1. USER INPUT                                                   │
│    Telegram: "/buy SOL 100"                                     │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│ 2. COMMAND PARSING                                              │
│    Parse: {"action": "buy", "token": "SOL", "amount": 100}     │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│ 3. VALIDATION                                                   │
│    • User authentication                                        │
│    • Rate limit check (Redis)                                   │
│    • Input sanitization                                         │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│ 4. RISK CHECKS                                                  │
│    • Max position size: $500                                    │
│    • Daily loss limit: $1000                                    │
│    • Open position count: <50                                   │
│    • Balance check                                              │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│ 5. AI DECISION (Optional)                                       │
│    • Bull/Bear debate                                           │
│    • Sentiment analysis                                         │
│    • Confidence score                                           │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│ 6. EXECUTION                                                    │
│    Try bags.fm → Fallback to Jupiter → Simulation → Send TX    │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│ 7. POSITION MANAGEMENT                                          │
│    • Create position record (PostgreSQL)                        │
│    • Set TP/SL monitors                                         │
│    • Start exit monitoring (1-second interval)                  │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│ 8. NOTIFICATION                                                 │
│    • Send Telegram confirmation                                 │
│    • Log to audit trail                                         │
│    • Update portfolio cache (Redis)                             │
└─────────────────────────────────────────────────────────────────┘
```

---

## Infrastructure

### Deployment Stack

```
Production Environment:
  - OS: Ubuntu 22.04 LTS
  - Python: 3.11+
  - PostgreSQL: 15 + TimescaleDB 2.13
  - Redis: 7.2
  - Supervisor: Process manager
  - Nginx: Reverse proxy (optional)
```

### Process Supervision

**Supervisor Configuration:**
```ini
[program:jarvis-telegram]
command=/path/to/venv/bin/python bots/supervisor.py
directory=/path/to/jarvis
user=jarvis
autostart=true
autorestart=true
startsecs=10
stopwaitsecs=60
stdout_logfile=/var/log/jarvis/telegram.log
stderr_logfile=/var/log/jarvis/telegram.err

[program:jarvis-api]
command=/path/to/venv/bin/uvicorn api.main:app --host 0.0.0.0 --port 8000
directory=/path/to/jarvis
user=jarvis
autostart=true
autorestart=true
stdout_logfile=/var/log/jarvis/api.log
```

### Monitoring

**Health Checks:**
```python
@app.get("/health")
async def health_check():
    """
    Comprehensive health check endpoint.
    """
    checks = {
        "database": await check_postgres(),
        "redis": await check_redis(),
        "rpc": await check_rpc_providers(),
        "geyser": await check_geyser_connection(),
    }

    all_healthy = all(checks.values())
    status_code = 200 if all_healthy else 503

    return JSONResponse(
        content={"status": "healthy" if all_healthy else "unhealthy", "checks": checks},
        status_code=status_code
    )
```

**Prometheus Metrics:**
```python
# Custom metrics
trade_counter = Counter('jarvis_trades_total', 'Total trades executed', ['side', 'token'])
trade_latency = Histogram('jarvis_trade_latency_seconds', 'Trade execution latency')
position_gauge = Gauge('jarvis_open_positions', 'Number of open positions')
```

---

## Scalability & Performance

### Horizontal Scaling

**Bot Instances:**
- Multiple Telegram bot instances (load balanced)
- Shared Redis for coordination
- No state in memory (stateless design)

**API Scaling:**
```
User → Load Balancer → API Instance 1
                     → API Instance 2
                     → API Instance 3
```

### Performance Characteristics

| Component | Latency (p95) | Throughput |
|-----------|---------------|------------|
| API endpoints | 20ms | 1000 req/s |
| Trade execution | 2-5s | 10 trades/s |
| Database queries | 20ms | 5000 qps |
| Redis operations | 1ms | 50,000 ops/s |
| RPC calls | 100ms | 100 req/s |
| Geyser updates | <10ms | 10,000 msg/s |

### Optimization Techniques

1. **Database:**
   - Connection pooling (10-50 connections)
   - Prepared statements
   - Index optimization
   - Query caching (Redis)

2. **API:**
   - HTTP session reuse
   - Response compression
   - Async I/O everywhere
   - Connection keepalive

3. **Caching:**
   - Price cache (5s TTL)
   - User session cache (1h TTL)
   - Query result cache (60s TTL)

---

## Security Architecture

### Defense in Depth

```
Layer 1: Network
  - Firewall (UFW)
  - Rate limiting (nginx)
  - DDoS protection

Layer 2: Application
  - Input validation
  - Rate limiting (Redis)
  - CSRF protection
  - Authentication (JWT)

Layer 3: Data
  - Encrypted at rest (database)
  - Encrypted in transit (TLS)
  - Secret vault (core/security/vault.py)
  - Audit logging

Layer 4: Infrastructure
  - Principle of least privilege
  - Secrets in environment (not code)
  - Regular security audits
  - Dependency scanning
```

---

## Disaster Recovery

### Backup Strategy

**Database Backups:**
```bash
# Automated daily backups
0 2 * * * pg_dump jarvis_core | gzip > /backups/jarvis_core_$(date +\%Y\%m\%d).sql.gz

# Keep 30 days of backups
find /backups -name "jarvis_core_*.sql.gz" -mtime +30 -delete
```

**Recovery Time Objectives:**
- RTO (Recovery Time Objective): 1 hour
- RPO (Recovery Point Objective): 24 hours (daily backups)

---

## Future Architecture Improvements

1. **Message Queue (RabbitMQ/Redis Streams):**
   - Decouple trade execution from API
   - Better handling of high-volume periods

2. **Kubernetes Deployment:**
   - Auto-scaling based on load
   - Rolling deployments
   - Better resource isolation

3. **Distributed Tracing (Jaeger):**
   - End-to-end request tracing
   - Performance bottleneck identification

4. **GraphQL API:**
   - More flexible querying
   - Reduced over-fetching

---

**Related Documentation:**
- [Features Overview](./FEATURES.md)
- [API Improvements](./API_IMPROVEMENTS.md)
- [Deployment Guide](./DEPLOYMENT.md)
