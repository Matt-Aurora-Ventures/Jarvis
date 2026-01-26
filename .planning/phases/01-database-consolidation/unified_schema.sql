-- =============================================================================
-- Jarvis Database Consolidation - Unified Schema Design
-- =============================================================================
-- Phase: 1.1 - Database Consolidation
-- Task: 2 - Design unified schema
-- Created: 2026-01-25
-- Target: Consolidate 35 databases → 3 databases
-- =============================================================================

-- =============================================================================
-- DATABASE 1: jarvis_core.db
-- Purpose: Core operational data (positions, trades, orders, users, bot state)
-- Estimated Size: ~800KB
-- Access Pattern: High frequency (100+ QPS)
-- Backup: Real-time replication
-- =============================================================================

-- -----------------------------------------------------------------------------
-- Positions & Trading
-- -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS positions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    token_address TEXT NOT NULL,
    token_symbol TEXT NOT NULL,
    entry_price REAL NOT NULL,
    current_price REAL,
    quantity REAL NOT NULL,
    sol_invested REAL NOT NULL,
    current_value REAL,
    pnl_sol REAL,
    pnl_percent REAL,
    status TEXT NOT NULL DEFAULT 'open', -- open, closed, exited
    source TEXT DEFAULT 'legacy', -- legacy, treasury
    open_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    close_time TIMESTAMP,
    exit_reason TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_positions_token ON positions(token_address);
CREATE INDEX idx_positions_status ON positions(status);
CREATE INDEX idx_positions_source ON positions(source);
CREATE INDEX idx_positions_open_time ON positions(open_time);

-- -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    token_address TEXT NOT NULL,
    token_symbol TEXT NOT NULL,
    trade_type TEXT NOT NULL, -- buy, sell
    price REAL NOT NULL,
    quantity REAL NOT NULL,
    sol_amount REAL NOT NULL,
    fee REAL DEFAULT 0,
    signature TEXT UNIQUE,
    source TEXT DEFAULT 'legacy', -- legacy, buy_tracker
    executed_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_trades_token ON trades(token_address);
CREATE INDEX idx_trades_type ON trades(trade_type);
CREATE INDEX idx_trades_source ON trades(source);
CREATE INDEX idx_trades_executed_at ON trades(executed_at);
CREATE INDEX idx_trades_signature ON trades(signature);

-- -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS treasury_orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id TEXT UNIQUE NOT NULL,
    token_address TEXT NOT NULL,
    token_symbol TEXT,
    order_type TEXT NOT NULL, -- market, limit, stop_loss, take_profit
    side TEXT NOT NULL, -- buy, sell
    quantity REAL NOT NULL,
    price REAL,
    stop_price REAL,
    status TEXT NOT NULL DEFAULT 'pending', -- pending, filled, cancelled, failed
    filled_quantity REAL DEFAULT 0,
    average_fill_price REAL,
    signature TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    filled_at TIMESTAMP
);

CREATE INDEX idx_treasury_orders_token ON treasury_orders(token_address);
CREATE INDEX idx_treasury_orders_status ON treasury_orders(status);
CREATE INDEX idx_treasury_orders_created_at ON treasury_orders(created_at);

-- -----------------------------------------------------------------------------
-- Users & Authentication
-- -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    telegram_id INTEGER UNIQUE,
    twitter_id TEXT UNIQUE,
    role TEXT NOT NULL DEFAULT 'user', -- admin, user, viewer
    is_active BOOLEAN DEFAULT 1,
    wallet_address TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_seen_at TIMESTAMP
);

CREATE INDEX idx_users_telegram_id ON users(telegram_id);
CREATE INDEX idx_users_twitter_id ON users(twitter_id);
CREATE INDEX idx_users_role ON users(role);

-- -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_type TEXT NOT NULL,
    item_data TEXT NOT NULL, -- JSON blob
    owner_id INTEGER,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (owner_id) REFERENCES users(id) ON DELETE SET NULL
);

CREATE INDEX idx_items_type ON items(item_type);
CREATE INDEX idx_items_owner ON items(owner_id);

-- -----------------------------------------------------------------------------
-- Memory & Context
-- -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS memory_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    memory_type TEXT NOT NULL, -- core, shared
    key TEXT NOT NULL,
    value TEXT NOT NULL, -- JSON blob
    source TEXT DEFAULT 'core',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP,
    UNIQUE(memory_type, key)
);

