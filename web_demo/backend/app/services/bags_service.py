"""
Bags.fm API Integration Service
Connects to the bags-swap-api server for trading operations.

This uses the local Bags API proxy (from gitignore) which handles:
- Quote generation for swaps
- Transaction creation
- Service fee calculation (0.5% default)
- Popular token pairs
"""

import logging
import os
from typing import Dict, List, Optional, Any
import httpx
from datetime import datetime

logger = logging.getLogger(__name__)


class BagsService:
    """
    Client for bags-swap-api service.

    The bags-swap-api is a proxy server that wraps the Bags.fm SDK
    and provides a simple REST API for the web demo.
    """

    def __init__(self):
        # bags-swap-api server URL (from docker-compose or local)
        self.base_url = os.getenv(
            "BAGS_API_URL",
            "http://localhost:3000"  # Default local dev
        )
        self.api_key = os.getenv("BAGS_API_KEY")  # For admin endpoints
        self.timeout = 30.0

        logger.info(f"Bags service initialized: {self.base_url}")

    async def get_quote(
        self,
        input_mint: str,
        output_mint: str,
        amount: int,
        slippage_mode: str = "auto",
        slippage_bps: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Get a swap quote from Bags API.

        Args:
            input_mint: Input token mint address
            output_mint: Output token mint address
            amount: Input amount in smallest units (e.g., lamports for SOL)
            slippage_mode: "auto" or "fixed"
            slippage_bps: Basis points for fixed slippage (e.g., 50 = 0.5%)

        Returns:
            Quote data including output amount, route, fees, etc.

        Example:
            quote = await bags.get_quote(
                input_mint="So11111111111111111111111111111111111111112",  # SOL
                output_mint="EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",  # USDC
                amount=1_000_000_000,  # 1 SOL
                slippage_mode="fixed",
                slippage_bps=50  # 0.5%
            )
        """
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.post(
                    f"{self.base_url}/quote",
                    json={
                        "inputMint": input_mint,
                        "outputMint": output_mint,
                        "amount": str(amount),
                        "slippageMode": slippage_mode,
                        "slippageBps": slippage_bps
                    }
                )
                response.raise_for_status()
                quote_data = response.json()

                logger.info(
                    f"Quote: {amount} {input_mint[:8]}... -> "
                    f"{quote_data.get('outAmount', 'N/A')} {output_mint[:8]}..."
                )

                return quote_data

            except httpx.HTTPError as e:
                logger.error(f"Bags quote error: {e}")
                raise Exception(f"Failed to get swap quote: {str(e)}")

    async def create_swap_transaction(
        self,
        quote_response: Dict[str, Any],
        user_public_key: str
    ) -> Dict[str, Any]:
        """
        Create a swap transaction that the user can sign.

        Args:
            quote_response: The quote data from get_quote()
            user_public_key: User's Solana wallet public key

        Returns:
            Transaction data for the user to sign

        Example:
            tx_data = await bags.create_swap_transaction(
                quote_response=quote,
                user_public_key="9WzDXwBbmkg8ZTbNMqUxvQRAyrZzDsGYdLVL9zYtAWWM"
            )
            # User signs tx_data["swapTransaction"] with their wallet
        """
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.post(
                    f"{self.base_url}/swap",
                    json={
                        "quoteResponse": quote_response,
                        "userPublicKey": user_public_key
                    }
                )
                response.raise_for_status()
                swap_data = response.json()

                logger.info(f"Swap transaction created for {user_public_key[:8]}...")

                return swap_data

            except httpx.HTTPError as e:
                logger.error(f"Bags swap creation error: {e}")
                raise Exception(f"Failed to create swap transaction: {str(e)}")

    async def get_popular_tokens(self) -> List[Dict[str, Any]]:
        """
        Get list of popular tokens for UI suggestions.

        Returns:
            List of popular token pairs with metadata

        Example:
            tokens = await bags.get_popular_tokens()
            # [
            #     {"symbol": "SOL", "mint": "So1111...", "name": "Solana", "decimals": 9},
            #     {"symbol": "USDC", "mint": "EPjFW...", "name": "USD Coin", "decimals": 6},
            #     ...
            # ]
        """
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.get(f"{self.base_url}/tokens/popular")
                response.raise_for_status()
                tokens = response.json()

                logger.info(f"Retrieved {len(tokens)} popular tokens")

                return tokens

            except httpx.HTTPError as e:
                logger.error(f"Bags popular tokens error: {e}")
                # Return default list as fallback
                return [
                    {
                        "symbol": "SOL",
                        "mint": "So11111111111111111111111111111111111111112",
                        "name": "Solana",
                        "decimals": 9
                    },
                    {
                        "symbol": "USDC",
                        "mint": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
                        "name": "USD Coin",
                        "decimals": 6
                    }
                ]

    async def get_health(self) -> Dict[str, Any]:
        """
        Check if bags-swap-api service is healthy.

        Returns:
            Health status and service fee info
        """
        async with httpx.AsyncClient(timeout=5.0) as client:
            try:
                response = await client.get(f"{self.base_url}/health")
                response.raise_for_status()
                health = response.json()

                return {
                    "status": "healthy",
                    "service_fee": health.get("serviceFee", "0.5%"),
                    "timestamp": datetime.now().isoformat()
                }

            except httpx.HTTPError as e:
                logger.error(f"Bags health check failed: {e}")
                return {
                    "status": "unhealthy",
                    "error": str(e),
                    "timestamp": datetime.now().isoformat()
                }

    async def get_usage_stats(self) -> Optional[Dict[str, Any]]:
        """
        Get usage statistics (admin only).

        Requires BAGS_API_KEY environment variable.

        Returns:
            Usage stats including total swaps, volume, etc.
        """
        if not self.api_key:
            logger.warning("BAGS_API_KEY not set - cannot fetch admin stats")
            return None

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.get(
                    f"{self.base_url}/admin/stats",
                    headers={"x-admin-key": self.api_key}
                )
                response.raise_for_status()
                stats = response.json()

                logger.info(
                    f"Bags stats: {stats.get('totalSwaps', 0)} swaps, "
                    f"{stats.get('swapsLast24h', 0)} in last 24h"
                )

                return stats

            except httpx.HTTPError as e:
                logger.error(f"Bags stats error: {e}")
                return None


# Global instance
_bags_service: Optional[BagsService] = None


def get_bags_service() -> BagsService:
    """Get or create global Bags service instance."""
    global _bags_service
    if _bags_service is None:
        _bags_service = BagsService()
    return _bags_service
