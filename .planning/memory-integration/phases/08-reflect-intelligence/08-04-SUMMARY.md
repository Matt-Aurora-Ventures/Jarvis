---
phase: 08-reflect-intelligence
plan: 04
title: "Weekly Pattern Analysis + Contradiction Detection"
status: complete
wave: 2
subsystem: memory-intelligence
tags: [patterns, contradictions, weekly-reports, llm-synthesis, analytics]

dependencies:
  requires: ["08-01"]
  provides:
    - "Weekly trading pattern summaries"
    - "Contradiction detection system"
    - "Actionable insights from aggregate data"
  affects: []

tech-stack:
  added:
    - "anthropic Python SDK (for pattern insights)"
  patterns:
    - "Weekly boundary calculation (Monday-Sunday)"
    - "SQL aggregate queries for statistics"
    - "LLM-synthesized insights from raw stats"
    - "Rule-based contradiction detection"

key-files:
  created:
    - "core/memory/patterns.py"
  modified:
    - "core/memory/reflect.py"
    - "core/memory/__init__.py"

decisions:
  - id: "PATTERN-001"
    decision: "Weekly summaries use last complete week (Monday-Sunday)"
    rationale: "ISO week standard, avoids partial week data"
    alternatives: ["Rolling 7-day window", "Calendar weeks"]
  - id: "PATTERN-002"
    decision: "Contradiction detection uses confidence threshold of 0.4"
    rationale: "Filters out low-confidence noise, focuses on meaningful conflicts"
    alternatives: ["Lower threshold (0.3)", "Higher threshold (0.5)"]
  - id: "PATTERN-003"
    decision: "Store contradictions in reflect_state.json"
    rationale: "Provides visibility without polluting fact database"
    alternatives: ["Create contradiction facts", "Separate contradictions table"]

metrics:
  loc-added: 408
  loc-modified: 19
  files-created: 1
  files-modified: 2
  commits: 3
  duration: "12 minutes"
  completed: "2026-01-25"

requirements-satisfied:
  - REF-006: "Weekly pattern reports show win rates, top tokens, strategy performance"
  - REF-007: "Contradiction detection finds conflicting preferences/entities"
---

# Phase 08 Plan 04: Weekly Pattern Analysis + Contradiction Detection Summary

**One-liner:** LLM-synthesized weekly trading reports with rule-based contradiction detection

## What Was Built

Created comprehensive pattern analysis system for weekly insights and data integrity:

### 1. Weekly Summary Generation (`generate_weekly_summary()`)
- **Last complete week calculation**: Monday-Sunday boundaries using ISO calendar
- **SQL aggregate queries**:
  - Trade outcomes: total/wins/losses/win rate from treasury facts
  - Top tokens: Ranked by wins with mention counts
  - Strategy performance: Win rates per strategy entity
  - Activity by source: Fact counts per source system
- **Claude synthesis**: Converts raw stats into 3-5 actionable insights
- **Markdown output**: Saves to `~/.lifeos/memory/bank/weekly_summaries/{year}-W{week}.md`

### 2. Contradiction Detection (`detect_contradictions()`)
- **Preference conflicts**: Same user/key with different values (conf > 0.4)
- **Entity type conflicts**: Same name (case-insensitive) with different types
- **Structured output**: List of dicts with type, IDs, reason, timestamp
- **Logging**: Warnings for each detected contradiction

### 3. Integration into `reflect_daily()`
- **Step 7**: Added contradiction detection to daily reflection workflow
- **State tracking**: Stores contradictions array in `reflect_state.json`
- **Return value**: Includes `contradictions_found` count
- **Visibility**: Logged warnings flag conflicts for manual review

## Technical Implementation

### Key Patterns

**Weekly Boundary Calculation:**
```python
# Last complete week (Monday-Sunday)
today = datetime.utcnow().date()
days_since_monday = today.weekday()
if days_since_monday == 0:
    week_end = today - timedelta(days=1)
else:
    week_end = today - timedelta(days=days_since_monday + 1)
week_start = week_end - timedelta(days=6)
```

