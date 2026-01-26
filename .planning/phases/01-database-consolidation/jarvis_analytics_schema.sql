-- ============================================================================
-- JARVIS ANALYTICS DATABASE - Unified Schema Design
-- ============================================================================
-- Purpose: Historical data, analytics, AI memory (non-critical path)
-- Access Pattern: Medium frequency (10-20 QPS), batch queries
-- Backup: Daily snapshots
-- Phase: 1.3 - Database Consolidation
-- ============================================================================

-- ============================================================================
-- LLM COSTS & API USAGE
-- ============================================================================

CREATE TABLE IF NOT EXISTS llm_costs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    provider TEXT NOT NULL, -- 'anthropic', 'openai', 'google', etc.
    model TEXT NOT NULL,
    prompt_tokens INTEGER DEFAULT 0,
    completion_tokens INTEGER DEFAULT 0,
    total_tokens INTEGER DEFAULT 0,
    cost_usd REAL DEFAULT 0,
    feature TEXT, -- 'trading', 'chat', 'analysis', etc.
    timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
    metadata_json TEXT,
    INDEX idx_llm_costs_user (user_id),
    INDEX idx_llm_costs_provider (provider),
    INDEX idx_llm_costs_timestamp (timestamp)
);

CREATE TABLE IF NOT EXISTS api_usage (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    api_name TEXT NOT NULL, -- 'helius', 'jupiter', 'dexscreener', etc.
    endpoint TEXT,
    method TEXT,
    status_code INTEGER,
    response_time_ms INTEGER,
    error_message TEXT,
    user_id INTEGER,
    timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_api_usage_api (api_name),
    INDEX idx_api_usage_timestamp (timestamp)
);

-- ============================================================================
-- PERFORMANCE METRICS & HEALTH
-- ============================================================================

CREATE TABLE IF NOT EXISTS system_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    metric_name TEXT NOT NULL,
    metric_value REAL NOT NULL,
    metric_unit TEXT, -- 'ms', 'bytes', 'count', etc.
    component TEXT, -- 'bot', 'api', 'database', etc.
    timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_metrics_name (metric_name),
    INDEX idx_metrics_component (component),
    INDEX idx_metrics_timestamp (timestamp)
);

CREATE TABLE IF NOT EXISTS health_checks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    service_name TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('healthy', 'degraded', 'down')),
    response_time_ms INTEGER,
    error_message TEXT,
    checked_at TEXT DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_health_service (service_name),
    INDEX idx_health_timestamp (checked_at)
);

CREATE TABLE IF NOT EXISTS error_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    error_type TEXT NOT NULL,
    component TEXT NOT NULL,
    message TEXT NOT NULL,
    context TEXT,
    stack_trace TEXT,
    user_id INTEGER,
    resolved BOOLEAN DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_errors_type (error_type),
    INDEX idx_errors_component (component),
    INDEX idx_errors_resolved (resolved),
    INDEX idx_errors_created (created_at)
);

-- ============================================================================
-- AI MEMORY & LEARNINGS
-- ============================================================================

CREATE TABLE IF NOT EXISTS conversation_memory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    platform TEXT NOT NULL, -- 'telegram', 'twitter', 'discord'
    role TEXT NOT NULL CHECK(role IN ('user', 'assistant', 'system')),
    content TEXT NOT NULL,
    tokens INTEGER,
    timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_conversation_user (user_id),
    INDEX idx_conversation_platform (platform),
    INDEX idx_conversation_timestamp (timestamp)
);

CREATE TABLE IF NOT EXISTS trade_learnings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trade_id TEXT,
    token_symbol TEXT,
    token_type TEXT, -- 'memecoin', 'defi', 'nft', etc.
    learning_type TEXT, -- 'success_pattern', 'failure_pattern', 'market_condition'
    insight TEXT NOT NULL,
    confidence REAL DEFAULT 0.5,
    applied_count INTEGER DEFAULT 0,
    success_rate REAL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_learnings_token (token_symbol),
    INDEX idx_learnings_type (learning_type),
    INDEX idx_learnings_confidence (confidence DESC)
);

CREATE TABLE IF NOT EXISTS user_preferences (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    platform TEXT NOT NULL,
    preference_key TEXT NOT NULL,
    preference_value TEXT NOT NULL,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, platform, preference_key),
    INDEX idx_prefs_user (user_id)
);

-- ============================================================================
-- SENTIMENT & SOCIAL DATA
-- ============================================================================

CREATE TABLE IF NOT EXISTS token_sentiment (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    token_mint TEXT NOT NULL,
    symbol TEXT,
    sentiment_score REAL, -- -1 to 1
    bullish_count INTEGER DEFAULT 0,
    bearish_count INTEGER DEFAULT 0,
    neutral_count INTEGER DEFAULT 0,
    total_mentions INTEGER DEFAULT 0,
    sources_json TEXT, -- Array of sources
    analyzed_at TEXT DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_sentiment_token (token_mint),
    INDEX idx_sentiment_analyzed (analyzed_at)
);

