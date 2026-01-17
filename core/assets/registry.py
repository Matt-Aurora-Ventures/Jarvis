"""
Asset Registry - Centralized definition of all tradeable instruments in Jarvis.

Contains metadata for 20 wrapped assets across 4 categories:
- Solana Native (5): SOL, BTC, ETH, BONK, JUP
- xStocks (7): xNVDA, xTSLA, xAAPL, xGOOG, xAMZN, xMSFT, xMETA
- PreStocks (5): pSPACEX, pOPENAI, pANTHROPIC, pXAI, pANDURIL
- Commodities (3): GOLD, SILVER, OIL
"""

from dataclasses import dataclass
from typing import Dict, Optional
from enum import Enum


class AssetCategory(Enum):
    """Asset category classification."""
    SOLANA_NATIVE = "solana_native"
    XSTOCKS = "xstocks"
    PRESTOCKS = "prestocks"
    COMMODITIES = "commodities"


@dataclass
class SentimentWeights:
    """Sentiment component weights for self-tuning engine."""
    price_momentum: float = 0.20  # 20% - Recent price movement
    volume: float = 0.15  # 15% - Trading volume spike
    social_sentiment: float = 0.25  # 25% - Grok AI sentiment analysis
    whale_activity: float = 0.20  # 20% - Large wallet movements
    technical_analysis: float = 0.20  # 20% - Technical indicators


@dataclass
class Asset:
    """Asset definition with metadata and sentiment configuration."""
    symbol: str
    display_name: str
    category: AssetCategory
    contract_address: str
    decimals: int
    sector: str  # For portfolio sector breakdown
    sentiment_weights: SentimentWeights = None
    
    def __post_init__(self):
        if self.sentiment_weights is None:
            self.sentiment_weights = SentimentWeights()
    
    @property
    def is_native_solana(self) -> bool:
        return self.category == AssetCategory.SOLANA_NATIVE
    
    @property
    def is_wrapped(self) -> bool:
        return self.category in (AssetCategory.XSTOCKS, AssetCategory.PRESTOCKS, AssetCategory.COMMODITIES)


