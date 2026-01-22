---
date: 2026-01-22T15:00:00Z
type: repo-research
status: complete
repository: Jarvis
---

# Repository Research: Jarvis

## Overview
Jarvis is an autonomous LifeOS trading and AI assistant system running on Solana, featuring multi-platform bot integration (Telegram, X/Twitter), treasury management, sentiment analysis, and automated trading capabilities.

## Architecture & Structure

### Project Organization

| Directory | Purpose |
|-----------|---------|
| `core/` | Main Python modules (200+ files) - trading, bots, execution, risk management, AI, security |
| `bots/` | Bot implementations - supervisor, treasury, twitter, discord, buy_tracker, bags_intel |
| `tg_bot/` | Telegram bot handlers and services |
| `api/` | FastAPI server, routes, middleware, websocket handlers |
| `lifeos/` | Configuration, context, events, memory, services |
| `scripts/` | Automation and utility scripts |
| `tests/` | Comprehensive test suite (unit, integration, security, load) |
| `data/` | Runtime data, logs, caches, ML models |
| `docs/` | Documentation (architecture, security, tutorials) |
| `integrations/` | External service integrations (bags.fm, coinglass) |

### Key Architectural Components

1. **Bot Supervisor** (`bots/supervisor.py`)
   - Process management with auto-restart and exponential backoff
   - Component isolation (one crash doesn't kill others)
   - Systemd integration for production deployments
   - Components: buy_bot, sentiment_reporter, twitter_poster, telegram_bot, autonomous_x, bags_intel

2. **Treasury Trading Engine** (`bots/treasury/trading.py`)
   - Jupiter DEX integration for Solana token swaps
   - Decision matrix for multi-signal confirmation
   - Cooldown system tracking closures
   - Emergency stop mechanism
   - Risk management integration

3. **Context Loader** (`core/context_loader.py`)
   - Shared capabilities across all interfaces
   - System prompt generation
   - State management

4. **Self-Correcting AI** (`core/self_correcting/`)
   - Shared memory, message bus, Ollama router, self-adjuster
   - Optional integration with supervisor

### Main Entry Points
- `bots/supervisor.py` - Main orchestrator
- `api/server.py` - API server
- `tg_bot/bot.py` - Telegram bot
- `jarvis_cli/main.py` - CLI entry point

### Technology Stack
- **Language:** Python 3.10+
- **Framework:** FastAPI (API), python-telegram-bot (Telegram)
- **Build Tool:** setuptools, pip
- **Testing:** pytest, pytest-asyncio, pytest-cov
- **Linting:** ruff, black, mypy, bandit
- **Blockchain:** Solana (solana-py, solders), Jupiter DEX

### Key Dependencies
| Category | Libraries |
|----------|-----------|
| AI/ML | anthropic, openai, groq, google-generativeai, instructor |
| Trading | solana, solders, jupiter API, birdeye, dexscreener |
| Bots | python-telegram-bot, tweepy (X/Twitter) |
| Web | fastapi, aiohttp, websockets |
| Data | lancedb, pyarrow, orjson, msgspec |
| Voice | edge-tts, pyttsx3, SpeechRecognition, openwakeword |
| Observability | opentelemetry-api, opentelemetry-sdk |

### Key Files
| File | Purpose |
|------|---------|
| `bots/supervisor.py` | Main supervisor orchestrating all components |
| `bots/treasury/trading.py` | Treasury trading engine (Jupiter DEX) |
| `bots/twitter/autonomous_engine.py` | Autonomous X posting (192KB - largest file) |
| `bots/twitter/x_claude_cli_handler.py` | X/Twitter CLI command handler |
| `tg_bot/services/chat_responder.py` | Telegram chat handler |
| `core/context_loader.py` | Shared Jarvis context/capabilities |
| `core/jarvis.py` | Core Jarvis logic |
| `core/position_manager.py` | Trading position management |

## Conventions & Patterns

### Code Style
- **Line length:** 88 characters (black)
- **Import sorting:** isort with black profile
- **Docstrings:** Google convention (pydocstyle)
- **Type hints:** Used throughout, mypy for checking

### File Organization Patterns
```
module/
├── __init__.py          # Package exports
├── config.py            # Module configuration
├── models.py            # Data models/dataclasses
├── client.py            # External service client
├── service.py           # Business logic
└── utils.py             # Helper functions
```

### Implementation Patterns

1. **Feature Detection with Graceful Fallback**
   ```python
   try:
       from core.feature import SomeClass
       FEATURE_AVAILABLE = True
   except ImportError:
       FEATURE_AVAILABLE = False
       SomeClass = None
   ```

2. **Dataclass for State/Config**
   ```python
   @dataclass
   class ComponentState:
       name: str
       status: ComponentStatus = ComponentStatus.STOPPED
       task: Optional[asyncio.Task] = None
   ```

3. **Enum for Status/Types**
   ```python
   class ComponentStatus(Enum):
       STOPPED = "stopped"
       RUNNING = "running"
       FAILED = "failed"
   ```

4. **Centralized Error Tracking**
   ```python
   from core.logging.error_tracker import error_tracker
   error_tracker.track_error(exc, context="...", component="...")
   ```

5. **Async-First Design**
   - Most bot/trading operations are async
   - `fire_and_forget` for non-blocking tasks
   - `TaskTracker` for safe task management

### Environment Variables Pattern
- All sensitive config via environment variables
- `.env` file for local development (never committed)
- `env.example` as template
- Key categories: Solana, AI APIs, Telegram, X/Twitter, Database

## Contribution Guidelines

### Issue Format
- No issue templates found in `.github/ISSUE_TEMPLATE/`

### PR Requirements
From `.github/pull_request_template.md`:
- Evidence-backed changes for research-driven updates
- Citations for non-trivial claims
- Evaluation plan (datasets, baselines, metrics)
- Tests added/updated
- Rollback plan included
- Feature flag/config gating for risky changes

### Coding Standards
- Pre-commit hooks enabled (black, isort, flake8, mypy, bandit, detect-secrets)
- No commit to main/master directly
- Commit message linting via commitizen

### Testing Requirements
- pytest with asyncio support
- Test markers: `slow`, `integration`, `security`, `unit`
- Coverage target: 60% minimum
- Fixtures in `tests/conftest.py`
- Factory fixtures for data generation

## Templates Found

| Template | Location | Purpose |
|----------|----------|---------|
| PR Template | `.github/pull_request_template.md` | Evidence-backed changes checklist |

## Key Insights

### What Makes This Project Unique

1. **Multi-Platform Bot Orchestration**
   - Single supervisor manages Telegram, X/Twitter, trading bots
   - Component isolation with auto-restart

2. **Autonomous Trading System**
   - Sentiment analysis → Signal generation → Trade execution
   - Decision matrix with multi-signal confirmation
   - Risk management with circuit breakers

3. **Self-Correcting AI Integration**
   - Optional Ollama router for local AI
   - Shared memory and message bus architecture

4. **Comprehensive Feature Flags**
   - Environment-based kill switches (`LIFEOS_KILL_SWITCH`, `X_BOT_ENABLED`)
   - Gradual feature rollout support

### Gotchas / Important Notes

1. **State Files Location**
   - Position state: `bots/treasury/.positions.json`
   - Exit intents: `~/.lifeos/trading/exit_intents.json`
   - Grok state: `bots/twitter/.grok_state.json`

2. **Configuration Limits**
   - Max positions: 50
   - Grok daily cost limit: $10
   - X Bot circuit breaker: 60s min interval, 30min cooldown after 3 errors

3. **Windows Encoding Fix**
   ```python
   if sys.platform == "win32":
       for stream in [sys.stdout, sys.stderr]:
           if hasattr(stream, 'reconfigure'):
               stream.reconfigure(encoding='utf-8', errors='replace')
   ```

4. **Import Paths**
   - Project root added to `sys.path` in most entry points
   - `core`, `api`, `bots`, `integrations`, `tg_bot` are first-party packages

## Recommendations

### Before Contributing
1. Copy `env.example` to `.env` and configure required values
2. Install pre-commit hooks: `pip install pre-commit && pre-commit install`
3. Run tests: `pytest tests/`
4. Check coverage: `pytest --cov=core --cov=api --cov=bots`

### Patterns to Follow
- Use `@dataclass` for state/config objects (`bots/supervisor.py:61`)
- Use feature detection pattern for optional imports (`bots/treasury/trading.py:29-81`)
- Track errors via centralized error_tracker
- Use async/await for I/O operations
- Add type hints for all public functions

### Key Workflows
1. **Start System**: `python bots/supervisor.py`
2. **Run Tests**: `pytest tests/ -v`
3. **Lint Code**: `ruff check . && black --check .`
4. **Type Check**: `mypy core/ api/ bots/`

## Sources
- `CLAUDE.md` - Project instructions
- `pyproject.toml` - Build configuration and tool settings
- `.pre-commit-config.yaml` - Pre-commit hooks
- `.github/pull_request_template.md` - PR requirements
- `env.example` - Environment variable template
- `tests/conftest.py` - Test fixtures
- `bots/supervisor.py` - Supervisor architecture
- `bots/treasury/trading.py` - Trading engine patterns
- `core/context_loader.py` - Context management