CREATE TABLE IF NOT EXISTS social_signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    token_mint TEXT NOT NULL,
    platform TEXT NOT NULL, -- 'twitter', 'telegram', 'reddit'
    signal_type TEXT, -- 'trending', 'whale_buy', 'influencer_mention'
    signal_strength REAL,
    metadata_json TEXT,
    detected_at TEXT DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_signals_token (token_mint),
    INDEX idx_signals_platform (platform),
    INDEX idx_signals_detected (detected_at)
);

-- ============================================================================
-- COMMUNITY & ACHIEVEMENTS
-- ============================================================================

CREATE TABLE IF NOT EXISTS user_achievements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    achievement_type TEXT NOT NULL,
    achievement_name TEXT NOT NULL,
    description TEXT,
    icon_emoji TEXT,
    earned_at TEXT DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_achievements_user (user_id),
    INDEX idx_achievements_type (achievement_type)
);

CREATE TABLE IF NOT EXISTS leaderboard (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    period TEXT NOT NULL, -- 'daily', 'weekly', 'monthly', 'all_time'
    metric TEXT NOT NULL, -- 'pnl', 'win_rate', 'total_trades'
    user_id INTEGER NOT NULL,
    rank INTEGER,
    score REAL,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(period, metric, user_id),
    INDEX idx_leaderboard_period_metric (period, metric, rank)
);

-- ============================================================================
-- WHALE TRACKING
-- ============================================================================

CREATE TABLE IF NOT EXISTS whale_wallets (
    wallet_address TEXT PRIMARY KEY,
    label TEXT,
    total_balance_sol REAL,
    token_count INTEGER,
    first_seen TEXT DEFAULT CURRENT_TIMESTAMP,
    last_active TEXT,
    is_monitored BOOLEAN DEFAULT 1,
    metadata_json TEXT
);

CREATE TABLE IF NOT EXISTS whale_transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    wallet_address TEXT NOT NULL,
    tx_signature TEXT UNIQUE NOT NULL,
    tx_type TEXT, -- 'buy', 'sell', 'transfer'
    token_mint TEXT,
    amount_sol REAL,
    amount_tokens REAL,
    price REAL,
    timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (wallet_address) REFERENCES whale_wallets(wallet_address),
    INDEX idx_whale_tx_wallet (wallet_address),
    INDEX idx_whale_tx_token (token_mint),
    INDEX idx_whale_tx_timestamp (timestamp)
);

-- ============================================================================
-- RESEARCH & TOKEN TRACKING
-- ============================================================================

CREATE TABLE IF NOT EXISTS token_research (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    token_mint TEXT NOT NULL,
    symbol TEXT,
    research_type TEXT, -- 'fundamental', 'technical', 'social'
    findings TEXT,
    risk_score INTEGER, -- 1-10
    opportunity_score INTEGER, -- 1-10
    analyst TEXT, -- 'ai' or user_id
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_research_token (token_mint),
    INDEX idx_research_type (research_type)
);

CREATE TABLE IF NOT EXISTS token_calls (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    token_mint TEXT NOT NULL,
    symbol TEXT,
    caller_id TEXT, -- telegram/twitter user
    platform TEXT,
    call_type TEXT, -- 'buy', 'sell', 'hold'
    target_price REAL,
    confidence INTEGER, -- 1-10
    called_at TEXT DEFAULT CURRENT_TIMESTAMP,
    outcome TEXT, -- 'hit', 'miss', 'pending'
    actual_price REAL,
    INDEX idx_calls_token (token_mint),
    INDEX idx_calls_platform (platform),
    INDEX idx_calls_outcome (outcome)
);

-- ============================================================================
-- TRADING ANALYTICS
-- ============================================================================

CREATE TABLE IF NOT EXISTS backtest_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    strategy_name TEXT NOT NULL,
    parameters_json TEXT,
    start_date TEXT,
    end_date TEXT,
    total_trades INTEGER,
    win_rate REAL,
    total_pnl_sol REAL,
    sharpe_ratio REAL,
    max_drawdown_pct REAL,
    run_at TEXT DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_backtest_strategy (strategy_name),
    INDEX idx_backtest_run (run_at)
);

CREATE TABLE IF NOT EXISTS market_conditions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    condition_type TEXT, -- 'bull', 'bear', 'sideways', 'volatile'
    sol_price_usd REAL,
    btc_price_usd REAL,
    market_cap_total_usd REAL,
    volume_24h_usd REAL,
    fear_greed_index INTEGER,
    recorded_at TEXT DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_market_recorded (recorded_at)
);

