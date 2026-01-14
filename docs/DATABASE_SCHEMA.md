# JARVIS Database Schema Documentation

## Overview

JARVIS uses SQLite for local development and PostgreSQL for production. The schema supports trading operations, user management, conversation history, and system monitoring.

---

## Tables

### users

Stores user account information.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | TEXT | PRIMARY KEY | Unique user identifier |
| email | TEXT | UNIQUE, NOT NULL | User email address |
| api_key | TEXT | UNIQUE | API key for authentication |
| created_at | TIMESTAMP | NOT NULL, DEFAULT NOW | Account creation time |
| updated_at | TIMESTAMP | NOT NULL | Last update time |
| is_active | BOOLEAN | DEFAULT TRUE | Account active status |
| role | TEXT | DEFAULT 'user' | User role (user, admin) |
| settings | JSON | DEFAULT '{}' | User preferences |

**Indexes:**
- `idx_users_email` on `email`
- `idx_users_api_key` on `api_key`

---

### conversations

Stores chat conversation metadata.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | TEXT | PRIMARY KEY | Unique conversation ID |
| user_id | TEXT | FOREIGN KEY → users.id | Owner user |
| title | TEXT | | Conversation title |
| created_at | TIMESTAMP | NOT NULL | Creation time |
| updated_at | TIMESTAMP | NOT NULL | Last message time |
| is_archived | BOOLEAN | DEFAULT FALSE | Archive status |
| metadata | JSON | DEFAULT '{}' | Extra metadata |

**Indexes:**
- `idx_conversations_user_id` on `user_id`
- `idx_conversations_updated` on `updated_at`

---

### messages

Stores individual chat messages.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | TEXT | PRIMARY KEY | Unique message ID |
| conversation_id | TEXT | FOREIGN KEY → conversations.id | Parent conversation |
| role | TEXT | NOT NULL | 'user', 'assistant', 'system' |
| content | TEXT | NOT NULL | Message content |
| created_at | TIMESTAMP | NOT NULL | Message timestamp |
| tokens_used | INTEGER | | Tokens consumed |
| model | TEXT | | LLM model used |
| latency_ms | INTEGER | | Response latency |
| metadata | JSON | DEFAULT '{}' | Extra metadata |

**Indexes:**
- `idx_messages_conversation` on `conversation_id`
- `idx_messages_created` on `created_at`

---

### trades

Stores executed trades.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | TEXT | PRIMARY KEY | Unique trade ID |
| user_id | TEXT | FOREIGN KEY → users.id | Trade owner |
| symbol | TEXT | NOT NULL | Trading pair (e.g., SOL/USDC) |
| side | TEXT | NOT NULL | 'buy' or 'sell' |
| amount | DECIMAL(20,8) | NOT NULL | Trade quantity |
| price | DECIMAL(20,8) | NOT NULL | Execution price |
| total_usd | DECIMAL(20,2) | NOT NULL | Total value in USD |
| fee | DECIMAL(20,8) | | Transaction fee |
| status | TEXT | NOT NULL | pending, filled, failed, cancelled |
| created_at | TIMESTAMP | NOT NULL | Order creation time |
| executed_at | TIMESTAMP | | Execution time |
| tx_hash | TEXT | | Blockchain transaction hash |
| metadata | JSON | DEFAULT '{}' | Extra data |

**Indexes:**
- `idx_trades_user_id` on `user_id`
- `idx_trades_symbol` on `symbol`
- `idx_trades_created` on `created_at`
- `idx_trades_status` on `status`

---

### portfolio_snapshots

Stores periodic portfolio snapshots.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | TEXT | PRIMARY KEY | Unique snapshot ID |
| user_id | TEXT | FOREIGN KEY → users.id | Portfolio owner |
| timestamp | TIMESTAMP | NOT NULL | Snapshot time |
| total_value_usd | DECIMAL(20,2) | NOT NULL | Total portfolio value |
| holdings | JSON | NOT NULL | Holdings breakdown |
| pnl_24h | DECIMAL(20,2) | | 24h P&L |
| pnl_7d | DECIMAL(20,2) | | 7d P&L |
| pnl_30d | DECIMAL(20,2) | | 30d P&L |

