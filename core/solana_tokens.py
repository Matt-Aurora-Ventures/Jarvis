"""Token metadata helpers for Solana trading."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from core import jupiter, solana_execution

try:
    from solders.pubkey import Pubkey
    from solana.rpc.async_api import AsyncClient
    HAS_SOLANA = True
except Exception:
    HAS_SOLANA = False
    Pubkey = None
    AsyncClient = None

LOCAL_TOKEN_LIST = Path.home() / ".lifeos" / "trading" / "token_list.json"

_TOKEN_CACHE: Dict[str, Dict[str, float]] = {}
_TOKEN_LIST: Optional[List[Dict[str, Any]]] = None
_DECIMALS_CACHE: Dict[str, int] = {}

def _extract_token_list(payload: Any) -> List[Dict[str, Any]]:
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        tokens = payload.get("tokens")
        if isinstance(tokens, list):
            return tokens
    return []


def _read_local_token_list() -> List[Dict[str, Any]]:
    env_path = os.getenv("LIFEOS_TOKEN_LIST_PATH", "").strip()
    path = Path(os.path.expanduser(env_path)) if env_path else LOCAL_TOKEN_LIST
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text())
    except json.JSONDecodeError:
        return []
    return _extract_token_list(payload)


def _write_local_token_list(tokens: List[Dict[str, Any]]) -> None:
    if not tokens:
        return
    path = LOCAL_TOKEN_LIST
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(tokens))
    except OSError:
        return


def _load_token_list() -> List[Dict[str, Any]]:
    global _TOKEN_LIST
    if _TOKEN_LIST is not None:
        return _TOKEN_LIST
    tokens = _read_local_token_list()
    if not tokens:
        tokens = jupiter.fetch_token_list(cache_ttl_seconds=3600)
        _write_local_token_list(tokens)
    _TOKEN_LIST = tokens
    return tokens


def _load_token_cache() -> Dict[str, Dict[str, float]]:
    if _TOKEN_CACHE:
        return _TOKEN_CACHE
    token_list = _load_token_list()
    for token in token_list:
        mint = token.get("address") or token.get("mint")
        if not mint:
            continue
        _TOKEN_CACHE[mint] = {
            "decimals": float(token.get("decimals", 0)),
        }
    return _TOKEN_CACHE


def _run_async(coro):
    import asyncio

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    return asyncio.run_coroutine_threadsafe(coro, loop).result()


def _fetch_onchain_decimals(mint: str) -> Optional[int]:
    if not HAS_SOLANA or Pubkey is None or AsyncClient is None:
        return None
    try:
        pubkey = Pubkey.from_string(mint)
    except Exception:
        return None
    endpoints = solana_execution.load_solana_rpc_endpoints()
    if not endpoints:
        return None

    async def _fetch() -> Optional[int]:
        for endpoint in endpoints:
            try:
                async with AsyncClient(endpoint.url) as client:
                    resp = await client.get_token_supply(pubkey)
                    value = resp.value
                    if value is not None:
                        return int(value.decimals)
            except Exception:
                continue
        return None

    try:
        return _run_async(_fetch())
    except Exception:
        return None


def get_token_decimals(mint: str, *, fallback: int = 9) -> int:
    cached = _DECIMALS_CACHE.get(mint)
    if cached is not None:
        return cached
    cache = _load_token_cache()
    entry = cache.get(mint)
    value = entry.get("decimals") if entry else None
    if value is not None:
        try:
            decimals = int(value)
            if 0 <= decimals <= 18:
                if decimals == 0:
                    onchain = _fetch_onchain_decimals(mint)
                    if onchain is not None and onchain > 0:
                        _DECIMALS_CACHE[mint] = onchain
                        return onchain
                _DECIMALS_CACHE[mint] = decimals
                return decimals
        except (TypeError, ValueError):
            pass

    onchain = _fetch_onchain_decimals(mint)
    if onchain is not None:
        _DECIMALS_CACHE[mint] = onchain
        return onchain
    return fallback


def get_mint_for_symbol(symbol: str) -> Optional[str]:
    token_list = _load_token_list()
    symbol_upper = symbol.upper()
    for token in token_list:
        if str(token.get("symbol", "")).upper() == symbol_upper:
            return token.get("address") or token.get("mint")
    return None
