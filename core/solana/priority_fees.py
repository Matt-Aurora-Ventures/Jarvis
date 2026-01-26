"""
Solana Priority Fee Estimation.

Dynamic priority fee estimation based on network congestion using
the getRecentPrioritizationFees RPC method.

Features:
- Fetch recent prioritization fees from Solana RPC
- Compute percentile-based fee tiers (Low, Medium, High, Ultra)
- Automatic tier selection based on transaction urgency
- Caching with configurable TTL
- Graceful fallback on API errors
- Integration helpers for transaction builders

Usage:
    from core.solana.priority_fees import PriorityFeeEstimator, PriorityFeeTier

    estimator = PriorityFeeEstimator(rpc_client=client)
    fee, tier = await estimator.get_recommended_fee(urgency=0.7)

    # Or use convenience function
    fee = await get_priority_fee(urgency=0.5)

Reference:
    https://solana.com/docs/rpc/http/getrecentprioritizationfees
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum, IntEnum
from typing import Any, Dict, List, Optional, Tuple

try:
    from solana.rpc.async_api import AsyncClient
    HAS_SOLANA = True
except ImportError:
    HAS_SOLANA = False
    AsyncClient = None

try:
    import aiohttp
    HAS_AIOHTTP = True
except ImportError:
    HAS_AIOHTTP = False
    aiohttp = None

logger = logging.getLogger(__name__)

# =============================================================================
# CONSTANTS
# =============================================================================

# Minimum priority fee to ensure transaction viability (1000 microlamports)
MIN_PRIORITY_FEE = 1000

# Maximum priority fee cap (10 SOL = 10B lamports - prevent runaway fees)
MAX_PRIORITY_FEE = 10_000_000_000

# Default fee estimates when RPC is unavailable (in microlamports per compute unit)
DEFAULT_FEES = {
    'low': 1000,          # 1000 microlamports
    'medium': 10000,      # 10,000 microlamports
    'high': 100000,       # 100,000 microlamports
    'ultra': 1000000,     # 1,000,000 microlamports
}

# Default cache TTL (10 seconds)
DEFAULT_CACHE_TTL_SECONDS = 10

# Default compute units estimate
DEFAULT_COMPUTE_UNITS = 200000


# =============================================================================
# ENUMS
# =============================================================================

class PriorityFeeTier(IntEnum):
    """Priority fee tiers for transaction urgency."""
    LOW = 1      # 25th percentile - economy, non-urgent
    MEDIUM = 2   # 50th percentile - standard
    HIGH = 3     # 75th percentile - fast, important
    ULTRA = 4    # 95th percentile - critical, time-sensitive


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class FeeTiers:
    """Container for computed fee tiers."""
    low: int
    medium: int
    high: int
    ultra: int
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'low': self.low,
            'medium': self.medium,
            'high': self.high,
            'ultra': self.ultra,
            'timestamp': self.timestamp,
        }

    def get(self, tier: PriorityFeeTier) -> int:
        """Get fee for a specific tier."""
        tier_map = {
            PriorityFeeTier.LOW: self.low,
            PriorityFeeTier.MEDIUM: self.medium,
            PriorityFeeTier.HIGH: self.high,
            PriorityFeeTier.ULTRA: self.ultra,
        }
        return tier_map[tier]


# =============================================================================
# PRIORITY FEE ESTIMATOR
# =============================================================================

class PriorityFeeEstimator:
    """
    Estimates optimal priority fees based on recent network activity.

    Uses the getRecentPrioritizationFees RPC method to fetch recent
    prioritization fees and computes percentile-based fee tiers.
    """

    def __init__(
        self,
        rpc_client: Optional[Any] = None,
        rpc_url: Optional[str] = None,
        cache_ttl_seconds: float = DEFAULT_CACHE_TTL_SECONDS,
    ):
        """
        Initialize the priority fee estimator.

        Args:
            rpc_client: Async RPC client (e.g., solana.rpc.async_api.AsyncClient)
            rpc_url: RPC endpoint URL (used if rpc_client not provided)
            cache_ttl_seconds: How long to cache fee estimates
        """
        self._rpc_client = rpc_client
        self._rpc_url = rpc_url or "https://api.mainnet-beta.solana.com"
        self._cache_ttl = cache_ttl_seconds

        # Cache
        self._cached_tiers: Optional[FeeTiers] = None
        self._cache_timestamp: float = 0

        # Last successful tiers (fallback)
        self._last_good_tiers: Optional[FeeTiers] = None

    async def fetch_recent_fees(
        self,
        accounts: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Fetch recent prioritization fees from RPC.

        Args:
            accounts: Optional list of account addresses to filter fees by
                     (useful for getting fees specific to writable accounts)

        Returns:
            List of fee data with slot and prioritizationFee fields
        """
        if self._rpc_client is not None:
            # Use provided RPC client
            if accounts:
                response = await self._rpc_client.get_recent_prioritization_fees(accounts)
            else:
                response = await self._rpc_client.get_recent_prioritization_fees()

            if hasattr(response, 'value'):
                return response.value if response.value else []
            return response if isinstance(response, list) else []

        # Fallback: Direct HTTP call
        if not HAS_AIOHTTP:
            logger.warning("aiohttp not available for RPC call")
            return []

        params = [accounts] if accounts else []
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getRecentPrioritizationFees",
            "params": params,
        }

        timeout = aiohttp.ClientTimeout(total=10)
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(self._rpc_url, json=payload) as resp:
                    if resp.status != 200:
                        logger.error(f"RPC returned HTTP {resp.status}")
                        return []

                    data = await resp.json()
                    if "error" in data:
                        logger.error(f"RPC error: {data['error']}")
                        return []

                    return data.get("result", [])

        except Exception as e:
            logger.error(f"Failed to fetch priority fees: {e}")
            return []

    async def compute_fee_tiers(
        self,
        force_refresh: bool = False,
    ) -> FeeTiers:
        """
        Compute fee tiers from recent prioritization fee data.

        Args:
            force_refresh: Bypass cache and fetch fresh data

        Returns:
            FeeTiers with low/medium/high/ultra estimates
        """
        # Check cache
        if not force_refresh and self._cached_tiers is not None:
            if time.time() - self._cache_timestamp < self._cache_ttl:
                return self._cached_tiers

        # Fetch fresh data
        try:
            fee_data = await self.fetch_recent_fees()

            if not fee_data:
                logger.warning("No fee data received, using fallback")
                return self._get_fallback_tiers()

            # Extract fees and sort
            fees = sorted([
                entry.get('prioritizationFee', 0)
                for entry in fee_data
                if isinstance(entry, dict)
            ])

            if not fees:
                logger.warning("No valid fees in response, using fallback")
                return self._get_fallback_tiers()

            # Compute percentiles
            tiers = FeeTiers(
                low=self._percentile(fees, 25),
                medium=self._percentile(fees, 50),
                high=self._percentile(fees, 75),
                ultra=self._percentile(fees, 95),
            )

            # Apply minimum fee
            tiers = FeeTiers(
                low=max(tiers.low, MIN_PRIORITY_FEE),
                medium=max(tiers.medium, MIN_PRIORITY_FEE),
                high=max(tiers.high, MIN_PRIORITY_FEE),
                ultra=max(tiers.ultra, MIN_PRIORITY_FEE),
            )

            # Apply maximum cap
            tiers = FeeTiers(
                low=min(tiers.low, MAX_PRIORITY_FEE),
                medium=min(tiers.medium, MAX_PRIORITY_FEE),
                high=min(tiers.high, MAX_PRIORITY_FEE),
                ultra=min(tiers.ultra, MAX_PRIORITY_FEE),
            )

            # Update cache
            self._cached_tiers = tiers
            self._cache_timestamp = time.time()
            self._last_good_tiers = tiers

            logger.debug(f"Computed fee tiers: {tiers.to_dict()}")
            return tiers

        except Exception as e:
            logger.error(f"Error computing fee tiers: {e}")
            return self._get_fallback_tiers()

    def _get_fallback_tiers(self) -> FeeTiers:
        """Get fallback fee tiers (last good or defaults)."""
        if self._last_good_tiers is not None:
            return self._last_good_tiers

        return FeeTiers(
            low=DEFAULT_FEES['low'],
            medium=DEFAULT_FEES['medium'],
            high=DEFAULT_FEES['high'],
            ultra=DEFAULT_FEES['ultra'],
        )

    @staticmethod
    def _percentile(values: List[int], p: float) -> int:
        """
        Calculate percentile from sorted values.

        Uses linear interpolation for more accurate estimates.
        """
        if not values:
            return 0

        n = len(values)
        if n == 1:
            return values[0]

        # Index for percentile
        idx = (p / 100) * (n - 1)
        lower_idx = int(idx)
        upper_idx = min(lower_idx + 1, n - 1)

        # Linear interpolation
        fraction = idx - lower_idx
        result = values[lower_idx] + fraction * (values[upper_idx] - values[lower_idx])

        return int(result)

    async def get_recommended_fee(
        self,
        urgency: float = 0.5,
    ) -> Tuple[int, PriorityFeeTier]:
        """
        Get recommended priority fee based on urgency.

        Args:
            urgency: Transaction urgency from 0.0 (low) to 1.0 (critical)

        Returns:
            Tuple of (fee_amount, tier)
        """
        tiers = await self.compute_fee_tiers()

        # Map urgency to tier
        if urgency < 0.25:
            tier = PriorityFeeTier.LOW
        elif urgency < 0.6:
            tier = PriorityFeeTier.MEDIUM
        elif urgency < 0.9:
            tier = PriorityFeeTier.HIGH
        else:
            tier = PriorityFeeTier.ULTRA

        fee = tiers.get(tier)

        # Apply bounds
        fee = max(fee, MIN_PRIORITY_FEE)
        fee = min(fee, MAX_PRIORITY_FEE)

        return fee, tier

    async def get_fee_for_tier(self, tier: PriorityFeeTier) -> int:
        """
        Get the current fee for a specific tier.

        Args:
            tier: The priority tier

        Returns:
            Fee amount in microlamports per compute unit
        """
        tiers = await self.compute_fee_tiers()
        return tiers.get(tier)


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def compute_unit_price_from_fee(
    fee_lamports: int,
    compute_units: int = DEFAULT_COMPUTE_UNITS,
) -> int:
    """
    Convert priority fee to compute unit price.

    The SetComputeUnitPrice instruction expects the price in
    microlamports (1/1,000,000 of a lamport) per compute unit.

    Args:
        fee_lamports: Total fee in lamports
        compute_units: Number of compute units to budget

    Returns:
        Price per compute unit in microlamports
    """
    if compute_units <= 0:
        return 0

    # Convert lamports to microlamports (multiply by 1,000,000)
    # Then divide by compute units
    return (fee_lamports * 1_000_000) // compute_units


