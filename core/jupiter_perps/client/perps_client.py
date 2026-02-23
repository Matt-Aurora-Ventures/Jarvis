"""Local AnchorPy Jupiter Perps client facade for execution and reconciliation."""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from solders.message import MessageV0
from solders.null_signer import NullSigner
from solders.pubkey import Pubkey
from solders.transaction import VersionedTransaction
from solana.rpc.async_api import AsyncClient
from solana.rpc.commitment import Confirmed
from spl.token.instructions import get_associated_token_address

from core.jupiter_perps.client.accounts.custody import Custody
from core.jupiter_perps.client.accounts.position import Position
from core.jupiter_perps.client.accounts.position_request import PositionRequest
from core.jupiter_perps.client.instructions.close_position_request2 import close_position_request2
from core.jupiter_perps.client.instructions.create_decrease_position_request2 import (
    create_decrease_position_request2,
)
from core.jupiter_perps.client.instructions.create_increase_position_market_request import (
    create_increase_position_market_request,
)
from core.jupiter_perps.client.program_id import PROGRAM_ID
from core.jupiter_perps.client.types import request_type as request_type_types
from core.jupiter_perps.client.types import side as side_types
from core.jupiter_perps.client.types.create_decrease_position_request2_params import (
    CreateDecreasePositionRequest2Params,
)
from core.jupiter_perps.client.types.create_increase_position_market_request_params import (
    CreateIncreasePositionMarketRequestParams,
)
from core.jupiter_perps.intent import CancelRequest, ClosePosition, CreateTPSL, ExecutionIntent, OpenPosition, ReducePosition, Side
from core.jupiter_perps.pda import (
    CUSTODY_MINTS,
    MAX_POSITION_SLOTS,
    derive_custody_pda,
    derive_perpetuals_pda,
    derive_pool_pda,
    derive_position_pda,
    derive_position_request_pda,
)

PROGRAM_ID_STR = "PERPHjGBqRHArX4DySjwM6UJHiR3sWAatqfdBS2qQJu"
ANCHOR_DISCRIMINATOR_SIZE = 8
USD_DECIMALS = int(os.environ.get("PERPS_USD_DECIMALS", "6"))
DEFAULT_REQUEST_COUNTER_SCAN = int(os.environ.get("PERPS_REQUEST_COUNTER_SCAN", "4096"))
DEFAULT_MARKET_CUSTODY_MINTS: dict[str, str] = {
    "SOL-USD": CUSTODY_MINTS["SOL"],
    "BTC-USD": CUSTODY_MINTS["BTC"],
    "ETH-USD": CUSTODY_MINTS["ETH"],
}

_REPO_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_IDL_PATH = _REPO_ROOT / "core" / "jupiter_perps" / "idl" / "jupiter_perps.json"


@dataclass(frozen=True)
class DecodedPosition:
    pda: str
    owner: str
    pool: str
    custody: str
    collateral_custody: str
    open_time: int
    update_time: int
    side: str
    price: float
    size_usd: float
    collateral_usd: float
    realised_pnl_usd: float
    cumulative_interest_snapshot: float
    locked_amount: int


def idl_path(path: str | Path | None = None) -> Path:
    return Path(path) if path else _DEFAULT_IDL_PATH


def load_local_idl(path: str | Path | None = None) -> dict[str, Any]:
    target = idl_path(path)
    if not target.exists():
        raise FileNotFoundError(f"IDL missing at {target}")
    return json.loads(target.read_text(encoding="utf-8-sig"))


def idl_sha256(path: str | Path | None = None) -> str:
    target = idl_path(path)
    return hashlib.sha256(target.read_bytes()).hexdigest()


def _has_generated_bindings() -> bool:
    instructions_dir = Path(__file__).with_name("instructions")
    accounts_dir = Path(__file__).with_name("accounts")
    types_dir = Path(__file__).with_name("types")
    return (
        instructions_dir.exists()
        and accounts_dir.exists()
        and types_dir.exists()
        and (instructions_dir / "create_increase_position_market_request.py").exists()
        and (instructions_dir / "create_decrease_position_request2.py").exists()
        and (instructions_dir / "close_position_request2.py").exists()
    )


