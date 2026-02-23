"""10-second chain reconciliation loop for Jupiter Perps."""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
import time
import urllib.request
from typing import Any

from core.jupiter_perps.event_journal import EventJournal
from core.jupiter_perps.pda import (
    CUSTODY_MINTS,
    MAX_POSITION_SLOTS,
    derive_custody_pda,
    derive_pool_pda,
    derive_position_pda,
    derive_position_request_pda,
)

log = logging.getLogger(__name__)

_HELIUS_RPC = os.environ.get("HELIUS_RPC_URL", "https://api.mainnet-beta.solana.com")
_WALLET_ADDRESS = os.environ.get("PERPS_WALLET_ADDRESS", "")
_TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
_TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_BUY_BOT_CHAT_ID", "")
_RECONCILE_INTERVAL = int(os.environ.get("PERPS_RECONCILE_INTERVAL", "10"))
_MAX_REQUEST_COUNTER_SCAN = int(os.environ.get("PERPS_MAX_REQUEST_COUNTER_SCAN", "64"))
# Anchor discriminator = sha256("account:Position")[:8]
# Computed via: hashlib.sha256(b"account:Position").digest()[:8]
_POSITION_DISCRIMINATOR = b"\x94\xa6\x0b[\xbf\xa2&\xe6"
_POSITION_REQUEST_DISCRIMINATOR = b"\x0c&\xfa\xc7.\x9a \xd8"
_USD_DECIMALS = int(os.environ.get("PERPS_USD_DECIMALS", "6"))


def _json_event(event: str, **fields: Any) -> None:
    payload = {
        "event": event,
        "timestamp": int(time.time()),
        **fields,
    }
    log.info(json.dumps(payload, sort_keys=True, separators=(",", ":")))


def _post_json_sync(url: str, payload: dict[str, str]) -> None:
    encoded = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=encoded,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=10):  # noqa: S310
        return


async def fetch_multiple_accounts(
    pda_addresses: list[str],
    rpc_url: str,
    batch_size: int = 100,
) -> dict[str, bytes | None]:
    """Fetch account data via getMultipleAccounts with confirmed commitment."""
    from solana.rpc.async_api import AsyncClient  # noqa: PLC0415
    from solana.rpc.commitment import Confirmed  # noqa: PLC0415
    from solders.pubkey import Pubkey  # noqa: PLC0415

    if not pda_addresses:
        return {}

    results: dict[str, bytes | None] = {}

    async with AsyncClient(rpc_url, commitment=Confirmed) as client:
        for start in range(0, len(pda_addresses), batch_size):
            batch = pda_addresses[start : start + batch_size]
            try:
                pubkeys = [Pubkey.from_string(addr) for addr in batch]
                response = await client.get_multiple_accounts(
                    pubkeys,
                    commitment=Confirmed,
                    encoding="base64",
                )
            except Exception as exc:  # noqa: BLE001
                _json_event("reconcile_rpc_error", error=str(exc), batch_size=len(batch))
                for addr in batch:
                    results[addr] = None
                continue

            accounts = response.value
            for addr, account in zip(batch, accounts, strict=False):
                if account is None:
                    results[addr] = None
                    continue
                data = getattr(account, "data", None)
                if isinstance(data, (bytes, bytearray)):
                    results[addr] = bytes(data)
                    continue
                if isinstance(data, (tuple, list)) and data:
                    raw = data[0]
                    if isinstance(raw, str):
                        results[addr] = base64.b64decode(raw)
                        continue
                results[addr] = None

    return results


def _enumerate_position_targets(wallet_address: str) -> list[str]:
    if not wallet_address:
        return []

    from solders.pubkey import Pubkey  # noqa: PLC0415

    owner = Pubkey.from_string(wallet_address)
    pool = derive_pool_pda()

    targets: list[str] = []
    for mint in CUSTODY_MINTS.values():
        custody = derive_custody_pda(pool, mint)
        for side in ("long", "short"):
            for slot in range(MAX_POSITION_SLOTS):
                pda = derive_position_pda(owner, pool, custody, side, slot)  # type: ignore[arg-type]
                targets.append(str(pda))
    return targets


def _enumerate_request_targets(wallet_address: str, max_counter_scan: int) -> list[str]:
    if not wallet_address:
        return []

    from solders.pubkey import Pubkey  # noqa: PLC0415

    owner = Pubkey.from_string(wallet_address)
    return [str(derive_position_request_pda(owner, counter)) for counter in range(max_counter_scan)]


