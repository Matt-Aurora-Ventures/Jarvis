# Database Code References
**Generated:** 2026-01-24

## Files by Database

### jarvis.db (15+ references)
- bots/treasury/database.py
- bots/treasury/scorekeeper.py
- core/position_manager.py
- core/pnl_tracker.py
- core/trade_journal.py
- core/trading/trade_journal.py
- tests/test_treasury.py
- tests/test_integration.py
- tests/test_persistence.py
- (+ 6 more test files)

### telegram_memory.db (8 references)
- tg_bot/services/conversation_memory.py
- tg_bot/handlers/*.py
- tests/test_telegram_bot.py
- tests/unit/test_telegram_handlers.py

### jarvis_x_memory.db (5 references)
- bots/twitter/autonomous_engine.py
- bots/twitter/engagement_tracker.py
- bots/twitter/ab_testing.py

### sentiment.db (3 references)
- core/sentiment_aggregator.py
- core/sentiment/self_tuning.py
- scripts/tune_sentiment.py

### whales.db (1 reference)
- core/whale_tracker.py

### llm_costs.db (2 references)
- tg_bot/services/cost_tracker.py
- core/monitoring/health_check.py

### rate_limiter.db (2 references)
- core/security/rate_limiter.py
- tests/unit/security/test_enhanced_rate_limiter.py

### raid_bot.db (1 reference)
- tg_bot/services/raid_database.py

## Update Priority

### CRITICAL (Must update first)
1. bots/treasury/database.py - Trading operations
2. core/position_manager.py - Position tracking
3. tg_bot/services/conversation_memory.py - Telegram bot

### HIGH (Update early)
4. bots/twitter/autonomous_engine.py - Twitter bot
5. core/sentiment_aggregator.py - Sentiment analysis
6. core/whale_tracker.py - Whale tracking

### MEDIUM (Update during main phase)
7-20. All other core/ modules

### LOW (Update last)
21+. Test files (can update after main code)

## Estimated Update Time

- Critical files: 4 hours
- High priority: 6 hours
- Medium priority: 10 hours
- Low priority (tests): 8 hours
- **Total: 28 hours**

