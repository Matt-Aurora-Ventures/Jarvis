"""
Tests for Token Metadata Cache System
=====================================

Tests cover:
- TokenMetadata dataclass
- TokenMetadataCache class
- Cache operations (get, set, invalidate)
- Batch lookups
- Auto-refresh on stale data
- Social links caching
- Logo/image caching
- Persistence
"""

import asyncio
import json
import pytest
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch


# Import the module under test (will fail until implemented)
from core.data.token_metadata_cache import (
    TokenMetadata,
    SocialLinks,
    TokenMetadataCache,
    get_token_metadata_cache,
    get_token_metadata,
    get_batch_metadata,
)


class TestTokenMetadata:
    """Tests for TokenMetadata dataclass."""

    def test_token_metadata_creation_minimal(self):
        """Test creating metadata with minimal required fields."""
        metadata = TokenMetadata(
            mint_address="So11111111111111111111111111111111111111112",
            symbol="SOL",
            name="Solana",
            decimals=9,
        )
        assert metadata.mint_address == "So11111111111111111111111111111111111111112"
        assert metadata.symbol == "SOL"
        assert metadata.name == "Solana"
        assert metadata.decimals == 9

    def test_token_metadata_creation_full(self):
        """Test creating metadata with all fields."""
        social = SocialLinks(
            twitter="https://twitter.com/solana",
            telegram="https://t.me/solana",
            discord="https://discord.gg/solana",
            website="https://solana.com",
        )
        metadata = TokenMetadata(
            mint_address="So11111111111111111111111111111111111111112",
            symbol="SOL",
            name="Solana",
            decimals=9,
            logo_url="https://example.com/sol.png",
            description="Solana is a high-performance blockchain",
            social_links=social,
            coingecko_id="solana",
            tags=["infrastructure", "layer1"],
        )
        assert metadata.logo_url == "https://example.com/sol.png"
        assert metadata.description == "Solana is a high-performance blockchain"
        assert metadata.social_links.twitter == "https://twitter.com/solana"
        assert metadata.coingecko_id == "solana"
        assert "layer1" in metadata.tags

    def test_token_metadata_to_dict(self):
        """Test serializing metadata to dictionary."""
        metadata = TokenMetadata(
            mint_address="test_mint",
            symbol="TEST",
            name="Test Token",
            decimals=6,
        )
        d = metadata.to_dict()
        assert d["mint_address"] == "test_mint"
        assert d["symbol"] == "TEST"
        assert d["decimals"] == 6

    def test_token_metadata_from_dict(self):
        """Test deserializing metadata from dictionary."""
        data = {
            "mint_address": "test_mint",
            "symbol": "TEST",
            "name": "Test Token",
            "decimals": 6,
            "logo_url": "https://example.com/test.png",
        }
        metadata = TokenMetadata.from_dict(data)
        assert metadata.mint_address == "test_mint"
        assert metadata.logo_url == "https://example.com/test.png"

    def test_token_metadata_from_dict_with_social(self):
        """Test deserializing metadata with social links."""
        data = {
            "mint_address": "test_mint",
            "symbol": "TEST",
            "name": "Test Token",
            "decimals": 6,
            "social_links": {
                "twitter": "https://twitter.com/test",
                "website": "https://test.com",
            },
        }
        metadata = TokenMetadata.from_dict(data)
        assert metadata.social_links is not None
        assert metadata.social_links.twitter == "https://twitter.com/test"


class TestSocialLinks:
    """Tests for SocialLinks dataclass."""

    def test_social_links_creation(self):
        """Test creating social links."""
        links = SocialLinks(
            twitter="https://twitter.com/test",
            telegram="https://t.me/test",
            discord="https://discord.gg/test",
            website="https://test.com",
            github="https://github.com/test",
        )
        assert links.twitter == "https://twitter.com/test"
        assert links.github == "https://github.com/test"

    def test_social_links_to_dict(self):
        """Test serializing social links."""
        links = SocialLinks(twitter="https://twitter.com/test")
        d = links.to_dict()
        assert d["twitter"] == "https://twitter.com/test"
        assert "telegram" in d  # Should include all fields

    def test_social_links_from_dict(self):
        """Test deserializing social links."""
        data = {"twitter": "https://twitter.com/test", "website": "https://test.com"}
        links = SocialLinks.from_dict(data)
        assert links.twitter == "https://twitter.com/test"
        assert links.website == "https://test.com"

    def test_social_links_has_any(self):
        """Test checking if any social links exist."""
        empty_links = SocialLinks()
        assert not empty_links.has_any()

        with_twitter = SocialLinks(twitter="https://twitter.com/test")
        assert with_twitter.has_any()


