# JARVIS Developer Setup Guide

Quick start guide for JARVIS development environment.

## Prerequisites

- Python 3.11+
- Node.js 18+ (for frontend tools)
- Git
- SQLite3
- Redis (optional, for caching)

## Quick Start

### 1. Clone Repository

```bash
git clone https://github.com/your-org/jarvis.git
cd jarvis
```

### 2. Create Virtual Environment

```bash
python -m venv venv

# Windows
.\venv\Scripts\activate

# Linux/macOS
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt

# Development dependencies
pip install -r requirements-dev.txt
```

### 4. Environment Setup

Copy the example environment file and configure:

```bash
cp env.example .env
```

Edit `.env` with your settings:

```env
# Required
TELEGRAM_BOT_TOKEN=your_bot_token
TWITTER_API_KEY=your_twitter_key

# Solana
SOLANA_RPC_URL=https://api.mainnet-beta.solana.com

# LLM Providers (at least one)
GROQ_API_KEY=your_groq_key
XAI_API_KEY=your_xai_key
OPENROUTER_API_KEY=your_openrouter_key

# Optional
REDIS_URL=redis://localhost:6379
```

### 5. Initialize Database

```bash
python scripts/db/migrate.py up
```

### 6. Verify Setup

```bash
python -c "from core import startup_validator; startup_validator.validate()"
```

## Development Workflow

### Running the API

```bash
python -m api.fastapi_app
```

API will be available at `http://localhost:8000`

### Running Bots

```bash
# Telegram bot
python -m tg_bot.bot

# Twitter bot
python -m bots.twitter.run

# Treasury bot
python -m bots.treasury.run_treasury
```

### Running Tests

```bash
# All tests
pytest

# With coverage
pytest --cov=core --cov-report=html

# Specific module
pytest tests/test_api.py -v
```

### Code Quality

Pre-commit hooks are configured. Install them:

```bash
pre-commit install
```

Run manually:

```bash
pre-commit run --all-files
```

## Project Structure

```
jarvis/
├── api/                    # FastAPI application
│   ├── fastapi_app.py     # Main app entry
│   └── middleware/        # HTTP middleware
├── bots/                  # Bot implementations
│   ├── buy_tracker/       # Buy signal tracker
│   ├── treasury/          # Treasury management
│   └── twitter/           # Twitter/X bot
├── core/                  # Core modules
│   ├── api/              # API utilities
│   ├── bot/              # Bot helpers
│   ├── cache/            # Caching
│   ├── config/           # Configuration
│   ├── data/             # Data management
│   ├── db/               # Database
│   ├── lifecycle/        # Lifecycle management
│   ├── llm/              # LLM integration
│   ├── monitoring/       # Health & metrics
│   ├── resilience/       # Retry & circuit breaker
│   ├── security/         # Security utilities
│   ├── tasks/            # Async task queue
│   ├── treasury/         # Treasury logic
│   └── validation/       # Input validation
├── docs/                  # Documentation
├── grafana/              # Monitoring dashboards
├── integrations/         # External integrations
├── scripts/              # Utility scripts
│   └── db/               # Database scripts
├── tests/                # Test suite
├── tg_bot/               # Telegram bot
└── requirements.txt      # Dependencies
```

## Key Modules

### LLM Integration

```python
from core.llm import quick_generate, route_task, TaskType

# Simple generation
response = await quick_generate("Analyze this market data...")

# Task-based routing
analysis = await route_task("What's the sentiment?", TaskType.SENTIMENT)
```

### Caching

```python
from core.cache import cached

@cached(ttl=300)  # Cache for 5 minutes
async def get_token_price(mint: str) -> float:
    return await fetch_price(mint)
```

### Task Queue

```python
from core.tasks import task, get_task_queue

@task(priority=1, retry=3)
async def process_trade(trade_data: dict):
    # Process trade asynchronously
    pass

# Enqueue
await get_task_queue().enqueue(process_trade, trade_data)
```

### Input Validation

```python
from core.validation import validate_params, SolanaAddressValidator

@validate_params(wallet=SolanaAddressValidator())
async def transfer(wallet: str, amount: float):
    # wallet is guaranteed to be valid
    pass
```

### Monitoring

```python
from core.monitoring import get_metrics_collector, track_request

@track_request("api", "/endpoint")
async def my_endpoint():
    # Automatically tracks latency and errors
    pass
```

## Database

### Migrations

```bash
# Apply pending migrations
python scripts/db/migrate.py up

# Rollback last migration
python scripts/db/migrate.py down

# Check status
python scripts/db/migrate.py status

# Create new migration
python scripts/db/migrate.py create add_new_table
```

### Backups

```bash
# Create backup
python scripts/db/backup.py backup

# List backups
python scripts/db/backup.py list

# Restore
python scripts/db/backup.py restore jarvis_db_20260113_120000.db.gz
```

## Debugging

### Enable Debug Logging

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

Or set environment variable:

```bash
LOG_LEVEL=DEBUG python -m api.fastapi_app
```

### API Documentation

When running the API, Swagger docs are at:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`
- OpenAPI JSON: `http://localhost:8000/openapi.json`

## Common Issues

### "Module not found"

Ensure virtual environment is activated and dependencies are installed:

```bash
pip install -r requirements.txt
```

### Database errors

Ensure database is initialized:

```bash
python scripts/db/migrate.py up
```

### API connection refused

Check if the port is already in use:

```bash
# Find process using port 8000
lsof -i :8000  # Linux/macOS
netstat -ano | findstr :8000  # Windows
```

### LLM provider errors

Verify API keys are set in `.env` and have valid credits.

## Contributing

1. Create a feature branch: `git checkout -b feature/my-feature`
2. Make changes and add tests
3. Run tests: `pytest`
4. Run linting: `pre-commit run --all-files`
5. Commit: `git commit -m "feat: add my feature"`
6. Push: `git push origin feature/my-feature`
7. Create pull request

## Need Help?

- Check [Troubleshooting Guide](./TROUBLESHOOTING.md)
- Review [API Documentation](./API.md)
- Open an issue on GitHub