def assert_live_ready() -> None:
    """Ensure local IDL and generated bindings exist for live mode."""
    try:
        import anchorpy  # noqa: F401
        import solders  # noqa: F401
        import solana  # noqa: F401
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"Live mode requires anchorpy/solders/solana: {exc}") from exc

    target = idl_path()
    if not target.exists():
        raise RuntimeError(f"IDL not found at {target}. Run python scripts/fetch_idl.py")

    if not _has_generated_bindings():
        raise RuntimeError(
            "Generated AnchorPy bindings are required for live execution. "
            "Run python scripts/generate_anchorpy_bindings.py"
        )


def _event_authority(program_id: Pubkey) -> Pubkey:
    pda, _ = Pubkey.find_program_address([b"__event_authority"], program_id)
    return pda


def _usd_to_u64(amount: float) -> int:
    if amount < 0:
        raise ValueError(f"USD amount must be non-negative, got {amount}")
    return int(round(amount * (10**USD_DECIMALS)))


def _resolve_market_custody_mint(market: str) -> str:
    mapping = dict(DEFAULT_MARKET_CUSTODY_MINTS)
    raw = os.environ.get("PERPS_MARKET_CUSTODY_MINTS_JSON", "").strip()
    if raw:
        overrides = json.loads(raw)
        if not isinstance(overrides, dict):
            raise RuntimeError("PERPS_MARKET_CUSTODY_MINTS_JSON must be an object mapping market->mint")
        mapping.update({str(k): str(v) for k, v in overrides.items()})

    custody_mint = mapping.get(market)
    if not custody_mint:
        raise RuntimeError(
            f"Unsupported live market mapping for '{market}'. "
            "Set PERPS_MARKET_CUSTODY_MINTS_JSON to include this market."
        )
    return custody_mint


def _side_enum(side: Side) -> side_types.SideKind:
    return side_types.Long() if side == Side.LONG else side_types.Short()


async def _find_first_free_position_slot(
    client: AsyncClient,
    owner: Pubkey,
    pool: Pubkey,
    custody: Pubkey,
    side: Side,
) -> tuple[int, Pubkey]:
    pdas = [derive_position_pda(owner, pool, custody, side.value, slot) for slot in range(MAX_POSITION_SLOTS)]
    accounts = (await client.get_multiple_accounts(pdas, commitment=Confirmed, encoding="base64")).value
    for slot, account in enumerate(accounts):
        if account is None:
            return slot, pdas[slot]
    raise RuntimeError("No free Jupiter position slots (all 9 are occupied)")


async def _find_free_request_counter(
    client: AsyncClient,
    owner: Pubkey,
    idempotency_key: str,
) -> int:
    digest = hashlib.sha256(idempotency_key.encode("utf-8")).digest()
    start = int.from_bytes(digest[:8], byteorder="little", signed=False)
    for offset in range(DEFAULT_REQUEST_COUNTER_SCAN):
        counter = (start + offset) & ((1 << 64) - 1)
        pda = derive_position_request_pda(owner, counter)
        info = await client.get_account_info(pda, commitment=Confirmed)
        if info.value is None:
            return counter
    raise RuntimeError(f"Unable to find free position request counter after {DEFAULT_REQUEST_COUNTER_SCAN} attempts")


def _unsigned_single_ix(owner: Pubkey, ix: Any, recent_blockhash: Any) -> bytes:
    msg = MessageV0.try_compile(
        payer=owner,
        instructions=[ix],
        address_lookup_table_accounts=[],
        recent_blockhash=recent_blockhash,
    )
    tx = VersionedTransaction(msg, [NullSigner(owner)])
    return bytes(tx)


