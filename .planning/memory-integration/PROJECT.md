# Clawdbot Memory System Integration

**Created:** 2026-01-25
**Owner:** @lucid
**Status:** In Progress
**Parent Project:** Jarvis V1 Production-Ready Trading & AI Assistant

---

## Vision

Integrate Clawdbot's hybrid Markdown + SQLite memory architecture across **every single Jarvis system** to enable persistent, personalized intelligence that evolves with every interaction.

**Core Pillars:**
1. **Unified Memory** - Single memory layer across all bots (Telegram, X, Treasury, Buy tracker, Bags intel)
2. **Remember Everything** - Trade outcomes, user preferences, token intel, conversation context
3. **Confidence Evolution** - Preferences strengthen/weaken based on evidence over time
4. **Cross-Platform Identity** - Link user identities across Telegram, X, voice, API
5. **Human + Machine Readable** - Markdown for humans, SQLite for machine efficiency

---

## Problem Statement

### Current State
Jarvis has fragmented memory across multiple systems:
- **28+ SQLite databases** - Scattered state without unified context
- **PostgreSQL semantic memory** - 100+ learnings with BGE embeddings (good foundation)
- **No personalization** - Bots don't remember user preferences or past interactions
- **No trade outcome memory** - Can't learn "KR8TIV pumped after bags.fm graduation" patterns
- **No confidence tracking** - Can't evolve opinions based on evidence
- **Siloed bot memory** - Telegram bot doesn't know what Treasury bot learned

### Missing Critical Capabilities
From Clawdbot architecture, Jarvis needs:

1. **Retain/Recall/Reflect Loop**
   - Retain: Store facts, preferences, outcomes in every interaction
   - Recall: Query memory before decisions (trade, chat response, post)
   - Reflect: Periodic synthesis to update core beliefs

2. **Dual-Layer Memory**
   - Markdown layer: `memory.md`, daily logs, entity profiles
   - SQLite layer: Fast queries, vector search, FTS5, statistics

3. **Entity Linking**
   - Cross-reference @users, @tokens, @strategies across all systems
   - "User lucid prefers aggressive TP/SL" applied in Treasury, Telegram, X

4. **Session Management**
   - Per-user isolation (don't mix lucid's prefs with other users)
   - Platform linking (lucid on Telegram = @lucid on X)

5. **Confidence-Weighted Opinions**
   - "bags.fm graduations are bullish" starts at 0.5 confidence
   - Strengthens to 0.8 after 10 successful trades
   - Weakens to 0.3 after string of failures

---

## Goals

### Integration Success Criteria

**Must-Have (Memory Foundation):**
1. ✅ Unified memory workspace structure (`~/jarvis/memory/`)
2. ✅ SQLite schema for facts, entities, preferences, sessions
3. ✅ Retain functions integrated into all 5 bot systems
4. ✅ Recall functions used before key decisions (trades, posts, responses)
5. ✅ Entity linking system (@tokens, @users, @strategies)
6. ✅ Session management with platform identity linking
7. ✅ Confidence-weighted preference storage

**Should-Have (Intelligence Layer):**
8. ✅ Trade outcome memory with full context
9. ✅ Token intel memory (bags.fm patterns, sentiment scores)
10. ✅ User preference evolution over time
11. ✅ Reflect functions for daily synthesis
12. ✅ FTS5 full-text search across all memory

**Nice-to-Have (Advanced Features):**
13. Entity profiles (per-token, per-user summaries)
14. Memory export/import for backups
15. Memory visualization dashboard
16. Cross-session context (resume conversations)

---

## Integration Points with Existing Jarvis Architecture

### 1. PostgreSQL Semantic Memory (Existing)
**Status:** Keep and extend
- Current: 100+ learnings with BGE embeddings
- Integration: Add `archival_memory` table links to SQLite fact IDs
- Flow: SQLite stores facts → PostgreSQL indexes embeddings → Recall uses both

### 2. Treasury Trading System
**Files:** `bots/treasury/trading.py` (3,754 lines)
- **Retain:** After every trade, store outcome + context
  ```python
  memory.retain_fact(
      content="KR8TIV bought at $0.05, sold at $0.12 (+140%)",
      context="bags.fm graduation within 2h, sentiment: 0.85",
      entities=["@KR8TIV", "@bags.fm", "@lucid"]
  )
  ```
- **Recall:** Before trade decisions, query past outcomes
  ```python
  similar_trades = memory.recall("bags.fm graduations", k=5)
  avg_outcome = calculate_average(similar_trades)
  ```