def _decode_chain_positions(accounts: dict[str, bytes | None]) -> list[dict[str, Any]]:
    positions: list[dict[str, Any]] = []
    for pda, raw in accounts.items():
        if raw is None or len(raw) < 8:
            continue
        if raw[:8] != _POSITION_DISCRIMINATOR:
            continue
        try:
            # Try AnchorPy-generated decoder first (requires client-gen to have run)
            try:
                from core.jupiter_perps.client import perps_client  # noqa: PLC0415
                decoded = perps_client.decode_position(pda, raw)
                positions.append(
                    {
                        "pda": decoded.pda,
                        "owner": decoded.owner,
                        "side": decoded.side,
                        "size_usd": float(decoded.size_usd),
                    }
                )
            except (ImportError, AttributeError):
                # AnchorPy client not yet generated — record PDA as open with partial data.
                # Run: python scripts/gen_client.py  to generate full decoder.
                # Chain truth is still recorded; size_usd=0 flags it for manual review.
                log.warning(
                    "AnchorPy client not available — partial decode for %s. "
                    "Run: python scripts/gen_client.py",
                    pda[:20],
                )
                positions.append(
                    {
                        "pda": pda,
                        "owner": "unknown",
                        "side": "unknown",
                        "size_usd": 0.0,
                        "partial_decode": True,
                    }
                )
        except Exception as exc:  # noqa: BLE001
            _json_event("reconcile_decode_error", pda=pda, error=str(exc))
    return positions


def _decode_chain_requests(accounts: dict[str, bytes | None]) -> list[dict[str, Any]]:
    """Decode PositionRequest accounts and classify as Market or Trigger (TP/SL)."""
    requests: list[dict[str, Any]] = []
    for pda, raw in accounts.items():
        if raw is None or len(raw) < 8:
            continue
        if raw[:8] != _POSITION_REQUEST_DISCRIMINATOR:
            continue
        try:
            from core.jupiter_perps.client.accounts.position_request import PositionRequest  # noqa: PLC0415
            decoded = PositionRequest.decode(raw)
            req_kind = getattr(decoded.request_type, "kind", "Unknown")
            trigger_price = None
            if decoded.trigger_price is not None:
                trigger_price = float(decoded.trigger_price) / (10 ** _USD_DECIMALS)
            requests.append({
                "pda": pda,
                "position": str(decoded.position),
                "request_type": req_kind,  # "Market" or "Trigger"
                "trigger_price": trigger_price,
                "trigger_above_threshold": decoded.trigger_above_threshold,
                "entire_position": decoded.entire_position,
                "executed": decoded.executed,
                "size_usd_delta": float(decoded.size_usd_delta) / (10 ** _USD_DECIMALS),
            })
        except (ImportError, AttributeError):
            # AnchorPy client not available — record PDA as active request with minimal data
            requests.append({
                "pda": pda,
                "position": "unknown",
                "request_type": "Unknown",
                "trigger_price": None,
                "trigger_above_threshold": None,
                "entire_position": None,
                "executed": False,
                "size_usd_delta": 0.0,
                "partial_decode": True,
            })
        except Exception as exc:  # noqa: BLE001
            _json_event("reconcile_request_decode_error", pda=pda, error=str(exc))
    return requests


def _classify_discrepancies(chain_positions: list[dict[str, Any]], db_positions: list[dict[str, Any]]) -> list[dict[str, str]]:
    chain_by_pda = {pos["pda"]: pos for pos in chain_positions if pos.get("pda")}
    db_by_pda = {pos.get("pda"): pos for pos in db_positions if pos.get("pda")}

    discrepancies: list[dict[str, str]] = []

    for pda, chain_pos in chain_by_pda.items():
        if pda not in db_by_pda:
            discrepancies.append(
                {
                    "type": "GHOST",
                    "pda": pda,
                    "detail": "position exists on-chain but not in projection",
                }
            )
            continue

        db_pos = db_by_pda[pda]
        chain_side = str(chain_pos.get("side", ""))
        db_side = str(db_pos.get("side", ""))
        chain_size = float(chain_pos.get("size_usd", 0.0))
        db_size = float(db_pos.get("size_usd", 0.0))

        if chain_side != db_side or abs(chain_size - db_size) > 0.01:
            discrepancies.append(
                {
                    "type": "MISMATCH",
                    "pda": pda,
                    "detail": (
                        f"chain(side={chain_side},size={chain_size}) "
                        f"!= db(side={db_side},size={db_size})"
                    ),
                }
            )

    for pda in db_by_pda:
        if pda not in chain_by_pda:
            discrepancies.append(
                {
                    "type": "ZOMBIE",
                    "pda": str(pda),
                    "detail": "position exists in projection but not on-chain",
                }
            )

    return discrepancies


