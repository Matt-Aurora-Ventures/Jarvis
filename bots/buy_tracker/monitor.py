"""
Transaction Monitor - Real-time monitoring of token buys using Helius.
"""

import asyncio
import json
import logging
import aiohttp
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional
import base58

logger = logging.getLogger(__name__)


@dataclass
class BuyTransaction:
    """Represents a detected buy transaction."""
    signature: str
    buyer_wallet: str
    token_amount: float
    sol_amount: float
    usd_amount: float
    price_per_token: float
    buyer_position_pct: float  # Percentage of supply held
    market_cap: float
    timestamp: datetime
    tx_url: str
    dex_url: str

    @property
    def buyer_short(self) -> str:
        """Get shortened buyer wallet address."""
        if len(self.buyer_wallet) > 8:
            return f"{self.buyer_wallet[:4]}...{self.buyer_wallet[-4:]}"
        return self.buyer_wallet

    @property
    def signature_short(self) -> str:
        """Get shortened transaction signature."""
        if len(self.signature) > 8:
            return f"{self.signature[:4]}...{self.signature[-4:]}"
        return self.signature


class TransactionMonitor:
    """
    Monitors transactions for a specific token using Helius WebSocket.

    Detects buys and notifies via callback.
    """

    # Maximum number of signatures to keep in memory (prevent unbounded growth)
    MAX_PROCESSED_SIGNATURES = 500

    def __init__(
        self,
        token_address: str,
        helius_api_key: str,
        min_buy_usd: float = 5.0,
        on_buy: Optional[Callable[[BuyTransaction], None]] = None,
        pair_address: str = "",
    ):
        self.token_address = token_address
        self.pair_address = pair_address  # LP pair address where trades happen
        self.helius_api_key = helius_api_key
        self.min_buy_usd = min_buy_usd
        self.on_buy = on_buy

        self.rpc_url = f"https://mainnet.helius-rpc.com/?api-key={helius_api_key}"
        self.ws_url = f"wss://mainnet.helius-rpc.com/?api-key={helius_api_key}"

        self._running = False
        self._ws = None
        self._session: Optional[aiohttp.ClientSession] = None

        # Cache for token data
        self._token_supply: float = 0
        self._sol_price_usd: float = 0
        self._token_price_usd: float = 0
        self._market_cap: float = 0

        # Track processed signatures to prevent duplicate notifications
        self._processed_signatures: List[str] = []

    def _is_already_processed(self, signature: str) -> bool:
        """Check if a signature has already been processed."""
        return signature in self._processed_signatures

    def _mark_as_processed(self, signature: str):
        """Mark a signature as processed, maintaining max size."""
        if signature not in self._processed_signatures:
            self._processed_signatures.append(signature)
            # Trim old signatures if we exceed max
            if len(self._processed_signatures) > self.MAX_PROCESSED_SIGNATURES:
                self._processed_signatures = self._processed_signatures[-self.MAX_PROCESSED_SIGNATURES:]

    async def start(self):
        """Start monitoring transactions."""
        self._running = True
        self._session = aiohttp.ClientSession()

        # Log what we're monitoring
        if self.pair_address:
            logger.info(f"Starting transaction monitor for pair {self.pair_address}")
        else:
            logger.info(f"Starting transaction monitor for token {self.token_address}")

        # Initial data fetch
        await self._update_prices()

        # Start monitoring loops
        asyncio.create_task(self._price_update_loop())
        asyncio.create_task(self._transaction_poll_loop())

    async def stop(self):
        """Stop monitoring."""
        self._running = False
        if self._ws:
            await self._ws.close()
        if self._session:
            await self._session.close()
        logger.info("Transaction monitor stopped")

    async def _price_update_loop(self):
        """Periodically update price data."""
        while self._running:
            try:
                await self._update_prices()
                await asyncio.sleep(30)  # Update every 30 seconds
            except Exception as e:
                logger.error(f"Price update error: {e}")
                await asyncio.sleep(10)

    async def _update_prices(self):
        """Update SOL and token prices."""
        try:
            # Get SOL price from CoinGecko (free, no API key needed)
            async with self._session.get(
                "https://api.coingecko.com/api/v3/simple/price?ids=solana&vs_currencies=usd"
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    self._sol_price_usd = data.get("solana", {}).get("usd", 0)

            # Get token data from DexScreener (free API)
            async with self._session.get(
                f"https://api.dexscreener.com/latest/dex/tokens/{self.token_address}"
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    pairs = data.get("pairs", [])
                    if pairs:
                        pair = pairs[0]  # Use first/main pair
                        self._token_price_usd = float(pair.get("priceUsd", 0))
                        self._market_cap = float(pair.get("marketCap", 0) or pair.get("fdv", 0))

            logger.debug(f"Prices updated: SOL=${self._sol_price_usd}, Token=${self._token_price_usd}")

        except Exception as e:
            logger.error(f"Failed to update prices: {e}")

    async def _transaction_poll_loop(self):
        """Poll for recent transactions (fallback to WebSocket)."""
        first_run = True
        poll_count = 0

        while self._running:
            try:
                # Get recent signatures for the pair/token
                signatures = await self._get_recent_signatures()
                poll_count += 1
                new_count = 0

                for sig_info in signatures:
                    sig = sig_info.get("signature")

                    # Skip if already processed (prevents duplicates)
                    if self._is_already_processed(sig):
                        continue

                    new_count += 1

                    # On first run, just mark existing signatures as processed
                    if first_run:
                        self._mark_as_processed(sig)
                        continue

                    # Parse transaction
                    buy = await self._parse_transaction(sig)
                    if buy:
                        if buy.usd_amount >= self.min_buy_usd:
                            logger.info(f"Buy detected: ${buy.usd_amount:.2f} by {buy.buyer_short} ({buy.sol_amount:.4f} SOL)")
                            self._mark_as_processed(sig)
                            if self.on_buy:
                                await self._safe_callback(buy)
                        else:
                            logger.info(f"Buy below threshold: ${buy.usd_amount:.2f} < ${self.min_buy_usd} by {buy.buyer_short}")
                            self._mark_as_processed(sig)
                    else:
                        # Mark non-buy transactions too (likely sells or other tx types)
                        logger.debug(f"Non-buy transaction: {sig[:12]}...")
                        self._mark_as_processed(sig)

                # Log status periodically
                if first_run and new_count > 0:
                    logger.info(f"Initialized with {new_count} existing transactions (skipped)")
                elif poll_count % 15 == 0:  # Every ~30 seconds
                    logger.info(f"Poll #{poll_count}: {len(self._processed_signatures)} txns tracked, min=${self.min_buy_usd}")

                # Log new transactions found (for debugging)
                if new_count > 0 and not first_run:
                    logger.info(f"Found {new_count} new transaction(s) to process")

                first_run = False
                await asyncio.sleep(2)  # Poll every 2 seconds

            except Exception as e:
                logger.error(f"Transaction poll error: {e}")
                await asyncio.sleep(5)

    async def _get_recent_signatures(self) -> List[Dict]:
        """Get recent transaction signatures for the pair/token."""
        try:
            # Use pair address if available, otherwise fall back to token address
            watch_address = self.pair_address if self.pair_address else self.token_address

            payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "getSignaturesForAddress",
                "params": [
                    watch_address,
                    {"limit": 30}  # Increased limit for more coverage
                ]
            }

            async with self._session.post(self.rpc_url, json=payload) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get("result", [])

        except Exception as e:
            logger.error(f"Failed to get signatures: {e}")

        return []

    async def _parse_transaction(self, signature: str) -> Optional[BuyTransaction]:
        """Parse a transaction to detect if it's a buy."""
        try:
            # Use Helius enhanced transaction API
            url = f"https://api.helius.xyz/v0/transactions/?api-key={self.helius_api_key}"
            payload = {"transactions": [signature]}

            async with self._session.post(url, json=payload) as resp:
                if resp.status != 200:
                    return None

                data = await resp.json()
                if not data:
                    return None

                tx = data[0]

            # Check for token transfers
            token_transfers = tx.get("tokenTransfers", [])
            native_transfers = tx.get("nativeTransfers", [])
            fee_payer = tx.get("feePayer")

            # Find token transfer where fee_payer RECEIVES the token (buy)
            token_in = None
            for transfer in token_transfers:
                if transfer.get("mint") == self.token_address:
                    to_user = transfer.get("toUserAccount", "")
                    from_user = transfer.get("fromUserAccount", "")

                    # Buy = fee_payer receives token
                    if to_user == fee_payer:
                        token_in = transfer
                        break
                    # Sell = fee_payer sends token (skip)
                    elif from_user == fee_payer:
                        return None

            if not token_in:
                return None

            # Calculate SOL spent (fee_payer sends SOL)
            sol_out = 0
            sol_in = 0
            for transfer in native_transfers:
                from_user = transfer.get("fromUserAccount", "")
                to_user = transfer.get("toUserAccount", "")
                amount = transfer.get("amount", 0) / 1e9  # Convert lamports to SOL

                if from_user == fee_payer:
                    sol_out += amount
                if to_user == fee_payer:
                    sol_in += amount

            # Net SOL spent (exclude transaction fees returned, etc)
            net_sol_spent = sol_out - sol_in
            if net_sol_spent <= 0.001:  # Minimum 0.001 SOL to count as buy
                return None

            # Calculate amounts
            token_amount = float(token_in.get("tokenAmount", 0))
            usd_amount = net_sol_spent * self._sol_price_usd

            # Get buyer position (if we have supply data)
            buyer_position_pct = 0
            if self._market_cap > 0 and self._token_price_usd > 0:
                buyer_value = token_amount * self._token_price_usd
                buyer_position_pct = (buyer_value / self._market_cap) * 100

            return BuyTransaction(
                signature=signature,
                buyer_wallet=fee_payer,
                token_amount=token_amount,
                sol_amount=net_sol_spent,
                usd_amount=usd_amount,
                price_per_token=self._token_price_usd,
                buyer_position_pct=buyer_position_pct,
                market_cap=self._market_cap,
                timestamp=datetime.utcnow(),
                tx_url=f"https://solscan.io/tx/{signature}",
                dex_url=f"https://dexscreener.com/solana/{self.token_address}",
            )

        except Exception as e:
            logger.error(f"Failed to parse transaction {signature}: {e}")
            return None

    async def _safe_callback(self, buy: BuyTransaction):
        """Safely call the buy callback."""
        try:
            if asyncio.iscoroutinefunction(self.on_buy):
                await self.on_buy(buy)
            else:
                self.on_buy(buy)
        except Exception as e:
            logger.error(f"Buy callback error: {e}")


class HeliusWebSocketMonitor(TransactionMonitor):
    """
    Enhanced monitor using Helius WebSocket for real-time updates.
    """

    async def start(self):
        """Start WebSocket monitoring."""
        self._running = True
        self._session = aiohttp.ClientSession()

        logger.info(f"Starting Helius WebSocket monitor for {self.token_address}")

        await self._update_prices()

        # Start monitoring
        asyncio.create_task(self._price_update_loop())
        asyncio.create_task(self._websocket_loop())

    async def _websocket_loop(self):
        """Connect and listen to Helius WebSocket."""
        while self._running:
            try:
                async with self._session.ws_connect(self.ws_url) as ws:
                    self._ws = ws

                    # Subscribe to account updates for the token
                    subscribe_msg = {
                        "jsonrpc": "2.0",
                        "id": 1,
                        "method": "accountSubscribe",
                        "params": [
                            self.token_address,
                            {"encoding": "jsonParsed", "commitment": "confirmed"}
                        ]
                    }
                    await ws.send_json(subscribe_msg)
                    logger.info("WebSocket subscribed to token account")

                    async for msg in ws:
                        if msg.type == aiohttp.WSMsgType.TEXT:
                            await self._handle_ws_message(json.loads(msg.data))
                        elif msg.type == aiohttp.WSMsgType.ERROR:
                            logger.error(f"WebSocket error: {ws.exception()}")
                            break

            except Exception as e:
                logger.error(f"WebSocket error: {e}")
                await asyncio.sleep(5)

    async def _handle_ws_message(self, data: Dict):
        """Handle incoming WebSocket message."""
        try:
            if "result" in data:
                logger.debug(f"Subscription confirmed: {data['result']}")
                return

            if "params" in data:
                # Account update notification
                slot = data["params"].get("result", {}).get("context", {}).get("slot")
                logger.debug(f"Account update at slot {slot}")

                # Fetch recent transactions to find the buy
                signatures = await self._get_recent_signatures()
                for sig_info in signatures:
                    sig = sig_info.get("signature")

                    # Skip if already processed (prevents duplicates)
                    if self._is_already_processed(sig):
                        continue

                    buy = await self._parse_transaction(sig)
                    if buy and buy.usd_amount >= self.min_buy_usd:
                        logger.info(f"Buy detected: ${buy.usd_amount:.2f} by {buy.buyer_short}")
                        self._mark_as_processed(sig)
                        if self.on_buy:
                            await self._safe_callback(buy)
                    else:
                        self._mark_as_processed(sig)

                    # Only process most recent unprocessed transaction per update
                    break

        except Exception as e:
            logger.error(f"Failed to handle WS message: {e}")
