"""Token metadata helpers for Solana trading."""

from __future__ import annotations

from typing import Dict, Optional

from core import jupiter

_TOKEN_CACHE: Dict[str, Dict[str, float]] = {}


def _load_token_cache() -> Dict[str, Dict[str, float]]:
    if _TOKEN_CACHE:
        return _TOKEN_CACHE
    token_list = jupiter.fetch_token_list(cache_ttl_seconds=3600)
    for token in token_list:
        mint = token.get("address") or token.get("mint")
        if not mint:
            continue
        _TOKEN_CACHE[mint] = {
            "decimals": float(token.get("decimals", 0)),
        }
    return _TOKEN_CACHE


def get_token_decimals(mint: str, *, fallback: int = 9) -> int:
    cache = _load_token_cache()
    entry = cache.get(mint)
    if not entry:
        return fallback
    value = entry.get("decimals")
    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback


def get_mint_for_symbol(symbol: str) -> Optional[str]:
    token_list = jupiter.fetch_token_list(cache_ttl_seconds=3600)
    symbol_upper = symbol.upper()
    for token in token_list:
        if str(token.get("symbol", "")).upper() == symbol_upper:
            return token.get("address") or token.get("mint")
    return None
