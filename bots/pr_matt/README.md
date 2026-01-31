# PR Matt - Marketing Communications Filter Bot

> "Every autist needs a little PR" - Matt, 2026-01-31

## Purpose

PR Matt automatically reviews all public communications to ensure they maintain professionalism while preserving the authentic founder voice. Prevents "saying crazy shit" while keeping the message genuine.

## Features

- **Multi-stage review**: Rule-based filter + Grok AI analysis
- **Platform-aware**: Different standards for Twitter, Telegram, LinkedIn
- **Smart suggestions**: Provides professional alternatives when needed
- **Learning system**: Tracks review history for improvement
- **Configurable**: Can require manual review or auto-approve high-confidence messages

## Architecture

```
Draft Message
    ↓
Quick Filter (rule-based)
    ↓
Grok AI Review (against brand guidelines)
    ↓
Decision: APPROVED / NEEDS_REVISION / BLOCKED
    ↓
Post or Suggest Alternative
```

## Installation

```bash
# PR Matt is already integrated into Jarvis

# Requires environment variable:
export XAI_API_KEY="your-grok-api-key"
```

## Usage

### Standalone Testing

```python
from bots.pr_matt.pr_matt_bot import PRMattBot
import asyncio

async def test():
    async with PRMattBot(xai_api_key="...") as pr_matt:
        review = await pr_matt.review_message(
            "We're building something that actually works - no hype, just code.",
            platform="twitter"
        )
        print(f"Decision: {review.decision}")
        if review.suggested_revision:
            print(f"Suggested: {review.suggested_revision}")

asyncio.run(test())
```

### Twitter Integration

```python
from bots.pr_matt.twitter_integration import PRMattTwitterFilter

# Initialize filter
filter = PRMattTwitterFilter(xai_api_key="...")
await filter.start()

# Review and post
posted, final_text = await filter.check_and_post(
    "Draft tweet here",
    twitter_client.post,
    use_suggestion=True  # Auto-use suggestions if provided
)
```

### Telegram Integration (TODO)

Not yet implemented. Will review messages to public groups before posting.

## Brand Guidelines

PR Matt uses the marketing guide at:
- `docs/KR8TIV_AI_MARKETING_GUIDE_JAN_31_2026.md`

### Acceptable

✅ "We're building something that actually works - no hype, just code"
✅ "Honestly, we found a critical security issue today. Fixed it."
✅ "GSD framework is working exceptionally well for systematic execution."
✅ Technical language, mild emphasis (crazy, wild, honestly)

### Not Acceptable

❌ "We're gonna make so much fucking money"
❌ "This project is trash" (even if true - phrase constructively)
❌ "Revolutionary paradigm shift" (buzzwords without substance)
❌ "BEST BOT EVER! GUARANTEED PROFITS!"

## Configuration

### PRMattBot Parameters

- `xai_api_key`: Grok API key (required)
- `marketing_guide_path`: Path to brand guidelines (default: docs/KR8TIV_AI_MARKETING_GUIDE_JAN_31_2026.md)
- `review_history_path`: Where to log reviews (default: bots/pr_matt/.review_history.jsonl)

### PRMattTwitterFilter Parameters

- `xai_api_key`: Grok API key (required)
- `auto_approve_threshold`: Confidence needed for auto-approval (default: 0.9)
- `require_manual_review`: If True, all posts need manual approval (default: False)

## Review History

All reviews are logged to `.review_history.jsonl` for analysis:

```jsonl
{"original_message": "...", "decision": "APPROVED", "concerns": [], ...}
{"original_message": "...", "decision": "NEEDS_REVISION", "suggested_revision": "...", ...}
```

### Get Statistics

```python
stats = await pr_matt.get_review_stats()
print(f"Total reviews: {stats['total']}")
print(f"Approval rate: {stats['approved'] / stats['total']:.1%}")
```

## Integration Roadmap

### Phase 1: Twitter (DONE)
- [x] Core PR Matt bot
- [x] Twitter integration
- [x] Review history logging
- [x] Statistics tracking

### Phase 2: Autonomous X Integration (TODO)
- [ ] Hook into autonomous_x_engine before posting
- [ ] Add PR Matt review to twitter_poster
- [ ] Dashboard for review queue

### Phase 3: Telegram Integration (TODO)
- [ ] Review public group messages
- [ ] Admin command: `/prreview <message>` for manual checks
- [ ] Weekly reports of filtered messages

### Phase 4: Learning & Improvement (TODO)
- [ ] Track which suggestions user accepts/rejects
- [ ] Fine-tune filters based on approval patterns
- [ ] Periodic model retraining

## Testing

```bash
# Test PR Matt standalone
cd /home/jarvis/Jarvis
python3 -m bots.pr_matt.pr_matt_bot

# Test Twitter integration
python3 -m bots.pr_matt.twitter_integration
```

## Monitoring

PR Matt logs all reviews with:
- Original message
- Decision (APPROVED/NEEDS_REVISION/BLOCKED)
- Concerns flagged
- Suggested alternative (if any)
- Timestamp

Check logs:
```bash
tail -f logs/supervisor.log | grep "PR Matt"
```

Review history:
```bash
cat bots/pr_matt/.review_history.jsonl | jq '.decision' | sort | uniq -c
```

## Troubleshooting

### "AI review failed"
- Check XAI_API_KEY is set correctly
- Verify Grok API is accessible
- Check rate limits

### All messages blocked
- Review `.review_history.jsonl` for patterns
- Adjust `HARD_BLOCKED_WORDS` if too strict
- Lower `auto_approve_threshold` for more approvals

### Not filtering enough
- Add patterns to `WARNING_PATTERNS`
- Increase AI review stringency (lower temperature)
- Update marketing guide with clearer examples

## References

- **Marketing Guide**: docs/KR8TIV_AI_MARKETING_GUIDE_JAN_31_2026.md
- **Origin**: docs/TELEGRAM_AUDIT_RESULTS_JAN_26_31.md (Task #2)
- **Grok API**: https://docs.x.ai/api

## License

Part of the Jarvis LifeOS system.

---

**Status**: ✅ Phase 1 COMPLETE (2026-01-31)
**Next**: Integrate with autonomous_x_engine
