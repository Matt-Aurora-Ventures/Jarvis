# Demo Refactor Extraction Audit

Date: 2026-01-26
Scope: Compare `tg_bot/handlers/demo_legacy.py` to `tg_bot/handlers/demo/*.py` modules.

## Summary
- Legacy top-level functions: 47
- Modular top-level functions: 48
- Duplicates (legacy + modules): 47
- Legacy-only functions: 0
- New-only module functions: 1

## Legacy-only functions (not yet extracted)
- None

## New-only module functions (not in legacy)
- get_callback_router

## Duplicates by module
- demo_callbacks.py: 0
- demo_core.py: 4
  - demo
  - demo_callback
  - demo_message_handler
  - register_demo_handlers
- demo_orders.py: 9
  - _auto_exit_enabled
  - _background_tp_sl_monitor
  - _check_demo_exit_triggers
  - _exit_checks_enabled
  - _format_exit_alert_message
  - _get_exit_check_interval_seconds
  - _maybe_execute_exit
  - _process_demo_exit_checks
  - _should_run_exit_checks
- demo_sentiment.py: 15
  - _conviction_label
  - _default_tp_sl
  - _get_pick_stats
  - _grade_for_signal_name
  - _load_treasury_top_picks
  - _pick_key
  - _update_sentiment_cache
  - get_ai_sentiment_for_token
  - get_bags_top_tokens_with_sentiment
  - get_cached_macro_sentiment
  - get_cached_sentiment_tokens
  - get_conviction_picks
  - get_market_regime
  - get_sentiment_cache_age
  - get_trending_with_sentiment
- demo_trading.py: 17
  - _execute_swap_with_fallback
  - _from_base_units
  - _get_demo_engine
  - _get_demo_slippage_bps
  - _get_demo_wallet_dir
  - _get_demo_wallet_password
  - _get_jupiter_client
  - _get_token_decimals
  - _load_demo_wallet
  - _register_token_id
  - _resolve_token_ref
  - _to_base_units
  - execute_buy_with_tpsl
  - get_bags_client
  - get_success_fee_manager
  - get_trade_intelligence
  - validate_buy_amount
- demo_ui.py: 2
  - generate_price_chart
  - safe_symbol

## Implications
- Handler entrypoints now live in `demo_core.py`.
- Modular files cover all legacy helper functions; `demo_legacy.py` is now redundant for core behavior.
- `tg_bot/bot.py` now registers demo handlers via `register_demo_handlers`.
- DemoContextLoader pulls sentiment/trading/UI helpers from modular files.
- Callback modules use modular imports for wallet and chart helpers.
- Token ref helpers live in `demo_trading.py`; demo_callbacks has no direct legacy imports.
- DemoMenuBuilder/JarvisTheme still sourced from `demo_legacy.py` via `demo_ui.py`.
- Unit tests now patch `demo_core` instead of `demo_legacy`.
- Swap execution now retries Bags/Jupiter calls with exponential backoff.
- Next step is to delete or archive `demo_legacy.py` and remove duplicate helpers once verified.
