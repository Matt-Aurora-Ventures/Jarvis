# JARVIS Twitter Bot - Autonomous Architecture

## Logic Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        JARVIS AUTONOMOUS TWITTER ENGINE                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────────┐    ┌──────────────────┐    ┌──────────────────┐      │
│  │  CONTENT ENGINE  │    │  MENTION HANDLER │    │  VIBE CODING     │      │
│  │  (autonomous)    │    │  (reactive)      │    │  (command exec)  │      │
│  └────────┬─────────┘    └────────┬─────────┘    └────────┬─────────┘      │
│           │                       │                       │                 │
│           ▼                       ▼                       ▼                 │
│  ┌──────────────────────────────────────────────────────────────────┐      │
│  │                      TWITTER CLIENT (API v2)                      │      │
│  │  • Post tweets     • Get mentions    • Reply to tweets           │      │
│  │  • Upload media    • Like tweets     • Quote retweet             │      │
│  └──────────────────────────────────────────────────────────────────┘      │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘

                              DETAILED FLOWS
                              ═════════════

╔═══════════════════════════════════════════════════════════════════════════╗
║                         1. AUTONOMOUS CONTENT ENGINE                       ║
╠═══════════════════════════════════════════════════════════════════════════╣
║                                                                            ║
║   every 60s check                                                          ║
║        │                                                                   ║
║        ▼                                                                   ║
║   ┌─────────────────┐                                                      ║
║   │ Time for post?  │───NO───► Sleep 60s ─────────────────┐               ║
║   │ (hourly default)│                                     │               ║
║   └───────┬─────────┘                                     │               ║
║           │ YES                                           │               ║
║           ▼                                               │               ║
║   ┌─────────────────┐                                     │               ║
║   │ Select Content  │                                     │               ║
║   │ Type (weighted) │                                     │               ║
║   └───────┬─────────┘                                     │               ║
║           │                                               │               ║
║           ▼                                               │               ║
║   ┌─────────────────────────────────────────────┐        │               ║
║   │ 18 Content Generators (weighted selection)  │        │               ║
║   │                                             │        │               ║
║   │  • market_update (15%)                      │        │               ║
║   │  • trending_token (15%)                     │        │               ║
║   │  • hourly_update (10%)                      │        │               ║
║   │  • agentic_thought (10%)                    │        │               ║
║   │  • quote_tweet (8%)                         │        │               ║
║   │  • portfolio_update (8%)                    │        │               ║
║   │  • self_aware_commentary (7%)               │        │               ║
║   │  • jarvis_musings (5%)                      │        │               ║
║   │  • community_question (5%)                  │        │               ║
║   │  • alpha_share (5%)                         │        │               ║
║   │  • breaking_news (4%)                       │        │               ║
║   │  • thread (4%)                              │        │               ║
║   │  • meme/roast (4%)                          │        │               ║
║   └───────────────┬─────────────────────────────┘        │               ║
║                   │                                       │               ║
║                   ▼                                       │               ║
║   ┌─────────────────┐                                     │               ║
║   │ Generate Draft  │                                     │               ║
║   │ via Claude Opus │                                     │               ║
║   └───────┬─────────┘                                     │               ║
║           │                                               │               ║
║           ▼                                               │               ║
║   ┌─────────────────┐                                     │               ║
║   │ Generate Image? │───YES───► Grok Imagine ───┐        │               ║
║   │ (sometimes)     │                           │        │               ║
║   └───────┬─────────┘                           │        │               ║
║           │ NO                                  │        │               ║
║           ▼                                     ▼        │               ║
║   ┌─────────────────────────────────────────────┐        │               ║
║   │         POST TWEET                          │        │               ║
║   │  • Add $cashtags, hashtags                  │        │               ║
║   │  • Include contract address if token        │        │               ║
║   │  • Attach image if generated                │        │               ║
║   └───────────────────────────────────────────┬─┘        │               ║
║                                               │          │               ║
║                                               ▼          │               ║
║                                        Store in Memory ──┘               ║
║                                                                           ║
╚═══════════════════════════════════════════════════════════════════════════╝

