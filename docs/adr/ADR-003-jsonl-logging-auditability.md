# ADR-003: JSONL Logging for Auditability and Compliance

## Status

Accepted

## Date

2026-01-15

## Context

JARVIS handles financial transactions and autonomous trading decisions. We need:

1. **Auditability**: Complete record of all system actions
2. **Compliance**: Ability to demonstrate regulatory compliance
3. **Debugging**: Rich context for troubleshooting
4. **Analysis**: Machine-parseable logs for analytics
5. **Immutability**: Append-only records that cannot be modified

### Requirements

- Every trade decision must be traceable
- All API calls must be logged with request/response
- Errors must include full stack traces and context
- Logs must be easily queryable
- Retention period: minimum 7 years for financial records

## Decision

Implement **JSONL (JSON Lines) structured logging** with:

1. **Append-Only Files**: One JSON object per line, immutable
2. **Structured Events**: Every log entry is a complete JSON document
3. **Correlation IDs**: Trace requests across services
4. **Rich Context**: Include all relevant metadata
5. **Rotation**: Daily log rotation with compression

### Log Format

```json
{"timestamp":"2026-01-15T10:30:00Z","level":"INFO","event":"TRADE_EXECUTED","trace_id":"abc123","user_id":8527130908,"token":"SOL","amount":50.0,"price":105.50,"pnl_usd":12.50,"decision_confidence":85.0,"algorithms_used":["sentiment","whale"],"latency_ms":450}
```

## Consequences

### Positive

1. **Complete Audit Trail**: Every action is recorded
2. **Machine Parseable**: Easy to query with jq, grep, or ingest into analytics
3. **Immutable**: Append-only prevents tampering
4. **Rich Context**: Full metadata in every entry
5. **Compliance Ready**: Meets financial record-keeping requirements

### Negative

1. **Storage Cost**: More verbose than traditional logs
2. **Write Performance**: Structured logging has overhead
3. **Query Complexity**: Requires JSON parsing tools
4. **Rotation Management**: Need to manage log file lifecycle

### Mitigations

1. **Compression**: Gzip older log files (90% reduction)
2. **Async Writing**: Buffer and batch log writes
3. **Indexing**: Use tools like Loki for querying
4. **Retention Policy**: Archive old logs to cold storage

## Implementation

### Structured Logger

```python
# core/logging/structured_logger.py

class StructuredLogger:
    """JSONL logger for auditability."""

    def log_event(self, event: str, **kwargs):
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": "INFO",
            "event": event,
            "trace_id": self.get_trace_id(),
            "service": self.service_name,
            **kwargs
        }
        self._write_jsonl(entry)
```

### Event Types

| Event | Description | Required Fields |
|-------|-------------|-----------------|
| `TRADE_EXECUTED` | Trade completed | token, amount, price, pnl |
| `TRADE_FAILED` | Trade failed | token, error, reason |
| `REACT_DECISION` | Dexter decision | symbol, decision, confidence |
| `SENTIMENT_ANALYSIS` | Grok analysis | token, score, source |
| `USER_ACTION` | User command | user_id, action, args |
| `API_REQUEST` | External API call | endpoint, status, latency |
| `ERROR` | System error | error, stack_trace, context |

### Log Locations

```
logs/
  jarvis.jsonl           # Main application logs
  trading.jsonl          # Trading-specific events
  audit.jsonl            # Financial audit trail (append-only)
  errors.jsonl           # Error events with stack traces
  api_calls.jsonl        # External API call logs
```

### Querying Examples

```bash
# Find all trades for a token
jq 'select(.event == "TRADE_EXECUTED" and .token == "SOL")' logs/trading.jsonl

# Calculate total PnL for a user
jq 'select(.event == "TRADE_EXECUTED" and .user_id == 8527130908) | .pnl_usd' logs/trading.jsonl | paste -sd+ | bc

# Find errors in last hour
jq 'select(.level == "ERROR" and .timestamp > "2026-01-15T09:30:00Z")' logs/jarvis.jsonl

# Count events by type
jq -s 'group_by(.event) | map({event: .[0].event, count: length})' logs/jarvis.jsonl
```

### Integration with Monitoring

```python
# Export to Prometheus metrics
class MetricsExporter:
    def process_log_line(self, line: str):
        entry = json.loads(line)
        if entry["event"] == "TRADE_EXECUTED":
            self.trade_counter.labels(
                token=entry["token"],
                result="success" if entry["pnl_usd"] > 0 else "loss"
            ).inc()
```

## Retention Policy

| Log Type | Hot Storage | Warm Storage | Cold Storage |
|----------|-------------|--------------|--------------|
| audit.jsonl | 90 days | 2 years | 7 years |
| trading.jsonl | 30 days | 1 year | 3 years |
| jarvis.jsonl | 7 days | 30 days | 1 year |
| errors.jsonl | 30 days | 1 year | 2 years |

## Alternatives Considered

### Alternative 1: Traditional Text Logs

- **Pros**: Simple, familiar, low overhead
- **Cons**: Hard to parse, no structure
- **Decision**: Rejected - insufficient for compliance

### Alternative 2: Database Logging

- **Pros**: Easy querying, indexing
- **Cons**: Single point of failure, not append-only
- **Decision**: Rejected - audit trail must be immutable

### Alternative 3: Third-Party Service (Datadog, Splunk)

- **Pros**: Rich features, no maintenance
- **Cons**: Cost, data residency concerns
- **Decision**: Rejected - prefer self-hosted for financial data

## Security Considerations

1. **Log Integrity**: Append-only files with checksums
2. **Access Control**: Audit logs readable only by admin
3. **Encryption**: Sensitive fields encrypted at rest
4. **No Secrets**: Never log passwords, private keys, or seeds

## References

- [Structured Logger Implementation](../core/logging/structured_logger.py)
- [Audit Trail Module](../core/security/audit_trail.py)
- [Log Rotation Configuration](../lifeos/config/logging.yaml)

## Review

- **Author**: JARVIS Development Team
- **Reviewed By**: Security Council
- **Last Updated**: 2026-01-15