def create_priority_fee_instructions(
    priority_fee_lamports: int,
    compute_units: int = DEFAULT_COMPUTE_UNITS,
) -> List[Any]:
    """
    Create compute budget instructions for priority fees.

    Returns instructions to:
    1. Set compute unit limit
    2. Set compute unit price (priority fee)

    Args:
        priority_fee_lamports: Priority fee in lamports
        compute_units: Compute unit limit

    Returns:
        List of instruction objects (solders format)
    """
    try:
        from solders.compute_budget import set_compute_unit_limit, set_compute_unit_price
    except ImportError:
        logger.warning("solders not available - cannot create compute budget instructions")
        # Return empty list but include metadata for testing
        return [{"type": "compute_budget", "fee": priority_fee_lamports, "units": compute_units}]

    unit_price = compute_unit_price_from_fee(priority_fee_lamports, compute_units)

    return [
        set_compute_unit_limit(compute_units),
        set_compute_unit_price(unit_price),
    ]


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

# Global estimator instance (lazy initialization)
_global_estimator: Optional[PriorityFeeEstimator] = None


def _get_global_estimator() -> PriorityFeeEstimator:
    """Get or create the global estimator instance."""
    global _global_estimator
    if _global_estimator is None:
        _global_estimator = PriorityFeeEstimator()
    return _global_estimator


