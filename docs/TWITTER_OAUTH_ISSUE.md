# Twitter OAuth 401 Issue

**Date:** 2026-01-31 09:45 UTC
**Status:** BLOCKED - Requires manual intervention

---

## Problem

Both OAuth 1.0a and OAuth 2.0 authentication failing with 401 Unauthorized:

```
2026-01-31 09:39:53,000 - bots.twitter.twitter_client - WARNING - OAuth 1.0a connection failed: 401 Unauthorized
2026-01-31 09:39:54,903 - bots.twitter.twitter_client - ERROR - Token refresh failed (status 401)
2026-01-31 09:39:54,905 - bots.twitter.twitter_client - ERROR - OAuth 2.0 /users/me failed (status 401)
```

## Tokens Present

All required tokens are configured in `bots/twitter/.env`:
- ✅ X_API_KEY
- ✅ X_API_SECRET
- ✅ X_BEARER_TOKEN
- ✅ X_ACCESS_TOKEN
- ✅ X_ACCESS_TOKEN_SECRET
- ✅ X_OAUTH2_CLIENT_ID
- ✅ X_OAUTH2_CLIENT_SECRET
- ✅ X_OAUTH2_ACCESS_TOKEN
- ✅ X_OAUTH2_REFRESH_TOKEN
- ✅ JARVIS_ACCESS_TOKEN (OAuth 1.0a)
- ✅ JARVIS_ACCESS_TOKEN_SECRET (OAuth 1.0a)

## Likely Causes

1. **Tokens Expired/Revoked**
   - OAuth 2.0 tokens may have expired
   - App may have lost access permissions
   - Twitter account may have revoked app access

2. **App Suspended**
   - Developer app may be suspended
   - Rate limits exceeded
   - Policy violations

3. **Credentials Changed**
   - API keys regenerated on developer portal
   - Client secrets rotated

## Resolution Steps (Manual)

### Option 1: Check Developer Portal
1. Go to https://developer.x.com/
2. Navigate to your app: "Projects & Apps"
3. Check app status (active/suspended)
4. Verify API key and secret match .env file
5. Check if app has required permissions:
   - Read and write tweets
   - Access user data

### Option 2: Regenerate OAuth 2.0 Tokens
1. Go to OAuth 2.0 settings in developer portal
2. Revoke existing tokens
3. Generate new access token + refresh token
4. Update in `bots/twitter/.env`:
   - X_OAUTH2_ACCESS_TOKEN
   - X_OAUTH2_REFRESH_TOKEN

### Option 3: Regenerate OAuth 1.0a Tokens (PIN Flow)
1. Use Twitter's PIN-based OAuth flow
2. Get new access token + secret
3. Update in `bots/twitter/.env`:
   - JARVIS_ACCESS_TOKEN
   - JARVIS_ACCESS_TOKEN_SECRET

### Option 4: Create New App
If app is suspended:
1. Create new Twitter Developer App
2. Configure permissions
3. Generate new API keys
4. Update all credentials in .env

## Impact

- ❌ twitter_poster: Cannot post sentiment tweets
- ❌ autonomous_x: Cannot post autonomous updates
- ⚠️ Social engagement features disabled

## Workaround

Use Grok AI fallback for sentiment analysis (still works) but posting is disabled.

## Testing After Fix

```bash
cd bots && python supervisor.py
# Monitor log for: twitter_poster component should start without 401 error
```

Or test directly:
```bash
cd bots/twitter
python -c "from twitter_client import TwitterClient; client = TwitterClient(); print('Success!' if client.is_connected else 'Failed')"
```

---

**Note:** This requires access to Twitter Developer Portal and cannot be fixed automatically.