### 3. Telegram Bot (`tg_bot/`)
**Files:** `tg_bot/handlers/demo.py` (391.5KB), `tg_bot/services/chat_responder.py`
- **Retain:** Store user preferences from conversations
  ```python
  memory.update_preference(
      user="lucid",
      key="risk_tolerance",
      value=0.75,  # aggressive
      evidence="User said 'I want max gains'"
  )
  ```
- **Recall:** Personalize responses based on history
  ```python
  user_prefs = memory.get_user_preferences("lucid")
  # Adjust response tone, suggestions based on prefs
  ```

### 4. X/Twitter Bot (`bots/twitter/`)
**Files:** `autonomous_engine.py`, `x_claude_cli_handler.py`
- **Retain:** Store post performance + audience reactions
  ```python
  memory.retain_fact(
      content="Posted about KR8TIV at 10am, 50 likes, 20 retweets",
      context="bags.fm graduation timing, bullish sentiment",
      entities=["@KR8TIV", "@X"]
  )
  ```
- **Recall:** Learn what content performs well
  ```python
  best_posts = memory.recall("high engagement posts about memecoins", k=10)
  # Use patterns to inform next post
  ```

### 5. Bags Intel (`bots/bags_intel/`)
**Files:** `sentiment_report.py`, `graduation_monitor.py`
- **Retain:** Store graduation patterns + outcomes
  ```python
  memory.retain_fact(
      content="Token XYZ graduated, bonding score: 82, 3x in 24h",
      context="Strong social presence, dev active",
      entities=["@XYZ", "@bags.fm"]
  )
  ```
- **Recall:** Predict graduation success
  ```python
  similar_grads = memory.recall("bags.fm graduations with score >80", k=20)
  success_rate = calculate_success_rate(similar_grads)
  ```

### 6. Trust Ladder System (Existing)
**Integration:** Memory confidence scores inform trust levels
- High confidence prefs (0.8+) → Higher trust autonomy
- Low confidence (0.3-) → Require confirmation

### 7. 81+ Trading Strategies (Existing)
**Integration:** Strategy performance memory
- Track which strategies work in which market conditions
- Evolve strategy selection based on outcomes

---

## Target Users

**Primary:** Jarvis admin (@lucid) and future multi-user deployments

**Use Cases:**
1. **Treasury Bot:** "Remember that bags.fm graduations pump within 2h"
2. **Telegram Admin:** "lucid prefers aggressive TP/SL, other users prefer conservative"
3. **X Bot:** "Posts about token graduations get 3x engagement vs general market updates"
4. **Bags Intel:** "Tokens with dev Twitter presence succeed 70% of the time"

---

## Non-Goals (Out of Scope)

