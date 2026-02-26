# Testing

## Frameworks
- `Pytest` is the dominant test runner.
- `pytest-asyncio` is utilized for testing async solana/bot calls.
- `pytest-cov` generates test coverage reports.

## Configuration
- Minimum coverage required is set to 60%.
- Marked test suites: `slow`, `integration`, `security`, `unit`.
- Excludes: `.venv`, `migrations`, `tests` folders from coverage computation.

## Existing Test files
- Massive `tests/` directory (791 files/subdirs).
- Many root-level manual tests (`test_backtest.py` equivalents, `test_enhanced_search.py`, `test_memory_behavior.py`, `test_personaplex.py`).
- JS/TS tests visible via Node.js setup `test_supermemory.mjs`.

## Notable Practices
- The user highlighted severe issues with current backtesting implementation, specifically lacking PyTorch logic required for hyperparameter tuning.