**Indexes:**
- `idx_portfolio_user_time` on `(user_id, timestamp)`

---

### alerts

Stores user-defined alerts.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | TEXT | PRIMARY KEY | Unique alert ID |
| user_id | TEXT | FOREIGN KEY → users.id | Alert owner |
| type | TEXT | NOT NULL | Alert type |
| condition | JSON | NOT NULL | Trigger condition |
| is_active | BOOLEAN | DEFAULT TRUE | Alert enabled |
| created_at | TIMESTAMP | NOT NULL | Creation time |
| triggered_at | TIMESTAMP | | Last trigger time |
| trigger_count | INTEGER | DEFAULT 0 | Times triggered |

**Indexes:**
- `idx_alerts_user_active` on `(user_id, is_active)`

---

### llm_usage

Tracks LLM API usage for cost management.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | TEXT | PRIMARY KEY | Unique record ID |
| timestamp | TIMESTAMP | NOT NULL | Usage time |
| provider | TEXT | NOT NULL | LLM provider name |
| model | TEXT | NOT NULL | Model name |
| input_tokens | INTEGER | NOT NULL | Input tokens used |
| output_tokens | INTEGER | NOT NULL | Output tokens used |
| cost_usd | DECIMAL(10,6) | NOT NULL | Cost in USD |
| user_id | TEXT | | Associated user |
| request_type | TEXT | | Type of request |
| latency_ms | INTEGER | | Response latency |

**Indexes:**
- `idx_llm_usage_timestamp` on `timestamp`
- `idx_llm_usage_provider_model` on `(provider, model)`
- `idx_llm_usage_user` on `user_id`

---

### audit_log

Stores security audit trail.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | TEXT | PRIMARY KEY | Unique log ID |
| timestamp | TIMESTAMP | NOT NULL | Event time |
| user_id | TEXT | | Acting user |
| action | TEXT | NOT NULL | Action performed |
| resource_type | TEXT | | Resource affected |
| resource_id | TEXT | | Resource identifier |
| ip_address | TEXT | | Client IP |
| user_agent | TEXT | | Client user agent |
| details | JSON | | Additional details |
| hash | TEXT | | Hash chain verification |

**Indexes:**
- `idx_audit_timestamp` on `timestamp`
- `idx_audit_user` on `user_id`
- `idx_audit_action` on `action`

---

### bot_metrics

Stores bot performance metrics.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | TEXT | PRIMARY KEY | Unique record ID |
| bot_type | TEXT | NOT NULL | telegram, twitter, treasury |
| timestamp | TIMESTAMP | NOT NULL | Metric time |
| messages_processed | INTEGER | | Messages handled |
| commands_executed | INTEGER | | Commands run |
| errors_count | INTEGER | | Errors occurred |
| avg_response_time_ms | DECIMAL(10,2) | | Average latency |
| active_users | INTEGER | | Unique active users |

**Indexes:**
- `idx_bot_metrics_type_time` on `(bot_type, timestamp)`

---

### system_metrics

Stores system performance metrics.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | TEXT | PRIMARY KEY | Unique record ID |
| timestamp | TIMESTAMP | NOT NULL | Metric time |
| component | TEXT | NOT NULL | System component |
| cpu_percent | DECIMAL(5,2) | | CPU usage |
| memory_mb | DECIMAL(10,2) | | Memory usage |
| disk_percent | DECIMAL(5,2) | | Disk usage |
| active_connections | INTEGER | | Open connections |
| requests_per_second | DECIMAL(10,2) | | Request rate |
| error_rate | DECIMAL(5,4) | | Error percentage |

**Indexes:**
- `idx_system_metrics_component_time` on `(component, timestamp)`

---

### api_keys

Stores API key details.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | TEXT | PRIMARY KEY | Key ID |
| user_id | TEXT | FOREIGN KEY → users.id | Key owner |
| key_hash | TEXT | NOT NULL, UNIQUE | Hashed key |
| name | TEXT | | Friendly name |
| scopes | JSON | NOT NULL | Allowed scopes |
| created_at | TIMESTAMP | NOT NULL | Creation time |
| expires_at | TIMESTAMP | | Expiration time |
| last_used_at | TIMESTAMP | | Last usage time |
| is_active | BOOLEAN | DEFAULT TRUE | Key active status |

