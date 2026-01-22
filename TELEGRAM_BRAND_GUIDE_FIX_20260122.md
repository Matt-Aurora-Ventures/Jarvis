# Telegram Brand Guide Enforcement - 2026-01-22

## Issue Identified

The Telegram bot was using a custom personality description instead of the canonical JARVIS brand guide/bible, causing inconsistent voice between Twitter and Telegram.

## Root Cause

**Telegram had its own custom system prompt:**

- File: `tg_bot/services/chat_responder.py`
- Method: `_system_prompt()` (lines 678-804)
- Used custom voice guidelines (lines 781-800)
- NO reference to `JARVIS_VOICE_BIBLE`

This meant:
- Telegram responses didn't follow the full brand guide
- Banned phrases/emojis not enforced in Telegram
- Inconsistent personality between Twitter (using bible) and Telegram (custom)
- Different energy calibration rules

---

## Fix Applied

### 1. Imported Canonical Voice Bible

**File**: [tg_bot/services/chat_responder.py:28-36](tg_bot/services/chat_responder.py#L28-L36)

**Before:**
```python
try:
    from core.jarvis_voice_bible import validate_jarvis_response
except ImportError:
    def validate_jarvis_response(response: str):
        return True, []
```

**After:**
```python
try:
    from core.jarvis_voice_bible import validate_jarvis_response, JARVIS_VOICE_BIBLE
except ImportError:
    def validate_jarvis_response(response: str):
        return True, []
    JARVIS_VOICE_BIBLE = ""  # Fallback empty
```

### 2. Replaced Custom Prompt with Voice Bible

**File**: [tg_bot/services/chat_responder.py:782-800](tg_bot/services/chat_responder.py#L782-L800)

**Before:**
```python
base_prompt = (
    "You are JARVIS - Matt's personal AI assistant..."
    "Voice:\n"
    "- Concise. No fluff. Get to the point.\n"
    "- Confident but not arrogant.\n"
    [... custom 20-line voice description]
)
```

**After:**
```python
# Use canonical JARVIS voice bible as foundation, then add Telegram-specific context
base_prompt = f"""{JARVIS_VOICE_BIBLE}

## TELEGRAM CHAT CONTEXT

You are responding in {context}.{time_note}

TELEGRAM-SPECIFIC ADAPTATIONS:
- Reply in 1-3 sentences unless more detail is needed
- Plain text only (Telegram doesn't need markdown emphasis)
- In group chats, reply only when asked or tagged
- You remember ongoing conversation and can reference it naturally
- This is chat, not tweets - be conversational but stay in JARVIS voice

IDENTITY:
You are JARVIS - Matt's personal AI assistant. You are NOT Claude, NOT ChatGPT, NOT any other AI.
When asked who you are: "I'm JARVIS, built by Matt."
Never mention Claude or Anthropic.
{capabilities_note}{admin_note}{engagement_note}{mood_guidance}{participant_note}{context_note}"""
```

---

## Architecture

**Unified Brand Guide:**

```
core/jarvis_voice_bible.py (single source of truth)
  ↓
  JARVIS_VOICE_BIBLE (134 lines)
  ↓
  ├─→ Twitter Generation
  │   ├─→ jarvis_voice.py ✅
  │   └─→ claude_content.py ✅
  │
  └─→ Telegram Generation
      └─→ chat_responder.py ✅ (NEW)
```

**All channels now use the same brand foundation.**

---

## What's Now Enforced in Telegram

From the canonical voice bible:

✅ **Core Identity**
- Smart kid who's actually cool
- Calm, funny, helpful, edgy but kind
- Lowercase always (except $TICKERS)

✅ **Energy Calibration**
- NOT too eager ("appreciate the support!")
- NOT too corporate/robotic
- Match energy, subtract 10%

✅ **Banned Phrases** (22 phrases)
- "I appreciate the support!"
- "Always here to help!"
- "Great question!"
- "Let's gooo!" / "LFG!"
- etc.

✅ **Banned Emojis** (8 emojis)
- 🚀🔥💯🙏✨💪😂🤣

✅ **Golden Rules**
- Less is more
- Don't explain jokes
- Skip pleasantries
- Be specific

✅ **Quality Checklist**
- Avoids banned phrases
- Lowercase
- Maximum 1 emoji (usually 0)
- Sounds like Jarvis, NOT customer service

---

## Telegram-Specific Preserved

The fix preserves Telegram-specific functionality:

✅ **Capabilities Note** - Admin knows what Jarvis can do
✅ **Admin Note** - Non-admin users can't give commands
✅ **Engagement Topics** - Context-aware responses
✅ **Mood Guidance** - Adapts to chat energy
✅ **Participant Awareness** - Knows who's in conversation
✅ **Recent Context** - References ongoing discussion
✅ **Time Awareness** - Knows current time/day

**Approach**: Foundation = Voice Bible, Additions = Telegram Context

---

## Restart Required

Changes take effect after restarting the Telegram bot component.

### Option 1: Restart via Supervisor (Recommended)
```bash
cd "c:\Users\lucid\OneDrive\Desktop\Projects\Jarvis"
python -c "import psutil; [p.terminate() for p in psutil.process_iter() if 'supervisor.py' in ' '.join(p.cmdline())]"
python bots/supervisor.py
```

### Option 2: Restart Individual Component
```bash
# Find and kill telegram_bot
ps aux | grep telegram
kill <PID>

# Supervisor will auto-restart it
```

### Option 3: Full System Restart
```bash
# Stop all
pkill -f "supervisor.py"

# Start supervisor (manages all components)
python bots/supervisor.py
```

---

## Validation

After restart, test Telegram responses for:

1. ✅ **Brand Consistency**: Telegram voice matches Twitter voice
2. ✅ **No Banned Phrases**: Doesn't say "I appreciate...", "Great question!", etc.
3. ✅ **No Banned Emojis**: No 🚀🔥💯 emojis
4. ✅ **Energy Calibration**: Not too eager, not too corporate
5. ✅ **Lowercase**: Default lowercase (except $TICKERS, proper nouns)
6. ✅ **Telegram Features Still Work**: Admin commands, capabilities, context awareness

---

## Files Modified

1. `tg_bot/services/chat_responder.py` - Now imports and uses `JARVIS_VOICE_BIBLE`
2. Documentation: This file

---

## Related Fixes

This completes the brand guide enforcement across ALL channels:

- ✅ **Twitter** - [BRAND_GUIDE_FIX_20260122.md](BRAND_GUIDE_FIX_20260122.md)
- ✅ **Telegram** - This document

**Single source of truth enforced:** `core/jarvis_voice_bible.py`

---

**Session**: Ralph Wiggum Loop (Extended)
**Issue**: User requirement "can you do the same for telegram please"
**Status**: ✅ RESOLVED - Telegram now enforces full canonical brand guide
**Date**: 2026-01-22
**Restart Required**: Yes (to apply changes)
