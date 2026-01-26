"""
Jito Bundle Optimization with Dynamic Tip Calculation.

Provides MEV protection and faster transaction confirmation via Jito bundles.
Implements dynamic tip calculation based on:
- Network congestion (from getRecentPrioritizationFees)
- Bundle size
- Urgency level

Features:
- Bundle creation and submission to Jito block engine
- Dynamic tip calculation with congestion awareness
- Bundle status tracking
- Retry logic with exponential backoff
- Integration with existing priority fee estimator

Usage:
    from core.solana.jito_bundles import (
        JitoBundleSubmitter,
        DynamicTipCalculator,
        UrgencyLevel,
    )

    # Calculate optimal tip
    calculator = DynamicTipCalculator()
    tip = calculator.calculate_optimal_tip(
        recent_fees=[10000, 15000, 12000],
        urgency=UrgencyLevel.HIGH,
        num_transactions=3,
    )

    # Submit bundle
    submitter = JitoBundleSubmitter()
    result = await submitter.submit(
        transactions=[tx1, tx2],
        tip_lamports=tip,
    )

References:
    - Jito docs: https://docs.jito.wtf/
    - Jito low latency tx send: https://docs.jito.wtf/lowlatencytxnsend/
"""

from __future__ import annotations

import asyncio
import base64
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

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

# Tip calculation constants
MIN_TIP_LAMPORTS = 1000         # Minimum tip floor (1000 lamports)
MAX_TIP_LAMPORTS = 1_000_000    # Maximum tip cap (0.001 SOL = 1M lamports)
DEFAULT_TIP_LAMPORTS = 5000     # Default when no data available
BUNDLE_SIZE_TIP_LAMPORTS = 500  # Additional tip per extra transaction

# Congestion thresholds (in microlamports per compute unit)
CONGESTION_LOW_THRESHOLD = 1000
CONGESTION_MEDIUM_THRESHOLD = 10000
CONGESTION_HIGH_THRESHOLD = 50000
CONGESTION_EXTREME_THRESHOLD = 100000

# Jito endpoints by region
JITO_ENDPOINTS = {
    "mainnet": "https://mainnet.block-engine.jito.wtf",
    "amsterdam": "https://amsterdam.mainnet.block-engine.jito.wtf",
    "frankfurt": "https://frankfurt.mainnet.block-engine.jito.wtf",
    "ny": "https://ny.mainnet.block-engine.jito.wtf",
    "tokyo": "https://tokyo.mainnet.block-engine.jito.wtf",
}

# Known Jito tip accounts
JITO_TIP_ACCOUNTS = [
    "96gYZGLnJYVFmbjzopPSU6QiEV5fGqZNyN9nmNhvrZU5",
    "HFqU5x63VTqvQss8hp11i4wVV8bD44PvwucfZ2bU7gRe",
    "Cw8CFyM9FkoMi7K7Crf6HNQqf4uEMzpKw6QNghXLvLkY",
    "ADaUMid9yfUytqMBgopwjb2DTLSokTSzL1zt6iGPaS49",
    "DfXygSm4jCyNCybVYYK6DwvWqjKee8pbDmJGcLWNDXjh",
    "ADuUkR4vqLUMWXxW9gh6D6L8pMSawimctcNZ5pGwDcEt",
    "DttWaMuVvTiduZRnguLF7jNxTgiMBZ1hyAumKUiL2KRL",
    "3AVi9Tg9Uo68tJfuvoKvqKNWKkC5wPdSSdeBnizKZ6jT",
]

# Max transactions per bundle
MAX_BUNDLE_TRANSACTIONS = 5


# =============================================================================
# ENUMS
# =============================================================================

