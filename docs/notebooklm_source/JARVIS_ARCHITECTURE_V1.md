# Jarvis V1 Architecture - Consolidated Source Document
> **For NotebookLM Ingestion**
> This document contains the complete architectural definition, schema designs, security models, and migration strategies for the Jarvis V1 Database Consolidation and Security Hardening project.

---

## 1. Executive Summary

**Project Phase:** 1 (Database Consolidation) & 6 (Security Audit)
**Goal:** Transition from a fragmented prototype architecture (30+ DBs, hardcoded secrets) to a unified, secure, production-grade system.

### Key Architectural Changes
1.  **Database Consolidation:** 
    - **Before:** 30+ fragmented SQLite files, no foreign keys, impossible to manage atomic transactions.
    - **After:** 3 Unified Databases (Core, Analytics, Cache) with strict normalization (3NF) and foreign key constraints.
2.  **Security Hardening:**
    - **Secrets:** Moved from `.env` to encrypted `SecretVault`.
    - **Wallet:** `ElonMusk987#` replaced with PBKDF2-HMAC-SHA256 + Fernet encryption (100k iterations).
    - **Validation:** Strict input sanitization for all user inputs (SQLi prevention).
    - **Rate Limiting:** Multi-window protection (Burst/Minute/Hour).

---

## 2. Database Architecture

### A. Core Database (`jarvis_core.db`)
**Purpose:** Mission-critical "Hot Path" data requiring ACID guarantees.
**Schema:**

```sql
-- USERS & AUTHENTICATION
CREATE TABLE users (
    user_id INTEGER PRIMARY KEY,
    telegram_user_id INTEGER UNIQUE NOT NULL,
    telegram_username TEXT,
    first_name TEXT,
    last_name TEXT,
    wallet_address TEXT UNIQUE,
    is_premium BOOLEAN DEFAULT 0,
    is_admin BOOLEAN DEFAULT 0,
    is_banned BOOLEAN DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    last_active_at TEXT,
    settings_json TEXT DEFAULT '{}'
);

CREATE INDEX idx_users_telegram ON users(telegram_user_id);
CREATE INDEX idx_users_wallet ON users(wallet_address);

CREATE TABLE user_sessions (
    session_id TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL,
    session_data TEXT, -- JSON blob
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    expires_at TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

CREATE INDEX idx_sessions_user ON user_sessions(user_id);
CREATE INDEX idx_sessions_expires ON user_sessions(expires_at);

CREATE TABLE admin_actions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    admin_user_id INTEGER NOT NULL,
    action_type TEXT NOT NULL,
    target_user_id INTEGER,
    reason TEXT,
    metadata_json TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (admin_user_id) REFERENCES users(user_id),
    FOREIGN KEY (target_user_id) REFERENCES users(user_id)
);

CREATE INDEX idx_admin_actions_admin ON admin_actions(admin_user_id);

-- TRADING & POSITIONS
CREATE TABLE positions (
    id TEXT PRIMARY KEY, -- UUID
    user_id INTEGER NOT NULL DEFAULT 0,
    symbol TEXT NOT NULL,
    token_mint TEXT NOT NULL,
    entry_price REAL NOT NULL,
    entry_amount_sol REAL NOT NULL,
    entry_amount_tokens REAL NOT NULL,
    take_profit_price REAL,
    stop_loss_price REAL,
    tp_order_id TEXT,
    sl_order_id TEXT,
    status TEXT DEFAULT 'open', -- 'open', 'closed', 'liquidated'
    exit_price REAL,
    exit_amount_sol REAL,
    pnl_sol REAL,
    pnl_pct REAL,
    opened_at TEXT DEFAULT CURRENT_TIMESTAMP,
    closed_at TEXT,
    tx_signature_entry TEXT,
    tx_signature_exit TEXT,
    metadata_json TEXT, -- Additional data
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

CREATE INDEX idx_positions_user ON positions(user_id);
CREATE INDEX idx_positions_token ON positions(token_mint);
CREATE INDEX idx_positions_status ON positions(status);

CREATE TABLE trades (
    id TEXT PRIMARY KEY, -- UUID
    user_id INTEGER NOT NULL DEFAULT 0,
    symbol TEXT NOT NULL,
    token_mint TEXT NOT NULL,
    side TEXT NOT NULL CHECK(side IN ('buy', 'sell')),
    amount_sol REAL NOT NULL,
    amount_tokens REAL NOT NULL,
    price REAL NOT NULL,
    slippage_pct REAL DEFAULT 1.0,
    priority_fee_lamports INTEGER DEFAULT 5000,
    timestamp TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    tx_signature TEXT UNIQUE,
    position_id TEXT,
    status TEXT DEFAULT 'pending', 
    error_message TEXT,
    execution_time_ms INTEGER,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    FOREIGN KEY (position_id) REFERENCES positions(id) ON DELETE SET NULL
);

CREATE INDEX idx_trades_user ON trades(user_id);
CREATE INDEX idx_trades_token ON trades(token_mint);
CREATE INDEX idx_trades_position ON trades(position_id);

CREATE TABLE orders (
    order_id TEXT PRIMARY KEY, -- UUID
    user_id INTEGER NOT NULL,
    position_id TEXT,
    order_type TEXT NOT NULL CHECK(order_type IN ('take_profit', 'stop_loss', 'limit', 'market')),
    side TEXT NOT NULL CHECK(side IN ('buy', 'sell')),
    token_mint TEXT NOT NULL,
    trigger_price REAL,
    limit_price REAL,
    amount_tokens REAL NOT NULL,
    status TEXT DEFAULT 'active',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    triggered_at TEXT,
    filled_at TEXT,
    cancelled_at TEXT,
    tx_signature TEXT,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    FOREIGN KEY (position_id) REFERENCES positions(id) ON DELETE CASCADE
);

CREATE INDEX idx_orders_user ON orders(user_id);
CREATE INDEX idx_orders_position ON orders(position_id);

CREATE TABLE bot_config (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER UNIQUE NOT NULL,
    trading_enabled BOOLEAN DEFAULT 1,
    max_position_size_sol REAL DEFAULT 10.0,
    max_positions INTEGER DEFAULT 5,
    default_slippage_pct REAL DEFAULT 1.0,
    auto_take_profit_pct REAL DEFAULT 100.0,
    auto_stop_loss_pct REAL DEFAULT 50.0,
    risk_level TEXT DEFAULT 'medium',
    notifications_enabled BOOLEAN DEFAULT 1,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

CREATE TABLE token_metadata (
    token_mint TEXT PRIMARY KEY,
    symbol TEXT,
    name TEXT,
    decimals INTEGER DEFAULT 9,
    logo_url TEXT,
    cached_at TEXT DEFAULT CURRENT_TIMESTAMP,
    is_verified BOOLEAN DEFAULT 0,
    is_scam BOOLEAN DEFAULT 0,
    metadata_json TEXT
);
```

