-- CCTP Bridge Tables — job tracking, fee accounting

CREATE TABLE IF NOT EXISTS inv_bridge_jobs (
    id SERIAL PRIMARY KEY,
    amount_usdc NUMERIC(18, 6) NOT NULL,
    amount_raw BIGINT NOT NULL,
    state VARCHAR(32) NOT NULL DEFAULT 'FEE_COLLECTED',

    -- Base (EVM) side
    approve_tx_hash VARCHAR(128),
    burn_tx_hash VARCHAR(128),
    cctp_nonce BIGINT,
    message_hash VARCHAR(128),

    -- Attestation
    attestation TEXT,

    -- Solana side
    mint_tx_hash VARCHAR(128),
    deposit_tx_hash VARCHAR(128),

    -- Fee accounting
    bridge_fee_usdc NUMERIC(18, 6) DEFAULT 0,
    gas_cost_usd NUMERIC(10, 4) DEFAULT 0,
    net_deposited_usdc NUMERIC(18, 6),

    -- Error handling
    error TEXT,
    retry_count INTEGER DEFAULT 0,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_inv_bridge_state ON inv_bridge_jobs(state);
CREATE INDEX IF NOT EXISTS idx_inv_bridge_created ON inv_bridge_jobs(created_at DESC);
