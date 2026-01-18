# Query Optimization Report
Generated: 2026-01-18T13:32:49.961337

## Summary
- Slow queries (>100.0ms): 1
- Tables analyzed: 9

## Slow Queries

### Query (avg: 159.6ms)
```sql
SELECT * FROM logs WHERE service = ? ORDER BY timestamp DESC
```
- Count: 2x
- Avg Time: 159.55ms
- Max Time: 162.80ms

**Recommendations:**
  - [MEDIUM] Avoid SELECT * - specify only needed columns to reduce data transfer
  . [LOW] ORDER BY may cause filesort - ensure index covers sort columns

## Index Recommendations

```sql
CREATE INDEX idx_positions_symbol ON positions(symbol);
CREATE INDEX idx_positions_tp_order_id ON positions(tp_order_id);
CREATE INDEX idx_positions_sl_order_id ON positions(sl_order_id);
CREATE INDEX idx_positions_opened_at ON positions(opened_at);
CREATE INDEX idx_positions_closed_at ON positions(closed_at);
CREATE INDEX idx_positions_user_id ON positions(user_id);
CREATE INDEX idx_trades_symbol ON trades(symbol);
CREATE INDEX idx_trades_timestamp ON trades(timestamp);
CREATE INDEX idx_trades_position_id ON trades(position_id);
CREATE INDEX idx_trades_user_id ON trades(user_id);
CREATE INDEX idx_treasury_orders_order_id ON treasury_orders(order_id);
CREATE INDEX idx_treasury_stats_updated_at ON treasury_stats(updated_at);
CREATE INDEX idx_trade_learnings_trade_id ON trade_learnings(trade_id);
CREATE INDEX idx_trade_learnings_created_at ON trade_learnings(created_at);
CREATE INDEX idx_error_logs_created_at ON error_logs(created_at);
CREATE INDEX idx_pick_performance_symbol ON pick_performance(symbol);
```

## Query Pattern Analysis

| Pattern | Count |
|---------|-------|
| SELECT | 4 |