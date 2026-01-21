"""
Token Metadata Cache System

Caches token metadata from various sources (Solana, DEX APIs, etc.)
with TTL-based expiration, batch operations, and persistence.

Features:
- In-memory cache with TTL
- Batch lookups
- Auto-refresh on stale data
- Social links and logo caching
- Persistence to disk
"""

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Callable, Coroutine, Dict, List, Optional
from threading import Lock

logger = logging.getLogger(__name__)

DEFAULT_CACHE_DIR = Path.home() / ".lifeos" / "cache" / "tokens"
DEFAULT_TTL = 3600  # 1 hour
DEFAULT_MAX_ENTRIES = 10000


@dataclass
class SocialLinks:
    """Social media and website links for a token."""
    twitter: Optional[str] = None
    telegram: Optional[str] = None
    discord: Optional[str] = None
    website: Optional[str] = None
    github: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'twitter': self.twitter,
            'telegram': self.telegram,
            'discord': self.discord,
            'website': self.website,
            'github': self.github,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SocialLinks':
        """Create from dictionary."""
        return cls(
            twitter=data.get('twitter'),
            telegram=data.get('telegram'),
            discord=data.get('discord'),
            website=data.get('website'),
            github=data.get('github'),
        )

    def has_any(self) -> bool:
        """Check if any social links are set."""
        return any([
            self.twitter,
            self.telegram,
            self.discord,
            self.website,
            self.github,
        ])


@dataclass
class TokenMetadata:
    """Metadata for a token."""
    mint_address: str
    symbol: str
    name: str
    decimals: int
    logo_url: Optional[str] = None
    description: Optional[str] = None
    social_links: Optional[SocialLinks] = None
    coingecko_id: Optional[str] = None
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'mint_address': self.mint_address,
            'symbol': self.symbol,
            'name': self.name,
            'decimals': self.decimals,
            'logo_url': self.logo_url,
            'description': self.description,
            'social_links': self.social_links.to_dict() if self.social_links else None,
            'coingecko_id': self.coingecko_id,
            'tags': self.tags,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TokenMetadata':
        """Create from dictionary."""
        social_data = data.get('social_links')
        social_links = SocialLinks.from_dict(social_data) if social_data else None

        return cls(
            mint_address=data['mint_address'],
            symbol=data['symbol'],
            name=data['name'],
            decimals=data['decimals'],
            logo_url=data.get('logo_url'),
            description=data.get('description'),
            social_links=social_links,
            coingecko_id=data.get('coingecko_id'),
            tags=data.get('tags', []),
        )


@dataclass
class CacheEntry:
    """Internal cache entry with TTL tracking."""
    metadata: TokenMetadata
    expires_at: float  # Unix timestamp
    created_at: float  # Unix timestamp