class UrgencyLevel(Enum):
    """Transaction urgency levels for tip calculation."""
    LOW = 1      # Non-urgent, economy
    MEDIUM = 2   # Standard
    HIGH = 3     # Urgent, time-sensitive

    @classmethod
    def from_string(cls, value: str) -> "UrgencyLevel":
        """Convert string to UrgencyLevel."""
        normalized = value.upper()
        if normalized == "LOW":
            return cls.LOW
        elif normalized == "MEDIUM":
            return cls.MEDIUM
        elif normalized == "HIGH":
            return cls.HIGH
        else:
            raise ValueError(f"Invalid urgency level: {value}")


class BundleStatus(Enum):
    """Status of a submitted bundle."""
    PENDING = "pending"       # Submitted, awaiting processing
    PROCESSING = "processing" # Being processed by block engine
    LANDED = "landed"         # Successfully included in a block
    FAILED = "failed"         # Failed to land
    DROPPED = "dropped"       # Dropped from mempool

    @property
    def is_terminal(self) -> bool:
        """Check if this is a terminal (final) status."""
        return self in (BundleStatus.LANDED, BundleStatus.FAILED, BundleStatus.DROPPED)


class JitoRegion(Enum):
    """Jito block engine regions."""
    MAINNET = "mainnet"
    AMSTERDAM = "amsterdam"
    FRANKFURT = "frankfurt"
    NY = "ny"
    TOKYO = "tokyo"


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class BundleResult:
    """Result of bundle submission."""
    success: bool
    bundle_id: Optional[str] = None
    slot: Optional[int] = None
    error: Optional[str] = None
    simulation_result: Optional[Dict[str, Any]] = None
    tip_amount: int = 0
    transactions: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "success": self.success,
            "bundle_id": self.bundle_id,
            "slot": self.slot,
            "error": self.error,
            "tip_amount": self.tip_amount,
            "transactions": self.transactions,
        }


@dataclass
class BundleInfo:
    """Information about a tracked bundle."""
    bundle_id: str
    status: BundleStatus
    slot: Optional[int] = None
    timestamp: float = field(default_factory=time.time)


@dataclass
class BundleStatusEntry:
    """Entry in bundle status history."""
    status: BundleStatus
    timestamp: float = field(default_factory=time.time)


@dataclass
class JitoBundle:
    """Represents a Jito bundle ready for submission."""
    transactions: List[bytes]
    tip_amount: int
    tip_instruction: Optional[Any] = None

    def is_valid(self) -> bool:
        """Validate the bundle."""
        if not self.transactions:
            return False
        if len(self.transactions) > MAX_BUNDLE_TRANSACTIONS:
            return False
        return True


# =============================================================================
# DYNAMIC TIP CALCULATOR
# =============================================================================

