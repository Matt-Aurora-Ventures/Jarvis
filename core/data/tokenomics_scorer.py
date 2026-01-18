"""
Tokenomics Scorer - Token Economic Model Scoring Engine
=======================================================

Scores token economics on a 0-100 scale with letter grades (A+ to F).

Score Components:
- Supply safety (10 pts): Fixed supply (best) -> Inflationary (worse)
- Distribution (20 pts): Decentralized holders
- Vesting schedule (15 pts): No sudden unlock cliffs
- Burn mechanism (10 pts): Deflationary = better
- Team allocation (10 pts): Reasonable team %
- DAO governance (10 pts): Community control
- Liquidity pool (15 pts): Sufficient for trading
- Time on market (10 pts): Established > new

Grade Scale:
- A+ (90-100): Excellent tokenomics
- A (80-89): Very good
- B (70-79): Good
- C (60-69): Fair
- D (50-59): Poor
- F (<50): Fail / High risk

Usage:
    from core.data.tokenomics_scorer import get_tokenomics_scorer

    scorer = get_tokenomics_scorer()
    result = await scorer.score_tokenomics(token_address=..., ...)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class TokenomicsGrade(str, Enum):
    """Tokenomics grade levels."""
    A_PLUS = "A+"
    A = "A"
    B = "B"
    C = "C"
    D = "D"
    F = "F"


@dataclass
class ScoreComponent:
    """Individual score component."""
    name: str
    score: float
    max_score: float
    reason: str

    @property
    def percentage(self) -> float:
        return (self.score / self.max_score) * 100 if self.max_score > 0 else 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "score": self.score,
            "max_score": self.max_score,
            "percentage": round(self.percentage, 1),
            "reason": self.reason,
        }


@dataclass
class TokenomicsScore:
    """Complete tokenomics scoring result."""
    token_address: str
    total_score: float = 0.0
    grade: TokenomicsGrade = TokenomicsGrade.F
    components: List[ScoreComponent] = field(default_factory=list)
    red_flags: List[str] = field(default_factory=list)
    green_flags: List[str] = field(default_factory=list)
    recommendation: str = ""
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "token_address": self.token_address,
            "total_score": round(self.total_score, 1),
            "grade": self.grade.value if isinstance(self.grade, TokenomicsGrade) else self.grade,
            "components": [c.to_dict() for c in self.components],
            "red_flags": self.red_flags,
            "green_flags": self.green_flags,
            "recommendation": self.recommendation,
            "timestamp": self.timestamp,
        }


class TokenomicsScorer:
    """
    Token economics scoring engine.

    Evaluates token economics across multiple dimensions
    and produces a weighted score with letter grade.
    """

    # Score weights (must sum to 100)
    WEIGHT_SUPPLY_SAFETY = 10
    WEIGHT_DISTRIBUTION = 20
    WEIGHT_VESTING = 15
    WEIGHT_BURN_MECHANISM = 10
    WEIGHT_TEAM_ALLOCATION = 10
    WEIGHT_DAO_GOVERNANCE = 10
    WEIGHT_LIQUIDITY_POOL = 15
    WEIGHT_TIME_ON_MARKET = 10

    _instance: Optional["TokenomicsScorer"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        # Verify weights sum to 100
        total = (
            self.WEIGHT_SUPPLY_SAFETY +
            self.WEIGHT_DISTRIBUTION +
            self.WEIGHT_VESTING +
            self.WEIGHT_BURN_MECHANISM +
            self.WEIGHT_TEAM_ALLOCATION +
            self.WEIGHT_DAO_GOVERNANCE +
            self.WEIGHT_LIQUIDITY_POOL +
            self.WEIGHT_TIME_ON_MARKET
        )
        assert total == 100, f"Weights must sum to 100, got {total}"

        self._initialized = True
        logger.info("TokenomicsScorer initialized")

    def _score_to_grade(self, score: float) -> TokenomicsGrade:
        """Convert numeric score to letter grade."""
        if score >= 90:
            return TokenomicsGrade.A_PLUS
        elif score >= 80:
            return TokenomicsGrade.A
        elif score >= 70:
            return TokenomicsGrade.B
        elif score >= 60:
            return TokenomicsGrade.C
        elif score >= 50:
            return TokenomicsGrade.D
        else:
            return TokenomicsGrade.F

    def _score_supply_safety(
        self,
        is_fixed_supply: bool,
        is_mintable: bool,
        max_supply: Optional[int],
        current_supply: int,
    ) -> float:
        """
        Score supply safety.

        Best: Fixed supply, not mintable
        Worst: Unlimited mintable supply
        """
        score = 0.0

        if is_fixed_supply and not is_mintable:
            # Best case: fixed supply, cannot mint more
            score = self.WEIGHT_SUPPLY_SAFETY
        elif is_fixed_supply:
            # Fixed but somehow mintable (unusual)
            score = self.WEIGHT_SUPPLY_SAFETY * 0.7
        elif max_supply and max_supply > 0:
            # Has max cap
            supply_ratio = current_supply / max_supply if max_supply > 0 else 0
            if supply_ratio > 0.9:
                # Most supply already in circulation
                score = self.WEIGHT_SUPPLY_SAFETY * 0.8
            elif supply_ratio > 0.5:
                score = self.WEIGHT_SUPPLY_SAFETY * 0.5
            else:
                score = self.WEIGHT_SUPPLY_SAFETY * 0.3
        else:
            # Unlimited supply
            if is_mintable:
                score = self.WEIGHT_SUPPLY_SAFETY * 0.1
            else:
                score = self.WEIGHT_SUPPLY_SAFETY * 0.2

        return round(score, 2)

    def _score_distribution(
        self,
        top_10_concentration: float,
        holder_count: int,
    ) -> float:
        """
        Score holder distribution.

        Best: Low concentration, many holders
        Worst: High concentration, few holders
        """
        score = 0.0

        # Concentration scoring (0-15 points)
        if top_10_concentration < 30:
            score += self.WEIGHT_DISTRIBUTION * 0.75  # Excellent
        elif top_10_concentration < 40:
            score += self.WEIGHT_DISTRIBUTION * 0.6  # Good
        elif top_10_concentration < 50:
            score += self.WEIGHT_DISTRIBUTION * 0.4  # Fair
        elif top_10_concentration < 70:
            score += self.WEIGHT_DISTRIBUTION * 0.2  # Poor
        else:
            score += self.WEIGHT_DISTRIBUTION * 0.05  # Very poor

        # Holder count bonus (0-5 points)
        if holder_count > 100000:
            score += self.WEIGHT_DISTRIBUTION * 0.25
        elif holder_count > 10000:
            score += self.WEIGHT_DISTRIBUTION * 0.2
        elif holder_count > 1000:
            score += self.WEIGHT_DISTRIBUTION * 0.15
        elif holder_count > 100:
            score += self.WEIGHT_DISTRIBUTION * 0.1
        else:
            score += 0

        return min(self.WEIGHT_DISTRIBUTION, round(score, 2))

    def _score_vesting(
        self,
        vesting_months_remaining: int,
        has_cliff: bool = False,
        cliff_months: int = 0,
    ) -> float:
        """
        Score vesting schedule.

        Best: No vesting or complete, no cliffs
        Worst: Long vesting with imminent cliffs
        """
        score = 0.0

        if vesting_months_remaining <= 0:
            # Vesting complete
            score = self.WEIGHT_VESTING
        elif vesting_months_remaining <= 6:
            # Almost done
            score = self.WEIGHT_VESTING * 0.8
        elif vesting_months_remaining <= 12:
            score = self.WEIGHT_VESTING * 0.6
        elif vesting_months_remaining <= 24:
            score = self.WEIGHT_VESTING * 0.4
        else:
            score = self.WEIGHT_VESTING * 0.2

        # Cliff penalty
        if has_cliff and cliff_months <= 3:
            score *= 0.5  # Imminent cliff is risky

        return round(score, 2)

    def _score_burn_mechanism(
        self,
        has_burn_mechanism: bool,
        burn_rate_pct: float = 0.0,
    ) -> float:
        """
        Score burn mechanism.

        Best: Active burn mechanism with reasonable rate
        Neutral: No burn mechanism
        """
        if not has_burn_mechanism:
            # Neutral - not having burn is not bad
            return self.WEIGHT_BURN_MECHANISM * 0.5

        if burn_rate_pct > 10:
            # Very aggressive burn - slightly risky
            return self.WEIGHT_BURN_MECHANISM * 0.7
        elif burn_rate_pct > 1:
            # Healthy burn rate
            return self.WEIGHT_BURN_MECHANISM
        elif burn_rate_pct > 0:
            # Small burn rate
            return self.WEIGHT_BURN_MECHANISM * 0.8
        else:
            # Has mechanism but no activity
            return self.WEIGHT_BURN_MECHANISM * 0.6

    def _score_team_allocation(
        self,
        team_allocation_pct: float,
    ) -> float:
        """
        Score team allocation.

        Best: 5-15% team allocation (aligned but not dominant)
        Worst: 0% (no skin in game) or >50% (too much control)
        """
        if team_allocation_pct <= 0:
            # No team allocation - could be concerning
            return self.WEIGHT_TEAM_ALLOCATION * 0.5

        if 5 <= team_allocation_pct <= 15:
            # Ideal range
            return self.WEIGHT_TEAM_ALLOCATION
        elif team_allocation_pct < 5:
            # Low team allocation
            return self.WEIGHT_TEAM_ALLOCATION * 0.7
        elif team_allocation_pct <= 25:
            # Acceptable but high
            return self.WEIGHT_TEAM_ALLOCATION * 0.6
        elif team_allocation_pct <= 40:
            # Too high
            return self.WEIGHT_TEAM_ALLOCATION * 0.3
        else:
            # Team controls majority
            return self.WEIGHT_TEAM_ALLOCATION * 0.1

    def _score_dao_governance(
        self,
        has_dao_governance: bool,
        governance_participation: float = 0.0,
    ) -> float:
        """
        Score DAO governance.

        Best: Active DAO with participation
        Neutral: No DAO (common for many tokens)
        """
        if not has_dao_governance:
            return self.WEIGHT_DAO_GOVERNANCE * 0.5

        # Has DAO
        if governance_participation > 20:
            return self.WEIGHT_DAO_GOVERNANCE
        elif governance_participation > 5:
            return self.WEIGHT_DAO_GOVERNANCE * 0.8
        else:
            return self.WEIGHT_DAO_GOVERNANCE * 0.6

    def _score_liquidity(
        self,
        liquidity_usd: float,
        market_cap: float,
    ) -> float:
        """
        Score liquidity pool depth.

        Best: Deep liquidity relative to market cap
        Worst: Thin liquidity (slippage risk)
        """
        if liquidity_usd <= 0:
            return self.WEIGHT_LIQUIDITY_POOL * 0.1

        # Liquidity to market cap ratio
        if market_cap > 0:
            liq_ratio = liquidity_usd / market_cap
        else:
            liq_ratio = 0

        # Absolute liquidity scoring
        if liquidity_usd > 10_000_000:
            base_score = self.WEIGHT_LIQUIDITY_POOL
        elif liquidity_usd > 1_000_000:
            base_score = self.WEIGHT_LIQUIDITY_POOL * 0.9
        elif liquidity_usd > 100_000:
            base_score = self.WEIGHT_LIQUIDITY_POOL * 0.7
        elif liquidity_usd > 50_000:
            base_score = self.WEIGHT_LIQUIDITY_POOL * 0.5
        elif liquidity_usd > 10_000:
            base_score = self.WEIGHT_LIQUIDITY_POOL * 0.3
        else:
            base_score = self.WEIGHT_LIQUIDITY_POOL * 0.1

        # Ratio bonus
        if liq_ratio > 0.1:  # >10% of mcap in liquidity
            base_score = min(self.WEIGHT_LIQUIDITY_POOL, base_score * 1.2)
        elif liq_ratio < 0.01:  # <1% of mcap in liquidity
            base_score *= 0.8

        return round(base_score, 2)

    def _score_time_on_market(
        self,
        created_timestamp: Optional[datetime],
    ) -> float:
        """
        Score time on market.

        Best: Established tokens (>2 years)
        Worst: Very new tokens (<1 week)
        """
        if not created_timestamp:
            # Unknown age - neutral
            return self.WEIGHT_TIME_ON_MARKET * 0.5

        now = datetime.now(timezone.utc)
        age = now - created_timestamp

        if age > timedelta(days=730):  # >2 years
            return self.WEIGHT_TIME_ON_MARKET
        elif age > timedelta(days=365):  # >1 year
            return self.WEIGHT_TIME_ON_MARKET * 0.9
        elif age > timedelta(days=180):  # >6 months
            return self.WEIGHT_TIME_ON_MARKET * 0.7
        elif age > timedelta(days=30):  # >1 month
            return self.WEIGHT_TIME_ON_MARKET * 0.5
        elif age > timedelta(days=7):  # >1 week
            return self.WEIGHT_TIME_ON_MARKET * 0.3
        else:
            return self.WEIGHT_TIME_ON_MARKET * 0.1

    async def score_tokenomics(
        self,
        token_address: str,
        total_supply: int = 0,
        current_supply: int = 0,
        is_fixed_supply: bool = True,
        is_mintable: bool = False,
        max_supply: Optional[int] = None,
        top_10_concentration: float = 50.0,
        holder_count: int = 0,
        liquidity_usd: float = 0.0,
        market_cap: float = 0.0,
        has_burn_mechanism: bool = False,
        burn_rate_pct: float = 0.0,
        team_allocation_pct: float = 0.0,
        has_dao_governance: bool = False,
        governance_participation: float = 0.0,
        vesting_months_remaining: int = 0,
        has_cliff: bool = False,
        cliff_months: int = 0,
        created_timestamp: Optional[datetime] = None,
    ) -> TokenomicsScore:
        """
        Calculate complete tokenomics score.

        Args:
            token_address: Token mint address
            total_supply: Total token supply
            current_supply: Current circulating supply
            is_fixed_supply: Whether supply is fixed
            is_mintable: Whether more can be minted
            max_supply: Maximum possible supply
            top_10_concentration: Top 10 holder concentration %
            holder_count: Number of holders
            liquidity_usd: Liquidity pool depth in USD
            market_cap: Market capitalization in USD
            has_burn_mechanism: Whether token has burn
            burn_rate_pct: Annual burn rate %
            team_allocation_pct: Team allocation %
            has_dao_governance: Whether has DAO
            governance_participation: DAO participation %
            vesting_months_remaining: Months until vesting complete
            has_cliff: Whether vesting has cliff
            cliff_months: Months until cliff
            created_timestamp: Token creation time

        Returns:
            TokenomicsScore with complete analysis
        """
        components = []
        red_flags = []
        green_flags = []

        # 1. Supply safety
        supply_score = self._score_supply_safety(
            is_fixed_supply, is_mintable, max_supply, current_supply or total_supply
        )
        components.append(ScoreComponent(
            name="Supply Safety",
            score=supply_score,
            max_score=self.WEIGHT_SUPPLY_SAFETY,
            reason="Fixed supply" if is_fixed_supply else "Inflationary"
        ))

        if is_fixed_supply:
            green_flags.append("Fixed supply")
        elif is_mintable:
            red_flags.append("Unlimited minting possible")

        # 2. Distribution
        dist_score = self._score_distribution(top_10_concentration, holder_count)
        components.append(ScoreComponent(
            name="Distribution",
            score=dist_score,
            max_score=self.WEIGHT_DISTRIBUTION,
            reason=f"{top_10_concentration:.1f}% top 10 concentration, {holder_count} holders"
        ))

        if top_10_concentration > 70:
            red_flags.append(f"High concentration: top 10 own {top_10_concentration:.1f}%")
        elif top_10_concentration < 30:
            green_flags.append("Well-distributed holders")

        # 3. Vesting
        vesting_score = self._score_vesting(vesting_months_remaining, has_cliff, cliff_months)
        components.append(ScoreComponent(
            name="Vesting Schedule",
            score=vesting_score,
            max_score=self.WEIGHT_VESTING,
            reason=f"{vesting_months_remaining} months remaining" if vesting_months_remaining > 0 else "Complete"
        ))

        if has_cliff and cliff_months <= 3:
            red_flags.append(f"Cliff unlock in {cliff_months} months")

        # 4. Burn mechanism
        burn_score = self._score_burn_mechanism(has_burn_mechanism, burn_rate_pct)
        components.append(ScoreComponent(
            name="Burn Mechanism",
            score=burn_score,
            max_score=self.WEIGHT_BURN_MECHANISM,
            reason="Active" if has_burn_mechanism else "None"
        ))

        if has_burn_mechanism and burn_rate_pct > 0:
            green_flags.append("Deflationary mechanism")

        # 5. Team allocation
        team_score = self._score_team_allocation(team_allocation_pct)
        components.append(ScoreComponent(
            name="Team Allocation",
            score=team_score,
            max_score=self.WEIGHT_TEAM_ALLOCATION,
            reason=f"{team_allocation_pct:.1f}% team allocation"
        ))

        if team_allocation_pct > 40:
            red_flags.append(f"High team allocation: {team_allocation_pct:.1f}%")
        elif 5 <= team_allocation_pct <= 15:
            green_flags.append("Balanced team allocation")

        # 6. DAO governance
        dao_score = self._score_dao_governance(has_dao_governance, governance_participation)
        components.append(ScoreComponent(
            name="DAO Governance",
            score=dao_score,
            max_score=self.WEIGHT_DAO_GOVERNANCE,
            reason="Active DAO" if has_dao_governance else "No DAO"
        ))

        if has_dao_governance:
            green_flags.append("Community governance")

        # 7. Liquidity
        liq_score = self._score_liquidity(liquidity_usd, market_cap)
        components.append(ScoreComponent(
            name="Liquidity Pool",
            score=liq_score,
            max_score=self.WEIGHT_LIQUIDITY_POOL,
            reason=f"${liquidity_usd:,.0f} liquidity"
        ))

        if liquidity_usd < 10000:
            red_flags.append("Very low liquidity")
        elif liquidity_usd > 1000000:
            green_flags.append("Deep liquidity")

        # 8. Time on market
        time_score = self._score_time_on_market(created_timestamp)
        age_str = "Unknown"
        if created_timestamp:
            age_days = (datetime.now(timezone.utc) - created_timestamp).days
            age_str = f"{age_days} days"
        components.append(ScoreComponent(
            name="Time on Market",
            score=time_score,
            max_score=self.WEIGHT_TIME_ON_MARKET,
            reason=f"Age: {age_str}"
        ))

        if created_timestamp:
            age_days = (datetime.now(timezone.utc) - created_timestamp).days
            if age_days < 7:
                red_flags.append("Very new token (<1 week)")
            elif age_days > 365:
                green_flags.append("Established token (>1 year)")

        # Calculate total score
        total_score = sum(c.score for c in components)
        grade = self._score_to_grade(total_score)

        # Generate recommendation
        if grade in [TokenomicsGrade.A_PLUS, TokenomicsGrade.A]:
            recommendation = "Strong tokenomics. Lower risk for trading."
        elif grade == TokenomicsGrade.B:
            recommendation = "Good tokenomics with some concerns. Acceptable risk."
        elif grade == TokenomicsGrade.C:
            recommendation = "Fair tokenomics. Exercise caution."
        elif grade == TokenomicsGrade.D:
            recommendation = "Poor tokenomics. Higher risk."
        else:
            recommendation = "Risky tokenomics. Not recommended for significant positions."

        return TokenomicsScore(
            token_address=token_address,
            total_score=total_score,
            grade=grade,
            components=components,
            red_flags=red_flags,
            green_flags=green_flags,
            recommendation=recommendation,
        )


# Singleton accessor
def get_tokenomics_scorer() -> TokenomicsScorer:
    """Get the TokenomicsScorer singleton instance."""
    return TokenomicsScorer()


if __name__ == "__main__":
    import asyncio
    logging.basicConfig(level=logging.INFO)

    async def test():
        print("=== Tokenomics Scorer Test ===")

        scorer = get_tokenomics_scorer()

        # Test with SOL-like token
        result = await scorer.score_tokenomics(
            token_address="So11111111111111111111111111111111111111112",
            total_supply=500_000_000,
            current_supply=400_000_000,
            is_fixed_supply=False,  # SOL is inflationary
            is_mintable=True,
            top_10_concentration=15.0,
            holder_count=5_000_000,
            liquidity_usd=100_000_000,
            market_cap=50_000_000_000,
            has_burn_mechanism=True,
            burn_rate_pct=0.5,
            team_allocation_pct=12.0,
            has_dao_governance=True,
            governance_participation=10.0,
            vesting_months_remaining=0,
            created_timestamp=datetime(2020, 3, 1, tzinfo=timezone.utc),
        )

        print(f"\nToken: {result.token_address}")
        print(f"Total Score: {result.total_score:.1f}/100")
        print(f"Grade: {result.grade.value}")
        print(f"\nComponents:")
        for comp in result.components:
            print(f"  {comp.name}: {comp.score}/{comp.max_score} ({comp.reason})")
        print(f"\nGreen Flags: {result.green_flags}")
        print(f"Red Flags: {result.red_flags}")
        print(f"\nRecommendation: {result.recommendation}")

    asyncio.run(test())