╔═══════════════════════════════════════════════════════════════════════════╗
║                     2. MENTION HANDLER (Standard Replies)                  ║
╠═══════════════════════════════════════════════════════════════════════════╣
║                                                                            ║
║   Poll mentions every 30-60s                                               ║
║        │                                                                   ║
║        ▼                                                                   ║
║   ┌─────────────────┐                                                      ║
║   │ GET /mentions   │                                                      ║
║   │ since_id: last  │                                                      ║
║   └───────┬─────────┘                                                      ║
║           │                                                                ║
║           ▼                                                                ║
║   For each mention:                                                        ║
║        │                                                                   ║
║        ▼                                                                   ║
║   ┌─────────────────┐                                                      ║
║   │ Coding request? │───YES───► Route to VIBE CODING ───────────────┐     ║
║   │ (@aurora_ventures)                                              │     ║
║   └───────┬─────────┘                                               │     ║
║           │ NO                                                      │     ║
║           ▼                                                         │     ║
║   ┌─────────────────┐                                               │     ║
║   │ Random chance?  │───NO───► Skip (avoid spam) ───────────────────┤     ║
║   │ (30% reply rate)│                                               │     ║
║   └───────┬─────────┘                                               │     ║
║           │ YES                                                     │     ║
║           ▼                                                         │     ║
║   ┌─────────────────┐                                               │     ║
║   │ Generate reply  │                                               │     ║
║   │ via Claude/Grok │                                               │     ║
║   └───────┬─────────┘                                               │     ║
║           │                                                         │     ║
║           ▼                                                         │     ║
║   ┌─────────────────┐                                               │     ║
║   │ POST reply      │                                               │     ║
║   │ as @Jarvis_     │                                               │     ║
║   │ lifeos          │                                               │     ║
║   └─────────────────┘                                               │     ║
║                                                                      │     ║
╚══════════════════════════════════════════════════════════════════════╝═════╝

╔═══════════════════════════════════════════════════════════════════════════╗
║                3. VIBE CODING FROM TWITTER (@aurora_ventures)              ║
╠═══════════════════════════════════════════════════════════════════════════╣
║                                                                            ║
║   Trigger: @Jarvis_lifeos mention from @aurora_ventures                    ║
║        │                                                                   ║
║        ▼                                                                   ║
║   ┌─────────────────┐                                                      ║
║   │ Admin check     │───FAIL───► Ignore ────────────────────────────┐     ║
║   │ (whitelist)     │                                               │     ║
║   └───────┬─────────┘                                               │     ║
║           │ PASS                                                    │     ║
║           ▼                                                         │     ║
║   ┌─────────────────┐                                               │     ║
║   │ Rate limit check│───FAIL───► Reply "slow down" ─────────────────┤     ║
║   │ (5/min max)     │                                               │     ║
║   └───────┬─────────┘                                               │     ║
║           │ PASS                                                    │     ║
║           ▼                                                         │     ║
║   ┌─────────────────┐                                               │     ║
║   │ Reply: "on it.  │                                               │     ║
║   │ give me a sec"  │                                               │     ║
║   └───────┬─────────┘                                               │     ║
║           │                                                         │     ║
║           ▼                                                         │     ║
║   ┌─────────────────┐                                               │     ║
║   │ Execute Claude  │                                               │     ║
║   │ CLI with:       │                                               │     ║
║   │ --print         │                                               │     ║
║   │ --dangerously-  │                                               │     ║
║   │  skip-perms     │                                               │     ║
║   └───────┬─────────┘                                               │     ║
║           │                                                         │     ║
║           ▼                                                         │     ║
║   ┌─────────────────┐                                               │     ║
║   │ TRIPLE SANITIZE │                                               │     ║
║   │ (paranoid mode) │                                               │     ║
║   │ - API keys      │                                               │     ║
║   │ - Tokens        │                                               │     ║
║   │ - Passwords     │                                               │     ║
║   │ - Paths         │                                               │     ║
║   └───────┬─────────┘                                               │     ║
║           │                                                         │     ║
║           ▼                                                         │     ║
║   ┌─────────────────┐                                               │     ║
║   │ Reply: "done.   │                                               │     ║
║   │ [summary]"      │                                               │     ║
║   └─────────────────┘                                               │     ║
║                                                                      │     ║
╚══════════════════════════════════════════════════════════════════════╝═════╝

