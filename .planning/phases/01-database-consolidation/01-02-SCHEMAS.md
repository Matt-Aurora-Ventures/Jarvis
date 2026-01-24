# Phase 1 Task 2: Consolidated Database Schemas

**Date**: 2026-01-24
**Status**: Design Complete
**Migration Target**: 29 databases → 3 consolidated databases

---

## Overview

Consolidating 29 SQLite databases into 3 purpose-built databases:

1. **jarvis_core.db** (~600KB) - Operational trading data
2. **jarvis_analytics.db** (~1.2MB) - Analytics, memory, logs
3. **jarvis_cache.db** (~100KB) - Temporary/ephemeral data

**Standalone databases** (kept separate for isolation):
- engagement.db (Twitter metrics)
- jarvis_spam_protection.db (security)
- raid_bot.db (feature-specific)
- achievements.db (community features)

---

## 1. jarvis_core.db - Core Operational Data

**Purpose**: Critical trading operations, positions, orders, configuration
**Expected Size**: ~600KB
**Backup Frequency**: Every 6 hours
**WAL Mode**: Enabled

### Schema DDL

```sql
-- ==================================================
-- jarvis_core.db - Core Operational Database
-- ==================================================

PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;

-- --------------------------------------------------
-- Positions Table (from jarvis.db)
-- --------------------------------------------------
CREATE TABLE positions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    token_address TEXT NOT NULL UNIQUE,
    entry_price REAL NOT NULL,
    current_price REAL,
    amount REAL NOT NULL,
    amount_sol REAL NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('open', 'closed', 'partial')),
    entry_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    exit_time TIMESTAMP,
    pnl_usd REAL DEFAULT 0.0,
    pnl_percent REAL DEFAULT 0.0,
    take_profit_percent REAL,
    stop_loss_percent REAL,
    trailing_stop_enabled INTEGER DEFAULT 0,
    trailing_stop_activation REAL,
    trailing_stop_distance REAL,
    highest_price REAL,
    wallet_address TEXT NOT NULL,
    user_id INTEGER,
    notes TEXT,
    metadata TEXT -- JSON blob for flexibility
);

CREATE INDEX idx_positions_status ON positions(status);
CREATE INDEX idx_positions_token ON positions(token_address);
CREATE INDEX idx_positions_wallet ON positions(wallet_address);
CREATE INDEX idx_positions_user ON positions(user_id);

-- --------------------------------------------------
-- Trades Table (from jarvis.db)
-- --------------------------------------------------
CREATE TABLE trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    position_id INTEGER,
    direction TEXT NOT NULL CHECK(direction IN ('buy', 'sell')),
    symbol TEXT NOT NULL,
    token_address TEXT NOT NULL,
    amount REAL NOT NULL,
    amount_sol REAL NOT NULL,
    price REAL NOT NULL,
    slippage_bps INTEGER,
    signature TEXT UNIQUE,
    status TEXT NOT NULL CHECK(status IN ('pending', 'confirmed', 'failed')),
    via TEXT CHECK(via IN ('bags_fm', 'jupiter', 'manual')),
    fee_sol REAL DEFAULT 0.0,
    partner_fee_sol REAL DEFAULT 0.0,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    confirmation_time TIMESTAMP,
    error_message TEXT,
    metadata TEXT, -- JSON blob
    FOREIGN KEY (position_id) REFERENCES positions(id) ON DELETE SET NULL
);

CREATE INDEX idx_trades_position ON trades(position_id);
CREATE INDEX idx_trades_signature ON trades(signature);
CREATE INDEX idx_trades_timestamp ON trades(timestamp DESC);
CREATE INDEX idx_trades_status ON trades(status);
CREATE INDEX idx_trades_via ON trades(via);

-- --------------------------------------------------
-- Treasury Orders Table (from treasury_trades.db)
-- --------------------------------------------------
CREATE TABLE treasury_orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_type TEXT NOT NULL CHECK(order_type IN ('market', 'limit', 'stop_loss', 'take_profit')),
    side TEXT NOT NULL CHECK(side IN ('buy', 'sell')),
    symbol TEXT NOT NULL,
    token_address TEXT NOT NULL,
    amount_sol REAL NOT NULL,
    limit_price REAL,
    trigger_price REAL,
    status TEXT NOT NULL CHECK(status IN ('pending', 'active', 'filled', 'cancelled', 'expired')),
    position_id INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    filled_at TIMESTAMP,
    filled_price REAL,
    filled_amount REAL,
    fills_count INTEGER DEFAULT 0,
    metadata TEXT, -- JSON blob
    FOREIGN KEY (position_id) REFERENCES positions(id) ON DELETE CASCADE
);

CREATE INDEX idx_treasury_orders_status ON treasury_orders(status);
CREATE INDEX idx_treasury_orders_token ON treasury_orders(token_address);
CREATE INDEX idx_treasury_orders_position ON treasury_orders(position_id);

-- --------------------------------------------------
-- Scorecard Table (from jarvis.db)
-- --------------------------------------------------
CREATE TABLE scorecard (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    total_trades INTEGER DEFAULT 0,
    winning_trades INTEGER DEFAULT 0,
    losing_trades INTEGER DEFAULT 0,
    total_pnl_sol REAL DEFAULT 0.0,
    total_pnl_usd REAL DEFAULT 0.0,
    total_volume_sol REAL DEFAULT 0.0,
    avg_win_percent REAL DEFAULT 0.0,
    avg_loss_percent REAL DEFAULT 0.0,
    win_rate REAL DEFAULT 0.0,
    sharpe_ratio REAL,
    max_drawdown_percent REAL,
    total_fees_paid_sol REAL DEFAULT 0.0,
    total_partner_fees_sol REAL DEFAULT 0.0,
    bags_fm_trade_count INTEGER DEFAULT 0,
    jupiter_trade_count INTEGER DEFAULT 0,
    period TEXT CHECK(period IN ('daily', 'weekly', 'monthly', 'all_time'))
);

CREATE INDEX idx_scorecard_timestamp ON scorecard(timestamp DESC);
CREATE INDEX idx_scorecard_period ON scorecard(period);

-- --------------------------------------------------
-- Tax Lots Table (from tax.db)
-- --------------------------------------------------
CREATE TABLE tax_lots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trade_id INTEGER NOT NULL,
    token_address TEXT NOT NULL,
    symbol TEXT NOT NULL,
    quantity REAL NOT NULL,
    cost_basis_usd REAL NOT NULL,
    acquisition_date TIMESTAMP NOT NULL,
    disposal_date TIMESTAMP,
    disposal_proceeds_usd REAL,
    short_term INTEGER DEFAULT 1,
    wash_sale INTEGER DEFAULT 0,
    FOREIGN KEY (trade_id) REFERENCES trades(id) ON DELETE CASCADE
);

CREATE INDEX idx_tax_lots_token ON tax_lots(token_address);
CREATE INDEX idx_tax_lots_acquisition ON tax_lots(acquisition_date);

-- --------------------------------------------------
-- Wash Sales Table (from tax.db)
-- --------------------------------------------------
CREATE TABLE wash_sales (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sold_lot_id INTEGER NOT NULL,
    replacement_lot_id INTEGER NOT NULL,
    disallowed_loss_usd REAL NOT NULL,
    wash_sale_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (sold_lot_id) REFERENCES tax_lots(id),
    FOREIGN KEY (replacement_lot_id) REFERENCES tax_lots(id)
);

-- --------------------------------------------------
-- Configuration Table
-- --------------------------------------------------
CREATE TABLE config (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    description TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Insert default config
INSERT INTO config (key, value, description) VALUES
    ('max_positions', '50', 'Maximum concurrent positions'),
    ('default_tp_percent', '50.0', 'Default take-profit percentage'),
    ('default_sl_percent', '20.0', 'Default stop-loss percentage'),
    ('max_trade_usd', '1000.0', 'Maximum single trade size USD'),
    ('max_daily_usd', '5000.0', 'Maximum daily trading volume USD'),
    ('use_bags_fm', 'true', 'Primary router: bags.fm or Jupiter'),
    ('slippage_bps', '100', 'Default slippage basis points (1%)');
```

