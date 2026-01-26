# Vibe Command Usage

## Overview

The `/vibe` command enables AI-powered coding tasks directly from Telegram using persistent Claude console sessions. Perfect for quick bug fixes, refactoring, and code improvements without leaving your chat.

## Features

- **Persistent Sessions**: Conversation history maintained across requests
- **Smart Chunking**: Large responses automatically split with code block preservation
- **Concurrency Protection**: One request per user prevents conflicts
- **Timeout Protection**: 5-minute safety limit with automatic cleanup
- **Progress Indicators**: Animated feedback while processing
- **Usage Analytics**: All requests logged for debugging and insights
- **Output Sanitization**: Automatic removal of sensitive data

---

## Usage

```
/vibe <your coding request>
```

### No Arguments

Running `/vibe` alone shows help text and current session stats:

```
/vibe
```

Response includes:
- Usage examples
- Session message count
- Session token usage
- Session age

---

## Examples

### Add Documentation

```
/vibe add docstrings to all public methods in core/trading/bags_client.py
```

**What happens:**
- Claude reads the file
- Adds comprehensive docstrings
- Preserves existing code
- Shows before/after diff

### Fix Bugs

```
/vibe fix the TypeError in demo_orders.py line 142
```

**What happens:**
- Claude identifies the issue
- Explains the root cause
- Provides corrected code
- Suggests related improvements

### Refactor Code

```
/vibe extract the database logic from demo_sentiment.py into a new db module
```

**What happens:**
- New file created
- Original file updated
- Imports reorganized
- Tests suggested

### Add Tests

```
/vibe write unit tests for the execute_buy_with_tpsl function
```

**What happens:**
- Comprehensive test suite generated
- Edge cases covered
- Mocking examples included
- Test runner compatible

### Optimize Performance

```
/vibe optimize the sentiment analysis loop to reduce API calls
```

**What happens:**
- Performance bottlenecks identified
- Caching strategy suggested
- Batch processing implemented
- Before/after benchmarks

---

## Limitations

| Limitation | Value | Workaround |
|------------|-------|------------|
| Timeout | 5 minutes | Break into smaller tasks |
| Concurrent requests | 1 per user | Wait for completion |
| Access | Admin only | Request admin access |
| Output size | ~15,000 chars | Automatic chunking |
| Max tokens | 4096 output | Use multiple requests |

---

## Troubleshooting

### "Request timed out after 5 minutes"

**Cause**: Task too complex for single request

**Solutions**:
1. Break task into smaller steps:
   ```
   # Instead of:
   /vibe refactor entire codebase

   # Do:
   /vibe refactor core/trading/bags_client.py
   /vibe refactor core/trading/sentiment.py
   ```
2. Focus on specific files/functions
3. Request outline first, then implement parts

### "You already have a vibe request running"

**Cause**: Previous request still processing

**Solutions**:
1. Wait for current request to complete
2. Check Telegram for completion message
3. If stuck >10 minutes, contact admin to restart bot

### "Claude API error"

**Cause**: Various API issues

**Check**:
1. VIBECODING_ANTHROPIC_KEY is valid
2. API rate limits at console.anthropic.com
3. Bot logs for specific error

**Solutions**:
- Wait a few minutes and retry
- Contact admin if persistent

### "Console unavailable"

**Cause**: API key not configured

**Solution**: Admin must set `VIBECODING_ANTHROPIC_KEY` in `.env`

---

## Response Format

### Single Message (< 3800 chars)

```
✅ Vibe Complete

<response content with code blocks>

⏱️ 23.5s | 🎯 1,234 tokens | 💬 5 msgs
🔒 Output sanitized
```

### Multiple Messages (> 3800 chars)

**Header:**
```
✅ Vibe Complete (3 parts)

⏱️ 45.2s | 🎯 3,456 tokens | 💬 12 msgs
🔒 Output sanitized
```

**Part 1:**
```
Part 1/3

<first chunk of response>
```

**Part 2:**
```
Part 2/3

<second chunk>
```

**Part 3:**
```
Part 3/3

<final chunk>
```

Code blocks are automatically preserved across chunks.

---

## Session Management

### Persistent Context

Each user has a persistent session that:
- Remembers previous requests
- Builds context over time
- Improves response quality
- Lasts 24 hours (inactive sessions auto-deleted)

### Clear Session

To reset your session:
```
/console clear
```

This:
- Deletes conversation history
- Resets token counter
- Starts fresh context

### View Session Stats

```
/vibe
```

Shows:
- Message count
- Total tokens used
- Session age
- Last activity

---

## Best Practices

### Be Specific

**Good:**
```
/vibe add error handling to the execute_buy function in trading.py
```

**Bad:**
```
/vibe improve the code
```

### Provide Context

**Good:**
```
/vibe fix the null pointer error in demo_orders.py line 142 when user_id is missing
```

**Bad:**
```
/vibe fix line 142
```

### One Task at a Time

**Good:**
```
/vibe add input validation to the BagsAPIClient constructor
```

**Bad:**
```
/vibe refactor everything, add tests, improve performance, and update docs
```

### Review Changes