╔═══════════════════════════════════════════════════════════════════════════╗
║                   4. VIBE CODING FROM TELEGRAM (@matthaynes88)             ║
╠═══════════════════════════════════════════════════════════════════════════╣
║                                                                            ║
║   Same flow as Twitter but:                                                ║
║   • Admin check: user_id == 8527130908                                     ║
║   • Direct message response (not tweet length limited)                     ║
║   • Includes conversation context from memory                              ║
║   • Extracts learnings for future context                                  ║
║                                                                            ║
║   Trigger keywords:                                                        ║
║   fix, add, create, build, implement, change, update, modify,              ║
║   refactor, debug, test, deploy, code, function, class, api,               ║
║   endpoint, command, feature, bug, error, ralph wiggum, vibe code          ║
║                                                                            ║
╚═══════════════════════════════════════════════════════════════════════════╝


## API & Service Requirements

### Currently Used (FREE)

| Service | Purpose | Status |
|---------|---------|--------|
| Twitter API v2 | Post tweets, get mentions | FREE tier works |
| DexScreener API | Trending tokens, pair data | FREE |
| CoinGecko API | BTC/ETH/SOL prices | FREE |
| Anthropic Claude | Voice generation | PAID (your key) |
| xAI Grok | Sentiment analysis, images | PAID (your key) |

### Required for Current Features

| Service | API Key Env Var | Status | Monthly Cost |
|---------|-----------------|--------|--------------|
| Anthropic Claude | `ANTHROPIC_API_KEY` | Required | ~$20-50/mo |
| xAI Grok | `XAI_API_KEY` | Required | ~$10-30/mo |
| Twitter API v2 | `TWITTER_*` keys | Required | FREE |
| DexScreener | None (public) | Working | FREE |
| CoinGecko | None (public) | Working | FREE |

### Optional Enhancements

| Service | Purpose | Cost |
|---------|---------|------|
| Moralis API | Multi-chain token data | ~$50/mo |
| CoinMarketCap Pro | Better price data | ~$30/mo |
| Birdeye Pro | Solana-specific data | ~$50/mo |
| Telegram Bot API | Already integrated | FREE |

## Current Limitations

### 1. ~~Solana-Only Content~~ (FIXED v4.6.1)
Multi-chain support now enabled:
- Supported chains: Solana, Ethereum, Base, BSC, Arbitrum
- GeckoTerminal API for trending tokens across chains
- Chain-aware hashtags and content generation

### 2. No Command Parsing
The bot can't handle specific commands like:
- `@jarvis analyze $BTC`
- `@jarvis price ETH`
- `@jarvis holders [contract]`

**To fix**: Add command parser to mention handler

### 3. No Thread Conversations
Doesn't maintain context across multiple tweets in a thread.

**To fix**: Store conversation_id and track thread context

## File Locations

| Component | File |
|-----------|------|
| Main autonomous engine | `bots/twitter/autonomous_engine.py` |
| Vibe coding (Twitter) | `bots/twitter/x_claude_cli_handler.py` |
| Vibe coding (Telegram) | `tg_bot/services/claude_cli_handler.py` |
| Twitter client | `bots/twitter/twitter_client.py` |
| Start script | `bots/twitter/run_autonomous.py` |
| Data fetching | `bots/twitter/fetch_sentiment.py` |
| Content generation | `bots/twitter/content.py` |

## Starting the Bot

```bash
# Full autonomous mode with vibe coding
cd bots/twitter
python run_autonomous.py

# Test content generation
python run_autonomous.py --test

# Post once and exit
python run_autonomous.py --once

# Custom interval (seconds)
python run_autonomous.py --interval 1800
```

## Security

- Admin whitelist (Twitter): `aurora_ventures`
- Admin whitelist (Telegram): user_id `8527130908`
- Triple-pass output sanitization
- No secrets ever exposed in replies
- Rate limiting: 5 requests/min
- Daily limit: 50 commands