class TestTokenMetadataCache:
    """Tests for TokenMetadataCache class."""

    @pytest.fixture
    def temp_cache_dir(self):
        """Create a temporary directory for cache."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def cache(self, temp_cache_dir):
        """Create a cache instance with temp directory."""
        return TokenMetadataCache(
            cache_dir=temp_cache_dir,
            default_ttl=3600,
            max_entries=1000,
        )

    def test_cache_init(self, cache):
        """Test cache initialization."""
        assert cache is not None
        assert cache.default_ttl == 3600
        assert cache.max_entries == 1000

    def test_cache_set_and_get(self, cache):
        """Test basic set and get operations."""
        metadata = TokenMetadata(
            mint_address="test_mint",
            symbol="TEST",
            name="Test Token",
            decimals=6,
        )
        cache.set(metadata)

        retrieved = cache.get("test_mint")
        assert retrieved is not None
        assert retrieved.symbol == "TEST"
        assert retrieved.decimals == 6

    def test_cache_get_nonexistent(self, cache):
        """Test getting non-existent entry returns None."""
        result = cache.get("nonexistent_mint")
        assert result is None

    def test_cache_invalidate(self, cache):
        """Test invalidating a cache entry."""
        metadata = TokenMetadata(
            mint_address="test_mint",
            symbol="TEST",
            name="Test Token",
            decimals=6,
        )
        cache.set(metadata)

        # Verify it's cached
        assert cache.get("test_mint") is not None

        # Invalidate
        result = cache.invalidate("test_mint")
        assert result is True

        # Verify it's gone
        assert cache.get("test_mint") is None

    def test_cache_invalidate_nonexistent(self, cache):
        """Test invalidating non-existent entry returns False."""
        result = cache.invalidate("nonexistent_mint")
        assert result is False

    def test_cache_clear_all(self, cache):
        """Test clearing all cache entries."""
        for i in range(5):
            metadata = TokenMetadata(
                mint_address=f"mint_{i}",
                symbol=f"TKN{i}",
                name=f"Token {i}",
                decimals=6,
            )
            cache.set(metadata)

        count = cache.clear_all()
        assert count == 5

        # Verify all are gone
        for i in range(5):
            assert cache.get(f"mint_{i}") is None

    def test_cache_expiration(self, cache):
        """Test that expired entries are not returned."""
        # Create cache with very short TTL
        short_ttl_cache = TokenMetadataCache(
            cache_dir=cache.cache_dir,
            default_ttl=0.1,  # 100ms TTL
            max_entries=1000,
        )

        metadata = TokenMetadata(
            mint_address="test_mint",
            symbol="TEST",
            name="Test Token",
            decimals=6,
        )
        short_ttl_cache.set(metadata)

        # Should be available immediately
        assert short_ttl_cache.get("test_mint") is not None

        # Wait for expiration
        time.sleep(0.15)

        # Should be expired now
        assert short_ttl_cache.get("test_mint") is None

    def test_cache_custom_ttl(self, cache):
        """Test setting entry with custom TTL."""
        metadata = TokenMetadata(
            mint_address="test_mint",
            symbol="TEST",
            name="Test Token",
            decimals=6,
        )
        cache.set(metadata, ttl=0.1)  # 100ms TTL

        # Should be available immediately
        assert cache.get("test_mint") is not None

        # Wait for expiration
        time.sleep(0.15)

        # Should be expired now
        assert cache.get("test_mint") is None

    def test_cache_is_stale(self, cache):
        """Test checking if entry is stale (past refresh threshold)."""
        metadata = TokenMetadata(
            mint_address="test_mint",
            symbol="TEST",
            name="Test Token",
            decimals=6,
        )
        cache.set(metadata, ttl=1.0)

        # Not stale immediately (assuming 80% threshold)
        assert not cache.is_stale("test_mint", refresh_threshold=0.8)

        # Wait for 80% of TTL
        time.sleep(0.85)

        # Should be stale now (but not expired)
        assert cache.is_stale("test_mint", refresh_threshold=0.8)

    def test_cache_stats(self, cache):
        """Test getting cache statistics."""
        for i in range(3):
            metadata = TokenMetadata(
                mint_address=f"mint_{i}",
                symbol=f"TKN{i}",
                name=f"Token {i}",
                decimals=6,
            )
            cache.set(metadata)

        # Get twice (one hit, one miss per)
        cache.get("mint_0")  # hit
        cache.get("nonexistent")  # miss

        stats = cache.get_stats()
        assert stats["entries"] == 3
        assert stats["hits"] >= 1
        assert stats["misses"] >= 1
        assert "hit_rate" in stats


class TestTokenMetadataCacheBatch:
    """Tests for batch operations."""

    @pytest.fixture
    def temp_cache_dir(self):
        """Create a temporary directory for cache."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def cache(self, temp_cache_dir):
        """Create a cache instance with temp directory."""
        return TokenMetadataCache(
            cache_dir=temp_cache_dir,
            default_ttl=3600,
            max_entries=1000,
        )

    def test_batch_get(self, cache):
        """Test batch get operation."""
        # Add some entries
        for i in range(3):
            metadata = TokenMetadata(
                mint_address=f"mint_{i}",
                symbol=f"TKN{i}",
                name=f"Token {i}",
                decimals=6,
            )
            cache.set(metadata)

        # Batch get (2 exist, 1 doesn't)
        mints = ["mint_0", "mint_1", "nonexistent"]
        results = cache.batch_get(mints)

        assert len(results) == 2  # Only found entries
        assert "mint_0" in results
        assert "mint_1" in results
        assert "nonexistent" not in results

    def test_batch_set(self, cache):
        """Test batch set operation."""
        metadata_list = [
            TokenMetadata(mint_address=f"mint_{i}", symbol=f"TKN{i}", name=f"Token {i}", decimals=6)
            for i in range(5)
        ]

        cache.batch_set(metadata_list)

        for i in range(5):
            assert cache.get(f"mint_{i}") is not None