**Indexes:**
- `idx_api_keys_hash` on `key_hash`
- `idx_api_keys_user` on `user_id`

---

### webhooks

Stores webhook configurations.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | TEXT | PRIMARY KEY | Webhook ID |
| user_id | TEXT | FOREIGN KEY → users.id | Owner |
| url | TEXT | NOT NULL | Callback URL |
| events | JSON | NOT NULL | Subscribed events |
| secret_hash | TEXT | NOT NULL | Signing secret hash |
| is_active | BOOLEAN | DEFAULT TRUE | Webhook enabled |
| created_at | TIMESTAMP | NOT NULL | Creation time |
| last_called_at | TIMESTAMP | | Last invocation |
| failure_count | INTEGER | DEFAULT 0 | Consecutive failures |

**Indexes:**
- `idx_webhooks_user` on `user_id`
- `idx_webhooks_active` on `is_active`

---

## Relationships

```
users
  ├── conversations (1:N)
  │     └── messages (1:N)
  ├── trades (1:N)
  ├── portfolio_snapshots (1:N)
  ├── alerts (1:N)
  ├── api_keys (1:N)
  └── webhooks (1:N)

llm_usage ← user_id (optional)
audit_log ← user_id (optional)
bot_metrics (standalone)
system_metrics (standalone)
```

---

## Migrations

### Migration Files Location
`scripts/db/migrations/`

### Running Migrations
```bash
# Apply all pending migrations
python scripts/db/migrate.py up

# Rollback last migration
python scripts/db/migrate.py down

# Show migration status
python scripts/db/migrate.py status
```

### Creating New Migrations
```bash
python scripts/db/migrate.py create "add_user_preferences"
```

---

## Index Optimization

### Recommended Indexes for Common Queries

#### Trading Dashboard
```sql
-- Fast portfolio lookup
CREATE INDEX idx_trades_user_recent ON trades(user_id, created_at DESC);

-- P&L calculations
CREATE INDEX idx_portfolio_user_daily ON portfolio_snapshots(user_id, DATE(timestamp));
```

#### Conversation History
```sql
-- Recent conversations
CREATE INDEX idx_conversations_user_recent ON conversations(user_id, updated_at DESC)
WHERE NOT is_archived;

-- Message retrieval
CREATE INDEX idx_messages_conversation_order ON messages(conversation_id, created_at);
```

#### Analytics
```sql
-- LLM cost analysis
CREATE INDEX idx_llm_daily_provider ON llm_usage(DATE(timestamp), provider);

-- System metrics aggregation
CREATE INDEX idx_metrics_hourly ON system_metrics(component, DATE_TRUNC('hour', timestamp));
```

---

## Data Retention

| Table | Retention | Action |
|-------|-----------|--------|
| messages | 90 days | Archive |
| llm_usage | 365 days | Delete |
| audit_log | 7 years | Archive |
| bot_metrics | 30 days | Delete |
| system_metrics | 7 days | Delete |
| portfolio_snapshots | Forever | Keep |
| trades | Forever | Keep |

---

## Backup Strategy

### Daily Backups
- Full database dump
- Stored in `/backups/daily/`
- Retained for 7 days

### Weekly Backups
- Full database dump
- Stored in `/backups/weekly/`
- Retained for 4 weeks

### Monthly Backups
- Full database dump
- Stored in `/backups/monthly/`
- Retained for 12 months

### Running Backups
```bash
# Manual backup
python scripts/db/backup.py --output /backups/manual/

# Restore from backup
python scripts/db/backup.py --restore /backups/daily/backup_20260113.sql
```

---

## Connection Configuration

### Development (SQLite)
```python
DATABASE_URL="sqlite:///data/jarvis.db"
```

### Production (PostgreSQL)
```python
DATABASE_URL="postgresql://user:pass@host:5432/jarvis"
DATABASE_POOL_SIZE=10
DATABASE_MAX_OVERFLOW=20
DATABASE_POOL_TIMEOUT=30
```

### Connection Pooling
```python
from core.db.pool import DatabasePool

pool = DatabasePool(
    database_url=DATABASE_URL,
    pool_size=10,
    max_overflow=20,
    pool_timeout=30,
    pool_recycle=3600
)
```
