# Jarvis Makefile - Common Operations
# Usage: make <target>
# Run 'make help' to see all available targets

.PHONY: help install dev test lint format type-check clean build deploy run \
        vps-status vps-logs vps-restart vps-sync \
        test-unit test-integration test-coverage

# Default target
.DEFAULT_GOAL := help

# VPS Configuration
VPS_HOST := root@72.61.7.126
VPS_PATH := /home/jarvis/Jarvis
VPS_USER := jarvis

# Colors (works in bash terminals)
BLUE := \033[0;34m
GREEN := \033[0;32m
YELLOW := \033[1;33m
NC := \033[0m

# ==============================================================================
# HELP
# ==============================================================================

help: ## Show this help message
	@echo "Jarvis Makefile - Available Targets"
	@echo "===================================="
	@echo ""
	@echo "Development:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "Usage: make <target>"

# ==============================================================================
# DEVELOPMENT TARGETS
# ==============================================================================

install: ## Install production dependencies
	pip install -r requirements.txt

dev: ## Install dev dependencies (editable + dev tools)
	pip install -e . 2>/dev/null || pip install -r requirements.txt
	pip install pytest pytest-cov pytest-asyncio pytest-mock black flake8 mypy ruff

test: ## Run all tests
	pytest tests/ -v

test-unit: ## Run unit tests only
	pytest tests/unit/ -v

test-integration: ## Run integration tests only
	pytest tests/integration/ -v

test-coverage: ## Run tests with coverage report
	pytest tests/ -v --cov=core --cov=bots --cov-report=term-missing --cov-report=html

lint: ## Run linter (ruff + flake8)
	ruff check core/ bots/ tg_bot/ || true
	flake8 core/ bots/ tg_bot/ --max-line-length=120 --ignore=E501,W503 || true

format: ## Format code with black
	black core/ bots/ tg_bot/ --line-length=120

format-check: ## Check formatting without changing files
	black core/ bots/ tg_bot/ --line-length=120 --check

type-check: ## Run mypy type checker
	mypy core/ --ignore-missing-imports || true

clean: ## Remove build artifacts and caches
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type f -name "*.pyo" -delete 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "htmlcov" -exec rm -rf {} + 2>/dev/null || true
	rm -rf build/ dist/ 2>/dev/null || true
	@echo "Cleaned build artifacts and caches"

build: ## Build the project
	python setup.py build 2>/dev/null || echo "No setup.py found - skipping build"

# ==============================================================================
# LOCAL RUN TARGETS
# ==============================================================================

run: ## Start supervisor (all bots locally)
	python bots/supervisor.py

run-telegram: ## Start Telegram bot only
	python -m tg_bot.bot

run-twitter: ## Start Twitter/X bot only
	python -m bots.twitter.run_autonomous

run-web: ## Start web trading interface
	cd web && python trading_web.py

run-control: ## Start system control deck
	cd web && python task_web.py

# ==============================================================================
# VPS TARGETS
# ==============================================================================

vps-status: ## Check VPS bot status (systemd services)
	@echo "Checking VPS services..."
	ssh $(VPS_HOST) "systemctl status jarvis-supervisor jarvis-telegram jarvis-twitter --no-pager" || \
	ssh $(VPS_HOST) "ps aux | grep -E 'supervisor|telegram|twitter' | grep -v grep"

vps-logs: ## Tail VPS supervisor logs
	ssh $(VPS_HOST) "journalctl -u jarvis-supervisor -n 100 -f" || \
	ssh $(VPS_HOST) "tail -f $(VPS_PATH)/logs/supervisor.log"

vps-logs-telegram: ## Tail VPS Telegram bot logs
	ssh $(VPS_HOST) "journalctl -u jarvis-telegram -n 100 -f"

vps-logs-twitter: ## Tail VPS Twitter bot logs
	ssh $(VPS_HOST) "journalctl -u jarvis-twitter -n 100 -f"

vps-restart: ## Restart VPS bots
	@echo "Restarting VPS services..."
	ssh $(VPS_HOST) "systemctl restart jarvis-supervisor jarvis-telegram jarvis-twitter" || \
	ssh $(VPS_HOST) "pkill -f supervisor.py; sleep 2; cd $(VPS_PATH) && nohup python bots/supervisor.py > logs/supervisor.log 2>&1 &"
	@echo "Services restarted"

vps-stop: ## Stop VPS bots
	@echo "Stopping VPS services..."
	ssh $(VPS_HOST) "systemctl stop jarvis-supervisor jarvis-telegram jarvis-twitter" || \
	ssh $(VPS_HOST) "pkill -f supervisor.py; pkill -f tg_bot; pkill -f twitter"
	@echo "Services stopped"

vps-sync: ## Rsync local code to VPS
	@echo "Syncing to VPS..."
	rsync -avz --progress \
		--exclude '.git' \
		--exclude '__pycache__' \
		--exclude '*.pyc' \
		--exclude 'venv' \
		--exclude 'node_modules' \
		--exclude '.env' \
		--exclude 'secrets/' \
		--exclude 'logs/' \
		--exclude '.pytest_cache' \
		--exclude '.mypy_cache' \
		--exclude 'htmlcov' \
		./ $(VPS_HOST):$(VPS_PATH)/
	@echo "Sync complete"

vps-sync-dry: ## Rsync dry-run (show what would be synced)
	rsync -avzn --progress \
		--exclude '.git' \
		--exclude '__pycache__' \
		--exclude '*.pyc' \
		--exclude 'venv' \
		--exclude 'node_modules' \
		--exclude '.env' \
		--exclude 'secrets/' \
		--exclude 'logs/' \
		./ $(VPS_HOST):$(VPS_PATH)/

vps-ssh: ## SSH into VPS
	ssh $(VPS_HOST)

vps-deploy: vps-sync vps-restart ## Full deploy: sync + restart

# ==============================================================================
# DEPLOY TARGETS
# ==============================================================================

deploy: vps-deploy ## Alias for vps-deploy

deploy-bots: ## Run the full bot deployment script
	bash scripts/deploy_all_bots.sh

# ==============================================================================
# UTILITY TARGETS
# ==============================================================================

check: lint type-check test ## Run all checks (lint, type-check, test)

ci: clean install check ## CI pipeline: clean, install, check

env-check: ## Verify environment variables are set
	@echo "Checking environment variables..."
	@test -f .env && echo ".env file exists" || echo "WARNING: No .env file found"
	@test -f lifeos/config/.env && echo "lifeos/config/.env exists" || echo "WARNING: No lifeos/config/.env"
	@test -f secrets/keys.json && echo "secrets/keys.json exists" || echo "WARNING: No secrets/keys.json"

logs: ## Show local logs
	@test -d logs && tail -f logs/*.log || echo "No logs directory found"

health: ## Quick health check
	@echo "=== Local Health Check ==="
	@python -c "import core; print('core module: OK')" 2>/dev/null || echo "core module: FAILED"
	@python -c "import bots; print('bots module: OK')" 2>/dev/null || echo "bots module: FAILED"
	@python -c "import tg_bot; print('tg_bot module: OK')" 2>/dev/null || echo "tg_bot module: FAILED"
	@echo ""
	@echo "=== Python Version ==="
	@python --version
	@echo ""
	@echo "=== Key Dependencies ==="
	@pip show anthropic 2>/dev/null | grep Version || echo "anthropic: NOT INSTALLED"
	@pip show python-telegram-bot 2>/dev/null | grep Version || echo "python-telegram-bot: NOT INSTALLED"
	@pip show tweepy 2>/dev/null | grep Version || echo "tweepy: NOT INSTALLED"