Always review Claude's suggestions before applying:
1. Check logic is correct
2. Verify edge cases handled
3. Ensure no regressions
4. Test locally before deploying

---

## Architecture

### Flow Diagram

```
User sends /vibe request
    ↓
Admin authorization check
    ↓
Concurrency check (one per user)
    ↓
Acquire user-specific lock
    ↓
Mark request as active
    ↓
Send to Anthropic API (Claude 3.5 Sonnet)
    ↓
Process response (5 min timeout)
    ↓
Sanitize output (remove secrets)
    ↓
Smart chunking if >3800 chars
    ↓
Send to Telegram
    ↓
Log to analytics DB
    ↓
Release lock & cleanup
```

### Components

| Component | Purpose | Location |
|-----------|---------|----------|
| Handler | /vibe command entry point | `tg_bot/bot_core.py:2070` |
| Console | Claude API integration | `core/continuous_console.py` |
| Chunking | Response splitting | `continuous_console.py:160` |
| Logging | Analytics tracking | `continuous_console.py:149` |
| Database | Usage analytics | `data/jarvis_analytics.db` |

### Session Storage

Sessions saved to: `~/.jarvis/console_sessions/session_{user_id}.json`

Contains:
- User ID and username
- Chat ID
- Message history (last 20)
- Token counts
- Timestamps

---

## Analytics

All vibe requests are logged to `jarvis_analytics.db` for monitoring and debugging.

### Database Schema

```sql
CREATE TABLE vibe_requests (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL,
    username TEXT,
    request TEXT NOT NULL,
    status TEXT CHECK(status IN ('success', 'error', 'timeout', 'rate_limited', 'concurrent_blocked')),
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    duration_seconds REAL,
    response_length INTEGER,
    chunks_sent INTEGER,
    tokens_used INTEGER,
    sanitized BOOLEAN,
    error_message TEXT
);
```

### Common Queries

**Daily stats:**
```sql
SELECT * FROM v_vibe_daily_stats WHERE date >= DATE('now', '-7 days');
```

**Your usage:**
```sql
SELECT request, status, duration_seconds, tokens_used
FROM vibe_requests
WHERE user_id = <your-user-id>
ORDER BY started_at DESC
LIMIT 10;
```

**Error analysis:**
```sql
SELECT error_message, COUNT(*) as count
FROM vibe_requests
WHERE status IN ('error', 'timeout')
GROUP BY error_message;
```

---

## Security

### Output Sanitization

All responses are automatically scrubbed for:
- API keys (sk-*, xai-*, etc.)
- Telegram bot tokens
- Twitter/X credentials
- Solana private keys
- Database URLs
- Email addresses
- File paths (absolute paths redacted)

### Admin Only

`/vibe` is restricted to users in `TELEGRAM_ADMIN_IDS` env var.

Unauthorized attempts are:
- Logged
- Rejected with "access denied" message
- Not executed

### Session Isolation

Each user has their own:
- Conversation history
- Concurrency lock
- Session storage

User A cannot access User B's context.

---

## FAQ

**Q: Can I cancel a running request?**
A: Not currently. Wait for timeout (5 min) or contact admin to restart bot.

**Q: Does vibe actually modify my code?**
A: No. Claude provides suggestions, but YOU must apply changes. Review carefully.

**Q: Why did my request timeout?**
A: Task too complex. Break into smaller chunks or simplify request.

**Q: Can I use vibe on private repos?**
A: Yes, if the bot has access to the codebase.

**Q: What's the token cost?**
A: Varies by request complexity. Check analytics DB or session stats.

**Q: How long do sessions last?**
A: 24 hours of inactivity, then auto-deleted.

**Q: Can I see my request history?**
A: Yes, query `vibe_requests` table (admin access required).

**Q: Is my data private?**
A: Requests sent to Anthropic API (see privacy policy). Sessions stored locally.

---

## Related Commands

- `/code` - Alternative Claude CLI integration (stateless)
- `/console clear` - Reset your vibe session
- `/help` - Bot command list

---

## Technical Details

### Model

Claude 3.5 Sonnet (`claude-3-5-sonnet-20241022`)

**Configuration:**
- Max tokens: 4096 (output)
- Temperature: 0.7
- System prompt: Vibe coding mode
- Context: Last 20 messages

### Timeout

5 minutes per request (300 seconds)

Configured in: `continuous_console.py:81`

### Chunking Algorithm

1. Check if response > 3800 chars
2. Split by lines
3. Track code block state (open/closed)
4. When chunk full:
   - Close code block if open
   - Start new chunk
   - Reopen code block with language
5. Preserve markdown formatting

### Progress Animation

Updates every 2 seconds:
- ⏳ Processing
- ⏳ Processing.
- ⏳ Processing..
- ⏳ Processing...

Runs in background task, auto-cancels on completion.

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-01-26 | Initial implementation (Phase 03-01) |
| | | - Smart chunking with code block preservation |
| | | - Per-user concurrency protection |
| | | - Animated progress indicators |
| | | - Comprehensive error handling |
| | | - Usage analytics logging |

---

**For issues or feature requests, contact admin via Telegram.**