async def build_transaction(intent: ExecutionIntent, wallet_address: str, rpc_url: str) -> bytes:
    """Route intent-specific transaction builders using local AnchorPy bindings."""
    assert_live_ready()

    if isinstance(intent, OpenPosition):
        return await build_open_position_tx(intent, wallet_address, rpc_url)
    if isinstance(intent, ReducePosition):
        return await build_reduce_position_tx(intent, wallet_address, rpc_url)
    if isinstance(intent, ClosePosition):
        return await build_close_position_tx(intent, wallet_address, rpc_url)
    if isinstance(intent, CreateTPSL):
        return await build_tpsl_tx(intent, wallet_address, rpc_url)
    if isinstance(intent, CancelRequest):
        return await build_cancel_request_tx(intent, wallet_address, rpc_url)

    raise ValueError(f"Unsupported intent class for transaction build: {type(intent).__name__}")


async def build_open_position_tx(intent: OpenPosition, wallet_address: str, rpc_url: str) -> bytes:
    owner = Pubkey.from_string(wallet_address)
    pool = derive_pool_pda()
    perpetuals = derive_perpetuals_pda()
    program_id = Pubkey.from_string(PROGRAM_ID_STR)
    event_authority = _event_authority(program_id)

    custody_mint = _resolve_market_custody_mint(intent.market)
    custody = derive_custody_pda(pool, custody_mint)
    collateral_custody = derive_custody_pda(pool, intent.collateral_mint.value)
    input_mint = Pubkey.from_string(intent.collateral_mint.value)

    if intent.collateral_mint.value not in {CUSTODY_MINTS["USDC"], CUSTODY_MINTS["USDT"]}:
        raise RuntimeError(
            "Live OpenPosition currently supports stable collateral only (USDC/USDT). "
            "Use PERPS_MARKET_CUSTODY_MINTS_JSON overrides and account adapters for other mints."
        )

    async with AsyncClient(rpc_url, commitment=Confirmed) as client:
        _, position = await _find_first_free_position_slot(client, owner, pool, custody, intent.side)
        counter = await _find_free_request_counter(client, owner, intent.idempotency_key)
        position_request = derive_position_request_pda(owner, counter)
        position_request_ata = get_associated_token_address(position_request, input_mint)
        funding_account = get_associated_token_address(owner, input_mint)
        blockhash = (await client.get_latest_blockhash(commitment=Confirmed)).value.blockhash

    params = CreateIncreasePositionMarketRequestParams(
        size_usd_delta=_usd_to_u64(intent.size_usd),
        collateral_token_delta=_usd_to_u64(intent.collateral_amount_usd),
        side=_side_enum(intent.side),
        price_slippage=int(intent.max_slippage_bps),
        jupiter_minimum_out=None,
        counter=counter,
    )

    ix = create_increase_position_market_request(
        args={"params": params},
        accounts={
            "owner": owner,
            "funding_account": funding_account,
            "perpetuals": perpetuals,
            "pool": pool,
            "position": position,
            "position_request": position_request,
            "position_request_ata": position_request_ata,
            "custody": custody,
            "collateral_custody": collateral_custody,
            "input_mint": input_mint,
            "referral": None,
            "event_authority": event_authority,
            "program": program_id,
        },
    )

    return _unsigned_single_ix(owner, ix, blockhash)


async def _load_position_context(
    client: AsyncClient,
    position_pda: Pubkey,
    program_id: Pubkey,
) -> tuple[Position, Custody, Custody]:
    position = await Position.fetch(client, position_pda, commitment=Confirmed, program_id=program_id)
    if position is None:
        raise RuntimeError(f"Position account not found: {position_pda}")

    custody = await Custody.fetch(client, position.custody, commitment=Confirmed, program_id=program_id)
    if custody is None:
        raise RuntimeError(f"Custody account not found: {position.custody}")

    collateral_custody = await Custody.fetch(
        client,
        position.collateral_custody,
        commitment=Confirmed,
        program_id=program_id,
    )
    if collateral_custody is None:
        raise RuntimeError(f"Collateral custody account not found: {position.collateral_custody}")

    return position, custody, collateral_custody


