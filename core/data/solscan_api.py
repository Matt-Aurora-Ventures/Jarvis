"""
Solscan API - Solana Blockchain Explorer Integration
=====================================================

Provides access to Solana token data via Solscan API:
- Token information (supply, decimals, holders)
- Holder lists (top 100 holders)
- Recent transactions
- Token accounts

Features:
- Caching with 1-hour TTL
- Rate limiting
- Optional API key support
- Graceful error handling

Usage:
    from core.data.solscan_api import get_solscan_api, get_token_info

    api = get_solscan_api()
    info = await api.get_token_info("token_mint_address")
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import aiohttp
    HAS_AIOHTTP = True
except ImportError:
    HAS_AIOHTTP = False
    aiohttp = None

logger = logging.getLogger(__name__)

# Cache configuration
ROOT = Path(__file__).resolve().parents[2]
CACHE_DIR = ROOT / "data" / "onchain_cache"
CACHE_TTL_SECONDS = 3600  # 1 hour

# Rate limiting - Solscan free tier: 1 req/sec
RATE_LIMIT_REQUESTS_PER_SECOND = 1
_last_request_time: float = 0
_rate_lock = asyncio.Lock() if HAS_AIOHTTP else None


@dataclass
class TokenInfo:
    """Token information from Solscan."""
    token_address: str
    symbol: str = ""
    name: str = ""
    decimals: int = 9
    total_supply: int = 0
    holder_count: int = 0
    price_usd: float = 0.0
    market_cap: float = 0.0
    created_time: Optional[datetime] = None
    icon: str = ""
    website: str = ""
    coingecko_id: str = ""

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        if self.created_time:
            d["created_time"] = self.created_time.isoformat()
        return d


@dataclass
class HolderInfo:
    """Token holder information."""
    owner: str
    amount: int = 0
    rank: int = 0
    percentage: float = 0.0
    decimals: int = 9

    @property
    def amount_formatted(self) -> float:
        """Return amount adjusted for decimals."""
        return self.amount / (10 ** self.decimals)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class TransactionInfo:
    """Transaction information."""
    signature: str
    block_time: int = 0
    from_address: str = ""
    to_address: str = ""
    amount: int = 0
    tx_type: str = ""  # transfer, swap, etc.
    fee: int = 0
    success: bool = True

    @property
    def timestamp(self) -> datetime:
        return datetime.fromtimestamp(self.block_time, tz=timezone.utc)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class SolscanAPI:
    """
    Solscan blockchain explorer API client.

    Features:
    - Token info retrieval
    - Holder distribution data
    - Transaction history
    - Caching with 1-hour TTL
    - Rate limiting
    """

    BASE_URL = "https://api.solscan.io"
    PUBLIC_API_URL = "https://public-api.solscan.io"
    CACHE_TTL_SECONDS = CACHE_TTL_SECONDS

    _instance: Optional["SolscanAPI"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self.api_key = os.environ.get("SOLSCAN_API_KEY")
        self.cache_dir = CACHE_DIR
        self._session: Optional[aiohttp.ClientSession] = None
        self._cache: Dict[str, Dict[str, Any]] = {}

        # Ensure cache directory exists
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # Load existing cache
        self._load_cache()

        self._initialized = True
        logger.info(f"SolscanAPI initialized (api_key={'set' if self.api_key else 'not set'})")

    def _load_cache(self):
        """Load cache from disk."""
        cache_file = self.cache_dir / "solscan_cache.json"
        if cache_file.exists():
            try:
                with open(cache_file) as f:
                    self._cache = json.load(f)
                logger.debug(f"Loaded {len(self._cache)} cached entries")
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"Failed to load cache: {e}")
                self._cache = {}

    def _save_cache(self):
        """Save cache to disk."""
        cache_file = self.cache_dir / "solscan_cache.json"
        try:
            with open(cache_file, "w") as f:
                json.dump(self._cache, f)
        except IOError as e:
            logger.warning(f"Failed to save cache: {e}")

    def _get_cached(self, key: str) -> Optional[Dict[str, Any]]:
        """Get cached data if valid."""
        entry = self._cache.get(key)
        if not entry:
            return None

        cached_at = entry.get("cached_at", 0)
        if time.time() - cached_at > self.CACHE_TTL_SECONDS:
            return None

        return entry.get("data")

    def _set_cached(self, key: str, data: Dict[str, Any]):
        """Cache data."""
        self._cache[key] = {
            "data": data,
            "cached_at": time.time(),
        }

        # Limit cache size
        if len(self._cache) > 1000:
            sorted_keys = sorted(
                self._cache.keys(),
                key=lambda k: self._cache[k].get("cached_at", 0)
            )
            for old_key in sorted_keys[:200]:
                del self._cache[old_key]

        self._save_cache()

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if not HAS_AIOHTTP:
            raise RuntimeError("aiohttp not available")

        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=15)
            self._session = aiohttp.ClientSession(timeout=timeout)
        return self._session

    async def _rate_limit(self):
        """Apply rate limiting."""
        global _last_request_time

        if _rate_lock:
            async with _rate_lock:
                now = time.time()
                elapsed = now - _last_request_time
                min_delay = 1.0 / RATE_LIMIT_REQUESTS_PER_SECOND
                if elapsed < min_delay:
                    await asyncio.sleep(min_delay - elapsed)
                _last_request_time = time.time()

    async def _make_request(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        use_public_api: bool = False,
    ) -> Optional[Dict[str, Any]]:
        """
        Make API request with rate limiting and error handling.

        Args:
            endpoint: API endpoint path
            params: Query parameters
            use_public_api: Use public API endpoint

        Returns:
            Response data or None on error
        """
        if not HAS_AIOHTTP:
            logger.error("aiohttp not available")
            return None

        await self._rate_limit()

        base_url = self.PUBLIC_API_URL if use_public_api else self.BASE_URL
        url = f"{base_url}{endpoint}"

        headers = {
            "Accept": "application/json",
            "User-Agent": "Jarvis-Trading-Bot/1.0",
        }

        if self.api_key:
            headers["token"] = self.api_key

        try:
            session = await self._get_session()
            async with session.get(url, params=params, headers=headers) as resp:
                if resp.status == 200:
                    return await resp.json()
                elif resp.status == 429:
                    logger.warning("Solscan rate limit hit")
                    return None
                elif resp.status == 403:
                    logger.warning("Solscan access denied - may need API key")
                    return None
                else:
                    logger.debug(f"Solscan API returned {resp.status}")
                    return None
        except asyncio.TimeoutError:
            logger.warning(f"Solscan request timed out: {endpoint}")
            return None
        except Exception as e:
            logger.error(f"Solscan request failed: {e}")
            return None

    async def get_token_info(self, token_address: str) -> Optional[TokenInfo]:
        """
        Get token information.

        Args:
            token_address: Token mint address

        Returns:
            TokenInfo or None if not found
        """
        if not token_address:
            return None

        # Check cache
        cache_key = f"token_info:{token_address}"
        cached = self._get_cached(cache_key)
        if cached:
            return TokenInfo(**cached)

        # Try public API first (no key required)
        data = await self._make_request(
            f"/token/meta",
            params={"token": token_address},
            use_public_api=True,
        )

        if not data:
            # Fallback to main API
            data = await self._make_request(f"/v2/token/meta?token={token_address}")

        if not data:
            return None

        try:
            d = data.get("data", data)

            # Parse creation time if available
            created_time = None
            if d.get("created_time"):
                try:
                    created_time = datetime.fromtimestamp(d["created_time"], tz=timezone.utc)
                except (ValueError, TypeError):
                    pass

            info = TokenInfo(
                token_address=token_address,
                symbol=d.get("symbol", ""),
                name=d.get("name", ""),
                decimals=int(d.get("decimals", 9)),
                total_supply=int(d.get("supply", 0)),
                holder_count=int(d.get("holder", 0)),
                price_usd=float(d.get("priceUsdt", 0) or 0),
                market_cap=float(d.get("market_cap", 0) or 0),
                created_time=created_time,
                icon=d.get("icon", ""),
                website=d.get("website", ""),
                coingecko_id=d.get("coingeckoId", ""),
            )

            self._set_cached(cache_key, info.to_dict())
            return info

        except Exception as e:
            logger.error(f"Failed to parse token info: {e}")
            return None

    async def get_token_holders(
        self,
        token_address: str,
        limit: int = 100,
        offset: int = 0,
    ) -> List[HolderInfo]:
        """
        Get token holder list.

        Args:
            token_address: Token mint address
            limit: Maximum holders to return (max 100)
            offset: Pagination offset

        Returns:
            List of HolderInfo
        """
        if not token_address:
            return []

        # Check cache
        cache_key = f"holders:{token_address}:{limit}:{offset}"
        cached = self._get_cached(cache_key)
        if cached:
            return [HolderInfo(**h) for h in cached]

        data = await self._make_request(
            f"/token/holders",
            params={
                "token": token_address,
                "limit": min(limit, 100),
                "offset": offset,
            },
            use_public_api=True,
        )

        if not data:
            return []

        try:
            holders_data = data.get("data", [])

            # Get token decimals for proper calculation
            token_info = await self.get_token_info(token_address)
            decimals = token_info.decimals if token_info else 9
            total_supply = token_info.total_supply if token_info else 0

            holders = []
            for i, h in enumerate(holders_data):
                amount = int(h.get("amount", 0))
                percentage = 0.0
                if total_supply > 0:
                    percentage = (amount / total_supply) * 100

                holders.append(HolderInfo(
                    owner=h.get("owner", ""),
                    amount=amount,
                    rank=offset + i + 1,
                    percentage=percentage,
                    decimals=decimals,
                ))

            # Sort by amount descending
            holders.sort(key=lambda x: x.amount, reverse=True)

            # Update ranks
            for i, h in enumerate(holders):
                h.rank = offset + i + 1

            self._set_cached(cache_key, [h.to_dict() for h in holders])
            return holders

        except Exception as e:
            logger.error(f"Failed to parse holders: {e}")
            return []

    async def get_recent_transactions(
        self,
        token_address: str,
        limit: int = 50,
    ) -> List[TransactionInfo]:
        """
        Get recent token transactions.

        Args:
            token_address: Token mint address
            limit: Maximum transactions to return

        Returns:
            List of TransactionInfo
        """
        if not token_address:
            return []

        # Check cache (shorter TTL for transactions)
        cache_key = f"txs:{token_address}:{limit}"
        cached = self._get_cached(cache_key)
        if cached:
            return [TransactionInfo(**t) for t in cached]

        data = await self._make_request(
            f"/token/transfer",
            params={
                "token": token_address,
                "limit": min(limit, 50),
            },
            use_public_api=True,
        )

        if not data:
            return []

        try:
            txs_data = data.get("data", [])

            transactions = []
            for tx in txs_data:
                transactions.append(TransactionInfo(
                    signature=tx.get("trans_id", tx.get("signature", "")),
                    block_time=int(tx.get("block_time", 0)),
                    from_address=tx.get("src_address", tx.get("from", "")),
                    to_address=tx.get("dst_address", tx.get("to", "")),
                    amount=int(tx.get("amount", 0)),
                    tx_type=tx.get("activity_type", "transfer"),
                    fee=int(tx.get("fee", 0)),
                    success=tx.get("status") != "fail",
                ))

            self._set_cached(cache_key, [t.to_dict() for t in transactions])
            return transactions

        except Exception as e:
            logger.error(f"Failed to parse transactions: {e}")
            return []

    async def get_token_accounts(
        self,
        token_address: str,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Get token accounts (program accounts holding the token).

        Args:
            token_address: Token mint address
            limit: Maximum accounts to return

        Returns:
            List of account data dicts
        """
        if not token_address:
            return []

        cache_key = f"accounts:{token_address}:{limit}"
        cached = self._get_cached(cache_key)
        if cached:
            return cached

        data = await self._make_request(
            f"/token/account",
            params={
                "token": token_address,
                "limit": min(limit, 100),
            },
            use_public_api=True,
        )

        if not data:
            return []

        accounts = data.get("data", [])
        self._set_cached(cache_key, accounts)
        return accounts

    def clear_cache(self) -> int:
        """
        Clear all cached data.

        Returns:
            Number of entries cleared
        """
        count = len(self._cache)
        self._cache = {}

        cache_file = self.cache_dir / "solscan_cache.json"
        try:
            if cache_file.exists():
                cache_file.unlink()
        except IOError:
            pass

        logger.info(f"Cleared {count} cache entries")
        return count

    async def close(self):
        """Close the aiohttp session."""
        if self._session and not self._session.closed:
            await self._session.close()

    def get_api_status(self) -> Dict[str, Any]:
        """Get API status information."""
        return {
            "available": HAS_AIOHTTP,
            "api_key_set": bool(self.api_key),
            "cached_entries": len(self._cache),
            "cache_ttl_seconds": self.CACHE_TTL_SECONDS,
            "rate_limit": f"{RATE_LIMIT_REQUESTS_PER_SECOND} req/sec",
            "base_url": self.BASE_URL,
        }


# Singleton accessor
def get_solscan_api() -> SolscanAPI:
    """Get the SolscanAPI singleton instance."""
    return SolscanAPI()


# Convenience functions
async def get_token_info(token_address: str) -> Optional[TokenInfo]:
    """Get token info (convenience function)."""
    api = get_solscan_api()
    return await api.get_token_info(token_address)


async def get_token_holders(token_address: str, limit: int = 100) -> List[HolderInfo]:
    """Get token holders (convenience function)."""
    api = get_solscan_api()
    return await api.get_token_holders(token_address, limit=limit)


if __name__ == "__main__":
    import asyncio
    logging.basicConfig(level=logging.INFO)

    async def test():
        print("=== Solscan API Test ===")
        api = get_solscan_api()
        print(f"Status: {api.get_api_status()}")

        # Test with SOL
        sol_mint = "So11111111111111111111111111111111111111112"
        print(f"\nFetching SOL token info...")
        info = await api.get_token_info(sol_mint)
        if info:
            print(f"  Symbol: {info.symbol}")
            print(f"  Name: {info.name}")
            print(f"  Holders: {info.holder_count}")
        else:
            print("  Failed to fetch")

        await api.close()

    asyncio.run(test())
