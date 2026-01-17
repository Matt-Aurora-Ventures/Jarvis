# Jarvis Memory Query Guide

Complete reference for accessing semantic memory, learnings, and context across all Claude Code sessions.

---

## Quick Start

### Import Memories from PostgreSQL
```bash
cd /path/to/Jarvis
python core/memory/auto_import.py
```

### Search Imported Memories
```python
from core.memory.auto_import import MemoryImporter

importer = MemoryImporter()

# Search for trading patterns
results = importer.search_imported_memories("trading strategy", limit=10)

# Get recent architectural decisions
decisions = importer.get_recent_by_type("ARCHITECTURAL_DECISION", limit=20)

# View statistics
stats = importer.get_memory_stats()
```

---

## Memory Query Shortcuts by Task

### 🤖 Trading & Treasury

**Query**: "What trading strategies have we tested?"
```bash
cd $CLAUDE_PROJECT_DIR && python -c "
from core.memory.auto_import import MemoryImporter
importer = MemoryImporter()
results = importer.search_imported_memories('trading strategy', limit=10)
for r in results:
    print(f\"{r['type']}: {r['context']}\")
    print(f\"  Content: {r['content'][:100]}...\")
"
```

**Query**: "Show trading bugs we've fixed"
```bash
cd $CLAUDE_PROJECT_DIR && python -c "
from core.memory.auto_import import MemoryImporter
importer = MemoryImporter()
results = importer.get_recent_by_type('ERROR_FIX', limit=20)
for r in results:
    if 'trading' in r['context'].lower() or 'treasury' in r['context'].lower():
        print(f\"✅ {r['context']}\")
        print(f\"   {r['content'][:150]}...\n\")
"
```

**Query**: "What positions should we track?"
```bash
cd $CLAUDE_PROJECT_DIR && python -c "
from core.memory.auto_import import MemoryImporter
importer = MemoryImporter()
# Get architectural decisions about position tracking
results = importer.get_recent_by_type('ARCHITECTURAL_DECISION', limit=20)
for r in results:
    if 'position' in r['content'].lower():
        print(f\"{r['content']}\n\")
"
```

---

### 🐦 Twitter/X Bot & Autonomous Posting

**Query**: "Successful tweet patterns we've used"
```bash
cd $CLAUDE_PROJECT_DIR && python -c "
from core.memory.auto_import import MemoryImporter
importer = MemoryImporter()
results = importer.search_imported_memories('tweet sentiment grok', limit=15)
for r in results:
    print(f\"[{r['confidence']}] {r['context']}\")
    print(f\"  {r['content'][:120]}...\n\")
"
```

**Query**: "X bot circuit breaker patterns"
```bash
cd $CLAUDE_PROJECT_DIR && python -c "
from core.memory.auto_import import MemoryImporter
importer = MemoryImporter()
results = importer.search_imported_memories('circuit breaker x twitter bot', limit=10)
for r in results:
    print(r['content'])
"
```

**Query**: "Rate limiting and throttling strategies"
```bash
cd $CLAUDE_PROJECT_DIR && python -c "
from core.memory.auto_import import MemoryImporter
importer = MemoryImporter()
results = importer.search_imported_memories('rate limit throttle cooldown', limit=10)
for r in results:
    print(f\"{r['type']}: {r['content']}\n\")
"
```

---

### 💬 Telegram Bot & Chat Handlers

**Query**: "Telegram command patterns we've implemented"
```bash
cd $CLAUDE_PROJECT_DIR && python -c "
from core.memory.auto_import import MemoryImporter
importer = MemoryImporter()
results = importer.search_imported_memories('telegram command handler', limit=10)
for r in results:
    print(f\"{r['context']}: {r['content'][:150]}...\")
"
```

**Query**: "Telegram bot error handling"
```bash
cd $CLAUDE_PROJECT_DIR && python -c "
from core.memory.auto_import import MemoryImporter
importer = MemoryImporter()
results = importer.get_recent_by_type('WORKING_SOLUTION', limit=20)
for r in results:
    if 'telegram' in r['context'].lower():
        print(f\"✅ {r['content']}\n\")
"
```

---

### 💰 Sentiment Analysis & Market Data

**Query**: "Grok sentiment scoring patterns"
```bash
cd $CLAUDE_PROJECT_DIR && python -c "
from core.memory.auto_import import MemoryImporter
importer = MemoryImporter()
results = importer.search_imported_memories('grok sentiment score', limit=10)
for r in results:
    print(f\"[{r['confidence']}] {r['content'][:150]}...\n\")
"
```