---

## 2. jarvis_analytics.db - Analytics & Memory

**Purpose**: Analytics, AI memory, logs, sentiment, metrics
**Expected Size**: ~1.2MB
**Backup Frequency**: Daily
**WAL Mode**: Enabled

### Schema DDL

```sql
-- ==================================================
-- jarvis_analytics.db - Analytics & Memory Database
-- ==================================================

PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;

-- --------------------------------------------------
-- Telegram Messages (from telegram_memory.db)
-- --------------------------------------------------
CREATE TABLE telegram_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    username TEXT,
    message TEXT NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    message_type TEXT CHECK(message_type IN ('command', 'query', 'response', 'notification')),
    context TEXT -- JSON blob for conversation context
);

CREATE INDEX idx_telegram_messages_user ON telegram_messages(user_id);
CREATE INDEX idx_telegram_messages_timestamp ON telegram_messages(timestamp DESC);

-- --------------------------------------------------
-- Telegram Users (from jarvis_admin.db)
-- --------------------------------------------------
CREATE TABLE telegram_users (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    first_name TEXT,
    last_name TEXT,
    is_admin INTEGER DEFAULT 0,
    is_banned INTEGER DEFAULT 0,
    first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    message_count INTEGER DEFAULT 0,
    preferences TEXT -- JSON blob
);

CREATE INDEX idx_telegram_users_admin ON telegram_users(is_admin);
CREATE INDEX idx_telegram_users_last_seen ON telegram_users(last_seen DESC);

-- --------------------------------------------------
-- Twitter/X Tweets (from jarvis_x_memory.db)
-- --------------------------------------------------
CREATE TABLE tweets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tweet_id TEXT UNIQUE,
    content TEXT NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    likes INTEGER DEFAULT 0,
    retweets INTEGER DEFAULT 0,
    replies INTEGER DEFAULT 0,
    impressions INTEGER DEFAULT 0,
    url TEXT,
    metadata TEXT -- JSON blob
);

CREATE INDEX idx_tweets_timestamp ON tweets(timestamp DESC);
CREATE INDEX idx_tweets_tweet_id ON tweets(tweet_id);

-- --------------------------------------------------
-- AI Memory - Entities (from jarvis_memory.db)
-- --------------------------------------------------
CREATE TABLE ai_entities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_type TEXT NOT NULL,
    name TEXT NOT NULL UNIQUE,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_referenced TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    reference_count INTEGER DEFAULT 1
);

CREATE INDEX idx_ai_entities_type ON ai_entities(entity_type);
CREATE INDEX idx_ai_entities_last_referenced ON ai_entities(last_referenced DESC);

-- --------------------------------------------------
-- AI Memory - Facts (from jarvis_memory.db)
-- --------------------------------------------------
CREATE TABLE ai_facts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_id INTEGER,
    fact TEXT NOT NULL,
    confidence REAL DEFAULT 1.0,
    source TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active INTEGER DEFAULT 1,
    FOREIGN KEY (entity_id) REFERENCES ai_entities(id) ON DELETE CASCADE
);

CREATE INDEX idx_ai_facts_entity ON ai_facts(entity_id);
CREATE INDEX idx_ai_facts_active ON ai_facts(is_active);

-- --------------------------------------------------
-- AI Memory - Reflections (from jarvis_memory.db)
-- Virtual FTS5 table for semantic search
-- --------------------------------------------------
CREATE VIRTUAL TABLE ai_reflections USING fts5(
    content,
    timestamp,
    tags,
    tokenize = 'porter unicode61'
);

-- --------------------------------------------------
-- Sentiment Readings (from sentiment.db)
-- --------------------------------------------------
CREATE TABLE sentiment_readings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    token_address TEXT NOT NULL,
    score REAL NOT NULL CHECK(score >= 0.0 AND score <= 100.0),
    sentiment TEXT CHECK(sentiment IN ('bullish', 'bearish', 'neutral')),
    confidence REAL,
    source TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metadata TEXT -- JSON: grok response, twitter mentions, etc.
);

CREATE INDEX idx_sentiment_symbol ON sentiment_readings(symbol);
CREATE INDEX idx_sentiment_timestamp ON sentiment_readings(timestamp DESC);

-- --------------------------------------------------
-- Call Tracking (from call_tracking.db)
-- --------------------------------------------------
CREATE TABLE calls (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    token_address TEXT NOT NULL,
    call_type TEXT CHECK(call_type IN ('buy', 'sell', 'hold')),
    entry_price REAL,
    target_price REAL,
    stop_loss_price REAL,
    reasoning TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    caller TEXT,
    metadata TEXT
);

CREATE TABLE call_outcomes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    call_id INTEGER NOT NULL,
    outcome TEXT CHECK(outcome IN ('win', 'loss', 'break_even', 'pending')),
    pnl_percent REAL,
    closed_at TIMESTAMP,
    notes TEXT,
    FOREIGN KEY (call_id) REFERENCES calls(id) ON DELETE CASCADE
);

CREATE INDEX idx_calls_timestamp ON calls(timestamp DESC);
CREATE INDEX idx_call_outcomes_call ON call_outcomes(call_id);

-- --------------------------------------------------
-- Whale Tracking (from whales.db)
-- --------------------------------------------------
CREATE TABLE whale_wallets (
    address TEXT PRIMARY KEY,
    label TEXT,
    total_sol_moved REAL DEFAULT 0.0,
    first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active INTEGER DEFAULT 1
);

CREATE TABLE whale_movements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    wallet_address TEXT NOT NULL,
    token_address TEXT NOT NULL,
    token_symbol TEXT,
    amount_sol REAL NOT NULL,
    direction TEXT CHECK(direction IN ('in', 'out')),
    signature TEXT UNIQUE,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (wallet_address) REFERENCES whale_wallets(address) ON DELETE CASCADE
);

CREATE INDEX idx_whale_movements_wallet ON whale_movements(wallet_address);
CREATE INDEX idx_whale_movements_timestamp ON whale_movements(timestamp DESC);

-- --------------------------------------------------
-- Metrics (from metrics.db)
-- --------------------------------------------------
CREATE TABLE metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    metric_name TEXT NOT NULL,
    metric_value REAL NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    tags TEXT, -- JSON blob for flexible tagging
    metadata TEXT
);

CREATE INDEX idx_metrics_name ON metrics(metric_name);
CREATE INDEX idx_metrics_timestamp ON metrics(timestamp DESC);

-- --------------------------------------------------
-- LLM Costs (from llm_costs.db)
-- --------------------------------------------------
CREATE TABLE llm_costs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    provider TEXT NOT NULL CHECK(provider IN ('anthropic', 'xai', 'openai', 'other')),
    model TEXT NOT NULL,
    input_tokens INTEGER DEFAULT 0,
    output_tokens INTEGER DEFAULT 0,
    cost_usd REAL NOT NULL,
    purpose TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metadata TEXT
);

CREATE INDEX idx_llm_costs_provider ON llm_costs(provider);
CREATE INDEX idx_llm_costs_timestamp ON llm_costs(timestamp DESC);
```

