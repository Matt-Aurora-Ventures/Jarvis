-- ============================================================================
-- PostgreSQL + TimescaleDB Schema Migration
-- Version: 001
-- Date: 2026-01-26
-- Description: Create core tables and TimescaleDB hypertables
-- ============================================================================

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;

-- ============================================================================
-- USERS & AUTHENTICATION
-- ============================================================================

CREATE TABLE IF NOT EXISTS users (
    user_id SERIAL PRIMARY KEY,
    telegram_user_id BIGINT UNIQUE NOT NULL,
    telegram_username TEXT,
    first_name TEXT,
    last_name TEXT,
    wallet_address TEXT UNIQUE,
    is_premium BOOLEAN DEFAULT FALSE,
    is_admin BOOLEAN DEFAULT FALSE,
    is_banned BOOLEAN DEFAULT FALSE,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    last_active_at TIMESTAMPTZ,
    settings_json JSONB DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_users_telegram ON users(telegram_user_id);
CREATE INDEX IF NOT EXISTS idx_users_wallet ON users(wallet_address);
CREATE INDEX IF NOT EXISTS idx_users_active ON users(is_active) WHERE is_active = TRUE;

-- ============================================================================
-- POSITIONS
-- ============================================================================

CREATE TABLE IF NOT EXISTS positions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id INTEGER NOT NULL DEFAULT 0 REFERENCES users(user_id) ON DELETE CASCADE,
    symbol TEXT NOT NULL,
    token_mint TEXT NOT NULL,
    entry_price DOUBLE PRECISION NOT NULL,
    entry_amount_sol DOUBLE PRECISION NOT NULL,
    entry_amount_tokens DOUBLE PRECISION NOT NULL,
    take_profit_price DOUBLE PRECISION,
    stop_loss_price DOUBLE PRECISION,
    take_profit_pct DOUBLE PRECISION,
    stop_loss_pct DOUBLE PRECISION,
    tp_order_id UUID,
    sl_order_id UUID,
    status TEXT DEFAULT 'open' CHECK(status IN ('open', 'closed', 'liquidated')),
    exit_price DOUBLE PRECISION,
    exit_amount_sol DOUBLE PRECISION,
    pnl_sol DOUBLE PRECISION,
    pnl_pct DOUBLE PRECISION,
    opened_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    closed_at TIMESTAMPTZ,
    tx_signature_entry TEXT,
    tx_signature_exit TEXT,
    metadata_json JSONB
);

CREATE INDEX IF NOT EXISTS idx_positions_user ON positions(user_id);
CREATE INDEX IF NOT EXISTS idx_positions_token ON positions(token_mint);
CREATE INDEX IF NOT EXISTS idx_positions_status ON positions(status);
CREATE INDEX IF NOT EXISTS idx_positions_opened ON positions(opened_at DESC);
CREATE INDEX IF NOT EXISTS idx_positions_user_status ON positions(user_id, status);

-- ============================================================================
-- TRADES
-- ============================================================================

CREATE TABLE IF NOT EXISTS trades (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id INTEGER NOT NULL DEFAULT 0 REFERENCES users(user_id) ON DELETE CASCADE,
    symbol TEXT NOT NULL,
    token_mint TEXT NOT NULL,
    side TEXT NOT NULL CHECK(side IN ('buy', 'sell')),
    amount_sol DOUBLE PRECISION NOT NULL,
    amount_tokens DOUBLE PRECISION NOT NULL,
    price DOUBLE PRECISION NOT NULL,
    slippage_pct DOUBLE PRECISION DEFAULT 1.0,
    priority_fee_lamports BIGINT DEFAULT 5000,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    tx_signature TEXT UNIQUE,
    position_id UUID REFERENCES positions(id) ON DELETE SET NULL,
    status TEXT DEFAULT 'pending' CHECK(status IN ('pending', 'confirmed', 'failed')),
    error_message TEXT,
    execution_time_ms INTEGER,
    fee DOUBLE PRECISION DEFAULT 0,
    total_value DOUBLE PRECISION
);

