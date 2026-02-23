"""
pda.py — Deterministic PDA derivation for Jupiter Perps on-chain accounts.

All derivations match the Jupiter Perps Anchor program on mainnet:
    PERPHjGBqRHArX4DySjwM6UJHiR3sWAatqfdBS2qQJu

Jupiter Perps uses 9 position PDA seeds per wallet (custody slots 0–8).
Each slot corresponds to one open position. When all 9 are occupied, no
new positions can be opened until one is closed.

Reference:
    https://github.com/julianfssen/jupiter-perps-anchor-idl-parsing
    https://dev.jup.ag/docs/perps

Account PDAs:
    - Perpetuals: ["perpetuals"] → singleton config account
    - Pool: ["pool", pool_name] → per-pool custody pool
    - Custody: ["custody", pool_pda, custody_token_mint]
    - Position: ["position", owner, pool_pda, custody_pda, side, position_slot]
    - PositionRequest: ["position_request", owner, counter]
"""

import struct
from typing import Literal

try:
    from solders.pubkey import Pubkey
    _HAS_SOLDERS = True
except ImportError:
    _HAS_SOLDERS = False

# Program IDs
JUPITER_PERPS_PROGRAM_ID = "PERPHjGBqRHArX4DySjwM6UJHiR3sWAatqfdBS2qQJu"

# Pool and custody constants (mainnet)
JLP_POOL_NAME = "JLP"
POOL_NAMES = {"JLP"}

# Custody token mints (mainnet)
CUSTODY_MINTS = {
    "SOL": "So11111111111111111111111111111111111111112",
    "BTC": "9n4nbM75f5Ui33ZbPYXn59EwSgE8CGsHtAeTH5YFeJ9E",
    "ETH": "7vfCXTUXx5WJV5JADk17DUJ4ksgau7utNKj4b963voxs",
    "USDC": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
    "USDT": "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB",
}

# Side discriminators used in PDA seeds
SIDE_LONG_SEED = b"\x00"   # 0 = long
SIDE_SHORT_SEED = b"\x01"  # 1 = short

# Max concurrent positions per wallet
MAX_POSITION_SLOTS = 9


def _program_id() -> "Pubkey":
    if not _HAS_SOLDERS:
        raise ImportError("solders is required for PDA derivation")
    return Pubkey.from_string(JUPITER_PERPS_PROGRAM_ID)


def derive_perpetuals_pda() -> "Pubkey":
    """
    Derive the singleton Perpetuals config account PDA.
    Seeds: ["perpetuals"]
    """
    program_id = _program_id()
    seeds = [b"perpetuals"]
    pda, _ = Pubkey.find_program_address(seeds, program_id)
    return pda


def derive_pool_pda(pool_name: str = JLP_POOL_NAME) -> "Pubkey":
    """
    Derive the pool PDA.
    Seeds: ["pool", pool_name_bytes]
    """
    program_id = _program_id()
    seeds = [b"pool", pool_name.encode("utf-8")]
    pda, _ = Pubkey.find_program_address(seeds, program_id)
    return pda


def derive_custody_pda(
    pool_pda: "Pubkey",
    custody_mint: str,
) -> "Pubkey":
    """
    Derive a custody account PDA for a given token mint.
    Seeds: ["custody", pool_pda_bytes, custody_mint_bytes]
    """
    program_id = _program_id()
    mint_pubkey = Pubkey.from_string(custody_mint)
    seeds = [b"custody", bytes(pool_pda), bytes(mint_pubkey)]
    pda, _ = Pubkey.find_program_address(seeds, program_id)
    return pda


def derive_position_pda(
    owner: "Pubkey",
    pool_pda: "Pubkey",
    custody_pda: "Pubkey",
    side: Literal["long", "short"],
    slot: int,
) -> "Pubkey":
    """
    Derive a Position account PDA for a specific slot (0–8).

    Seeds: ["position", owner_bytes, pool_pda_bytes, custody_pda_bytes, side_byte, slot_byte]

    Args:
        owner: The trader's wallet pubkey
        pool_pda: The pool PDA (from derive_pool_pda)
        custody_pda: The custody PDA for the position's token
        side: "long" or "short"
        slot: Position slot 0–8 (Jupiter supports up to 9 concurrent positions)

    Returns:
        The deterministic Position account PDA
    """
    if slot < 0 or slot >= MAX_POSITION_SLOTS:
        raise ValueError(f"Position slot must be 0–{MAX_POSITION_SLOTS - 1}, got {slot}")

    program_id = _program_id()
    side_byte = SIDE_LONG_SEED if side == "long" else SIDE_SHORT_SEED
    slot_byte = struct.pack("B", slot)

    seeds = [
        b"position",
        bytes(owner),
        bytes(pool_pda),
        bytes(custody_pda),
        side_byte,
        slot_byte,
    ]
    pda, _ = Pubkey.find_program_address(seeds, program_id)
    return pda


def enumerate_all_position_pdas(
    owner: "Pubkey",
    pool_pda: "Pubkey",
    custody_pdas: dict[str, "Pubkey"],
    side: Literal["long", "short"],
) -> list[dict]:
    """
    Enumerate all 9 Position PDAs for a given owner/pool/custody/side combo.

    Returns list of dicts: {"pda": str, "slot": int, "side": str, "custody_symbol": str}
    """
    results = []
    for symbol, custody_pda in custody_pdas.items():
        for slot in range(MAX_POSITION_SLOTS):
            pda = derive_position_pda(owner, pool_pda, custody_pda, side, slot)
            results.append(
                {
                    "pda": str(pda),
                    "slot": slot,
                    "side": side,
                    "custody_symbol": symbol,
                }
            )
    return results


def derive_position_request_pda(
    owner: "Pubkey",
    counter: int,
) -> "Pubkey":
    """
    Derive a PositionRequest PDA for a pending open/close order.

    Seeds: ["position_request", owner_bytes, counter_le_u64]

    Args:
        owner: The trader's wallet pubkey
        counter: The request counter (monotonically increasing per wallet)
    """
    program_id = _program_id()
    counter_bytes = struct.pack("<Q", counter)  # little-endian u64
    seeds = [b"position_request", bytes(owner), counter_bytes]
    pda, _ = Pubkey.find_program_address(seeds, program_id)
    return pda


def get_all_custody_pdas(pool_pda: "Pubkey") -> dict[str, "Pubkey"]:
    """Return all custody PDAs for the JLP pool."""
    return {
        symbol: derive_custody_pda(pool_pda, mint)
        for symbol, mint in CUSTODY_MINTS.items()
    }


def build_full_pda_map(owner_address: str) -> dict:
    """
    Build a complete map of all PDAs for a wallet.
    Used by the reconciliation loop.

    Returns:
        {
          "perpetuals": str,
          "pool": str,
          "custodies": {"SOL": str, "BTC": str, ...},
          "position_pdas": [{"pda": str, "slot": int, "side": str, "custody_symbol": str}, ...]
        }
    """
    owner = Pubkey.from_string(owner_address)
    perpetuals = derive_perpetuals_pda()
    pool = derive_pool_pda()
    custodies = get_all_custody_pdas(pool)

    position_pdas = []
    for side in ("long", "short"):
        position_pdas.extend(
            enumerate_all_position_pdas(owner, pool, custodies, side)  # type: ignore[arg-type]
        )

    return {
        "perpetuals": str(perpetuals),
        "pool": str(pool),
        "custodies": {sym: str(pda) for sym, pda in custodies.items()},
        "position_pdas": position_pdas,
    }