### B. Analytics Database (`jarvis_analytics.db`)
**Purpose:** "Warm Path" historical data, AI memory, sentiment analysis.
**Key Tables:**
- `llm_costs`: Track token usage per provider/model.
- `conversation_memory`: Long-term AI memory storage.
- `token_sentiment`: Aggregated social sentiment scores (-1 to +1).
- `whale_tracking`: Wallet monitoring and large transaction logs.
- `backtest_results`: Strategy performance records.

### C. Cache Database (`jarvis_cache.db`)
**Purpose:** "Cold Path" or Ephemeral data. Auto-cleaning.
**Key Features:**
- **Auto-Cleanup Triggers:** Database automatically deletes expired rows.
- **Tables:**
    - `api_cache`: REST API responses.
    - `rate_limit_state`: Request counters.
    - `session_cache`: Web/Telegram sessions.
    - `spam_protection`: User reputation scores.

---

## 3. Security Infrastructure

### A. Secret Vault (`core/secrets/vault.py`)
Centralized secret management. Prevents accidental logging of keys.
- **Mechanism:** Stores secrets in memory only (environment variables loaded once).
- **Protection:** `__repr__` method overridden to return `***` instead of value.
- **Rotation:** Supports dynamic key updates.

### B. Encrypted Keystore (`core/wallet/keystore.py`)
Replaces insecure password storage.
- **Algorithm:** PBKDF2-HMAC-SHA256 (100,000 iterations) for key derivation.
- **Encryption:** Fernet (AES-128 via cryptography library).
- **Salt:** Random 16-byte salt per key.

### C. Rate Limiting (`core/rate_limiting.py`)
Multi-window protection against abuse.
- **Burst:** 5 requests / 10 seconds.
- **Sustained:** 30 requests / 1 minute.
- **Hourly:** 500 requests / 1 hour.
- **Storage:** Uses `jarvis_cache.db` for persistence across restarts.

### D. Input Validation (`core/security_validation.py`)
Prevents SQL Injection and malicious payloads.
- **Validators:** `validate_solana_address`, `sanitize_input`, `validate_json`.
- **Strategy:** All user input used in SQL queries MUST be parameterized or validated against an allowlist.

---

## 4. Migration Strategy

### "Big Bang" vs "Staged"
We are using a **Staged Migration** strategy to minimize risk.

1.  **Stage 1: Core Data (Completed)**
    - Migrate critical `positions` and `trades` to `jarvis_core.db`.
    - Validate row counts and integrity.
    
2.  **Stage 2: Analytics Data (Pending)**
    - Migrate high-volume logs (sentiment, LLM costs).
    - Can be done asynchronously.

3.  **Stage 3: Cache Data (Pending)**
    - Migrate active sessions.
    - Expired data is discarded during migration.

### Migration Tooling (`scripts/migrate_core_db.py`)
- **Safety:** Automatically creates a timestamped backup of source DBs before writing to target.
- **Validation:** Compares source row counts to target row counts.
- **Atomicity:** Uses SQLite transactions. If an error occurs, the target DB is rolled back (or can be discarded since it's a new file).
- **Driver:** Uses `cursor.executescript()` for DDL (schema) and `cursor.execute()` with parameter binding for DML (data) to prevent injection during migration.

---

## 5. Research & Justification

**Why SQLite?**
- Research confirms SQLite 3.39+ is sufficient for our concurrency needs (WAL mode enabled).
- Single-file Consolidated Schema is the industry best practice for SQLite (vs multiple files) because it ensures referential integrity (Foreign Keys).
- `executescript` vs `execute`: Research confirms `executescript` is correct for DDL (Schema) while `execute` is mandatory for DML (Data) to prevent injection. We follow this pattern strictly.

**Why Separate Analytics DB?**
- Analytics queries (aggregations, huge scans) can lock the database table (even in WAL mode) for write operations.
- Separating "Warm" analytics data prevents reporting queries from slowing down "Hot" trading execution.

---

## 6. Implementation Status (as of 2026-01-25)

- **Security:** 100% Implemented (Class A).
- **Core Database:** Schema defined, Migration script verified (dry-run success).
- **Analytics/Cache:** Schemas defined, Migration pending.
- **Demo Bot:** Critical bug fixed (Handler Priority).

This architecture provides the foundation for the **Solana Intelligence Unit** (Phase 8) by treating memory and data as first-class citizens.
