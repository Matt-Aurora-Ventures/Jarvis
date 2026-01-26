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

from core.solana.retry_logic import (
    ErrorCategory,
    classify_error,
    is_retryable,
    needs_blockhash_refresh,
    calculate_backoff,
    execute_with_retry,
    BlockhashCache,
    RetryStrategy,
    RetryMetrics,
    RetryResult,
    TransactionRetryExecutor,
    BLOCKHASH_VALIDITY_SECONDS,
    DEFAULT_VALIDITY_THRESHOLD,
    DEFAULT_MAX_RETRIES,
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
    "ErrorCategory",
    "classify_error",
    "is_retryable",
    "needs_blockhash_refresh",
    "calculate_backoff",
    "execute_with_retry",
    "BlockhashCache",
    "RetryStrategy",
    "RetryMetrics",
    "RetryResult",
    "TransactionRetryExecutor",
    "BLOCKHASH_VALIDITY_SECONDS",
    "DEFAULT_VALIDITY_THRESHOLD",
    "DEFAULT_MAX_RETRIES",
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
