# Database Consolidation - Visual Map

## Current State (29 databases)

```
data/
├── telegram_memory.db     (312K) ─┐
├── jarvis.db              (300K) ─┤
├── jarvis_x_memory.db     (200K) ─┤
├── call_tracking.db       (188K) ─┤
├── jarvis_admin.db        (156K) ─┤
├── jarvis_memory.db       (140K) ─┤── SCATTERED
├── raid_bot.db             (76K) ─┤   29 FILES
├── sentiment.db            (48K) ─┤   NO POOLING
├── whales.db               (40K) ─┤   NO WAL MODE
├── llm_costs.db            (36K) ─┤
├── metrics.db              (36K) ─┤
├── rate_limiter.db         (36K) ─┤
├── treasury_trades.db      (28K) ─┤
└── ... 16 more databases ...      ─┘
```

## Future State (7 databases)

```
data/
├── jarvis_core.db         (600K) ───┐
│   ├── positions                    │
│   ├── trades                       │
│   ├── scorecard                    │
│   ├── treasury_trades              │  CONSOLIDATED
│   ├── tax_lots                     │  CONNECTION POOLING
│   └── rate_configs                 │  WAL MODE ENABLED
│                                    │
├── jarvis_analytics.db   (1.2MB) ───┤
│   ├── telegram_messages            │
│   ├── tweets                       │
│   ├── entities & facts (FTS)       │
│   ├── sentiment_readings           │
│   ├── whale_movements              │
│   ├── llm_usage                    │
│   ├── metrics_1m / 1h              │
│   └── call_tracking                │
│                                    │
├── jarvis_cache.db        (100K) ───┘
│   ├── cache_entries
│   ├── request_log
│   └── rate_limiter_stats
│
├── engagement.db          (44K)  ← KEEP STANDALONE
├── jarvis_spam_protection.db     ← KEEP STANDALONE
├── raid_bot.db                   ← KEEP STANDALONE
└── achievements.db               ← KEEP STANDALONE
```

## Migration Flow

```
┌─────────────────────────────────────────────────────────────┐
│ PHASE 01-02: Schema Design & Scripts                       │
├─────────────────────────────────────────────────────────────┤
│ 1. Create jarvis_core.db schema                            │
│ 2. Create jarvis_analytics.db schema (with FTS)            │
│ 3. Create jarvis_cache.db schema                           │
│ 4. Write Python migration scripts                          │
│ 5. Handle FTS virtual tables                               │
└─────────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────────┐
│ PHASE 01-03: Code Updates                                  │
├─────────────────────────────────────────────────────────────┤
│ 1. Create core/db/config.py (centralized paths)            │
│ 2. Update 100+ file references                             │
│ 3. Implement connection pooling                            │
│ 4. Update all tests                                        │
└─────────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────────┐
│ PHASE 01-04: Testing & Deployment                          │
├─────────────────────────────────────────────────────────────┤
│ 1. Backup all 29 databases                                 │
│ 2. Run migration in staging                                │
│ 3. Integration tests (trading, telegram, twitter)          │
│ 4. Production deployment with feature flag                 │
│ 5. Monitor for 7 days                                      │
│ 6. Rollback if error rate >5%                              │
└─────────────────────────────────────────────────────────────┘
```

## Dependency Graph

```
jarvis_core.db
├── positions ←──┐ (FK)
└── trades ──────┘

jarvis_analytics.db
├── entities ←───┐ (FK)
├── facts ───────┘
├── whale_wallets ←──┐ (FK)
├── whale_movements ──┘
├── calls ←──┬─── (FK)
├── outcomes ─┘
└── (120+ tables total)

jarvis_cache.db
└── (temp data, no FKs)
```

## Code Update Heatmap

```
CRITICAL (15+ references)
  jarvis.db ████████████████ (update first)
  
HIGH (5-10 references)
  telegram_memory.db ██████████
  jarvis_x_memory.db ██████
  
MEDIUM (3-5 references)
  call_tracking.db ████
  sentiment.db ████
  
LOW (1-2 references)
  whales.db ██
  llm_costs.db ██
  rate_limiter.db ██
  raid_bot.db ██
```

## Risk Matrix

```
         LOW          MEDIUM          HIGH
        ─────────────────────────────────
HIGH   │                           │ FTS  │
IMPACT │                           │tables│
       │─────────────────────────────────│
MEDIUM │            │ Code paths   │     │
       │            │ FK constraints│     │
       │─────────────────────────────────│
LOW    │ Empty DBs  │              │     │
       │ Cache data │              │     │
        ─────────────────────────────────
```

## Success Criteria

```
BEFORE                      AFTER
══════                      ═════
29 databases           →    7 databases
No pooling             →    Connection pooling
No WAL mode            →    WAL mode enabled
Direct file paths      →    Centralized config
Siloed data            →    Cross-table JOINs
```

