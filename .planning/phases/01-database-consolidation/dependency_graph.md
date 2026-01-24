# Database Dependency Graph
**Generated:** 2026-01-24

## Foreign Key Relationships

### jarvis.db
```
positions (id PK)
    ↑
    └── trades.position_id (FK)
```

### call_tracking.db
```
calls (id PK)
    ↑
    ├── outcomes.call_id (FK)
    └── trades.call_id (FK)
```

### jarvis_memory.db
```
entities (id PK)
    ↑
    └── facts.entity_id (FK)
```

### whales.db
```
whale_wallets (address PK)
    ↑
    └── whale_movements.wallet_address (FK)
```

### raid_bot.db
```
raid_users (id PK)
    ↑
    ├── raid_participations.user_id (FK)
    └── weekly_winners.user_id (FK)

raids (id PK)
    ↑
    └── raid_participations.raid_id (FK)
```

### tax.db
```
tax_lots (id PK)
    ↑
    └── wash_sales.replacement_lot_id (FK)
```

## Code Dependencies

### High Usage (10+ references)
- jarvis.db → 15+ files (treasury, position_manager, pnl_tracker)
- telegram_memory.db → 8 files (tg_bot services & handlers)
- jarvis_x_memory.db → 5 files (twitter bot)

### Medium Usage (3-10 references)
- call_tracking.db → 3 files
- sentiment.db → 3 files
- llm_costs.db → 2 files
- whales.db → 1 file (whale_tracker.py)

### Low Usage (1-2 references)
- Most other databases (single module)

## Cross-Table Join Patterns

Currently NO cross-database JOINs (all isolated).

After consolidation, possible JOINs:
```sql
-- Link trades to telegram users
SELECT t.*, tu.username 
FROM trades t
JOIN telegram_users tu ON t.user_id = tu.user_id;

-- Link whale movements to sentiment
SELECT wm.*, s.score
FROM whale_movements wm
JOIN sentiment_readings s ON wm.token_symbol = s.symbol;
```