async def get_priority_fee(
    urgency: float = 0.5,
    rpc_url: Optional[str] = None,
) -> int:
    """
    Convenience function to get a priority fee.

    Args:
        urgency: Transaction urgency (0.0-1.0)
        rpc_url: Optional RPC URL (uses default if not provided)

    Returns:
        Recommended priority fee in microlamports per compute unit
    """
    if rpc_url:
        estimator = PriorityFeeEstimator(rpc_url=rpc_url)
    else:
        estimator = _get_global_estimator()

    fee, _ = await estimator.get_recommended_fee(urgency)
    return fee


async def estimate_swap_priority_fee(
    input_mint: str,
    output_mint: str,
    urgency: float = 0.5,
    rpc_url: Optional[str] = None,
) -> int:
    """
    Estimate priority fee for a swap transaction.

    For swaps, we could potentially filter fees by the specific
    accounts involved (Jupiter program, AMMs, token accounts).
    Currently uses general priority fee estimation.

    Args:
        input_mint: Input token mint address
        output_mint: Output token mint address
        urgency: Transaction urgency (0.0-1.0)
        rpc_url: Optional RPC URL

    Returns:
        Recommended priority fee
    """
    # For now, use the general estimation
    # Future enhancement: filter by swap-related accounts
    return await get_priority_fee(urgency=urgency, rpc_url=rpc_url)


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
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
]
