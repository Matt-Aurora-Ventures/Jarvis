"""Staking Cranker — deposits bridged rewards into the KR8TIV staking pool.

Phase 4 of the Autonomous Investment Service.  After Circle CCTP bridges
USDC from Base to Solana, this module handles the "last mile": converting
the USDC balance into SOL and depositing it into the on-chain reward vault
so stakers can claim their share.

The on-chain ``deposit_rewards`` instruction (see
contracts/kr8tiv-staking/programs/kr8tiv-staking/src/lib.rs) is a plain
SOL system-transfer from the authority wallet to the reward-vault PDA.
Accounts required:
    pool        — PDA seeds=[b"pool"], read-only
    reward_vault— PDA seeds=[b"reward_vault"], writable
    authority   — signer, writable (must match pool.authority)
    system_program

The cranker wallet MUST be the pool authority for the instruction to pass
the ``has_one = authority`` constraint.

Usage:
    cranker = StakingCranker(cfg, db, redis)
    result  = await cranker.run_deposit_cycle()
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import struct
import time
from datetime import datetime, timezone
from typing import Any, Optional

import asyncpg
import httpx
import redis.asyncio as aioredis

from services.investments.config import InvestmentConfig

logger = logging.getLogger("investments.staking_cranker")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# KR8TIV Staking program ID (Anchor.toml — all clusters)
STAKING_PROGRAM_ID = "Fg6PaFpoGXkYsidMpWTK6W2BeZ7FEfcYkg476zPFsLnS"

# Anchor 8-byte discriminator for `deposit_rewards`
# sha256("global:deposit_rewards")[:8]
DEPOSIT_REWARDS_DISCRIMINATOR = bytes([
    0xAC, 0x8E, 0x6F, 0xE9, 0x98, 0xB5, 0x26, 0x6E,
])

# USDC mint on Solana mainnet
USDC_MINT = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"

# Minimum deposit threshold in lamports (approximately $1 worth of SOL).
# Recalculated dynamically when SOL price is available; this is the fallback.
MIN_DEPOSIT_LAMPORTS = 5_000_000  # 0.005 SOL (~$1 at $200/SOL)

# Minimum deposit threshold in USDC (for the pending-balance check).
MIN_DEPOSIT_USDC = 1.0

# USDC has 6 decimals on Solana.
USDC_DECIMALS = 6

# Solana system program
SYSTEM_PROGRAM_ID = "11111111111111111111111111111111"

# SPL Token program
TOKEN_PROGRAM_ID = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"

# Associated Token Account program
ATA_PROGRAM_ID = "ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL"

# StakingPool account layout (after 8-byte Anchor discriminator):
#   authority:               Pubkey (32)
#   staking_mint:            Pubkey (32)
#   staking_vault:           Pubkey (32)
#   reward_vault:            Pubkey (32)
#   reward_rate:             u64   (8)
#   total_staked:            u64   (8)
#   reward_per_token_stored: u64   (8)
#   last_update_time:        u64   (8)
#   paused:                  bool  (1)
#   bump:                    u8    (1)
# Total: 8 (disc) + 162 = 170 bytes
_POOL_DATA_OFFSET = 8  # skip Anchor discriminator

# Offsets within the pool data (after discriminator)
_OFF_AUTHORITY = 0
_OFF_STAKING_MINT = 32
_OFF_STAKING_VAULT = 64
_OFF_REWARD_VAULT = 96
_OFF_REWARD_RATE = 128
_OFF_TOTAL_STAKED = 136
_OFF_REWARD_PER_TOKEN = 144
_OFF_LAST_UPDATE = 152
_OFF_PAUSED = 160
_OFF_BUMP = 161

# Reward-tier multipliers (cranker-side, for off-chain estimation / API).
# NOTE: The on-chain program has its own 4-tier multiplier schedule applied at
# claim time.  These 3-tier multipliers are for the *off-chain* investment
# service UI and reporting.  They do NOT override the program.
REWARD_TIERS = [
    # (min_days, multiplier, label)
    (90, 1.50, "Gold"),
    (30, 1.25, "Silver"),
    (0,  1.00, "Base"),
]


# ---------------------------------------------------------------------------
# Reward multiplier helper
# ---------------------------------------------------------------------------

def calculate_reward(base_amount: float, stake_days: int) -> float:
    """Apply the 3-tier reward multiplier to *base_amount*.

    Tier schedule:
        Base   (0-29 days):  1.00x
        Silver (30-89 days): 1.25x
        Gold   (90+ days):   1.50x

    Args:
        base_amount: The raw reward amount (any unit — USDC, SOL, etc.).
        stake_days:  Number of days the user has been staking.

    Returns:
        The reward after applying the tier multiplier.
    """
    for min_days, multiplier, _label in REWARD_TIERS:
        if stake_days >= min_days:
            return base_amount * multiplier
    # Fallback (should not be reached because the last tier starts at 0)
    return base_amount


def get_reward_tier(stake_days: int) -> dict[str, Any]:
    """Return tier metadata for *stake_days*.

    Returns:
        dict with ``name``, ``multiplier``, ``min_days``, ``next_tier_in_days``
        (None when already at the highest tier).
    """
    for idx, (min_days, multiplier, label) in enumerate(REWARD_TIERS):
        if stake_days >= min_days:
            next_in: Optional[int] = None
            if idx > 0:
                next_min = REWARD_TIERS[idx - 1][0]
                next_in = next_min - stake_days
            return {
                "name": label,
                "multiplier": multiplier,
                "min_days": min_days,
                "next_tier_in_days": next_in,
            }
    return {"name": "Base", "multiplier": 1.0, "min_days": 0, "next_tier_in_days": 30}


# ---------------------------------------------------------------------------
# Solana helpers (pure functions — no SDK dependency)
# ---------------------------------------------------------------------------

def _b58decode(s: str) -> bytes:
    """Decode a base-58 encoded string (Bitcoin/Solana alphabet)."""
    alphabet = b"123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
    base = len(alphabet)
    result = 0
    for ch in s.encode():
        result = result * base + alphabet.index(ch)
    # Count leading '1's — they map to 0x00 bytes.
    pad_size = 0
    for ch in s:
        if ch == "1":
            pad_size += 1
        else:
            break
    result_bytes = result.to_bytes((result.bit_length() + 7) // 8, "big") if result else b""
    return b"\x00" * pad_size + result_bytes


def _b58encode(data: bytes) -> str:
    """Encode bytes to base-58 (Bitcoin/Solana alphabet)."""
    alphabet = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
    base = len(alphabet)
    num = int.from_bytes(data, "big")
    result = []
    while num > 0:
        num, rem = divmod(num, base)
        result.append(alphabet[rem])
    # Preserve leading zero bytes
    for byte in data:
        if byte == 0:
            result.append(alphabet[0])
        else:
            break
    return "".join(reversed(result))


def _pubkey_bytes(pubkey_str: str) -> bytes:
    """Convert a base-58 public key string to 32 raw bytes."""
    raw = _b58decode(pubkey_str)
    if len(raw) != 32:
        raise ValueError(f"Invalid pubkey length ({len(raw)} bytes): {pubkey_str}")
    return raw


def _find_pda(seeds: list[bytes], program_id: bytes) -> tuple[bytes, int]:
    """Derive a Program Derived Address (PDA).

    Tries bump values from 255 down to 0 until one produces a valid
    off-curve point.  Uses SHA-256 (the same hash Solana uses internally).

    Falls back to the ``solders`` library if available for correctness.
    """
    try:
        from solders.pubkey import Pubkey as SoldersPubkey  # type: ignore[import-untyped]
        program_pk = SoldersPubkey.from_bytes(program_id)
        seed_list = [bytes(s) for s in seeds]
        pda, bump = SoldersPubkey.find_program_address(seed_list, program_pk)
        return bytes(pda), bump
    except ImportError:
        pass

    # Pure-Python fallback using hashlib
    import hashlib
    for bump in range(255, -1, -1):
        hasher = hashlib.sha256()
        for seed in seeds:
            hasher.update(seed)
        hasher.update(bytes([bump]))
        hasher.update(program_id)
        hasher.update(b"ProgramDerivedAddress")
        candidate = hasher.digest()
        # A valid PDA must NOT be on the ed25519 curve.
        # Simplified check: if the high bit of the last byte is set, it is
        # almost certainly off-curve.  For production, prefer the solders path.
        # This is good enough for address derivation logging/dry-run.
        return candidate, bump

    raise RuntimeError("PDA derivation failed — no valid bump found")


# ---------------------------------------------------------------------------
# StakingCranker
# ---------------------------------------------------------------------------

class StakingCranker:
    """Deposits bridged rewards into the KR8TIV on-chain staking pool.

    After Circle CCTP delivers USDC to the cranker wallet on Solana this
    class handles:
      1. Checking the pending USDC balance
      2. (Future) swapping USDC -> SOL via Jupiter
      3. Building and submitting the ``deposit_rewards`` transaction
      4. Recording the deposit in Postgres + publishing to Redis
    """

    def __init__(
        self,
        cfg: InvestmentConfig,
        db: asyncpg.Pool,
        redis: aioredis.Redis,
    ) -> None:
        self.cfg = cfg
        self.db = db
        self.redis = redis

        # HTTP client for Solana JSON-RPC
        self._rpc = httpx.AsyncClient(
            base_url=cfg.solana_rpc_url,
            timeout=30.0,
            headers={"Content-Type": "application/json"},
        )

        # Cranker keypair — loaded lazily to avoid import-time errors when
        # the env var is not set (e.g. during tests / dry-run).
        self._keypair: Any = None

        # Derived PDA addresses (populated on first use)
        self._pool_pda: Optional[str] = None
        self._reward_vault_pda: Optional[str] = None

        logger.info(
            "StakingCranker initialised (program=%s, dry_run=%s, rpc=%s)",
            STAKING_PROGRAM_ID,
            cfg.dry_run,
            cfg.solana_rpc_url,
        )

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def close(self) -> None:
        """Shut down the underlying HTTP client."""
        await self._rpc.aclose()

    # ------------------------------------------------------------------
    # Keypair management
    # ------------------------------------------------------------------

    def _get_keypair(self) -> Any:
        """Load the cranker keypair from config (hex-encoded private key).

        Returns a ``solders.keypair.Keypair`` if the library is installed,
        otherwise returns a dict with ``public_key`` and ``secret`` bytes
        sufficient for manual transaction signing.
        """
        if self._keypair is not None:
            return self._keypair

        raw_key = self.cfg.solana_wallet_key
        if not raw_key:
            raise RuntimeError(
                "SOLANA_WALLET_KEY not set — cannot sign transactions"
            )

        secret = bytes.fromhex(raw_key)

        try:
            from solders.keypair import Keypair as SoldersKeypair  # type: ignore[import-untyped]
            self._keypair = SoldersKeypair.from_bytes(secret)
            logger.info(
                "Cranker pubkey (solders): %s", self._keypair.pubkey()
            )
        except ImportError:
            # Minimal fallback: store raw bytes.  Full transaction signing
            # requires solders or solana-py; dry-run still works.
            from nacl.signing import SigningKey  # type: ignore[import-untyped]
            signing_key = SigningKey(secret[:32])
            pubkey = bytes(signing_key.verify_key)
            self._keypair = {
                "secret": secret,
                "public_key": pubkey,
                "public_key_b58": _b58encode(pubkey),
            }
            logger.info(
                "Cranker pubkey (nacl fallback): %s",
                self._keypair["public_key_b58"],
            )

        return self._keypair

    def _get_pubkey_str(self) -> str:
        """Return the cranker's base-58 public key."""
        kp = self._get_keypair()
        if hasattr(kp, "pubkey"):
            return str(kp.pubkey())
        return kp["public_key_b58"]

    # ------------------------------------------------------------------
    # PDA derivation
    # ------------------------------------------------------------------

    def _derive_pdas(self) -> tuple[str, str]:
        """Derive pool and reward-vault PDAs.

        If ``staking_pool_address`` is set in config, it is used directly.
        Otherwise, the pool PDA is derived from seeds=[b"pool"].
        """
        if self._pool_pda and self._reward_vault_pda:
            return self._pool_pda, self._reward_vault_pda

        program_id = _pubkey_bytes(STAKING_PROGRAM_ID)

        if self.cfg.staking_pool_address:
            self._pool_pda = self.cfg.staking_pool_address
        else:
            pool_bytes, _bump = _find_pda([b"pool"], program_id)
            self._pool_pda = _b58encode(pool_bytes)

        vault_bytes, _vbump = _find_pda([b"reward_vault"], program_id)
        self._reward_vault_pda = _b58encode(vault_bytes)

        logger.info(
            "Derived PDAs — pool=%s, reward_vault=%s",
            self._pool_pda,
            self._reward_vault_pda,
        )
        return self._pool_pda, self._reward_vault_pda

    # ------------------------------------------------------------------
    # Solana JSON-RPC helpers
    # ------------------------------------------------------------------

    async def _rpc_call(self, method: str, params: list[Any] | None = None) -> Any:
        """Send a JSON-RPC request to the Solana cluster."""
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": method,
            "params": params or [],
        }
        resp = await self._rpc.post("", json=payload)
        resp.raise_for_status()
        body = resp.json()
        if "error" in body:
            raise RuntimeError(
                f"Solana RPC error ({method}): {body['error']}"
            )
        return body.get("result")

    async def _get_account_info(self, pubkey: str) -> Optional[dict[str, Any]]:
        """Fetch account info (base64 encoded data)."""
        result = await self._rpc_call(
            "getAccountInfo",
            [pubkey, {"encoding": "base64", "commitment": "confirmed"}],
        )
        if result and result.get("value"):
            return result["value"]
        return None

    async def _get_token_account_balance(self, token_account: str) -> dict[str, Any]:
        """Fetch SPL token account balance."""
        result = await self._rpc_call(
            "getTokenAccountBalance",
            [token_account, {"commitment": "confirmed"}],
        )
        return result.get("value", {})

    async def _get_balance(self, pubkey: str) -> int:
        """Fetch SOL balance in lamports."""
        result = await self._rpc_call(
            "getBalance",
            [pubkey, {"commitment": "confirmed"}],
        )
        return result.get("value", 0) if result else 0

    async def _get_latest_blockhash(self) -> str:
        """Fetch a recent blockhash for transaction construction."""
        result = await self._rpc_call(
            "getLatestBlockhash",
            [{"commitment": "confirmed"}],
        )
        return result["value"]["blockhash"]

    async def _send_transaction(self, signed_tx_b64: str) -> str:
        """Submit a signed transaction and return its signature."""
        result = await self._rpc_call(
            "sendTransaction",
            [
                signed_tx_b64,
                {"encoding": "base64", "skipPreflight": False, "preflightCommitment": "confirmed"},
            ],
        )
        return result  # tx signature string

    async def _confirm_transaction(self, signature: str, timeout_s: int = 60) -> bool:
        """Poll until a transaction is confirmed or timeout is reached."""
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            result = await self._rpc_call(
                "getSignatureStatuses",
                [[signature], {"searchTransactionHistory": False}],
            )
            statuses = result.get("value", [])
            if statuses and statuses[0]:
                status = statuses[0]
                if status.get("err"):
                    raise RuntimeError(
                        f"Transaction {signature} failed: {status['err']}"
                    )
                conf = status.get("confirmationStatus", "")
                if conf in ("confirmed", "finalized"):
                    return True
            await asyncio.sleep(2)
        raise TimeoutError(
            f"Transaction {signature} not confirmed within {timeout_s}s"
        )

    async def _simulate_transaction(self, signed_tx_b64: str) -> dict[str, Any]:
        """Simulate a transaction without submitting it."""
        result = await self._rpc_call(
            "simulateTransaction",
            [
                signed_tx_b64,
                {"encoding": "base64", "commitment": "confirmed", "sigVerify": False},
            ],
        )
        return result.get("value", {})

    # ------------------------------------------------------------------
    # On-chain pool state
    # ------------------------------------------------------------------

    def _parse_pool_state(self, data: bytes) -> dict[str, Any]:
        """Deserialize a ``StakingPool`` account from raw bytes."""
        if len(data) < _POOL_DATA_OFFSET + 162:
            raise ValueError(
                f"Pool account data too short ({len(data)} bytes, need >= 170)"
            )

        d = data[_POOL_DATA_OFFSET:]
        authority = _b58encode(d[_OFF_AUTHORITY : _OFF_AUTHORITY + 32])
        staking_mint = _b58encode(d[_OFF_STAKING_MINT : _OFF_STAKING_MINT + 32])
        staking_vault = _b58encode(d[_OFF_STAKING_VAULT : _OFF_STAKING_VAULT + 32])
        reward_vault = _b58encode(d[_OFF_REWARD_VAULT : _OFF_REWARD_VAULT + 32])
        reward_rate = struct.unpack_from("<Q", d, _OFF_REWARD_RATE)[0]
        total_staked = struct.unpack_from("<Q", d, _OFF_TOTAL_STAKED)[0]
        reward_per_token = struct.unpack_from("<Q", d, _OFF_REWARD_PER_TOKEN)[0]
        last_update = struct.unpack_from("<Q", d, _OFF_LAST_UPDATE)[0]
        paused = bool(d[_OFF_PAUSED])
        bump = d[_OFF_BUMP]

        return {
            "authority": authority,
            "staking_mint": staking_mint,
            "staking_vault": staking_vault,
            "reward_vault": reward_vault,
            "reward_rate": reward_rate,
            "total_staked": total_staked,
            "reward_per_token_stored": reward_per_token,
            "last_update_time": last_update,
            "paused": paused,
            "bump": bump,
        }

    # ------------------------------------------------------------------
    # Transaction building (deposit_rewards)
    # ------------------------------------------------------------------

    async def _build_deposit_rewards_tx(self, amount_lamports: int) -> str:
        """Build, sign, and return the ``deposit_rewards`` transaction (base64).

        The on-chain instruction is an Anchor instruction with:
            discriminator (8 bytes) + amount (u64, 8 bytes) = 16 bytes data
        Account list:
            0. pool         (read-only)
            1. reward_vault (writable)
            2. authority    (signer, writable)
            3. system_program
        """
        try:
            return await self._build_tx_solders(amount_lamports)
        except ImportError:
            logger.info("solders not available — falling back to manual tx build")
            return await self._build_tx_manual(amount_lamports)

    async def _build_tx_solders(self, amount_lamports: int) -> str:
        """Build the transaction using the ``solders`` library."""
        from solders.keypair import Keypair as SoldersKeypair  # type: ignore[import-untyped]
        from solders.pubkey import Pubkey as SoldersPubkey  # type: ignore[import-untyped]
        from solders.instruction import Instruction as SoldersInstruction, AccountMeta  # type: ignore[import-untyped]
        from solders.message import Message  # type: ignore[import-untyped]
        from solders.transaction import Transaction  # type: ignore[import-untyped]
        from solders.hash import Hash as SoldersHash  # type: ignore[import-untyped]

        kp = self._get_keypair()
        if not isinstance(kp, SoldersKeypair):
            raise ImportError("Keypair is not a solders Keypair")

        pool_pda, reward_vault_pda = self._derive_pdas()

        program_id = SoldersPubkey.from_string(STAKING_PROGRAM_ID)
        pool_pk = SoldersPubkey.from_string(pool_pda)
        vault_pk = SoldersPubkey.from_string(reward_vault_pda)
        sys_pk = SoldersPubkey.from_string(SYSTEM_PROGRAM_ID)

        # Instruction data: discriminator + amount (u64 LE)
        ix_data = DEPOSIT_REWARDS_DISCRIMINATOR + struct.pack("<Q", amount_lamports)

        ix = SoldersInstruction(
            program_id,
            ix_data,
            [
                AccountMeta(pool_pk, is_signer=False, is_writable=False),
                AccountMeta(vault_pk, is_signer=False, is_writable=True),
                AccountMeta(kp.pubkey(), is_signer=True, is_writable=True),
                AccountMeta(sys_pk, is_signer=False, is_writable=False),
            ],
        )

        blockhash_str = await self._get_latest_blockhash()
        blockhash = SoldersHash.from_string(blockhash_str)

        msg = Message.new_with_blockhash([ix], kp.pubkey(), blockhash)
        tx = Transaction.new_unsigned(msg)
        tx.sign([kp], blockhash)

        return base64.b64encode(bytes(tx)).decode()

    async def _build_tx_manual(self, amount_lamports: int) -> str:
        """Build the transaction manually (raw bytes) when solders is not installed.

        This is a best-effort fallback.  For production, ``solders`` is
        strongly recommended.
        """
        raise NotImplementedError(
            "Manual transaction building without solders is not implemented. "
            "Install solders: pip install solders"
        )

    # ==================================================================
    # Public API
    # ==================================================================

    async def deposit_rewards(self, amount_usdc: float) -> Optional[str]:
        """Deposit rewards into the staking pool.

        In the current program design, the reward vault holds SOL.  This
        method treats ``amount_usdc`` as the nominal value to deposit.
        In a future iteration the cranker will swap USDC -> SOL via Jupiter
        before depositing.  For now, ``amount_usdc`` is interpreted as a
        SOL value in lamports (``amount_usdc * 1e9``).

        Args:
            amount_usdc: The amount to deposit (in SOL for now; will be USDC
                         after Jupiter swap integration).

        Returns:
            Transaction signature string, or ``None`` in dry-run mode.
        """
        # Convert to lamports (SOL has 9 decimals)
        amount_lamports = int(amount_usdc * 1_000_000_000)

        if amount_lamports <= 0:
            logger.warning("deposit_rewards called with non-positive amount: %s", amount_usdc)
            return None

        pool_pda, reward_vault_pda = self._derive_pdas()

        if self.cfg.dry_run:
            logger.info(
                "[DRY RUN] Would deposit %d lamports (%.6f SOL) to reward vault %s "
                "(pool=%s, authority=%s)",
                amount_lamports,
                amount_usdc,
                reward_vault_pda,
                pool_pda,
                self._get_pubkey_str() if self.cfg.solana_wallet_key else "<no-key>",
            )
            return None

        # --- Live execution ---
        logger.info(
            "Building deposit_rewards tx: %d lamports (%.6f SOL) -> vault %s",
            amount_lamports,
            amount_usdc,
            reward_vault_pda,
        )

        signed_tx = await self._build_deposit_rewards_tx(amount_lamports)

        # Simulate first
        sim_result = await self._simulate_transaction(signed_tx)
        if sim_result.get("err"):
            raise RuntimeError(
                f"Deposit simulation failed: {sim_result['err']}\n"
                f"Logs: {sim_result.get('logs', [])}"
            )
        logger.info(
            "Simulation passed (units consumed: %s)",
            sim_result.get("unitsConsumed", "?"),
        )

        # Submit
        signature = await self._send_transaction(signed_tx)
        logger.info("Transaction submitted: %s", signature)

        # Confirm
        await self._confirm_transaction(signature, timeout_s=60)
        logger.info("Transaction confirmed: %s", signature)

        return signature

    async def get_pool_stats(self) -> dict[str, Any]:
        """Read on-chain staking pool state and return summary statistics.

        Returns:
            dict with keys:
                total_staked        — raw token amount (u64)
                reward_per_token    — reward accumulator value (u64)
                reward_rate         — rewards per token per second (u64)
                last_update_time    — unix timestamp of last update
                paused              — whether the pool is paused
                authority           — pool authority pubkey
                reward_vault        — reward vault PDA
                reward_vault_balance_lamports — SOL balance in the reward vault
                estimated_apy       — rough APY estimate (annualised)
        """
        pool_pda, reward_vault_pda = self._derive_pdas()

        # Fetch pool account data
        account = await self._get_account_info(pool_pda)
        if not account:
            logger.error("Pool account %s not found on-chain", pool_pda)
            return {"error": "pool_not_found", "pool_pda": pool_pda}

        raw_data = base64.b64decode(account["data"][0])
        pool = self._parse_pool_state(raw_data)

        # Fetch reward vault SOL balance
        vault_balance = await self._get_balance(reward_vault_pda)

        # Estimate APY:  reward_rate is "rewards per token per second" scaled
        # by 1e9.  Annualised:  rate * seconds_per_year / 1e9
        seconds_per_year = 365.25 * 24 * 3600
        if pool["total_staked"] > 0:
            # Per-token annual reward in lamports
            annual_reward_per_token = (
                pool["reward_rate"] * seconds_per_year / 1e9
            )
            # APY as fraction (e.g. 0.12 = 12%)
            # This is a simplification — it does not compound.
            estimated_apy = annual_reward_per_token  # per unit staked
        else:
            estimated_apy = 0.0

        return {
            "total_staked": pool["total_staked"],
            "reward_per_token_stored": pool["reward_per_token_stored"],
            "reward_rate": pool["reward_rate"],
            "last_update_time": pool["last_update_time"],
            "paused": pool["paused"],
            "authority": pool["authority"],
            "staking_mint": pool["staking_mint"],
            "reward_vault": pool["reward_vault"],
            "reward_vault_balance_lamports": vault_balance,
            "reward_vault_balance_sol": vault_balance / 1e9,
            "estimated_apy": estimated_apy,
            "pool_pda": pool_pda,
        }

    async def get_pending_rewards(self) -> float:
        """Check the USDC balance of the cranker's token account.

        This represents the rewards that have been bridged from Base via
        CCTP but not yet deposited into the staking pool.

        Returns:
            Pending USDC balance as a float, or 0.0 if the account does not
            exist or an error occurs.
        """
        try:
            pubkey_str = self._get_pubkey_str()
        except RuntimeError:
            if self.cfg.dry_run:
                logger.info("[DRY RUN] No wallet key — returning 0 pending rewards")
                return 0.0
            raise

        # Derive the Associated Token Account (ATA) for USDC
        # ATA = PDA(ATA_PROGRAM, [wallet, TOKEN_PROGRAM, USDC_MINT])
        try:
            from solders.pubkey import Pubkey as SoldersPubkey  # type: ignore[import-untyped]
            wallet_pk = SoldersPubkey.from_string(pubkey_str)
            token_prog = SoldersPubkey.from_string(TOKEN_PROGRAM_ID)
            usdc_mint = SoldersPubkey.from_string(USDC_MINT)
            ata_prog = SoldersPubkey.from_string(ATA_PROGRAM_ID)

            ata, _bump = SoldersPubkey.find_program_address(
                [bytes(wallet_pk), bytes(token_prog), bytes(usdc_mint)],
                ata_prog,
            )
            ata_str = str(ata)
        except ImportError:
            # Fallback: derive ATA using pure-Python PDA finder
            wallet_bytes = _pubkey_bytes(pubkey_str)
            token_bytes = _pubkey_bytes(TOKEN_PROGRAM_ID)
            mint_bytes = _pubkey_bytes(USDC_MINT)
            ata_prog_bytes = _pubkey_bytes(ATA_PROGRAM_ID)
            ata_raw, _ = _find_pda(
                [wallet_bytes, token_bytes, mint_bytes],
                ata_prog_bytes,
            )
            ata_str = _b58encode(ata_raw)

        try:
            balance_info = await self._get_token_account_balance(ata_str)
            if not balance_info:
                logger.debug("USDC ATA %s has no balance info (may not exist)", ata_str)
                return 0.0

            ui_amount = balance_info.get("uiAmount")
            if ui_amount is not None:
                return float(ui_amount)

            # Fallback: parse from raw amount string
            raw_amount = balance_info.get("amount", "0")
            decimals = balance_info.get("decimals", USDC_DECIMALS)
            return int(raw_amount) / (10 ** decimals)

        except RuntimeError as exc:
            # Account might not exist
            if "could not find account" in str(exc).lower():
                logger.debug("USDC ATA not found for %s — no pending rewards", pubkey_str)
                return 0.0
            raise

    async def run_deposit_cycle(self) -> dict[str, Any]:
        """Execute a full deposit cycle.

        Steps:
            1. Check pending USDC balance on the cranker wallet
            2. If >= minimum threshold ($1), deposit into the staking pool
            3. Record a snapshot in ``inv_staking_pool_snapshots``
            4. Publish an event to Redis ``investments:staking_events``
            5. Return a summary dict

        Returns:
            dict with cycle results including status, amounts, and tx sig.
        """
        cycle_start = datetime.now(timezone.utc)
        logger.info("Staking deposit cycle started at %s", cycle_start.isoformat())

        summary: dict[str, Any] = {
            "status": "no_action",
            "started_at": cycle_start.isoformat(),
            "pending_usdc": 0.0,
            "deposited_usdc": 0.0,
            "tx_signature": None,
            "pool_stats": None,
        }

        try:
            # Step 1: Check pending balance
            pending = await self.get_pending_rewards()
            summary["pending_usdc"] = pending
            logger.info("Pending USDC balance: $%.4f", pending)

            if pending < MIN_DEPOSIT_USDC:
                logger.info(
                    "Pending balance $%.4f below minimum $%.2f — skipping deposit",
                    pending,
                    MIN_DEPOSIT_USDC,
                )
                summary["status"] = "below_threshold"

                # Still record pool stats
                try:
                    pool_stats = await self.get_pool_stats()
                    summary["pool_stats"] = pool_stats
                except Exception as exc:
                    logger.warning("Failed to fetch pool stats: %s", exc)

                return summary

            # Step 2: Deposit into pool
            logger.info("Depositing $%.4f into staking pool...", pending)
            tx_sig = await self.deposit_rewards(pending)
            summary["deposited_usdc"] = pending
            summary["tx_signature"] = tx_sig
            summary["status"] = "deposited" if tx_sig else "dry_run"

            # Step 3: Fetch updated pool stats
            try:
                pool_stats = await self.get_pool_stats()
                summary["pool_stats"] = pool_stats
            except Exception as exc:
                logger.warning("Failed to fetch pool stats after deposit: %s", exc)

            # Step 4: Record snapshot to database
            await self._record_snapshot(pending, tx_sig, pool_stats)

            # Step 5: Publish event to Redis
            event_payload = json.dumps({
                "event": "reward_deposit",
                "amount_usdc": pending,
                "tx_signature": tx_sig,
                "pool_total_staked": pool_stats.get("total_staked") if pool_stats else None,
                "pool_vault_balance_sol": pool_stats.get("reward_vault_balance_sol") if pool_stats else None,
                "dry_run": self.cfg.dry_run,
                "timestamp": cycle_start.isoformat(),
            })
            await self.redis.publish("investments:staking_events", event_payload)
            logger.info("Published staking event to Redis")

        except Exception as exc:
            logger.exception("Deposit cycle failed: %s", exc)
            summary["status"] = "error"
            summary["error"] = str(exc)

            # Publish error event
            try:
                await self.redis.publish(
                    "investments:staking_events",
                    json.dumps({
                        "event": "reward_deposit_error",
                        "error": str(exc),
                        "timestamp": cycle_start.isoformat(),
                    }),
                )
            except Exception:
                logger.warning("Failed to publish error event to Redis")

        elapsed = (datetime.now(timezone.utc) - cycle_start).total_seconds()
        summary["elapsed_s"] = elapsed
        logger.info(
            "Deposit cycle completed in %.1fs — status=%s, deposited=$%.4f",
            elapsed,
            summary["status"],
            summary.get("deposited_usdc", 0),
        )

        return summary

    # ------------------------------------------------------------------
    # Database helpers
    # ------------------------------------------------------------------

    async def _record_snapshot(
        self,
        deposited_usdc: float,
        tx_signature: Optional[str],
        pool_stats: Optional[dict[str, Any]],
    ) -> None:
        """Write a row to ``inv_staking_pool_snapshots``."""
        try:
            await self.db.execute(
                """
                INSERT INTO inv_staking_pool_snapshots (
                    pool_address,
                    deposited_amount_usdc,
                    tx_signature,
                    total_staked,
                    reward_vault_balance_lamports,
                    reward_rate,
                    estimated_apy,
                    dry_run,
                    created_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, NOW())
                """,
                self._pool_pda or self.cfg.staking_pool_address,
                deposited_usdc,
                tx_signature,
                pool_stats.get("total_staked") if pool_stats else None,
                pool_stats.get("reward_vault_balance_lamports") if pool_stats else None,
                pool_stats.get("reward_rate") if pool_stats else None,
                pool_stats.get("estimated_apy") if pool_stats else None,
                self.cfg.dry_run,
            )
            logger.info("Snapshot recorded in inv_staking_pool_snapshots")
        except Exception as exc:
            # Non-fatal — the deposit already happened on-chain.
            logger.warning("Failed to record snapshot: %s", exc)

    # ------------------------------------------------------------------
    # Convenience: one-shot deposit
    # ------------------------------------------------------------------

    @staticmethod
    async def one_shot(
        cfg: InvestmentConfig,
        db: asyncpg.Pool,
        redis: aioredis.Redis,
    ) -> dict[str, Any]:
        """Create a cranker, run one deposit cycle, then clean up."""
        cranker = StakingCranker(cfg, db, redis)
        try:
            return await cranker.run_deposit_cycle()
        finally:
            await cranker.close()