class TokenMetadataCache:
    """
    Cache for token metadata with TTL support.

    Features:
    - In-memory storage with configurable TTL
    - Batch operations
    - Auto-refresh on stale data
    - Persistence to disk
    - Thread-safe
    """

    def __init__(
        self,
        cache_dir: Optional[Path] = None,
        default_ttl: float = DEFAULT_TTL,
        max_entries: int = DEFAULT_MAX_ENTRIES,
    ):
        self.cache_dir = cache_dir or DEFAULT_CACHE_DIR
        self.default_ttl = default_ttl
        self.max_entries = max_entries

        self._cache: Dict[str, CacheEntry] = {}
        self._lock = Lock()
        self._hits = 0
        self._misses = 0

        # Ensure cache directory exists
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def set(self, metadata: TokenMetadata, ttl: Optional[float] = None) -> None:
        """Add or update a cache entry."""
        ttl = ttl if ttl is not None else self.default_ttl
        now = time.time()

        with self._lock:
            # Evict if at capacity
            if len(self._cache) >= self.max_entries and metadata.mint_address not in self._cache:
                self._evict_oldest()

            self._cache[metadata.mint_address] = CacheEntry(
                metadata=metadata,
                expires_at=now + ttl,
                created_at=now,
            )

    def get(self, mint_address: str) -> Optional[TokenMetadata]:
        """Get a cache entry if it exists and is not expired."""
        with self._lock:
            entry = self._cache.get(mint_address)

            if entry is None:
                self._misses += 1
                return None

            # Check expiration
            if time.time() > entry.expires_at:
                del self._cache[mint_address]
                self._misses += 1
                return None

            self._hits += 1
            return entry.metadata

    def invalidate(self, mint_address: str) -> bool:
        """Remove a cache entry."""
        with self._lock:
            if mint_address in self._cache:
                del self._cache[mint_address]
                return True
            return False

    def clear_all(self) -> int:
        """Clear all cache entries. Returns count of removed entries."""
        with self._lock:
            count = len(self._cache)
            self._cache.clear()
            return count

    def batch_get(self, mint_addresses: List[str]) -> Dict[str, TokenMetadata]:
        """Get multiple entries at once."""
        results = {}
        for mint in mint_addresses:
            metadata = self.get(mint)
            if metadata is not None:
                results[mint] = metadata
        return results

    def batch_set(self, metadata_list: List[TokenMetadata], ttl: Optional[float] = None) -> None:
        """Set multiple entries at once."""
        for metadata in metadata_list:
            self.set(metadata, ttl)

    def is_stale(self, mint_address: str, refresh_threshold: float = 0.8) -> bool:
        """Check if an entry is stale (past refresh threshold but not expired)."""
        with self._lock:
            entry = self._cache.get(mint_address)
            if entry is None:
                return False

            now = time.time()
            ttl = entry.expires_at - entry.created_at
            age = now - entry.created_at

            return age >= ttl * refresh_threshold

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        with self._lock:
            total = self._hits + self._misses
            hit_rate = self._hits / total if total > 0 else 0.0

            return {
                'entries': len(self._cache),
                'hits': self._hits,
                'misses': self._misses,
                'hit_rate': hit_rate,
                'max_entries': self.max_entries,
            }

    def get_logo_url(self, mint_address: str) -> Optional[str]:
        """Get just the logo URL for a token."""
        metadata = self.get(mint_address)
        return metadata.logo_url if metadata else None

    def get_social_links(self, mint_address: str) -> Optional[SocialLinks]:
        """Get just the social links for a token."""
        metadata = self.get(mint_address)
        return metadata.social_links if metadata else None

    async def get_or_fetch(
        self,
        mint_address: str,
        fetcher: Callable[[str], Coroutine[Any, Any, Optional[TokenMetadata]]],
        ttl: Optional[float] = None,
        auto_refresh: bool = False,
        refresh_threshold: float = 0.8,
    ) -> Optional[TokenMetadata]:
        """Get from cache or fetch if not present."""
        # Check cache first
        cached = self.get(mint_address)

        if cached is not None:
            # Check if stale and auto-refresh requested
            if auto_refresh and self.is_stale(mint_address, refresh_threshold):
                # Trigger background refresh (don't await)
                asyncio.create_task(self._refresh_entry(mint_address, fetcher, ttl))
            return cached

        # Fetch and cache
        metadata = await fetcher(mint_address)
        if metadata is not None:
            self.set(metadata, ttl)

        return metadata

    async def batch_get_or_fetch(
        self,
        mint_addresses: List[str],
        batch_fetcher: Callable[[List[str]], Coroutine[Any, Any, Dict[str, TokenMetadata]]],
        ttl: Optional[float] = None,
    ) -> Dict[str, TokenMetadata]:
        """Get multiple from cache, fetch missing ones."""
        results = {}
        missing = []

        # Check cache
        for mint in mint_addresses:
            cached = self.get(mint)
            if cached is not None:
                results[mint] = cached
            else:
                missing.append(mint)

        # Fetch missing
        if missing:
            fetched = await batch_fetcher(missing)
            for mint, metadata in fetched.items():
                self.set(metadata, ttl)
                results[mint] = metadata

        return results

    async def _refresh_entry(
        self,
        mint_address: str,
        fetcher: Callable[[str], Coroutine[Any, Any, Optional[TokenMetadata]]],
        ttl: Optional[float] = None,
    ) -> None:
        """Background refresh of a stale entry."""
        try:
            metadata = await fetcher(mint_address)
            if metadata is not None:
                self.set(metadata, ttl)
        except Exception as e:
            logger.warning(f"Failed to refresh metadata for {mint_address}: {e}")

    def save(self) -> None:
        """Save cache to disk."""
        cache_file = self.cache_dir / "token_metadata_cache.json"

        with self._lock:
            data = {}
            now = time.time()

            for mint, entry in self._cache.items():
                # Only save non-expired entries
                if entry.expires_at > now:
                    data[mint] = {
                        'metadata': entry.metadata.to_dict(),
                        'expires_at': entry.expires_at,
                        'created_at': entry.created_at,
                    }

        with open(cache_file, 'w') as f:
            json.dump(data, f, indent=2)

        logger.debug(f"Saved {len(data)} cache entries to {cache_file}")

    def load(self) -> int:
        """Load cache from disk. Returns count of loaded entries."""
        cache_file = self.cache_dir / "token_metadata_cache.json"

        if not cache_file.exists():
            return 0

        try:
            with open(cache_file) as f:
                data = json.load(f)

            now = time.time()
            loaded = 0

            with self._lock:
                for mint, entry_data in data.items():
                    # Skip expired entries
                    if entry_data['expires_at'] <= now:
                        continue

                    metadata = TokenMetadata.from_dict(entry_data['metadata'])
                    self._cache[mint] = CacheEntry(
                        metadata=metadata,
                        expires_at=entry_data['expires_at'],
                        created_at=entry_data['created_at'],
                    )
                    loaded += 1

            logger.debug(f"Loaded {loaded} cache entries from {cache_file}")
            return loaded

        except Exception as e:
            logger.warning(f"Failed to load cache: {e}")
            return 0

    def _evict_oldest(self) -> None:
        """Evict the oldest entry from the cache."""
        if not self._cache:
            return

        oldest_key = min(self._cache.keys(), key=lambda k: self._cache[k].created_at)
        del self._cache[oldest_key]


# Global singleton
_cache: Optional[TokenMetadataCache] = None


def get_token_metadata_cache() -> TokenMetadataCache:
    """Get the global token metadata cache singleton."""
    global _cache
    if _cache is None:
        _cache = TokenMetadataCache()
    return _cache


async def get_token_metadata(mint_address: str) -> Optional[TokenMetadata]:
    """Convenience function to get token metadata."""
    cache = get_token_metadata_cache()
    return cache.get(mint_address)


async def get_batch_metadata(mint_addresses: List[str]) -> Dict[str, TokenMetadata]:
    """Convenience function for batch metadata lookup."""
    cache = get_token_metadata_cache()
    return cache.batch_get(mint_addresses)
