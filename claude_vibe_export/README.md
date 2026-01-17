# Claude Vibe from Telegram & X

Execute coding commands via Claude CLI from Telegram and X/Twitter.

## Features

- **Telegram Integration**: Send coding commands via Telegram, get results back
- **X/Twitter Integration**: Mention @Jarvis with coding requests, get replies
- **Security**: All output sanitized, admin-only access, rate limiting
- **Claude CLI**: Uses Claude Code CLI for intelligent code execution

## Architecture

```
┌─────────────┐     ┌──────────────────┐     ┌─────────────┐
│  Telegram   │────▶│  Claude CLI      │────▶│   Results   │
│  Message    │     │  Handler         │     │  (cleansed) │
└─────────────┘     └──────────────────┘     └─────────────┘

┌─────────────┐     ┌──────────────────┐     ┌─────────────┐
│  X/Twitter  │────▶│  X CLI Handler   │────▶│   Reply     │
│  Mention    │     │  (mention loop)  │     │  (cleansed) │
└─────────────┘     └──────────────────┘     └─────────────┘
```

## Security Features

1. **Admin Whitelisting**: Only configured admin users can execute commands
2. **Output Sanitization**: 20+ regex patterns redact:
   - API keys (Anthropic, OpenAI, XAI, GitHub)
   - Bot tokens and bearer tokens
   - Private keys and mnemonics
   - Database connection strings
   - Passwords and secrets
3. **Rate Limiting**: Daily command limits prevent abuse
4. **Input Validation**: Coding keywords detected before execution
5. **Timeout Protection**: 5-minute timeout on all executions

## Setup

### Prerequisites

- Python 3.10+
- Claude CLI installed (`claude --version`)
- Telegram Bot Token (from @BotFather)
- X/Twitter API credentials (for mention monitoring)

### Environment Variables

```bash
# Telegram
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_ADMIN_IDS=123456789,987654321

# X/Twitter (optional, for X integration)
X_API_KEY=your_api_key
X_API_SECRET=your_api_secret
X_ACCESS_TOKEN=your_access_token
X_ACCESS_TOKEN_SECRET=your_access_secret

# Working directory
JARVIS_WORKING_DIR=/path/to/your/project
```

### Installation

```bash
pip install -r requirements.txt
```

## Usage

### Telegram

Send messages to your bot:
- `/code add a new endpoint for user profiles`
- `fix the bug in the authentication module`
- `create a function that validates email addresses`

### X/Twitter

Mention @YourBot:
- `@YourBot fix the trending endpoint`
- `@YourBot add rate limiting to the API`

## Files

- `telegram/claude_cli_handler.py` - Telegram Claude CLI integration
- `twitter/x_claude_cli_handler.py` - X/Twitter mention monitoring
- `tests/security_pentest.py` - Security penetration tests

## Security Tests

Run the security test suite:

```bash
python tests/security_pentest.py
```

Tests verify:
- Unauthorized users are blocked
- All secret patterns are redacted
- Output is properly escaped
- Rate limits are enforced

## License

MIT
