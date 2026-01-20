"""
Analysis System - Content analysis, credibility scoring, market regime detection, order book analysis, and correlation analysis.

Provides:
- CredibilityScorer: Evaluate trustworthiness of sources and content
- SourceProfile: Profile of information sources
- CredibilityAssessment: Assessment results for content
- RegimeDetector: Detect market regimes (trending, ranging, volatile, crash)
- StrategyRecommendation: Strategy recommendations per regime
- OrderBookAnalyzer: Analyze order book depth, liquidity, and walls
- OrderBookSnapshot: Snapshot of order book data
- OrderBookAnalysis: Analysis results
- CorrelationAnalyzer: Analyze asset correlations for portfolio management
- CorrelationResult: Correlation calculation result with significance
- BreakdownEvent: Correlation breakdown detection event
"""

from core.analysis.credibility import (
    CredibilityScorer,
    SourceProfile,
    CredibilityAssessment,
    SourceCategory,
    CredibilityTier,
    BiasLevel,
    get_credibility_scorer,
)

# Correlation Analysis
from core.analysis.correlation_analyzer import (
    CorrelationAnalyzer,
    CorrelationResult,
    BreakdownEvent,
    LeadLagResult,
    get_correlation_analyzer,
)

# Optional imports for modules that may not exist
try:
    from core.analysis.regime_detector import (
        MarketRegime,
        RegimeDetectionResult,
        RegimeTransition,
        RegimeFeatureExtractor,
        RegimeDetector,
        StrategyRecommendation,
        get_regime_detector,
    )
    _has_regime_detector = True
except ImportError:
    _has_regime_detector = False

try:
    from core.analysis.order_book_analyzer import (
        OrderBookAnalyzer,
        OrderBookSnapshot,
        OrderBookAnalysis,
        SlippageEstimate,
        Wall,
        LiquidityGrade,
        get_order_book_analyzer,
    )
    _has_order_book = True
except ImportError:
    _has_order_book = False

__all__ = [
    # Credibility
    "CredibilityScorer",
    "SourceProfile",
    "CredibilityAssessment",
    "SourceCategory",
    "CredibilityTier",
    "BiasLevel",
    "get_credibility_scorer",
    # Correlation Analysis
    "CorrelationAnalyzer",
    "CorrelationResult",
    "BreakdownEvent",
    "LeadLagResult",
    "get_correlation_analyzer",
]

# Add regime detector exports if available
if _has_regime_detector:
    __all__.extend([
        "MarketRegime",
        "RegimeDetectionResult",
        "RegimeTransition",
        "RegimeFeatureExtractor",
        "RegimeDetector",
        "StrategyRecommendation",
        "get_regime_detector",
    ])

# Add order book exports if available
if _has_order_book:
    __all__.extend([
        "OrderBookAnalyzer",
        "OrderBookSnapshot",
        "OrderBookAnalysis",
        "SlippageEstimate",
        "Wall",
        "LiquidityGrade",
        "get_order_book_analyzer",
    ])
