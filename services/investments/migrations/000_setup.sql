-- Autonomous Cross-Chain AI Portfolio Manager — Core Tables
-- Requires TimescaleDB extension

CREATE EXTENSION IF NOT EXISTS timescaledb;

-- NAV time-series (TimescaleDB hypertable)
CREATE TABLE IF NOT EXISTS inv_nav_snapshots (
    ts TIMESTAMPTZ NOT NULL,
    basket_id VARCHAR(64) NOT NULL DEFAULT 'alpha',
    nav_usd NUMERIC(18, 2) NOT NULL,
    btc_benchmark NUMERIC(18, 2),
    eth_benchmark NUMERIC(18, 2)
);
SELECT create_hypertable('inv_nav_snapshots', 'ts', if_not_exists => TRUE);
CREATE INDEX IF NOT EXISTS idx_inv_nav_basket ON inv_nav_snapshots(basket_id, ts DESC);

-- Token prices (TimescaleDB hypertable)
CREATE TABLE IF NOT EXISTS inv_token_prices (
    ts TIMESTAMPTZ NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    address VARCHAR(64),
    price_usd NUMERIC(24, 8) NOT NULL,
    volume_24h NUMERIC(24, 2)
);
SELECT create_hypertable('inv_token_prices', 'ts', if_not_exists => TRUE);
CREATE INDEX IF NOT EXISTS idx_inv_token_symbol ON inv_token_prices(symbol, ts DESC);

-- Basket snapshots (full state cache)
CREATE TABLE IF NOT EXISTS inv_basket_snapshots (
    id SERIAL PRIMARY KEY,
    basket_id VARCHAR(64) NOT NULL DEFAULT 'alpha',
    data JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Basket events from on-chain
CREATE TABLE IF NOT EXISTS inv_basket_events (
    id SERIAL PRIMARY KEY,
    basket_address VARCHAR(64) NOT NULL,
    block_number BIGINT NOT NULL,
    tx_hash VARCHAR(128) NOT NULL,
    event_data JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Fee collections
CREATE TABLE IF NOT EXISTS inv_fee_collections (
    id SERIAL PRIMARY KEY,
    basket_id VARCHAR(64) NOT NULL DEFAULT 'alpha',
    fee_amount_usdc NUMERIC(18, 6) NOT NULL,
    nav_at_collection NUMERIC(18, 2),
    bridged BOOLEAN DEFAULT FALSE,
    bridge_job_id INTEGER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Staking deposits (from cranker)
CREATE TABLE IF NOT EXISTS inv_staking_deposits (
    id SERIAL PRIMARY KEY,
    amount_raw BIGINT NOT NULL,
    amount_usdc NUMERIC(18, 6) NOT NULL,
    tx_hash VARCHAR(128),
    status VARCHAR(32) NOT NULL DEFAULT 'pending',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Staking pool snapshots (for dashboard)
CREATE TABLE IF NOT EXISTS inv_staking_pool_snapshots (
    id SERIAL PRIMARY KEY,
    total_staked BIGINT DEFAULT 0,
    total_stakers INTEGER DEFAULT 0,
    reward_vault_balance NUMERIC(18, 6) DEFAULT 0,
    estimated_apy NUMERIC(8, 2) DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Staking entries (mirror of on-chain for fast queries)
CREATE TABLE IF NOT EXISTS inv_staking_entries (
    owner VARCHAR(64) PRIMARY KEY,
    amount BIGINT DEFAULT 0,
    pending_rewards BIGINT DEFAULT 0,
    stake_timestamp BIGINT,
    tier VARCHAR(16),
    multiplier NUMERIC(4, 2),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
