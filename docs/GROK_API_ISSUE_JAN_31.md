# Grok API Key Issue - Jan 31, 2026

**Status:** Root cause identified - BLOCKED (requires manual fix)
**Priority:** MEDIUM (feature degradation, not system critical)

---

## Issue Summary

Grok API calls failing with 400 error showing truncated key "xa***pS" instead of full key.

---

## Investigation Results

### ✅ Verified: Key Loads Correctly
```bash
$ python -c "import os; from dotenv import load_dotenv; load_dotenv('bots/twitter/.env'); print(os.getenv('XAI_API_KEY')[:20])"
xai-RuHo5zq2NxLSIL7p  # ← Correct prefix

$ python -c "..."
Key length: 84 chars  # ← Full key loaded
```

### ✅ Verified: Key Sent Correctly to API
```python
# GrokClient sends full 84-char key in Authorization header
headers = {
    "Authorization": f"Bearer {self.api_key}",  # ← Full key here
    "Content-Type": "application/json"
}
```

### ✅ Verified: API Rejects the Key
```bash
Status: 400
Response: {
  "code":"Client specified an invalid argument",
  "error":"Incorrect API key provided: xa***pS. You can obtain an API key from https://console.x.ai."
}
```

---

## Root Cause

**The API key is INVALID or REVOKED.**

The "xa***pS" in the error message is **not truncation** - it's the xAI server showing a **masked version** of the key it received (for security reasons).

The server is saying: "You sent me key 'xai-RuHo5zq...5FpS' (shown as 'xa***pS') and it's incorrect."

---

## Why This Looked Like Truncation

| What We Saw | What We Thought | Reality |
|-------------|----------------|----------|
| Error shows "xa***pS" | Key truncated to 7 chars | Server masking 84-char key |
| Missing "i-" prefix | Env var bug | Server strips "xai-" prefix in error |
| Missing middle chars | String slicing bug | Server replaces with "***" for security |

---

## Impact

**Affected Features:**
- ❌ Grok-powered tweet generation
- ❌ Grok sentiment analysis fallback
- ❌ Jarvis voice responses via Grok
- ❌ Image generation (grok-2-image model)

**Still Working:**
- ✅ Claude-based content generation
- ✅ Twitter posting (OAuth issue separate)
- ✅ All other bots and features

---

## Resolution Required

**Manual action needed at xAI console:**

### Step 1: Check Current Key Status
1. Visit https://console.x.ai
2. Navigate to API Keys section
3. Check if current key is revoked or expired
4. Check usage limits/quotas

### Step 2: Generate New Key
```bash
# At console.x.ai:
1. Click "Create new secret key"
2. Copy the generated key (starts with "xai-")
3. Save it securely (won't be shown again)
```

### Step 3: Update Configuration
```bash
# Update .env file
cd bots/twitter
nano .env  # or vim/code

# Replace line 19:
XAI_API_KEY=<new_key_here>

# Update secrets/keys.json if needed
```

### Step 4: Restart Affected Services
```bash
# Supervisor will auto-restart, or manually:
supervisorctl restart autonomous_x
supervisorctl restart twitter_poster
```

### Step 5: Test
```bash
cd /path/to/Jarvis
python -c "
import asyncio
from bots.twitter.grok_client import GrokClient

async def test():
    client = GrokClient()
    resp = await client.generate_tweet('Test: say hello')
    print(f'Success: {resp.success}')
    print(f'Content: {resp.content if resp.success else resp.error}')
    await client.close()

asyncio.run(test())
"
```

---

## Alternative: Switch to Claude-Only Mode

If xAI API is not available or costs too much, disable Grok fallback:

```python
# In bots/twitter/jarvis_voice.py or similar
ENABLE_GROK_FALLBACK = False  # Set to False to skip Grok API
```

This will make the bots use Claude exclusively (which is already working).

---

## Logs

**Error Pattern (last 100 occurrences):**
```
2026-01-31 10:47:03 - jarvis.grok - ERROR - Grok API error: 400 - {"error":"Incorrect API key provided: xa***pS"}
2026-01-31 10:47:34 - jarvis.grok - ERROR - Grok API error: 400 - {"error":"Incorrect API key provided: xa***pS"}
2026-01-31 10:50:48 - jarvis.grok - ERROR - Grok API error: 400 - {"error":"Incorrect API key provided: xa***pS"}
... (continues every few minutes)
```

**First Occurrence:** 2026-01-31 05:30:57 UTC
**Latest Occurrence:** 2026-01-31 11:02:17 UTC
**Frequency:** Every API call attempt (~every 3-5 minutes)

---

## Cost Impact

**Current Grok Usage (from state file):**
- Total input tokens: Unknown (state file not checked)
- Total output tokens: Unknown
- Daily cost: $0 (no successful calls)
- All-time cost: Previous successful calls only

**If Key Was Valid:**
- $0.005 per 1K input tokens
- $0.015 per 1K output tokens
- $0.02 per image generation

---

## Related Issues

This is similar to:
1. **Twitter OAuth 401** - Also requires manual fix at developer portal
2. **Telegram bot token exposure** - Credential management issue

**Pattern:** Multiple external service credentials need rotation/verification.

---

## Recommended Next Steps

1. **Immediate:** Document this as BLOCKED until user has access to xAI console
2. **Short-term:** User visits console.x.ai and generates new key
3. **Long-term:** Implement credential health checks (ping APIs on startup)

---

## Status

**BLOCKED** - Requires user action at https://console.x.ai

**Add to critical tasks list:**
- [ ] User: Check xAI API key status
- [ ] User: Generate new xAI API key if revoked
- [ ] Update XAI_API_KEY in bots/twitter/.env
- [ ] Restart supervisor
- [ ] Test Grok API calls

---

**Investigation Complete:** Jan 31, 2026 11:05 UTC
