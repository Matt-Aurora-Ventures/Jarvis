# ClawdBots New Features - OpenClaw 2026.2.3

## 🆕 Telegram Inline Model Selection

### What's New

Previously, changing models in Telegram required typing:
```
/model claude-opus-4-5-20251101
```

Now, you can use interactive buttons:
```
/models
```

### How It Works

1. **List Models**
   ```
   User: /models

   Bot: Available models:
   [Claude Opus 4.5] [Claude Sonnet 4] [Grok 3] [Grok 2]
   ```

2. **Select Model**
   - Click any button to switch models
   - Instant confirmation
   - Selection persists across sessions

3. **Check Current Model**
   ```
   User: /model

   Bot: Current model: claude-opus-4-5-20251101
   [Claude Opus 4.5] [Claude Sonnet 4] [Grok 3]
   ```

### Benefits

- ✅ No need to remember exact model names
- ✅ Visual selection interface
- ✅ Faster model switching
- ✅ Works on mobile Telegram
- ✅ Selections are properly saved (bug fix)

### Example Use Cases

**Friday (CMO):**
```
User: /models
[Claude Opus 4.5] [Claude Sonnet 4] [Grok 3]

User: *clicks Grok 3 for creative marketing ideas*

Friday: ✓ Switched to grok-3. Ready for creative thinking!
```

**Matt (COO):**
```
User: /models
[Claude Sonnet 4] [Claude Opus 4.5] [Codex]

User: *clicks Codex for coding tasks*

Matt: ✓ Switched to codex. Ready to write code!
```

## 🎮 Discord Presence (Optional)

### What's New

Set custom bot status and activity visible to Discord users.

### Configuration

Add to `clawdbot.json`:

```json
{
  "channels": {
    "discord": {
      "enabled": true,
      "token": "YOUR_DISCORD_TOKEN",
      "presence": {
        "status": "online",      // online, idle, dnd, invisible
        "activity": {
          "name": "Trading on Solana",
          "type": "WATCHING"     // PLAYING, WATCHING, LISTENING, COMPETING
        }
      }
    }
  }
}
```

### Status Types

| Status | Meaning | When to Use |
|--------|---------|-------------|
| `online` | Green dot | Bot is active and ready |
| `idle` | Yellow crescent | Bot is running but not actively used |
| `dnd` | Red dot | Bot is in maintenance mode |
| `invisible` | Offline | Bot is active but appears offline |

### Activity Types

| Type | Display | Example |
|------|---------|---------|
| `PLAYING` | Playing... | "Playing Chess" |
| `WATCHING` | Watching... | "Watching the markets" |
| `LISTENING` | Listening to... | "Listening to user feedback" |
| `COMPETING` | Competing in... | "Competing in trading" |

### Example Configurations

**Trading Bot:**
```json
{
  "presence": {
    "status": "online",
    "activity": {
      "name": "Solana markets 📈",
      "type": "WATCHING"
    }
  }
}
```

**Code Bot:**
```json
{
  "presence": {
    "status": "online",
    "activity": {
      "name": "with TypeScript",
      "type": "PLAYING"
    }
  }
}
```

**Maintenance Mode:**
```json
{
  "presence": {
    "status": "dnd",
    "activity": {
      "name": "System Updates",
      "type": "WATCHING"
    }
  }
}
```

## 🔒 Security Improvements

### Model Override Persistence

**Fixed:** Telegram button model selections are now properly saved.

**Before:**
- User selects model via button
- Selection ignored on next session
- Reverts to default model

**After:**
- User selects model via button
- Selection saved to session
- Persists across restarts

### Benefits

- ✅ Consistent model usage
- ✅ User preferences respected
- ✅ Better cost control (users can stay on cheaper models)

## 💬 Message Indicators

### What's New

Improved visual indicators for new messages in web chat interface.

### Features

- New message badge on unread chats
- Typing indicators for active chats
- Read/unread status synchronization
- Smoother animation transitions

