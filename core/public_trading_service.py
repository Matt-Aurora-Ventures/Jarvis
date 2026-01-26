"""
Public trading utilities for per-user wallets.

Implements token resolution, portfolio lookups, Jupiter quotes, and swap/send execution.
"""

from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import aiohttp
from aiohttp import ClientTimeout

from bots.treasury.jupiter import JupiterClient, SwapQuote, SwapResult
from bots.treasury.wallet import WalletInfo
from core import dexscreener
from core.wallet_service import WalletService
from tg_bot.services.token_data import KNOWN_TOKENS

try:
    from solders.keypair import Keypair
    from solders.pubkey import Pubkey
    from solders.system_program import TransferParams, transfer
    from solana.rpc.async_api import AsyncClient
    from solana.transaction import Transaction
    HAS_SOLANA = True
except Exception:
    Keypair = None
    Pubkey = None
    TransferParams = None
    transfer = None
    AsyncClient = None
    Transaction = None
    HAS_SOLANA = False

logger = logging.getLogger(__name__)

TOKEN_PROGRAM_ID = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"


@dataclass
class ResolvedToken:
    mint: str
    symbol: str
    name: str
    decimals: int
    price_usd: float


@dataclass
class TokenHolding:
    mint: str
    amount: float
    decimals: int
    symbol: str
    name: str
    price_usd: float
    value_usd: float


@dataclass
class PortfolioSnapshot:
    sol_balance: float
    sol_price_usd: float
    sol_value_usd: float
    holdings: List[TokenHolding]


class UserWalletAdapter:
    """Minimal wallet adapter for Jupiter swap execution."""

    def __init__(self, keypair: "Keypair"):
        self._keypair = keypair
        address = str(keypair.pubkey())
        self._wallet_info = WalletInfo(
            address=address,
            created_at="",
            label="User",
            is_treasury=False,
        )

    def get_treasury(self) -> Optional[WalletInfo]:
        return self._wallet_info

    def sign_transaction(self, address: str, transaction: Any) -> bytes:
        tx_bytes = transaction
        if isinstance(transaction, (bytes, bytearray)):
            tx_bytes = bytes(transaction)
        if isinstance(tx_bytes, (bytes, bytearray)):
            try:
                from solders.transaction import VersionedTransaction

                versioned = VersionedTransaction.from_bytes(tx_bytes)
                signed_tx = VersionedTransaction(versioned.message, [self._keypair])
                return bytes(signed_tx)
            except Exception:
                signature = self._keypair.sign_message(tx_bytes)
                return bytes(signature)

        if hasattr(transaction, "sign"):
            transaction.sign([self._keypair])
            try:
                return bytes(transaction)
            except Exception:
                return b""

        signature = self._keypair.sign_message(transaction)
        return bytes(signature)

    @property
    def address(self) -> str:
        return self._wallet_info.address


