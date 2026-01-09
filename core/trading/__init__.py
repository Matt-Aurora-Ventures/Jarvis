"""
Trading subpackage for Jarvis.

This package consolidates all trading-related modules for better organization.
All modules are re-exported here for backwards compatibility.

Modules:
- DEX integrations: jupiter, raydium, jito
- Trading strategies and pipeline
- Market data: birdeye, dexscreener, geckoterminal
- Wallet and execution infrastructure
- Sentiment and signal aggregation
"""

# DEX Integrations
from core.jupiter import (
    fetch_quote,
    fetch_swap_transaction,
    fetch_token_list,
    get_quote,
    execute_swap,
)

from core.jupiter_orders import (
    create_limit_order,
    create_stop_loss_order,
    create_take_profit_order,
    cancel_order,
    get_open_orders,
)

from core.jupiter_perps import (
    open_position,
    close_position,
    get_position,
    get_funding_rate,
)

from core.raydium import (
    get_pool_info,
    get_amm_pools,
    fetch_raydium_price,
)

from core.jito_executor import (
    JitoExecutor,
    create_jito_bundle,
    submit_bundle,
)

# Trading Strategies
from core.trading_strategies import (
    Strategy,
    get_strategy,
    list_strategies,
)

from core.trading_strategies_advanced import (
    TriangularArbitrage,
    GridTrading,
    BreakoutStrategy,
    MarketMaking,
)

from core.trading_pipeline import (
    TradingPipeline,
    run_backtest,
    run_walk_forward,
)

from core.trading_coliseum import (
    TradingColiseum,
    run_coliseum,
    get_coliseum_results,
)

# Market Data
from core.birdeye import (
    fetch_token_price,
    fetch_token_metadata,
    get_trending_tokens,
    BirdEyeResult,
)

from core.dexscreener import (
    fetch_pair_data,
    get_solana_trending,
    search_pairs,
)

from core.geckoterminal import (
    fetch_pools_safe,
    get_ohlcv,
)

# Signal Aggregation
from core.signal_aggregator import (
    aggregate_signals,
    get_combined_score,
)

from core.gmgn_metrics import (
    fetch_smart_money_metrics,
    get_insider_activity,
)

from core.lute_momentum import (
    get_momentum_calls,
    track_momentum_signal,
)

# Sentiment
from core.x_sentiment import (
    analyze_sentiment,
    get_token_sentiment,
)

from core.xai_twitter import (
    fetch_grok_sentiment,
    get_social_metrics,
)

# Wallet Infrastructure
from core.wallet_infrastructure import (
    TransactionBuilder,
    TokenSafetyAnalyzer,
    AddressLookupTableManager,
    PriorityFeeConfig,
    TransactionPriority,
    is_valid_solana_address,
)

from core.solana_wallet import (
    load_keypair,
    get_wallet_balance,
)

from core.solana_execution import (
    execute_transaction,
    load_solana_rpc_endpoints,
    SolanaRPCEndpoint,
)

from core.solana_scanner import (
    scan_new_tokens,
    analyze_token,
)

from core.solana_tokens import (
    get_token_decimals,
    get_token_metadata,
)

# Exit Management
from core.exit_intents import (
    ExitIntent,
    load_exit_intents,
    save_exit_intent,
    check_exit_conditions,
)

# Risk Management
from core.risk_manager import (
    calculate_position_size,
    check_risk_limits,
)

from core.approval_gate import (
    request_approval,
    get_pending_approvals,
    approve_trade,
    reject_trade,
)

# Data Ingestion
from core.data_ingestion import (
    WebSocketDataFeed,
    normalize_orderbook,
)

# ML Regime Detection
from core.ml_regime_detector import (
    detect_market_regime,
    get_volatility_forecast,
)

# Micro-cap Trading
from core.micro_cap_sniper import (
    MicroCapSniper,
    get_sniper,
)

from core.lut_micro_alpha import (
    LUTMicroAlpha,
    run_lut_alpha,
)

# Trading Daemons
from core.trading_daemon import (
    start_trading_daemon,
    stop_trading_daemon,
)

from core.lut_daemon import (
    start_lut_daemon,
    stop_lut_daemon,
)

__all__ = [
    # Jupiter
    "fetch_quote",
    "fetch_swap_transaction",
    "fetch_token_list",
    "get_quote",
    "execute_swap",
    # Jupiter Orders
    "create_limit_order",
    "create_stop_loss_order",
    "create_take_profit_order",
    "cancel_order",
    "get_open_orders",
    # Jupiter Perps
    "open_position",
    "close_position",
    "get_position",
    "get_funding_rate",
    # Raydium
    "get_pool_info",
    "get_amm_pools",
    "fetch_raydium_price",
    # Jito
    "JitoExecutor",
    "create_jito_bundle",
    "submit_bundle",
    # Strategies
    "Strategy",
    "get_strategy",
    "list_strategies",
    "TriangularArbitrage",
    "GridTrading",
    "BreakoutStrategy",
    "MarketMaking",
    # Pipeline
    "TradingPipeline",
    "run_backtest",
    "run_walk_forward",
    # Coliseum
    "TradingColiseum",
    "run_coliseum",
    "get_coliseum_results",
    # BirdEye
    "fetch_token_price",
    "fetch_token_metadata",
    "get_trending_tokens",
    "BirdEyeResult",
    # DexScreener
    "fetch_pair_data",
    "get_solana_trending",
    "search_pairs",
    # GeckoTerminal
    "fetch_pools_safe",
    "get_ohlcv",
    # Signals
    "aggregate_signals",
    "get_combined_score",
    "fetch_smart_money_metrics",
    "get_insider_activity",
    "get_momentum_calls",
    "track_momentum_signal",
    # Sentiment
    "analyze_sentiment",
    "get_token_sentiment",
    "fetch_grok_sentiment",
    "get_social_metrics",
    # Wallet
    "TransactionBuilder",
    "TokenSafetyAnalyzer",
    "AddressLookupTableManager",
    "PriorityFeeConfig",
    "TransactionPriority",
    "is_valid_solana_address",
    "load_keypair",
    "get_wallet_balance",
    # Execution
    "execute_transaction",
    "load_solana_rpc_endpoints",
    "SolanaRPCEndpoint",
    # Scanner
    "scan_new_tokens",
    "analyze_token",
    # Tokens
    "get_token_decimals",
    "get_token_metadata",
    # Exit
    "ExitIntent",
    "load_exit_intents",
    "save_exit_intent",
    "check_exit_conditions",
    # Risk
    "calculate_position_size",
    "check_risk_limits",
    # Approval
    "request_approval",
    "get_pending_approvals",
    "approve_trade",
    "reject_trade",
    # Data
    "WebSocketDataFeed",
    "normalize_orderbook",
    # ML
    "detect_market_regime",
    "get_volatility_forecast",
    # Sniper
    "MicroCapSniper",
    "get_sniper",
    "LUTMicroAlpha",
    "run_lut_alpha",
    # Daemons
    "start_trading_daemon",
    "stop_trading_daemon",
    "start_lut_daemon",
    "stop_lut_daemon",
]
