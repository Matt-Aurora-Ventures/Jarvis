# Tech Stack

## Core Technologies
- **Language**: Python 3.10+ (specifically requires 3.11+ per README)
- **Runtime**: Node.js 18+ for frontend components
- **Database**: PostgreSQL (for semantic memory)

## Cloud & Infrastructure
- Docker & Docker Compose (has `docker-compose.yml`, `docker-compose.bots.yml`, `docker-compose.web.yml`)
- K8s / Helm (directories exist for both)
- Terraform (directory exists)
- GitHub Actions (CI/CD pipeline)
- VPS Deployment scripts (via bash `vps-ultimate-deployment.sh` etc)

## Backend Dependencies
- **Trading & Blockchain**: `solana`, `solders`, Solana CLI
- **APIs**: `httpx`, `tweepy`
- **AI/LLM**: Local Ollama setup, Grok AI integration (via API)

## Development & Tooling
- **Linting & Formatting**: Ruff, Black, pre-commit
- **Type Checking**: Mypy
- **Testing**: Pytest, pytest-asyncio, pytest-cov, locust
- **Security Analysis**: Bandit

## Key Architectural Highlights
- The architecture is heavily decoupled through specific task bots (traders, reporters, sentiment analysis) using Python scripts ran by the operating system, orchestrator or Docker.