### Visual Improvements

**Before:**
```
Chat List
- Friday (2)
- Matt (1)
- Jarvis
```

**After:**
```
Chat List
🔵 Friday (2 new)
🔵 Matt (1 new)
   Jarvis
```

## 🚀 Performance Improvements

### Installation Speed

**Optimizations:**
- Faster npm package resolution
- Parallel dependency installation
- Reduced Docker image size
- Better caching strategies

**Results:**
- 30% faster container startup
- 15% smaller image size
- Reduced network bandwidth

## 🛠️ Developer Experience

### Better Error Messages

**Before:**
```
Error: Model not found
```

**After:**
```
Error: Model 'claude-opus-5' not found

Available models:
- claude-opus-4-5-20251101
- claude-sonnet-4-20250514
- grok-3

Hint: Use /models command to see all available models
```

### Health Check Improvements

**Enhanced endpoints:**
```bash
# Basic health
curl http://localhost:18789/health

# Detailed health
curl http://localhost:18789/__clawdbot__/health/detailed

# Canvas check (for Docker healthcheck)
curl http://localhost:18789/__clawdbot__/canvas/
```

## 📊 Metrics & Monitoring

### New Telemetry

Track bot usage:
- Model selection frequency
- Response times by model
- Error rates
- User engagement

### Enable Telemetry

```json
{
  "telemetry": {
    "enabled": true,
    "anonymize": true,
    "endpoint": "https://telemetry.openclaw.ai"
  }
}
```

## 🎯 Migration Checklist

After updating, test these features:

### Telegram
- [ ] `/models` shows inline buttons
- [ ] Clicking buttons switches models
- [ ] Model selection persists after restart
- [ ] `/model` shows current model

### Discord (if enabled)
- [ ] Bot presence shows custom status
- [ ] Activity type displays correctly
- [ ] Status changes when needed

### Health Checks
- [ ] All 3 bots respond to health checks
- [ ] Docker healthcheck passes
- [ ] Logs show openclaw 2026.2.3

### Integration
- [ ] Supermemory still works
- [ ] Telegram bots respond to commands
- [ ] All environment variables loaded

## 📚 Documentation Updates

### New Commands

| Command | Description | Example |
|---------|-------------|---------|
| `/models` | Show model selection buttons | `/models` |
| `/model` | Show current model + buttons | `/model` |
| `/health` | Show bot health status | `/health` |

### Updated Commands

| Command | What Changed |
|---------|--------------|
| `/start` | Now shows available models |
| `/help` | Lists new /models command |

## 🔄 Changelog Highlights

Full changelog: https://github.com/openclaw/openclaw/blob/main/CHANGELOG.md

### 2026.2.3 (Feb 3, 2026)

**Features:**
- Telegram: Inline button model selection (#8193)
- Discord: Set-presence action for bot activity
- Web UI: New messages indicator style

**Fixes:**
- Telegram: Honor session model overrides in buttons
- Security: Various security improvements

**Breaking Changes:**
- None - fully backward compatible

## 🎓 Learning Resources

### Tutorials

1. **Setting up Telegram Inline Buttons**
   - Enable Telegram channel
   - Configure bot token
   - Test `/models` command

2. **Discord Presence Configuration**
   - Get Discord bot token
   - Configure presence settings
   - Set custom status/activity

3. **Health Check Monitoring**
   - Set up health check endpoints
   - Configure Docker healthcheck
   - Monitor with external tools

### Videos

- OpenClaw 2026.2.3 Overview (coming soon)
- Telegram Model Selection Demo (coming soon)
- Discord Integration Guide (coming soon)

## 🤝 Community

- Discord: https://discord.gg/openclaw
- GitHub Discussions: https://github.com/openclaw/openclaw/discussions
- Twitter: @openclaw_ai

---

**Last Updated:** February 3, 2026
**Version:** OpenClaw 2026.2.3
**Bots:** ClawdFriday, ClawdMatt, ClawdJarvis
