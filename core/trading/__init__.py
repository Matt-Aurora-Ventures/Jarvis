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
- Signal analyzers (liquidation, dual MA, meta-labeling)
- Decision matrix for multi-signal confirmation
- Cooldown system for trade management
- Backtesting and robustness testing framework
"""

# Track what's available
_AVAILABLE_MODULES = {}

# DEX Integrations
try:
    from core.jupiter import get_quote, fetch_token_list
    # Optional functions - may not exist in all versions
    try:
        from core.jupiter import fetch_quote
    except ImportError:
        fetch_quote = get_quote  # Fallback
    try:
        from core.jupiter import fetch_swap_transaction
    except ImportError:
        fetch_swap_transaction = None
    try:
        from core.jupiter import execute_swap
    except ImportError:
        execute_swap = None
    _AVAILABLE_MODULES['jupiter'] = True
except ImportError:
    _AVAILABLE_MODULES['jupiter'] = False
    fetch_quote = None
    fetch_swap_transaction = None
    fetch_token_list = None
    get_quote = None
    execute_swap = None

try:
    from core.jupiter_orders import (
        create_limit_order,
        create_stop_loss_order,
        create_take_profit_order,
        cancel_order,
        get_open_orders,
    )
    _AVAILABLE_MODULES['jupiter_orders'] = True
except ImportError:
    _AVAILABLE_MODULES['jupiter_orders'] = False
    create_limit_order = None
    create_stop_loss_order = None
    create_take_profit_order = None
    cancel_order = None
    get_open_orders = None

try:
    from core.jupiter_perps import (
        open_position,
        close_position,
        get_position,
        get_funding_rate,
    )
    _AVAILABLE_MODULES['jupiter_perps'] = True
except ImportError:
    _AVAILABLE_MODULES['jupiter_perps'] = False
    open_position = None
    close_position = None
    get_position = None
    get_funding_rate = None

try:
    from core.raydium import (
        get_pool_info,
        get_amm_pools,
        fetch_raydium_price,
    )
    _AVAILABLE_MODULES['raydium'] = True
except ImportError:
    _AVAILABLE_MODULES['raydium'] = False
    get_pool_info = None
    get_amm_pools = None
    fetch_raydium_price = None

try:
    from core.jito_executor import (
        JitoExecutor,
        create_jito_bundle,
        submit_bundle,
    )
    _AVAILABLE_MODULES['jito'] = True
except ImportError:
    _AVAILABLE_MODULES['jito'] = False
    JitoExecutor = None
    create_jito_bundle = None
    submit_bundle = None

# Trading Strategies
try:
    from core.trading_strategies import (
        Strategy,
        get_strategy,
        list_strategies,
    )
    _AVAILABLE_MODULES['trading_strategies'] = True
except ImportError:
    _AVAILABLE_MODULES['trading_strategies'] = False
    Strategy = None
    get_strategy = None
    list_strategies = None

try:
    from core.trading_strategies_advanced import (
        TriangularArbitrage,
        GridTrading,
        BreakoutStrategy,
        MarketMaking,
    )
    _AVAILABLE_MODULES['trading_strategies_advanced'] = True
except ImportError:
    _AVAILABLE_MODULES['trading_strategies_advanced'] = False
    TriangularArbitrage = None
    GridTrading = None
    BreakoutStrategy = None
    MarketMaking = None

try:
    from core.trading_pipeline import (
        TradingPipeline,
        run_backtest,
        run_walk_forward,
    )
    _AVAILABLE_MODULES['trading_pipeline'] = True
except ImportError:
    _AVAILABLE_MODULES['trading_pipeline'] = False
    TradingPipeline = None
    run_backtest = None
    run_walk_forward = None

try:
    from core.trading_coliseum import (
        TradingColiseum,
        run_coliseum,
        get_coliseum_results,
    )
    _AVAILABLE_MODULES['trading_coliseum'] = True
except ImportError:
    _AVAILABLE_MODULES['trading_coliseum'] = False
    TradingColiseum = None
    run_coliseum = None
    get_coliseum_results = None

# Market Data
try:
    from core.birdeye import (
        fetch_token_price,
        fetch_token_metadata,
        get_trending_tokens,
        BirdEyeResult,
    )
    _AVAILABLE_MODULES['birdeye'] = True
except ImportError:
    _AVAILABLE_MODULES['birdeye'] = False
    fetch_token_price = None
    fetch_token_metadata = None
    get_trending_tokens = None
    BirdEyeResult = None

try:
    from core.dexscreener import (
        fetch_pair_data,
        get_solana_trending,
        search_pairs,
    )
    _AVAILABLE_MODULES['dexscreener'] = True
except ImportError:
    _AVAILABLE_MODULES['dexscreener'] = False
    fetch_pair_data = None
    get_solana_trending = None
    search_pairs = None

try:
    from core.geckoterminal import (
        fetch_pools_safe,
        get_ohlcv,
    )
    _AVAILABLE_MODULES['geckoterminal'] = True
except ImportError:
    _AVAILABLE_MODULES['geckoterminal'] = False
    fetch_pools_safe = None
    get_ohlcv = None

# Signal Aggregation
try:
    from core.signal_aggregator import (
        aggregate_signals,
        get_combined_score,
    )
    _AVAILABLE_MODULES['signal_aggregator'] = True
except ImportError:
    _AVAILABLE_MODULES['signal_aggregator'] = False
    aggregate_signals = None
    get_combined_score = None

try:
    from core.gmgn_metrics import (
        fetch_smart_money_metrics,
        get_insider_activity,
    )
    _AVAILABLE_MODULES['gmgn_metrics'] = True
except ImportError:
    _AVAILABLE_MODULES['gmgn_metrics'] = False
    fetch_smart_money_metrics = None
    get_insider_activity = None

try:
    from core.lute_momentum import (
        get_momentum_calls,
        track_momentum_signal,
    )
    _AVAILABLE_MODULES['lute_momentum'] = True
except ImportError:
    _AVAILABLE_MODULES['lute_momentum'] = False
    get_momentum_calls = None
    track_momentum_signal = None

# Sentiment
try:
    from core.x_sentiment import (
        analyze_sentiment,
        get_token_sentiment,
    )
    _AVAILABLE_MODULES['x_sentiment'] = True
except ImportError:
    _AVAILABLE_MODULES['x_sentiment'] = False
    analyze_sentiment = None
    get_token_sentiment = None

try:
    from core.xai_twitter import (
        fetch_grok_sentiment,
        get_social_metrics,
    )
    _AVAILABLE_MODULES['xai_twitter'] = True
except ImportError:
    _AVAILABLE_MODULES['xai_twitter'] = False
    fetch_grok_sentiment = None
    get_social_metrics = None

# Wallet Infrastructure
try:
    from core.wallet_infrastructure import (
        TransactionBuilder,
        TokenSafetyAnalyzer,
        AddressLookupTableManager,
        PriorityFeeConfig,
        TransactionPriority,
        is_valid_solana_address,
    )
    _AVAILABLE_MODULES['wallet_infrastructure'] = True
except ImportError:
    _AVAILABLE_MODULES['wallet_infrastructure'] = False
    TransactionBuilder = None
    TokenSafetyAnalyzer = None
    AddressLookupTableManager = None
    PriorityFeeConfig = None
    TransactionPriority = None
    is_valid_solana_address = None

try:
    from core.solana_wallet import (
        load_keypair,
        get_wallet_balance,
    )
    _AVAILABLE_MODULES['solana_wallet'] = True
except ImportError:
    _AVAILABLE_MODULES['solana_wallet'] = False
    load_keypair = None
    get_wallet_balance = None

try:
    from core.solana_execution import (
        execute_transaction,
        load_solana_rpc_endpoints,
        SolanaRPCEndpoint,
    )
    _AVAILABLE_MODULES['solana_execution'] = True
except ImportError:
    _AVAILABLE_MODULES['solana_execution'] = False
    execute_transaction = None
    load_solana_rpc_endpoints = None
    SolanaRPCEndpoint = None

try:
    from core.solana_scanner import (
        scan_new_tokens,
        analyze_token,
    )
    _AVAILABLE_MODULES['solana_scanner'] = True
except ImportError:
    _AVAILABLE_MODULES['solana_scanner'] = False
    scan_new_tokens = None
    analyze_token = None

try:
    from core.solana_tokens import (
        get_token_decimals,
        get_token_metadata,
    )
    _AVAILABLE_MODULES['solana_tokens'] = True
except ImportError:
    _AVAILABLE_MODULES['solana_tokens'] = False
    get_token_decimals = None
    get_token_metadata = None

# Exit Management
try:
    from core.exit_intents import (
        ExitIntent,
        load_exit_intents,
        save_exit_intent,
        check_exit_conditions,
    )
    _AVAILABLE_MODULES['exit_intents'] = True
except ImportError:
    _AVAILABLE_MODULES['exit_intents'] = False
    ExitIntent = None
    load_exit_intents = None
    save_exit_intent = None
    check_exit_conditions = None

# Risk Management
try:
    from core.risk_manager import (
        calculate_position_size,
        check_risk_limits,
    )
    _AVAILABLE_MODULES['risk_manager'] = True
except ImportError:
    _AVAILABLE_MODULES['risk_manager'] = False
    calculate_position_size = None
    check_risk_limits = None

try:
    from core.approval_gate import (
        request_approval,
        get_pending_approvals,
        approve_trade,
        reject_trade,
    )
    _AVAILABLE_MODULES['approval_gate'] = True
except ImportError:
    _AVAILABLE_MODULES['approval_gate'] = False
    request_approval = None
    get_pending_approvals = None
    approve_trade = None
    reject_trade = None

# Data Ingestion
try:
    from core.data_ingestion import (
        WebSocketDataFeed,
        normalize_orderbook,
    )
    _AVAILABLE_MODULES['data_ingestion'] = True
except ImportError:
    _AVAILABLE_MODULES['data_ingestion'] = False
    WebSocketDataFeed = None
    normalize_orderbook = None

# ML Regime Detection
try:
    from core.ml_regime_detector import (
        detect_market_regime,
        get_volatility_forecast,
    )
    _AVAILABLE_MODULES['ml_regime_detector'] = True
except ImportError:
    _AVAILABLE_MODULES['ml_regime_detector'] = False
    detect_market_regime = None
    get_volatility_forecast = None

# Micro-cap Trading
try:
    from core.micro_cap_sniper import (
        MicroCapSniper,
        get_sniper,
    )
    _AVAILABLE_MODULES['micro_cap_sniper'] = True
except ImportError:
    _AVAILABLE_MODULES['micro_cap_sniper'] = False
    MicroCapSniper = None
    get_sniper = None

try:
    from core.lut_micro_alpha import (
        LUTMicroAlpha,
        run_lut_alpha,
    )
    _AVAILABLE_MODULES['lut_micro_alpha'] = True
except ImportError:
    _AVAILABLE_MODULES['lut_micro_alpha'] = False
    LUTMicroAlpha = None
    run_lut_alpha = None

# Trading Daemons
try:
    from core.trading_daemon import (
        start_trading_daemon,
        stop_trading_daemon,
    )
    _AVAILABLE_MODULES['trading_daemon'] = True
except ImportError:
    _AVAILABLE_MODULES['trading_daemon'] = False
    start_trading_daemon = None
    stop_trading_daemon = None

try:
    from core.lut_daemon import (
        start_lut_daemon,
        stop_lut_daemon,
    )
    _AVAILABLE_MODULES['lut_daemon'] = True
except ImportError:
    _AVAILABLE_MODULES['lut_daemon'] = False
    start_lut_daemon = None
    stop_lut_daemon = None

# Signal Analyzers
try:
    from core.trading.signals.liquidation import (
        LiquidationAnalyzer,
        LiquidationSignal,
        Liquidation,
    )
    from core.trading.signals.dual_ma import (
        DualMAAnalyzer,
        DualMASignal,
        TrendFilter,
    )
    from core.trading.signals.meta_labeler import (
        MetaLabeler,
        MetaLabelResult,
        MarketRegime,
    )
    SIGNAL_ANALYZERS_AVAILABLE = True
except ImportError:
    SIGNAL_ANALYZERS_AVAILABLE = False
    LiquidationAnalyzer = None
    LiquidationSignal = None
    Liquidation = None
    DualMAAnalyzer = None
    DualMASignal = None
    TrendFilter = None
    MetaLabeler = None
    MetaLabelResult = None
    MarketRegime = None

# Advanced Signal Analyzers
try:
    from core.trading.signals.trailing_stop import (
        TrailingStopAnalyzer,
        TrailingStopSignal,
    )
    from core.trading.signals.rsi_strategy import (
        RSIAnalyzer,
        RSISignal,
    )
    from core.trading.signals.macd_strategy import (
        MACDAnalyzer,
        MACDSignal,
    )
    from core.trading.signals.dca_strategy import (
        DCAAnalyzer,
        DCASignal,
    )
    from core.trading.signals.mean_reversion import (
        MeanReversionAnalyzer,
        MeanReversionSignal,
    )
    ADVANCED_SIGNALS_AVAILABLE = True
except ImportError:
    ADVANCED_SIGNALS_AVAILABLE = False
    TrailingStopAnalyzer = None
    TrailingStopSignal = None
    RSIAnalyzer = None
    RSISignal = None
    MACDAnalyzer = None
    MACDSignal = None
    DCAAnalyzer = None
    DCASignal = None
    MeanReversionAnalyzer = None
    MeanReversionSignal = None

# Decision Matrix
try:
    from core.trading.decision_matrix import (
        DecisionMatrix,
        TradeDecision,
        DecisionType,
        EntryConditions,
        ExitConditions,
    )
    DECISION_MATRIX_AVAILABLE = True
except ImportError:
    DECISION_MATRIX_AVAILABLE = False
    DecisionMatrix = None
    TradeDecision = None
    DecisionType = None
    EntryConditions = None
    ExitConditions = None

# Cooldown System
try:
    from core.trading.cooldown import (
        CooldownManager,
        CooldownConfig,
        CooldownType,
        CooldownEvent,
    )
    COOLDOWN_AVAILABLE = True
except ImportError:
    COOLDOWN_AVAILABLE = False
    CooldownManager = None
    CooldownConfig = None
    CooldownType = None
    CooldownEvent = None

# Backtesting Framework
try:
    from core.trading.backtesting import (
        StrategyValidator,
        WalkForwardTester,
        PerformanceMetrics,
        calculate_sharpe,
        calculate_sortino,
        calculate_calmar,
    )
    BACKTESTING_AVAILABLE = True
except ImportError:
    BACKTESTING_AVAILABLE = False
    StrategyValidator = None
    WalkForwardTester = None
    PerformanceMetrics = None
    calculate_sharpe = None
    calculate_sortino = None
    calculate_calmar = None

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
    # Signal Analyzers
    "LiquidationAnalyzer",
    "LiquidationSignal",
    "Liquidation",
    "DualMAAnalyzer",
    "DualMASignal",
    "TrendFilter",
    "MetaLabeler",
    "MetaLabelResult",
    "MarketRegime",
    # Advanced Signal Analyzers
    "TrailingStopAnalyzer",
    "TrailingStopSignal",
    "RSIAnalyzer",
    "RSISignal",
    "MACDAnalyzer",
    "MACDSignal",
    "DCAAnalyzer",
    "DCASignal",
    "MeanReversionAnalyzer",
    "MeanReversionSignal",
    # Decision Matrix
    "DecisionMatrix",
    "TradeDecision",
    "DecisionType",
    "EntryConditions",
    "ExitConditions",
    # Cooldown System
    "CooldownManager",
    "CooldownConfig",
    "CooldownType",
    "CooldownEvent",
    # Backtesting
    "StrategyValidator",
    "WalkForwardTester",
    "PerformanceMetrics",
    "calculate_sharpe",
    "calculate_sortino",
    "calculate_calmar",
    # Availability flags
    "SIGNAL_ANALYZERS_AVAILABLE",
    "ADVANCED_SIGNALS_AVAILABLE",
    "DECISION_MATRIX_AVAILABLE",
    "COOLDOWN_AVAILABLE",
    "BACKTESTING_AVAILABLE",
]
