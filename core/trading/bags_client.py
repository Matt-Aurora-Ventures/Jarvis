"""
Bags.fm API Client

Client for Bags.fm API trading operations.
Used for copy trading and partner fee collection.

Prompt #165: Bags API Client
"""

import asyncio
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, List, Any
from enum import Enum
import json

logger = logging.getLogger(__name__)


class SwapStatus(str, Enum):
    """Swap transaction status"""
    PENDING = "pending"
    CONFIRMED = "confirmed"
    FAILED = "failed"


@dataclass
class SwapResult:
    """Result of a swap operation"""
    success: bool
    tx_hash: Optional[str] = None
    from_token: str = ""
    to_token: str = ""
    from_amount: float = 0.0
    to_amount: float = 0.0
    price: float = 0.0
    fee_paid: float = 0.0
    partner_fee: float = 0.0
    slippage: float = 0.0
    status: SwapStatus = SwapStatus.PENDING
    error: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class TokenInfo:
    """Token information from Bags API"""
    address: str
    symbol: str
    name: str
    decimals: int
    price_usd: float
    price_sol: float
    volume_24h: float
    liquidity: float
    holders: int
    market_cap: float


@dataclass
class Quote:
    """Swap quote from Bags API"""
    from_token: str
    to_token: str
    from_amount: float
    to_amount: float
    price: float
    price_impact: float
    fee: float
    route: List[str]
    expires_at: datetime
    quote_id: str


