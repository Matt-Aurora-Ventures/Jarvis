"""SQLite schema definitions for Jarvis memory system."""

SCHEMA_VERSION = 1

# Core tables for facts and entities
CREATE_TABLES_SQL = """
-- Facts: Core memory entries
CREATE TABLE IF NOT EXISTS facts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    content TEXT NOT NULL,
    context TEXT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    source TEXT CHECK(source IN ('telegram', 'treasury', 'x', 'bags_intel', 'buy_tracker', 'system', NULL)),
    confidence REAL DEFAULT 1.0 CHECK(confidence >= 0.0 AND confidence <= 1.0),
    entity_id INTEGER,
    user_id INTEGER,
    session_id TEXT,
    FOREIGN KEY (entity_id) REFERENCES entities(id) ON DELETE SET NULL,
    FOREIGN KEY (user_id) REFERENCES user_identities(id) ON DELETE SET NULL
);

-- Entities: Tokens, users, strategies, etc.
CREATE TABLE IF NOT EXISTS entities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    type TEXT NOT NULL CHECK(type IN ('token', 'user', 'strategy', 'other')),
    metadata TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(name, type)
);

-- Entity mentions: Track @mentions in facts
CREATE TABLE IF NOT EXISTS entity_mentions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fact_id INTEGER NOT NULL,
    entity_id INTEGER NOT NULL,
    mention_text TEXT NOT NULL,
    position INTEGER,
    FOREIGN KEY (fact_id) REFERENCES facts(id) ON DELETE CASCADE,
    FOREIGN KEY (entity_id) REFERENCES entities(id) ON DELETE CASCADE
);

-- Preferences: Confidence-weighted opinions
CREATE TABLE IF NOT EXISTS preferences (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    category TEXT NOT NULL,
    preference_key TEXT NOT NULL,
    preference_value TEXT NOT NULL,
    confidence REAL DEFAULT 0.5 CHECK(confidence >= 0.0 AND confidence <= 1.0),
    evidence_count INTEGER DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES user_identities(id) ON DELETE CASCADE,
    UNIQUE(user_id, category, preference_key)
);

-- Sessions: Per-user conversation context
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL,
    platform TEXT NOT NULL CHECK(platform IN ('telegram', 'x', 'system')),
    context TEXT,
    started_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_active DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES user_identities(id) ON DELETE CASCADE
);

-- User identities: Cross-platform user linking
CREATE TABLE IF NOT EXISTS user_identities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    canonical_name TEXT NOT NULL UNIQUE,
    telegram_username TEXT,
    twitter_username TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Fact embeddings: PostgreSQL integration reference
CREATE TABLE IF NOT EXISTS fact_embeddings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fact_id INTEGER NOT NULL UNIQUE,
    postgres_id INTEGER,
    embedding_synced_at DATETIME,
    FOREIGN KEY (fact_id) REFERENCES facts(id) ON DELETE CASCADE
);

-- Schema version tracking
CREATE TABLE IF NOT EXISTS schema_info (
    version INTEGER PRIMARY KEY,
    applied_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
"""

# FTS5 full-text search virtual table
CREATE_FTS_SQL = """
CREATE VIRTUAL TABLE IF NOT EXISTS facts_fts USING fts5(
    content, context,
    content=facts,
    content_rowid=id,
    tokenize='porter unicode61'
);

-- Triggers to keep FTS5 in sync with facts table
CREATE TRIGGER IF NOT EXISTS facts_ai AFTER INSERT ON facts BEGIN
  INSERT INTO facts_fts(rowid, content, context) VALUES (new.id, new.content, new.context);
END;

CREATE TRIGGER IF NOT EXISTS facts_ad AFTER DELETE ON facts BEGIN
  INSERT INTO facts_fts(facts_fts, rowid, content, context) VALUES('delete', old.id, old.content, old.context);
END;

CREATE TRIGGER IF NOT EXISTS facts_au AFTER UPDATE ON facts BEGIN
  INSERT INTO facts_fts(facts_fts, rowid, content, context) VALUES('delete', old.id, old.content, old.context);
  INSERT INTO facts_fts(rowid, content, context) VALUES (new.id, new.content, new.context);
END;
"""

# Indexes for query performance
CREATE_INDEXES_SQL = """
CREATE INDEX IF NOT EXISTS idx_facts_timestamp ON facts(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_facts_source ON facts(source);
CREATE INDEX IF NOT EXISTS idx_facts_entity_id ON facts(entity_id);
CREATE INDEX IF NOT EXISTS idx_facts_user_id ON facts(user_id);
CREATE INDEX IF NOT EXISTS idx_facts_session_id ON facts(session_id);

CREATE INDEX IF NOT EXISTS idx_entities_name ON entities(name);
CREATE INDEX IF NOT EXISTS idx_entities_type ON entities(type);

CREATE INDEX IF NOT EXISTS idx_entity_mentions_fact_id ON entity_mentions(fact_id);
CREATE INDEX IF NOT EXISTS idx_entity_mentions_entity_id ON entity_mentions(entity_id);

CREATE INDEX IF NOT EXISTS idx_preferences_user_id ON preferences(user_id);
CREATE INDEX IF NOT EXISTS idx_preferences_category ON preferences(category);

CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_platform ON sessions(platform);
CREATE INDEX IF NOT EXISTS idx_sessions_last_active ON sessions(last_active DESC);

CREATE INDEX IF NOT EXISTS idx_user_identities_telegram ON user_identities(telegram_username);
CREATE INDEX IF NOT EXISTS idx_user_identities_twitter ON user_identities(twitter_username);
"""

def get_all_schema_sql() -> str:
    """Get complete schema SQL for database initialization."""
    return "\n".join([
        CREATE_TABLES_SQL,
        CREATE_FTS_SQL,
        CREATE_INDEXES_SQL,
        f"INSERT OR IGNORE INTO schema_info (version) VALUES ({SCHEMA_VERSION});"
    ])
