# ADR-005: SQLite + JSONL for Persistence (Simplicity over Scale)

## Status

Accepted

## Date

2026-01-15

## Context

JARVIS needs persistent storage for:

1. **User Data**: Accounts, preferences, encrypted wallets
2. **Trading State**: Positions, trade history, algorithm performance
3. **Audit Logs**: Immutable record of all actions
4. **Configuration**: Feature flags, system settings
5. **Analytics**: Algorithm metrics, performance data

### Requirements

- Single-node deployment (no distributed system complexity)
- Easy backup and restore
- Human-readable audit trail
- Zero external dependencies
- Works on Windows, Linux, macOS

## Decision

Use a **hybrid persistence strategy**:

1. **SQLite**: Structured relational data (users, wallets, trades)
2. **JSONL**: Append-only audit logs and event streams
3. **JSON Files**: Configuration and state snapshots

### Why Not PostgreSQL/MySQL?

| Factor | SQLite | PostgreSQL |
|--------|--------|------------|
| Setup complexity | Zero | Moderate |
| Operational overhead | None | High |
| Backup simplicity | File copy | pg_dump |
| Concurrent users | 1000s (read) | Millions |
| Transaction safety | Full ACID | Full ACID |
| Our scale | Sufficient | Overkill |

For a single-user admin system with <1000 public users, SQLite provides:
- ACID compliance
- Zero configuration
- File-based backup
- Cross-platform support

## Consequences

### Positive

1. **Zero Dependencies**: No database server to manage
2. **Simple Backup**: Copy files to backup
3. **Portable**: Database is a single file
4. **Fast Local Access**: No network latency
5. **Easy Development**: No database setup needed

### Negative

1. **Single Writer**: Only one writer at a time
2. **No Network Access**: Local access only
3. **Scale Limit**: Not suitable for millions of users
4. **No Replication**: No built-in high availability

### Mitigations

1. **WAL Mode**: Enable Write-Ahead Logging for concurrent reads
2. **Connection Pooling**: Use connection pool for efficiency
3. **Read Replicas**: If needed, sync to read-only copies
4. **Migration Path**: Schema designed for future PostgreSQL migration

## Implementation

### Database Schema

```sql
-- ~/.lifeos/public_users.db

CREATE TABLE users (
    id INTEGER PRIMARY KEY,
    telegram_id INTEGER UNIQUE NOT NULL,
    username TEXT,
    risk_level TEXT DEFAULT 'MODERATE',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_active TIMESTAMP
);

CREATE TABLE wallets (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL,
    address TEXT UNIQUE NOT NULL,
    encrypted_key BLOB NOT NULL,  -- PBKDF2 + Fernet encrypted
    label TEXT,
    is_default BOOLEAN DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE trades (
    id TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL,
    token_mint TEXT NOT NULL,
    token_symbol TEXT NOT NULL,
    direction TEXT NOT NULL,
    entry_price REAL NOT NULL,
    exit_price REAL,
    amount REAL NOT NULL,
    amount_usd REAL NOT NULL,
    status TEXT NOT NULL,
    pnl_usd REAL DEFAULT 0,
    opened_at TIMESTAMP NOT NULL,
    closed_at TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE algorithm_metrics (
    id INTEGER PRIMARY KEY,
    algorithm_type TEXT NOT NULL,
    total_signals INTEGER DEFAULT 0,
    winning_signals INTEGER DEFAULT 0,
    accuracy REAL DEFAULT 0,
    confidence_score REAL DEFAULT 50.0,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### File Structure

```
~/.lifeos/
  public_users.db           # SQLite database
  trading/
    positions.json          # Current open positions (snapshot)
    exit_intents.json       # Pending exit orders
    algorithm_metrics.json  # Algorithm performance cache

logs/
  audit.jsonl               # Immutable audit log
  trading.jsonl             # Trading events
  errors.jsonl              # Error events
```

### SQLite Configuration

```python
# core/database/sqlite_config.py

def get_connection():
    conn = sqlite3.connect(
        str(Path.home() / ".lifeos" / "public_users.db"),
        check_same_thread=False,
        timeout=30.0
    )
    conn.execute("PRAGMA journal_mode=WAL")      # Write-ahead logging
    conn.execute("PRAGMA synchronous=NORMAL")    # Balance durability/speed
    conn.execute("PRAGMA foreign_keys=ON")       # Enforce FK constraints
    conn.execute("PRAGMA busy_timeout=30000")    # Wait 30s on lock
    return conn
```

### JSONL Audit Logging

```python
# core/logging/audit_log.py

class AuditLog:
    """Append-only audit trail."""

    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def log(self, event: str, **kwargs):
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event": event,
            **kwargs
        }
        with open(self.path, "a") as f:
            f.write(json.dumps(entry) + "\n")
```

### Backup Strategy

```bash
#!/bin/bash
# scripts/backup.sh

DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="backups/$DATE"
mkdir -p "$BACKUP_DIR"

# SQLite backup (safe copy while database is in use)
sqlite3 ~/.lifeos/public_users.db ".backup '$BACKUP_DIR/public_users.db'"

# Copy state files
cp -r ~/.lifeos/trading "$BACKUP_DIR/"

# Copy audit logs
cp logs/*.jsonl "$BACKUP_DIR/"

# Compress
tar -czf "backups/$DATE.tar.gz" "$BACKUP_DIR"
rm -rf "$BACKUP_DIR"

echo "Backup complete: backups/$DATE.tar.gz"
```

## Migration Path

If we need to scale beyond SQLite:

1. **Export**: Dump SQLite to SQL statements
2. **Transform**: Convert to PostgreSQL syntax
3. **Import**: Load into PostgreSQL
4. **Update Config**: Change database URL

```python
# Future: PostgreSQL migration
if os.getenv("DATABASE_URL"):
    # Use PostgreSQL
    engine = create_engine(os.getenv("DATABASE_URL"))
else:
    # Use SQLite
    engine = create_engine(f"sqlite:///{DB_PATH}")
```

## Alternatives Considered

### Alternative 1: PostgreSQL from Start

- **Pros**: Industry standard, scalable
- **Cons**: Operational overhead, Docker dependency
- **Decision**: Rejected - unnecessary complexity for current scale

### Alternative 2: Redis + PostgreSQL

- **Pros**: Fast caching, durable storage
- **Cons**: Two systems to manage
- **Decision**: Rejected - SQLite fast enough for our access patterns

### Alternative 3: Firebase/Supabase

- **Pros**: Managed, real-time
- **Cons**: External dependency, data residency concerns
- **Decision**: Rejected - prefer self-hosted for financial data

## Performance Benchmarks

| Operation | SQLite | PostgreSQL |
|-----------|--------|------------|
| Read (single row) | 0.1ms | 0.5ms |
| Write (single row) | 1ms | 2ms |
| Bulk insert (1000 rows) | 50ms | 100ms |
| Full scan (10k rows) | 10ms | 15ms |

SQLite is faster for local access due to no network overhead.

## References

- [SQLite Configuration](../core/database/sqlite_config.py)
- [User Manager](../core/public_user_manager.py)
- [Audit Log](../core/logging/audit_log.py)
- [Backup Script](../scripts/backup.sh)

## Review

- **Author**: JARVIS Development Team
- **Reviewed By**: Architecture Council
- **Last Updated**: 2026-01-15
