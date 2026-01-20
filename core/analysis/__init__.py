"""
Analysis System - Content analysis, credibility scoring, and market regime detection.

Provides:
- CredibilityScorer: Evaluate trustworthiness of sources and content
- SourceProfile: Profile of information sources
- CredibilityAssessment: Assessment results for content
- RegimeDetector: Detect market regimes (trending, ranging, volatile, crash)
- StrategyRecommendation: Strategy recommendations per regime
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

from core.analysis.regime_detector import (
    MarketRegime,
    RegimeDetectionResult,
    RegimeTransition,
    RegimeFeatureExtractor,
    RegimeDetector,
    StrategyRecommendation,
    get_regime_detector,
)

__all__ = [
    # Credibility
    "CredibilityScorer",
    "SourceProfile",
    "CredibilityAssessment",
    "SourceCategory",
    "CredibilityTier",
    "BiasLevel",
    "get_credibility_scorer",
    # Regime Detection
    "MarketRegime",
    "RegimeDetectionResult",
    "RegimeTransition",
    "RegimeFeatureExtractor",
    "RegimeDetector",
    "StrategyRecommendation",
    "get_regime_detector",
]