class AssetRegistry:
    """Central registry for all tradeable assets."""
    
    # Solana Native Assets (5)
    SOL = Asset(
        symbol="SOL",
        display_name="Solana",
        category=AssetCategory.SOLANA_NATIVE,
        contract_address="So11111111111111111111111111111111111111112",  # Wrapped SOL
        decimals=9,
        sector="Layer-1 Blockchain",
        sentiment_weights=SentimentWeights(
            price_momentum=0.25,
            volume=0.15,
            social_sentiment=0.20,
            whale_activity=0.25,
            technical_analysis=0.15,
        )
    )
    
    BTC = Asset(
        symbol="BTC",
        display_name="Bitcoin (Solana)",
        category=AssetCategory.SOLANA_NATIVE,
        contract_address="9n4nbM75f5Ui33ZbPYen9qC2EyTw3371fDwQesEHcaH",  # btcSOL or wormhole BTC
        decimals=8,
        sector="Digital Asset",
        sentiment_weights=SentimentWeights(
            price_momentum=0.30,
            volume=0.15,
            social_sentiment=0.15,
            whale_activity=0.25,
            technical_analysis=0.15,
        )
    )
    
    ETH = Asset(
        symbol="ETH",
        display_name="Ethereum (Solana)",
        category=AssetCategory.SOLANA_NATIVE,
        contract_address="2FPyTwcZLUg1MDrwsyoP4D6sA3kVJisEdmgvvAh2YvTn",  # ethSOL or wormhole ETH
        decimals=8,
        sector="Digital Asset",
        sentiment_weights=SentimentWeights(
            price_momentum=0.25,
            volume=0.15,
            social_sentiment=0.20,
            whale_activity=0.25,
            technical_analysis=0.15,
        )
    )
    
    BONK = Asset(
        symbol="BONK",
        display_name="Bonk",
        category=AssetCategory.SOLANA_NATIVE,
        contract_address="DezXAZ8z7PnrnRJjz3wXBoRgixVqXaSo1ngnSyUcrVJ",
        decimals=5,
        sector="Meme Coin",
        sentiment_weights=SentimentWeights(
            price_momentum=0.35,
            volume=0.20,
            social_sentiment=0.30,
            whale_activity=0.10,
            technical_analysis=0.05,
        )
    )
    
    JUP = Asset(
        symbol="JUP",
        display_name="Jupiter",
        category=AssetCategory.SOLANA_NATIVE,
        contract_address="JUP6i3Z5FYwjV24ND5r5tau2pDWZjhCoXcqtiqWnP98",
        decimals=6,
        sector="DEX Protocol",
        sentiment_weights=SentimentWeights(
            price_momentum=0.22,
            volume=0.18,
            social_sentiment=0.22,
            whale_activity=0.20,
            technical_analysis=0.18,
        )
    )
    
    # xStocks - Wrapped Stock Tokens (7)
    XNVDA = Asset(
        symbol="xNVDA",
        display_name="NVIDIA Stock",
        category=AssetCategory.XSTOCKS,
        contract_address="",  # Placeholder - actual address from wrapped stock provider
        decimals=8,
        sector="Technology",
        sentiment_weights=SentimentWeights(
            price_momentum=0.18,
            volume=0.12,
            social_sentiment=0.25,
            whale_activity=0.25,
            technical_analysis=0.20,
        )
    )
    
    XTSLA = Asset(
        symbol="xTSLA",
        display_name="Tesla Stock",
        category=AssetCategory.XSTOCKS,
        contract_address="",  # Placeholder
        decimals=8,
        sector="Automotive",
        sentiment_weights=SentimentWeights(
            price_momentum=0.20,
            volume=0.12,
            social_sentiment=0.25,
            whale_activity=0.23,
            technical_analysis=0.20,
        )
    )
    
    XAAPL = Asset(
        symbol="xAAPL",
        display_name="Apple Stock",
        category=AssetCategory.XSTOCKS,
        contract_address="",  # Placeholder
        decimals=8,
        sector="Technology",
        sentiment_weights=SentimentWeights(
            price_momentum=0.18,
            volume=0.12,
            social_sentiment=0.22,
            whale_activity=0.26,
            technical_analysis=0.22,
        )
    )
    
    XGOOG = Asset(
        symbol="xGOOG",
        display_name="Google Stock",
        category=AssetCategory.XSTOCKS,
        contract_address="",  # Placeholder
        decimals=8,
        sector="Technology",
        sentiment_weights=SentimentWeights(
            price_momentum=0.18,
            volume=0.12,
            social_sentiment=0.22,
            whale_activity=0.26,
            technical_analysis=0.22,
        )
    )
    
    XAMZN = Asset(
        symbol="xAMZN",
        display_name="Amazon Stock",
        category=AssetCategory.XSTOCKS,
        contract_address="",  # Placeholder
        decimals=8,
        sector="Technology",
        sentiment_weights=SentimentWeights(
            price_momentum=0.18,
            volume=0.12,
            social_sentiment=0.22,
            whale_activity=0.26,
            technical_analysis=0.22,
        )
    )
    
    XMSFT = Asset(
        symbol="xMSFT",
        display_name="Microsoft Stock",
        category=AssetCategory.XSTOCKS,
        contract_address="",  # Placeholder
        decimals=8,
        sector="Technology",
        sentiment_weights=SentimentWeights(
            price_momentum=0.18,
            volume=0.12,
            social_sentiment=0.22,
            whale_activity=0.26,
            technical_analysis=0.22,
        )
    )
    
    XMETA = Asset(
        symbol="xMETA",
        display_name="Meta Stock",
        category=AssetCategory.XSTOCKS,
        contract_address="",  # Placeholder
        decimals=8,
        sector="Technology",
        sentiment_weights=SentimentWeights(
            price_momentum=0.20,
            volume=0.12,
            social_sentiment=0.24,
            whale_activity=0.24,
            technical_analysis=0.20,
        )
    )
    
    # PreStocks - Future Company Stock Tokens (5)
    PSSPACEX = Asset(
        symbol="pSPACEX",
        display_name="SpaceX Pre-IPO",
        category=AssetCategory.PRESTOCKS,
        contract_address="",  # Placeholder
        decimals=8,
        sector="Aerospace & Defense",
        sentiment_weights=SentimentWeights(
            price_momentum=0.25,
            volume=0.15,
            social_sentiment=0.25,
            whale_activity=0.20,
            technical_analysis=0.15,
        )
    )
    
    POPENAI = Asset(
        symbol="pOPENAI",
        display_name="OpenAI Pre-IPO",
        category=AssetCategory.PRESTOCKS,
        contract_address="",  # Placeholder
        decimals=8,
        sector="Artificial Intelligence",
        sentiment_weights=SentimentWeights(
            price_momentum=0.25,
            volume=0.15,
            social_sentiment=0.30,
            whale_activity=0.15,
            technical_analysis=0.15,
        )
    )
    
    Panthropic = Asset(
        symbol="pANTHROPIC",
        display_name="Anthropic Pre-IPO",
        category=AssetCategory.PRESTOCKS,
        contract_address="",  # Placeholder
        decimals=8,
        sector="Artificial Intelligence",
        sentiment_weights=SentimentWeights(
            price_momentum=0.25,
            volume=0.15,
            social_sentiment=0.30,
            whale_activity=0.15,
            technical_analysis=0.15,
        )
    )
    
    PXAI = Asset(
        symbol="pXAI",
        display_name="xAI Pre-IPO",
        category=AssetCategory.PRESTOCKS,
        contract_address="",  # Placeholder
        decimals=8,
        sector="Artificial Intelligence",
        sentiment_weights=SentimentWeights(
            price_momentum=0.25,
            volume=0.15,
            social_sentiment=0.30,
            whale_activity=0.15,
            technical_analysis=0.15,
        )
    )
    
    PANDURIL = Asset(
        symbol="pANDURIL",
        display_name="Anduril Pre-IPO",
        category=AssetCategory.PRESTOCKS,
        contract_address="",  # Placeholder
        decimals=8,
        sector="Defense Technology",
        sentiment_weights=SentimentWeights(
            price_momentum=0.22,
            volume=0.13,
            social_sentiment=0.23,
            whale_activity=0.22,
            technical_analysis=0.20,
        )
    )
    
    # Commodities (3)
    GOLD = Asset(
        symbol="GOLD",
        display_name="Gold (Commodity)",
        category=AssetCategory.COMMODITIES,
        contract_address="",  # Placeholder
        decimals=8,
        sector="Commodity",
        sentiment_weights=SentimentWeights(
            price_momentum=0.15,
            volume=0.15,
            social_sentiment=0.20,
            whale_activity=0.25,
            technical_analysis=0.25,
        )
    )
    
    SILVER = Asset(
        symbol="SILVER",
        display_name="Silver (Commodity)",
        category=AssetCategory.COMMODITIES,
        contract_address="",  # Placeholder
        decimals=8,
        sector="Commodity",
        sentiment_weights=SentimentWeights(
            price_momentum=0.15,
            volume=0.15,
            social_sentiment=0.20,
            whale_activity=0.25,
            technical_analysis=0.25,
        )
    )
    
    OIL = Asset(
        symbol="OIL",
        display_name="Oil (Commodity)",
        category=AssetCategory.COMMODITIES,
        contract_address="",  # Placeholder
        decimals=8,
        sector="Commodity",
        sentiment_weights=SentimentWeights(
            price_momentum=0.18,
            volume=0.15,
            social_sentiment=0.18,
            whale_activity=0.24,
            technical_analysis=0.25,
        )
    )
    
    # Registry lookup methods
    _ASSETS_BY_SYMBOL: Dict[str, Asset] = None
    _ALL_ASSETS: list = None
    
    @classmethod
    def _build_registry(cls):
        """Build the registry lookup tables on first access."""
        if cls._ASSETS_BY_SYMBOL is not None:
            return
        
        cls._ASSETS_BY_SYMBOL = {}
        cls._ALL_ASSETS = []
        
        for attr_name in dir(cls):
            attr = getattr(cls, attr_name)
            if isinstance(attr, Asset):
                cls._ASSETS_BY_SYMBOL[attr.symbol] = attr
                cls._ALL_ASSETS.append(attr)
        
        # Sort by symbol for consistent ordering
        cls._ALL_ASSETS.sort(key=lambda a: a.symbol)
    
    @classmethod
    def get_asset(cls, symbol: str) -> Optional[Asset]:
        """Get asset by symbol (case-insensitive)."""
        cls._build_registry()
        return cls._ASSETS_BY_SYMBOL.get(symbol.upper())
    
    @classmethod
    def get_all_assets(cls) -> list:
        """Get all assets in registry."""
        cls._build_registry()
        return cls._ALL_ASSETS.copy()
    
    @classmethod
    def get_assets_by_category(cls, category: AssetCategory) -> list:
        """Get all assets in a specific category."""
        cls._build_registry()
        return [a for a in cls._ALL_ASSETS if a.category == category]
    
    @classmethod
    def get_solana_native(cls) -> list:
        """Get all Solana native assets."""
        return cls.get_assets_by_category(AssetCategory.SOLANA_NATIVE)
    
    @classmethod
    def get_xstocks(cls) -> list:
        """Get all xStock tokens."""
        return cls.get_assets_by_category(AssetCategory.XSTOCKS)
    
    @classmethod
    def get_prestocks(cls) -> list:
        """Get all PreStock tokens."""
        return cls.get_assets_by_category(AssetCategory.PRESTOCKS)
    
    @classmethod
    def get_commodities(cls) -> list:
        """Get all commodity tokens."""
        return cls.get_assets_by_category(AssetCategory.COMMODITIES)
    
    @classmethod
    def get_sector_breakdown(cls) -> Dict[str, int]:
        """Get count of assets per sector."""
        cls._build_registry()
        sectors = {}
        for asset in cls._ALL_ASSETS:
            sectors[asset.sector] = sectors.get(asset.sector, 0) + 1
        return sectors
    
    @classmethod
    def total_assets(cls) -> int:
        """Get total number of assets in registry."""
        cls._build_registry()
        return len(cls._ALL_ASSETS)
    
    @classmethod
    def list_symbols(cls) -> list:
        """Get list of all asset symbols."""
        cls._build_registry()
        return [a.symbol for a in cls._ALL_ASSETS]


