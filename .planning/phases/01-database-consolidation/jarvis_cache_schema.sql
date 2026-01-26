-- ============================================================================
-- JARVIS CACHE DATABASE - Unified Schema Design
-- ============================================================================
-- Purpose: Temporary/ephemeral data that can be rebuilt
-- Access Pattern: Variable (can spike), short-lived data
-- Backup: None needed (can rebuild from source)
-- Phase: 1.3 - Database Consolidation
-- ============================================================================

-- ============================================================================
-- API RATE LIMITING
-- ============================================================================

CREATE TABLE IF NOT EXISTS rate_limit_state (
    id TEXT PRIMARY KEY, -- user_id:api_name or IP:endpoint
    request_count INTEGER DEFAULT 0,
    window_start TEXT DEFAULT CURRENT_TIMESTAMP,
    last_request TEXT DEFAULT CURRENT_TIMESTAMP,
    blocked_until TEXT
);

CREATE TABLE IF NOT EXISTS rate_limit_violations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    identifier TEXT NOT NULL, -- user_id or IP
    api_name TEXT,
    violation_count INTEGER DEFAULT 1,
    blocked_duration_seconds INTEGER,
    violated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================================
-- SESSION CACHE
-- ============================================================================

CREATE TABLE IF NOT EXISTS session_cache (
    session_id TEXT PRIMARY KEY,
    user_id INTEGER,
    session_type TEXT, -- 'web', 'telegram', 'api'
    data_json TEXT NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    expires_at TEXT NOT NULL,
    last_accessed TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS websocket_subscriptions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    connection_id TEXT NOT NULL,
    user_id INTEGER,
    subscription_type TEXT NOT NULL, -- 'token_price', 'portfolio', 'trades'
    params_json TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================================
-- API RESPONSE CACHE
-- ============================================================================

CREATE TABLE IF NOT EXISTS api_cache (
    cache_key TEXT PRIMARY KEY,
    api_name TEXT NOT NULL,
    endpoint TEXT,
    response_data TEXT NOT NULL,
    status_code INTEGER DEFAULT 200,
    cached_at TEXT DEFAULT CURRENT_TIMESTAMP,
    expires_at TEXT NOT NULL,
    hit_count INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS price_cache (
    token_mint TEXT PRIMARY KEY,
    price_usd REAL NOT NULL,
    price_sol REAL,
    volume_24h_usd REAL,
    price_change_24h_pct REAL,
    source TEXT, -- 'jupiter', 'dexscreener', 'coingecko'
    cached_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================================
-- FILE CACHE
-- ============================================================================

CREATE TABLE IF NOT EXISTS file_cache (
    file_path TEXT PRIMARY KEY,
    file_hash TEXT NOT NULL,
    file_size_bytes INTEGER,
    mime_type TEXT,
    storage_location TEXT, -- 's3', 'local', 'cdn'
    cached_at TEXT DEFAULT CURRENT_TIMESTAMP,
    accessed_at TEXT DEFAULT CURRENT_TIMESTAMP,
    access_count INTEGER DEFAULT 0,
    expires_at TEXT
);

-- ============================================================================
-- SPAM PROTECTION
-- ============================================================================

CREATE TABLE IF NOT EXISTS spam_users (
    user_id INTEGER PRIMARY KEY,
    telegram_user_id INTEGER UNIQUE,
    spam_score REAL DEFAULT 0, -- 0-1, higher = more likely spam
    message_count_24h INTEGER DEFAULT 0,
    last_message_at TEXT,
    is_banned BOOLEAN DEFAULT 0,
    ban_reason TEXT,
    banned_at TEXT
);

CREATE TABLE IF NOT EXISTS spam_patterns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pattern_type TEXT NOT NULL, -- 'regex', 'keyword', 'behavior'
    pattern_value TEXT NOT NULL,
    severity INTEGER DEFAULT 1, -- 1-10
    action TEXT DEFAULT 'flag', -- 'flag', 'warn', 'ban'
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT 1
);

CREATE TABLE IF NOT EXISTS user_reputation (
    user_id INTEGER PRIMARY KEY,
    reputation_score INTEGER DEFAULT 100, -- 0-1000
    trust_level TEXT DEFAULT 'new', -- 'new', 'trusted', 'verified', 'flagged'
    reports_received INTEGER DEFAULT 0,
    reports_made INTEGER DEFAULT 0,
    helpful_count INTEGER DEFAULT 0,
    last_updated TEXT DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================================
-- TEMPORARY COMPUTATION CACHE
-- ============================================================================

CREATE TABLE IF NOT EXISTS computation_cache (
    computation_id TEXT PRIMARY KEY,
    computation_type TEXT NOT NULL, -- 'backtest', 'sentiment_analysis', 'portfolio_optimization'
    input_hash TEXT NOT NULL,
    result_json TEXT NOT NULL,
    computation_time_ms INTEGER,
    cached_at TEXT DEFAULT CURRENT_TIMESTAMP,
    expires_at TEXT,
    hit_count INTEGER DEFAULT 0
);

-- ============================================================================
-- TELEGRAM STATE CACHE
-- ============================================================================

CREATE TABLE IF NOT EXISTS telegram_state (
    user_id INTEGER PRIMARY KEY,
    conversation_state TEXT, -- 'awaiting_token', 'awaiting_amount', 'confirming_trade'
    state_data_json TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    expires_at TEXT
);

CREATE TABLE IF NOT EXISTS telegram_message_cache (
    message_id INTEGER PRIMARY KEY,
    chat_id INTEGER NOT NULL,
    user_id INTEGER,
    message_text TEXT,
    has_inline_keyboard BOOLEAN DEFAULT 0,
    sent_at TEXT DEFAULT CURRENT_TIMESTAMP,
    expires_at TEXT
);

-- ============================================================================
-- CUSTOM/TEMPORARY DATA
-- ============================================================================

CREATE TABLE IF NOT EXISTS kv_cache (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    category TEXT, -- For grouping related keys
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    expires_at TEXT
);

-- ============================================================================
-- CLEANUP TRIGGERS (Auto-delete expired data)
-- ============================================================================

-- Auto-cleanup expired sessions
CREATE TRIGGER IF NOT EXISTS cleanup_expired_sessions
AFTER INSERT ON session_cache
BEGIN
    DELETE FROM session_cache 
    WHERE expires_at < datetime('now');
END;

-- Auto-cleanup expired API cache
CREATE TRIGGER IF NOT EXISTS cleanup_expired_api_cache
AFTER INSERT ON api_cache
BEGIN
    DELETE FROM api_cache 
    WHERE expires_at < datetime('now');
END;

-- Auto-cleanup expired computations
CREATE TRIGGER IF NOT EXISTS cleanup_expired_computations
AFTER INSERT ON computation_cache
BEGIN
    DELETE FROM computation_cache 
    WHERE expires_at < datetime('now')
       OR (hit_count = 0 AND cached_at < datetime('now', '-7 days'));
END;

-- Auto-cleanup old rate limit data
CREATE TRIGGER IF NOT EXISTS cleanup_old_rate_limits
AFTER INSERT ON rate_limit_state
BEGIN
    DELETE FROM rate_limit_state 
    WHERE window_start < datetime('now', '-1 hour');
END;

-- Auto-cleanup expired Telegram state
CREATE TRIGGER IF NOT EXISTS cleanup_expired_telegram_state
AFTER INSERT ON telegram_state
BEGIN
    DELETE FROM telegram_state 
    WHERE expires_at < datetime('now');
END;

-- Auto-cleanup old Telegram messages
CREATE TRIGGER IF NOT EXISTS cleanup_old_telegram_messages
AFTER INSERT ON telegram_message_cache
BEGIN
    DELETE FROM telegram_message_cache 
    WHERE expires_at < datetime('now')
        OR sent_at < datetime('now', '-24 hours');
END;

-- ============================================================================
-- UTILITY VIEWS
-- ============================================================================

CREATE VIEW IF NOT EXISTS v_cache_stats AS
SELECT 
    'api_cache' AS cache_type,
    COUNT(*) AS entry_count,
    SUM(hit_count) AS total_hits,
    AVG(hit_count) AS avg_hits
FROM api_cache
UNION ALL
SELECT 
    'price_cache',
    COUNT(*),
    0,
    0
FROM price_cache
UNION ALL
SELECT 
    'file_cache',
    COUNT(*),
    SUM(access_count),
    AVG(access_count)
FROM file_cache
UNION ALL
SELECT 
    'computation_cache',
    COUNT(*),
    SUM(hit_count),
    AVG(hit_count)
FROM computation_cache;

CREATE VIEW IF NOT EXISTS v_active_sessions AS
SELECT 
    session_id,
    user_id,
    session_type,
    created_at,
    expires_at,
    last_accessed,
    ROUND((julianday(expires_at) - julianday('now')) * 24, 2) AS hours_remaining
FROM session_cache
WHERE expires_at > datetime('now')
ORDER BY last_accessed DESC;

-- ============================================================================
-- MIGRATION NOTES
-- ============================================================================

/*
CONSOLIDATED FROM:
- data/cache/file_cache.db: file_cache
- data/rate_limiter.db: rate_limit_state, rate_limit_violations
- data/jarvis_spam_protection.db: spam_users, spam_patterns, user_reputation
- data/custom.db: kv_cache
- Session data from multiple sources
- WebSocket subscriptions
- API caches

ENHANCEMENTS:
- Added auto-cleanup triggers for expired data
- Added cache hit tracking for optimization
- Separated rate limiting from spam protection
- Added computation cache for expensive operations
- Created cache statistics views
- Added TTL (Time To Live) on all cache entries

TOTAL TABLES: 13 tables + 2 views
TOTAL TRIGGERS: 6 auto-cleanup triggers

MAINTENANCE:
- No backup needed - all data is ephemeral
- Can be cleared with: DELETE FROM table_name;
- Triggers auto-clean expired data
- Optional: VACUUM every week to reclaim space
*/


-- ============================================================================
-- FIXED INDEXES (Moved from inline)
-- ============================================================================

CREATE INDEX IF NOT EXISTS idx_rate_limit_window ON rate_limit_state(window_start);
CREATE INDEX IF NOT EXISTS idx_violations_identifier ON rate_limit_violations(identifier);
CREATE INDEX IF NOT EXISTS idx_violations_api ON rate_limit_violations(api_name);
CREATE INDEX IF NOT EXISTS idx_session_user ON session_cache(user_id);
CREATE INDEX IF NOT EXISTS idx_session_expires ON session_cache(expires_at);
CREATE INDEX IF NOT EXISTS idx_ws_connection ON websocket_subscriptions(connection_id);
CREATE INDEX IF NOT EXISTS idx_ws_user ON websocket_subscriptions(user_id);
CREATE INDEX IF NOT EXISTS idx_ws_type ON websocket_subscriptions(subscription_type);
CREATE INDEX IF NOT EXISTS idx_cache_api ON api_cache(api_name);
CREATE INDEX IF NOT EXISTS idx_cache_expires ON api_cache(expires_at);
CREATE INDEX IF NOT EXISTS idx_price_cached ON price_cache(cached_at);
CREATE INDEX IF NOT EXISTS idx_file_hash ON file_cache(file_hash);
CREATE INDEX IF NOT EXISTS idx_file_expires ON file_cache(expires_at);
CREATE INDEX IF NOT EXISTS idx_spam_score ON spam_users(spam_score DESC);
CREATE INDEX IF NOT EXISTS idx_spam_banned ON spam_users(is_banned);
CREATE INDEX IF NOT EXISTS idx_patterns_active ON spam_patterns(is_active);
CREATE INDEX IF NOT EXISTS idx_reputation_score ON user_reputation(reputation_score DESC);
CREATE INDEX IF NOT EXISTS idx_reputation_trust ON user_reputation(trust_level);
CREATE INDEX IF NOT EXISTS idx_comp_type ON computation_cache(computation_type);
CREATE INDEX IF NOT EXISTS idx_comp_hash ON computation_cache(input_hash);
CREATE INDEX IF NOT EXISTS idx_comp_expires ON computation_cache(expires_at);
CREATE INDEX IF NOT EXISTS idx_tg_state_expires ON telegram_state(expires_at);
CREATE INDEX IF NOT EXISTS idx_tg_msg_chat ON telegram_message_cache(chat_id);
CREATE INDEX IF NOT EXISTS idx_tg_msg_expires ON telegram_message_cache(expires_at);
CREATE INDEX IF NOT EXISTS idx_kv_category ON kv_cache(category);
CREATE INDEX IF NOT EXISTS idx_kv_expires ON kv_cache(expires_at);
