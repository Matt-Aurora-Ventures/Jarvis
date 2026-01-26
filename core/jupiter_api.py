"""
Jupiter DEX API Client - Simplified wrapper

US-005: bags.fm + Jupiter Backup with TP/SL

This is a clean, focused API wrapper for Jupiter swap operations.
For the full-featured client with DCA and advanced features, see bots/treasury/jupiter.py

Features:
- Transaction simulation with preflight checks
- Honeypot detection from simulation errors
- Compute unit estimation with 10% buffer
- Dynamic priority fees via Helius getPriorityFeeEstimate API
"""

import logging
import os
import re
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# =============================================================================
# CONSTANTS
# =============================================================================

# Default priority fee in microlamports (50,000 = 0.00005 SOL)
DEFAULT_PRIORITY_FEE = 50000

# Maximum priority fee cap to prevent runaway costs during congestion
# Default: 1 SOL = 1,000,000,000 lamports
DEFAULT_MAX_PRIORITY_FEE_LAMPORTS = 1_000_000_000

# Helius RPC URL pattern
HELIUS_RPC_URL = "https://mainnet.helius-rpc.com/?api-key={api_key}"


# =============================================================================
# ENUMS
# =============================================================================

class PriorityLevel(str, Enum):
    """
    Priority levels for transaction fees.

    Maps to Helius getPriorityFeeEstimate levels:
    - MIN: Lowest fee, may take longer to confirm
    - LOW: Low fee, suitable for non-urgent transactions
    - MEDIUM: Standard fee for normal transactions
    - HIGH: Higher fee for faster confirmation
    - VERY_HIGH: Highest fee for critical/time-sensitive transactions
    """
    MIN = "min"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERY_HIGH = "veryHigh"

# Honeypot detection patterns in simulation logs
HONEYPOT_PATTERNS = [
    r"transfer\s+blocked",
    r"transfer\s+not\s+allowed",
    r"cannot\s+transfer",
    r"trading\s+disabled",
    r"blacklisted",
    r"frozen",
    r"paused",
]

# Potential rug patterns (slippage manipulation)
RUG_PATTERNS = [
    r"slippage.*exceeded",
    r"insufficient.*output",
    r"expected\s+minimum.*got:\s*[01]$",
]