---

## 3. jarvis_cache.db - Temporary/Ephemeral Data

**Purpose**: Cache, rate limiting, sessions
**Expected Size**: ~100KB
**Backup Frequency**: Optional (can be rebuilt)
**WAL Mode**: Enabled

### Schema DDL

```sql
-- ==================================================
-- jarvis_cache.db - Temporary/Ephemeral Database
-- ==================================================

PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;

-- --------------------------------------------------
-- Cache Entries (generic key-value cache)
-- --------------------------------------------------
CREATE TABLE cache_entries (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    expires_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_cache_expires ON cache_entries(expires_at);

-- --------------------------------------------------
-- Rate Limiter Logs (from rate_limiter.db)
-- --------------------------------------------------
CREATE TABLE rate_limiter_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    endpoint TEXT NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    allowed INTEGER DEFAULT 1
);

CREATE INDEX idx_rate_limiter_user ON rate_limiter_logs(user_id);
CREATE INDEX idx_rate_limiter_timestamp ON rate_limiter_logs(timestamp DESC);

-- --------------------------------------------------
-- Sessions (for stateful operations)
-- --------------------------------------------------
CREATE TABLE sessions (
    session_id TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL,
    data TEXT, -- JSON blob
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_accessed TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP
);

CREATE INDEX idx_sessions_user ON sessions(user_id);
CREATE INDEX idx_sessions_expires ON sessions(expires_at);
```