- ❌ Replace PostgreSQL semantic memory (extend it, don't replace)
- ❌ Change existing bot functionality (memory is additive)
- ❌ Multi-tenant isolation (single user for V1)
- ❌ Real-time collaboration (future)

---

## Technical Context

### Existing Codebase Structure

**Core Components:**
- `bots/supervisor.py` - Orchestrates all components
- `bots/treasury/trading.py` - Treasury trading engine (3,754 lines)
- `tg_bot/` - Telegram bot (demo.py is 391.5KB)
- `bots/twitter/` - X/Twitter autonomous engine
- `bots/bags_intel/` - bags.fm monitoring
- `core/context_loader.py` - Shared Jarvis context

**External Integrations:**
- PostgreSQL (semantic memory - 100+ learnings with BGE embeddings)
- 18 MCPs configured
- Jupiter DEX (Solana trading)
- bags.fm API
- Telegram Bot API
- X/Twitter API
- Grok AI (xAI)
- Helius RPC (Solana)

**Existing Memory Infrastructure:**
- PostgreSQL `archival_memory` table with BGE embeddings (bge-large-en-v1.5, 1024-dim)
- SQLite databases (28+ scattered) - target for consolidation
- `~/.lifeos/trading/` - Runtime state files

---

## Clawdbot Architecture to Integrate

### Workspace Structure
```
~/jarvis/memory/               # NEW: Clawdbot memory root
├── memory.md                  # Core durable facts
├── memory/
│   ├── YYYY-MM-DD.md         # Daily session logs
│   └── archives/             # Older logs
├── bank/
│   ├── world.md              # Objective facts
│   ├── experience.md         # Agent experiences
│   ├── opinions.md           # Preferences with confidence
│   └── entities/             # Per-entity summaries
│       ├── tokens/
│       ├── users/
│       └── strategies/
├── jarvis.db                  # NEW: SQLite memory database
├── SOUL.md                   # Agent personality (Jarvis identity)
├── AGENTS.md                 # Operating instructions
└── USER.md                   # User profile (@lucid)
```

### SQLite Schema
```sql
-- Core facts table
CREATE TABLE facts (
    id INTEGER PRIMARY KEY,
    content TEXT NOT NULL,
    context TEXT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    source TEXT,  -- 'telegram', 'treasury', 'x', 'bags_intel'
    confidence REAL DEFAULT 1.0
);

-- Entities (tokens, users, strategies)
CREATE TABLE entities (
    id INTEGER PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    type TEXT NOT NULL,  -- 'token', 'user', 'strategy'
    summary TEXT,
    last_updated DATETIME
);

-- Entity mentions (linking)
CREATE TABLE entity_mentions (
    fact_id INTEGER REFERENCES facts(id),
    entity_id INTEGER REFERENCES entities(id),
    PRIMARY KEY (fact_id, entity_id)
);

-- User preferences with confidence
CREATE TABLE preferences (
    id INTEGER PRIMARY KEY,
    user TEXT NOT NULL,
    key TEXT NOT NULL,
    value TEXT NOT NULL,
    confidence REAL DEFAULT 0.5,
    evidence_count INTEGER DEFAULT 1,
    last_updated DATETIME,
    UNIQUE(user, key)
);

-- Sessions (per-user, per-platform)
CREATE TABLE sessions (
    id TEXT PRIMARY KEY,  -- UUID
    user TEXT NOT NULL,
    platform TEXT NOT NULL,  -- 'telegram', 'x', 'api'
    started_at DATETIME,
    ended_at DATETIME,
    metadata TEXT  -- JSON
);

-- FTS5 for full-text search
CREATE VIRTUAL TABLE facts_fts USING fts5(
    content,
    context,
    content=facts,
    content_rowid=id
);

-- Vector embeddings (link to PostgreSQL)
CREATE TABLE fact_embeddings (
    fact_id INTEGER PRIMARY KEY REFERENCES facts(id),
    postgres_memory_id INTEGER  -- Links to archival_memory.id
);
```

### Retain/Recall/Reflect Functions

**Retain (Store):**
```python
def retain_fact(content: str, context: str = None, entities: list[str] = None, source: str = None):
    """Store a fact in both Markdown and SQLite"""
    # 1. Append to daily log: memory/YYYY-MM-DD.md
    # 2. Insert into SQLite facts table
    # 3. Link entities via entity_mentions
    # 4. Generate embedding → store in PostgreSQL archival_memory
    # 5. Update FTS5 index
```

**Recall (Query):**
```python
def recall(query: str, k: int = 5, filters: dict = None) -> list[dict]:
    """Hybrid search: FTS5 + vector embeddings"""
    # 1. FTS5 text search in SQLite
    # 2. Vector search in PostgreSQL
    # 3. RRF merge results
    # 4. Return top k facts with context
```

**Reflect (Synthesize):**
```python
def reflect_daily():
    """Daily synthesis: update memory.md, entity summaries"""
    # 1. Read today's log: memory/YYYY-MM-DD.md
    # 2. Extract key facts → update memory.md
    # 3. Update entity summaries in bank/entities/
    # 4. Update confidence scores in preferences
    # 5. Archive old logs
```

---

## Constraints

1. **Preserve existing functionality** - Memory is additive, not disruptive
2. **No data loss** - Migrate existing PostgreSQL learnings to new schema
3. **Performance** - Recall queries <100ms for real-time decisions
4. **Consistency** - Same memory accessible from all bot systems
5. **Security** - User preferences isolated (when multi-user support added)

---

## Success Metrics

**Memory Foundation:**
- Unified memory workspace created
- All 5 bot systems call retain() after key events
- All 5 bot systems call recall() before decisions
- SQLite + PostgreSQL integration working

**Intelligence:**
- Trade outcome memory: 100+ trades stored with context
- User preferences: 20+ prefs tracked with confidence evolution
- Token intel: 50+ tokens with graduation patterns
- Entity linking: 500+ entity mentions

**Performance:**
- Recall latency: <100ms p95
- Daily reflect: <5 minutes
- Memory DB size: <500MB for 10K facts

---

## References

**Clawdbot Source:**
- Full documentation provided by user (workspace structure, SQLite schema, Retain/Recall/Reflect functions)

**Jarvis Codebase:**
- GitHub: Matt-Aurora-Ventures/Jarvis
- `.planning/PROJECT.md` - Main Jarvis V1 context
- `.planning/REQUIREMENTS.md` - REQ-001 through REQ-011
- `.planning/ROADMAP.md` - 8-phase roadmap

**Integration Target:**
- Phase 6: Security Fixes (add memory foundation)
- Phase 7: Testing & QA (build Retain/Recall functions)
- Phase 8: Monitoring & Launch (add Reflect system)

---

**Document Version:** 1.0
**Last Updated:** 2026-01-25 after initialization
**Next Review:** After requirements definition complete
