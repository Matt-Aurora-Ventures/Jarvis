-- ============================================================================
-- VIBE CODING REQUEST TRACKING
-- ============================================================================
-- Purpose: Track /vibe command usage for analytics and debugging
-- Added: Phase 3-01 (Vibe Command Implementation)
-- ============================================================================

CREATE TABLE IF NOT EXISTS vibe_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    username TEXT,
    chat_id INTEGER,
    request TEXT NOT NULL,
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    duration_seconds REAL,
    status TEXT CHECK(status IN ('success', 'error', 'timeout', 'rate_limited', 'concurrent_blocked')) NOT NULL,
    error_message TEXT,
    response_length INTEGER, -- Character count of response
    chunks_sent INTEGER DEFAULT 1, -- Number of chunks sent to Telegram
    tokens_used INTEGER DEFAULT 0, -- Total tokens (input + output)
    sanitized BOOLEAN DEFAULT 0, -- Whether output was sanitized
    session_message_count INTEGER DEFAULT 0, -- How many messages in the session
    FOREIGN KEY (user_id) REFERENCES users(telegram_id)
);

CREATE INDEX IF NOT EXISTS idx_vibe_user ON vibe_requests(user_id);
CREATE INDEX IF NOT EXISTS idx_vibe_status ON vibe_requests(status);
CREATE INDEX IF NOT EXISTS idx_vibe_started ON vibe_requests(started_at);

-- ============================================================================
-- AGGREGATION VIEW
-- ============================================================================

CREATE VIEW IF NOT EXISTS v_vibe_daily_stats AS
SELECT
    DATE(started_at) AS date,
    COUNT(*) AS total_requests,
    SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) AS successful_requests,
    SUM(CASE WHEN status = 'error' THEN 1 ELSE 0 END) AS error_requests,
    SUM(CASE WHEN status = 'timeout' THEN 1 ELSE 0 END) AS timeout_requests,
    SUM(CASE WHEN status = 'concurrent_blocked' THEN 1 ELSE 0 END) AS concurrent_blocked,
    AVG(duration_seconds) AS avg_duration_seconds,
    SUM(tokens_used) AS total_tokens_used,
    AVG(tokens_used) AS avg_tokens_per_request
FROM vibe_requests
WHERE started_at IS NOT NULL
GROUP BY DATE(started_at)
ORDER BY date DESC;