class BagsAPIClient:
    """
    Client for Bags.fm API

    Handles trading operations securely.
    Partner integration for fee sharing.
    """

    BASE_URL = "https://public-api-v2.bags.fm/api/v1"

    def __init__(
        self,
        api_key: Optional[str] = None,
        partner_key: Optional[str] = None
    ):
        self.api_key = api_key or os.environ.get("BAGS_API_KEY")
        self.partner_key = partner_key or os.environ.get("BAGS_PARTNER_KEY")
        if not self.api_key or not self.partner_key:
            try:
                from core.secrets import get_key
                if not self.api_key:
                    self.api_key = (
                        get_key("bags_api_key", "BAGS_API_KEY")
                        or get_key("bags_key", "BAGS_API_KEY")
                    )
                if not self.partner_key:
                    self.partner_key = (
                        get_key("bags_partner_key", "BAGS_PARTNER_KEY")
                        or get_key("bags_partner", "BAGS_PARTNER_KEY")
                    )
            except Exception:
                pass
        self.client = None
        self._initialize_client()
        self._warned_no_api_key = False

        # Rate limiting
        self.requests_per_minute = 60
        self.request_timestamps: List[datetime] = []

        # Tracking
        self.total_volume = 0.0
        self.total_partner_fees = 0.0
        self.successful_swaps = 0
        self.failed_swaps = 0

    def _initialize_client(self):
        """Initialize HTTP client"""
        try:
            import httpx
            self.client = httpx.AsyncClient(
                timeout=30.0,
                headers={
                    "Content-Type": "application/json",
                    "User-Agent": "Jarvis/1.0"
                }
            )
            logger.info("Bags API client initialized")
        except ImportError:
            logger.warning("httpx not installed, Bags client will not work")

    async def _check_rate_limit(self):
        """Check and enforce rate limiting"""
        now = datetime.now()

        # Remove old timestamps
        self.request_timestamps = [
            ts for ts in self.request_timestamps
            if (now - ts).seconds < 60
        ]

        if len(self.request_timestamps) >= self.requests_per_minute:
            wait_time = 60 - (now - self.request_timestamps[0]).seconds
            logger.warning(f"Rate limit reached, waiting {wait_time}s")
            await asyncio.sleep(wait_time)

        self.request_timestamps.append(now)

    def _get_headers(self) -> Dict[str, str]:
        """Get request headers with auth"""
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["x-api-key"] = self.api_key
        return headers

    def _warn_missing_api_key(self, feature: str) -> None:
        if self._warned_no_api_key:
            return
        logger.warning("Bags API key not configured; %s disabled", feature)
        self._warned_no_api_key = True

    async def get_quote(
        self,
        from_token: str,
        to_token: str,
        amount: float,
        slippage_bps: int = 100  # 1%
    ) -> Optional[Quote]:
        """
        Get swap quote without executing

        Args:
            from_token: Input token mint address (base58)
            to_token: Output token mint address (base58)
            amount: Amount in SOL (will be converted to lamports)
            slippage_bps: Slippage in basis points (100 = 1%)

        Returns:
            Quote object or None if failed
        """

        if not self.client:
            logger.error("HTTP client not initialized")
            return None

        await self._check_rate_limit()

        try:
            # Convert SOL to lamports (1 SOL = 1_000_000_000 lamports)
            # For SOL mint, decimals = 9
            amount_lamports = int(amount * 1_000_000_000)

            response = await self.client.get(
                f"{self.BASE_URL}/trade/quote",  # FIXED: was /quote, now /trade/quote
                params={
                    "inputMint": from_token,  # FIXED: was "from"
                    "outputMint": to_token,    # FIXED: was "to"
                    "amount": str(amount_lamports),  # FIXED: now in lamports
                    "slippageMode": "manual",  # ADDED: required for slippageBps
                    "slippageBps": slippage_bps
                },
                headers=self._get_headers()
            )

            response.raise_for_status()
            result = response.json()

            if not result.get("success"):
                logger.error(f"Quote API returned error: {result.get('error')}")
                return None

            data = result.get("response", {})

            return Quote(
                from_token=from_token,
                to_token=to_token,
                from_amount=amount,
                to_amount=float(data.get("outAmount", 0)) / 1_000_000,  # Convert from micro-USDC to USDC
                price=float(data.get("outAmount", 0)) / float(data.get("inAmount", 1)),  # Calculate price
                price_impact=float(data.get("priceImpactPct", 0)),  # FIXED: was priceImpact
                fee=0.0,  # Fee is included in the route, calculate separately if needed
                route=data.get("routePlan", []),  # FIXED: was route
                expires_at=datetime.now(),
                quote_id=data.get("requestId", "")  # FIXED: was quoteId
            )

        except Exception as e:
            logger.error(f"Failed to get quote: {e}")
            return None

    async def get_quote_raw(
        self,
        from_token: str,
        to_token: str,
        amount: float,
        slippage_bps: int = 100
    ) -> Optional[Dict[str, Any]]:
        """
        Get raw quote response from bags.fm API.
        Returns the full response object needed for swap execution.
        """
        if not self.client:
            return None

        await self._check_rate_limit()

        try:
            # Convert SOL to lamports
            amount_lamports = int(amount * 1_000_000_000)

            response = await self.client.get(
                f"{self.BASE_URL}/trade/quote",
                params={
                    "inputMint": from_token,
                    "outputMint": to_token,
                    "amount": str(amount_lamports),
                    "slippageMode": "manual",
                    "slippageBps": slippage_bps
                },
                headers=self._get_headers()
            )

            try:
                response.raise_for_status()
            except Exception as http_exc:
                body = None
                try:
                    body = response.text
                except Exception:
                    body = None
                if body and len(body) > 1200:
                    body = body[:1200] + "…"
                logger.error(
                    "Bags quote HTTP %s: %s",
                    getattr(response, "status_code", "?"),
                    body or str(http_exc),
                )
                raise

            result = response.json()

            if not result.get("success"):
                logger.error(f"Quote API returned error: {result.get('error')}")
                return None

            return result.get("response")

        except Exception as e:
            logger.error(f"Failed to get raw quote: {e}")
            return None

    async def swap(
        self,
        from_token: str,
        to_token: str,
        amount: float,
        wallet_address: str,
        slippage_bps: int = 100,
        keypair_path: Optional[str] = None,
        keypair: Optional[Any] = None  # Solders Keypair object for user wallets
    ) -> SwapResult:
        """
        Execute a swap via bags.fm API.

        Flow:
        1. Get quote with full response
        2. Request swap transaction from API
        3. Sign transaction with keypair
        4. Send to Solana RPC

        Args:
            from_token: Input token mint (SOL = So11111111111111111111111111111111111111112)
            to_token: Output token mint
            amount: Amount in SOL (e.g., 0.01 for 0.01 SOL)
            wallet_address: Wallet public key (user's or treasury)
            slippage_bps: Slippage in basis points (100 = 1%)
            keypair_path: Path to keypair JSON (encrypted) - used if keypair not provided
            keypair: Solders Keypair object - preferred for user wallets
        """
        if not self.client:
            return SwapResult(
                success=False,
                error="HTTP client not initialized"
            )

        await self._check_rate_limit()

        try:
            # Step 1: Get raw quote response
            quote_response = await self.get_quote_raw(from_token, to_token, amount, slippage_bps)

            if not quote_response:
                return SwapResult(
                    success=False,
                    from_token=from_token,
                    to_token=to_token,
                    from_amount=amount,
                    error="Failed to get quote from bags.fm"
                )

            logger.info(f"Got quote: {amount} SOL -> {int(quote_response.get('outAmount', 0)) / 1e9:.6f} tokens")

            # Step 2: Request swap transaction from API
            swap_request = {
                "userPublicKey": wallet_address,
                "quoteResponse": quote_response
            }

            response = await self.client.post(
                f"{self.BASE_URL}/trade/swap",
                json=swap_request,
                headers=self._get_headers()
            )

            try:
                response.raise_for_status()
            except Exception as http_exc:
                # Surface the body for debugging (bags.fm often returns a helpful JSON error).
                body = None
                try:
                    body = response.text
                except Exception:
                    body = None
                if body and len(body) > 1200:
                    body = body[:1200] + "…"
                logger.error(
                    "Bags swap HTTP %s: %s",
                    getattr(response, "status_code", "?"),
                    body or str(http_exc),
                )
                raise

            swap_result = response.json()

            if not swap_result.get("success"):
                return SwapResult(
                    success=False,
                    from_token=from_token,
                    to_token=to_token,
                    from_amount=amount,
                    error=f"Swap API error: {swap_result.get('response', 'Unknown')}"
                )

            swap_tx_base58 = swap_result.get("response", {}).get("swapTransaction")
            if not swap_tx_base58:
                return SwapResult(
                    success=False,
                    from_token=from_token,
                    to_token=to_token,
                    from_amount=amount,
                    error="No swap transaction returned from API"
                )

            logger.info(f"Got swap transaction from bags.fm API")

            # Step 3: Sign and send transaction
            tx_signature = await self._sign_and_send_transaction(
                swap_tx_base58,
                keypair_path or os.path.join(os.path.dirname(__file__), "../../data/treasury_keypair.json"),
                keypair=keypair  # Pass user keypair if provided
            )

            if not tx_signature:
                return SwapResult(
                    success=False,
                    from_token=from_token,
                    to_token=to_token,
                    from_amount=amount,
                    error="Failed to sign/send transaction"
                )

            # Track success
            self.successful_swaps += 1
            self.total_volume += amount
            out_amount = int(quote_response.get("outAmount", 0)) / 1_000_000_000

            logger.info(f"Swap successful! TX: {tx_signature}")

            return SwapResult(
                success=True,
                tx_hash=tx_signature,
                from_token=from_token,
                to_token=to_token,
                from_amount=amount,
                to_amount=out_amount,
                price=out_amount / amount if amount > 0 else 0,
                fee_paid=float(quote_response.get("platformFee", {}).get("amount", 0)) / 1e9,
                partner_fee=0,  # Will be tracked separately
                slippage=float(quote_response.get("slippageBps", 0)) / 100,
                status=SwapStatus.CONFIRMED
            )

        except Exception as e:
            self.failed_swaps += 1
            logger.error(f"Swap failed: {e}")

            return SwapResult(
                success=False,
                from_token=from_token,
                to_token=to_token,
                from_amount=amount,
                error=str(e),
                status=SwapStatus.FAILED
            )

    async def _sign_and_send_transaction(
        self,
        tx_base58: str,
        keypair_path: str,
        keypair: Optional[Any] = None  # Solders Keypair object
    ) -> Optional[str]:
        """
        Sign a base58-encoded transaction and send to Solana via Jito for guaranteed inclusion.

        Args:
            tx_base58: Base58-encoded serialized transaction
            keypair_path: Path to encrypted treasury keypair (fallback if keypair not provided)
            keypair: Solders Keypair object (preferred for user wallets)

        Returns:
            Transaction signature or None on failure
        """
        try:
            import base58
            import base64
            from solders.transaction import VersionedTransaction
            from solders.keypair import Keypair as SoldersKeypair

            # Use provided keypair or load from path
            if keypair is None:
                keypair = await self._load_keypair(keypair_path)
                if not keypair:
                    logger.error("Failed to load keypair")
                    return None

            # Decode and deserialize transaction
            tx_bytes = base58.b58decode(tx_base58)
            tx = VersionedTransaction.from_bytes(tx_bytes)

            # Sign the transaction
            signed_tx = VersionedTransaction(tx.message, [keypair])
            signed_tx_bytes = bytes(signed_tx)
            
            # Get RPC endpoints
            helius_key = os.getenv("HELIUS_API_KEY")
            helius_rpc = f"https://mainnet.helius-rpc.com/?api-key={helius_key}" if helius_key else None
            jito_rpc = "https://mainnet.block-engine.jito.wtf/api/v1/transactions"
            
            # Try Jito first for guaranteed inclusion (with automatic priority fee)
            signature = None
            
            # Method 1: Jito block engine (best for landing transactions)
            try:
                jito_payload = {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "sendTransaction",
                    "params": [
                        base64.b64encode(signed_tx_bytes).decode(),
                        {"encoding": "base64", "skipPreflight": True}
                    ]
                }
                
                jito_response = await self.client.post(jito_rpc, json=jito_payload, timeout=10.0)
                jito_result = jito_response.json()
                
                if "result" in jito_result:
                    signature = jito_result["result"]
                    logger.info(f"Transaction sent via Jito: {signature}")
                elif "error" in jito_result:
                    logger.warning(f"Jito rejected transaction: {jito_result['error']}")
            except Exception as jito_err:
                logger.warning(f"Jito submission failed: {jito_err}")
            
            # Method 2: Helius RPC with retry (fallback)
            if not signature and helius_rpc:
                try:
                    helius_payload = {
                        "jsonrpc": "2.0",
                        "id": 1,
                        "method": "sendTransaction",
                        "params": [
                            base64.b64encode(signed_tx_bytes).decode(),
                            {"encoding": "base64", "skipPreflight": True, "maxRetries": 5}
                        ]
                    }
                    
                    helius_response = await self.client.post(helius_rpc, json=helius_payload)
                    helius_result = helius_response.json()
                    
                    if "result" in helius_result:
                        signature = helius_result["result"]
                        logger.info(f"Transaction sent via Helius: {signature}")
                    elif "error" in helius_result:
                        logger.error(f"Helius RPC error: {helius_result['error']}")
                        return None
                except Exception as helius_err:
                    logger.error(f"Helius submission failed: {helius_err}")
                    return None
            
            if not signature:
                logger.error("Failed to send transaction to any RPC")
                return None

            # Poll for confirmation (max 45 seconds for Jito landing)
            confirmation_rpc = helius_rpc or "https://api.mainnet-beta.solana.com"
            
            for attempt in range(45):
                try:
                    status_payload = {
                        "jsonrpc": "2.0",
                        "id": 1,
                        "method": "getSignatureStatuses",
                        "params": [[signature], {"searchTransactionHistory": True}]
                    }
                    status_response = await self.client.post(confirmation_rpc, json=status_payload)
                    status_result = status_response.json()
                    
                    statuses = status_result.get("result", {}).get("value", [])
                    if statuses and statuses[0] is not None:
                        status = statuses[0]
                        if status.get("err"):
                            err_msg = str(status['err'])
                            logger.error(f"Transaction failed on-chain: {err_msg}")
                            # Check for common errors
                            if "InsufficientFunds" in err_msg:
                                logger.error("Insufficient SOL for transaction fees")
                            elif "SlippageToleranceExceeded" in err_msg:
                                logger.error("Price moved too much - slippage exceeded")
                            return None
                        confirmation = status.get("confirmationStatus")
                        if confirmation in ["confirmed", "finalized"]:
                            logger.info(f"Transaction confirmed ({confirmation}): {signature}")
                            return signature
                except Exception as poll_err:
                    logger.warning(f"Confirmation poll error (attempt {attempt+1}): {poll_err}")
                
                await asyncio.sleep(1)
            
            # Check one more time with transaction history search
            try:
                final_check = {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "getTransaction",
                    "params": [signature, {"encoding": "json", "maxSupportedTransactionVersion": 0}]
                }
                final_response = await self.client.post(confirmation_rpc, json=final_check)
                final_result = final_response.json()
                
                if final_result.get("result"):
                    if final_result["result"].get("meta", {}).get("err") is None:
                        logger.info(f"Transaction landed (late confirmation): {signature}")
                        return signature
            except Exception:
                pass
            
            logger.error(f"Transaction not confirmed after 45s: {signature}")
            return None

        except ImportError as e:
            logger.error(f"Missing dependency for signing: {e}. Install: pip install solders base58")
            return None
        except Exception as e:
            logger.error(f"Failed to sign/send transaction: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None

    async def _load_keypair(self, keypair_path: str):
        """
        Load and decrypt treasury keypair.

        The keypair is encrypted with PyNaCl Argon2id.
        Password is loaded from TREASURY_PASSWORD or JARVIS_WALLET_PASSWORD env var.
        """
        def pad_base64(s):
            """Add padding to base64 string if needed."""
            return s + '=' * (4 - len(s) % 4) if len(s) % 4 else s

        try:
            import json
            import base64

            with open(keypair_path, 'r') as f:
                data = json.load(f)

            # Check if encrypted (PyNaCl Argon2id format)
            if "encrypted_key" in data and "salt" in data and "nonce" in data:
                # Try multiple password env vars
                password = os.getenv("TREASURY_PASSWORD") or os.getenv("JARVIS_WALLET_PASSWORD")
                if not password:
                    logger.error("TREASURY_PASSWORD or JARVIS_WALLET_PASSWORD not set - cannot decrypt keypair")
                    return None

                salt = base64.b64decode(pad_base64(data["salt"]))
                nonce = base64.b64decode(pad_base64(data["nonce"]))
                encrypted_key = base64.b64decode(pad_base64(data["encrypted_key"]))

                # Use PyNaCl Argon2id for decryption (matches run_treasury.py)
                try:
                    import nacl.secret
                    import nacl.pwhash

                    key = nacl.pwhash.argon2id.kdf(
                        nacl.secret.SecretBox.KEY_SIZE,
                        password.encode(),
                        salt,
                        opslimit=nacl.pwhash.argon2id.OPSLIMIT_MODERATE,
                        memlimit=nacl.pwhash.argon2id.MEMLIMIT_MODERATE,
                    )

                    box = nacl.secret.SecretBox(key)
                    decrypted = box.decrypt(encrypted_key, nonce)

                    from solders.keypair import Keypair
                    kp = Keypair.from_bytes(decrypted)
                    logger.info(f"Loaded treasury keypair: {str(kp.pubkey())[:8]}...")
                    return kp

                except ImportError:
                    logger.error("PyNaCl not installed. Install with: pip install pynacl")
                    return None

            # Unencrypted (legacy format - array of bytes)
            elif isinstance(data, list):
                from solders.keypair import Keypair
                return Keypair.from_bytes(bytes(data))

            else:
                logger.error(f"Unknown keypair format in {keypair_path}")
                return None

        except Exception as e:
            logger.error(f"Failed to load keypair: {e}")
            return None

    async def get_token_info(self, mint: str) -> Optional[TokenInfo]:
        """Get token information via Helius RPC

        NOTE: bags.fm API v1 does not provide a token info endpoint.
        Using Helius RPC as alternative (requires HELIUS_API_KEY in .env)
        """

        if not self.client:
            return None

        helius_api_key = os.getenv("HELIUS_API_KEY")
        if not helius_api_key:
            logger.warning("HELIUS_API_KEY not configured; cannot fetch token info")
            return None

        try:
            # Use Helius token metadata API
            helius_url = "https://api.helius.xyz/v0/token-metadata"
            response = await self.client.get(
                helius_url,
                params={"api-key": helius_api_key, "mint": mint}
            )

            response.raise_for_status()
            result = response.json()

            # Helius returns array of token metadata
            if not result or not isinstance(result, list) or len(result) == 0:
                logger.warning(f"Token metadata not found for mint: {mint}")
                return None

            data = result[0]  # First result
            metadata = data.get("onChainMetadata", {}).get("metadata", {})

            return TokenInfo(
                address=mint,
                symbol=data.get("symbol", metadata.get("symbol", "UNKNOWN")),
                name=data.get("name", metadata.get("name", "Unknown Token")),
                decimals=int(data.get("decimals", 9)),
                # Note: Helius doesn't provide price/volume - would need additional API
                price_usd=0.0,
                price_sol=0.0,
                volume_24h=0.0,
                liquidity=0.0,
                holders=0,
                market_cap=0.0
            )

        except Exception as e:
            status = getattr(getattr(e, "response", None), "status_code", None)
            if status == 404:
                logger.warning("Token not found via Helius: %s", mint)
            else:
                logger.error(f"Failed to get token info via Helius: {e}")
            return None

    async def get_trending_tokens(self, limit: int = 10, allow_public: bool = False) -> List[TokenInfo]:
        """Get trending tokens

        NOTE: bags.fm API v1 does not provide a trending tokens endpoint.
        This feature is deferred to V1.1. Returns empty list.

        To implement in future:
        - Build custom analytics from on-chain transaction volume data
        - Query bags.fm token launches and sort by recent activity
        - Integrate Bitquery or similar for trending analytics
        """

        logger.warning(
            "Trending tokens endpoint not available in bags.fm API v1 - "
            "returning empty list (feature deferred to V1.1)"
        )
        return []

    async def get_top_tokens_by_volume(self, limit: int = 15, allow_public: bool = False) -> List[TokenInfo]:
        """Get top tokens sorted by 24h volume"""

        if not self.client:
            return []
        if not self.api_key and not allow_public:
            self._warn_missing_api_key("top tokens by volume")
            return []

        await self._check_rate_limit()

        base_urls = [self.BASE_URL]
        env_url = os.environ.get("BAGS_API_URL")
        if env_url and env_url not in base_urls:
            base_urls.insert(0, env_url)
        for alt in (
            "https://api.bags.fm/api/v1",
            "https://public-api.bags.fm/api/v1",
            "https://public-api-v2.bags.fm/api/v1",
        ):
            if alt not in base_urls:
                base_urls.append(alt)

        last_error = None
        for base_url in base_urls:
            try:
                response = await self.client.get(
                    f"{base_url}/tokens/top",
                    params={"limit": limit, "sort": "volume24h"},
                    headers=self._get_headers(),
                )

                response.raise_for_status()
                data = response.json()

                tokens = []
                for token_data in data.get("tokens", [])[:limit]:
                    tokens.append(TokenInfo(
                        address=token_data.get("address", ""),
                        symbol=token_data.get("symbol", ""),
                        name=token_data.get("name", ""),
                        decimals=int(token_data.get("decimals", 9)),
                        price_usd=float(token_data.get("priceUsd", 0)),
                        price_sol=float(token_data.get("priceSol", 0)),
                        volume_24h=float(token_data.get("volume24h", 0)),
                        liquidity=float(token_data.get("liquidity", 0)),
                        holders=int(token_data.get("holders", 0)),
                        market_cap=float(token_data.get("marketCap", 0))
                    ))

                if tokens:
                    return tokens
            except Exception as e:
                last_error = e
                status = getattr(getattr(e, "response", None), "status_code", None)
                if status == 404:
                    logger.warning("Bags top tokens endpoint unavailable")
                else:
                    logger.error(f"Failed to get top tokens by volume: {e}")

        # Fallback: reuse trending tokens when the top endpoint is unavailable.
        try:
            trending = await self.get_trending_tokens(limit=limit)
            if trending:
                return sorted(
                    trending,
                    key=lambda t: getattr(t, "volume_24h", 0) or 0,
                    reverse=True,
                )
        except Exception as e:
            logger.warning(f"Top tokens fallback to trending failed: {e}")

        if last_error:
            logger.warning("Bags top tokens endpoint unavailable")
        return []

    async def claim_partner_fees(self) -> Dict[str, Any]:
        """Claim accumulated partner fees"""

        if not self.partner_key:
            return {"success": False, "error": "No partner key configured"}

        if not self.client:
            return {"success": False, "error": "HTTP client not initialized"}

        await self._check_rate_limit()

        try:
            response = await self.client.post(
                f"{self.BASE_URL}/partner/claim",
                json={"partnerKey": self.partner_key},
                headers=self._get_headers()
            )

            response.raise_for_status()
            result = response.json()

            return {
                "success": True,
                "amount_claimed": float(result.get("amountClaimed", 0)),
                "tx_hash": result.get("txHash"),
                "timestamp": datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Failed to claim partner fees: {e}")
            return {"success": False, "error": str(e)}

    async def get_partner_stats(self) -> Dict[str, Any]:
        """Get partner statistics

        Uses bags.fm API v1 endpoint: GET /fee-share/partner-config/stats
        """

        if not self.partner_key:
            return {"error": "No partner key configured"}

        if not self.client:
            return {"error": "HTTP client not initialized"}

        await self._check_rate_limit()

        try:
            response = await self.client.get(
                f"{self.BASE_URL}/fee-share/partner-config/stats",  # FIXED: correct API v1 path
                params={"partner": self.partner_key},  # FIXED: param name is "partner" not "partnerKey"
                headers=self._get_headers()
            )

            response.raise_for_status()
            result = response.json()

            # API v1 returns: {"success": true, "response": {"claimedFees": "...", "unclaimedFees": "..."}}
            if not result.get("success"):
                logger.error(f"Partner stats API returned error: {result.get('error')}")
                return {"error": result.get("error", "Unknown error")}

            data = result.get("response", {})
            return {
                "claimed_fees": int(data.get("claimedFees", 0)),  # In lamports
                "unclaimed_fees": int(data.get("unclaimedFees", 0)),  # In lamports
                # Legacy field mappings for backward compatibility
                "total_fees_earned": int(data.get("claimedFees", 0)),
                "pending_fees": int(data.get("unclaimedFees", 0))
            }

        except Exception as e:
            logger.error(f"Failed to get partner stats: {e}")
            return {"error": str(e)}

    def get_client_stats(self) -> Dict[str, Any]:
        """Get local client statistics"""
        return {
            "total_volume": self.total_volume,
            "total_partner_fees": self.total_partner_fees,
            "successful_swaps": self.successful_swaps,
            "failed_swaps": self.failed_swaps,
            "success_rate": (
                self.successful_swaps / (self.successful_swaps + self.failed_swaps)
                if (self.successful_swaps + self.failed_swaps) > 0
                else 0.0
            ),
            "requests_in_last_minute": len(self.request_timestamps)
        }

    async def close(self):
        """Close the HTTP client"""
        if self.client:
            await self.client.aclose()
            logger.info("Bags API client closed")


class BagsTradeRouter:
    """
    Trade router that uses Bags.fm with Jupiter fallback

    Provides resilient trading by falling back to Jupiter
    if Bags.fm is unavailable.
    """

    def __init__(
        self,
        bags_client: Optional[BagsAPIClient] = None,
        jupiter_client: Any = None,
        partner_id: str = "jarvis"
    ):
        self.bags = bags_client or BagsAPIClient()
        self.jupiter = jupiter_client
        self.partner_id = partner_id

        # Tracking
        self.bags_trades = 0
        self.jupiter_trades = 0
        self.total_volume = 0.0

    async def swap(
        self,
        wallet_address: str,
        from_token: str,
        to_token: str,
        amount: float,
        slippage_bps: int = 100,
        signed_transaction: Optional[bytes] = None
    ) -> SwapResult:
        """
        Execute swap through Bags.fm, falling back to Jupiter

        Prioritizes Bags.fm for partner fee collection.
        """

        # Try Bags.fm first
        try:
            result = await self.bags.swap(
                from_token=from_token,
                to_token=to_token,
                amount=amount,
                wallet_address=wallet_address,
                slippage_bps=slippage_bps,
                signed_transaction=signed_transaction
            )

            if result.success:
                self.bags_trades += 1
                self.total_volume += amount
                logger.info(f"Swap executed via Bags.fm: {result.tx_hash}")
                return result

        except Exception as e:
            logger.warning(f"Bags.fm swap failed, trying Jupiter: {e}")

        # Fallback to Jupiter
        if self.jupiter:
            try:
                result = await self._jupiter_swap(
                    wallet_address=wallet_address,
                    from_token=from_token,
                    to_token=to_token,
                    amount=amount,
                    slippage_bps=slippage_bps
                )

                if result.success:
                    self.jupiter_trades += 1
                    self.total_volume += amount
                    logger.info(f"Swap executed via Jupiter: {result.tx_hash}")
                    return result

            except Exception as e:
                logger.error(f"Jupiter swap also failed: {e}")

        return SwapResult(
            success=False,
            from_token=from_token,
            to_token=to_token,
            from_amount=amount,
            error="All swap routes failed"
        )

    async def _jupiter_swap(
        self,
        wallet_address: str,
        from_token: str,
        to_token: str,
        amount: float,
        slippage_bps: int
    ) -> SwapResult:
        """Execute swap via Jupiter"""

        if not self.jupiter:
            return SwapResult(
                success=False,
                error="Jupiter client not configured"
            )

        # Would implement Jupiter swap here
        # Placeholder for now
        return SwapResult(
            success=False,
            error="Jupiter swap not implemented"
        )

    def get_stats(self) -> Dict[str, Any]:
        """Get router statistics"""
        total_trades = self.bags_trades + self.jupiter_trades

        return {
            "total_volume": self.total_volume,
            "total_trades": total_trades,
            "bags_trades": self.bags_trades,
            "jupiter_trades": self.jupiter_trades,
            "bags_percentage": (
                self.bags_trades / total_trades * 100
                if total_trades > 0 else 0
            ),
            "partner_id": self.partner_id
        }


class SuccessFeeManager:
    """
    Success Fee Manager - 0.5% fee on profitable trades

    Integrates with Bags.fm for fee collection.
    Only charges fee on winning trades (positive PnL).
    """

    SUCCESS_FEE_PERCENT = 0.5  # 0.5% fee on winning trades

    def __init__(self, bags_client: Optional[BagsAPIClient] = None):
        self.bags = bags_client
        self.total_fees_collected = 0.0
        self.fee_transactions: List[Dict[str, Any]] = []

    def calculate_success_fee(
        self,
        entry_price: float,
        exit_price: float,
        amount_sol: float,
        token_symbol: str,
    ) -> Dict[str, Any]:
        """
        Calculate success fee for a closed trade.

        Only charges fee if trade was profitable.
        Returns fee details including amount and whether it applies.
        """
        # Calculate PnL
        pnl_percent = ((exit_price - entry_price) / entry_price) * 100 if entry_price > 0 else 0
        pnl_usd = amount_sol * (exit_price - entry_price) * 225  # Approximate SOL price

        # Only charge fee on profitable trades
        if pnl_percent <= 0 or pnl_usd <= 0:
            return {
                "applies": False,
                "reason": "Not a winning trade",
                "pnl_percent": pnl_percent,
                "pnl_usd": pnl_usd,
                "fee_amount": 0.0,
                "fee_percent": 0.0,
            }

        # Calculate fee (0.5% of profit)
        fee_amount = pnl_usd * (self.SUCCESS_FEE_PERCENT / 100)

        return {
            "applies": True,
            "token_symbol": token_symbol,
            "entry_price": entry_price,
            "exit_price": exit_price,
            "amount_sol": amount_sol,
            "pnl_percent": pnl_percent,
            "pnl_usd": pnl_usd,
            "fee_percent": self.SUCCESS_FEE_PERCENT,
            "fee_amount": fee_amount,
            "net_profit": pnl_usd - fee_amount,
            "timestamp": datetime.now().isoformat(),
        }

    async def collect_fee(
        self,
        fee_details: Dict[str, Any],
        wallet_address: str,
    ) -> Dict[str, Any]:
        """
        Collect the success fee via Bags.fm API.

        Returns collection result with transaction details.
        """
        if not fee_details.get("applies"):
            return {"success": False, "reason": "Fee does not apply"}

        fee_amount = fee_details.get("fee_amount", 0)
        if fee_amount <= 0:
            return {"success": False, "reason": "No fee to collect"}

        try:
            # Record fee collection
            fee_record = {
                "timestamp": datetime.now().isoformat(),
                "wallet": wallet_address,
                "token": fee_details.get("token_symbol"),
                "pnl_usd": fee_details.get("pnl_usd"),
                "fee_amount": fee_amount,
                "fee_percent": self.SUCCESS_FEE_PERCENT,
            }

            self.fee_transactions.append(fee_record)
            self.total_fees_collected += fee_amount

            # In production, this would transfer the fee via Bags API
            # For now, we track it locally
            logger.info(
                f"Success fee collected: ${fee_amount:.4f} on {fee_details.get('token_symbol')} "
                f"(${fee_details.get('pnl_usd'):.2f} profit)"
            )

            return {
                "success": True,
                "fee_amount": fee_amount,
                "total_collected": self.total_fees_collected,
                "transaction_count": len(self.fee_transactions),
            }

        except Exception as e:
            logger.error(f"Failed to collect success fee: {e}")
            return {"success": False, "error": str(e)}

    def get_fee_stats(self) -> Dict[str, Any]:
        """Get fee collection statistics."""
        return {
            "fee_percent": self.SUCCESS_FEE_PERCENT,
            "total_collected": self.total_fees_collected,
            "transaction_count": len(self.fee_transactions),
            "recent_fees": self.fee_transactions[-10:],
        }


# Singleton instances
_bags_clients: Dict[str, BagsAPIClient] = {}
_fee_managers: Dict[str, SuccessFeeManager] = {}


def get_bags_client(profile: Optional[str] = None) -> BagsAPIClient:
    """Get Bags API client singleton (optionally per profile)."""
    key = (profile or "default").strip().lower()
    if key not in _bags_clients:
        api_key = None
        partner_key = None
        if profile and key != "default":
            prefix = f"{key.upper()}_"
            api_key = os.environ.get(f"{prefix}BAGS_API_KEY") or os.environ.get("BAGS_API_KEY")
            partner_key = os.environ.get(f"{prefix}BAGS_PARTNER_KEY") or os.environ.get("BAGS_PARTNER_KEY")
        if not api_key or not partner_key:
            try:
                from core.secrets import get_key
                if not api_key:
                    api_key = (
                        get_key("bags_api_key", "BAGS_API_KEY")
                        or get_key("bags_key", "BAGS_API_KEY")
                    )
                if not partner_key:
                    partner_key = (
                        get_key("bags_partner_key", "BAGS_PARTNER_KEY")
                        or get_key("bags_partner", "BAGS_PARTNER_KEY")
                    )
            except Exception:
                pass
        _bags_clients[key] = BagsAPIClient(api_key=api_key, partner_key=partner_key)
    return _bags_clients[key]


def get_success_fee_manager(profile: Optional[str] = None) -> SuccessFeeManager:
    """Get Success Fee Manager singleton (optionally per profile)."""
    key = (profile or "default").strip().lower()
    if key not in _fee_managers:
        _fee_managers[key] = SuccessFeeManager(bags_client=get_bags_client(profile=profile))
    return _fee_managers[key]


# Testing
if __name__ == "__main__":
    async def test():
        client = BagsAPIClient()

        # Test get quote
        print("Getting quote...")
        quote = await client.get_quote(
            from_token="SOL",
            to_token="BONK",
            amount=0.1
        )
        if quote:
            print(f"Quote: {quote.from_amount} {quote.from_token} -> {quote.to_amount} {quote.to_token}")

        # Test get trending
        print("\nGetting trending tokens...")
        trending = await client.get_trending_tokens(limit=5)
        for token in trending:
            print(f"  {token.symbol}: ${token.price_usd:.6f}")

        # Print stats
        print(f"\nClient stats: {client.get_client_stats()}")

        await client.close()

    asyncio.run(test())

# Backwards compatibility alias
BagsClient = BagsAPIClient
