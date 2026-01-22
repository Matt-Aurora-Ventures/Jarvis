# Start Here: Jarvis Quickstart

## One Command Startup

```bash
jarvis up --profile voice
```

### Profiles

| Profile | Description | Requirements |
| --- | --- | --- |
| `voice` | Local speaking/chat assistant with graceful fallbacks. | None |
| `telegram` | Telegram bot. | `TELEGRAM_BOT_TOKEN` |
| `twitter` | Autonomous X/Twitter bot. | `X_API_KEY`, `X_API_SECRET`, `X_ACCESS_TOKEN`, `X_ACCESS_TOKEN_SECRET` |
| `all` | Start everything available. | Optional |

## Doctor + Validation

```bash
jarvis doctor
jarvis validate
```

`jarvis doctor` applies safe fixes (create folders, ensure .env exists, repair venv) and writes
`logs/startup_report.json`. `jarvis validate` runs the startup validator without changing files.

## Dependencies

```bash
jarvis deps
```

This creates/repairs a `./venv` and installs `requirements.txt`.

## Voice Fallbacks

Jarvis voice mode always starts:

- If speech-to-text is unavailable, it falls back to typed input.
- If text-to-speech is unavailable, it prints responses.

Use `--no-stt` or `--no-tts` to force a fallback mode.