---

## Migration Strategy

### Data Sources

| Target DB | Source DBs | Tables to Migrate | Rows |
|-----------|------------|-------------------|------|
| **jarvis_core.db** | jarvis.db, treasury_trades.db, tax.db | positions, trades, scorecard, treasury_orders, tax_lots, wash_sales | ~700 |
| **jarvis_analytics.db** | telegram_memory.db, jarvis_admin.db, jarvis_x_memory.db, jarvis_memory.db, sentiment.db, call_tracking.db, whales.db, metrics.db, llm_costs.db | 15+ tables | ~3,500 |
| **jarvis_cache.db** | rate_limiter.db, cache.db | cache_entries, rate_limiter_logs, sessions | ~50 |

### Special Cases

#### 1. FTS5 Virtual Tables (jarvis_memory.db)
**Issue**: `ai_reflections` uses FTS5 triggers
**Solution**:
```python
# Export FTS content
cursor.execute("SELECT content, timestamp, tags FROM ai_reflections")
rows = cursor.fetchall()

# Import to new FTS table
new_cursor.execute("INSERT INTO ai_reflections(content, timestamp, tags) VALUES (?, ?, ?)", row)
```

#### 2. Foreign Key Constraints
**Issue**: Must migrate parent tables before child tables
**Order**:
1. positions (parent)
2. trades (child of positions)
3. treasury_orders (child of positions)
4. tax_lots (child of trades)
5. wash_sales (child of tax_lots)