**Query**: "Token analysis and scoring methods"
```bash
cd $CLAUDE_PROJECT_DIR && python -c "
from core.memory.auto_import import MemoryImporter
importer = MemoryImporter()
results = importer.search_imported_memories('token analysis scoring buy tracker', limit=15)
for r in results:
    print(r['content'])
    print('---')
"
```

---

### 🔧 Configuration & System Architecture

**Query**: "System configuration decisions"
```bash
cd $CLAUDE_PROJECT_DIR && python -c "
from core.memory.auto_import import MemoryImporter
importer = MemoryImporter()
results = importer.get_recent_by_type('ARCHITECTURAL_DECISION', limit=50)
for r in results:
    print(f\"{r['context']}\")
    print(f\"  {r['content'][:200]}...\n\")
"
```

**Query**: "Configuration best practices for bots"
```bash
cd $CLAUDE_PROJECT_DIR && python -c "
from core.memory.auto_import import MemoryImporter
importer = MemoryImporter()
results = importer.search_imported_memories('config yaml environment variables', limit=10)
for r in results:
    print(r['content'])
"
```

---

### 🐛 Bug Fixes & Error Handling

**Query**: "Recent bugs and how we fixed them"
```bash
cd $CLAUDE_PROJECT_DIR && python -c "
from core.memory.auto_import import MemoryImporter
importer = MemoryImporter()
results = importer.get_recent_by_type('ERROR_FIX', limit=30)
for r in results:
    print(f\"🔧 {r['context']}\")
    print(f\"   {r['content']}\n\")
"
```

**Query**: "Failed approaches we tried"
```bash
cd $CLAUDE_PROJECT_DIR && python -c "
from core.memory.auto_import import MemoryImporter
importer = MemoryImporter()
results = importer.get_recent_by_type('FAILED_APPROACH', limit=20)
for r in results:
    print(f\"❌ {r['context']}\")
    print(f\"   Why: {r['content']}\n\")
"
```

---

### 📊 Memory Statistics

**Get overview of all stored learnings:**
```bash
cd $CLAUDE_PROJECT_DIR && python -c "
from core.memory.auto_import import MemoryImporter
import json

importer = MemoryImporter()
stats = importer.get_memory_stats()

print('📊 Memory Statistics:')
print(f\"Total entries: {stats['total_entries']}\")
print(f\"\\nBy Type:\")
for t, count in stats['by_type'].items():
    print(f\"  {t}: {count}\")
print(f\"\\nBy Confidence:\")
for c, count in stats['by_confidence'].items():
    print(f\"  {c}: {count}\")
print(f\"\\nTop Topics:\")
for topic in stats['topics'][:10]:
    print(f\"  {topic['topic']}: {topic['count']}\")
print(f\"\\nMost Recent:\")
if stats['most_recent']:
    print(f\"  {stats['most_recent']['context']} ({stats['most_recent']['imported_at']})\")
"
```

---

## PostgreSQL Direct Queries

If you want to query `continuous_claude` database directly:

### Connect via Docker
```bash
docker exec continuous-claude-postgres psql -U claude -d continuous_claude -c \
  "SELECT id, type, context, confidence FROM archival_memory ORDER BY created_at DESC LIMIT 20;"
```

### Query specific type
```bash
docker exec continuous-claude-postgres psql -U claude -d continuous_claude -c \
  "SELECT context, content FROM archival_memory WHERE type = 'WORKING_SOLUTION' LIMIT 10;"
```

### Search by keyword
```bash
docker exec continuous-claude-postgres psql -U claude -d continuous_claude -c \
  "SELECT * FROM archival_memory WHERE content ILIKE '%trading%' LIMIT 10;"
```

### Get high-confidence learnings
```bash
docker exec continuous-claude-postgres psql -U claude -d continuous_claude -c \
  "SELECT type, context, content FROM archival_memory WHERE confidence = 'high' ORDER BY created_at DESC LIMIT 20;"
```

---

## Using Memory in Claude Code Sessions

### Method 1: Direct Python (Fastest)
```python
# In any Claude Code session
from core.memory.auto_import import MemoryImporter

importer = MemoryImporter()
traders_tips = importer.search_imported_memories("trading", limit=5)
```

