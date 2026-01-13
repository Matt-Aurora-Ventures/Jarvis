"""
Data Sources Module

Provides live data feeds for various market data:
- Commodity prices (gold, silver, etc.)
- Stock prices
- Crypto prices
- Hyperliquid perp data (order book, liquidations, funding)

Created to avoid stale training data issues with AI models.
"""

from core.data_sources.commodity_prices import (
    CommodityPriceClient,
    CommodityPrice,
    get_commodity_client,
    get_live_gold_price,
    get_live_silver_price,
)

from core.data_sources.hyperliquid_api import (
    HyperliquidClient,
    TimeFrame,
    OrderBookLevel,
    Trade,
    Position,
    FundingRate,
    LiquidationEvent,
    get_client as get_hyperliquid_client,
)

from core.data_sources.twelve_data import (
    TwelveDataClient,
    Interval as TwelveDataInterval,
    Quote,
    OHLCV,
    TechnicalIndicator,
    get_client as get_twelve_data_client,
)

from core.data_sources.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerRegistry,
    CircuitOpenError,
    get_breaker,
    get_api_breaker,
    get_registry,
)

__all__ = [
    # Commodities
    'CommodityPriceClient',
    'CommodityPrice',
    'get_commodity_client',
    'get_live_gold_price',
    'get_live_silver_price',
    # Hyperliquid
    'HyperliquidClient',
    'TimeFrame',
    'OrderBookLevel',
    'Trade',
    'Position',
    'FundingRate',
    'LiquidationEvent',
    'get_hyperliquid_client',
    # Twelve Data (Traditional Markets)
    'TwelveDataClient',
    'TwelveDataInterval',
    'Quote',
    'OHLCV',
    'TechnicalIndicator',
    'get_twelve_data_client',
    # Circuit Breaker (Fault Tolerance)
    'CircuitBreaker',
    'CircuitBreakerConfig',
    'CircuitBreakerRegistry',
    'CircuitOpenError',
    'get_breaker',
    'get_api_breaker',
    'get_registry',
]