async def _build_decrease_request_tx(
    *,
    owner: Pubkey,
    position_pda: Pubkey,
    size_usd_delta: int,
    collateral_usd_delta: int,
    max_slippage_bps: int,
    entire_position: bool,
    idempotency_key: str,
    rpc_url: str,
    trigger_price: int | None = None,
    trigger_above_threshold: bool | None = None,
) -> bytes:
    program_id = Pubkey.from_string(PROGRAM_ID_STR)
    event_authority = _event_authority(program_id)
    perpetuals = derive_perpetuals_pda()

    async with AsyncClient(rpc_url, commitment=Confirmed) as client:
        position, custody, collateral_custody = await _load_position_context(client, position_pda, program_id)
        if position.owner != owner:
            raise RuntimeError(f"Position owner mismatch: expected {owner}, found {position.owner}")

        counter = await _find_free_request_counter(client, owner, idempotency_key)
        position_request = derive_position_request_pda(owner, counter)
        desired_mint = collateral_custody.mint
        receiving_account = get_associated_token_address(owner, desired_mint)
        position_request_ata = get_associated_token_address(position_request, desired_mint)
        blockhash = (await client.get_latest_blockhash(commitment=Confirmed)).value.blockhash

    # Use Trigger request type when trigger_price is provided (on-chain TP/SL),
    # otherwise Market for immediate execution.
    if trigger_price is not None:
        req_type = request_type_types.Trigger()
    else:
        req_type = request_type_types.Market()

    params = CreateDecreasePositionRequest2Params(
        collateral_usd_delta=collateral_usd_delta,
        size_usd_delta=size_usd_delta,
        request_type=req_type,
        price_slippage=int(max_slippage_bps),
        jupiter_minimum_out=None,
        trigger_price=trigger_price,
        trigger_above_threshold=trigger_above_threshold,
        entire_position=entire_position,
        counter=counter,
    )

    ix = create_decrease_position_request2(
        args={"params": params},
        accounts={
            "owner": owner,
            "receiving_account": receiving_account,
            "perpetuals": perpetuals,
            "pool": position.pool,
            "position": position_pda,
            "position_request": position_request,
            "position_request_ata": position_request_ata,
            "custody": position.custody,
            "custody_doves_price_account": custody.doves_oracle,
            "custody_pythnet_price_account": custody.oracle.oracle_account,
            "collateral_custody": position.collateral_custody,
            "desired_mint": desired_mint,
            "referral": None,
            "event_authority": event_authority,
            "program": program_id,
        },
    )

    return _unsigned_single_ix(owner, ix, blockhash)


async def build_reduce_position_tx(intent: ReducePosition, wallet_address: str, rpc_url: str) -> bytes:
    owner = Pubkey.from_string(wallet_address)
    position_pda = Pubkey.from_string(intent.position_pda)
    return await _build_decrease_request_tx(
        owner=owner,
        position_pda=position_pda,
        size_usd_delta=_usd_to_u64(intent.reduce_size_usd),
        collateral_usd_delta=0,
        max_slippage_bps=int(intent.max_slippage_bps),
        entire_position=False,
        idempotency_key=intent.idempotency_key,
        rpc_url=rpc_url,
    )


async def build_close_position_tx(intent: ClosePosition, wallet_address: str, rpc_url: str) -> bytes:
    owner = Pubkey.from_string(wallet_address)
    position_pda = Pubkey.from_string(intent.position_pda)

    async with AsyncClient(rpc_url, commitment=Confirmed) as client:
        position, _, _ = await _load_position_context(client, position_pda, Pubkey.from_string(PROGRAM_ID_STR))
        size_usd_delta = int(position.size_usd)

    return await _build_decrease_request_tx(
        owner=owner,
        position_pda=position_pda,
        size_usd_delta=size_usd_delta,
        collateral_usd_delta=0,
        max_slippage_bps=int(intent.max_slippage_bps),
        entire_position=True,
        idempotency_key=intent.idempotency_key,
        rpc_url=rpc_url,
    )