### Method 2: Recall Skill (Within Claude Code)
```bash
# Use the /recall skill for semantic search
/recall "trading strategies for Solana tokens"
```

### Method 3: MCP Memory Server
The `memory` MCP in `.claude/mcp.json` provides session-level memory via JSONL.

### Method 4: Filesystem Search
```bash
# Search JSONL memory directly
grep -l "trading" ./data/memory/jarvis-memory.jsonl | xargs grep "strategy"
```

---

## Memory Types Reference

| Type | Use For | Example Query |
|------|---------|---------------|
| `WORKING_SOLUTION` | Fixes that work | "How did we fix the X bot spam issue?" |
| `ERROR_FIX` | Bug solutions | "Bare except fixes" |
| `FAILED_APPROACH` | What didn't work | "What approaches failed for state backup?" |
| `ARCHITECTURAL_DECISION` | System design | "Why did we choose PostgreSQL for memory?" |
| `CODEBASE_PATTERN` | Reusable patterns | "Event bus handler patterns" |
| `USER_PREFERENCE` | Your preferred style | "Use Opus for complex tasks" |
| `OPEN_THREAD` | Incomplete work | "Resume after deploying M6" |

---

## Quick Reference Commands

### Refresh memory from PostgreSQL
```bash
python core/memory/auto_import.py
```

### Search for trading decisions
```bash
python -c "from core.memory.auto_import import MemoryImporter; importer = MemoryImporter(); [print(r['content']) for r in importer.search_imported_memories('trading', 10)]"
```

### Show stats
```bash
python -c "from core.memory.auto_import import MemoryImporter; import json; importer = MemoryImporter(); print(json.dumps(importer.get_memory_stats(), indent=2, default=str))"
```

### List all high-confidence learnings
```bash
sqlite3 ./data/jarvis.db "SELECT type, context FROM memory_entries WHERE confidence='high' LIMIT 20;"
```

---

## Integration with Workflows

### Before implementing a feature
```bash
# 1. Import fresh learnings
python core/memory/auto_import.py

# 2. Search for similar work
python -c "from core.memory.auto_import import MemoryImporter; importer = MemoryImporter(); [print(r['content']) for r in importer.search_imported_memories('YOUR_FEATURE_NAME', 10)]"

# 3. Learn from past approach
# Review context and apply lessons
```

### After fixing a bug
```bash
# Store the learning (for next session)
cd $CLAUDE_PROJECT_DIR/opc && PYTHONPATH=. uv run python scripts/core/store_learning.py \
  --session-id "bug-fix-$(date +%Y%m%d)" \
  --type ERROR_FIX \
  --content "Describe the fix here" \
  --context "Component or feature" \
  --tags "tag1,tag2" \
  --confidence high
```

### Before architectural changes
```bash
# Get similar decisions
python -c "from core.memory.auto_import import MemoryImporter; importer = MemoryImporter(); [print(f\"{r['context']}: {r['content'][:200]}\") for r in importer.get_recent_by_type('ARCHITECTURAL_DECISION', 30)]"
```

---

## Troubleshooting

### "PostgreSQL not configured"
**Solution**: Add `DATABASE_URL=postgresql://claude:claude_dev@localhost:5432/continuous_claude` to `.env`

### "psycopg2 not installed"
**Solution**:
```bash
pip install psycopg2-binary
```

### "No memory entries found"
**Solution**: Run import first:
```bash
python core/memory/auto_import.py
```

### "SQLite database locked"
**Solution**: Close any open database connections and retry

### "Memory entries are empty"
**Solution**: Check that PostgreSQL `continuous_claude` database exists:
```bash
docker exec continuous-claude-postgres psql -U claude -d continuous_claude -c "SELECT COUNT(*) FROM archival_memory;"
```

---

## Pro Tips

1. **Import regularly** - Run `python core/memory/auto_import.py` at start of each session for fresh learnings

2. **Tag everything** - When storing learnings, use consistent tags: `trading`, `twitter`, `telegram`, `sentiment`, `config`, etc.

3. **Search with specificity** - "trading jupiter solana" is better than just "trading"

4. **Check confidence** - High-confidence learnings are usually more reliable

5. **Review failed approaches** - Before trying something new, see what didn't work before

6. **Cross-reference** - Often multiple memory types relate to same problem (error fix + failed approach + working solution)

---

Generated: 2026-01-17
Last Updated: When MCPs were enabled
