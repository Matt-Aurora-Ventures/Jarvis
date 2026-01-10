-- Credit System Database Schema
-- PostgreSQL migration for JARVIS credit/payment system

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- =============================================================================
-- Users Table
-- =============================================================================

CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    wallet_address VARCHAR(44) UNIQUE,  -- Solana wallet
    email VARCHAR(255) UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    tier VARCHAR(20) NOT NULL DEFAULT 'free' CHECK (tier IN ('free', 'starter', 'pro', 'whale')),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    metadata JSONB DEFAULT '{}'::jsonb
);

CREATE INDEX idx_users_wallet ON users(wallet_address);
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_tier ON users(tier);

-- =============================================================================
-- Credit Balances
-- =============================================================================

CREATE TABLE credit_balances (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    balance INTEGER NOT NULL DEFAULT 0 CHECK (balance >= 0),
    lifetime_credits INTEGER NOT NULL DEFAULT 0,
    points INTEGER NOT NULL DEFAULT 0,  -- Loyalty points
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(user_id)
);

CREATE INDEX idx_credit_balances_user ON credit_balances(user_id);

-- =============================================================================
-- Credit Transactions
-- =============================================================================

CREATE TABLE credit_transactions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    amount INTEGER NOT NULL,  -- Positive = credit, negative = debit
    balance_after INTEGER NOT NULL,
    transaction_type VARCHAR(50) NOT NULL CHECK (
        transaction_type IN ('purchase', 'consumption', 'refund', 'bonus', 'adjustment', 'expiry')
    ),
    description TEXT,
    reference_id VARCHAR(255),  -- Stripe payment ID, API request ID, etc.
    idempotency_key VARCHAR(255) UNIQUE,  -- Prevent duplicate transactions
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_credit_transactions_user ON credit_transactions(user_id);
CREATE INDEX idx_credit_transactions_type ON credit_transactions(transaction_type);
CREATE INDEX idx_credit_transactions_reference ON credit_transactions(reference_id);
CREATE INDEX idx_credit_transactions_created ON credit_transactions(created_at);

-- =============================================================================
-- Credit Packages
-- =============================================================================