CREATE INDEX IF NOT EXISTS idx_trades_user ON trades(user_id);
CREATE INDEX IF NOT EXISTS idx_trades_token ON trades(token_mint);
CREATE INDEX IF NOT EXISTS idx_trades_position ON trades(position_id);
CREATE INDEX IF NOT EXISTS idx_trades_timestamp ON trades(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_trades_user_timestamp ON trades(user_id, timestamp DESC);

-- ============================================================================
-- ORDERS (TP/SL)
-- ============================================================================

CREATE TABLE IF NOT EXISTS orders (
    order_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    position_id UUID REFERENCES positions(id) ON DELETE CASCADE,
    order_type TEXT NOT NULL CHECK(order_type IN ('take_profit', 'stop_loss', 'limit', 'market')),
    side TEXT NOT NULL CHECK(side IN ('buy', 'sell')),
    token_mint TEXT NOT NULL,
    trigger_price DOUBLE PRECISION,
    limit_price DOUBLE PRECISION,
    amount_tokens DOUBLE PRECISION NOT NULL,
    status TEXT DEFAULT 'active' CHECK(status IN ('active', 'triggered', 'filled', 'cancelled')),
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    triggered_at TIMESTAMPTZ,
    filled_at TIMESTAMPTZ,
    cancelled_at TIMESTAMPTZ,
    tx_signature TEXT
);

CREATE INDEX IF NOT EXISTS idx_orders_user ON orders(user_id);
CREATE INDEX IF NOT EXISTS idx_orders_position ON orders(position_id);
CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);
CREATE INDEX IF NOT EXISTS idx_orders_type ON orders(order_type);
CREATE INDEX IF NOT EXISTS idx_orders_active ON orders(status) WHERE status = 'active';

-- ============================================================================
-- BOT CONFIGURATION
-- ============================================================================