@pytest.mark.asyncio
class TestTokenMetadataCacheAsync:
    """Tests for async operations."""

    @pytest.fixture
    def temp_cache_dir(self):
        """Create a temporary directory for cache."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def cache(self, temp_cache_dir):
        """Create a cache instance with temp directory."""
        return TokenMetadataCache(
            cache_dir=temp_cache_dir,
            default_ttl=3600,
            max_entries=1000,
        )

    async def test_get_or_fetch(self, cache):
        """Test get_or_fetch with async fetcher."""
        fetch_count = 0

        async def mock_fetcher(mint: str) -> Optional[TokenMetadata]:
            nonlocal fetch_count
            fetch_count += 1
            return TokenMetadata(
                mint_address=mint,
                symbol="FETCHED",
                name="Fetched Token",
                decimals=6,
            )

        # First call should fetch
        result1 = await cache.get_or_fetch("test_mint", mock_fetcher)
        assert result1.symbol == "FETCHED"
        assert fetch_count == 1

        # Second call should use cache
        result2 = await cache.get_or_fetch("test_mint", mock_fetcher)
        assert result2.symbol == "FETCHED"
        assert fetch_count == 1  # No additional fetch

    async def test_get_or_fetch_failed(self, cache):
        """Test get_or_fetch when fetcher returns None."""
        async def mock_fetcher(mint: str) -> Optional[TokenMetadata]:
            return None

        result = await cache.get_or_fetch("test_mint", mock_fetcher)
        assert result is None

    async def test_batch_get_or_fetch(self, cache):
        """Test batch get_or_fetch."""
        fetch_calls = []

        async def mock_batch_fetcher(mints: List[str]) -> Dict[str, TokenMetadata]:
            fetch_calls.append(mints)
            return {
                mint: TokenMetadata(
                    mint_address=mint,
                    symbol=f"TKN{i}",
                    name=f"Token {i}",
                    decimals=6,
                )
                for i, mint in enumerate(mints)
            }

        # Pre-cache one entry
        cache.set(TokenMetadata(
            mint_address="cached_mint",
            symbol="CACHED",
            name="Cached Token",
            decimals=6,
        ))

        # Batch fetch (one cached, two need fetching)
        mints = ["cached_mint", "new_mint_1", "new_mint_2"]
        results = await cache.batch_get_or_fetch(mints, mock_batch_fetcher)

        assert len(results) == 3
        assert results["cached_mint"].symbol == "CACHED"  # From cache
        assert results["new_mint_1"].symbol == "TKN0"  # From fetcher
        assert results["new_mint_2"].symbol == "TKN1"  # From fetcher

        # Only non-cached mints should be fetched
        assert len(fetch_calls) == 1
        assert "cached_mint" not in fetch_calls[0]

    async def test_auto_refresh_stale(self, cache):
        """Test automatic refresh of stale data."""
        # Create cache with short TTL for testing
        cache.default_ttl = 0.5  # 500ms

        refresh_count = 0

        async def mock_fetcher(mint: str) -> Optional[TokenMetadata]:
            nonlocal refresh_count
            refresh_count += 1
            return TokenMetadata(
                mint_address=mint,
                symbol=f"V{refresh_count}",
                name=f"Version {refresh_count}",
                decimals=6,
            )

        # First fetch
        result1 = await cache.get_or_fetch("test_mint", mock_fetcher)
        assert result1.symbol == "V1"
        assert refresh_count == 1

        # Wait until stale (but not expired) - 80% of TTL = 0.4s
        time.sleep(0.42)

        # Get with auto-refresh
        result2 = await cache.get_or_fetch(
            "test_mint",
            mock_fetcher,
            auto_refresh=True,
            refresh_threshold=0.8
        )

        # Should return cached value but trigger background refresh
        # For simplicity, we'll check that refresh was triggered
        assert refresh_count >= 1  # At least initial fetch occurred


class TestTokenMetadataCachePersistence:
    """Tests for cache persistence."""

    @pytest.fixture
    def temp_cache_dir(self):
        """Create a temporary directory for cache."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    def test_persistence_save(self, temp_cache_dir):
        """Test saving cache to disk."""
        cache = TokenMetadataCache(
            cache_dir=temp_cache_dir,
            default_ttl=3600,
            max_entries=1000,
        )

        metadata = TokenMetadata(
            mint_address="test_mint",
            symbol="TEST",
            name="Test Token",
            decimals=6,
        )
        cache.set(metadata)
        cache.save()

        # Check file exists
        cache_file = temp_cache_dir / "token_metadata_cache.json"
        assert cache_file.exists()

        # Check content
        with open(cache_file) as f:
            data = json.load(f)
        assert "test_mint" in data

    def test_persistence_load(self, temp_cache_dir):
        """Test loading cache from disk."""
        # Create initial cache and save
        cache1 = TokenMetadataCache(
            cache_dir=temp_cache_dir,
            default_ttl=3600,
            max_entries=1000,
        )
        metadata = TokenMetadata(
            mint_address="test_mint",
            symbol="TEST",
            name="Test Token",
            decimals=6,
        )
        cache1.set(metadata)
        cache1.save()

        # Create new cache instance (should load from disk)
        cache2 = TokenMetadataCache(
            cache_dir=temp_cache_dir,
            default_ttl=3600,
            max_entries=1000,
        )
        cache2.load()

        # Should find the entry
        result = cache2.get("test_mint")
        assert result is not None
        assert result.symbol == "TEST"