CREATE INDEX idx_memory_type ON memory_entries(memory_type);
CREATE INDEX idx_memory_expires ON memory_entries(expires_at);

-- -----------------------------------------------------------------------------
-- Telegram Bot Data
-- -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS telegram_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    message_id INTEGER NOT NULL,
    chat_id INTEGER NOT NULL,
    message_text TEXT,
    message_type TEXT DEFAULT 'text',
    timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX idx_telegram_messages_user ON telegram_messages(user_id);
CREATE INDEX idx_telegram_messages_chat ON telegram_messages(chat_id);
CREATE INDEX idx_telegram_messages_timestamp ON telegram_messages(timestamp);

-- -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS telegram_memories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    memory_key TEXT NOT NULL,
    memory_value TEXT NOT NULL,
    context TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE(user_id, memory_key)
);

CREATE INDEX idx_telegram_memories_user ON telegram_memories(user_id);

-- -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS telegram_instructions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    instruction_text TEXT NOT NULL,
    is_active BOOLEAN DEFAULT 1,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX idx_telegram_instructions_user ON telegram_instructions(user_id);
CREATE INDEX idx_telegram_instructions_active ON telegram_instructions(is_active);

-- -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS telegram_learnings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    learning_type TEXT NOT NULL,
    learning_data TEXT NOT NULL, -- JSON blob
    confidence REAL DEFAULT 0.5,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_telegram_learnings_type ON telegram_learnings(learning_type);

-- -----------------------------------------------------------------------------
-- Twitter/X Bot Data
-- -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS tweets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tweet_id TEXT UNIQUE NOT NULL,
    tweet_text TEXT NOT NULL,
    tweet_type TEXT DEFAULT 'status', -- status, reply, retweet
    in_reply_to TEXT,
    posted_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_tweets_type ON tweets(tweet_type);
CREATE INDEX idx_tweets_posted_at ON tweets(posted_at);

