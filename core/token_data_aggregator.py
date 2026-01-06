"""
Unified Token Data Aggregator
=============================

Combines multiple data sources (BirdEye, DexScreener, GeckoTerminal) with
automatic fallback for reliable token data retrieval.

Features:
- Automatic failover between data sources
- Unified response format
- Rate limit awareness across sources
- Caching coordination
- Health monitoring
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from core import birdeye, dexscreener, geckoterminal

logger = logging.getLogger(__name__)


class DataSource(Enum):
    """Available data sources."""
    BIRDEYE = "birdeye"
    DEXSCREENER = "dexscreener"
    GECKOTERMINAL = "geckoterminal"


@dataclass
class TokenData:
    """Unified token data format."""
    address: str
    symbol: str
    name: str
    price_usd: float
    price_change_1h: float = 0.0
    price_change_24h: float = 0.0
    price_change_5m: float = 0.0
    volume_24h: float = 0.0
    volume_1h: float = 0.0
    liquidity_usd: float = 0.0
    source: DataSource = DataSource.DEXSCREENER
    timestamp: float = field(default_factory=time.time)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "address": self.address,
            "symbol": self.symbol,
            "name": self.name,
            "price_usd": self.price_usd,
            "price_change_1h": self.price_change_1h,
            "price_change_24h": self.price_change_24h,
            "price_change_5m": self.price_change_5m,
            "volume_24h": self.volume_24h,
            "volume_1h": self.volume_1h,
            "liquidity_usd": self.liquidity_usd,
            "source": self.source.value,
            "timestamp": self.timestamp,
        }


@dataclass
class AggregatorResult:
    """Result from aggregator operations."""
    success: bool
    data: Optional[Any] = None
    source: Optional[DataSource] = None
    error: Optional[str] = None
    sources_tried: List[str] = field(default_factory=list)


# Source priority order (most reliable first for each operation)
PRICE_PRIORITY = [DataSource.DEXSCREENER, DataSource.BIRDEYE, DataSource.GECKOTERMINAL]
TRENDING_PRIORITY = [DataSource.DEXSCREENER, DataSource.BIRDEYE]
OHLCV_PRIORITY = [DataSource.BIRDEYE, DataSource.GECKOTERMINAL]


def get_sources_status() -> Dict[str, Any]:
    """Get status of all data sources."""
    return {
        "birdeye": {
            "available": birdeye.has_api_key(),
            **birdeye.get_api_status(),
        },
        "dexscreener": dexscreener.get_api_status(),
        "geckoterminal": geckoterminal.get_api_status(),
    }


def get_token_price(
    address: str,
    *,
    chain: str = "solana",
    sources: Optional[List[DataSource]] = None,
) -> AggregatorResult:
    """
    Get token price from multiple sources with fallback.
    
    Args:
        address: Token contract address
        chain: Blockchain (default: solana)
        sources: Override source priority
    
    Returns:
        AggregatorResult with TokenData or error
    """
    priority = sources or PRICE_PRIORITY
    sources_tried = []
    last_error = None
    
    for source in priority:
        sources_tried.append(source.value)
        
        try:
            if source == DataSource.DEXSCREENER:
                result = dexscreener.get_pairs_by_token(address)
                if result.success and result.data:
                    pairs = result.data.get("pairs", [])
                    if pairs:
                        pair = pairs[0]  # Get first/best pair
                        token_data = TokenData(
                            address=address,
                            symbol=pair.get("baseToken", {}).get("symbol", ""),
                            name=pair.get("baseToken", {}).get("name", ""),
                            price_usd=float(pair.get("priceUsd", 0) or 0),
                            price_change_1h=float(pair.get("priceChange", {}).get("h1", 0) or 0),
                            price_change_24h=float(pair.get("priceChange", {}).get("h24", 0) or 0),
                            price_change_5m=float(pair.get("priceChange", {}).get("m5", 0) or 0),
                            volume_24h=float(pair.get("volume", {}).get("h24", 0) or 0),
                            volume_1h=float(pair.get("volume", {}).get("h1", 0) or 0),
                            liquidity_usd=float(pair.get("liquidity", {}).get("usd", 0) or 0),
                            source=DataSource.DEXSCREENER,
                        )
                        logger.info(f"Got price for {address[:16]}... from DexScreener")
                        return AggregatorResult(
                            success=True,
                            data=token_data,
                            source=DataSource.DEXSCREENER,
                            sources_tried=sources_tried,
                        )
                last_error = result.error
                
            elif source == DataSource.BIRDEYE:
                if not birdeye.has_api_key():
                    last_error = "no_api_key"
                    continue
                    
                result = birdeye.fetch_token_price_safe(address, chain=chain)
                if result.success and result.data:
                    price_data = result.data.get("data", {})
                    token_data = TokenData(
                        address=address,
                        symbol="",  # BirdEye price endpoint doesn't return symbol
                        name="",
                        price_usd=float(price_data.get("value", 0) or 0),
                        source=DataSource.BIRDEYE,
                    )
                    logger.info(f"Got price for {address[:16]}... from BirdEye")
                    return AggregatorResult(
                        success=True,
                        data=token_data,
                        source=DataSource.BIRDEYE,
                        sources_tried=sources_tried,
                    )
                last_error = result.error
                
            elif source == DataSource.GECKOTERMINAL:
                result = geckoterminal.fetch_token(chain, address)
                if result:
                    attrs = result.get("data", {}).get("attributes", {})
                    token_data = TokenData(
                        address=address,
                        symbol=attrs.get("symbol", ""),
                        name=attrs.get("name", ""),
                        price_usd=float(attrs.get("price_usd", 0) or 0),
                        source=DataSource.GECKOTERMINAL,
                    )
                    logger.info(f"Got price for {address[:16]}... from GeckoTerminal")
                    return AggregatorResult(
                        success=True,
                        data=token_data,
                        source=DataSource.GECKOTERMINAL,
                        sources_tried=sources_tried,
                    )
                last_error = "no_data"
                
        except Exception as e:
            logger.warning(f"Error fetching from {source.value}: {e}")
            last_error = str(e)
            continue
    
    logger.error(f"Failed to get price for {address} from all sources")
    return AggregatorResult(
        success=False,
        error=last_error or "all_sources_failed",
        sources_tried=sources_tried,
    )


def get_trending_tokens(
    *,
    chain: str = "solana",
    min_liquidity: float = 10_000,
    min_volume: float = 100_000,
    limit: int = 20,
    sources: Optional[List[DataSource]] = None,
) -> AggregatorResult:
    """
    Get trending tokens from multiple sources with fallback.
    
    Args:
        chain: Blockchain (default: solana)
        min_liquidity: Minimum liquidity filter
        min_volume: Minimum 24h volume filter
        limit: Maximum results
        sources: Override source priority
    
    Returns:
        AggregatorResult with list of TokenData
    """
    priority = sources or TRENDING_PRIORITY
    sources_tried = []
    last_error = None
    
    for source in priority:
        sources_tried.append(source.value)
        
        try:
            if source == DataSource.DEXSCREENER:
                pairs = dexscreener.get_solana_trending(
                    min_liquidity=min_liquidity,
                    min_volume_24h=min_volume,
                    limit=limit,
                )
                if pairs:
                    tokens = [
                        TokenData(
                            address=p.base_token_address,
                            symbol=p.base_token_symbol,
                            name=p.base_token_name,
                            price_usd=p.price_usd,
                            price_change_1h=p.price_change_1h,
                            price_change_24h=p.price_change_24h,
                            price_change_5m=p.price_change_5m,
                            volume_24h=p.volume_24h,
                            volume_1h=p.volume_1h,
                            liquidity_usd=p.liquidity_usd,
                            source=DataSource.DEXSCREENER,
                        )
                        for p in pairs
                    ]
                    logger.info(f"Got {len(tokens)} trending tokens from DexScreener")
                    return AggregatorResult(
                        success=True,
                        data=tokens,
                        source=DataSource.DEXSCREENER,
                        sources_tried=sources_tried,
                    )
                last_error = "no_results"
                
            elif source == DataSource.BIRDEYE:
                if not birdeye.has_api_key():
                    last_error = "no_api_key"
                    continue
                    
                result = birdeye.fetch_trending_tokens(chain=chain, limit=limit * 2)
                if result:
                    raw_tokens = result.get("data", {}).get("tokens", [])
                    tokens = []
                    for t in raw_tokens:
                        liq = float(t.get("liquidity", 0) or 0)
                        vol = float(t.get("volume24hUSD", 0) or 0)
                        if liq >= min_liquidity and vol >= min_volume:
                            tokens.append(TokenData(
                                address=t.get("address", ""),
                                symbol=t.get("symbol", ""),
                                name=t.get("name", ""),
                                price_usd=float(t.get("price", 0) or 0),
                                volume_24h=vol,
                                liquidity_usd=liq,
                                source=DataSource.BIRDEYE,
                            ))
                            if len(tokens) >= limit:
                                break
                    if tokens:
                        logger.info(f"Got {len(tokens)} trending tokens from BirdEye")
                        return AggregatorResult(
                            success=True,
                            data=tokens,
                            source=DataSource.BIRDEYE,
                            sources_tried=sources_tried,
                        )
                last_error = "no_results"
                
        except Exception as e:
            logger.warning(f"Error fetching trending from {source.value}: {e}")
            last_error = str(e)
            continue
    
    logger.error("Failed to get trending tokens from all sources")
    return AggregatorResult(
        success=False,
        error=last_error or "all_sources_failed",
        sources_tried=sources_tried,
    )


def get_momentum_tokens(
    *,
    chain: str = "solana",
    min_liquidity: float = 10_000,
    min_volume: float = 100_000,
    limit: int = 20,
) -> AggregatorResult:
    """
    Get tokens with recent momentum (price movement).
    
    Uses DexScreener as primary source since it has the best
    short-term price change data (5m, 1h).
    """
    try:
        pairs = dexscreener.get_momentum_tokens(
            min_liquidity=min_liquidity,
            min_volume_24h=min_volume,
            limit=limit,
        )
        
        if pairs:
            tokens = [
                TokenData(
                    address=p.base_token_address,
                    symbol=p.base_token_symbol,
                    name=p.base_token_name,
                    price_usd=p.price_usd,
                    price_change_1h=p.price_change_1h,
                    price_change_24h=p.price_change_24h,
                    price_change_5m=p.price_change_5m,
                    volume_24h=p.volume_24h,
                    volume_1h=p.volume_1h,
                    liquidity_usd=p.liquidity_usd,
                    source=DataSource.DEXSCREENER,
                )
                for p in pairs
            ]
            logger.info(f"Got {len(tokens)} momentum tokens")
            return AggregatorResult(
                success=True,
                data=tokens,
                source=DataSource.DEXSCREENER,
                sources_tried=["dexscreener"],
            )
        
        return AggregatorResult(
            success=False,
            error="no_momentum_tokens",
            sources_tried=["dexscreener"],
        )
        
    except Exception as e:
        logger.error(f"Error fetching momentum tokens: {e}")
        return AggregatorResult(
            success=False,
            error=str(e),
            sources_tried=["dexscreener"],
        )


def get_ohlcv(
    address: str,
    *,
    chain: str = "solana",
    timeframe: str = "1H",
    limit: int = 100,
    sources: Optional[List[DataSource]] = None,
) -> AggregatorResult:
    """
    Get OHLCV data from multiple sources with fallback.
    
    Args:
        address: Token or pool address
        chain: Blockchain
        timeframe: Candle timeframe (1m, 5m, 15m, 1H, 4H, 1D)
        limit: Number of candles
        sources: Override source priority
    
    Returns:
        AggregatorResult with list of OHLCV candles
    """
    priority = sources or OHLCV_PRIORITY
    sources_tried = []
    last_error = None
    
    for source in priority:
        sources_tried.append(source.value)
        
        try:
            if source == DataSource.BIRDEYE:
                if not birdeye.has_api_key():
                    last_error = "no_api_key"
                    continue
                    
                result = birdeye.fetch_ohlcv_safe(address, chain=chain, timeframe=timeframe, limit=limit)
                if result.success and result.data:
                    candles = birdeye.normalize_ohlcv(result.data)
                    if candles:
                        logger.info(f"Got {len(candles)} candles from BirdEye")
                        return AggregatorResult(
                            success=True,
                            data=candles,
                            source=DataSource.BIRDEYE,
                            sources_tried=sources_tried,
                        )
                last_error = result.error or "no_data"
                
            elif source == DataSource.GECKOTERMINAL:
                # GeckoTerminal uses pool address, not token address
                # Would need pool address lookup first
                result = geckoterminal.fetch_pool_ohlcv_safe(chain, address, timeframe, limit=limit)
                if result.success and result.data:
                    ohlcv_list = result.data.get("data", {}).get("attributes", {}).get("ohlcv_list", [])
                    candles = geckoterminal.normalize_ohlcv_list(ohlcv_list)
                    if candles:
                        logger.info(f"Got {len(candles)} candles from GeckoTerminal")
                        return AggregatorResult(
                            success=True,
                            data=candles,
                            source=DataSource.GECKOTERMINAL,
                            sources_tried=sources_tried,
                        )
                last_error = result.error or "no_data"
                
        except Exception as e:
            logger.warning(f"Error fetching OHLCV from {source.value}: {e}")
            last_error = str(e)
            continue
    
    logger.error(f"Failed to get OHLCV for {address} from all sources")
    return AggregatorResult(
        success=False,
        error=last_error or "all_sources_failed",
        sources_tried=sources_tried,
    )


def clear_all_caches() -> Dict[str, int]:
    """Clear caches for all data sources."""
    return {
        "birdeye": birdeye.clear_cache(),
        "dexscreener": dexscreener.clear_cache(),
        "geckoterminal": geckoterminal.clear_cache(),
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    print("=== Data Aggregator Status ===")
    status = get_sources_status()
    for source, info in status.items():
        print(f"\n{source}:")
        for k, v in info.items():
            print(f"  {k}: {v}")
    
    print("\n=== Testing Price Lookup ===")
    # Test with RAY token
    ray_address = "4k3Dyjzvzp8eMZWUXbBCjEvwSkkk59S5iCNLY3QrkX6R"
    result = get_token_price(ray_address)
    if result.success:
        print(f"RAY price: ${result.data.price_usd:.4f} (from {result.source.value})")
    else:
        print(f"Failed: {result.error} (tried: {result.sources_tried})")
    
    print("\n=== Testing Trending Tokens ===")
    result = get_trending_tokens(limit=5)
    if result.success:
        print(f"Got {len(result.data)} trending tokens from {result.source.value}:")
        for token in result.data[:3]:
            print(f"  {token.symbol}: ${token.price_usd:.6f} (vol: ${token.volume_24h/1000:.0f}K)")
    else:
        print(f"Failed: {result.error}")
    
    print("\n=== Testing Momentum Tokens ===")
    result = get_momentum_tokens(limit=5)
    if result.success:
        print(f"Got {len(result.data)} momentum tokens:")
        for token in result.data[:3]:
            print(f"  {token.symbol}: 5m={token.price_change_5m:+.1f}%, 1h={token.price_change_1h:+.1f}%")
    else:
        print(f"Failed: {result.error}")