class DynamicTipCalculator:
    """
    Calculates optimal tips for Jito bundles based on multiple factors.

    Factors considered:
    - Network congestion (from recent prioritization fees)
    - Urgency level (LOW, MEDIUM, HIGH)
    - Bundle size (number of transactions)

    Tip Formula:
        optimal_tip = (base_tip * congestion_multiplier * urgency_multiplier) + bundle_size_tip

    Where:
        - base_tip = 1000 lamports
        - congestion_multiplier = 1x-10x based on recent fees
        - urgency_multiplier = 1x (low), 2x (medium), 3x (high)
        - bundle_size_tip = 500 lamports per additional transaction
    """

    def __init__(self, rpc_url: Optional[str] = None):
        """Initialize the tip calculator."""
        self._rpc_url = rpc_url

    def calculate_base_tip(self) -> int:
        """Get the base tip amount."""
        return MIN_TIP_LAMPORTS

    def get_congestion_multiplier(self, recent_fees: List[int]) -> float:
        """
        Calculate congestion multiplier from recent prioritization fees.

        Args:
            recent_fees: List of recent prioritization fees (microlamports)

        Returns:
            Multiplier from 1.0 (low congestion) to 10.0 (extreme congestion)
        """
        if not recent_fees:
            return 1.0

        avg_fee = sum(recent_fees) / len(recent_fees)

        if avg_fee < CONGESTION_LOW_THRESHOLD:
            return 1.0
        elif avg_fee < CONGESTION_MEDIUM_THRESHOLD:
            # Linear interpolation 1x to 3x
            ratio = (avg_fee - CONGESTION_LOW_THRESHOLD) / (
                CONGESTION_MEDIUM_THRESHOLD - CONGESTION_LOW_THRESHOLD
            )
            return 1.0 + ratio * 2.0
        elif avg_fee < CONGESTION_HIGH_THRESHOLD:
            # Linear interpolation 3x to 7x
            ratio = (avg_fee - CONGESTION_MEDIUM_THRESHOLD) / (
                CONGESTION_HIGH_THRESHOLD - CONGESTION_MEDIUM_THRESHOLD
            )
            return 3.0 + ratio * 4.0
        elif avg_fee < CONGESTION_EXTREME_THRESHOLD:
            # Linear interpolation 7x to 10x
            ratio = (avg_fee - CONGESTION_HIGH_THRESHOLD) / (
                CONGESTION_EXTREME_THRESHOLD - CONGESTION_HIGH_THRESHOLD
            )
            return 7.0 + ratio * 3.0
        else:
            return 10.0

    def get_urgency_multiplier(self, urgency: UrgencyLevel) -> float:
        """
        Get multiplier for urgency level.

        Args:
            urgency: UrgencyLevel enum

        Returns:
            Multiplier: 1x (LOW), 2x (MEDIUM), 3x (HIGH)
        """
        multipliers = {
            UrgencyLevel.LOW: 1.0,
            UrgencyLevel.MEDIUM: 2.0,
            UrgencyLevel.HIGH: 3.0,
        }
        return multipliers.get(urgency, 1.0)

    def get_bundle_size_tip(self, num_transactions: int) -> int:
        """
        Calculate additional tip based on bundle size.

        Args:
            num_transactions: Number of transactions in bundle

        Returns:
            Additional lamports (0 for single tx, +500 per extra tx)
        """
        if num_transactions <= 1:
            return 0
        return (num_transactions - 1) * BUNDLE_SIZE_TIP_LAMPORTS

    def calculate_optimal_tip(
        self,
        recent_fees: List[int],
        urgency: UrgencyLevel,
        num_transactions: int,
    ) -> int:
        """
        Calculate optimal tip considering all factors.

        Args:
            recent_fees: Recent prioritization fees (microlamports)
            urgency: Transaction urgency level
            num_transactions: Number of transactions in bundle

        Returns:
            Optimal tip in lamports, bounded by MIN and MAX
        """
        base_tip = self.calculate_base_tip()
        congestion_mult = self.get_congestion_multiplier(recent_fees)
        urgency_mult = self.get_urgency_multiplier(urgency)
        size_tip = self.get_bundle_size_tip(num_transactions)

        # Calculate total tip
        tip = int(base_tip * congestion_mult * urgency_mult) + size_tip

        # Apply bounds
        tip = max(tip, MIN_TIP_LAMPORTS)
        tip = min(tip, MAX_TIP_LAMPORTS)

        return tip

    async def calculate_optimal_tip_async(
        self,
        urgency: UrgencyLevel,
        num_transactions: int,
    ) -> int:
        """
        Calculate optimal tip using async fee fetching.

        Args:
            urgency: Transaction urgency level
            num_transactions: Number of transactions in bundle

        Returns:
            Optimal tip in lamports
        """
        try:
            # Try to use PriorityFeeEstimator if available
            from core.solana.priority_fees import PriorityFeeEstimator

            estimator = PriorityFeeEstimator(rpc_url=self._rpc_url)
            fee_data = await estimator.fetch_recent_fees()

            recent_fees = [
                entry.get("prioritizationFee", 0)
                for entry in fee_data
                if isinstance(entry, dict)
            ]

            return self.calculate_optimal_tip(
                recent_fees=recent_fees,
                urgency=urgency,
                num_transactions=num_transactions,
            )

        except Exception as e:
            logger.warning(f"Failed to fetch fees, using default: {e}")
            # Fallback: use default tip with urgency multiplier
            base = DEFAULT_TIP_LAMPORTS
            urgency_mult = self.get_urgency_multiplier(urgency)
            size_tip = self.get_bundle_size_tip(num_transactions)
            return int(base * urgency_mult) + size_tip


