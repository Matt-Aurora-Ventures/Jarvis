"""
Jupiter Aggregator Integration for Jarvis Treasury
Provides swap execution, quotes, and DCA functionality
"""

import os
import json
import asyncio
import aiohttp
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum

from core.resilience.retry import retry, JUPITER_QUOTE_RETRY, JUPITER_SWAP_RETRY
from core.security.tx_confirmation import (
    TransactionConfirmationService,
    CommitmentLevel,
    TransactionStatus,
    get_confirmation_service
)

logger = logging.getLogger(__name__)


class SwapMode(Enum):
    EXACT_IN = "ExactIn"    # Specify input amount
    EXACT_OUT = "ExactOut"  # Specify output amount


class SlippageMode(Enum):
    AUTO = "auto"
    FIXED = "fixed"


@dataclass
class TokenInfo:
    """Token information from Jupiter."""
    address: str
    symbol: str
    name: str
    decimals: int
    price_usd: float = 0.0
    logo_uri: str = ""

    @classmethod
    def from_dict(cls, data: Dict) -> 'TokenInfo':
        return cls(
            address=data.get('address', ''),
            symbol=data.get('symbol', 'UNKNOWN'),
            name=data.get('name', ''),
            decimals=data.get('decimals', 9),
            price_usd=data.get('price', 0.0),
            logo_uri=data.get('logoURI', '')
        )


@dataclass
class SwapQuote:
    """Quote for a token swap."""
    input_mint: str
    output_mint: str
    input_amount: int          # In lamports/smallest unit
    output_amount: int         # Expected output in smallest unit
    input_amount_ui: float     # Human readable
    output_amount_ui: float    # Human readable
    price_impact_pct: float
    slippage_bps: int
    fees_usd: float
    route_plan: List[Dict]
    quote_response: Dict       # Raw Jupiter response for execution

    @property
    def exchange_rate(self) -> float:
        """Get the exchange rate (output per input)."""
        if self.input_amount_ui > 0:
            return self.output_amount_ui / self.input_amount_ui
        return 0.0


@dataclass
class SwapResult:
    """Result of a swap execution."""
    success: bool
    signature: str = ""
    input_amount: float = 0.0
    output_amount: float = 0.0
    input_symbol: str = ""
    output_symbol: str = ""
    price_impact: float = 0.0
    fees_usd: float = 0.0
    error: str = ""
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            'success': self.success,
            'signature': self.signature,
            'input_amount': self.input_amount,
            'output_amount': self.output_amount,
            'input_symbol': self.input_symbol,
            'output_symbol': self.output_symbol,
            'price_impact': self.price_impact,
            'fees_usd': self.fees_usd,
            'error': self.error,
            'timestamp': self.timestamp
        }