class PublicTradingService:
    """Core services for public bot trading and portfolio lookups."""

    def __init__(
        self,
        wallet_service: WalletService,
        rpc_url: Optional[str] = None,
    ) -> None:
        self.wallet_service = wallet_service
        self.rpc_url = rpc_url or os.environ.get(
            "SOLANA_RPC_URL", "https://api.mainnet-beta.solana.com"
        )
        self.jupiter = JupiterClient(self.rpc_url)
        self._session: Optional[aiohttp.ClientSession] = None

    def load_keypair(self, encrypted_key: str, password: str) -> "Keypair":
        private_key = self.wallet_service.decrypt_private_key(encrypted_key, password)
        return self.wallet_service.load_keypair_from_private_key(private_key)

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()
        await self.jupiter.close()

    def validate_address(self, address: str) -> bool:
        if not address or not HAS_SOLANA or Pubkey is None:
            return False
        try:
            Pubkey.from_string(address)
            return True
        except Exception:
            return False

    async def resolve_token(self, token_input: str) -> Optional[ResolvedToken]:
        token = (token_input or "").strip()
        if not token:
            return None

        mint = None
        symbol_guess = token.upper()

        if self.validate_address(token):
            mint = token
        elif symbol_guess in KNOWN_TOKENS:
            mint = KNOWN_TOKENS[symbol_guess]
        else:
            result = await asyncio.to_thread(dexscreener.search_pairs, token)
            pairs = []
            if result and result.success and result.data:
                pairs = result.data.get("pairs") or []
            solana_pairs = [p for p in pairs if p.get("chainId") == "solana"]
            if solana_pairs:
                def liquidity(pair: Dict[str, Any]) -> float:
                    try:
                        return float(pair.get("liquidity", {}).get("usd", 0) or 0)
                    except (TypeError, ValueError):
                        return 0.0

                solana_pairs.sort(key=liquidity, reverse=True)
                mint = (solana_pairs[0].get("baseToken") or {}).get("address")

        if not mint:
            return None

        info = await self.jupiter.get_token_info(mint)
        if not info:
            return None

        return ResolvedToken(
            mint=mint,
            symbol=info.symbol,
            name=info.name or info.symbol,
            decimals=info.decimals or 9,
            price_usd=info.price_usd or 0.0,
        )

    async def get_sol_balance(self, address: str) -> float:
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getBalance",
            "params": [address],
        }
        data = await self._rpc_call(payload)
        if not data:
            return 0.0
        lamports = data.get("result", {}).get("value", 0)
        return float(lamports) / 1e9

    async def get_token_accounts(self, address: str) -> List[Dict[str, Any]]:
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getTokenAccountsByOwner",
            "params": [
                address,
                {"programId": TOKEN_PROGRAM_ID},
                {"encoding": "jsonParsed"},
            ],
        }
        data = await self._rpc_call(payload)
        if not data:
            return []
        return data.get("result", {}).get("value", []) or []

    async def get_portfolio(self, address: str) -> PortfolioSnapshot:
        sol_balance = await self.get_sol_balance(address)
        sol_price = await self.jupiter.get_token_price(self.jupiter.SOL_MINT)
        sol_value = sol_balance * (sol_price or 0.0)

        token_accounts = await self.get_token_accounts(address)
        holdings: List[TokenHolding] = []

        for entry in token_accounts:
            info = entry.get("account", {}).get("data", {}).get("parsed", {}).get("info", {})
            mint = info.get("mint")
            token_amount = info.get("tokenAmount", {})
            amount_raw = token_amount.get("uiAmount")
            decimals = token_amount.get("decimals", 0)

            if not mint or amount_raw is None:
                continue
            amount = float(amount_raw or 0)
            if amount <= 0:
                continue

            token_info = await self.jupiter.get_token_info(mint)
            symbol = token_info.symbol if token_info else mint[:6]
            name = token_info.name if token_info else symbol
            price = 0.0
            try:
                price = await self.jupiter.get_token_price(mint)
            except Exception:
                price = 0.0
            value = amount * (price or 0.0)
            if value < 0.01:
                continue

            holdings.append(
                TokenHolding(
                    mint=mint,
                    amount=amount,
                    decimals=decimals,
                    symbol=symbol,
                    name=name,
                    price_usd=price or 0.0,
                    value_usd=value,
                )
            )

        holdings.sort(key=lambda h: h.value_usd, reverse=True)
        return PortfolioSnapshot(
            sol_balance=sol_balance,
            sol_price_usd=sol_price or 0.0,
            sol_value_usd=sol_value,
            holdings=holdings,
        )

    async def get_buy_quote(
        self,
        output_mint: str,
        amount_sol: float,
        slippage_bps: int,
    ) -> Optional[SwapQuote]:
        amount_lamports = int(amount_sol * 1e9)
        return await self.jupiter.get_quote(
            self.jupiter.SOL_MINT,
            output_mint,
            amount_lamports,
            slippage_bps=slippage_bps,
        )

    async def get_sell_quote(
        self,
        input_mint: str,
        amount_tokens: float,
        slippage_bps: int,
    ) -> Optional[SwapQuote]:
        info = await self.jupiter.get_token_info(input_mint)
        decimals = info.decimals if info else 9
        amount_raw = int(amount_tokens * (10 ** decimals))
        return await self.jupiter.get_quote(
            input_mint,
            self.jupiter.SOL_MINT,
            amount_raw,
            slippage_bps=slippage_bps,
        )

    async def execute_swap(self, quote: SwapQuote, keypair: "Keypair") -> SwapResult:
        wallet = UserWalletAdapter(keypair)
        return await self.jupiter.execute_swap(quote, wallet)

    async def send_sol(
        self,
        keypair: "Keypair",
        destination: str,
        amount_sol: float,
    ) -> Optional[str]:
        if not HAS_SOLANA or AsyncClient is None or Transaction is None or transfer is None:
            raise RuntimeError("Solana dependencies missing for transfer")
        if amount_sol <= 0:
            raise ValueError("Amount must be positive")
        if not self.validate_address(destination):
            raise ValueError("Invalid destination address")

        lamports = int(amount_sol * 1e9)
        from_pubkey = keypair.pubkey()
        to_pubkey = Pubkey.from_string(destination)

        transfer_ix = transfer(
            TransferParams(
                from_pubkey=from_pubkey,
                to_pubkey=to_pubkey,
                lamports=lamports,
            )
        )

        async with AsyncClient(self.rpc_url) as client:
            blockhash = (await client.get_latest_blockhash()).value.blockhash
            tx = Transaction()
            tx.recent_blockhash = blockhash
            tx.add(transfer_ix)
            tx.sign(keypair)
            result = await client.send_transaction(tx)
            return str(result.value)

    async def _rpc_call(self, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        session = await self._get_session()
        try:
            async with session.post(
                self.rpc_url,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                if resp.status != 200:
                    return None
                return await resp.json()
        except Exception as exc:
            logger.warning(f"RPC call failed: {exc}")
            return None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            # Configure timeouts: 60s total, 30s connect (for token/wallet data fetching)
            timeout = ClientTimeout(total=60, connect=30)
            self._session = aiohttp.ClientSession(timeout=timeout)
        return self._session