# =============================================================================
# BUNDLE BUILDER
# =============================================================================

class JitoBundleBuilder:
    """
    Builder for creating Jito bundles.

    Example:
        builder = JitoBundleBuilder()
        builder.add_transaction(tx1_bytes)
        builder.add_transaction(tx2_bytes)
        builder.set_tip(5000)
        bundle = builder.build()
    """

    def __init__(self):
        """Initialize the bundle builder."""
        self.transactions: List[bytes] = []
        self._tip_amount: int = MIN_TIP_LAMPORTS
        self._tip_account: Optional[str] = None

    def add_transaction(self, tx_data: bytes) -> "JitoBundleBuilder":
        """
        Add a transaction to the bundle.

        Args:
            tx_data: Serialized transaction bytes

        Returns:
            Self for chaining

        Raises:
            ValueError: If bundle already has maximum transactions
        """
        if len(self.transactions) >= MAX_BUNDLE_TRANSACTIONS:
            raise ValueError(f"Bundle cannot exceed maximum of {MAX_BUNDLE_TRANSACTIONS} transactions")

        self.transactions.append(tx_data)
        return self

    def set_tip(self, amount: int) -> "JitoBundleBuilder":
        """
        Set the tip amount for the bundle.

        Args:
            amount: Tip in lamports

        Returns:
            Self for chaining
        """
        self._tip_amount = max(amount, MIN_TIP_LAMPORTS)
        return self

    def set_tip_account(self, account: str) -> "JitoBundleBuilder":
        """
        Set the specific tip account to use.

        Args:
            account: Jito tip account pubkey

        Returns:
            Self for chaining
        """
        self._tip_account = account
        return self

    def build(self) -> JitoBundle:
        """
        Build the final bundle.

        Returns:
            JitoBundle ready for submission

        Raises:
            ValueError: If bundle is empty
        """
        if not self.transactions:
            raise ValueError("Cannot build empty bundle")

        # Create tip instruction placeholder
        tip_instruction = {
            "type": "tip",
            "amount": self._tip_amount,
            "account": self._tip_account or JITO_TIP_ACCOUNTS[0],
        }

        return JitoBundle(
            transactions=self.transactions.copy(),
            tip_amount=self._tip_amount,
            tip_instruction=tip_instruction,
        )


# =============================================================================
# BUNDLE STATUS TRACKER
# =============================================================================