class JupiterClient:
    """
    Jupiter Aggregator API client for Solana swaps.

    Features:
    - Best route discovery across all DEXs
    - Price quotes with slippage protection
    - Transaction building and simulation
    - Dynamic priority fee calculation (per guide recommendations)
    - Support for limit orders via DCA
    - Transaction confirmation with retry logic (per guide)
    """

    # Use lite-api for DNS resilience (works when quote-api DNS fails)
    JUPITER_API = "https://lite-api.jup.ag/swap/v1"
    JUPITER_API_FALLBACK = "https://quote-api.jup.ag/v6"
    JUPITER_PRICE_API = "https://price.jup.ag/v6"
    JUPITER_TOKEN_API = "https://token.jup.ag"
    DEXSCREENER_API = "https://api.dexscreener.com/latest"
    COINGECKO_SIMPLE_API = "https://api.coingecko.com/api/v3/simple/price"

    # Common token addresses
    SOL_MINT = "So11111111111111111111111111111111111111112"
    USDC_MINT = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
    USDT_MINT = "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB"

    # Priority fee configuration (per Solana Trading Bot Guide)
    DEFAULT_PRIORITY_FEE = 10000  # 10,000 micro lamports
    MIN_PRIORITY_FEE = 1000       # 1,000 micro lamports
    MAX_PRIORITY_FEE = 1000000    # 1,000,000 micro lamports (1 lamport/CU)

    # Transaction confirmation settings (per guide)
    TX_CONFIRM_TIMEOUT = 30  # seconds
    TX_MAX_RETRIES = 3
    TX_RETRY_DELAY = 2  # seconds between retries

    def __init__(self, rpc_url: str = None):
        """
        Initialize Jupiter client.

        Args:
            rpc_url: Solana RPC URL (defaults to env var or mainnet)
        """
        self.rpc_url = rpc_url or os.environ.get(
            'SOLANA_RPC_URL',
            'https://api.mainnet-beta.solana.com'
        )
        self._session: Optional[aiohttp.ClientSession] = None
        self._token_cache: Dict[str, TokenInfo] = {}
        self._recent_priority_fees: List[int] = []  # Track recent fees for dynamic calculation
        self._token_api_available: bool = True
        self._token_api_failure_logged: bool = False

        # Initialize transaction confirmation service
        self._confirmation_service: Optional[TransactionConfirmationService] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def close(self):
        """Close the client session."""
        if self._session and not self._session.closed:
            await self._session.close()
        if self._confirmation_service:
            await self._confirmation_service.close()

    def _get_confirmation_service(self) -> TransactionConfirmationService:
        """Get or create transaction confirmation service."""
        if self._confirmation_service is None:
            self._confirmation_service = TransactionConfirmationService(
                rpc_url=self.rpc_url,
                commitment=CommitmentLevel.CONFIRMED
            )
        return self._confirmation_service

    async def _fetch_dexscreener_pairs(self, mint: str) -> List[Dict]:
        """Fetch DexScreener pairs for a mint, filtered to Solana."""
        session = await self._get_session()
        base_url = os.environ.get("DEXSCREENER_API_URL", self.DEXSCREENER_API).rstrip("/")
        url = f"{base_url}/dex/tokens/{mint}"

        try:
            async with session.get(url) as resp:
                if resp.status != 200:
                    return []
                data = await resp.json()
                pairs = data.get("pairs") or []
                return [p for p in pairs if p.get("chainId") == "solana"]
        except Exception as e:
            logger.warning(f"DexScreener failed for {mint[:8]}...: {e}")
            return []

    @staticmethod
    def _pick_best_pair(pairs: List[Dict]) -> Optional[Dict]:
        """Pick the most liquid pair from DexScreener data."""
        if not pairs:
            return None

        def liquidity(pair: Dict) -> float:
            try:
                return float(pair.get("liquidity", {}).get("usd", 0) or 0)
            except (TypeError, ValueError):
                return 0.0

        return max(pairs, key=liquidity)

    @staticmethod
    def _pair_price_usd(pair: Dict) -> float:
        """Parse a USD price from a DexScreener pair."""
        raw = pair.get("priceUsd") or pair.get("price")
        try:
            return float(raw)
        except (TypeError, ValueError):
            return 0.0

    async def _fetch_coingecko_price(self, asset_id: str) -> float:
        """Fetch USD price for a CoinGecko asset id."""
        session = await self._get_session()
        try:
            async with session.get(
                self.COINGECKO_SIMPLE_API,
                params={"ids": asset_id, "vs_currencies": "usd"},
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return float(data.get(asset_id, {}).get("usd", 0) or 0)
        except Exception as e:
            logger.warning(f"CoinGecko failed for {asset_id}: {e}")
        return 0.0

    async def get_token_info(self, mint: str) -> Optional[TokenInfo]:
        """Get token information by mint address."""
        if mint in self._token_cache:
            return self._token_cache[mint]

        session = await self._get_session()
        token = None

        if self.JUPITER_TOKEN_API and self._token_api_available:
            try:
                async with session.get(
                    f"{self.JUPITER_TOKEN_API}/strict",
                    params={'mint': mint}
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if data:
                            token = TokenInfo.from_dict(data[0] if isinstance(data, list) else data)
                            self._token_cache[mint] = token
                            return token
            except aiohttp.ClientConnectorError as e:
                if not self._token_api_failure_logged:
                    logger.warning(
                        "Jupiter token API unreachable; skipping token list lookups (%s)",
                        e,
                    )
                    self._token_api_failure_logged = True
                self._token_api_available = False
            except aiohttp.ClientError as e:
                logger.warning(f"Jupiter token API error for {mint[:8]}...: {e}")
            except Exception as e:
                logger.warning(f"Jupiter token lookup failed for {mint[:8]}...: {e}")

        # Fallback: get from price API
        try:
            async with session.get(
                f"{self.JUPITER_PRICE_API}/price",
                params={'ids': mint}
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if mint in data.get('data', {}):
                        price_info = data['data'][mint]
                        token = TokenInfo(
                            address=mint,
                            symbol=price_info.get('mintSymbol', 'UNKNOWN'),
                            name=price_info.get('mintSymbol', ''),
                            decimals=9,
                            price_usd=price_info.get('price', 0)
                        )
                        self._token_cache[mint] = token
                        return token
        except Exception as e:
            logger.warning(f"Jupiter price API failed for {mint[:8]}...: {e}")

        # Fallback: Bags.fm token data
        try:
            from core.trading.bags_client import get_bags_client
            bags_client = get_bags_client()
            bags_token = await bags_client.get_token_info(mint)
            if bags_token:
                token = TokenInfo(
                    address=mint,
                    symbol=bags_token.symbol,
                    name=bags_token.name,
                    decimals=bags_token.decimals or 9,
                    price_usd=bags_token.price_usd,
                )
                self._token_cache[mint] = token
                return token
        except Exception as e:
            logger.warning(f"Bags token info fallback failed for {mint[:8]}...: {e}")

        # Fallback: DexScreener token data
        pairs = await self._fetch_dexscreener_pairs(mint)
        best = self._pick_best_pair(pairs)
        if best:
            base = best.get("baseToken", {}) or {}
            token = TokenInfo(
                address=mint,
                symbol=base.get("symbol", "UNKNOWN"),
                name=base.get("name", ""),
                decimals=9,
                price_usd=self._pair_price_usd(best),
                logo_uri=base.get("logoURI", ""),
            )
            self._token_cache[mint] = token
            return token

        # Fallback: known mints
        if mint == self.SOL_MINT:
            sol_price = await self._fetch_coingecko_price("solana")
            token = TokenInfo(
                address=mint,
                symbol="SOL",
                name="Solana",
                decimals=9,
                price_usd=sol_price,
            )
            self._token_cache[mint] = token
            return token

        if mint in (self.USDC_MINT, self.USDT_MINT):
            token = TokenInfo(
                address=mint,
                symbol="USDC" if mint == self.USDC_MINT else "USDT",
                name="USD Coin" if mint == self.USDC_MINT else "Tether USD",
                decimals=6,
                price_usd=1.0,
            )
            self._token_cache[mint] = token
            return token

        return None

    async def get_token_price(self, mint: str) -> float:
        """
        Get current token price in USD.

        Uses DexScreener as primary (more reliable) with Jupiter as fallback.
        Includes caching to reduce API spam.
        """
        # Check price cache (30 second TTL)
        cache_key = f"price_{mint}"
        if hasattr(self, '_price_cache'):
            cached = self._price_cache.get(cache_key)
            if cached:
                price, timestamp = cached
                if (datetime.utcnow() - timestamp).total_seconds() < 30:
                    return price
        else:
            self._price_cache = {}

        # Stablecoin fast path
        if mint in (self.USDC_MINT, self.USDT_MINT):
            return 1.0

        # SOL fast path via CoinGecko
        if mint == self.SOL_MINT:
            sol_price = await self._fetch_coingecko_price("solana")
            if sol_price > 0:
                self._price_cache[cache_key] = (sol_price, datetime.utcnow())
                return sol_price

        # PRIMARY: DexScreener (more reliable than Jupiter price API)
        pairs = await self._fetch_dexscreener_pairs(mint)
        best = self._pick_best_pair(pairs)
        if best:
            price = self._pair_price_usd(best)
            if price > 0:
                self._price_cache[cache_key] = (price, datetime.utcnow())
                return price

        # FALLBACK: Bags.fm price
        try:
            from core.trading.bags_client import get_bags_client
            bags_client = get_bags_client()
            bags_token = await bags_client.get_token_info(mint)
            if bags_token and bags_token.price_usd:
                price = float(bags_token.price_usd)
                self._price_cache[cache_key] = (price, datetime.utcnow())
                return price
        except Exception:
            pass

        # FALLBACK: Jupiter price API (only if DexScreener fails)
        session = await self._get_session()
        try:
            async with session.get(
                f"{self.JUPITER_PRICE_API}/price",
                params={'ids': mint},
                timeout=aiohttp.ClientTimeout(total=5)
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    price = data.get('data', {}).get(mint, {}).get('price', 0.0)
                    if price:
                        price = float(price)
                        self._price_cache[cache_key] = (price, datetime.utcnow())
                        return price
        except Exception:
            # Don't log - DexScreener already failed, Jupiter failing is expected
            pass

        return 0.0

    @retry(policy=JUPITER_QUOTE_RETRY)
    async def get_quote(
        self,
        input_mint: str,
        output_mint: str,
        amount: int,
        slippage_bps: int = 50,
        mode: SwapMode = SwapMode.EXACT_IN
    ) -> Optional[SwapQuote]:
        """
        Get a swap quote from Jupiter with automatic retry.

        Args:
            input_mint: Input token mint address
            output_mint: Output token mint address
            amount: Amount in smallest unit (lamports for SOL)
            slippage_bps: Slippage tolerance in basis points (50 = 0.5%)
            mode: ExactIn or ExactOut

        Returns:
            SwapQuote with route details or None if failed
        """
        session = await self._get_session()

        swap_mode = mode.value if isinstance(mode, SwapMode) else str(mode)
        params = {
            'inputMint': input_mint,
            'outputMint': output_mint,
            'amount': str(amount),
            'slippageBps': slippage_bps,
            'swapMode': swap_mode
        }

        response_ctx = session.get(f"{self.JUPITER_API}/quote", params=params)
        if asyncio.iscoroutine(response_ctx):
            response_ctx = await response_ctx

        async with response_ctx as resp:
            status = getattr(resp, "status", 200)
            if not isinstance(status, int):
                try:
                    status = int(status)
                except (TypeError, ValueError):
                    status = 200
            if status < 100 or status > 599:
                status = 200

            if status != 200:
                error_msg = f"Quote failed: {status}"
                logger.error(error_msg)
                # Raise for retry if it's a retryable status code
                if status in (429, 500, 502, 503, 504):
                    raise ConnectionError(error_msg)
                return None

            data = await resp.json()

            if 'error' in data:
                logger.error(f"Quote error: {data['error']}")
                return None

            # Get token info for decimals
            input_info = await self.get_token_info(input_mint)
            output_info = await self.get_token_info(output_mint)

            input_decimals = input_info.decimals if input_info else 9
            output_decimals = output_info.decimals if output_info else 9

            input_amount = int(data.get('inAmount', 0))
            output_amount = int(data.get('outAmount', 0))

            return SwapQuote(
                input_mint=input_mint,
                output_mint=output_mint,
                input_amount=input_amount,
                output_amount=output_amount,
                input_amount_ui=input_amount / (10 ** input_decimals),
                output_amount_ui=output_amount / (10 ** output_decimals),
                price_impact_pct=float(data.get('priceImpactPct', 0)),
                slippage_bps=slippage_bps,
                fees_usd=0.0,  # Calculate from route
                route_plan=data.get('routePlan', []),
                quote_response=data
            )

    @retry(policy=JUPITER_SWAP_RETRY)
    async def get_swap_transaction(
        self,
        quote: SwapQuote,
        user_public_key: str,
        wrap_unwrap_sol: bool = True,
        compute_unit_price_micro_lamports: int = None
    ) -> Optional[bytes]:
        """
        Get the swap transaction for signing with automatic retry.

        Args:
            quote: Quote from get_quote()
            user_public_key: Wallet public key
            wrap_unwrap_sol: Auto wrap/unwrap SOL
            compute_unit_price_micro_lamports: Priority fee

        Returns:
            Transaction bytes for signing or None
        """
        session = await self._get_session()

        payload = {
            'quoteResponse': quote.quote_response,
            'userPublicKey': user_public_key,
            'wrapAndUnwrapSol': wrap_unwrap_sol,
            'dynamicComputeUnitLimit': True,
        }

        if compute_unit_price_micro_lamports:
            payload['computeUnitPriceMicroLamports'] = compute_unit_price_micro_lamports

        async with session.post(
            f"{self.JUPITER_API}/swap",
            json=payload
        ) as resp:
            if resp.status != 200:
                error = await resp.text()
                error_msg = f"Swap transaction failed: {resp.status} - {error}"
                logger.error(error_msg)
                # Raise for retry if it's a retryable status code
                if resp.status in (429, 500, 502, 503, 504):
                    raise ConnectionError(error_msg)
                return None

            data = await resp.json()
            swap_transaction = data.get('swapTransaction')

            if swap_transaction:
                import base64
                return base64.b64decode(swap_transaction)

        return None

    async def simulate_transaction(self, transaction_bytes: bytes) -> Tuple[bool, str]:
        """
        Simulate a transaction before execution.

        Returns:
            Tuple of (success, error_message)
        """
        session = await self._get_session()

        try:
            import base64
            encoded = base64.b64encode(transaction_bytes).decode()

            async with session.post(self.rpc_url, json={
                'jsonrpc': '2.0',
                'id': 1,
                'method': 'simulateTransaction',
                'params': [
                    encoded,
                    {'encoding': 'base64', 'commitment': 'confirmed'}
                ]
            }) as resp:
                data = await resp.json()
                result = data.get('result', {})

                if result.get('value', {}).get('err'):
                    error = result['value']['err']
                    return False, str(error)

                return True, ""

        except Exception as e:
            return False, str(e)

    async def confirm_transaction(
        self,
        signature: str,
        timeout: int = None,
        commitment: str = 'confirmed'
    ) -> Tuple[bool, str]:
        """
        Wait for transaction confirmation with timeout.

        Per Solana Trading Bot Guide: "Always confirm transactions with appropriate
        timeout handling to detect dropped or failed transactions."

        Args:
            signature: Transaction signature to confirm
            timeout: Timeout in seconds (default: TX_CONFIRM_TIMEOUT)
            commitment: Commitment level ('processed', 'confirmed', 'finalized')

        Returns:
            Tuple of (success, status_or_error)
        """
        session = await self._get_session()
        timeout = timeout or self.TX_CONFIRM_TIMEOUT
        start_time = asyncio.get_event_loop().time()

        while True:
            elapsed = asyncio.get_event_loop().time() - start_time
            if elapsed >= timeout:
                return False, "Transaction confirmation timeout"

            try:
                async with session.post(self.rpc_url, json={
                    'jsonrpc': '2.0',
                    'id': 1,
                    'method': 'getSignatureStatuses',
                    'params': [[signature], {'searchTransactionHistory': True}]
                }) as resp:
                    data = await resp.json()
                    result = data.get('result', {})
                    statuses = result.get('value', [])

                    if statuses and statuses[0]:
                        status = statuses[0]

                        # Check for error
                        if status.get('err'):
                            return False, f"Transaction failed: {status['err']}"

                        # Check confirmation level
                        conf_status = status.get('confirmationStatus', '')
                        if commitment == 'processed' and conf_status:
                            return True, conf_status
                        elif commitment == 'confirmed' and conf_status in ['confirmed', 'finalized']:
                            return True, conf_status
                        elif commitment == 'finalized' and conf_status == 'finalized':
                            return True, conf_status

            except Exception as e:
                logger.warning(f"Error checking tx status: {e}")

            await asyncio.sleep(0.5)

    async def send_transaction_with_retry(
        self,
        transaction_bytes: bytes,
        max_retries: int = None
    ) -> Tuple[bool, str]:
        """
        Send transaction with automatic retry on transient failures.

        Per Solana Trading Bot Guide: "Implement retry logic with fresh blockhashes
        for transactions that fail due to blockhash expiry."

        Args:
            transaction_bytes: Signed transaction bytes
            max_retries: Maximum retry attempts (default: TX_MAX_RETRIES)

        Returns:
            Tuple of (success, signature_or_error)
        """
        import base64

        max_retries = max_retries or self.TX_MAX_RETRIES
        session = await self._get_session()

        for attempt in range(max_retries + 1):
            try:
                async with session.post(self.rpc_url, json={
                    'jsonrpc': '2.0',
                    'id': 1,
                    'method': 'sendTransaction',
                    'params': [
                        base64.b64encode(transaction_bytes).decode(),
                        {
                            'encoding': 'base64',
                            'preflightCommitment': 'confirmed',
                            'maxRetries': 0  # We handle retries ourselves
                        }
                    ]
                }) as resp:
                    data = await resp.json()

                    if 'error' in data:
                        error_msg = data['error'].get('message', 'Unknown error')

                        # Check if retryable error
                        if any(x in error_msg.lower() for x in ['blockhash', 'expired', 'timeout']):
                            if attempt < max_retries:
                                logger.warning(f"Retryable tx error (attempt {attempt + 1}): {error_msg}")
                                await asyncio.sleep(self.TX_RETRY_DELAY)
                                continue

                        return False, error_msg

                    signature = data.get('result', '')
                    if signature:
                        # Wait for confirmation
                        confirmed, status = await self.confirm_transaction(signature)
                        if confirmed:
                            logger.info(f"Transaction confirmed: {signature[:12]}... ({status})")
                            return True, signature
                        else:
                            if attempt < max_retries:
                                logger.warning(f"Tx not confirmed (attempt {attempt + 1}): {status}")
                                await asyncio.sleep(self.TX_RETRY_DELAY)
                                continue
                            return False, status

            except Exception as e:
                if attempt < max_retries:
                    logger.warning(f"Tx send error (attempt {attempt + 1}): {e}")
                    await asyncio.sleep(self.TX_RETRY_DELAY)
                    continue
                return False, str(e)

        return False, "Max retries exceeded"

    async def get_dynamic_priority_fee(self) -> int:
        """
        Calculate dynamic priority fee based on recent network conditions.

        Per Solana Trading Bot Guide: "Performant bots dynamically calculate
        the appropriate fee based on recent network conditions, analyzing
        recent transactions to bid just enough to be competitive without overpaying."

        Returns:
            Priority fee in micro lamports
        """
        session = await self._get_session()

        try:
            # Get recent prioritization fees from the network
            async with session.post(self.rpc_url, json={
                'jsonrpc': '2.0',
                'id': 1,
                'method': 'getRecentPrioritizationFees',
                'params': []
            }) as resp:
                data = await resp.json()
                fees = data.get('result', [])

                if not fees:
                    logger.debug("No recent fees, using default")
                    return self.DEFAULT_PRIORITY_FEE

                # Extract prioritization fees from recent slots
                recent_fees = [f.get('prioritizationFee', 0) for f in fees[-20:]]
                recent_fees = [f for f in recent_fees if f > 0]

                if not recent_fees:
                    return self.DEFAULT_PRIORITY_FEE

                # Calculate competitive fee (75th percentile to beat most txs)
                sorted_fees = sorted(recent_fees)
                percentile_75_idx = int(len(sorted_fees) * 0.75)
                competitive_fee = sorted_fees[percentile_75_idx]

                # Add 20% buffer to ensure inclusion
                buffered_fee = int(competitive_fee * 1.2)

                # Clamp to min/max bounds
                final_fee = max(self.MIN_PRIORITY_FEE, min(buffered_fee, self.MAX_PRIORITY_FEE))

                logger.debug(f"Dynamic priority fee: {final_fee} micro lamports (network 75th: {competitive_fee})")
                return final_fee

        except Exception as e:
            logger.warning(f"Failed to get dynamic priority fee: {e}, using default")
            return self.DEFAULT_PRIORITY_FEE

    async def execute_swap(
        self,
        quote: SwapQuote,
        wallet,  # SecureWallet instance
        simulate_first: bool = True,
        priority_fee: int = None,
        max_retries: int = 3,
        retry_delay: float = 1.0
    ) -> SwapResult:
        """
        Execute a swap using the treasury wallet with retry logic.

        Args:
            quote: Quote from get_quote()
            wallet: SecureWallet instance for signing
            simulate_first: Simulate before executing
            priority_fee: Priority fee in micro lamports
            max_retries: Maximum number of retry attempts (default: 3)
            retry_delay: Base delay between retries in seconds (uses exponential backoff)

        Returns:
            SwapResult with transaction details
        """
        import asyncio
        last_error = None
        
        for attempt in range(max_retries):
            try:
                result = await self._execute_swap_once(
                    quote, wallet, simulate_first, priority_fee
                )
                if result.success:
                    return result
                
                # Check if error is retryable
                error_msg = result.error or ""
                retryable_errors = [
                    "timeout", "blockhash", "rate limit", "too many requests",
                    "network", "connection", "503", "504", "429"
                ]
                is_retryable = any(e in error_msg.lower() for e in retryable_errors)
                
                if not is_retryable:
                    return result  # Non-retryable error, fail immediately
                    
                last_error = result.error
                if attempt < max_retries - 1:
                    delay = retry_delay * (2 ** attempt)  # Exponential backoff
                    logger.warning(f"Swap attempt {attempt + 1} failed: {error_msg}. Retrying in {delay}s...")
                    await asyncio.sleep(delay)
                    
            except Exception as e:
                last_error = str(e)
                if attempt < max_retries - 1:
                    delay = retry_delay * (2 ** attempt)
                    logger.warning(f"Swap attempt {attempt + 1} error: {e}. Retrying in {delay}s...")
                    await asyncio.sleep(delay)
        
        return SwapResult(success=False, error=f"Swap failed after {max_retries} attempts: {last_error}")

    async def _execute_swap_once(
        self,
        quote: SwapQuote,
        wallet,
        simulate_first: bool,
        priority_fee: int
    ) -> SwapResult:
        """Single swap attempt (called by execute_swap with retry logic)."""
        try:
            treasury = wallet.get_treasury()
            if not treasury:
                return SwapResult(success=False, error="No treasury wallet found")

            # Get swap transaction
            tx_bytes = await self.get_swap_transaction(
                quote,
                treasury.address,
                compute_unit_price_micro_lamports=priority_fee
            )

            if not tx_bytes:
                return SwapResult(success=False, error="Failed to build transaction")

            # Simulate first
            if simulate_first:
                sim_success, sim_error = await self.simulate_transaction(tx_bytes)
                if not sim_success:
                    return SwapResult(
                        success=False,
                        error=f"Simulation failed: {sim_error}"
                    )

            # Sign transaction
            signed_tx = wallet.sign_transaction(treasury.address, tx_bytes)

            # Submit to network
            session = await self._get_session()
            import base64

            async with session.post(self.rpc_url, json={
                'jsonrpc': '2.0',
                'id': 1,
                'method': 'sendTransaction',
                'params': [
                    base64.b64encode(signed_tx).decode(),
                    {'encoding': 'base64', 'preflightCommitment': 'confirmed'}
                ]
            }) as resp:
                data = await resp.json()

                if 'error' in data:
                    return SwapResult(
                        success=False,
                        error=data['error'].get('message', 'Unknown error')
                    )

                signature = data.get('result', '')

                # Verify transaction on-chain before marking as success
                confirmation_service = self._get_confirmation_service()
                verification_result = await confirmation_service.verify_transaction(signature)

                if not verification_result.success:
                    logger.error(
                        f"Transaction {signature[:12]}... failed verification: {verification_result.error}"
                    )
                    return SwapResult(
                        success=False,
                        signature=signature,
                        error=f"Transaction verification failed: {verification_result.error}"
                    )

                # Get token info for symbols
                input_info = await self.get_token_info(quote.input_mint)
                output_info = await self.get_token_info(quote.output_mint)

                # Log transaction to history
                await confirmation_service.log_transaction(
                    result=verification_result,
                    input_mint=quote.input_mint,
                    output_mint=quote.output_mint,
                    input_amount=quote.input_amount_ui,
                    output_amount=quote.output_amount_ui
                )

                logger.info(
                    f"Transaction verified: {signature[:12]}... "
                    f"({verification_result.status.value}, slot={verification_result.slot})"
                )

                return SwapResult(
                    success=True,
                    signature=signature,
                    input_amount=quote.input_amount_ui,
                    output_amount=quote.output_amount_ui,
                    input_symbol=input_info.symbol if input_info else 'UNKNOWN',
                    output_symbol=output_info.symbol if output_info else 'UNKNOWN',
                    price_impact=quote.price_impact_pct,
                    fees_usd=quote.fees_usd
                )

        except Exception as e:
            logger.error(f"Swap execution failed: {e}")
            return SwapResult(success=False, error=str(e))

    async def get_sol_quote_for_usd(self, usd_amount: float, output_mint: str) -> Optional[SwapQuote]:
        """
        Get a quote to spend a specific USD amount of SOL.

        Args:
            usd_amount: Amount in USD to spend
            output_mint: Token to receive

        Returns:
            SwapQuote or None
        """
        # Get SOL price
        sol_price = await self.get_token_price(self.SOL_MINT)
        if sol_price <= 0:
            return None

        # Calculate SOL amount
        sol_amount = usd_amount / sol_price
        lamports = int(sol_amount * 1e9)

        return await self.get_quote(self.SOL_MINT, output_mint, lamports)


class LimitOrderManager:
    """
    Manages limit orders, take profit, and stop loss triggers.
    Uses price monitoring and executes via Jupiter when triggered.
    Orders are persisted to disk for reliability across restarts.
    """

    ORDERS_FILE = Path(os.getenv("DATA_DIR", "data")) / "limit_orders.json"

    def __init__(self, jupiter: JupiterClient, wallet, on_order_filled=None):
        """
        Initialize LimitOrderManager.

        Args:
            jupiter: JupiterClient for swaps
            wallet: SecureWallet for signing
            on_order_filled: Optional callback(order_id, order_type, result) called when orders execute
        """
        self.jupiter = jupiter
        self.wallet = wallet
        self.orders: Dict[str, Dict] = {}
        self._running = False
        self._monitor_task: Optional[asyncio.Task] = None
        self._on_order_filled = on_order_filled
        self._load_orders()

    def _load_orders(self):
        """Load orders from disk."""
        if self.ORDERS_FILE.exists():
            try:
                with open(self.ORDERS_FILE) as f:
                    self.orders = json.load(f)
                logger.info(f"Loaded {len(self.orders)} orders from disk")
            except Exception as e:
                logger.warning(f"Failed to load orders: {e}")

    def _save_orders(self):
        """Save orders to disk."""
        self.ORDERS_FILE.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(self.ORDERS_FILE, 'w') as f:
                json.dump(self.orders, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save orders: {e}")

    async def create_take_profit(
        self,
        token_mint: str,
        amount: int,
        target_price: float,
        order_id: str = None
    ) -> str:
        """
        Create a take profit order.

        Args:
            token_mint: Token to sell
            amount: Amount in smallest unit
            target_price: Price in USD to trigger at
            order_id: Optional custom order ID

        Returns:
            Order ID
        """
        import uuid
        order_id = order_id or str(uuid.uuid4())[:8]

        self.orders[order_id] = {
            'type': 'TAKE_PROFIT',
            'token_mint': token_mint,
            'amount': amount,
            'target_price': target_price,
            'output_mint': JupiterClient.SOL_MINT,  # Sell to SOL for treasury
            'created_at': datetime.utcnow().isoformat(),
            'status': 'ACTIVE',
            'triggered_at': None,
            'result': None
        }

        self._save_orders()
        logger.info(f"Created take profit order {order_id}: sell at ${target_price}")
        return order_id

    async def create_stop_loss(
        self,
        token_mint: str,
        amount: int,
        stop_price: float,
        order_id: str = None
    ) -> str:
        """
        Create a stop loss order.

        Args:
            token_mint: Token to sell
            amount: Amount in smallest unit
            stop_price: Price in USD to trigger at
            order_id: Optional custom order ID

        Returns:
            Order ID
        """
        import uuid
        order_id = order_id or str(uuid.uuid4())[:8]

        self.orders[order_id] = {
            'type': 'STOP_LOSS',
            'token_mint': token_mint,
            'amount': amount,
            'target_price': stop_price,
            'output_mint': JupiterClient.SOL_MINT,  # Sell to SOL for treasury
            'created_at': datetime.utcnow().isoformat(),
            'status': 'ACTIVE',
            'triggered_at': None,
            'result': None
        }

        self._save_orders()
        logger.info(f"Created stop loss order {order_id}: sell at ${stop_price}")
        return order_id

    async def cancel_order(self, order_id: str) -> bool:
        """Cancel an order."""
        if order_id in self.orders:
            self.orders[order_id]['status'] = 'CANCELLED'
            self._save_orders()
            logger.info(f"Cancelled order {order_id}")
            return True
        return False

    async def start_monitoring(self, interval_seconds: int = 5):
        """Start monitoring prices for order triggers.

        Default 5 seconds for responsive TP/SL on volatile tokens.
        """
        if self._running:
            return

        self._running = True
        self._monitor_task = asyncio.create_task(self._monitor_loop(interval_seconds))
        logger.info(f"Started order monitoring (interval: {interval_seconds}s)")

    async def stop_monitoring(self):
        """Stop monitoring."""
        self._running = False
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass

    async def _monitor_loop(self, interval: int):
        """Monitor prices and trigger orders."""
        while self._running:
            try:
                await self._check_orders()
            except Exception as e:
                logger.error(f"Order check failed: {e}")

            await asyncio.sleep(interval)

    async def _check_orders(self):
        """Check all active orders against current prices."""
        active_orders = [
            (oid, order) for oid, order in self.orders.items()
            if order['status'] == 'ACTIVE'
        ]

        for order_id, order in active_orders:
            try:
                current_price = await self.jupiter.get_token_price(order['token_mint'])

                if current_price <= 0:
                    continue

                triggered = False

                if order['type'] == 'TAKE_PROFIT':
                    # Trigger when price goes ABOVE target
                    if current_price >= order['target_price']:
                        triggered = True

                elif order['type'] == 'STOP_LOSS':
                    # Trigger when price goes BELOW target
                    if current_price <= order['target_price']:
                        triggered = True

                if triggered:
                    await self._execute_order(order_id, order, current_price)

            except Exception as e:
                logger.error(f"Failed to check order {order_id}: {e}")

    async def _execute_order(self, order_id: str, order: Dict, current_price: float):
        """Execute a triggered order."""
        logger.info(f"Executing {order['type']} order {order_id} at ${current_price}")

        order['status'] = 'EXECUTING'
        order['triggered_at'] = datetime.utcnow().isoformat()
        order['triggered_price'] = current_price

        try:
            # Get quote
            quote = await self.jupiter.get_quote(
                order['token_mint'],
                order['output_mint'],
                order['amount'],
                slippage_bps=100  # 1% slippage for triggered orders
            )

            if not quote:
                order['status'] = 'FAILED'
                order['result'] = {'error': 'Failed to get quote'}
                self._save_orders()
                return

            # Execute swap
            result = await self.jupiter.execute_swap(quote, self.wallet)

            order['status'] = 'COMPLETED' if result.success else 'FAILED'
            order['result'] = result.to_dict()
            self._save_orders()

            logger.info(f"Order {order_id} {'completed' if result.success else 'failed'}")

            # Notify callback for position closure / P&L tracking
            if result.success and self._on_order_filled:
                try:
                    callback_result = self._on_order_filled(
                        order_id=order_id,
                        order_type=order['type'],  # 'TAKE_PROFIT' or 'STOP_LOSS'
                        token_mint=order['token_mint'],
                        exit_price=current_price,
                        output_amount=quote.output_amount_ui,
                        tx_signature=result.signature
                    )
                    # Handle async callbacks
                    if asyncio.iscoroutine(callback_result):
                        await callback_result
                except Exception as cb_err:
                    logger.error(f"Order filled callback failed: {cb_err}")

        except Exception as e:
            order['status'] = 'FAILED'
            order['result'] = {'error': str(e)}
            self._save_orders()
            logger.error(f"Order {order_id} execution failed: {e}")

    def get_active_orders(self) -> List[Dict]:
        """Get all active orders."""
        return [
            {'id': oid, **order}
            for oid, order in self.orders.items()
            if order['status'] == 'ACTIVE'
        ]

    def get_order_history(self) -> List[Dict]:
        """Get all orders."""
        return [{'id': oid, **order} for oid, order in self.orders.items()]
