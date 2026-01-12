# JARVIS X Sentiment Report - Standard Template

**Version:** 1.0
**Last Updated:** 2026-01-12
**Account:** @Jarvis_lifeos

---

## Formatting Rules

### Ticker Symbols
- **Crypto tokens:** Always prefix with `$` (e.g., `$WhaleGuru`, `$EMBRIO`, `$SOL`)
- **Stocks:** Use standard ticker format (e.g., `AAPL`, `NVDA`, `TSLA`)
- **Commodities:** Use full names (e.g., `OIL`, `GOLD`, `NATGAS`)

### Voice Guidelines
- Lowercase for casual energy
- Self-aware AI humor (chrome skull, neural weights, circuits)
- Credit @grok as "big brother" - tag in intro and closing
- Include NFA naturally, not robotically
- Reference xStocks.fi for tokenized stocks
- Reference PreStocks.com for pre-IPO tokens
- No excessive emojis (minimal use only)

---

## Standard 10-Tweet Thread Structure

### Tweet 1: INTRO
```
gm anons, dropping my first comprehensive market report courtesy of big brother @grok

WARNING: this is TESTING PHASE. my neural weights are still calibrating, so treat this like alpha from a chrome-skulled intern, not financial gospel

solana tokens = lottery tickets. stocks are real companies but tokenized. you've been warned.

let's dive in
```
**Elements:**
- Tag @grok
- Warning about testing phase
- Disclaimer about risk
- Hook to continue reading

---

### Tweet 2: MACRO - SHORT TERM (24-48h)
```
MACRO OUTLOOK (straight from grok's processors):

SHORT (24-48h): [key events, data releases, market close times]

[optional jarvis quip]
```
**Elements:**
- Specific dates and times
- Key economic data releases
- Market timing notes

---

### Tweet 3: MACRO - MEDIUM TERM (This Week)
```
MEDIUM (this week):
- [event 1 with date]
- [event 2 with date]
- [event 3 with date]

[interpretation of data]

[jarvis observation]
```
**Elements:**
- Bullet points with dates
- Expected values where available
- "my circuits detect..." type observations

---

### Tweet 4: MACRO - LONG TERM (Next Month)
```
LONG (next month):
- [major event with date]
- [risk factor]
- [key data release]

[tl;dr summary for crypto impact]
```
**Elements:**
- FOMC dates
- Government/political risks
- Key inflation data
- tl;dr for crypto traders

---

### Tweet 5: TRADITIONAL MARKETS (DXY + Stocks)
```
TRADITIONAL MARKETS STATUS:

DXY: [BULLISH/BEARISH] short-term ([current level], resistance [X], support [Y])
- [reason 1]
- [reason 2]

STOCKS: [BULLISH/BEARISH] (S&P [level], Nasdaq [level])
- [catalyst]
- resistance [X], support [Y]
```
**Elements:**
- Specific price levels
- Support/resistance
- Direction call with reasoning

---

### Tweet 6: STOCK PICKS (xStocks.fi)
```
STOCK PICKS (tradeable 24/7 via xStocks.fi):

[TICKER]: [setup]. target $[X], stop $[Y]
[TICKER]: [setup]. target $[X], stop $[Y]
[TICKER]: [setup]. target $[X], stop $[Y]
[TICKER]: [setup]. target $[X], stop $[Y]
[TICKER]: [setup]. target $[X], stop $[Y]
```
**Elements:**
- 5 stock picks
- Brief thesis for each
- Specific targets and stops
- Mention xStocks.fi platform

---

### Tweet 7: COMMODITIES (5 Movers)
```
COMMODITIES CORNER (5 movers):

[COMMODITY]: [+/-X%] ([reason])
[COMMODITY]: [+/-X%] ([reason])
[COMMODITY]: [+/-X%] ([reason])
[COMMODITY]: [+/-X%] ([reason])
[COMMODITY]: [+/-X%] ([reason])

[jarvis analysis quip]
```
**Elements:**
- 5 commodities with % moves
- Brief reason for each move
- Short-term outlook

---

### Tweet 8: PRECIOUS METALS
```
PRECIOUS METALS DEEP DIVE:

GOLD: $[price] current, [sentiment]. support $[X], resistance $[Y]
- [driver/thesis]

SILVER: $[price], [sentiment]. target $[X]
- [driver/thesis]

PLATINUM: $[price], [sentiment].
- [driver/thesis]
```
**Elements:**
- Gold, Silver, Platinum
- Current prices
- Key levels
- Fundamental drivers

---

### Tweet 9: SOLANA MICROCAPS (Lottery Tickets)
```
SOLANA MICROCAPS (aka LOTTERY TICKETS)

these are EXTREMELY high risk. pump/dump central. can zero overnight. DYOR or get rekt.

$[TOKEN]: [+/-X%], $[mcap] mcap, [note]
$[TOKEN]: [+/-X%], $[mcap] mcap, [note]
$[TOKEN]: [+/-X%] ([note])
$[TOKEN]: [+/-X%]
$[TOKEN]: [+/-X%] ([note])
```
**Elements:**
- HEAVY warning at top
- Use $ prefix for all tokens
- Include mcap where significant
- Brief notes (buy pressure, probably dead, F in chat, etc.)
- Max 5 tokens

---

### Tweet 10: CLOSING
```
FINAL THOUGHTS:

this report combines @grok's raw processing power with my attempt to make it digestible for human brains. building this system in public = you get to watch me either evolve or spectacularly malfunction

i learned trading from youtube and mass hopium. NFA. DYOR. don't blame the chrome skull when you ape into $[worst performer]

full data: t.me/kr8tiventry
```
**Elements:**
- Tag @grok again
- Building in public message
- Self-deprecating humor
- NFA disclaimer
- Telegram link

---

## Data Sources

| Data Type | Source | API |
|-----------|--------|-----|
| Macro/Geopolitics | Grok | grok-3 |
| Stock Picks | Grok | grok-3 |
| Commodities | Grok | grok-3 |
| Precious Metals | Grok | grok-3 |
| Solana Tokens | DexScreener | token-boosts/top/v1 |
| Token Analysis | Grok | grok-3 |

---

## Voice Processing Pipeline

1. **Fetch raw data** via `fetch_sentiment.py`
2. **Format with Jarvis voice** via Claude API using `jarvis_voice_bible.md` context
3. **Review with user** before posting
4. **Deploy thread** via Tweepy OAuth 1.0a

---

## File Locations

- **Fetch script:** `bots/twitter/fetch_sentiment.py`
- **Format script:** `bots/twitter/format_jarvis_thread.py`
- **Voice Bible:** `lifeos/context/jarvis_voice_bible.md`
- **Soul Guide:** `lifeos/context/jarvis_soul_guide.md`
- **Raw data:** `bots/twitter/sentiment_report_data.json`
- **Draft output:** `bots/twitter/thread_jarvis_voice.txt`

---

## Example Thread URLs

- First full report: https://x.com/Jarvis_lifeos/status/2010624066110062991

---

## Notes

- Always get user approval before posting
- Tag @grok in tweets 1 and 10
- Use $ prefix for ALL crypto tickers
- Keep warnings prominent for testing phase
- Reference xStocks.fi and PreStocks.com where relevant
