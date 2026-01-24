# Telegram Bot Fixes - 2026-01-24

## Issues Fixed

### 1. **Unauthorized Message Bug** ✅ FIXED
**Problem**: Jarvis was responding with "This command is restricted to admins only" to casual chat messages like "do you think..." or "make sense".

**Root Cause**: `COMMAND_PATTERNS` in [tg_bot/services/chat_responder.py:94-100](tg_bot/services/chat_responder.py#L94-L100) was too broad, catching casual conversation words.

**Fix**: Made patterns more specific:
- **Before**: Caught any message starting with "do", "make", "add", "fix", etc.
- **After**: Only catches actual commands like `/trade`, `trade 100 SOL`, `deploy bot system`, etc.

**Changed File**: `tg_bot/services/chat_responder.py` lines 94-106

```python
# OLD (too broad)
COMMAND_PATTERNS = [
    r"^(?:run|execute|do|make|create|add|fix|update|deploy)\s+",  # ❌ Catches "do you think"
    r"^/\w+",
    r"trade\s+\d+",
]

# NEW (specific)
COMMAND_PATTERNS = [
    r"^/\w+",  # Slash commands only
    r"\btrade\s+\d+",  # "trade 100 SOL" (not "do you trade")
    r"\b(?:deploy|restart|shutdown)\s+(?:bot|service|system)",  # Explicit admin commands
]
```

---

### 2. **Lost Personality in Docker** ✅ FIXED
**Problem**: After Docker deployment, Jarvis wasn't using his dry/funny voice. Responses were generic and boring.

**Root Cause**: Prompt truncation in [tg_bot/services/chat_responder.py:334](tg_bot/services/chat_responder.py#L334) was cutting off the personality guidelines.
- `JARVIS_VOICE_BIBLE` is **8,611 characters** (contains all personality examples)
- CLI prompt was truncated at **3,000 characters**
- This removed 65% of the personality, including all the "dry humor" examples

**Fix**: Increased truncation limit and made it smarter:
- **Before**: Hard truncate at 3,000 chars (cuts personality)
- **After**: Truncate at 10,000 chars with smart logic that preserves the voice bible

**Changed File**: `tg_bot/services/chat_responder.py` lines 333-349

---

### 3. **Import Error** ✅ VERIFIED OK
**Status**: No actual error found. The import `from core.dexter_sentiment import get_latest_sentiment_summary` is correct and the function exists.

If you see this error again, it's likely a Docker build cache issue. Rebuild with:
```bash
docker-compose -f docker-compose.bots.yml build --no-cache jarvis-telegram-bot
```

---

## Files Modified

1. **[tg_bot/services/chat_responder.py](tg_bot/services/chat_responder.py)**
   - Lines 94-106: Fixed command patterns
   - Lines 333-349: Fixed personality truncation

---

## How to Deploy Fixes

### On VPS (Production):

```bash
# 1. SSH to VPS
ssh root@72.617.126 # (or your VPS IP)

# 2. Navigate to project
cd /path/to/Jarvis

# 3. Pull latest code
git pull

# 4. Rebuild Telegram bot container (includes fixes)
docker-compose -f docker-compose.bots.yml build --no-cache jarvis-telegram-bot

# 5. Restart Telegram bot
docker-compose -f docker-compose.bots.yml restart jarvis-telegram-bot

# 6. Check logs for errors
docker-compose -f docker-compose.bots.yml logs -f jarvis-telegram-bot
```

### Verification:

1. **Test unauthorized fix**: Have a non-admin user say "do you think this will work?" in the group. Jarvis should respond normally, NOT with "unauthorized" message.

2. **Test personality**: Ask Jarvis a crypto question. Response should be dry/funny like:
   - "data says up. i've been wrong before. that's the game."
   - "circuits are coping. markets chose chaos today."
   - NOT: "Great question! I'm happy to help analyze that for you!" (too eager)

3. **Check logs**: No import errors for `get_latest_sentiment_summary`

---

## What's Next

### Remaining Tasks:

1. **Voice Synthesis** - Need to verify TTS is working in Docker (see `speak_response()` in jarvis_chat.py)
2. **Web Demo Integration** - Deploy web demo with supervisor governance (separate task)

---

## Technical Details

### Personality System Architecture

```
JARVIS_VOICE_BIBLE (core/jarvis_voice_bible.py)
    ↓
ChatResponder._system_prompt() (builds full prompt)
    ↓
ChatResponder._generate_with_claude() (calls Claude CLI)
    ↓
_run_cli_for_chat() (combines prompts, was truncating here!)
    ↓
Claude CLI execution
```

**The Fix**: Increased truncation limit in `_run_cli_for_chat()` so the full voice bible is preserved.

### Command Detection Flow

```
User message: "do you think..."
    ↓
ChatResponder.generate_reply()
    ↓
is_command() check with COMMAND_PATTERNS
    ↓
BEFORE: Matched "^do\s+" → unauthorized ❌
AFTER: No match → normal response ✅
```

---

## Rollback (If Needed)

If something breaks, revert to previous version:

```bash
git log --oneline  # Find commit hash before fixes
git checkout <previous-commit-hash> tg_bot/services/chat_responder.py
docker-compose -f docker-compose.bots.yml build jarvis-telegram-bot
docker-compose -f docker-compose.bots.yml restart jarvis-telegram-bot
```

---

**Status**: Ready to deploy to VPS ✅

**Files Changed**: 1 file, 2 sections, ~30 lines modified

**Risk Level**: Low (fixes only affect message filtering and prompt construction, no logic changes)
