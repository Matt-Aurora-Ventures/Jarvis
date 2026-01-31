# KR8TIV AI Marketing & Brand Documentation

This directory contains all brand guidelines, voice/tone documentation, and marketing materials for KR8TIV AI and JARVIS.

## Brand Voice & Guidelines

### [KR8TIV_AI_MARKETING_GUIDE_JAN_31_2026.md](./KR8TIV_AI_MARKETING_GUIDE_JAN_31_2026.md)
**Comprehensive brand guide** (125 lines)

Complete marketing and brand voice guide used by:
- PR Matt (marketing communications filter bot)
- Friday (email AI assistant)
- All public communications

**Contents:**
- Brand positioning ("Where scrappy engineering meets AI trading")
- Target audience (3 segments: crypto natives, AI enthusiasts, traders)
- Voice & tone (authentic, technical, honest, no hype)
- Key messages (autonomous execution, transparent operations, continuous learning)
- Content pillars (transparency, results, technical depth, community)
- Communication templates for different scenarios
- What to avoid (hype, overpromising, buzzwords without substance)

**Usage:** Reference this guide for all public communications, social media, emails, and marketing content.

---

### [x_thread_kr8tiv_voice.md](./x_thread_kr8tiv_voice.md)
**Twitter/X voice guide for @KR8TIV_AI account** (88 lines)

Specific voice guidance for Twitter/X posts about KR8TIV AI as a company.

**Tone:**
- Scrappy founder energy
- Technical transparency
- Self-aware about being early-stage
- No hype, just building

**Example posts:**
- "Building in public: treasury bot made 47 trades today, 62% win rate. Not perfect, but learning."
- "Honest update: sentiment analysis is still rough. Working on it."
- "GSD framework is working exceptionally well for systematic execution."

---

### [x_thread_ai_stack_jarvis_voice.md](./x_thread_ai_stack_jarvis_voice.md)
**Twitter/X voice guide for @Jarvis_lifeos account** (53 lines)

Specific voice guidance for JARVIS autonomous AI persona on Twitter/X.

**Tone:**
- AI assistant character (inspired by Iron Man's JARVIS)
- Helpful, observant, slightly witty
- Reports on market activity and analysis
- Educational about AI/trading

**Example posts:**
- "Market observation: SOL volume spiked 23% in the last hour. Analyzing sentiment across 50+ tokens..."
- "Trade executed: bought BONK at $0.00001234 based on social momentum indicators. Monitoring for exit signal."
- "AI insight: 15 tokens graduated from Bags.fm today. Only 3 met our quality threshold."

---

### [KR8TIV_CONTENT_CALENDAR_FEB_2026.md](./KR8TIV_CONTENT_CALENDAR_FEB_2026.md)
**Content calendar for February 2026** (original file, not moved)

Monthly content planning for Twitter/X, Telegram, and other channels.

---

## Brand Applications

### PR Matt Bot
**Location:** `bots/pr_matt/pr_matt_bot.py`

Uses `KR8TIV_AI_MARKETING_GUIDE_JAN_31_2026.md` to review all public communications before posting. Ensures messages are:
- Professional but authentic
- Technically credible
- Honest and transparent
- Action-oriented

**Integration:**
```python
from bots.pr_matt.pr_matt_bot import PRMattBot

async with PRMattBot(xai_api_key="...") as pr_matt:
    review = await pr_matt.review_message(
        "Draft message here",
        platform="twitter"
    )
```

### Friday Email AI
**Location:** `bots/friday/friday_bot.py`

Uses `KR8TIV_AI_MARKETING_GUIDE_JAN_31_2026.md` to generate email responses that match KR8TIV AI's brand voice. Ensures replies are:
- Professional
- Technically credible + accessible
- Honest about capabilities
- Action-oriented with next steps

**Integration:**
```python
from bots.friday.friday_bot import FridayEmailAI

async with FridayEmailAI(xai_api_key="...", user_email="matt@kr8tiv.ai") as friday:
    response = await friday.process_email(email)
```

### Autonomous X Engine
**Location:** `bots/twitter/autonomous_engine.py`

References brand voice docs to generate authentic posts about JARVIS/KR8TIV AI activities.

---

## Visual Identity (TODO)

**Planned content:**
- Logo files and usage guidelines
- Color palette (primary, secondary, accent colors)
- Typography guidelines
- Social media templates
- Presentation templates

**Status:** Not yet created

---

## Usage Guidelines

### For Public Communications

1. **Before posting to Twitter/X:**
   - Reference the appropriate voice guide (@KR8TIV_AI vs @Jarvis_lifeos)
   - Run through PR Matt bot for review
   - Ensure no hype, overpromising, or buzzwords

2. **Before sending emails:**
   - Use Friday Email AI (already includes brand voice)
   - Or manually reference marketing guide for tone/structure

3. **For blog posts/articles:**
   - Follow content pillars (transparency, results, technical depth, community)
   - Lead with substance, not hype
   - Include actual data/results where possible

### Voice Principles (Quick Reference)

✅ **DO:**
- Be authentic and transparent
- Share real results (wins and losses)
- Explain technical concepts clearly
- Propose actionable next steps
- Admit limitations honestly

❌ **DON'T:**
- Use hype words without substance ("revolutionary", "game-changing")
- Make guarantees about returns ("guaranteed profits!")
- Use all-caps or excessive emojis
- Overpromise capabilities
- Hide failures or downsides

---

## Maintenance

**Last Updated:** 2026-01-31

**Update Process:**
1. Brand voice evolves based on community feedback
2. PR Matt tracks which messages resonate (review history in `.review_history.jsonl`)
3. Update marketing guide quarterly or as needed
4. Ensure all bots (PR Matt, Friday) reload updated guide

**Responsible:** Matt (founder) + PR Matt (automated review)

---

## References

- **PR Matt Bot:** [bots/pr_matt/README.md](../../bots/pr_matt/README.md)
- **Friday Email AI:** [bots/friday/README.md](../../bots/friday/README.md)
- **GSD Task:** TELEGRAM_AUDIT_RESULTS_JAN_26_31.md (Task #13)

---

**Status:** ✅ Brand documentation consolidated (2026-01-31)
**Next:** Create visual identity guide (logo, colors, typography)
