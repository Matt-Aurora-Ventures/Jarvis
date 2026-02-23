-- Agent Pipeline Tables — decision log, reflections, strategies, calibration

-- Decision log: every agent pipeline run
CREATE TABLE IF NOT EXISTS inv_decisions (
    id SERIAL PRIMARY KEY,
    basket_id VARCHAR(64) NOT NULL DEFAULT 'alpha',
    trigger_type VARCHAR(32) NOT NULL,
    action VARCHAR(32) NOT NULL,
    final_weights JSONB NOT NULL,
    previous_weights JSONB NOT NULL,
    basket_nav_usd NUMERIC(18, 2) NOT NULL,

    -- Individual agent reports
    grok_sentiment_report JSONB,
    claude_risk_report JSONB,
    chatgpt_macro_report JSONB,
    dexter_fundamental_report JSONB,

    -- Debate
    bull_thesis JSONB,
    bear_thesis JSONB,
    debate_rounds INTEGER DEFAULT 0,

    -- Risk officer
    risk_approved BOOLEAN NOT NULL,
    risk_veto_reason TEXT,

    -- Trader
    trader_confidence NUMERIC(4, 3),
    trader_reasoning TEXT,

    -- Execution
    tx_hash VARCHAR(128),
    gas_cost_usd NUMERIC(10, 4),
    execution_status VARCHAR(32) DEFAULT 'pending',

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_inv_decisions_basket ON inv_decisions(basket_id, created_at DESC);

-- Reflection outcomes
CREATE TABLE IF NOT EXISTS inv_reflections (
    id SERIAL PRIMARY KEY,
    decision_id INTEGER REFERENCES inv_decisions(id),
    data JSONB NOT NULL,
    calibration_hint TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Strategy library
CREATE TABLE IF NOT EXISTS inv_strategies (
    id SERIAL PRIMARY KEY,
    name VARCHAR(128) NOT NULL,
    conditions JSONB NOT NULL,
    recommended_action VARCHAR(32) NOT NULL,
    success_rate NUMERIC(4, 3),
    sample_size INTEGER DEFAULT 0,
    notes TEXT,
    active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Calibration hints cache
CREATE TABLE IF NOT EXISTS inv_calibration_hints (
    id SERIAL PRIMARY KEY,
    agent_name VARCHAR(64) NOT NULL,
    hint TEXT NOT NULL,
    hint_type VARCHAR(32) NOT NULL,
    weight NUMERIC(4, 3) DEFAULT 1.0,
    expires_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