-- ============================================================================
-- TAX & REPORTING
-- ============================================================================

CREATE TABLE IF NOT EXISTS tax_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    event_type TEXT NOT NULL, -- 'trade', 'transfer', 'airdrop', 'stake'
    token_mint TEXT,
    amount_tokens REAL,
    cost_basis_usd REAL,
    fair_market_value_usd REAL,
    capital_gain_usd REAL,
    tx_signature TEXT,
    event_date TEXT NOT NULL,
    tax_year INTEGER,
    INDEX idx_tax_user (user_id),
    INDEX idx_tax_year (tax_year),
    INDEX idx_tax_event_date (event_date)
);

-- ============================================================================
-- TOKEN DISTRIBUTIONS
-- ============================================================================

CREATE TABLE IF NOT EXISTS airdrops (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    token_mint TEXT NOT NULL,
    symbol TEXT,
    user_wallet TEXT,
    amount_tokens REAL,
    claimed BOOLEAN DEFAULT 0,
    claimed_at TEXT,
    airdrop_date TEXT DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_airdrops_token (token_mint),
    INDEX idx_airdrops_wallet (user_wallet)
);

-- ============================================================================
-- RAID BOT DATA
-- ============================================================================

CREATE TABLE IF NOT EXISTS raid_campaigns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_name TEXT NOT NULL,
    target_platform TEXT,
    target_url TEXT,
    hashtags TEXT,
    participant_count INTEGER DEFAULT 0,
    status TEXT DEFAULT 'active',
    started_at TEXT DEFAULT CURRENT_TIMESTAMP,
    ended_at TEXT,
    INDEX idx_raids_status (status)
);

CREATE TABLE IF NOT EXISTS raid_participants (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    contribution_count INTEGER DEFAULT 0,
    points_earned INTEGER DEFAULT 0,
    joined_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (campaign_id) REFERENCES raid_campaigns(id),
    UNIQUE(campaign_id, user_id),
    INDEX idx_raid_users_campaign (campaign_id)
);

-- ============================================================================
-- TWITTER/X ENGAGEMENT
-- ============================================================================

CREATE TABLE IF NOT EXISTS twitter_engagement (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tweet_id TEXT UNIQUE NOT NULL,
    author_username TEXT,
    content TEXT,
    likes INTEGER DEFAULT 0,
    retweets INTEGER DEFAULT 0,
    replies INTEGER DEFAULT 0,
    engagement_score REAL,
    posted_at TEXT,
    analyzed_at TEXT DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_twitter_author (author_username),
    INDEX idx_twitter_score (engagement_score DESC)
);

-- ============================================================================
-- AGGREGATED VIEWS
-- ============================================================================

CREATE VIEW IF NOT EXISTS v_daily_llm_costs AS
SELECT 
    DATE(timestamp) AS date,
    provider,
    SUM(total_tokens) AS total_tokens,
    SUM(cost_usd) AS total_cost_usd,
    COUNT(*) AS request_count
FROM llm_costs
GROUP BY DATE(timestamp), provider;

CREATE VIEW IF NOT EXISTS v_top_tokens_by_sentiment AS
SELECT 
    ts.symbol,
    ts.token_mint,
    ts.sentiment_score,
    ts.total_mentions,
    COUNT(tt.id) AS trade_count,
    AVG(tt.pnl_pct) AS avg_pnl_pct
FROM token_sentiment ts
LEFT JOIN (SELECT * FROM jarvis_core.trades) tt 
    ON ts.token_mint = tt.token_mint
WHERE ts.analyzed_at > datetime('now', '-7 days')
GROUP BY ts.token_mint
ORDER BY ts.sentiment_score DESC, ts.total_mentions DESC
LIMIT 100;

-- ============================================================================
-- MIGRATION NOTES
-- ============================================================================

/*
CONSOLIDATED FROM:
- data/llm_costs.db: llm_costs, api_usage
- data/metrics.db, health.db, bot_health.db: system_metrics, health_checks
- data/jarvis_memory.db, telegram_memory.db, jarvis_x_memory.db: conversation_memory, user_preferences
- data/sentiment.db: token_sentiment, social_signals
- data/community/achievements.db: user_achievements,leaderboard
- data/whales.db: whale_wallets, whale_transactions
- data/research.db: token_research
- data/call_tracking.db: token_calls
- data/backtests.db: backtest_results
- data/tax.db: tax_events
- data/distributions.db: airdrops
- data/raid_bot.db: raid_campaigns, raid_participants
- bots/twitter/engagement.db: twitter_engagement

ENHANCEMENTS:
- Consolidated 15 databases into single analytics DB
- Added proper indexes for time-series queries
- Created aggregation views for common reports
- Normalized social/sentiment data across platforms
- Added metadata_json for extensibility

TOTAL TABLES: 26 tables + 2 views
*/