-- -----------------------------------------------------------------------------
-- Bags.fm Intelligence
-- -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS bags_intel (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    token_address TEXT UNIQUE NOT NULL,
    token_name TEXT,
    graduation_time TIMESTAMP,
    score REAL,
    quality_tier TEXT,
    intel_data TEXT NOT NULL, -- JSON blob with full analysis
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_bags_intel_token ON bags_intel(token_address);
CREATE INDEX idx_bags_intel_score ON bags_intel(score);
CREATE INDEX idx_bags_intel_graduation ON bags_intel(graduation_time);

-- =============================================================================
-- DATABASE 2: jarvis_analytics.db
-- Purpose: Analytics, metrics, performance tracking, cost monitoring
-- Estimated Size: ~150KB
-- Access Pattern: Medium frequency (10-20 QPS)
-- Backup: Daily snapshots
-- =============================================================================

-- -----------------------------------------------------------------------------
-- LLM Cost Tracking
-- -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS llm_usage (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    provider TEXT NOT NULL, -- openai, anthropic, xai
    model TEXT NOT NULL,
    prompt_tokens INTEGER NOT NULL,
    completion_tokens INTEGER NOT NULL,
    total_tokens INTEGER NOT NULL,
    cost_usd REAL NOT NULL,
    request_type TEXT,
    user_id INTEGER,
    timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_llm_usage_provider ON llm_usage(provider);
CREATE INDEX idx_llm_usage_model ON llm_usage(model);
CREATE INDEX idx_llm_usage_timestamp ON llm_usage(timestamp);

-- -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS llm_daily_stats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date DATE UNIQUE NOT NULL,
    provider TEXT NOT NULL,
    model TEXT NOT NULL,
    total_requests INTEGER DEFAULT 0,
    total_tokens INTEGER DEFAULT 0,
    total_cost_usd REAL DEFAULT 0,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(date, provider, model)
);

CREATE INDEX idx_llm_daily_stats_date ON llm_daily_stats(date);

-- -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS budget_alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    alert_type TEXT NOT NULL, -- daily_limit, monthly_limit, threshold
    threshold_usd REAL NOT NULL,
    actual_usd REAL NOT NULL,
    alert_message TEXT,
    triggered_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_budget_alerts_triggered_at ON budget_alerts(triggered_at);

-- -----------------------------------------------------------------------------
-- Performance Metrics
-- -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS metrics_1m (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    metric_name TEXT NOT NULL,
    metric_value REAL NOT NULL,
    metric_tags TEXT, -- JSON blob
    timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_metrics_1m_name ON metrics_1m(metric_name);
CREATE INDEX idx_metrics_1m_timestamp ON metrics_1m(timestamp);

-- -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS metrics_1h (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    metric_name TEXT NOT NULL,
    metric_value REAL NOT NULL,
    metric_tags TEXT, -- JSON blob
    timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_metrics_1h_name ON metrics_1h(metric_name);
CREATE INDEX idx_metrics_1h_timestamp ON metrics_1h(timestamp);

-- -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS alert_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    alert_type TEXT NOT NULL,
    severity TEXT NOT NULL, -- low, medium, high, critical
    alert_message TEXT NOT NULL,
    alert_data TEXT, -- JSON blob
    acknowledged BOOLEAN DEFAULT 0,
    acknowledged_by INTEGER,
    triggered_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    acknowledged_at TIMESTAMP
);

CREATE INDEX idx_alert_history_type ON alert_history(alert_type);
CREATE INDEX idx_alert_history_severity ON alert_history(severity);
CREATE INDEX idx_alert_history_triggered ON alert_history(triggered_at);

-- -----------------------------------------------------------------------------
-- Trading Analytics
-- -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS daily_stats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date DATE UNIQUE NOT NULL,
    total_trades INTEGER DEFAULT 0,
    total_volume_sol REAL DEFAULT 0,
    total_pnl_sol REAL DEFAULT 0,
    win_rate REAL DEFAULT 0,
    best_trade_pnl REAL,
    worst_trade_pnl REAL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_daily_stats_date ON daily_stats(date);

-- -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS treasury_stats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date DATE UNIQUE NOT NULL,
    total_positions INTEGER DEFAULT 0,
    open_positions INTEGER DEFAULT 0,
    total_value_sol REAL DEFAULT 0,
    total_pnl_sol REAL DEFAULT 0,
    win_rate REAL DEFAULT 0,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_treasury_stats_date ON treasury_stats(date);

-- -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS trade_learnings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    learning_type TEXT NOT NULL, -- pattern, strategy, risk
    learning_data TEXT NOT NULL, -- JSON blob
    confidence REAL DEFAULT 0.5,
    success_rate REAL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_trade_learnings_type ON trade_learnings(learning_type);

-- -----------------------------------------------------------------------------
-- Bot Scorecards (Consolidated from 4 sources)
-- -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS scorecards (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    bot_type TEXT NOT NULL, -- treasury, buy_tracker, sentiment, twitter
    bot_id TEXT,
    metric_name TEXT NOT NULL,
    metric_value REAL NOT NULL,
    metric_data TEXT, -- JSON blob for additional data
    period_start TIMESTAMP NOT NULL,
    period_end TIMESTAMP NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(bot_type, bot_id, metric_name, period_start)
);

CREATE INDEX idx_scorecards_bot_type ON scorecards(bot_type);
CREATE INDEX idx_scorecards_period ON scorecards(period_start);

-- -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS pick_performance (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    token_address TEXT NOT NULL,
    token_symbol TEXT,
    pick_source TEXT NOT NULL, -- manual, ai, community
    entry_price REAL NOT NULL,
    exit_price REAL,
    pnl_percent REAL,
    status TEXT NOT NULL DEFAULT 'active', -- active, closed
    picked_at TIMESTAMP NOT NULL,
    closed_at TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_pick_performance_token ON pick_performance(token_address);
CREATE INDEX idx_pick_performance_source ON pick_performance(pick_source);
CREATE INDEX idx_pick_performance_picked_at ON pick_performance(picked_at);

-- =============================================================================
-- DATABASE 3: jarvis_cache.db
-- Purpose: Transient cache data (rate limiting, file cache, session state)
-- Estimated Size: ~100KB
-- Access Pattern: Variable (can spike)
-- Backup: None needed (can rebuild)
-- TTL: Most entries expire after 24-48 hours
-- =============================================================================

-- -----------------------------------------------------------------------------
-- Rate Limiting
-- -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS rate_configs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    endpoint TEXT UNIQUE NOT NULL,
    max_requests INTEGER NOT NULL,
    time_window_seconds INTEGER NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_rate_configs_endpoint ON rate_configs(endpoint);

-- -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS request_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    endpoint TEXT NOT NULL,
    client_id TEXT,
    request_count INTEGER DEFAULT 1,
    timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NOT NULL -- Auto-delete after expiry
);

CREATE INDEX idx_request_log_endpoint ON request_log(endpoint);
CREATE INDEX idx_request_log_client ON request_log(client_id);
CREATE INDEX idx_request_log_expires ON request_log(expires_at);

-- -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS limit_stats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    endpoint TEXT NOT NULL,
    total_requests INTEGER DEFAULT 0,
    blocked_requests INTEGER DEFAULT 0,
    last_block_at TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(endpoint)
);

-- -----------------------------------------------------------------------------
-- File & Response Cache
-- -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS cache_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cache_key TEXT UNIQUE NOT NULL,
    cache_value TEXT NOT NULL,
    cache_type TEXT DEFAULT 'file', -- file, response, session
    size_bytes INTEGER,
    hit_count INTEGER DEFAULT 0,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    accessed_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NOT NULL
);

