"""
Token Analyzer - Comprehensive on-demand token analysis for public bot

Analyzes any Solana token and provides:
- Price and market data
- Liquidity analysis
- Technical indicators
- Sentiment aggregation
- Whale activity
- Risk assessment
- Buy/Sell recommendations
"""

import logging
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class TokenRiskRating(Enum):
    """Risk rating for a token."""
    VERY_LOW = "🟢 Very Low"
    LOW = "🟢 Low"
    MEDIUM = "🟡 Medium"
    HIGH = "🔴 High"
    VERY_HIGH = "🔴 Very High"
    EXTREME = "🔴💀 Extreme"


class TokenTrend(Enum):
    """Token trend direction."""
    STRONG_UP = "📈 Strong Up"
    UP = "📈 Up"
    NEUTRAL = "➡️ Neutral"
    DOWN = "📉 Down"
    STRONG_DOWN = "📉 Strong Down"


@dataclass
class PriceData:
    """Token price information."""
    symbol: str
    current_price: float
    price_24h_ago: float
    price_7d_ago: float
    price_30d_ago: float
    price_change_24h_pct: float
    price_change_7d_pct: float
    price_change_30d_pct: float
    high_24h: float
    low_24h: float
    ath: float  # All-time high
    atl: float  # All-time low
    market_cap_usd: float
    trading_volume_24h: float
    volume_to_mcap_ratio: float


@dataclass
class LiquidityData:
    """Liquidity and DEX information."""
    total_liquidity_usd: float
    pool_count: int
    largest_pool_usd: float
    largest_pool_symbol: str  # Usually USDC or WSOL
    liquidity_score: float  # 0-100
    is_liquid: bool  # > $100k liquidity
    recommended_max_trade_usd: float  # Based on liquidity


@dataclass
class WalletDistribution:
    """Token holder distribution."""
    total_holders: int
    top_10_holders_pct: float
    top_100_holders_pct: float
    concentration_score: float  # 0-100, higher = more concentrated
    is_concentrated: bool  # > 70% in top holders?


@dataclass
class SentimentData:
    """Aggregated sentiment scores."""
    grok_score: float  # -100 to +100
    twitter_score: float
    news_score: float
    onchain_score: float
    whale_score: float
    composite_score: float
    sentiment_trend: TokenTrend
    momentum_24h: str


@dataclass
class TechnicalIndicators:
    """Technical analysis indicators."""
    sma_7: float  # 7-day simple moving average
    sma_25: float
    ema_12: float  # Exponential moving average
    rsi_14: float  # Relative Strength Index
    macd: float  # MACD value
    macd_signal: float
    bollinger_upper: float
    bollinger_middle: float
    bollinger_lower: float
    atr_14: float  # Average True Range
    signal_trend: TokenTrend


@dataclass
class RiskAssessment:
    """Token risk evaluation."""
    risk_rating: TokenRiskRating
    risk_score: float  # 0-100
    concentration_risk: float  # Token holder concentration
    liquidity_risk: float  # Can we exit?
    volatility_risk: float  # Price swings
    regulatory_risk: float  # Is it a scam?
    smart_contract_risk: float  # Code audit status
    team_risk: float  # Team doxing
    market_risk: float  # Market conditions
    key_risks: List[str]  # Specific risks
    safety_recommendations: List[str]


@dataclass
class TokenRecommendation:
    """Buy/Sell recommendation for token."""
    symbol: str
    action: str  # "BUY", "HOLD", "SELL", "WAIT"
    confidence: float  # 0-100
    short_thesis: str
    entry_price: float
    target_price: float
    stop_loss_price: float
    reasoning: List[str]
    catalysts: List[str]  # What could drive price?
    time_horizon: str  # "hours", "days", "weeks"
    signals_by_type: Dict[str, str]  # "sentiment": "bullish", etc