async def _alert_operator(discrepancies: list[dict[str, str]]) -> None:
    if not _TELEGRAM_BOT_TOKEN or not _TELEGRAM_CHAT_ID:
        return

    lines = ["PERPS reconciliation discrepancy detected"]
    for item in discrepancies[:10]:
        lines.append(f"[{item['type']}] {item['pda'][:24]} {item['detail'][:120]}")
    if len(discrepancies) > 10:
        lines.append(f"... and {len(discrepancies) - 10} more")

    message = "\n".join(lines)
    url = f"https://api.telegram.org/bot{_TELEGRAM_BOT_TOKEN}/sendMessage"

    try:
        await asyncio.to_thread(
            _post_json_sync,
            url,
            {"chat_id": _TELEGRAM_CHAT_ID, "text": message},
        )
    except Exception as exc:  # noqa: BLE001
        _json_event("reconcile_alert_error", error=str(exc))


async def discover_existing_tpsl(
    wallet_address: str | None = None,
    rpc_url: str | None = None,
) -> set[str]:
    """On startup, discover positions that already have on-chain Trigger requests.

    Returns a set of position PDA strings that have active (non-executed) Trigger
    PositionRequest PDAs. The runner uses this to populate its tpsl_created set,
    preventing duplicate TP/SL submissions after a restart.
    """
    wallet = wallet_address or _WALLET_ADDRESS
    rpc = rpc_url or _HELIUS_RPC
    if not wallet:
        return set()

    try:
        request_targets = _enumerate_request_targets(wallet, _MAX_REQUEST_COUNTER_SCAN)
        chain_request_accounts = await fetch_multiple_accounts(request_targets, rpc)
        chain_requests = _decode_chain_requests(chain_request_accounts)

        # Find all positions that have active Trigger requests
        protected: set[str] = set()
        for req in chain_requests:
            if req["request_type"] == "Trigger" and not req["executed"]:
                protected.add(req["position"])

        _json_event(
            "tpsl_discovery",
            trigger_orders_found=len(protected),
            positions_protected=len(protected),
        )
        return protected
    except Exception as exc:  # noqa: BLE001
        _json_event("tpsl_discovery_error", error=str(exc))
        return set()


async def reconciliation_loop(
    journal: EventJournal,
    interval_seconds: int = _RECONCILE_INTERVAL,
) -> None:
    """Mandatory chain reconciliation loop. Chain truth wins always."""
    _json_event(
        "reconcile_start",
        interval_seconds=interval_seconds,
        wallet=(_WALLET_ADDRESS[:8] + "...") if _WALLET_ADDRESS else "unset",
    )

    while True:
        cycle_start = time.monotonic()
        try:
            position_targets = _enumerate_position_targets(_WALLET_ADDRESS)
            request_targets = _enumerate_request_targets(_WALLET_ADDRESS, _MAX_REQUEST_COUNTER_SCAN)

            chain_position_accounts = await fetch_multiple_accounts(position_targets, _HELIUS_RPC)
            chain_request_accounts = await fetch_multiple_accounts(request_targets, _HELIUS_RPC)

            chain_positions = _decode_chain_positions(chain_position_accounts)
            chain_requests = _decode_chain_requests(chain_request_accounts)

            # Classify requests: Market (pending fills) vs Trigger (on-chain TP/SL)
            market_requests = [r for r in chain_requests if r["request_type"] == "Market" and not r["executed"]]
            trigger_requests = [r for r in chain_requests if r["request_type"] == "Trigger" and not r["executed"]]
            active_request_count = len(market_requests) + len(trigger_requests)

            # Check which positions have on-chain TP/SL protection
            protected_positions = {r["position"] for r in trigger_requests}
            unprotected = [
                p for p in chain_positions
                if p["pda"] not in protected_positions and float(p.get("size_usd", 0)) > 0
            ]

            db_positions = await journal.get_projected_positions()
            discrepancies = _classify_discrepancies(chain_positions, db_positions)

            if discrepancies:
                await journal.record_reconciliation_failure(
                    chain_positions=chain_positions,
                    db_positions=db_positions,
                    discrepancies=discrepancies,
                )
                await _alert_operator(discrepancies)

            elapsed_ms = int((time.monotonic() - cycle_start) * 1000)
            _json_event(
                "reconciliation_cycle",
                chain_positions=len(chain_positions),
                active_request_pdas=active_request_count,
                pending_market_requests=len(market_requests),
                active_trigger_orders=len(trigger_requests),
                unprotected_positions=len(unprotected),
                projected_positions=len(db_positions),
                discrepancies=len(discrepancies),
                chain_truth_wins=True,
                cycle_ms=elapsed_ms,
            )
        except asyncio.CancelledError:
            _json_event("reconcile_stop", reason="cancelled")
            raise
        except Exception as exc:  # noqa: BLE001
            _json_event("reconcile_error", error=str(exc))

        await asyncio.sleep(interval_seconds)