class JupiterAPI:
    """
    Simple Jupiter API client for swap operations.

    Usage:
        api = JupiterAPI()
        quote = await api.get_quote(
            input_mint="So11111111111111111111111111111111111111112",
            output_mint="TOKEN_MINT",
            amount=1000000000,  # 1 SOL in lamports
            slippage_bps=100
        )
        result = await api.execute_swap(quote, user_public_key="...")
    """

    BASE_URL = "https://quote-api.jup.ag/v6"
    SWAP_URL = "https://quote-api.jup.ag/v6/swap"

    # Common token mints
    SOL_MINT = "So11111111111111111111111111111111111111112"
    USDC_MINT = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"

    def __init__(
        self,
        rpc_url: Optional[str] = None,
        helius_api_key: Optional[str] = None,
    ):
        """
        Initialize Jupiter API client.

        Args:
            rpc_url: Solana RPC URL (defaults to SOLANA_RPC_URL env var)
            helius_api_key: Helius API key for priority fee estimation
                           (defaults to HELIUS_API_KEY env var)
        """
        self.rpc_url = rpc_url or os.environ.get(
            "SOLANA_RPC_URL",
            "https://api.mainnet-beta.solana.com"
        )

        # Helius configuration for priority fee estimation
        self._helius_api_key = helius_api_key or os.environ.get("HELIUS_API_KEY")
        self._helius_url = None
        if self._helius_api_key:
            self._helius_url = HELIUS_RPC_URL.format(api_key=self._helius_api_key)

        self._client = None
        self._helius_client = None
        self._initialize_client()

    def _initialize_client(self):
        """Initialize HTTP clients lazily."""
        try:
            import httpx
            self._client = httpx.AsyncClient(
                timeout=30.0,
                headers={
                    "Content-Type": "application/json",
                    "User-Agent": "Jarvis/1.0",
                },
            )

            # Initialize Helius client if API key is available
            if self._helius_url:
                self._helius_client = httpx.AsyncClient(
                    timeout=10.0,
                    headers={
                        "Content-Type": "application/json",
                        "User-Agent": "Jarvis/1.0",
                    },
                )
        except ImportError:
            logger.warning("httpx not installed, JupiterAPI will not work")

    async def get_quote(
        self,
        input_mint: str,
        output_mint: str,
        amount: int,
        slippage_bps: int = 100,
        only_direct_routes: bool = False,
    ) -> Optional[Dict[str, Any]]:
        """
        Get a swap quote from Jupiter.

        Args:
            input_mint: Input token mint address
            output_mint: Output token mint address
            amount: Amount in smallest unit (lamports for SOL)
            slippage_bps: Slippage tolerance in basis points (100 = 1%)
            only_direct_routes: If True, only use direct swap routes

        Returns:
            Quote dict or None on error
        """
        if not self._client:
            return None

        try:
            params = {
                "inputMint": input_mint,
                "outputMint": output_mint,
                "amount": str(amount),
                "slippageBps": slippage_bps,
            }

            if only_direct_routes:
                params["onlyDirectRoutes"] = "true"

            response = await self._client.get(
                f"{self.BASE_URL}/quote",
                params=params,
            )
            response.raise_for_status()
            data = response.json()

            return {
                "inputMint": data.get("inputMint"),
                "outputMint": data.get("outputMint"),
                "inAmount": data.get("inAmount"),
                "outAmount": data.get("outAmount"),
                "otherAmountThreshold": data.get("otherAmountThreshold"),
                "priceImpactPct": data.get("priceImpactPct"),
                "routePlan": data.get("routePlan", []),
                "slippageBps": slippage_bps,
                # Keep full response for execute_swap
                "_raw": data,
            }

        except Exception as e:
            logger.error(f"Jupiter quote failed: {e}")
            return None

    async def get_priority_fee_estimate(
        self,
        account_keys: Optional[List[str]] = None,
        priority_level: Optional[str] = None,
        max_lamports: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Get priority fee estimate from Helius API.

        Uses the Helius getPriorityFeeEstimate method for dynamic fee estimation
        based on current network conditions.

        Args:
            account_keys: Optional list of account addresses to consider
                         (e.g., Jupiter program, token mints)
            priority_level: Priority level (min, low, medium, high, veryHigh)
            max_lamports: Maximum fee cap in lamports

        Returns:
            Dict with priorityFeeEstimate and priorityFeeLevels
        """
        max_lamports = max_lamports or DEFAULT_MAX_PRIORITY_FEE_LAMPORTS

        # Fallback response if Helius is unavailable
        fallback = {
            "priorityFeeEstimate": DEFAULT_PRIORITY_FEE,
            "priorityFeeLevels": {
                "min": 1000,
                "low": 10000,
                "medium": DEFAULT_PRIORITY_FEE,
                "high": 100000,
                "veryHigh": 500000,
            },
        }

        # If no Helius client, return fallback
        if not self._helius_client or not self._helius_url:
            logger.debug("Helius not configured, using fallback priority fees")
            return fallback

        try:
            # Build Helius getPriorityFeeEstimate request
            params: Dict[str, Any] = {}

            if account_keys:
                params["accountKeys"] = account_keys

            if priority_level:
                params["options"] = {"priorityLevel": priority_level}

            payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "getPriorityFeeEstimate",
                "params": [params] if params else [{}],
            }

            response = await self._helius_client.post(
                self._helius_url,
                json=payload,
            )

            if response.status_code != 200:
                logger.warning(f"Helius returned HTTP {response.status_code}, using fallback")
                return fallback

            data = response.json()

            if "error" in data:
                logger.warning(f"Helius error: {data['error']}, using fallback")
                return fallback

            result = data.get("result", {})

            # Extract fee estimate
            priority_fee = result.get("priorityFeeEstimate", DEFAULT_PRIORITY_FEE)
            fee_levels = result.get("priorityFeeLevels", fallback["priorityFeeLevels"])

            # Apply max lamports cap
            priority_fee = min(priority_fee, max_lamports)
            if fee_levels:
                fee_levels = {
                    level: min(fee, max_lamports)
                    for level, fee in fee_levels.items()
                }

            return {
                "priorityFeeEstimate": priority_fee,
                "priorityFeeLevels": fee_levels,
                "recommended": priority_fee,
            }

        except Exception as e:
            logger.error(f"Helius priority fee estimation failed: {e}")
            return fallback

    async def execute_swap(
        self,
        quote: Dict[str, Any],
        user_public_key: str,
        wrap_unwrap_sol: bool = True,
        priority_level: Optional[str] = None,
        max_priority_fee_lamports: Optional[int] = None,
        use_dynamic_fees: bool = True,
        simulate: bool = False,
    ) -> Dict[str, Any]:
        """
        Execute a swap using a quote.

        Args:
            quote: Quote dict from get_quote()
            user_public_key: User's wallet public key
            wrap_unwrap_sol: Auto wrap/unwrap SOL
            priority_level: Priority level for fees (min, low, medium, high, veryHigh)
                           Defaults to "high" for trading transactions
            max_priority_fee_lamports: Maximum priority fee cap in lamports
                                       Prevents runaway costs during congestion
            use_dynamic_fees: Whether to use dynamic fee estimation (default: True)
                             If False, falls back to Jupiter's "auto" mode
            simulate: If True, simulate the transaction before returning it
                     This detects honeypots and provides accurate CU estimates

        Returns:
            Result dict with success, signature, or error
            If simulate=True, includes:
            - simulation: Dict with simulation results
            - compute_units_estimate: CU estimate with 10% buffer
        """
        if not self._client:
            return {"success": False, "error": "HTTP client not initialized"}

        try:
            # Get raw quote data
            raw_quote = quote.get("_raw", quote)

            # Build swap request
            swap_request: Dict[str, Any] = {
                "quoteResponse": raw_quote,
                "userPublicKey": user_public_key,
                "wrapAndUnwrapSol": wrap_unwrap_sol,
                "dynamicComputeUnitLimit": True,
            }

            # Configure priority fees
            if use_dynamic_fees and (self._helius_client or priority_level or max_priority_fee_lamports):
                # Use dynamic priority fees via Helius
                level = priority_level or PriorityLevel.HIGH.value
                max_fee = max_priority_fee_lamports or DEFAULT_MAX_PRIORITY_FEE_LAMPORTS

                # Get fee estimate from Helius
                fee_estimate = await self.get_priority_fee_estimate(
                    priority_level=level,
                    max_lamports=max_fee,
                )

                # Use Jupiter's priorityLevelWithMaxLamports format
                # This tells Jupiter to use the specified priority level
                # but cap the fee at maxLamports
                swap_request["priorityLevelWithMaxLamports"] = {
                    "priorityLevel": level,
                    "maxLamports": max_fee,
                }

                logger.debug(
                    f"Using dynamic priority fee: level={level}, "
                    f"estimate={fee_estimate.get('priorityFeeEstimate')}, max={max_fee}"
                )
            else:
                # Fall back to Jupiter's auto mode
                swap_request["prioritizationFeeLamports"] = "auto"

            response = await self._client.post(
                self.SWAP_URL,
                json=swap_request,
            )
            response.raise_for_status()
            data = response.json()

            # Get the swap transaction
            swap_tx = data.get("swapTransaction")
            if not swap_tx:
                return {"success": False, "error": "No swap transaction returned"}

            # Simulate transaction if requested
            simulation_result = None
            compute_units_estimate = None

            if simulate:
                simulation_result = await self.simulate_transaction(swap_tx)

                # Check for honeypot/rug detection
                if simulation_result.get("is_honeypot"):
                    return {
                        "success": False,
                        "error": f"Honeypot detected: {simulation_result.get('error')}",
                        "simulation": simulation_result,
                    }

                if simulation_result.get("is_potential_rug"):
                    return {
                        "success": False,
                        "error": f"Potential rug detected: {simulation_result.get('error')}",
                        "simulation": simulation_result,
                    }

                # Check if simulation itself failed
                if not simulation_result.get("success"):
                    return {
                        "success": False,
                        "error": f"Simulation failed: {simulation_result.get('error')}",
                        "simulation": simulation_result,
                    }

                compute_units_estimate = simulation_result.get("compute_units_with_buffer")

            # Build result
            result = {
                "success": True,
                "swap_transaction": swap_tx,
                "last_valid_block_height": data.get("lastValidBlockHeight"),
                "in_amount": quote.get("inAmount"),
                "out_amount": quote.get("outAmount"),
                "source": "jupiter",
                "priority_level": priority_level if use_dynamic_fees else "auto",
            }

            # Add simulation results if available
            if simulate and simulation_result:
                result["simulation"] = simulation_result
                result["compute_units_estimate"] = compute_units_estimate

            return result

        except Exception as e:
            logger.error(f"Jupiter swap execution failed: {e}")
            return {
                "success": False,
                "error": str(e),
            }

    async def _sign_and_send(
        self,
        swap_transaction: str,
        wallet: Any,
    ) -> Dict[str, Any]:
        """
        Sign and send a swap transaction.

        This is a placeholder - actual implementation depends on wallet type.

        Args:
            swap_transaction: Base64-encoded transaction
            wallet: Wallet object with sign capability

        Returns:
            Result dict with success and signature
        """
        # This would be implemented by the caller using their wallet
        return {
            "success": False,
            "error": "Transaction signing not implemented - use execute_swap and sign externally",
        }

    async def get_token_price(
        self,
        token_mint: str,
        vs_token: str = None,
    ) -> Optional[float]:
        """
        Get token price via Jupiter price API.

        Args:
            token_mint: Token mint address
            vs_token: Quote token (defaults to USDC)

        Returns:
            Price as float or None
        """
        if not self._client:
            return None

        vs_token = vs_token or self.USDC_MINT

        try:
            response = await self._client.get(
                "https://price.jup.ag/v6/price",
                params={
                    "ids": token_mint,
                    "vsToken": vs_token,
                },
            )
            response.raise_for_status()
            data = response.json()

            token_data = data.get("data", {}).get(token_mint, {})
            return token_data.get("price")

        except Exception as e:
            logger.error(f"Failed to get token price: {e}")
            return None

    async def get_token_info(self, mint: str) -> Optional[Dict[str, Any]]:
        """
        Get token info from Jupiter token list.

        Args:
            mint: Token mint address

        Returns:
            Token info dict or None
        """
        if not self._client:
            return None

        try:
            # Try strict list first
            response = await self._client.get(
                "https://token.jup.ag/strict",
            )
            response.raise_for_status()
            tokens = response.json()

            for token in tokens:
                if token.get("address") == mint:
                    return {
                        "address": token.get("address"),
                        "symbol": token.get("symbol"),
                        "name": token.get("name"),
                        "decimals": token.get("decimals", 9),
                        "logo_uri": token.get("logoURI"),
                    }

            return None

        except Exception as e:
            logger.error(f"Failed to get token info: {e}")
            return None

    async def close(self):
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
        if self._helius_client:
            await self._helius_client.aclose()

    async def simulate_transaction(
        self,
        transaction: str,
    ) -> Dict[str, Any]:
        """
        Simulate a transaction before submission using Solana RPC.

        This method provides preflight checks to:
        1. Detect honeypots and rug pulls from simulation errors
        2. Extract actual compute unit consumption
        3. Add 10% buffer to CU estimate for reliable execution

        Args:
            transaction: Base64-encoded transaction string

        Returns:
            Dict with simulation results:
            {
                "success": bool,
                "compute_units": int,
                "compute_units_with_buffer": int,  # CU + 10% buffer
                "logs": list[str],
                "error": str | None,
                "is_honeypot": bool,
                "is_potential_rug": bool,
            }
        """
        if not self._client:
            return {
                "success": False,
                "compute_units": 0,
                "compute_units_with_buffer": 0,
                "logs": [],
                "error": "HTTP client not initialized",
                "is_honeypot": False,
                "is_potential_rug": False,
            }

        try:
            # Call Solana RPC simulateTransaction
            response = await self._client.post(
                self.rpc_url,
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "simulateTransaction",
                    "params": [
                        transaction,
                        {
                            "encoding": "base64",
                            "commitment": "confirmed",
                            "replaceRecentBlockhash": True,
                        }
                    ]
                }
            )
            data = await response.json()

            # Handle RPC error response
            if "error" in data:
                error_msg = data["error"].get("message", str(data["error"]))
                return {
                    "success": False,
                    "compute_units": 0,
                    "compute_units_with_buffer": 0,
                    "logs": [],
                    "error": error_msg,
                    "is_honeypot": False,
                    "is_potential_rug": False,
                }

            result = data.get("result", {})
            value = result.get("value", {})
            logs = value.get("logs", [])
            err = value.get("err")

            # Extract compute units (from response or parse from logs)
            compute_units = value.get("unitsConsumed", 0)
            if not compute_units:
                compute_units = self._parse_cu_from_logs(logs)

            # Add 10% buffer for reliable execution
            compute_units_with_buffer = int(compute_units * 1.1)

            # Check for simulation error
            if err:
                # Analyze logs for honeypot/rug patterns
                is_honeypot = self._detect_honeypot(logs)
                is_potential_rug = self._detect_rug(logs)

                error_msg = str(err)
                if is_honeypot:
                    error_msg = f"Honeypot detected: {err}"
                elif is_potential_rug:
                    error_msg = f"Potential rug detected (slippage manipulation): {err}"

                return {
                    "success": False,
                    "compute_units": compute_units,
                    "compute_units_with_buffer": compute_units_with_buffer,
                    "logs": logs,
                    "error": error_msg,
                    "is_honeypot": is_honeypot,
                    "is_potential_rug": is_potential_rug,
                }

            # Simulation succeeded
            return {
                "success": True,
                "compute_units": compute_units,
                "compute_units_with_buffer": compute_units_with_buffer,
                "logs": logs,
                "error": None,
                "is_honeypot": False,
                "is_potential_rug": False,
            }

        except Exception as e:
            logger.error(f"Transaction simulation failed: {e}")
            return {
                "success": False,
                "compute_units": 0,
                "compute_units_with_buffer": 0,
                "logs": [],
                "error": str(e),
                "is_honeypot": False,
                "is_potential_rug": False,
            }

    def _parse_cu_from_logs(self, logs: List[str]) -> int:
        """
        Parse compute units consumed from simulation logs.

        Solana programs log CU consumption like:
        "Program XYZ consumed 12345 of 200000 compute units"

        Args:
            logs: List of log strings from simulation

        Returns:
            Compute units consumed, or 0 if not found
        """
        cu_pattern = re.compile(
            r"consumed\s+(\d+)\s+of\s+\d+\s+compute\s+units", re.IGNORECASE
        )

        max_cu = 0
        for log in logs:
            match = cu_pattern.search(log)
            if match:
                cu = int(match.group(1))
                max_cu = max(max_cu, cu)

        return max_cu

    def _detect_honeypot(self, logs: List[str]) -> bool:
        """
        Detect honeypot patterns in simulation logs.

        Common honeypot patterns:
        - "transfer blocked"
        - "transfer not allowed"
        - "trading disabled"
        - "blacklisted"

        Args:
            logs: List of log strings from simulation

        Returns:
            True if honeypot pattern detected
        """
        logs_text = " ".join(logs).lower()
        for pattern in HONEYPOT_PATTERNS:
            if re.search(pattern, logs_text, re.IGNORECASE):
                return True
        return False

    def _detect_rug(self, logs: List[str]) -> bool:
        """
        Detect potential rug patterns in simulation logs.

        Common rug patterns:
        - Slippage tolerance exceeded with extreme amounts
        - Output amount is 0 or 1

        Args:
            logs: List of log strings from simulation

        Returns:
            True if rug pattern detected
        """
        logs_text = " ".join(logs).lower()
        for pattern in RUG_PATTERNS:
            if re.search(pattern, logs_text, re.IGNORECASE):
                return True
        return False


# Singleton instance
_jupiter_api: Optional[JupiterAPI] = None


def get_jupiter_api() -> JupiterAPI:
    """Get singleton JupiterAPI instance."""
    global _jupiter_api
    if _jupiter_api is None:
        _jupiter_api = JupiterAPI()
    return _jupiter_api
