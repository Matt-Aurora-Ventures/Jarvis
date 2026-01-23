"""
Jupiter DEX API Client - Simplified wrapper

US-005: bags.fm + Jupiter Backup with TP/SL

This is a clean, focused API wrapper for Jupiter swap operations.
For the full-featured client with DCA and advanced features, see bots/treasury/jupiter.py
"""

import logging
import os
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


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

    def __init__(self, rpc_url: Optional[str] = None):
        """
        Initialize Jupiter API client.

        Args:
            rpc_url: Solana RPC URL (defaults to SOLANA_RPC_URL env var)
        """
        self.rpc_url = rpc_url or os.environ.get(
            "SOLANA_RPC_URL",
            "https://api.mainnet-beta.solana.com"
        )
        self._client = None
        self._initialize_client()

    def _initialize_client(self):
        """Initialize HTTP client lazily."""
        try:
            import httpx
            self._client = httpx.AsyncClient(
                timeout=30.0,
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

    async def execute_swap(
        self,
        quote: Dict[str, Any],
        user_public_key: str,
        wrap_unwrap_sol: bool = True,
    ) -> Dict[str, Any]:
        """
        Execute a swap using a quote.

        Args:
            quote: Quote dict from get_quote()
            user_public_key: User's wallet public key
            wrap_unwrap_sol: Auto wrap/unwrap SOL

        Returns:
            Result dict with success, signature, or error
        """
        if not self._client:
            return {"success": False, "error": "HTTP client not initialized"}

        try:
            # Get raw quote data
            raw_quote = quote.get("_raw", quote)

            swap_request = {
                "quoteResponse": raw_quote,
                "userPublicKey": user_public_key,
                "wrapAndUnwrapSol": wrap_unwrap_sol,
                "dynamicComputeUnitLimit": True,
                "prioritizationFeeLamports": "auto",
            }

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

            # The actual signing and sending needs to happen externally
            # This returns the transaction for the caller to sign
            return {
                "success": True,
                "swap_transaction": swap_tx,
                "last_valid_block_height": data.get("lastValidBlockHeight"),
                "in_amount": quote.get("inAmount"),
                "out_amount": quote.get("outAmount"),
                "source": "jupiter",
            }

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


# Singleton instance
_jupiter_api: Optional[JupiterAPI] = None


def get_jupiter_api() -> JupiterAPI:
    """Get singleton JupiterAPI instance."""
    global _jupiter_api
    if _jupiter_api is None:
        _jupiter_api = JupiterAPI()
    return _jupiter_api