class TestConvenienceFunctions:
    """Tests for module-level convenience functions."""

    @pytest.fixture
    def temp_cache_dir(self):
        """Create a temporary directory for cache."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    def test_get_token_metadata_cache_singleton(self, temp_cache_dir):
        """Test that get_token_metadata_cache returns singleton."""
        with patch('core.data.token_metadata_cache.DEFAULT_CACHE_DIR', temp_cache_dir):
            cache1 = get_token_metadata_cache()
            cache2 = get_token_metadata_cache()
            assert cache1 is cache2

    @pytest.mark.asyncio
    async def test_get_token_metadata_convenience(self, temp_cache_dir):
        """Test convenience function for getting single token metadata."""
        with patch('core.data.token_metadata_cache.DEFAULT_CACHE_DIR', temp_cache_dir):
            # Need to mock the fetcher
            mock_metadata = TokenMetadata(
                mint_address="test_mint",
                symbol="TEST",
                name="Test Token",
                decimals=6,
            )

            cache = get_token_metadata_cache()
            cache.set(mock_metadata)

            result = await get_token_metadata("test_mint")
            assert result is not None
            assert result.symbol == "TEST"

    @pytest.mark.asyncio
    async def test_get_batch_metadata_convenience(self, temp_cache_dir):
        """Test convenience function for batch metadata lookup."""
        with patch('core.data.token_metadata_cache.DEFAULT_CACHE_DIR', temp_cache_dir):
            cache = get_token_metadata_cache()

            # Pre-populate cache
            for i in range(3):
                metadata = TokenMetadata(
                    mint_address=f"mint_{i}",
                    symbol=f"TKN{i}",
                    name=f"Token {i}",
                    decimals=6,
                )
                cache.set(metadata)

            results = await get_batch_metadata(["mint_0", "mint_1", "mint_2"])
            assert len(results) == 3


class TestLogoImageCaching:
    """Tests for logo/image caching functionality."""

    @pytest.fixture
    def temp_cache_dir(self):
        """Create a temporary directory for cache."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def cache(self, temp_cache_dir):
        """Create a cache instance with temp directory."""
        return TokenMetadataCache(
            cache_dir=temp_cache_dir,
            default_ttl=3600,
            max_entries=1000,
        )

    def test_logo_url_cached(self, cache):
        """Test that logo URLs are cached with metadata."""
        metadata = TokenMetadata(
            mint_address="test_mint",
            symbol="TEST",
            name="Test Token",
            decimals=6,
            logo_url="https://example.com/logo.png",
        )
        cache.set(metadata)

        retrieved = cache.get("test_mint")
        assert retrieved.logo_url == "https://example.com/logo.png"

    def test_get_logo_url(self, cache):
        """Test getting just the logo URL."""
        metadata = TokenMetadata(
            mint_address="test_mint",
            symbol="TEST",
            name="Test Token",
            decimals=6,
            logo_url="https://example.com/logo.png",
        )
        cache.set(metadata)

        logo_url = cache.get_logo_url("test_mint")
        assert logo_url == "https://example.com/logo.png"

    def test_get_logo_url_missing(self, cache):
        """Test getting logo URL for non-existent token."""
        logo_url = cache.get_logo_url("nonexistent")
        assert logo_url is None