async def build_tpsl_tx(intent: CreateTPSL, wallet_address: str, rpc_url: str) -> bytes:
    """Build an on-chain TP/SL trigger order via create_decrease_position_request2.

    Creates a PositionRequest PDA with requestType=Trigger. Jupiter's keepers
    monitor this on-chain and execute when the oracle price crosses trigger_price.
    Only the owner signature is required at creation time.
    """
    owner = Pubkey.from_string(wallet_address)
    position_pda = Pubkey.from_string(intent.position_pda)

    # trigger_price is stored on-chain as u64 with USD_DECIMALS precision
    trigger_price_u64 = _usd_to_u64(intent.trigger_price)

    # size_usd_delta: for entire_position=True we still need the position's size
    # For partial closes, use the intent's size_usd
    if intent.entire_position:
        async with AsyncClient(rpc_url, commitment=Confirmed) as client:
            position, _, _ = await _load_position_context(
                client, position_pda, Pubkey.from_string(PROGRAM_ID_STR)
            )
            size_usd_delta = int(position.size_usd)
    else:
        size_usd_delta = _usd_to_u64(intent.size_usd)

    return await _build_decrease_request_tx(
        owner=owner,
        position_pda=position_pda,
        size_usd_delta=size_usd_delta,
        collateral_usd_delta=0,
        max_slippage_bps=300,  # wider slippage for trigger orders (3%)
        entire_position=intent.entire_position,
        idempotency_key=intent.idempotency_key,
        rpc_url=rpc_url,
        trigger_price=trigger_price_u64,
        trigger_above_threshold=intent.trigger_above_threshold,
    )


async def build_cancel_request_tx(intent: CancelRequest, wallet_address: str, rpc_url: str) -> bytes:
    owner = Pubkey.from_string(wallet_address)
    request_pda = Pubkey.from_string(intent.request_pda)
    program_id = Pubkey.from_string(PROGRAM_ID_STR)
    event_authority = _event_authority(program_id)

    async with AsyncClient(rpc_url, commitment=Confirmed) as client:
        request = await PositionRequest.fetch(client, request_pda, commitment=Confirmed, program_id=program_id)
        if request is None:
            raise RuntimeError(f"Position request not found: {request_pda}")
        if request.owner != owner:
            raise RuntimeError(f"Request owner mismatch: expected {owner}, found {request.owner}")

        owner_ata = get_associated_token_address(owner, request.mint)
        request_ata = get_associated_token_address(request_pda, request.mint)
        blockhash = (await client.get_latest_blockhash(commitment=Confirmed)).value.blockhash

    ix = close_position_request2(
        accounts={
            "keeper": None,
            "owner": owner,
            "owner_ata": owner_ata,
            "pool": request.pool,
            "position_request": request_pda,
            "position_request_ata": request_ata,
            "position": request.position,
            "mint": request.mint,
            "event_authority": event_authority,
            "program": program_id,
        },
    )
    return _unsigned_single_ix(owner, ix, blockhash)


def decode_position(pda: str, data: bytes) -> DecodedPosition:
    """Decode a Position account for reconciliation without JS SDK dependencies."""
    parsed = Position.decode(data)
    side = "long" if getattr(parsed.side, "kind", "") == "Long" else "short"
    return DecodedPosition(
        pda=pda,
        owner=str(parsed.owner),
        pool=str(parsed.pool),
        custody=str(parsed.custody),
        collateral_custody=str(parsed.collateral_custody),
        open_time=int(parsed.open_time),
        update_time=int(parsed.update_time),
        side=side,
        price=float(parsed.price),
        size_usd=float(parsed.size_usd),
        collateral_usd=float(parsed.collateral_usd),
        realised_pnl_usd=float(parsed.realised_pnl_usd),
        cumulative_interest_snapshot=float(parsed.cumulative_interest_snapshot),
        locked_amount=int(parsed.locked_amount),
    )
