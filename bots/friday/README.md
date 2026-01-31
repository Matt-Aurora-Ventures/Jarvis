# Friday - KR8TIV AI Email Assistant

> Named after Tony Stark's AI assistant FRIDAY (Female Replacement Intelligent Digital Assistant Youth)

## Purpose

Friday helps process emails and generate professional, brand-aligned responses for KR8TIV AI.

## Features (MVP)

✅ **Email Categorization**
- business_inquiry, technical_support, partnership, investor
- community, spam, personal, urgent, info

✅ **Priority Detection**
- Automatic urgent flagging based on keywords
- Priority levels: urgent, normal, low

✅ **AI-Powered Responses**
- Grok AI generates professional responses
- Aligned with KR8TIV AI brand voice
- Confidence scoring for auto-send decisions

✅ **Brand Voice Integration**
- Uses marketing guide for tone/style
- Professional but authentic
- Technical credibility + accessibility

## Installation

```bash
# Friday is included in Jarvis

# Requires:
export XAI_API_KEY="your-grok-api-key"
```

## Usage

### Process Single Email

```python
from bots.friday.friday_bot import FridayEmailAI, EmailMessage
from datetime import datetime, timezone

async with FridayEmailAI(
    xai_api_key="...",
    user_email="matt@kr8tiv.ai"
) as friday:
    email = EmailMessage(
        message_id="123",
        from_addr="investor@vc.com",
        to_addr="matt@kr8tiv.ai",
        subject="Investment Inquiry",
        body="I'm interested in KR8TIV AI...",
        date=datetime.now(timezone.utc).isoformat()
    )

    response = await friday.process_email(email)

    print(f"Category: {email.category}")
    print(f"Priority: {email.priority}")
    if response.response_text:
        print(f"Suggested Reply:\n{response.response_text}")
```

### Get Inbox Summary

```python
emails = [...]  # List of EmailMessage objects
summary = await friday.get_inbox_summary(emails)

print(f"Total: {summary['total']}")
print(f"Urgent: {summary['urgent']}")
print(f"By category: {summary['by_category']}")
```

## Roadmap

### Phase 1: MVP (DONE)
- [x] Email categorization (9 categories)
- [x] Priority detection
- [x] AI response generation (Grok)
- [x] Brand voice integration
- [x] Confidence scoring

### Phase 2: IMAP Integration
- [ ] Connect to email inbox (IMAP)
- [ ] Fetch unread emails
- [ ] Mark as read/archive
- [ ] Send responses (SMTP)

### Phase 3: Smart Features
- [ ] Calendar integration (schedule meetings)
- [ ] Task creation (from action items)
- [ ] Email threading (context awareness)
- [ ] Learning from sent responses

### Phase 4: Automation
- [ ] Auto-respond to low-risk emails
- [ ] Daily inbox summary
- [ ] Priority notifications (urgent emails)
- [ ] Telegram integration (email alerts)

## Email Categories

| Category | Description | Example |
|----------|-------------|---------|
| business_inquiry | New opportunities | "Interested in your services" |
| technical_support | Support requests | "Bug in the trading bot" |
| partnership | Partnerships | "Let's collaborate" |
| investor | Investment | "VC fund interested in KR8TIV" |
| community | Questions | "How does Jarvis work?" |
| spam | Spam/marketing | "Limited time offer!" |
| personal | Personal | From friends/family |
| urgent | Urgent | Contains "ASAP", "urgent" |
| info | FYI only | Newsletters, receipts |

## Brand Voice

Friday uses the marketing guide to ensure responses match KR8TIV AI's voice:

- **Authentic but professional**: No corporate jargon
- **Technical + accessible**: Explain clearly
- **Honest**: Transparent about capabilities/limits
- **Action-oriented**: Propose next steps

### Example Responses

**Investor Inquiry:**
> Thanks for reaching out! KR8TIV AI is building autonomous trading systems on Solana with AI-driven decision making. We'd be happy to discuss our traction and vision. Would you be available for a 30-min call next week?

**Technical Support:**
> Thanks for flagging this. We take stability seriously. Can you share the error logs or steps to reproduce? In the meantime, try restarting the supervisor: `pkill -f supervisor.py && python bots/supervisor.py &`

**Spam:**
> *No response - marked as spam*

## Testing

```bash
# Test Friday with sample emails
cd /home/jarvis/Jarvis
python3 -m bots.friday.friday_bot
```

## Configuration

- `xai_api_key`: Grok API key (required)
- `user_email`: Your email address
- `brand_guide_path`: Path to marketing guide (default: docs/KR8TIV_AI_MARKETING_GUIDE_JAN_31_2026.md)
- `auto_respond`: Enable auto-send for safe emails (default: False)

## Future Integrations

- **Gmail API**: Better than IMAP for Gmail accounts
- **Outlook API**: For Microsoft 365
- **Telegram**: Email notifications + quick responses
- **Calendar**: Auto-schedule from emails
- **Tasks**: Create tasks from action items

## References

- **Origin**: ClawdMatt GSD-TODO #1 (Jan 29, 2026)
- **Brand Guide**: docs/KR8TIV_AI_MARKETING_GUIDE_JAN_31_2026.md
- **Iron Man's FRIDAY**: https://marvelcinematicuniverse.fandom.com/wiki/F.R.I.D.A.Y.

---

**Status**: ✅ MVP COMPLETE (2026-01-31)
**Next**: IMAP integration for inbox fetching
