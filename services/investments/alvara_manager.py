"""Alvara ERC-7621 Basket Manager — reads/writes an on-chain basket on Base.

Connects via web3.py (v7+ async) to Base chain.  Supports:
  - get_basket_state()       -> token addresses, weights, NAV in USD
  - rebalance(new_weights)   -> calls rebalance(address[], uint256[]) on basket
  - get_management_fee_accrued() -> reads accrued management fees
  - collect_fees()           -> calls collectManagementFee()

All methods honour the DRY_RUN flag: when enabled, actions are logged but
never broadcast to the network.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

import aiohttp
from eth_account import Account
from eth_account.signers.local import LocalAccount
from web3 import AsyncWeb3
from web3.providers import AsyncHTTPProvider
from web3.contract import AsyncContract
from web3.types import TxParams

from services.investments.config import InvestmentConfig

logger = logging.getLogger("investments.alvara")

# ---------------------------------------------------------------------------
# Base chain constants
# ---------------------------------------------------------------------------
BASE_CHAIN_ID = 8453

# ---------------------------------------------------------------------------
# Minimal ERC-7621 ABI (only the functions we call / read)
# ---------------------------------------------------------------------------
ERC7621_ABI: list[dict[str, Any]] = [
    # --- Reads ---
    {
        "name": "getTokens",
        "type": "function",
        "stateMutability": "view",
        "inputs": [],
        "outputs": [{"name": "", "type": "address[]"}],
    },
    {
        "name": "getWeights",
        "type": "function",
        "stateMutability": "view",
        "inputs": [],
        "outputs": [{"name": "", "type": "uint256[]"}],
    },
    {
        "name": "totalSupply",
        "type": "function",
        "stateMutability": "view",
        "inputs": [],
        "outputs": [{"name": "", "type": "uint256"}],
    },
    {
        "name": "decimals",
        "type": "function",
        "stateMutability": "view",
        "inputs": [],
        "outputs": [{"name": "", "type": "uint8"}],
    },
    {
        "name": "name",
        "type": "function",
        "stateMutability": "view",
        "inputs": [],
        "outputs": [{"name": "", "type": "string"}],
    },
    {
        "name": "accruedManagementFee",
        "type": "function",
        "stateMutability": "view",
        "inputs": [],
        "outputs": [{"name": "", "type": "uint256"}],
    },
    # --- Writes ---
    {
        "name": "rebalance",
        "type": "function",
        "stateMutability": "nonpayable",
        "inputs": [
            {"name": "tokens", "type": "address[]"},
            {"name": "weights", "type": "uint256[]"},
        ],
        "outputs": [],
    },
    {
        "name": "collectManagementFee",
        "type": "function",
        "stateMutability": "nonpayable",
        "inputs": [],
        "outputs": [],
    },
]

# Minimal ERC-20 ABI for reading token balances held by the basket
ERC20_BALANCE_ABI: list[dict[str, Any]] = [
    {
        "name": "balanceOf",
        "type": "function",
        "stateMutability": "view",
        "inputs": [{"name": "account", "type": "address"}],
        "outputs": [{"name": "", "type": "uint256"}],
    },
    {
        "name": "decimals",
        "type": "function",
        "stateMutability": "view",
        "inputs": [],
        "outputs": [{"name": "", "type": "uint8"}],
    },
    {
        "name": "symbol",
        "type": "function",
        "stateMutability": "view",
        "inputs": [],
        "outputs": [{"name": "", "type": "string"}],
    },
]

# DexScreener endpoint for price lookups (free, no key required)
_DEXSCREENER_BASE_URL = "https://api.dexscreener.com/latest/dex/tokens"


class AlvaraManager:
    """Manages an ERC-7621 basket contract on Base chain."""

    def __init__(self, cfg: InvestmentConfig) -> None:
        self.cfg = cfg
        self.dry_run = cfg.dry_run

        # Web3 async provider
        self.w3 = AsyncWeb3(AsyncHTTPProvider(cfg.base_rpc_url))

        # Basket contract
        self.basket_address: str = AsyncWeb3.to_checksum_address(cfg.basket_address)
        self.basket: AsyncContract = self.w3.eth.contract(
            address=self.basket_address, abi=ERC7621_ABI
        )

        # Management wallet (only instantiated when we have a key)
        self.account: Optional[LocalAccount] = None
        if cfg.management_wallet_key:
            self.account = Account.from_key(cfg.management_wallet_key)
            logger.info(
                "Management wallet loaded: %s", self.account.address
            )

        # Reusable HTTP session for price fetches
        self._http: Optional[aiohttp.ClientSession] = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def _ensure_http(self) -> aiohttp.ClientSession:
        if self._http is None or self._http.closed:
            self._http = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=15)
            )
        return self._http

    async def close(self) -> None:
        """Shut down HTTP session."""
        if self._http and not self._http.closed:
            await self._http.close()

    # ------------------------------------------------------------------
    # Read helpers
    # ------------------------------------------------------------------

    async def get_basket_state(self) -> dict[str, Any]:
        """Read full basket state from chain: tokens, weights, NAV.

        Returns a dict matching the schema the orchestrator expects:
          {
            "tokens": {
              "SYMBOL": {
                "address": "0x...",
                "weight": 0.25,           # float 0-1
                "balance": 1234.56,       # human-readable token balance
                "price_usd": 3200.0,
                "value_usd": 394752.0,
                "liquidity_usd": 5000000, # from DexScreener
              },
              ...
            },
            "nav_usd": 200000.0,
          }
        """
        try:
            # Parallel on-chain reads
            token_addresses: list[str] = await self.basket.functions.getTokens().call()
            raw_weights: list[int] = await self.basket.functions.getWeights().call()
        except Exception as exc:
            logger.error("Failed reading basket tokens/weights from chain: %s", exc)
            raise

        if len(token_addresses) != len(raw_weights):
            raise ValueError(
                f"Token/weight length mismatch: {len(token_addresses)} vs {len(raw_weights)}"
            )

        # Build per-token metadata
        tokens: dict[str, dict[str, Any]] = {}
        total_nav_usd = 0.0

        for addr_raw, weight_bp in zip(token_addresses, raw_weights):
            addr = AsyncWeb3.to_checksum_address(addr_raw)

            # Read ERC-20 metadata + balance in basket
            erc20 = self.w3.eth.contract(address=addr, abi=ERC20_BALANCE_ABI)
            try:
                symbol, decimals, balance_raw = await self._multicall_erc20(
                    erc20, addr
                )
            except Exception as exc:
                logger.warning("ERC20 read failed for %s: %s", addr, exc)
                symbol = addr[:8]
                decimals = 18
                balance_raw = 0

            balance = balance_raw / (10**decimals)
            weight = weight_bp / 10_000  # basis points -> fraction

            # Price from DexScreener (Base chain)
            price_usd, liquidity_usd = await self._get_price(addr)

            value_usd = balance * price_usd
            total_nav_usd += value_usd

            tokens[symbol] = {
                "address": addr,
                "weight": weight,
                "balance": balance,
                "price_usd": price_usd,
                "value_usd": value_usd,
                "liquidity_usd": liquidity_usd,
            }

        logger.info(
            "Basket state: %d tokens, NAV=$%.2f", len(tokens), total_nav_usd
        )

        return {"tokens": tokens, "nav_usd": total_nav_usd}

    async def _multicall_erc20(
        self, erc20: AsyncContract, token_address: str
    ) -> tuple[str, int, int]:
        """Read symbol, decimals, and balanceOf(basket) for an ERC-20 token."""
        symbol: str = await erc20.functions.symbol().call()
        decimals: int = await erc20.functions.decimals().call()
        balance_raw: int = await erc20.functions.balanceOf(
            self.basket_address
        ).call()
        return symbol, decimals, balance_raw

    async def _get_price(self, token_address: str) -> tuple[float, float]:
        """Fetch price_usd and liquidity_usd for a token on Base from DexScreener.

        Returns (price_usd, liquidity_usd). Falls back to (0.0, 0.0) on error.
        """
        try:
            session = await self._ensure_http()
            url = f"{_DEXSCREENER_BASE_URL}/{token_address}"
            async with session.get(url) as resp:
                if resp.status != 200:
                    logger.warning(
                        "DexScreener returned %d for %s", resp.status, token_address
                    )
                    return 0.0, 0.0
                data = await resp.json()

            pairs = data.get("pairs") or []
            # Filter for Base chain pairs and pick the one with highest liquidity
            base_pairs = [
                p
                for p in pairs
                if p.get("chainId") == "base"
                and p.get("priceUsd") is not None
            ]
            if not base_pairs:
                # Fall back to any pair
                base_pairs = [p for p in pairs if p.get("priceUsd") is not None]

            if not base_pairs:
                logger.warning("No DexScreener pairs for %s", token_address)
                return 0.0, 0.0

            # Sort by liquidity descending and take the best
            best = max(
                base_pairs,
                key=lambda p: float(p.get("liquidity", {}).get("usd", 0) or 0),
            )
            price_usd = float(best.get("priceUsd", 0))
            liquidity_usd = float(
                best.get("liquidity", {}).get("usd", 0) or 0
            )
            return price_usd, liquidity_usd

        except Exception as exc:
            logger.warning("Price fetch failed for %s: %s", token_address, exc)
            return 0.0, 0.0

    # ------------------------------------------------------------------
    # Fee management
    # ------------------------------------------------------------------

    async def get_management_fee_accrued(self) -> float:
        """Read accrued management fee from the basket (in basket-token units)."""
        try:
            raw: int = await self.basket.functions.accruedManagementFee().call()
            # Assume basket token has 18 decimals (ERC-7621 standard)
            try:
                decimals: int = await self.basket.functions.decimals().call()
            except Exception:
                decimals = 18
            return raw / (10**decimals)
        except Exception as exc:
            logger.error("Failed reading accrued fee: %s", exc)
            raise

    async def collect_fees(self) -> Optional[str]:
        """Call collectManagementFee() on the basket contract.

        Returns the tx hash hex string, or None in dry-run mode.
        """
        if self.dry_run:
            fee = await self.get_management_fee_accrued()
            logger.info(
                "[DRY RUN] Would collect management fee (accrued: %.6f)", fee
            )
            return None

        self._require_wallet()

        try:
            tx = await self._build_and_send(
                self.basket.functions.collectManagementFee()
            )
            logger.info("Fee collection tx sent: %s", tx)
            return tx
        except Exception as exc:
            logger.error("Fee collection failed: %s", exc)
            raise

    # ------------------------------------------------------------------
    # Rebalance
    # ------------------------------------------------------------------

    async def rebalance(self, new_weights: dict[str, float]) -> Optional[str]:
        """Rebalance the basket to the given target weights.

        Args:
            new_weights: mapping of token_symbol -> target_weight (0.0-1.0).
                         Weights must sum to 1.0. Every token currently in the
                         basket must be present (removing tokens is not supported
                         in a single rebalance call).

        Returns:
            Transaction hash hex string, or None in dry-run mode.
        """
        # Validate weights sum ~1.0
        weight_sum = sum(new_weights.values())
        if abs(weight_sum - 1.0) > 0.001:
            raise ValueError(
                f"Weights must sum to 1.0 (got {weight_sum:.4f})"
            )

        # Read current basket to map symbols -> addresses
        current_state = await self.get_basket_state()
        current_tokens = current_state["tokens"]

        token_addresses: list[str] = []
        weight_bps: list[int] = []

        for symbol, target_weight in new_weights.items():
            if symbol not in current_tokens:
                raise ValueError(
                    f"Token {symbol} not in current basket. "
                    f"Available: {list(current_tokens.keys())}"
                )
            addr = current_tokens[symbol]["address"]
            token_addresses.append(AsyncWeb3.to_checksum_address(addr))
            weight_bps.append(int(round(target_weight * 10_000)))

        # Ensure basis points sum to 10_000
        bp_sum = sum(weight_bps)
        if bp_sum != 10_000:
            # Adjust the largest weight to correct rounding
            diff = 10_000 - bp_sum
            max_idx = weight_bps.index(max(weight_bps))
            weight_bps[max_idx] += diff

        if self.dry_run:
            logger.info(
                "[DRY RUN] Would rebalance basket to: %s",
                {s: f"{w:.2%}" for s, w in new_weights.items()},
            )
            logger.info(
                "[DRY RUN] Addresses: %s, BPS: %s", token_addresses, weight_bps
            )
            return None

        self._require_wallet()

        try:
            tx = await self._build_and_send(
                self.basket.functions.rebalance(token_addresses, weight_bps)
            )
            logger.info(
                "Rebalance tx sent: %s (weights: %s)", tx, new_weights
            )
            return tx
        except Exception as exc:
            logger.error("Rebalance failed: %s", exc)
            raise

    # ------------------------------------------------------------------
    # Transaction helpers
    # ------------------------------------------------------------------

    def _require_wallet(self) -> None:
        """Raise if the management wallet is not loaded."""
        if self.account is None:
            raise RuntimeError(
                "Management wallet not configured — set MANAGEMENT_WALLET_KEY"
            )

    async def _build_and_send(self, contract_fn: Any) -> str:
        """Build a transaction from a contract function call, estimate gas,
        sign, and broadcast.  Returns the tx hash hex string.
        """
        assert self.account is not None  # caller must check

        nonce = await self.w3.eth.get_transaction_count(self.account.address)

        # Fetch current gas prices (EIP-1559)
        latest_block = await self.w3.eth.get_block("latest")
        base_fee = latest_block.get("baseFeePerGas", 0)
        max_priority_fee = await self.w3.eth.max_priority_fee
        max_fee = base_fee * 2 + max_priority_fee

        tx_params: TxParams = {
            "from": self.account.address,
            "nonce": nonce,
            "chainId": BASE_CHAIN_ID,
            "maxFeePerGas": max_fee,
            "maxPriorityFeePerGas": max_priority_fee,
        }

        # Estimate gas with a 20% buffer
        try:
            gas_estimate = await contract_fn.estimate_gas(tx_params)
            tx_params["gas"] = int(gas_estimate * 1.2)
        except Exception as exc:
            logger.warning("Gas estimation failed (%s), using 300k default", exc)
            tx_params["gas"] = 300_000

        logger.info(
            "TX params: gas=%s, maxFee=%s gwei, nonce=%d",
            tx_params.get("gas"),
            max_fee / 10**9 if max_fee else "?",
            nonce,
        )

        # Build, sign, send
        built_tx = await contract_fn.build_transaction(tx_params)
        signed = self.account.sign_transaction(built_tx)
        tx_hash = await self.w3.eth.send_raw_transaction(signed.raw_transaction)
        hex_hash = tx_hash.hex()

        logger.info("Transaction broadcast: %s", hex_hash)

        # Wait for receipt (up to 120 seconds)
        try:
            receipt = await self.w3.eth.wait_for_transaction_receipt(
                tx_hash, timeout=120
            )
            if receipt["status"] == 0:
                raise RuntimeError(
                    f"Transaction reverted: {hex_hash} "
                    f"(gasUsed={receipt.get('gasUsed')})"
                )
            logger.info(
                "Transaction confirmed in block %d (gas used: %s)",
                receipt["blockNumber"],
                receipt.get("gasUsed"),
            )
        except Exception as exc:
            if "reverted" in str(exc).lower():
                raise
            logger.warning(
                "Could not confirm tx %s within timeout: %s", hex_hash, exc
            )

        return hex_hash