class BundleStatusTracker:
    """
    Tracks status of submitted bundles.

    Maintains history of status changes and handles expiry of old entries.
    """

    def __init__(self, expiry_seconds: float = 3600):
        """
        Initialize the tracker.

        Args:
            expiry_seconds: How long to keep bundle tracking data
        """
        self._expiry_seconds = expiry_seconds
        self._bundles: Dict[str, BundleInfo] = {}
        self._history: Dict[str, List[BundleStatusEntry]] = {}

    def track(self, bundle_id: str, status: BundleStatus) -> None:
        """
        Start tracking a bundle.

        Args:
            bundle_id: The bundle identifier
            status: Initial status
        """
        now = time.time()
        self._bundles[bundle_id] = BundleInfo(
            bundle_id=bundle_id,
            status=status,
            timestamp=now,
        )
        self._history[bundle_id] = [BundleStatusEntry(status=status, timestamp=now)]

    def update(
        self,
        bundle_id: str,
        status: BundleStatus,
        slot: Optional[int] = None,
    ) -> None:
        """
        Update bundle status.

        Args:
            bundle_id: The bundle identifier
            status: New status
            slot: Slot number if landed
        """
        if bundle_id not in self._bundles:
            return

        now = time.time()
        self._bundles[bundle_id].status = status
        self._bundles[bundle_id].timestamp = now
        if slot is not None:
            self._bundles[bundle_id].slot = slot

        if bundle_id not in self._history:
            self._history[bundle_id] = []
        self._history[bundle_id].append(BundleStatusEntry(status=status, timestamp=now))

    def get_status(self, bundle_id: str) -> Optional[BundleStatus]:
        """
        Get current status of a bundle.

        Args:
            bundle_id: The bundle identifier

        Returns:
            Current status or None if not tracked
        """
        if bundle_id not in self._bundles:
            return None
        return self._bundles[bundle_id].status

    def get_info(self, bundle_id: str) -> Optional[BundleInfo]:
        """
        Get full info for a bundle.

        Args:
            bundle_id: The bundle identifier

        Returns:
            BundleInfo or None if not tracked
        """
        return self._bundles.get(bundle_id)

    def get_history(self, bundle_id: str) -> List[BundleStatusEntry]:
        """
        Get status history for a bundle.

        Args:
            bundle_id: The bundle identifier

        Returns:
            List of status entries (may be empty)
        """
        return self._history.get(bundle_id, [])

    def cleanup_expired(self) -> int:
        """
        Remove expired bundle tracking entries.

        Returns:
            Number of entries removed
        """
        cutoff = time.time() - self._expiry_seconds
        expired = [
            bid for bid, info in self._bundles.items()
            if info.timestamp < cutoff
        ]

        for bid in expired:
            del self._bundles[bid]
            if bid in self._history:
                del self._history[bid]

        return len(expired)


# =============================================================================
# BUNDLE CLIENT
# =============================================================================

