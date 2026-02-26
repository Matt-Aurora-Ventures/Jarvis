# Conventions

## Style Guides
- **Python**: Enforced via `Black` (line length 88) and `Ruff`.
- **Typing**: Strict type hints enforced via `Mypy` (`strict_equality`, `check_untyped_defs`).
- **Complexity**: Ruff McCabe complexity set to 10 max.

## Common Patterns
- **Async Execution**: Heavy use of `pytest-asyncio` and `async`/`await` for I/O operations (blockchain RPCs, Telegram, Twitter).
- **Environment variables**: Use of `.env` files (e.g. `tokens.env.example`) to avoid hardcoded secrets. `Bandit` is set up to find hardcoded passwords (`S105`-`S107` overrides).

## Git Commit Practices
- Extensive Changelog updates (evidenced by `add_changelog.py`, `update_changelog.py`, `insert_changelog_entry.py`).
- Pre-commit hooks (`.pre-commit-config.yaml`).

## Logging & Feedback
- Extremely verbose Telegram alerts ("Alert", "Intel", "Backtest result").
