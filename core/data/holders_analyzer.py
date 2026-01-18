"""
Holder Distribution Analyzer
============================

Analyzes token holder distribution to detect:
- Whale concentration
- Potential rug pull patterns
- Team allocation
- Healthy diversification

Generates trading signals based on holder patterns:
- WHALE_CONCENTRATION (confidence: 0.7 if top10 > 50%)
- HOLDER_DIVERSIFICATION (confidence: 0.8 if concentrated < 40%)
- POTENTIAL_RUG (confidence: 0.9 if top10 > 80% AND decreasing)

Usage:
    from core.data.holders_analyzer import get_holders_analyzer

    analyzer = get_holders_analyzer()
    distribution = analyzer.calculate_distribution(holders, total_supply)
    signals = analyzer.generate_signals(holders, total_supply)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Set

from core.data.solscan_api import HolderInfo

logger = logging.getLogger(__name__)

# Whale threshold: addresses holding more than this % are whales
WHALE_THRESHOLD_PCT = 5.0

# Concentration thresholds
HIGH_CONCENTRATION_THRESHOLD = 50.0  # Top 10 > 50% is concerning
EXTREME_CONCENTRATION_THRESHOLD = 80.0  # Top 10 > 80% is very risky
LOW_CONCENTRATION_THRESHOLD = 40.0  # Top 10 < 40% is healthy

# Known team/treasury patterns (simplified - could be expanded)
TEAM_WALLET_PATTERNS = [
    "team", "treasury", "foundation", "dev", "marketing",
    "ecosystem", "reserve", "liquidity", "airdrop"
]


class SignalType(str, Enum):
    """Holder distribution signal types."""
    WHALE_CONCENTRATION = "WHALE_CONCENTRATION"
    HOLDER_DIVERSIFICATION = "HOLDER_DIVERSIFICATION"
    POTENTIAL_RUG = "POTENTIAL_RUG"
    TEAM_ALLOCATION = "TEAM_ALLOCATION"
    HEALTHY_DISTRIBUTION = "HEALTHY_DISTRIBUTION"


@dataclass
class ConcentrationSignal:
    """Signal generated from holder analysis."""
    signal_type: str
    confidence: float  # 0.0 to 1.0
    description: str
    timestamp: str = ""
    data: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class HolderDistribution:
    """Holder distribution analysis result."""
    token_address: str = ""
    total_holders: int = 0
    top_10_concentration: float = 0.0  # Percentage owned by top 10
    top_50_concentration: float = 0.0  # Percentage owned by top 50
    whale_count: int = 0  # Addresses holding > WHALE_THRESHOLD_PCT
    whale_addresses: List[str] = field(default_factory=list)
    avg_holder_balance: float = 0.0
    median_holder_balance: float = 0.0
    largest_holder_pct: float = 0.0
    largest_holder_address: str = ""
    team_allocation_pct: float = 0.0  # Estimated team holdings
    is_concentrated: bool = False
    risk_level: str = "unknown"  # low, medium, high, critical
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class HoldersAnalyzer:
    """
    Analyzes token holder distribution for trading signals.

    Key metrics:
    - Top 10 holder concentration
    - Whale detection (>5% supply)
    - Team allocation estimation
    - Distribution health scoring
    """

    _instance: Optional["HoldersAnalyzer"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._initialized = True
        logger.info("HoldersAnalyzer initialized")

    def calculate_distribution(
        self,
        holders: List[HolderInfo],
        total_supply: int,
        token_address: str = "",
    ) -> HolderDistribution:
        """
        Calculate holder distribution metrics.

        Args:
            holders: List of HolderInfo from Solscan
            total_supply: Total token supply
            token_address: Token mint address

        Returns:
            HolderDistribution with calculated metrics
        """
        if not holders or total_supply <= 0:
            return HolderDistribution(
                token_address=token_address,
                risk_level="unknown",
            )

        # Sort by amount descending
        sorted_holders = sorted(holders, key=lambda h: h.amount, reverse=True)

        # Calculate concentrations
        top_10 = sorted_holders[:10]
        top_50 = sorted_holders[:50]

        top_10_total = sum(h.amount for h in top_10)
        top_50_total = sum(h.amount for h in top_50)

        top_10_concentration = (top_10_total / total_supply) * 100 if total_supply > 0 else 0
        top_50_concentration = (top_50_total / total_supply) * 100 if total_supply > 0 else 0

        # Detect whales (>5% supply)
        whale_threshold = total_supply * (WHALE_THRESHOLD_PCT / 100)
        whales = [h for h in sorted_holders if h.amount >= whale_threshold]
        whale_addresses = [h.owner for h in whales]

        # Calculate averages
        total_balance = sum(h.amount for h in sorted_holders)
        avg_balance = total_balance / len(sorted_holders) if sorted_holders else 0

        # Median calculation
        mid = len(sorted_holders) // 2
        if sorted_holders:
            if len(sorted_holders) % 2 == 0:
                median_balance = (sorted_holders[mid - 1].amount + sorted_holders[mid].amount) / 2
            else:
                median_balance = sorted_holders[mid].amount
        else:
            median_balance = 0

        # Largest holder
        largest = sorted_holders[0] if sorted_holders else None
        largest_holder_pct = (largest.amount / total_supply) * 100 if largest and total_supply > 0 else 0
        largest_holder_address = largest.owner if largest else ""

        # Estimate team allocation (simplified heuristic)
        team_allocation = self._estimate_team_allocation(sorted_holders, total_supply)

        # Determine concentration level
        is_concentrated = top_10_concentration > HIGH_CONCENTRATION_THRESHOLD

        # Determine risk level
        if top_10_concentration > EXTREME_CONCENTRATION_THRESHOLD:
            risk_level = "critical"
        elif top_10_concentration > HIGH_CONCENTRATION_THRESHOLD:
            risk_level = "high"
        elif top_10_concentration > LOW_CONCENTRATION_THRESHOLD:
            risk_level = "medium"
        else:
            risk_level = "low"

        return HolderDistribution(
            token_address=token_address,
            total_holders=len(sorted_holders),
            top_10_concentration=round(top_10_concentration, 2),
            top_50_concentration=round(top_50_concentration, 2),
            whale_count=len(whales),
            whale_addresses=whale_addresses[:10],  # Limit to top 10 whales
            avg_holder_balance=avg_balance,
            median_holder_balance=median_balance,
            largest_holder_pct=round(largest_holder_pct, 2),
            largest_holder_address=largest_holder_address,
            team_allocation_pct=round(team_allocation, 2),
            is_concentrated=is_concentrated,
            risk_level=risk_level,
        )

    def _estimate_team_allocation(
        self,
        holders: List[HolderInfo],
        total_supply: int,
    ) -> float:
        """
        Estimate team/insider allocation.

        Uses heuristics:
        - Very large holders (>10%) in first few wallets
        - Wallets with team-like patterns (limited in this version)

        Args:
            holders: Sorted holder list
            total_supply: Total supply

        Returns:
            Estimated team allocation percentage
        """
        if not holders or total_supply <= 0:
            return 0.0

        # Consider top 5 holders that have >10% as potential team
        team_total = 0
        threshold = total_supply * 0.10

        for h in holders[:5]:
            if h.amount >= threshold:
                team_total += h.amount

        return (team_total / total_supply) * 100 if total_supply > 0 else 0

    def generate_signals(
        self,
        holders: List[HolderInfo],
        total_supply: int,
        previous_concentration: Optional[float] = None,
        token_address: str = "",
    ) -> List[ConcentrationSignal]:
        """
        Generate trading signals from holder distribution.

        Args:
            holders: List of HolderInfo
            total_supply: Total token supply
            previous_concentration: Previous top 10 concentration (for trend detection)
            token_address: Token mint address

        Returns:
            List of ConcentrationSignal
        """
        signals: List[ConcentrationSignal] = []

        if not holders or total_supply <= 0:
            return signals

        # Calculate current distribution
        distribution = self.calculate_distribution(holders, total_supply, token_address)

        # Signal 1: WHALE_CONCENTRATION
        if distribution.top_10_concentration > HIGH_CONCENTRATION_THRESHOLD:
            confidence = 0.7
            if distribution.top_10_concentration > EXTREME_CONCENTRATION_THRESHOLD:
                confidence = 0.9

            signals.append(ConcentrationSignal(
                signal_type=SignalType.WHALE_CONCENTRATION.value,
                confidence=confidence,
                description=f"Top 10 holders control {distribution.top_10_concentration:.1f}% of supply",
                data={
                    "top_10_concentration": distribution.top_10_concentration,
                    "whale_count": distribution.whale_count,
                    "largest_holder_pct": distribution.largest_holder_pct,
                },
            ))

        # Signal 2: HOLDER_DIVERSIFICATION (positive signal)
        if distribution.top_10_concentration < LOW_CONCENTRATION_THRESHOLD:
            signals.append(ConcentrationSignal(
                signal_type=SignalType.HOLDER_DIVERSIFICATION.value,
                confidence=0.8,
                description=f"Well-distributed: top 10 only control {distribution.top_10_concentration:.1f}%",
                data={
                    "top_10_concentration": distribution.top_10_concentration,
                    "total_holders": distribution.total_holders,
                },
            ))

        # Signal 3: POTENTIAL_RUG
        if distribution.top_10_concentration > EXTREME_CONCENTRATION_THRESHOLD:
            # Check if concentration is decreasing (selling pattern)
            if previous_concentration and previous_concentration > distribution.top_10_concentration:
                signals.append(ConcentrationSignal(
                    signal_type=SignalType.POTENTIAL_RUG.value,
                    confidence=0.9,
                    description=f"Extreme concentration ({distribution.top_10_concentration:.1f}%) and declining (was {previous_concentration:.1f}%)",
                    data={
                        "current_concentration": distribution.top_10_concentration,
                        "previous_concentration": previous_concentration,
                        "change": previous_concentration - distribution.top_10_concentration,
                    },
                ))
            else:
                # Still flag extreme concentration
                signals.append(ConcentrationSignal(
                    signal_type=SignalType.POTENTIAL_RUG.value,
                    confidence=0.7,
                    description=f"Extreme concentration: top 10 control {distribution.top_10_concentration:.1f}%",
                    data={
                        "top_10_concentration": distribution.top_10_concentration,
                    },
                ))

        # Signal 4: TEAM_ALLOCATION
        if distribution.team_allocation_pct > 30:
            signals.append(ConcentrationSignal(
                signal_type=SignalType.TEAM_ALLOCATION.value,
                confidence=0.6,
                description=f"High estimated team allocation: {distribution.team_allocation_pct:.1f}%",
                data={
                    "team_allocation_pct": distribution.team_allocation_pct,
                },
            ))

        # Signal 5: HEALTHY_DISTRIBUTION
        if (distribution.risk_level == "low" and
            distribution.total_holders > 1000 and
            not distribution.is_concentrated):
            signals.append(ConcentrationSignal(
                signal_type=SignalType.HEALTHY_DISTRIBUTION.value,
                confidence=0.85,
                description=f"Healthy distribution: {distribution.total_holders} holders, low concentration",
                data={
                    "total_holders": distribution.total_holders,
                    "top_10_concentration": distribution.top_10_concentration,
                    "risk_level": distribution.risk_level,
                },
            ))

        return signals

    def get_risk_assessment(
        self,
        holders: List[HolderInfo],
        total_supply: int,
    ) -> Dict[str, Any]:
        """
        Get comprehensive risk assessment.

        Args:
            holders: List of HolderInfo
            total_supply: Total token supply

        Returns:
            Risk assessment dict
        """
        distribution = self.calculate_distribution(holders, total_supply)
        signals = self.generate_signals(holders, total_supply)

        # Calculate overall risk score (0-100, higher = riskier)
        risk_score = 0

        # Concentration risk
        if distribution.top_10_concentration > EXTREME_CONCENTRATION_THRESHOLD:
            risk_score += 40
        elif distribution.top_10_concentration > HIGH_CONCENTRATION_THRESHOLD:
            risk_score += 25
        elif distribution.top_10_concentration > LOW_CONCENTRATION_THRESHOLD:
            risk_score += 10

        # Whale risk
        risk_score += min(20, distribution.whale_count * 5)

        # Single holder dominance
        if distribution.largest_holder_pct > 50:
            risk_score += 30
        elif distribution.largest_holder_pct > 30:
            risk_score += 15
        elif distribution.largest_holder_pct > 10:
            risk_score += 5

        # Low holder count risk
        if distribution.total_holders < 100:
            risk_score += 15
        elif distribution.total_holders < 500:
            risk_score += 5

        risk_score = min(100, risk_score)

        return {
            "distribution": distribution.to_dict(),
            "signals": [s.to_dict() for s in signals],
            "risk_score": risk_score,
            "risk_level": distribution.risk_level,
            "is_risky": risk_score > 50,
            "red_flags": self._extract_red_flags(distribution, signals),
        }

    def _extract_red_flags(
        self,
        distribution: HolderDistribution,
        signals: List[ConcentrationSignal],
    ) -> List[str]:
        """Extract red flags from analysis."""
        flags = []

        if distribution.top_10_concentration > EXTREME_CONCENTRATION_THRESHOLD:
            flags.append("extreme_concentration")

        if distribution.largest_holder_pct > 50:
            flags.append("single_holder_dominance")

        if distribution.whale_count > 5:
            flags.append("multiple_whales")

        if distribution.total_holders < 100:
            flags.append("low_holder_count")

        for signal in signals:
            if signal.signal_type == SignalType.POTENTIAL_RUG.value:
                flags.append("potential_rug_pattern")

        return flags


# Singleton accessor
def get_holders_analyzer() -> HoldersAnalyzer:
    """Get the HoldersAnalyzer singleton instance."""
    return HoldersAnalyzer()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    # Test with mock data
    print("=== Holder Analyzer Test ===")

    analyzer = get_holders_analyzer()

    # Create mock holders with high concentration
    mock_holders = [
        HolderInfo(owner="whale1", amount=50000000, rank=1, percentage=50.0),
        HolderInfo(owner="whale2", amount=20000000, rank=2, percentage=20.0),
        HolderInfo(owner="holder3", amount=5000000, rank=3, percentage=5.0),
    ]

    distribution = analyzer.calculate_distribution(mock_holders, 100000000)
    print(f"\nDistribution:")
    print(f"  Top 10 concentration: {distribution.top_10_concentration}%")
    print(f"  Whale count: {distribution.whale_count}")
    print(f"  Risk level: {distribution.risk_level}")

    signals = analyzer.generate_signals(mock_holders, 100000000)
    print(f"\nSignals ({len(signals)}):")
    for sig in signals:
        print(f"  - {sig.signal_type}: {sig.description} (confidence: {sig.confidence})")