@dataclass
class TokenAnalysis:
    """Complete token analysis result."""
    symbol: str
    analyzed_at: datetime = field(default_factory=datetime.utcnow)
    price_data: Optional[PriceData] = None
    liquidity_data: Optional[LiquidityData] = None
    wallet_distribution: Optional[WalletDistribution] = None
    sentiment_data: Optional[SentimentData] = None
    technical_indicators: Optional[TechnicalIndicators] = None
    risk_assessment: Optional[RiskAssessment] = None
    recommendation: Optional[TokenRecommendation] = None


class TokenAnalyzer:
    """
    Comprehensive token analysis engine.

    Analyzes any Solana token and provides:
    - Market data and price action
    - Liquidity assessment
    - Risk evaluation
    - Sentiment analysis
    - Technical indicators
    - Trading recommendations
    """

    def __init__(self):
        """Initialize token analyzer."""
        self.cache: Dict[str, TokenAnalysis] = {}
        self.cache_ttl_minutes = 30

    # ==================== PRICE ANALYSIS ====================

    async def analyze_price(self, symbol: str, market_data: Dict[str, Any]) -> Optional[PriceData]:
        """
        Analyze token price data.

        Args:
            symbol: Token symbol
            market_data: Market data from DexScreener or similar

        Returns:
            PriceData or None
        """
        try:
            current_price = market_data.get('price', 0)
            if not current_price:
                return None

            price_24h_ago = market_data.get('price_24h_ago', current_price)
            price_7d_ago = market_data.get('price_7d_ago', current_price)
            price_30d_ago = market_data.get('price_30d_ago', current_price)

            price_change_24h_pct = ((current_price - price_24h_ago) / max(price_24h_ago, 0.0001)) * 100
            price_change_7d_pct = ((current_price - price_7d_ago) / max(price_7d_ago, 0.0001)) * 100
            price_change_30d_pct = ((current_price - price_30d_ago) / max(price_30d_ago, 0.0001)) * 100

            high_24h = market_data.get('high_24h', current_price)
            low_24h = market_data.get('low_24h', current_price)
            ath = market_data.get('ath', current_price)
            atl = market_data.get('atl', current_price)

            market_cap_usd = market_data.get('market_cap', 0)
            volume_24h = market_data.get('volume_24h', 0)
            volume_to_mcap = (volume_24h / market_cap_usd) if market_cap_usd > 0 else 0

            return PriceData(
                symbol=symbol,
                current_price=current_price,
                price_24h_ago=price_24h_ago,
                price_7d_ago=price_7d_ago,
                price_30d_ago=price_30d_ago,
                price_change_24h_pct=price_change_24h_pct,
                price_change_7d_pct=price_change_7d_pct,
                price_change_30d_pct=price_change_30d_pct,
                high_24h=high_24h,
                low_24h=low_24h,
                ath=ath,
                atl=atl,
                market_cap_usd=market_cap_usd,
                trading_volume_24h=volume_24h,
                volume_to_mcap_ratio=volume_to_mcap,
            )

        except Exception as e:
            logger.error(f"Price analysis failed: {e}")
            return None

    # ==================== LIQUIDITY ANALYSIS ====================

    async def analyze_liquidity(self, symbol: str, liquidity_info: Dict[str, Any]) -> Optional[LiquidityData]:
        """
        Analyze token liquidity.

        Args:
            symbol: Token symbol
            liquidity_info: Pool and liquidity data

        Returns:
            LiquidityData or None
        """
        try:
            total_liquidity = liquidity_info.get('total_liquidity_usd', 0)
            pool_count = liquidity_info.get('pool_count', 0)
            largest_pool = liquidity_info.get('largest_pool_usd', 0)

            if total_liquidity < 10_000:  # Less than $10K
                liquidity_score = 0
                is_liquid = False
            elif total_liquidity < 100_000:  # Less than $100K
                liquidity_score = 25
                is_liquid = False
            elif total_liquidity < 1_000_000:  # Less than $1M
                liquidity_score = 50
                is_liquid = True
            elif total_liquidity < 10_000_000:  # Less than $10M
                liquidity_score = 75
                is_liquid = True
            else:  # Greater than $10M
                liquidity_score = 100
                is_liquid = True

            # Recommended trade size: 1-5% of largest pool
            recommended_max_trade = largest_pool * 0.05 if largest_pool > 0 else 0

            return LiquidityData(
                total_liquidity_usd=total_liquidity,
                pool_count=pool_count,
                largest_pool_usd=largest_pool,
                largest_pool_symbol=liquidity_info.get('largest_pool_symbol', 'UNKNOWN'),
                liquidity_score=liquidity_score,
                is_liquid=is_liquid,
                recommended_max_trade_usd=recommended_max_trade,
            )

        except Exception as e:
            logger.error(f"Liquidity analysis failed: {e}")
            return None

    # ==================== RISK ASSESSMENT ====================

    async def assess_risk(self, symbol: str, token_data: Dict[str, Any]) -> Optional[RiskAssessment]:
        """
        Comprehensive risk assessment for token.

        Args:
            symbol: Token symbol
            token_data: All token metadata

        Returns:
            RiskAssessment or None
        """
        try:
            concentration_risk = token_data.get('concentration_risk', 50)
            liquidity_risk = 100 - token_data.get('liquidity_score', 50)
            volatility_risk = min(100, token_data.get('volatility_24h_pct', 0) / 10)
            regulatory_risk = token_data.get('regulatory_risk', 30)
            smart_contract_risk = token_data.get('audit_status', 50)
            team_risk = token_data.get('team_doxxed', 0) * 50  # 0-50 based on doxxing
            market_risk = token_data.get('market_risk', 40)

            # Calculate weighted risk score
            risk_score = (
                concentration_risk * 0.2 +
                liquidity_risk * 0.2 +
                volatility_risk * 0.15 +
                regulatory_risk * 0.15 +
                smart_contract_risk * 0.15 +
                team_risk * 0.1 +
                market_risk * 0.05
            )

            # Determine risk rating
            if risk_score < 25:
                risk_rating = TokenRiskRating.VERY_LOW
            elif risk_score < 40:
                risk_rating = TokenRiskRating.LOW
            elif risk_score < 55:
                risk_rating = TokenRiskRating.MEDIUM
            elif risk_score < 70:
                risk_rating = TokenRiskRating.HIGH
            elif risk_score < 85:
                risk_rating = TokenRiskRating.VERY_HIGH
            else:
                risk_rating = TokenRiskRating.EXTREME

            # Specific risks
            key_risks = []
            if concentration_risk > 70:
                key_risks.append("⚠️ High holder concentration - whales can dump")
            if liquidity_risk > 50:
                key_risks.append("⚠️ Limited liquidity - may be hard to exit")
            if volatility_risk > 70:
                key_risks.append("⚠️ Extreme volatility - high risk of sharp moves")
            if regulatory_risk > 70:
                key_risks.append("⚠️ Regulatory concerns - potential delisting")
            if smart_contract_risk > 70:
                key_risks.append("⚠️ Unaudited smart contract - code risk")
            if team_risk > 30:
                key_risks.append("⚠️ Anonymous team - potential rug pull risk")

            # Safety recommendations
            safety_recommendations = []
            if risk_rating.value.startswith("🔴"):
                safety_recommendations.append("❌ This token has HIGH RISK. Avoid unless experienced trader.")
            if liquidity_risk > 60:
                safety_recommendations.append("💰 Only trade small position sizes due to liquidity concerns")
            if concentration_risk > 60:
                safety_recommendations.append("👁️ Watch for whale dumps - set tight stop losses")
            if volatility_risk > 60:
                safety_recommendations.append("⚡ Set tight stop losses - volatile price movements expected")
            safety_recommendations.append("💡 Never invest more than you can afford to lose")

            return RiskAssessment(
                risk_rating=risk_rating,
                risk_score=risk_score,
                concentration_risk=concentration_risk,
                liquidity_risk=liquidity_risk,
                volatility_risk=volatility_risk,
                regulatory_risk=regulatory_risk,
                smart_contract_risk=smart_contract_risk,
                team_risk=team_risk,
                market_risk=market_risk,
                key_risks=key_risks,
                safety_recommendations=safety_recommendations,
            )

        except Exception as e:
            logger.error(f"Risk assessment failed: {e}")
            return None

    # ==================== RECOMMENDATION ENGINE ====================

    async def generate_recommendation(self, symbol: str, analysis_data: Dict[str, Any]) -> Optional[TokenRecommendation]:
        """
        Generate buy/sell recommendation based on all analysis.

        Args:
            symbol: Token symbol
            analysis_data: All analysis components

        Returns:
            TokenRecommendation or None
        """
        try:
            current_price = analysis_data.get('current_price', 0)
            sentiment_score = analysis_data.get('sentiment_score', 0)
            risk_score = analysis_data.get('risk_score', 50)
            liquidity_score = analysis_data.get('liquidity_score', 50)
            volume_mcap_ratio = analysis_data.get('volume_mcap_ratio', 0)
            whale_score = analysis_data.get('whale_score', 0)

            if not current_price:
                return None

            # Decision logic
            signal_scores = {
                'sentiment': sentiment_score,
                'liquidity': liquidity_score,
                'whale': whale_score,
                'volume': min(100, volume_mcap_ratio * 100),
            }

            bullish_signals = sum(1 for s in signal_scores.values() if s > 55)
            bearish_signals = sum(1 for s in signal_scores.values() if s < 45)

            # Action determination
            if risk_score > 80:
                action = "WAIT"
                confidence = 30
                short_thesis = "Token has excessive risk - wait for better entry or avoid entirely"
            elif sentiment_score > 70 and liquidity_score > 60 and bullish_signals >= 2:
                action = "BUY"
                confidence = min(100, 50 + (sentiment_score - 55) + (liquidity_score - 50))
                short_thesis = "Multiple bullish signals with good liquidity"
                target_price = current_price * 1.5  # 50% upside
                stop_loss_price = current_price * 0.85  # 15% stop
            elif sentiment_score < 30 or bearish_signals >= 2:
                action = "SELL"
                confidence = min(100, abs(sentiment_score - 30))
                short_thesis = "Bearish signals indicate downside risk"
                target_price = current_price * 0.70
                stop_loss_price = current_price * 1.15
            else:
                action = "HOLD"
                confidence = 60
                short_thesis = "Mixed signals - insufficient conviction to trade"
                target_price = current_price * 1.1
                stop_loss_price = current_price * 0.95

            # Build reasoning
            reasoning = []
            if sentiment_score > 60:
                reasoning.append(f"✅ Strong positive sentiment ({sentiment_score:.0f})")
            elif sentiment_score < 40:
                reasoning.append(f"❌ Negative sentiment ({sentiment_score:.0f})")

            if liquidity_score > 70:
                reasoning.append(f"✅ Good liquidity ({liquidity_score:.0f})")
            elif liquidity_score < 30:
                reasoning.append(f"⚠️ Poor liquidity ({liquidity_score:.0f})")

            if volume_mcap_ratio > 1:
                reasoning.append(f"✅ Healthy volume/market cap ratio ({volume_mcap_ratio:.2f})")

            if whale_score > 70:
                reasoning.append(f"✅ Whale activity detected ({whale_score:.0f})")

            # Catalysts
            catalysts = analysis_data.get('catalysts', [])

            return TokenRecommendation(
                symbol=symbol,
                action=action,
                confidence=confidence,
                short_thesis=short_thesis,
                entry_price=current_price,
                target_price=target_price,
                stop_loss_price=stop_loss_price,
                reasoning=reasoning,
                catalysts=catalysts,
                time_horizon="24 hours to 7 days",
                signals_by_type=signal_scores,
            )

        except Exception as e:
            logger.error(f"Recommendation generation failed: {e}")
            return None

    # ==================== FULL ANALYSIS ====================

    async def analyze_token(self, symbol: str, market_data: Dict[str, Any]) -> Optional[TokenAnalysis]:
        """
        Perform complete token analysis.

        Args:
            symbol: Token symbol
            market_data: Market data from all sources

        Returns:
            Complete TokenAnalysis
        """
        try:
            logger.info(f"Starting analysis of {symbol}")

            analysis = TokenAnalysis(symbol=symbol)

            # Price analysis
            analysis.price_data = await self.analyze_price(symbol, market_data)

            # Liquidity analysis
            analysis.liquidity_data = await self.analyze_liquidity(
                symbol,
                market_data.get('liquidity_data', {})
            )

            # Risk assessment
            if analysis.price_data and analysis.liquidity_data:
                risk_data = {
                    'concentration_risk': market_data.get('concentration_risk', 50),
                    'liquidity_score': analysis.liquidity_data.liquidity_score,
                    'volatility_24h_pct': analysis.price_data.price_change_24h_pct,
                    'regulatory_risk': market_data.get('regulatory_risk', 30),
                    'audit_status': market_data.get('audit_status', 50),
                    'team_doxxed': market_data.get('team_doxxed', False),
                    'market_risk': market_data.get('market_risk', 40),
                }
                analysis.risk_assessment = await self.assess_risk(symbol, risk_data)

                # Generate recommendation
                recommendation_data = {
                    'current_price': analysis.price_data.current_price,
                    'sentiment_score': market_data.get('sentiment_score', 50),
                    'risk_score': analysis.risk_assessment.risk_score if analysis.risk_assessment else 50,
                    'liquidity_score': analysis.liquidity_data.liquidity_score,
                    'volume_mcap_ratio': analysis.price_data.volume_to_mcap_ratio,
                    'whale_score': market_data.get('whale_score', 50),
                    'catalysts': market_data.get('catalysts', []),
                }
                analysis.recommendation = await self.generate_recommendation(symbol, recommendation_data)

            logger.info(f"Analysis complete for {symbol}")
            return analysis

        except Exception as e:
            logger.error(f"Token analysis failed: {e}")
            return None

    # ==================== FORMATTING ====================

    def format_analysis_for_telegram(self, analysis: TokenAnalysis) -> str:
        """Format token analysis as Telegram message."""
        try:
            lines = [f"<b>🔍 {analysis.symbol} - Token Analysis</b>\n"]

            if analysis.price_data:
                pd = analysis.price_data
                lines.append(f"<b>📊 Price Data</b>")
                lines.append(f"Current: ${pd.current_price:.6f}")
                lines.append(f"24h: {pd.price_change_24h_pct:+.2f}%")
                lines.append(f"Market Cap: ${pd.market_cap_usd:,.0f}")
                lines.append(f"Volume: ${pd.trading_volume_24h:,.0f}\n")

            if analysis.liquidity_data:
                ld = analysis.liquidity_data
                lines.append(f"<b>💧 Liquidity</b>")
                lines.append(f"Total: ${ld.total_liquidity_usd:,.0f}")
                lines.append(f"Score: {ld.liquidity_score:.0f}/100")
                lines.append(f"Max Trade: ${ld.recommended_max_trade_usd:,.0f}\n")

            if analysis.risk_assessment:
                ra = analysis.risk_assessment
                lines.append(f"<b>⚠️ Risk Assessment</b>")
                lines.append(f"Rating: {ra.risk_rating.value}")
                lines.append(f"Score: {ra.risk_score:.1f}/100")
                if ra.key_risks:
                    lines.append("Risks:")
                    for risk in ra.key_risks[:3]:
                        lines.append(f"  {risk}")
                lines.append("")

            if analysis.recommendation:
                rec = analysis.recommendation
                lines.append(f"<b>💡 Recommendation</b>")
                lines.append(f"Action: <b>{rec.action}</b>")
                lines.append(f"Confidence: {rec.confidence:.0f}%")
                lines.append(f"Entry: ${rec.entry_price:.6f}")
                lines.append(f"Target: ${rec.target_price:.6f}")
                lines.append(f"Stop: ${rec.stop_loss_price:.6f}")

            lines.append(f"\n<i>Analyzed: {analysis.analyzed_at.strftime('%Y-%m-%d %H:%M UTC')}</i>")

            return "\n".join(lines)

        except Exception as e:
            logger.error(f"Failed to format analysis: {e}")
            return "Analysis formatting failed"
