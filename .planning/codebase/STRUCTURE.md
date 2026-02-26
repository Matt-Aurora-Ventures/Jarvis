# Codebase Structure

## Root Directories
- `api/` - Backend API endpoints
- `artifacts/` - Design/output files
- `bots/` - The autonomous agents (buy_tracker, bags_intel, treasury, twitter, etc.)
- `contracts/` - Solana smart contracts
- `core/` - Shared logic across all bots and subsystems
- `deploy/`, `docker/`, `terraform/`, `k8s/` - Deployment, containerization, and configuration
- `frontend/` / `web/` / `webapp/` / `web_demo/` - NodeJS frontend codebases
- `integrations/` - Code to handle 3rd party APIs (CoinGecko, X, Telegram)
- `lifeos/` - An application/module integration called LifeOS
- `scripts/` - Maintenance and utility bash/python scripts
- `skills/` - Custom MCP tools and skills
- `tests/` - Comprehensive test suites
- `tg_bot/` - Main Telegram Bot integration
- `workflow_engine/` - Logic for multi-step agent behaviors

## Key Files
- `pyproject.toml` - Main configuration for python dependencies and linters
- `docker-compose.yml` - Container orchestration
- `vps-ultimate-deployment.sh` - Main deployment script for production
- `README.md` - Canonical truth for architecture and goals