#### 3. Backward Compatibility
**Issue**: 100+ code files reference old paths
**Solution**: Create symlinks initially, then update code
```bash
ln -s ~/.lifeos/data/jarvis_core.db ~/.lifeos/data/jarvis.db
```

---

## Validation Queries

After migration, run these to verify data integrity:

```sql
-- 1. Check position-trade relationships
SELECT COUNT(*) FROM trades WHERE position_id NOT IN (SELECT id FROM positions);
-- Expected: 0

-- 2. Check foreign key constraints
PRAGMA foreign_key_check;
-- Expected: empty

-- 3. Count total rows
SELECT
    (SELECT COUNT(*) FROM positions) as positions,
    (SELECT COUNT(*) FROM trades) as trades,
    (SELECT COUNT(*) FROM telegram_messages) as messages;
-- Compare against source databases

-- 4. Check FTS index
SELECT COUNT(*) FROM ai_reflections;
-- Compare against source jarvis_memory.db
```

---

## Rollback Plan

If migration fails:
1. **Keep originals**: All 29 source databases in `data/backup/`
2. **Feature flag**: `USE_CONSOLIDATED_DBS=false` in .env
3. **Symlinks**: Remove symlinks, code reverts to old paths
4. **Monitor**: Error rate >5% triggers automatic rollback

---

## Next Steps

1. **Create migration scripts** (Task 01-03)
   - Python scripts using sqlite3 module
   - Handle FTS5 special case
   - Preserve foreign key relationships

2. **Test in staging** (Task 01-04)
   - Migrate copy of production data
   - Run integration tests
   - Verify performance

3. **Production migration** (Task 01-05)
   - Schedule maintenance window
   - Backup all 29 databases
   - Run migration with monitoring
   - Rollback if issues detected

**Estimated Effort**: Schema design (2 days), Migration scripts (3 days), Testing (2 days)
**Total**: 1 week

---

**Document Version**: 1.0
**Author**: Claude Sonnet 4.5
**Status**: Ready for Review → Migration Script Implementation
