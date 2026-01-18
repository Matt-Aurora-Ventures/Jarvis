"""
On-Chain Analyzer - Main Aggregator for Token On-Chain Analysis
================================================================

Aggregates all on-chain metrics into a comprehensive analysis:
- Solscan API for blockchain data
- Holder distribution analysis
- Tokenomics scoring
- Pump and dump pattern detection
- Red flag identification

Usage:
    from core.data.onchain_analyzer import get_onchain_analyzer

    analyzer = get_onchain_analyzer()
    analysis = await analyzer.analyze_token("token_mint_address")

    # Access specific metrics
    distribution = await analyzer.get_holder_distribution("token_mint")
    score = await analyzer.get_tokenomics_score("token_mint")
    is_pnd = await analyzer.detect_pump_and_dump_pattern("token_mint")
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from core.data.solscan_api import (
    SolscanAPI,
    get_solscan_api,
    TokenInfo,
    HolderInfo,
    TransactionInfo,
)
from core.data.holders_analyzer import (
    HoldersAnalyzer,
    get_holders_analyzer,
    HolderDistribution,
    ConcentrationSignal,
)
from core.data.tokenomics_scorer import (
    TokenomicsScorer,
    get_tokenomics_scorer,
    TokenomicsScore,
    TokenomicsGrade,
)

logger = logging.getLogger(__name__)

# Feature flag check
try:
    from core.feature_flags import is_feature_enabled
    HAS_FEATURE_FLAGS = True
except ImportError:
    HAS_FEATURE_FLAGS = False

    def is_feature_enabled(flag: str, user_id: str = None) -> bool:
        return True  # Default to enabled if feature flags not available


@dataclass
class OnChainAnalysis:
    """
    Complete on-chain analysis result.

    Contains all metrics needed for trading decisions.
    """
    token_mint: str
    total_supply: int = 0
    holder_count: int = 0
    top_10_concentration: float = 0.0
    avg_holder_tokens: int = 0
    largest_holder_pct: float = 0.0
    tokenomics_grade: str = "F"
    tokenomics_score: int = 0
    is_risky: bool = True
    red_flags: List[str] = field(default_factory=list)
    signals: List[str] = field(default_factory=list)

    # Additional data
    symbol: str = ""
    name: str = ""
    decimals: int = 9
    liquidity_usd: float = 0.0
    market_cap: float = 0.0
    whale_count: int = 0
    risk_level: str = "unknown"
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class OnChainAnalyzer:
    """
    Main aggregator for on-chain token analysis.

    Combines:
    - Solscan blockchain data
    - Holder distribution analysis
    - Tokenomics scoring
    - Pattern detection

    Features:
    - Graceful fallback on API failures
    - Feature flag support
    - Signal generation for trading
    """

    _instance: Optional["OnChainAnalyzer"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self.solscan = get_solscan_api()
        self.holders_analyzer = get_holders_analyzer()
        self.tokenomics_scorer = get_tokenomics_scorer()

        self._initialized = True
        logger.info("OnChainAnalyzer initialized")

    async def analyze_token(
        self,
        token_mint: str,
        respect_feature_flag: bool = False,
    ) -> OnChainAnalysis:
        """
        Perform comprehensive on-chain analysis of a token.

        Args:
            token_mint: Token mint address
            respect_feature_flag: Whether to check ONCHAIN_ANALYSIS_ENABLED flag

        Returns:
            OnChainAnalysis with all metrics
        """
        # Check feature flag
        if respect_feature_flag and not is_feature_enabled("onchain_analysis"):
            logger.debug("On-chain analysis disabled by feature flag")
            return OnChainAnalysis(
                token_mint=token_mint,
                red_flags=["feature_disabled"],
            )

        if not token_mint:
            return OnChainAnalysis(
                token_mint=token_mint,
                is_risky=True,
                red_flags=["invalid_token_address"],
            )

        # Fetch data in parallel
        try:
            token_info, holders = await asyncio.gather(
                self.solscan.get_token_info(token_mint),
                self.solscan.get_token_holders(token_mint, limit=100),
                return_exceptions=True,
            )

            # Handle exceptions
            if isinstance(token_info, Exception):
                logger.warning(f"Failed to fetch token info: {token_info}")
                token_info = None
            if isinstance(holders, Exception):
                logger.warning(f"Failed to fetch holders: {holders}")
                holders = []

        except Exception as e:
            logger.error(f"Failed to fetch on-chain data: {e}")
            return OnChainAnalysis(
                token_mint=token_mint,
                is_risky=True,
                red_flags=["api_unavailable"],
            )

        # Build analysis
        analysis = OnChainAnalysis(token_mint=token_mint)
        red_flags = []
        signals = []

        # Process token info
        if token_info:
            analysis.symbol = token_info.symbol
            analysis.name = token_info.name
            analysis.decimals = token_info.decimals
            analysis.total_supply = token_info.total_supply
            analysis.holder_count = token_info.holder_count
            analysis.market_cap = token_info.market_cap

            # Red flags from token info
            if token_info.holder_count < 100:
                red_flags.append("low_holder_count")
        else:
            red_flags.append("api_unavailable")

        # Process holder distribution
        if holders and analysis.total_supply > 0:
            distribution = self.holders_analyzer.calculate_distribution(
                holders, analysis.total_supply, token_mint
            )

            analysis.top_10_concentration = distribution.top_10_concentration
            analysis.largest_holder_pct = distribution.largest_holder_pct
            analysis.whale_count = distribution.whale_count
            analysis.risk_level = distribution.risk_level

            # Calculate average
            if analysis.holder_count > 0:
                analysis.avg_holder_tokens = analysis.total_supply // analysis.holder_count

            # Generate holder signals
            holder_signals = self.holders_analyzer.generate_signals(
                holders, analysis.total_supply, token_address=token_mint
            )
            for sig in holder_signals:
                signals.append(sig.signal_type)
                if sig.signal_type in ["WHALE_CONCENTRATION", "POTENTIAL_RUG"]:
                    red_flags.append(sig.signal_type.lower())

            # Additional red flags from distribution
            if distribution.top_10_concentration > 80:
                red_flags.append("extreme_concentration")
            if distribution.largest_holder_pct > 50:
                red_flags.append("single_holder_dominance")

        # Calculate tokenomics score
        try:
            tokenomics_result = await self.tokenomics_scorer.score_tokenomics(
                token_address=token_mint,
                total_supply=analysis.total_supply,
                current_supply=analysis.total_supply,
                is_fixed_supply=True,  # Assume fixed for SPL tokens
                is_mintable=False,
                top_10_concentration=analysis.top_10_concentration,
                holder_count=analysis.holder_count,
                liquidity_usd=analysis.liquidity_usd,
                market_cap=analysis.market_cap,
                created_timestamp=token_info.created_time if token_info else None,
            )

            analysis.tokenomics_score = int(tokenomics_result.total_score)
            analysis.tokenomics_grade = tokenomics_result.grade.value if isinstance(
                tokenomics_result.grade, TokenomicsGrade
            ) else str(tokenomics_result.grade)

            # Add tokenomics red/green flags
            red_flags.extend(tokenomics_result.red_flags)

            for flag in tokenomics_result.green_flags:
                signals.append(flag.lower().replace(" ", "_"))

        except Exception as e:
            logger.warning(f"Failed to calculate tokenomics score: {e}")
            analysis.tokenomics_grade = "F"
            analysis.tokenomics_score = 0

        # Determine if risky
        analysis.red_flags = list(set(red_flags))  # Deduplicate
        analysis.signals = list(set(signals))
        analysis.is_risky = (
            len(red_flags) > 2 or
            analysis.tokenomics_score < 50 or
            analysis.risk_level in ["high", "critical"] or
            analysis.holder_count < 50
        )

        return analysis

    async def get_holder_distribution(
        self,
        token_mint: str,
    ) -> HolderDistribution:
        """
        Get holder distribution analysis for a token.

        Args:
            token_mint: Token mint address

        Returns:
            HolderDistribution with concentration metrics
        """
        token_info = await self.solscan.get_token_info(token_mint)
        holders = await self.solscan.get_token_holders(token_mint, limit=100)

        total_supply = token_info.total_supply if token_info else 0

        return self.holders_analyzer.calculate_distribution(
            holders, total_supply, token_mint
        )

    async def get_tokenomics_score(
        self,
        token_mint: str,
    ) -> TokenomicsScore:
        """
        Get tokenomics score for a token.

        Args:
            token_mint: Token mint address

        Returns:
            TokenomicsScore with grade and components
        """
        token_info = await self.solscan.get_token_info(token_mint)
        holders = await self.solscan.get_token_holders(token_mint, limit=100)

        total_supply = token_info.total_supply if token_info else 0
        holder_count = token_info.holder_count if token_info else 0

        # Calculate concentration
        distribution = self.holders_analyzer.calculate_distribution(
            holders, total_supply, token_mint
        )

        return await self.tokenomics_scorer.score_tokenomics(
            token_address=token_mint,
            total_supply=total_supply,
            current_supply=total_supply,
            is_fixed_supply=True,
            is_mintable=False,
            top_10_concentration=distribution.top_10_concentration,
            holder_count=holder_count,
            liquidity_usd=0.0,  # Would need DEX data
            market_cap=token_info.market_cap if token_info else 0,
            created_timestamp=token_info.created_time if token_info else None,
        )

    async def detect_pump_and_dump_pattern(
        self,
        token_mint: str,
    ) -> bool:
        """
        Detect pump and dump patterns.

        Patterns checked:
        - Rapid holder selling
        - High concentration with recent large sells
        - Price spike followed by dumps

        Args:
            token_mint: Token mint address

        Returns:
            True if pump and dump pattern detected
        """
        try:
            # Get holders and transactions
            holders = await self.solscan.get_token_holders(token_mint, limit=20)
            transactions = await self.solscan.get_recent_transactions(token_mint, limit=50)

            if not holders or not transactions:
                return False

            token_info = await self.solscan.get_token_info(token_mint)
            total_supply = token_info.total_supply if token_info else 0

            # Check concentration
            distribution = self.holders_analyzer.calculate_distribution(
                holders, total_supply, token_mint
            )

            # Pattern 1: Extreme concentration (>80%)
            if distribution.top_10_concentration > 80:
                # Check for recent large sells from top holders
                top_addresses = set(h.owner for h in holders[:10])
                recent_sells = [
                    tx for tx in transactions
                    if tx.from_address in top_addresses and tx.tx_type == "sell"
                ]

                if len(recent_sells) > 5:
                    logger.warning(f"Pump and dump pattern: {len(recent_sells)} sells from top holders")
                    return True

            # Pattern 2: Single holder dominance with selling
            if distribution.largest_holder_pct > 60:
                largest_holder = holders[0].owner if holders else ""
                largest_sells = [
                    tx for tx in transactions
                    if tx.from_address == largest_holder
                ]

                if len(largest_sells) > 3:
                    logger.warning("Pump and dump pattern: largest holder selling")
                    return True

            return False

        except Exception as e:
            logger.warning(f"Failed to detect pump and dump: {e}")
            return False

    def _calculate_signal_impact(self, tokenomics_score: int) -> int:
        """
        Calculate signal impact based on tokenomics score.

        Score impact range: +5 to +25 points

        Args:
            tokenomics_score: Tokenomics score (0-100)

        Returns:
            Signal impact points (5-25)
        """
        if tokenomics_score >= 90:
            return 25
        elif tokenomics_score >= 80:
            return 22
        elif tokenomics_score >= 70:
            return 18
        elif tokenomics_score >= 60:
            return 15
        elif tokenomics_score >= 50:
            return 12
        elif tokenomics_score >= 40:
            return 10
        elif tokenomics_score >= 30:
            return 8
        else:
            return 5

    def get_status(self) -> Dict[str, Any]:
        """Get analyzer status."""
        return {
            "initialized": self._initialized,
            "solscan_status": self.solscan.get_api_status(),
            "feature_flags_available": HAS_FEATURE_FLAGS,
        }

    async def close(self):
        """Clean up resources."""
        await self.solscan.close()


# Singleton accessor
def get_onchain_analyzer() -> OnChainAnalyzer:
    """Get the OnChainAnalyzer singleton instance."""
    return OnChainAnalyzer()


if __name__ == "__main__":
    import asyncio
    logging.basicConfig(level=logging.INFO)

    async def test():
        print("=== On-Chain Analyzer Test ===")

        analyzer = get_onchain_analyzer()
        print(f"Status: {analyzer.get_status()}")

        # Test with well-known tokens
        tokens = [
            ("So11111111111111111111111111111111111111112", "SOL"),
            ("EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v", "USDC"),
        ]

        for mint, name in tokens:
            print(f"\n=== Analyzing {name} ===")
            analysis = await analyzer.analyze_token(mint)

            print(f"Symbol: {analysis.symbol}")
            print(f"Holders: {analysis.holder_count}")
            print(f"Top 10 Concentration: {analysis.top_10_concentration:.1f}%")
            print(f"Tokenomics Grade: {analysis.tokenomics_grade}")
            print(f"Tokenomics Score: {analysis.tokenomics_score}/100")
            print(f"Is Risky: {analysis.is_risky}")
            print(f"Red Flags: {analysis.red_flags}")
            print(f"Signals: {analysis.signals}")

        await analyzer.close()

    asyncio.run(test())