# Export for easy access
__all__ = [
    'Asset',
    'AssetRegistry',
    'AssetCategory',
    'SentimentWeights',
]


if __name__ == "__main__":
    # Quick test
    print(f"Total assets: {AssetRegistry.total_assets()}")
    print(f"\nAsset symbols: {AssetRegistry.list_symbols()}")
    print(f"\nSector breakdown: {AssetRegistry.get_sector_breakdown()}")
    
    print(f"\nSolana Native ({len(AssetRegistry.get_solana_native())}):")
    for asset in AssetRegistry.get_solana_native():
        print(f"  - {asset.symbol}: {asset.display_name}")
    
    print(f"\nxStocks ({len(AssetRegistry.get_xstocks())}):")
    for asset in AssetRegistry.get_xstocks():
        print(f"  - {asset.symbol}: {asset.display_name}")
    
    print(f"\nPreStocks ({len(AssetRegistry.get_prestocks())}):")
    for asset in AssetRegistry.get_prestocks():
        print(f"  - {asset.symbol}: {asset.display_name}")
    
    print(f"\nCommodities ({len(AssetRegistry.get_commodities())}):")
    for asset in AssetRegistry.get_commodities():
        print(f"  - {asset.symbol}: {asset.display_name}")
    
    print(f"\nLookup test - SOL: {AssetRegistry.get_asset('SOL').display_name}")
    print(f"Lookup test - BTC: {AssetRegistry.get_asset('btc').display_name}")
