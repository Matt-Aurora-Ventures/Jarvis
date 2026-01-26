"""Solana-specific modules for RPC health, execution, and monitoring."""

from core.solana.rpc_health import (
    RPCHealthScorer,
    EndpointHealth,
    HealthScore,
    LatencyStats,
    HealthCheckResult,
    HEALTH_CHECK_INTERVAL,
)

from core.solana.priority_fees import (
    PriorityFeeEstimator,
    PriorityFeeTier,
    FeeTiers,
    MIN_PRIORITY_FEE,
    MAX_PRIORITY_FEE,
    DEFAULT_FEES,
    compute_unit_price_from_fee,
    create_priority_fee_instructions,
    get_priority_fee,
    estimate_swap_priority_fee,
)

# Retry logic requires solana-py, make imports optional
try:
    from core.solana.retry_logic import (
        ErrorType,
        BlockhashCache,
        RetryConfig,
        RetryStats,
        TransactionRetryManager,
        send_transaction_with_retry,
    )
    HAS_RETRY_LOGIC = True
except ImportError:
    HAS_RETRY_LOGIC = False
    ErrorType = None
    BlockhashCache = None
    RetryConfig = None
    RetryStats = None
    TransactionRetryManager = None
    send_transaction_with_retry = None

# Import circuit breaker and error handler
from core.solana.circuit_breaker import (
    CircuitState,
    CircuitStats,
    CircuitOpenError,
    RPCCircuitBreaker,
    RPCCircuitBreakerManager,
    get_rpc_circuit_manager,
    get_rpc_circuit_breaker,
    rpc_circuit_breaker,
    get_rpc_provider_breaker,
    RPC_PROVIDER_CONFIGS,
)

from core.solana.error_handler import (
    ErrorCategory,
    ErrorPattern,
    RPCErrorHandler,
    get_rpc_error_handler,
    categorize_error,
    get_user_error_message,
    should_retry_error,
    log_rpc_error,
    USER_MESSAGES,
)

from core.solana.jito_bundles import (
    # Classes
    DynamicTipCalculator,
    JitoBundleBuilder,
    JitoBundleClient,
    JitoBundleSubmitter,
    BundleStatusTracker,
    # Data classes
    BundleResult,
    BundleInfo,
    BundleStatusEntry,
    JitoBundle,
    # Enums
    UrgencyLevel,
    BundleStatus,
    JitoRegion,
    # Constants
    MIN_TIP_LAMPORTS,
    MAX_TIP_LAMPORTS,
    DEFAULT_TIP_LAMPORTS,
    BUNDLE_SIZE_TIP_LAMPORTS,
    JITO_TIP_ACCOUNTS,
    # Functions
    calculate_tip,
    submit_bundle,
)

__all__ = [
    # RPC Health
    "RPCHealthScorer",
    "EndpointHealth",
    "HealthScore",
    "LatencyStats",
    "HealthCheckResult",
    "HEALTH_CHECK_INTERVAL",
    # Priority Fees
    "PriorityFeeEstimator",
    "PriorityFeeTier",
    "FeeTiers",
    "MIN_PRIORITY_FEE",
    "MAX_PRIORITY_FEE",
    "DEFAULT_FEES",
    "compute_unit_price_from_fee",
    "create_priority_fee_instructions",
    "get_priority_fee",
    "estimate_swap_priority_fee",
    # Retry Logic
    "ErrorType",
    "BlockhashCache",
    "RetryConfig",
    "RetryStats",
    "TransactionRetryManager",
    "send_transaction_with_retry",
    # Circuit Breaker
    "CircuitState",
    "CircuitStats",
    "CircuitOpenError",
    "RPCCircuitBreaker",
    "RPCCircuitBreakerManager",
    "get_rpc_circuit_manager",
    "get_rpc_circuit_breaker",
    "rpc_circuit_breaker",
    "get_rpc_provider_breaker",
    "RPC_PROVIDER_CONFIGS",
    # Error Handler
    "ErrorCategory",
    "ErrorPattern",
    "RPCErrorHandler",
    "get_rpc_error_handler",
    "categorize_error",
    "get_user_error_message",
    "should_retry_error",
    "log_rpc_error",
    "USER_MESSAGES",
    # Jito Bundles
    "DynamicTipCalculator",
    "JitoBundleBuilder",
    "JitoBundleClient",
    "JitoBundleSubmitter",
    "BundleStatusTracker",
    "BundleResult",
    "BundleInfo",
    "BundleStatusEntry",
    "JitoBundle",
    "UrgencyLevel",
    "BundleStatus",
    "JitoRegion",
    "MIN_TIP_LAMPORTS",
    "MAX_TIP_LAMPORTS",
    "DEFAULT_TIP_LAMPORTS",
    "BUNDLE_SIZE_TIP_LAMPORTS",
    "JITO_TIP_ACCOUNTS",
    "calculate_tip",
    "submit_bundle",
]
