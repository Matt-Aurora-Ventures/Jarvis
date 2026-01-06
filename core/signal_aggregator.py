"""
Unified Trading Signal Aggregator
==================================

Combines all data sources with Grok sentiment analysis for comprehensive
token signals used in trading decisions.

Integrates:
- DexScreener (primary price/volume data)
- BirdEye (Solana token data, OHLCV)
- GeckoTerminal (pools, charts)
- DexTools (hot pairs, audit scores)
- GMGN (smart money, security)
- Lute.gg (momentum calls)
- Grok/X (sentiment analysis)

Usage:
    from core.signal_aggregator import get_comprehensive_signal, get_momentum_opportunities
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class SignalStrength(Enum):
    """Signal strength levels."""
    STRONG_BUY = "strong_buy"
    BUY = "buy"
    NEUTRAL = "neutral"
    SELL = "sell"
    STRONG_SELL = "strong_sell"
    AVOID = "avoid"  # Security concerns


@dataclass
class TokenSignal:
    """Comprehensive token trading signal."""
    address: str
    symbol: str
    name: str
    chain: str = "solana"
    
    # Price data
    price_usd: float = 0.0
    price_change_5m: float = 0.0
    price_change_1h: float = 0.0
    price_change_24h: float = 0.0
    
    # Volume/Liquidity
    volume_24h: float = 0.0
    volume_1h: float = 0.0
    liquidity_usd: float = 0.0
    
    # Momentum indicators
    momentum_score: float = 0.0  # 0-100
    lute_call_count: int = 0
    dextools_hot_level: int = 0
    
    # Smart money
    smart_money_signal: str = "neutral"  # bullish, bearish, neutral
    insider_activity: str = "none"
    
    # Security
    security_score: float = 0.0  # 0-100
    risk_level: str = "unknown"
    security_warnings: List[str] = field(default_factory=list)
    
    # Sentiment (Grok)
    sentiment: str = "neutral"  # positive, negative, neutral, mixed
    sentiment_confidence: float = 0.0
    sentiment_topics: List[str] = field(default_factory=list)
    
    # Aggregated signal
    signal: str = "neutral"  # SignalStrength value
    signal_score: float = 0.0  # -100 to +100
    signal_reasons: List[str] = field(default_factory=list)
    
    # Metadata
    sources_used: List[str] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class SignalResult:
    """Result from signal operations."""
    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None
    sources_tried: List[str] = field(default_factory=list)


def _safe_import(module_name: str):
    """Safely import a module, returning None if not available."""
    try:
        import importlib
        return importlib.import_module(module_name)
    except ImportError:
        return None


def get_comprehensive_signal(
    token_address: str,
    *,
    chain: str = "solana",
    include_sentiment: bool = True,
    sentiment_context: str = "",
) -> SignalResult:
    """
    Get comprehensive trading signal for a token.
    
    Aggregates data from all available sources and computes
    a unified signal with Grok sentiment integration.
    
    Args:
        token_address: Token contract address
        chain: Blockchain (default: solana)
        include_sentiment: Whether to include Grok sentiment
        sentiment_context: Additional context for sentiment analysis
    
    Returns:
        SignalResult with TokenSignal
    """
    sources_tried = []
    signal = TokenSignal(address=token_address, chain=chain)
    
    # 1. Get price data from DexScreener (primary)
    try:
        from core import dexscreener
        result = dexscreener.get_pairs_by_token(token_address)
        sources_tried.append("dexscreener")
        
        if result.success and result.data:
            pairs = result.data.get("pairs", [])
            if pairs:
                pair = pairs[0]
                base = pair.get("baseToken", {})
                signal.symbol = base.get("symbol", "")
                signal.name = base.get("name", "")
                signal.price_usd = float(pair.get("priceUsd", 0) or 0)
                signal.price_change_5m = float(pair.get("priceChange", {}).get("m5", 0) or 0)
                signal.price_change_1h = float(pair.get("priceChange", {}).get("h1", 0) or 0)
                signal.price_change_24h = float(pair.get("priceChange", {}).get("h24", 0) or 0)
                signal.volume_24h = float(pair.get("volume", {}).get("h24", 0) or 0)
                signal.volume_1h = float(pair.get("volume", {}).get("h1", 0) or 0)
                signal.liquidity_usd = float(pair.get("liquidity", {}).get("usd", 0) or 0)
                signal.sources_used.append("dexscreener")
    except Exception as e:
        logger.debug(f"DexScreener failed: {e}")
    
    # 2. Get DexTools data (hot level, audit)
    try:
        from core import dextools
        result = dextools.get_token_info(token_address, chain=chain)
        sources_tried.append("dextools")
        
        if result.success and result.data:
            token = result.data
            signal.dextools_hot_level = getattr(token, 'hot_level', 0)
            if hasattr(token, 'audit_score') and token.audit_score > 0:
                signal.security_score = max(signal.security_score, token.audit_score)
            signal.sources_used.append("dextools")
    except Exception as e:
        logger.debug(f"DexTools failed: {e}")
    
    # 3. Get GMGN security and smart money data
    try:
        from core import gmgn_metrics
        
        # Security check
        sec_result = gmgn_metrics.analyze_token_security(token_address, chain="sol" if chain == "solana" else chain)
        sources_tried.append("gmgn_security")
        
        if sec_result.success and sec_result.data:
            sec = sec_result.data
            signal.security_score = sec.security_score
            signal.risk_level = sec.risk_level
            signal.security_warnings = sec.warnings[:5]
            signal.sources_used.append("gmgn")
        
        # Smart money activity
        sm_result = gmgn_metrics.get_smart_money_activity(token_address)
        sources_tried.append("gmgn_smart_money")
        
        if sm_result.success and sm_result.data:
            sm = sm_result.data
            signal.smart_money_signal = sm.smart_money_signal
            if sm.insider_buys > 0 or sm.insider_sells > 0:
                signal.insider_activity = f"{sm.insider_buys} buys, {sm.insider_sells} sells"
    except Exception as e:
        logger.debug(f"GMGN failed: {e}")
    
    # 4. Get Lute momentum signals
    try:
        from core import lute_momentum
        result = lute_momentum.get_momentum_signals(chain=chain)
        sources_tried.append("lute")
        
        if result.success and result.data:
            for sig in result.data:
                if sig.get("token_address") == token_address:
                    signal.lute_call_count = sig.get("call_count", 0)
                    signal.momentum_score = sig.get("momentum_score", 0) * 25  # Scale to 0-100
                    signal.sources_used.append("lute")
                    break
    except Exception as e:
        logger.debug(f"Lute momentum failed: {e}")
    
    # 5. Get Grok sentiment analysis
    if include_sentiment and signal.symbol:
        try:
            from core import x_sentiment
            
            text = f"${signal.symbol} Solana token"
            if sentiment_context:
                text = f"{text} {sentiment_context}"
            
            result = x_sentiment.analyze_sentiment(text, focus="trading")
            sources_tried.append("grok_sentiment")
            
            if result:
                signal.sentiment = result.sentiment
                signal.sentiment_confidence = result.confidence
                signal.sentiment_topics = result.key_topics[:5]
                signal.sources_used.append("grok")
        except Exception as e:
            logger.debug(f"Grok sentiment failed: {e}")
    
    # 6. Calculate aggregated signal
    signal = _calculate_signal(signal)
    
    return SignalResult(
        success=True,
        data=signal,
        sources_tried=sources_tried,
    )


def _calculate_signal(signal: TokenSignal) -> TokenSignal:
    """Calculate aggregated signal score and strength."""
    score = 0.0
    reasons = []
    
    # Price momentum (weight: 25%)
    if signal.price_change_5m > 5:
        score += 10
        reasons.append(f"Strong 5m momentum: +{signal.price_change_5m:.1f}%")
    elif signal.price_change_5m > 2:
        score += 5
    elif signal.price_change_5m < -5:
        score -= 10
        reasons.append(f"Negative 5m momentum: {signal.price_change_5m:.1f}%")
    
    if signal.price_change_1h > 10:
        score += 10
        reasons.append(f"Strong 1h momentum: +{signal.price_change_1h:.1f}%")
    elif signal.price_change_1h > 3:
        score += 5
    elif signal.price_change_1h < -10:
        score -= 10
    
    # Volume (weight: 15%)
    if signal.volume_1h > 100_000:
        score += 10
        reasons.append(f"High 1h volume: ${signal.volume_1h/1000:.0f}K")
    elif signal.volume_1h > 50_000:
        score += 5
    
    # Liquidity (weight: 10%)
    if signal.liquidity_usd > 100_000:
        score += 5
    elif signal.liquidity_usd < 10_000:
        score -= 10
        reasons.append(f"Low liquidity: ${signal.liquidity_usd:.0f}")
    
    # Security (weight: 20%)
    if signal.risk_level == "critical":
        score -= 50
        reasons.append("CRITICAL security risk")
    elif signal.risk_level == "high":
        score -= 20
        reasons.append("High security risk")
    elif signal.risk_level == "low":
        score += 10
        reasons.append("Good security score")
    
    if signal.security_warnings:
        score -= len(signal.security_warnings) * 5
    
    # Smart money (weight: 15%)
    if signal.smart_money_signal == "bullish":
        score += 15
        reasons.append("Smart money bullish")
    elif signal.smart_money_signal == "bearish":
        score -= 15
        reasons.append("Smart money bearish")
    
    # Lute momentum (weight: 10%)
    if signal.lute_call_count >= 3:
        score += 10
        reasons.append(f"{signal.lute_call_count} Lute calls")
    elif signal.lute_call_count >= 1:
        score += 5
    
    # Sentiment (weight: 15%)
    if signal.sentiment == "positive" and signal.sentiment_confidence > 0.7:
        score += 15
        reasons.append(f"Strong positive sentiment ({signal.sentiment_confidence:.0%})")
    elif signal.sentiment == "positive":
        score += 8
    elif signal.sentiment == "negative" and signal.sentiment_confidence > 0.7:
        score -= 15
        reasons.append(f"Strong negative sentiment ({signal.sentiment_confidence:.0%})")
    elif signal.sentiment == "negative":
        score -= 8
    
    # DexTools hot level
    if signal.dextools_hot_level > 0:
        score += min(10, signal.dextools_hot_level * 2)
        reasons.append(f"DexTools hot level: {signal.dextools_hot_level}")
    
    # Clamp score
    score = max(-100, min(100, score))
    signal.signal_score = score
    
    # Determine signal strength
    if signal.risk_level == "critical":
        signal.signal = SignalStrength.AVOID.value
    elif score >= 40:
        signal.signal = SignalStrength.STRONG_BUY.value
    elif score >= 20:
        signal.signal = SignalStrength.BUY.value
    elif score <= -40:
        signal.signal = SignalStrength.STRONG_SELL.value
    elif score <= -20:
        signal.signal = SignalStrength.SELL.value
    else:
        signal.signal = SignalStrength.NEUTRAL.value
    
    signal.signal_reasons = reasons
    return signal


def get_momentum_opportunities(
    *,
    chain: str = "solana",
    min_liquidity: float = 10_000,
    min_volume_24h: float = 50_000,
    include_sentiment: bool = True,
    limit: int = 20,
) -> SignalResult:
    """
    Get tokens with momentum signals across all sources.
    
    Combines:
    - DexScreener trending pairs
    - DexTools hot pairs
    - Lute momentum calls
    - GMGN smart money activity
    
    Filters by:
    - Minimum liquidity
    - Minimum volume
    - Security score
    
    Args:
        chain: Blockchain
        min_liquidity: Minimum liquidity USD
        min_volume_24h: Minimum 24h volume
        include_sentiment: Add Grok sentiment to top results
        limit: Maximum results
    
    Returns:
        SignalResult with list of TokenSignal
    """
    candidates: Dict[str, TokenSignal] = {}
    sources_tried = []
    
    # 1. Get DexScreener momentum tokens
    try:
        from core import dexscreener
        pairs = dexscreener.get_momentum_tokens(
            min_liquidity=min_liquidity,
            min_volume_24h=min_volume_24h,
            limit=limit * 2,
        )
        sources_tried.append("dexscreener")
        
        for pair in pairs or []:
            addr = pair.base_token_address
            if addr not in candidates:
                candidates[addr] = TokenSignal(
                    address=addr,
                    symbol=pair.base_token_symbol,
                    name=pair.base_token_name,
                    chain=chain,
                    price_usd=pair.price_usd,
                    price_change_5m=pair.price_change_5m,
                    price_change_1h=pair.price_change_1h,
                    price_change_24h=pair.price_change_24h,
                    volume_24h=pair.volume_24h,
                    volume_1h=pair.volume_1h,
                    liquidity_usd=pair.liquidity_usd,
                )
                candidates[addr].sources_used.append("dexscreener")
    except Exception as e:
        logger.debug(f"DexScreener momentum failed: {e}")
    
    # 2. Get DexTools hot pairs
    try:
        from core import dextools
        result = dextools.get_hot_pairs(chain=chain, limit=limit)
        sources_tried.append("dextools")
        
        if result.success and result.data:
            for pair in result.data:
                addr = pair.base_token
                if addr not in candidates:
                    candidates[addr] = TokenSignal(
                        address=addr,
                        symbol=pair.base_symbol,
                        name="",
                        chain=chain,
                        price_usd=pair.price_usd,
                        price_change_24h=pair.price_change_24h,
                        volume_24h=pair.volume_24h,
                        liquidity_usd=pair.liquidity_usd,
                        dextools_hot_level=pair.hot_level,
                    )
                else:
                    candidates[addr].dextools_hot_level = pair.hot_level
                candidates[addr].sources_used.append("dextools")
    except Exception as e:
        logger.debug(f"DexTools hot pairs failed: {e}")
    
    # 3. Get Lute momentum signals
    try:
        from core import lute_momentum
        result = lute_momentum.get_momentum_signals(chain=chain)
        sources_tried.append("lute")
        
        if result.success and result.data:
            for sig in result.data:
                addr = sig.get("token_address", "")
                if addr and addr not in candidates:
                    candidates[addr] = TokenSignal(
                        address=addr,
                        symbol=sig.get("token_symbol", ""),
                        name="",
                        chain=chain,
                        lute_call_count=sig.get("call_count", 0),
                        momentum_score=sig.get("momentum_score", 0) * 25,
                    )
                elif addr:
                    candidates[addr].lute_call_count = sig.get("call_count", 0)
                    candidates[addr].momentum_score = sig.get("momentum_score", 0) * 25
                    candidates[addr].sources_used.append("lute")
    except Exception as e:
        logger.debug(f"Lute momentum failed: {e}")
    
    # 4. Calculate preliminary scores
    for signal in candidates.values():
        signal = _calculate_signal(signal)
    
    # 5. Sort by signal score and take top results
    sorted_candidates = sorted(
        candidates.values(),
        key=lambda s: s.signal_score,
        reverse=True,
    )[:limit]
    
    # 6. Enhance top candidates with security and sentiment
    enhanced = []
    for signal in sorted_candidates[:10]:  # Only top 10 get full enhancement
        try:
            # Add security check
            from core import gmgn_metrics
            sec_result = gmgn_metrics.analyze_token_security(signal.address)
            if sec_result.success and sec_result.data:
                sec = sec_result.data
                signal.security_score = sec.security_score
                signal.risk_level = sec.risk_level
                signal.security_warnings = sec.warnings[:3]
        except Exception:
            pass
        
        if include_sentiment and signal.symbol:
            try:
                from core import x_sentiment
                result = x_sentiment.analyze_sentiment(
                    f"${signal.symbol} Solana token trading",
                    focus="trading"
                )
                if result:
                    signal.sentiment = result.sentiment
                    signal.sentiment_confidence = result.confidence
            except Exception:
                pass
        
        # Recalculate with new data
        signal = _calculate_signal(signal)
        enhanced.append(signal)
    
    # Add remaining candidates without enhancement
    enhanced.extend(sorted_candidates[10:])
    
    return SignalResult(
        success=True,
        data=enhanced,
        sources_tried=sources_tried,
    )


def get_all_sources_status() -> Dict[str, Any]:
    """Get status of all integrated data sources."""
    status = {}
    
    sources = [
        ("dexscreener", "core.dexscreener"),
        ("birdeye", "core.birdeye"),
        ("geckoterminal", "core.geckoterminal"),
        ("dextools", "core.dextools"),
        ("gmgn", "core.gmgn_metrics"),
        ("lute", "core.lute_momentum"),
        ("grok_sentiment", "core.x_sentiment"),
    ]
    
    for name, module_path in sources:
        try:
            module = _safe_import(module_path)
            if module and hasattr(module, "get_api_status"):
                status[name] = module.get_api_status()
            else:
                status[name] = {"available": module is not None}
        except Exception as e:
            status[name] = {"available": False, "error": str(e)}
    
    return status


def clear_all_caches() -> Dict[str, int]:
    """Clear caches for all data sources."""
    results = {}
    
    sources = [
        ("dexscreener", "core.dexscreener"),
        ("birdeye", "core.birdeye"),
        ("geckoterminal", "core.geckoterminal"),
        ("dextools", "core.dextools"),
        ("gmgn", "core.gmgn_metrics"),
        ("lute", "core.lute_momentum"),
    ]
    
    for name, module_path in sources:
        try:
            module = _safe_import(module_path)
            if module and hasattr(module, "clear_cache"):
                results[name] = module.clear_cache()
            else:
                results[name] = 0
        except Exception:
            results[name] = 0
    
    return results


if __name__ == "__main__":
    import json
    logging.basicConfig(level=logging.INFO)
    
    print("=== Trading Signal Aggregator ===")
    print("\nSource Status:")
    print(json.dumps(get_all_sources_status(), indent=2, default=str))
    
    print("\n=== Testing Momentum Opportunities ===")
    result = get_momentum_opportunities(limit=5, include_sentiment=False)
    if result.success and result.data:
        print(f"Found {len(result.data)} opportunities:")
        for sig in result.data[:3]:
            print(f"  {sig.symbol}: signal={sig.signal}, score={sig.signal_score:.1f}")
            if sig.signal_reasons:
                for reason in sig.signal_reasons[:2]:
                    print(f"    - {reason}")