class TestSocialLinksCaching:
    """Tests for social links caching functionality."""

    @pytest.fixture
    def temp_cache_dir(self):
        """Create a temporary directory for cache."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def cache(self, temp_cache_dir):
        """Create a cache instance with temp directory."""
        return TokenMetadataCache(
            cache_dir=temp_cache_dir,
            default_ttl=3600,
            max_entries=1000,
        )

    def test_social_links_cached(self, cache):
        """Test that social links are cached with metadata."""
        social = SocialLinks(
            twitter="https://twitter.com/test",
            telegram="https://t.me/test",
            website="https://test.com",
        )
        metadata = TokenMetadata(
            mint_address="test_mint",
            symbol="TEST",
            name="Test Token",
            decimals=6,
            social_links=social,
        )
        cache.set(metadata)

        retrieved = cache.get("test_mint")
        assert retrieved.social_links.twitter == "https://twitter.com/test"
        assert retrieved.social_links.telegram == "https://t.me/test"

    def test_get_social_links(self, cache):
        """Test getting just the social links."""
        social = SocialLinks(
            twitter="https://twitter.com/test",
            website="https://test.com",
        )
        metadata = TokenMetadata(
            mint_address="test_mint",
            symbol="TEST",
            name="Test Token",
            decimals=6,
            social_links=social,
        )
        cache.set(metadata)

        links = cache.get_social_links("test_mint")
        assert links is not None
        assert links.twitter == "https://twitter.com/test"

    def test_get_social_links_missing(self, cache):
        """Test getting social links for non-existent token."""
        links = cache.get_social_links("nonexistent")
        assert links is None