CREATE INDEX idx_cache_entries_key ON cache_entries(cache_key);
CREATE INDEX idx_cache_entries_type ON cache_entries(cache_type);
CREATE INDEX idx_cache_entries_expires ON cache_entries(expires_at);

-- -----------------------------------------------------------------------------
-- Key-Value Store
-- -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS kv_entries (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    value_type TEXT DEFAULT 'string', -- string, json, binary
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP
);

CREATE INDEX idx_kv_expires ON kv_entries(expires_at);

-- -----------------------------------------------------------------------------
-- Bot State (Transient)
-- -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS bot_state (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    bot_type TEXT NOT NULL, -- twitter, buy_tracker, sentiment, bags_intel
    bot_id TEXT,
    state_key TEXT NOT NULL,
    state_value TEXT NOT NULL, -- JSON blob
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(bot_type, bot_id, state_key)
);

CREATE INDEX idx_bot_state_bot_type ON bot_state(bot_type);

-- -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS last_actions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    action_type TEXT NOT NULL, -- last_post, last_report, last_check
    bot_type TEXT NOT NULL,
    bot_id TEXT,
    timestamp TIMESTAMP NOT NULL,
    action_data TEXT, -- JSON blob
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(action_type, bot_type, bot_id)
);

CREATE INDEX idx_last_actions_bot ON last_actions(bot_type);

-- =============================================================================
-- Migration Views (For Backward Compatibility)
-- =============================================================================

-- These views allow old code to work during migration phase
-- DROP AFTER MIGRATION COMPLETE

-- Legacy scorecard view (maps to new scorecards table)
CREATE VIEW IF NOT EXISTS scorecard AS
SELECT
    id,
    metric_name,
    metric_value,
    period_start as timestamp
FROM scorecards
WHERE bot_type = 'treasury';

-- =============================================================================
-- Cleanup Triggers (For Cache Database)
-- =============================================================================

-- Auto-delete expired cache entries
CREATE TRIGGER IF NOT EXISTS cleanup_expired_cache
AFTER INSERT ON cache_entries
BEGIN
    DELETE FROM cache_entries WHERE expires_at < CURRENT_TIMESTAMP;
END;

-- Auto-delete expired request logs
CREATE TRIGGER IF NOT EXISTS cleanup_expired_requests
AFTER INSERT ON request_log
BEGIN
    DELETE FROM request_log WHERE expires_at < CURRENT_TIMESTAMP;
END;

-- Auto-delete expired KV entries
CREATE TRIGGER IF NOT EXISTS cleanup_expired_kv
AFTER INSERT ON kv_entries
BEGIN
    DELETE FROM kv_entries WHERE expires_at IS NOT NULL AND expires_at < CURRENT_TIMESTAMP;
END;

-- =============================================================================
-- Schema Version Tracking
-- =============================================================================

CREATE TABLE IF NOT EXISTS schema_version (
    database_name TEXT PRIMARY KEY,
    version INTEGER NOT NULL,
    migrated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

INSERT OR REPLACE INTO schema_version (database_name, version) VALUES ('jarvis_core', 1);
INSERT OR REPLACE INTO schema_version (database_name, version) VALUES ('jarvis_analytics', 1);
INSERT OR REPLACE INTO schema_version (database_name, version) VALUES ('jarvis_cache', 1);

-- =============================================================================
-- END OF UNIFIED SCHEMA
-- =============================================================================