CREATE TABLE credit_packages (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(50) NOT NULL UNIQUE,
    credits INTEGER NOT NULL,
    bonus_credits INTEGER NOT NULL DEFAULT 0,
    price_cents INTEGER NOT NULL,  -- USD cents
    points INTEGER NOT NULL DEFAULT 0,  -- Loyalty points awarded
    stripe_price_id VARCHAR(255),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Insert default packages
INSERT INTO credit_packages (name, credits, bonus_credits, price_cents, points, is_active) VALUES
    ('starter', 100, 0, 2500, 25, TRUE),
    ('pro', 500, 50, 10000, 150, TRUE),
    ('whale', 3000, 500, 50000, 1000, TRUE);

-- =============================================================================
-- Payment Records
-- =============================================================================

CREATE TABLE payments (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    package_id UUID REFERENCES credit_packages(id),
    stripe_payment_id VARCHAR(255) UNIQUE,
    stripe_checkout_session_id VARCHAR(255) UNIQUE,
    amount_cents INTEGER NOT NULL,
    currency VARCHAR(3) NOT NULL DEFAULT 'USD',
    status VARCHAR(50) NOT NULL CHECK (
        status IN ('pending', 'completed', 'failed', 'refunded', 'disputed')
    ),
    credits_granted INTEGER,
    processed_at TIMESTAMPTZ,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_payments_user ON payments(user_id);
CREATE INDEX idx_payments_stripe ON payments(stripe_payment_id);
CREATE INDEX idx_payments_session ON payments(stripe_checkout_session_id);
CREATE INDEX idx_payments_status ON payments(status);

-- =============================================================================
-- API Usage Logs
-- =============================================================================

CREATE TABLE api_usage_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    endpoint VARCHAR(255) NOT NULL,
    method VARCHAR(10) NOT NULL,
    credits_consumed INTEGER NOT NULL DEFAULT 0,
    response_status INTEGER,
    response_time_ms INTEGER,
    ip_address INET,
    user_agent TEXT,
    request_id VARCHAR(255),
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Partition by month for performance
CREATE INDEX idx_api_usage_user ON api_usage_logs(user_id);
CREATE INDEX idx_api_usage_endpoint ON api_usage_logs(endpoint);
CREATE INDEX idx_api_usage_created ON api_usage_logs(created_at);

-- =============================================================================
-- Rate Limit State (for distributed rate limiting)
-- =============================================================================

CREATE TABLE rate_limit_state (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    key VARCHAR(255) NOT NULL UNIQUE,  -- user_id:endpoint or ip:endpoint
    count INTEGER NOT NULL DEFAULT 0,
    window_start TIMESTAMPTZ NOT NULL,
    window_seconds INTEGER NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_rate_limit_key ON rate_limit_state(key);
CREATE INDEX idx_rate_limit_window ON rate_limit_state(window_start);

-- =============================================================================
-- Staking Records (off-chain tracking)
-- =============================================================================

CREATE TABLE staking_records (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    wallet_address VARCHAR(44) NOT NULL,
    amount_tokens BIGINT NOT NULL,
    stake_signature VARCHAR(88),
    stake_time TIMESTAMPTZ NOT NULL,
    unstake_time TIMESTAMPTZ,
    unstake_signature VARCHAR(88),
    rewards_claimed BIGINT NOT NULL DEFAULT 0,
    multiplier DECIMAL(3, 2) NOT NULL DEFAULT 1.0,
    status VARCHAR(20) NOT NULL CHECK (
        status IN ('active', 'cooldown', 'unstaked')
    ),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_staking_user ON staking_records(user_id);
CREATE INDEX idx_staking_wallet ON staking_records(wallet_address);
CREATE INDEX idx_staking_status ON staking_records(status);

-- =============================================================================
-- Fee Collection Records
-- =============================================================================

CREATE TABLE fee_collections (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    amount_lamports BIGINT NOT NULL,
    amount_sol DECIMAL(20, 9) NOT NULL,
    signature VARCHAR(88) NOT NULL UNIQUE,
    destination_wallet VARCHAR(44) NOT NULL,
    source VARCHAR(50) NOT NULL CHECK (source IN ('bags_partner', 'trading', 'staking')),
    collected_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    distributed BOOLEAN NOT NULL DEFAULT FALSE,
    distribution_id UUID,
    metadata JSONB DEFAULT '{}'::jsonb
);

CREATE INDEX idx_fee_collections_source ON fee_collections(source);
CREATE INDEX idx_fee_collections_distributed ON fee_collections(distributed);

-- =============================================================================
-- Treasury Distributions
-- =============================================================================

CREATE TABLE treasury_distributions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    total_amount_lamports BIGINT NOT NULL,
    staking_amount BIGINT NOT NULL,  -- 60%
    operations_amount BIGINT NOT NULL,  -- 25%
    development_amount BIGINT NOT NULL,  -- 15%
    staking_signature VARCHAR(88),
    operations_signature VARCHAR(88),
    development_signature VARCHAR(88),
    status VARCHAR(20) NOT NULL CHECK (
        status IN ('pending', 'processing', 'completed', 'failed')
    ),
    distributed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    metadata JSONB DEFAULT '{}'::jsonb
);

CREATE INDEX idx_treasury_distributions_status ON treasury_distributions(status);

-- =============================================================================
-- Event Log (for analytics)
-- =============================================================================

CREATE TABLE event_log (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    event_type VARCHAR(100) NOT NULL,
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    properties JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_event_log_type ON event_log(event_type);
CREATE INDEX idx_event_log_user ON event_log(user_id);
CREATE INDEX idx_event_log_created ON event_log(created_at);

-- Partial index for recent events
CREATE INDEX idx_event_log_recent ON event_log(created_at)
    WHERE created_at > NOW() - INTERVAL '7 days';

-- =============================================================================
-- Aggregated Metrics (for dashboard)
-- =============================================================================

CREATE TABLE metrics_hourly (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    hour TIMESTAMPTZ NOT NULL,
    metric_name VARCHAR(100) NOT NULL,
    value DECIMAL(20, 4) NOT NULL,
    dimensions JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(hour, metric_name, dimensions)
);

CREATE INDEX idx_metrics_hourly_hour ON metrics_hourly(hour);
CREATE INDEX idx_metrics_hourly_name ON metrics_hourly(metric_name);

CREATE TABLE metrics_daily (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    date DATE NOT NULL,
    metric_name VARCHAR(100) NOT NULL,
    value DECIMAL(20, 4) NOT NULL,
    dimensions JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(date, metric_name, dimensions)
);

CREATE INDEX idx_metrics_daily_date ON metrics_daily(date);
CREATE INDEX idx_metrics_daily_name ON metrics_daily(metric_name);

-- =============================================================================
-- Functions
-- =============================================================================

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Apply to tables
CREATE TRIGGER update_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_credit_balances_updated_at
    BEFORE UPDATE ON credit_balances
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_payments_updated_at
    BEFORE UPDATE ON payments
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_staking_records_updated_at
    BEFORE UPDATE ON staking_records
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Function to safely consume credits
CREATE OR REPLACE FUNCTION consume_credits(
    p_user_id UUID,
    p_amount INTEGER,
    p_description TEXT,
    p_reference_id VARCHAR(255),
    p_idempotency_key VARCHAR(255)
) RETURNS TABLE(success BOOLEAN, new_balance INTEGER, message TEXT) AS $$
DECLARE
    v_current_balance INTEGER;
    v_new_balance INTEGER;
BEGIN
    -- Check for existing transaction with same idempotency key
    IF EXISTS (SELECT 1 FROM credit_transactions WHERE idempotency_key = p_idempotency_key) THEN
        RETURN QUERY SELECT FALSE, -1, 'Duplicate transaction'::TEXT;
        RETURN;
    END IF;

    -- Lock and get current balance
    SELECT balance INTO v_current_balance
    FROM credit_balances
    WHERE user_id = p_user_id
    FOR UPDATE;

    IF v_current_balance IS NULL THEN
        RETURN QUERY SELECT FALSE, 0, 'No balance found'::TEXT;
        RETURN;
    END IF;

    IF v_current_balance < p_amount THEN
        RETURN QUERY SELECT FALSE, v_current_balance, 'Insufficient credits'::TEXT;
        RETURN;
    END IF;

    -- Update balance
    v_new_balance := v_current_balance - p_amount;
    UPDATE credit_balances SET balance = v_new_balance WHERE user_id = p_user_id;

    -- Record transaction
    INSERT INTO credit_transactions (user_id, amount, balance_after, transaction_type, description, reference_id, idempotency_key)
    VALUES (p_user_id, -p_amount, v_new_balance, 'consumption', p_description, p_reference_id, p_idempotency_key);

    RETURN QUERY SELECT TRUE, v_new_balance, 'Success'::TEXT;
END;
$$ LANGUAGE plpgsql;

-- Function to add credits
CREATE OR REPLACE FUNCTION add_credits(
    p_user_id UUID,
    p_amount INTEGER,
    p_transaction_type VARCHAR(50),
    p_description TEXT,
    p_reference_id VARCHAR(255),
    p_idempotency_key VARCHAR(255)
) RETURNS TABLE(success BOOLEAN, new_balance INTEGER, message TEXT) AS $$
DECLARE
    v_current_balance INTEGER;
    v_new_balance INTEGER;
BEGIN
    -- Check for existing transaction with same idempotency key
    IF EXISTS (SELECT 1 FROM credit_transactions WHERE idempotency_key = p_idempotency_key) THEN
        RETURN QUERY SELECT FALSE, -1, 'Duplicate transaction'::TEXT;
        RETURN;
    END IF;

    -- Get or create balance
    INSERT INTO credit_balances (user_id, balance, lifetime_credits)
    VALUES (p_user_id, 0, 0)
    ON CONFLICT (user_id) DO NOTHING;

    -- Lock and update balance
    SELECT balance INTO v_current_balance
    FROM credit_balances
    WHERE user_id = p_user_id
    FOR UPDATE;

    v_new_balance := v_current_balance + p_amount;

    UPDATE credit_balances
    SET balance = v_new_balance,
        lifetime_credits = lifetime_credits + p_amount
    WHERE user_id = p_user_id;

    -- Record transaction
    INSERT INTO credit_transactions (user_id, amount, balance_after, transaction_type, description, reference_id, idempotency_key)
    VALUES (p_user_id, p_amount, v_new_balance, p_transaction_type, p_description, p_reference_id, p_idempotency_key);

    RETURN QUERY SELECT TRUE, v_new_balance, 'Success'::TEXT;
END;
$$ LANGUAGE plpgsql;

-- =============================================================================
-- Views
-- =============================================================================

-- User credit summary view
CREATE VIEW user_credit_summary AS
SELECT
    u.id AS user_id,
    u.wallet_address,
    u.email,
    u.tier,
    COALESCE(cb.balance, 0) AS current_balance,
    COALESCE(cb.lifetime_credits, 0) AS lifetime_credits,
    COALESCE(cb.points, 0) AS points,
    COUNT(DISTINCT ct.id) AS transaction_count,
    SUM(CASE WHEN ct.amount < 0 THEN ABS(ct.amount) ELSE 0 END) AS total_consumed,
    u.created_at
FROM users u
LEFT JOIN credit_balances cb ON u.id = cb.user_id
LEFT JOIN credit_transactions ct ON u.id = ct.user_id
GROUP BY u.id, u.wallet_address, u.email, u.tier, cb.balance, cb.lifetime_credits, cb.points, u.created_at;

-- Daily revenue view
CREATE VIEW daily_revenue AS
SELECT
    DATE(p.created_at) AS date,
    COUNT(*) AS transaction_count,
    SUM(p.amount_cents) AS total_cents,
    SUM(p.credits_granted) AS total_credits_granted,
    COUNT(DISTINCT p.user_id) AS unique_users
FROM payments p
WHERE p.status = 'completed'
GROUP BY DATE(p.created_at)
ORDER BY date DESC;