CREATE TABLE IF NOT EXISTS bot_config (
    id SERIAL PRIMARY KEY,
    user_id INTEGER UNIQUE REFERENCES users(user_id) ON DELETE CASCADE,
    key TEXT UNIQUE,
    value TEXT,
    description TEXT,
    trading_enabled BOOLEAN DEFAULT TRUE,
    max_position_size_sol DOUBLE PRECISION DEFAULT 10.0,
    max_positions INTEGER DEFAULT 5,
    default_slippage_pct DOUBLE PRECISION DEFAULT 1.0,
    auto_take_profit_pct DOUBLE PRECISION DEFAULT 100.0,
    auto_stop_loss_pct DOUBLE PRECISION DEFAULT 50.0,
    risk_level TEXT DEFAULT 'medium' CHECK(risk_level IN ('low', 'medium', 'high', 'degen')),
    notifications_enabled BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================================
-- TOKEN METADATA CACHE
-- ============================================================================

CREATE TABLE IF NOT EXISTS token_metadata (
    token_mint TEXT PRIMARY KEY,
    symbol TEXT,
    name TEXT,
    decimals INTEGER DEFAULT 9,
    logo_url TEXT,
    coingecko_id TEXT,
    dexscreener_pair TEXT,
    market_cap_usd DOUBLE PRECISION,
    liquidity_usd DOUBLE PRECISION,
    holder_count INTEGER,
    cached_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    is_verified BOOLEAN DEFAULT FALSE,
    is_scam BOOLEAN DEFAULT FALSE,
    metadata_json JSONB
);

CREATE INDEX IF NOT EXISTS idx_token_symbol ON token_metadata(symbol);
CREATE INDEX IF NOT EXISTS idx_token_cached ON token_metadata(cached_at DESC);

-- ============================================================================
-- USER SCORECARDS
-- ============================================================================

CREATE TABLE IF NOT EXISTS user_scorecard (
    user_id INTEGER PRIMARY KEY REFERENCES users(user_id) ON DELETE CASCADE,
    total_trades INTEGER DEFAULT 0,
    winning_trades INTEGER DEFAULT 0,
    losing_trades INTEGER DEFAULT 0,
    total_pnl_sol DOUBLE PRECISION DEFAULT 0,
    total_pnl_usd DOUBLE PRECISION DEFAULT 0,
    largest_win_sol DOUBLE PRECISION DEFAULT 0,
    largest_loss_sol DOUBLE PRECISION DEFAULT 0,
    current_streak INTEGER DEFAULT 0,
    best_streak INTEGER DEFAULT 0,
    worst_streak INTEGER DEFAULT 0,
    avg_win_pct DOUBLE PRECISION DEFAULT 0,
    avg_loss_pct DOUBLE PRECISION DEFAULT 0,
    win_rate DOUBLE PRECISION DEFAULT 0,
    sharpe_ratio DOUBLE PRECISION,
    max_drawdown_pct DOUBLE PRECISION,
    last_updated TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================================
-- DAILY PNL
-- ============================================================================

CREATE TABLE IF NOT EXISTS daily_pnl (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    date DATE NOT NULL,
    trades_opened INTEGER DEFAULT 0,
    trades_closed INTEGER DEFAULT 0,
    wins INTEGER DEFAULT 0,
    losses INTEGER DEFAULT 0,
    total_pnl_sol DOUBLE PRECISION DEFAULT 0,
    total_pnl_percent DOUBLE PRECISION DEFAULT 0,
    largest_win DOUBLE PRECISION DEFAULT 0,
    largest_loss DOUBLE PRECISION DEFAULT 0,
    win_rate DOUBLE PRECISION DEFAULT 0,
    UNIQUE(user_id, date)
);

CREATE INDEX IF NOT EXISTS idx_daily_pnl_user_date ON daily_pnl(user_id, date DESC);

-- ============================================================================
-- TIMESCALEDB HYPERTABLES
-- ============================================================================

-- Price ticks (time-series)
CREATE TABLE IF NOT EXISTS price_ticks (
    token_mint TEXT NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    price DOUBLE PRECISION NOT NULL,
    volume DOUBLE PRECISION DEFAULT 0,
    source TEXT DEFAULT 'jupiter',
    metadata JSONB,
    PRIMARY KEY (token_mint, timestamp)
);

-- Convert to hypertable
SELECT create_hypertable('price_ticks', 'timestamp',
    if_not_exists => TRUE,
    chunk_time_interval => INTERVAL '1 day'
);

CREATE INDEX IF NOT EXISTS idx_price_ticks_token_time ON price_ticks(token_mint, timestamp DESC);

-- Strategy signals (time-series)
CREATE TABLE IF NOT EXISTS strategy_signals (
    id SERIAL,
    strategy_id TEXT NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    signal_type TEXT NOT NULL CHECK(signal_type IN ('buy', 'sell', 'hold')),
    confidence DOUBLE PRECISION NOT NULL,
    token_mint TEXT NOT NULL,
    metadata JSONB,
    PRIMARY KEY (id, timestamp)
);

SELECT create_hypertable('strategy_signals', 'timestamp',
    if_not_exists => TRUE,
    chunk_time_interval => INTERVAL '1 day'
);

CREATE INDEX IF NOT EXISTS idx_signals_strategy_time ON strategy_signals(strategy_id, timestamp DESC);

-- Position history (time-series snapshots)
CREATE TABLE IF NOT EXISTS position_history (
    position_id UUID NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    pnl_sol DOUBLE PRECISION NOT NULL,
    pnl_pct DOUBLE PRECISION NOT NULL,
    size_tokens DOUBLE PRECISION NOT NULL,
    current_price DOUBLE PRECISION NOT NULL,
    metadata JSONB,
    PRIMARY KEY (position_id, timestamp)
);

SELECT create_hypertable('position_history', 'timestamp',
    if_not_exists => TRUE,
    chunk_time_interval => INTERVAL '1 day'
);

CREATE INDEX IF NOT EXISTS idx_position_history_pos_time ON position_history(position_id, timestamp DESC);

-- ============================================================================
-- CONTINUOUS AGGREGATES (OHLC)
-- ============================================================================

-- 1-hour OHLC bars
CREATE MATERIALIZED VIEW IF NOT EXISTS price_ohlc_1h
WITH (timescaledb.continuous) AS
SELECT
    token_mint,
    time_bucket('1 hour', timestamp) AS bucket,
    first(price, timestamp) AS open,
    max(price) AS high,
    min(price) AS low,
    last(price, timestamp) AS close,
    sum(volume) AS volume
FROM price_ticks
GROUP BY token_mint, time_bucket('1 hour', timestamp)
WITH NO DATA;

-- 1-day OHLC bars
CREATE MATERIALIZED VIEW IF NOT EXISTS price_ohlc_1d
WITH (timescaledb.continuous) AS
SELECT
    token_mint,
    time_bucket('1 day', timestamp) AS bucket,
    first(price, timestamp) AS open,
    max(price) AS high,
    min(price) AS low,
    last(price, timestamp) AS close,
    sum(volume) AS volume
FROM price_ticks
GROUP BY token_mint, time_bucket('1 day', timestamp)
WITH NO DATA;

-- Refresh policies for continuous aggregates
SELECT add_continuous_aggregate_policy('price_ohlc_1h',
    start_offset => INTERVAL '3 hours',
    end_offset => INTERVAL '1 hour',
    schedule_interval => INTERVAL '1 hour',
    if_not_exists => TRUE
);

SELECT add_continuous_aggregate_policy('price_ohlc_1d',
    start_offset => INTERVAL '3 days',
    end_offset => INTERVAL '1 day',
    schedule_interval => INTERVAL '1 day',
    if_not_exists => TRUE
);

-- ============================================================================
-- DATA RETENTION POLICIES
-- ============================================================================

-- Keep raw price ticks for 30 days
SELECT add_retention_policy('price_ticks', INTERVAL '30 days', if_not_exists => TRUE);

-- Keep strategy signals for 90 days
SELECT add_retention_policy('strategy_signals', INTERVAL '90 days', if_not_exists => TRUE);

-- Keep position history for 1 year
SELECT add_retention_policy('position_history', INTERVAL '365 days', if_not_exists => TRUE);

-- ============================================================================
-- VIEWS
-- ============================================================================

CREATE OR REPLACE VIEW v_active_positions AS
SELECT
    p.*,
    t.symbol AS token_symbol,
    t.name AS token_name,
    u.telegram_username,
    (SELECT COUNT(*) FROM trades WHERE position_id = p.id) AS trade_count
FROM positions p
LEFT JOIN token_metadata t ON p.token_mint = t.token_mint
LEFT JOIN users u ON p.user_id = u.user_id
WHERE p.status = 'open';

CREATE OR REPLACE VIEW v_user_portfolio AS
SELECT
    u.user_id,
    u.telegram_username,
    COUNT(DISTINCT p.id) AS open_positions,
    COALESCE(SUM(p.entry_amount_sol), 0) AS total_invested_sol,
    COALESCE(SUM(p.pnl_sol), 0) AS unrealized_pnl_sol,
    s.win_rate,
    s.total_pnl_sol AS realized_pnl_sol
FROM users u
LEFT JOIN positions p ON u.user_id = p.user_id AND p.status = 'open'
LEFT JOIN user_scorecard s ON u.user_id = s.user_id
GROUP BY u.user_id, u.telegram_username, s.win_rate, s.total_pnl_sol;

-- ============================================================================
-- COMPRESSION (optional for older data)
-- ============================================================================

-- Enable compression on price_ticks
ALTER TABLE price_ticks SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'token_mint'
);

-- Compress chunks older than 7 days
SELECT add_compression_policy('price_ticks', INTERVAL '7 days', if_not_exists => TRUE);

-- ============================================================================
-- MIGRATION METADATA
-- ============================================================================

CREATE TABLE IF NOT EXISTS schema_migrations (
    version TEXT PRIMARY KEY,
    applied_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    description TEXT
);

INSERT INTO schema_migrations (version, description)
VALUES ('001', 'Create core tables and TimescaleDB hypertables')
ON CONFLICT (version) DO NOTHING;
