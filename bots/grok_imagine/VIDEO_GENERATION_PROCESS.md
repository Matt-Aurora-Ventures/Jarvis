# Grok Imagine Video Generation Process

## Current Workflow (v2 - Automated with Base Image)

### Key Learning (Jan 12, 2026)
- Use **base image** (original_jarvis.jpg) for consistent JARVIS style
- Generate **VIDEO from image** (img2video), not new images each time
- Download button selector: `button[aria-label*="ownload"]`
- Video generation takes ~60 seconds after prompt submission

### Step 1: Initial Setup (One-time)
```bash
python bots/grok_imagine/grok_login.py
# Choose option 1 for interactive login
# Login with X/Google in the browser window
# Cookies are saved to grok_cookies.json
```

### Step 2: Generate Video from Base Image
```bash
python bots/grok_imagine/generate_video_from_image.py
# 1. Uploads original_jarvis.jpg (our consistent style)
# 2. Enters video motion prompt (particles, glow, camera drift)
# 3. Presses Enter to generate
# 4. Waits 60 seconds for video generation
# 5. Clicks download button (aria-label="Download")
# 6. Saves to generated/jarvis_btc_video_TIMESTAMP.mp4
```

### Step 3: Approval (In Claude Code chat ONLY)
- Video path is displayed for approval
- User says "APPROVE" to proceed
- **NEVER post to Telegram for approval - always in this chat**
- **NEVER ask "is this okay?" in Telegram**

### Step 4: Post to X
- Use **Twitter API v2** (OAuth 2.0 for posting, tweepy v1.1 for media upload)
- Credentials in `bots/twitter/.env`
- Post tweet with approved video to @jarvis_lifeos
- Account verification prevents posting to wrong account

---

## File Structure
```
bots/grok_imagine/
├── grok_login.py          # Interactive login for grok.com
├── grok_cookies.json      # Saved grok.com auth (gitignored)
├── x_cookies.json         # Saved x.com auth (gitignored)
├── generate_video.py      # Main video generation script
├── grok_imagine.py        # Original automation class
├── post_to_x.py           # Tweet posting script
└── generated/             # Output images/videos
    ├── original_jarvis.jpg
    └── *.png, *.mp4
```

---

## Known Issues & TODOs

### Authentication
- [ ] grok.com and x.com use different auth - need separate cookies
- [ ] Cookies expire - need auto-refresh mechanism
- [ ] Manual login required - should automate with OAuth

### Image Generation
- [ ] Grok Imagine page structure changes frequently
- [ ] Selectors need updating when UI changes
- [ ] No official API yet - browser automation only

### Improvements Planned
1. **OAuth Integration**: Implement X OAuth flow programmatically
2. **Cookie Management**: Auto-detect expiration, refresh seamlessly
3. **Grok API**: When available, switch from browser to API
4. **Unified Auth**: Single login for X + Grok
5. **Error Recovery**: Auto-retry on failures, better logging

---

## Quick Commands

```bash
# Login to Grok (first time or cookies expired)
python bots/grok_imagine/grok_login.py

# Generate image
python bots/grok_imagine/generate_video.py

# Test if cookies still work
python bots/grok_imagine/grok_login.py  # Choose option 2
```

---

## Integration with Tweet Flow

1. Draft tweet (Grok API via temp_tweet_draft.py)
2. Generate video from base image (Grok Imagine via Playwright)
3. Show in chat for approval
4. Post to @jarvis_lifeos via Twitter API v2

**RULE**: All approvals happen in Claude Code chat, NEVER in Telegram.