class JitoBundleClient:
    """
    Low-level client for Jito block engine API.

    Handles HTTP communication with Jito endpoints.
    """

    def __init__(
        self,
        region: JitoRegion = JitoRegion.MAINNET,
        auth_token: Optional[str] = None,
    ):
        """
        Initialize the client.

        Args:
            region: Jito region to connect to
            auth_token: Optional authentication token
        """
        self.region = region
        self.endpoint = JITO_ENDPOINTS.get(region.value, JITO_ENDPOINTS["mainnet"])
        self.auth_token = auth_token
        self._session: Optional[Any] = None

    async def _get_session(self) -> Any:
        """Get or create aiohttp session."""
        if not HAS_AIOHTTP:
            raise RuntimeError("aiohttp not installed")

        if self._session is None or self._session.closed:
            headers = {"Content-Type": "application/json"}
            if self.auth_token:
                headers["Authorization"] = f"Bearer {self.auth_token}"
            self._session = aiohttp.ClientSession(headers=headers)

        return self._session

    async def close(self) -> None:
        """Close the HTTP session."""
        if self._session and not self._session.closed:
            await self._session.close()

    async def _http_get(self, path: str) -> Dict[str, Any]:
        """Perform HTTP GET request."""
        session = await self._get_session()
        async with session.get(f"{self.endpoint}{path}") as resp:
            return await resp.json()

    async def _http_post(self, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Perform HTTP POST request."""
        session = await self._get_session()
        async with session.post(f"{self.endpoint}{path}", json=payload) as resp:
            return await resp.json()

    async def get_tip_accounts(self) -> List[str]:
        """
        Get current Jito tip accounts.

        Returns:
            List of tip account pubkeys
        """
        try:
            result = await self._http_get("/api/v1/bundles/tip_accounts")
            return result.get("result", JITO_TIP_ACCOUNTS)
        except Exception:
            return JITO_TIP_ACCOUNTS

    async def get_bundle_status(self, bundle_id: str) -> BundleInfo:
        """
        Get status of a submitted bundle.

        Args:
            bundle_id: The bundle identifier

        Returns:
            BundleInfo with current status
        """
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getBundleStatuses",
            "params": [[bundle_id]],
        }

        result = await self._http_post("/api/v1/bundles", payload)
        data = result.get("result", {})

        # Parse status
        status_str = data.get("status", "pending").lower()
        status_map = {
            "pending": BundleStatus.PENDING,
            "processing": BundleStatus.PROCESSING,
            "landed": BundleStatus.LANDED,
            "failed": BundleStatus.FAILED,
            "dropped": BundleStatus.DROPPED,
        }
        status = status_map.get(status_str, BundleStatus.PENDING)

        return BundleInfo(
            bundle_id=bundle_id,
            status=status,
            slot=data.get("slot"),
        )

    async def send_bundle(
        self,
        transactions: List[bytes],
        tip_lamports: int = MIN_TIP_LAMPORTS,
    ) -> BundleResult:
        """
        Send a bundle to Jito block engine.

        Args:
            transactions: List of serialized transactions
            tip_lamports: Tip amount

        Returns:
            BundleResult with success status
        """
        if len(transactions) > MAX_BUNDLE_TRANSACTIONS:
            return BundleResult(
                success=False,
                error=f"Maximum {MAX_BUNDLE_TRANSACTIONS} transactions per bundle"
            )

        if len(transactions) == 0:
            return BundleResult(success=False, error="Empty bundle")

        try:
            # Encode transactions as base64
            encoded_txs = [base64.b64encode(tx).decode() for tx in transactions]

            payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "sendBundle",
                "params": [encoded_txs],
            }

            result = await self._http_post("/api/v1/bundles", payload)

            if "error" in result:
                return BundleResult(
                    success=False,
                    error=result["error"].get("message", str(result["error"])),
                )

            bundle_id = result.get("result")

            return BundleResult(
                success=True,
                bundle_id=bundle_id,
                tip_amount=tip_lamports,
            )

        except Exception as e:
            logger.error(f"Bundle submission failed: {e}")
            return BundleResult(success=False, error=str(e))

    async def simulate_bundle(self, transactions: List[bytes]) -> Dict[str, Any]:
        """
        Simulate a bundle before submission.

        Args:
            transactions: List of serialized transactions

        Returns:
            Simulation result
        """
        try:
            encoded_txs = [base64.b64encode(tx).decode() for tx in transactions]

            payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "simulateBundle",
                "params": [{"encodedTransactions": encoded_txs}],
            }

            result = await self._http_post("/api/v1/bundles", payload)

            if "error" in result:
                return {"success": False, "error": result["error"]}

            return {
                "success": True,
                "result": result.get("result", {}),
            }

        except Exception as e:
            return {"success": False, "error": str(e)}


# =============================================================================
# BUNDLE SUBMITTER
# =============================================================================

class JitoBundleSubmitter:
    """
    High-level bundle submitter with retry logic.

    Features:
    - Automatic retries with exponential backoff
    - Optional simulation before submission
    - Integration with dynamic tip calculation
    """

    def __init__(
        self,
        region: JitoRegion = JitoRegion.MAINNET,
        max_retries: int = 3,
        base_delay_ms: int = 500,
        simulate_first: bool = False,
    ):
        """
        Initialize the submitter.

        Args:
            region: Jito region to connect to
            max_retries: Maximum retry attempts
            base_delay_ms: Base delay for exponential backoff (ms)
            simulate_first: Whether to simulate before submission
        """
        self._client = JitoBundleClient(region=region)
        self._max_retries = max_retries
        self._base_delay_ms = base_delay_ms
        self._simulate_first = simulate_first
        self._tracker = BundleStatusTracker()

    async def close(self) -> None:
        """Close connections."""
        await self._client.close()

    async def _send_to_jito(
        self,
        transactions: List[bytes],
        tip_lamports: int,
    ) -> BundleResult:
        """Send bundle to Jito (internal)."""
        return await self._client.send_bundle(transactions, tip_lamports)

    async def _simulate_bundle(self, transactions: List[bytes]) -> Dict[str, Any]:
        """Simulate bundle (internal)."""
        return await self._client.simulate_bundle(transactions)

    async def submit(
        self,
        transactions: List[bytes],
        tip_lamports: int,
    ) -> BundleResult:
        """
        Submit a bundle with retry logic.

        Args:
            transactions: List of serialized transactions
            tip_lamports: Tip amount in lamports

        Returns:
            BundleResult with success status
        """
        # Optionally simulate first
        if self._simulate_first:
            sim_result = await self._simulate_bundle(transactions)
            if not sim_result.get("success"):
                return BundleResult(
                    success=False,
                    error=f"Simulation failed: {sim_result.get('error')}",
                    simulation_result=sim_result,
                )

        # Submit with retries
        last_error = None
        for attempt in range(self._max_retries):
            result = await self._send_to_jito(transactions, tip_lamports)

            if result.success:
                # Track the bundle
                if result.bundle_id:
                    self._tracker.track(result.bundle_id, BundleStatus.PENDING)
                return result

            last_error = result.error
            logger.warning(f"Bundle attempt {attempt + 1} failed: {last_error}")

            # Exponential backoff
            if attempt < self._max_retries - 1:
                delay_ms = self._base_delay_ms * (2 ** attempt)
                await asyncio.sleep(delay_ms / 1000)

        return BundleResult(
            success=False,
            error=f"Failed after {self._max_retries} attempts: {last_error}",
            tip_amount=tip_lamports,
        )


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def calculate_tip(
    recent_fees: List[int],
    urgency: str,
    num_transactions: int,
) -> int:
    """
    Calculate optimal tip (sync convenience function).

    Args:
        recent_fees: Recent prioritization fees
        urgency: Urgency level ("low", "medium", "high")
        num_transactions: Number of transactions

    Returns:
        Optimal tip in lamports
    """
    calculator = DynamicTipCalculator()
    urgency_level = UrgencyLevel.from_string(urgency)
    return calculator.calculate_optimal_tip(
        recent_fees=recent_fees,
        urgency=urgency_level,
        num_transactions=num_transactions,
    )


async def submit_bundle(
    transactions: List[bytes],
    urgency: str = "medium",
    tip_lamports: Optional[int] = None,
    simulate: bool = True,
) -> BundleResult:
    """
    Quick bundle submission (async convenience function).

    Args:
        transactions: List of serialized transactions
        urgency: Urgency level string
        tip_lamports: Optional explicit tip (auto-calculated if not provided)
        simulate: Whether to simulate first

    Returns:
        BundleResult
    """
    submitter = JitoBundleSubmitter(simulate_first=simulate)

    # Calculate tip if not provided
    if tip_lamports is None:
        calculator = DynamicTipCalculator()
        urgency_level = UrgencyLevel.from_string(urgency)
        tip_lamports = await calculator.calculate_optimal_tip_async(
            urgency=urgency_level,
            num_transactions=len(transactions),
        )

    try:
        return await submitter.submit(transactions, tip_lamports)
    finally:
        await submitter.close()


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    # Classes
    "DynamicTipCalculator",
    "JitoBundleBuilder",
    "JitoBundleClient",
    "JitoBundleSubmitter",
    "BundleStatusTracker",
    # Data classes
    "BundleResult",
    "BundleInfo",
    "BundleStatusEntry",
    "JitoBundle",
    # Enums
    "UrgencyLevel",
    "BundleStatus",
    "JitoRegion",
    # Constants
    "MIN_TIP_LAMPORTS",
    "MAX_TIP_LAMPORTS",
    "DEFAULT_TIP_LAMPORTS",
    "BUNDLE_SIZE_TIP_LAMPORTS",
    "JITO_TIP_ACCOUNTS",
    # Functions
    "calculate_tip",
    "submit_bundle",
]