**SQL Aggregates for Win Rates:**
```sql
SELECT
    COUNT(*) as total_trades,
    SUM(CASE WHEN content LIKE '%+%' OR content LIKE '%profit%' THEN 1 ELSE 0 END) as wins,
    SUM(CASE WHEN content LIKE '%-%' OR content LIKE '%loss%' THEN 1 ELSE 0 END) as losses
FROM facts
WHERE source = 'treasury'
AND context LIKE '%trade_outcome%'
AND timestamp >= ? AND timestamp <= ?
```

**Contradiction Detection (Preferences):**
```sql
SELECT p1.id, p2.id, p1.user_id, p1.preference_key,
       p1.preference_value, p2.preference_value
FROM preferences p1
JOIN preferences p2 ON p1.user_id = p2.user_id
    AND p1.preference_key = p2.preference_key
WHERE p1.id < p2.id
AND p1.preference_value != p2.preference_value
AND p1.confidence > 0.4 AND p2.confidence > 0.4
```

### File Structure

**core/memory/patterns.py** (408 lines):
- `generate_weekly_summary()` - Main weekly analysis function
- `_synthesize_pattern_insights()` - Claude API integration
- `detect_contradictions()` - Rule-based conflict detection

**Integration:**
- `core/memory/reflect.py` - Added Step 7 for daily contradiction checks
- `core/memory/__init__.py` - Exported both pattern functions

## Testing & Verification

### Functionality Verified

1. ✅ `generate_weekly_summary()` importable and callable
2. ✅ `detect_contradictions()` returns list of conflict dicts
3. ✅ Weekly summaries directory path: `~/.lifeos/memory/bank/weekly_summaries/`
4. ✅ Contradiction detection found real conflict (entity type mismatch)
5. ✅ `reflect_daily()` includes contradiction detection step
6. ✅ Both functions exported from `core.memory` module

### Live Results

Contradiction detection **found 1 real issue** during testing:
```
Entity '@test' has conflicting types: 'user' vs 'token'
```

This validates the system works on actual memory data.

## Deviations from Plan

**None** - Plan executed exactly as written.

All tasks completed:
1. ✅ Created patterns module with weekly summary generation
2. ✅ Added contradiction detection
3. ✅ Exported and integrated pattern functions

## Impact & Integration

### Upstream Dependencies
- **08-01 (Daily Reflection)**: Contradiction detection runs during reflect_daily()
- **database.py**: SQL queries for aggregate statistics
- **summarize.py**: Pattern for LLM synthesis

### Downstream Effects
- **Future phases**: Weekly summaries provide trend analysis for decision-making
- **Data quality**: Contradiction detection prevents conflicting facts from accumulating
- **Visibility**: reflect_state.json now includes contradictions for monitoring

### User-Facing Changes

**New capabilities:**
1. Generate weekly trading reports: `generate_weekly_summary()`
2. Detect memory conflicts: `detect_contradictions()`
3. Daily contradiction checks during `reflect_daily()`

**Files created on first run:**
- `~/.lifeos/memory/bank/weekly_summaries/{year}-W{week}.md`

## Next Phase Readiness

### Blockers
None.

### Concerns
1. **LLM costs**: Weekly summaries call Claude API - monitor token usage
2. **Contradiction volume**: If contradictions grow, need manual review workflow
3. **Weekly summary timing**: Need to schedule weekly report generation

### Recommendations
1. Add scheduled task to run `generate_weekly_summary()` every Monday
2. Create admin endpoint to view/resolve contradictions
3. Add metrics dashboard showing contradiction trends over time

## Commits

| Hash | Message | Files |
|------|---------|-------|
| ad9002d | feat(08-04): create weekly pattern analysis with LLM insights | patterns.py |
| be2a881 | feat(08-04): integrate contradiction detection into reflect_daily | reflect.py |
| f15d24b | feat(08-04): export pattern analysis functions from core.memory | __init__.py |

**Total:** 3 commits, 408 lines added, 19 lines modified

---

**Plan Duration:** 12 minutes
**Lines of Code:** 408 new, 19 modified
**Status:** ✅ Complete - All success criteria met
