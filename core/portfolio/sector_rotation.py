"""
Sector Rotation

Manages sector-based portfolio allocation.
Rotates allocation based on sector sentiment changes.

Prompts #293: Multi-Asset Support and Portfolio Optimization
"""

import logging
import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class SectorAllocation:
    """Sector allocation details."""
    sector: str
    current_weight: float
    target_weight: float
    sentiment: float
    tokens: List[str]


class SectorRotation:
    """
    Manages sector-based portfolio rotation.

    Features:
    - Token-to-sector mapping
    - Sector weight calculation
    - Sentiment-based rotation
    - Quarterly rotation schedule
    """

    SECTOR_STATE_FILE = Path("data/portfolio/sector_state.json")

    # Token to sector mapping
    SECTOR_MAPPING = {
        # DeFi
        'JUP': 'DeFi',
        'RAY': 'DeFi',
        'ORCA': 'DeFi',
        'MNDE': 'DeFi',
        'SBR': 'DeFi',
        'MSOL': 'DeFi',
        'STSOL': 'DeFi',

        # Infrastructure / Layer 1
        'SOL': 'Infrastructure',
        'RNDR': 'Infrastructure',
        'HNT': 'Infrastructure',
        'MOBILE': 'Infrastructure',
        'IOT': 'Infrastructure',
        'PYTH': 'Infrastructure',
        'W': 'Infrastructure',

        # Meme
        'BONK': 'Meme',
        'WIF': 'Meme',

        # Gaming / NFT
        'GENE': 'Gaming',
        'GMT': 'Gaming',
        'GST': 'Gaming',

        # Layer 2 / Scaling (cross-chain)
        'WETH': 'Layer2',
        'WBTC': 'Layer2',

        # Stablecoins
        'USDC': 'Stablecoin',
        'USDT': 'Stablecoin',

        # Governance
        'JTO': 'Governance',

        # Storage
        'SHDW': 'Storage',
    }

    # Default sector weights
    DEFAULT_SECTOR_WEIGHTS = {
        'DeFi': 0.25,
        'Infrastructure': 0.30,
        'Meme': 0.10,
        'Gaming': 0.10,
        'Layer2': 0.10,
        'Governance': 0.05,
        'Storage': 0.05,
        'Stablecoin': 0.05,
        'Other': 0.00,
    }

    FREQUENCY_DAYS = {
        'monthly': 30,
        'quarterly': 90,
        'semiannual': 180,
    }

    def __init__(
        self,
        rotation_frequency: str = 'quarterly',
        rotation_threshold: float = 0.20,  # 20% sentiment change
        storage_path: Optional[str] = None
    ):
        """
        Initialize sector rotation manager.

        Args:
            rotation_frequency: 'monthly', 'quarterly', 'semiannual'
            rotation_threshold: Minimum sentiment change to trigger rotation
            storage_path: Path to store sector state
        """
        self.rotation_frequency = rotation_frequency
        self.rotation_threshold = rotation_threshold
        self.storage_path = Path(storage_path) if storage_path else self.SECTOR_STATE_FILE

        self._last_rotation: Optional[datetime] = None
        self._sector_sentiment: Dict[str, float] = {}
        self._rotation_history: List[Dict] = []

        self._load_state()

    def get_sector(self, token: str) -> str:
        """
        Get sector for a token.

        Args:
            token: Token symbol

        Returns:
            Sector name (or 'Other' if unknown)
        """
        return self.SECTOR_MAPPING.get(token.upper(), 'Other')

    def calculate_sector_weights(
        self,
        positions: Dict[str, Dict[str, Any]]
    ) -> Dict[str, float]:
        """
        Calculate current sector weights from positions.

        Args:
            positions: Dict mapping token to position info with 'value' key

        Returns:
            Dict mapping sector to weight (0-1)
        """
        if not positions:
            return {}

        # Calculate total value
        total_value = sum(p.get('value', 0) for p in positions.values())

        if total_value <= 0:
            return {}

        # Aggregate by sector
        sector_values = {}
        for token, pos in positions.items():
            sector = self.get_sector(token)
            value = pos.get('value', 0)
            sector_values[sector] = sector_values.get(sector, 0) + value

        # Convert to weights
        return {s: v / total_value for s, v in sector_values.items()}

    def calculate_rotation(
        self,
        old_sentiment: Dict[str, float],
        new_sentiment: Dict[str, float]
    ) -> Dict[str, float]:
        """
        Calculate sector rotation based on sentiment change.

        Args:
            old_sentiment: Previous sentiment scores by sector
            new_sentiment: Current sentiment scores by sector

        Returns:
            Dict mapping sector to weight change (positive = increase, negative = decrease)
        """
        rotation = {}

        # Get all sectors
        all_sectors = set(old_sentiment.keys()) | set(new_sentiment.keys())

        for sector in all_sectors:
            old = old_sentiment.get(sector, 0.5)  # Default neutral
            new = new_sentiment.get(sector, 0.5)

            change = new - old

            # Only rotate if change exceeds threshold
            if abs(change) >= self.rotation_threshold:
                # Scale rotation by sentiment change magnitude
                rotation[sector] = change * 0.5  # Moderate the rotation
            else:
                rotation[sector] = 0

        return rotation

    def should_rotate(
        self,
        last_rotation: Optional[datetime] = None
    ) -> bool:
        """
        Check if enough time has passed for scheduled rotation.

        Args:
            last_rotation: Time of last rotation (uses stored if None)

        Returns:
            True if should rotate based on schedule
        """
        last = last_rotation or self._last_rotation

        if last is None:
            return True  # Never rotated

        days_since = (datetime.now() - last).days
        required_days = self.FREQUENCY_DAYS.get(self.rotation_frequency, 90)

        return days_since >= required_days

    def get_recommendations(
        self,
        current_positions: Dict[str, Dict[str, Any]],
        sentiment: Dict[str, float]
    ) -> Dict[str, Any]:
        """
        Get sector rotation recommendations.

        Args:
            current_positions: Current positions with 'value' and optionally 'sector'
            sentiment: Current sentiment by sector (0-1, higher = more bullish)

        Returns:
            Recommendations dict with 'reduce', 'increase', 'maintain'
        """
        # Calculate current sector weights
        current_weights = self.calculate_sector_weights(current_positions)

        recommendations = {
            'reduce': [],
            'increase': [],
            'maintain': [],
            'analysis': []
        }

        # Analyze each sector
        for sector, sent in sentiment.items():
            current_weight = current_weights.get(sector, 0)
            default_weight = self.DEFAULT_SECTOR_WEIGHTS.get(sector, 0.05)

            # Determine recommendation based on sentiment
            if sent >= 0.7:  # Strong bullish
                if current_weight < default_weight * 1.2:
                    recommendations['increase'].append({
                        'sector': sector,
                        'sentiment': sent,
                        'current_weight': round(current_weight, 3),
                        'suggested_action': 'increase allocation'
                    })
                else:
                    recommendations['maintain'].append({
                        'sector': sector,
                        'sentiment': sent,
                        'current_weight': round(current_weight, 3)
                    })

            elif sent <= 0.3:  # Bearish
                if current_weight > default_weight * 0.5:
                    recommendations['reduce'].append({
                        'sector': sector,
                        'sentiment': sent,
                        'current_weight': round(current_weight, 3),
                        'suggested_action': 'reduce allocation'
                    })
                else:
                    recommendations['maintain'].append({
                        'sector': sector,
                        'sentiment': sent,
                        'current_weight': round(current_weight, 3)
                    })

            else:  # Neutral
                recommendations['maintain'].append({
                    'sector': sector,
                    'sentiment': sent,
                    'current_weight': round(current_weight, 3)
                })

        # Check for underweight high-sentiment sectors
        for sector in self.DEFAULT_SECTOR_WEIGHTS:
            if sector not in sentiment:
                continue

            sent = sentiment.get(sector, 0.5)
            current = current_weights.get(sector, 0)
            default = self.DEFAULT_SECTOR_WEIGHTS.get(sector, 0.05)

            if sent >= 0.6 and current < default * 0.5:
                recommendations['analysis'].append({
                    'observation': f"{sector} has strong sentiment ({sent:.2f}) but is underweight ({current*100:.1f}%)",
                    'suggestion': 'Consider adding exposure'
                })

            elif sent <= 0.4 and current > default * 1.5:
                recommendations['analysis'].append({
                    'observation': f"{sector} has weak sentiment ({sent:.2f}) but is overweight ({current*100:.1f}%)",
                    'suggestion': 'Consider reducing exposure'
                })

        recommendations['generated_at'] = datetime.now().isoformat()
        return recommendations

    def apply_rotation(
        self,
        current_weights: Dict[str, float],
        rotation: Dict[str, float]
    ) -> Dict[str, float]:
        """
        Apply rotation to get new target weights.

        Args:
            current_weights: Current sector weights
            rotation: Rotation changes from calculate_rotation

        Returns:
            New target sector weights (normalized to sum to 1)
        """
        new_weights = {}

        # Apply rotation
        for sector in set(current_weights.keys()) | set(rotation.keys()):
            current = current_weights.get(sector, 0)
            change = rotation.get(sector, 0)
            new_weights[sector] = max(0, current + change)

        # Normalize to sum to 1
        total = sum(new_weights.values())
        if total > 0:
            new_weights = {s: w / total for s, w in new_weights.items()}

        return new_weights

    def get_sector_report(
        self,
        positions: Dict[str, Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Generate a sector allocation report.

        Args:
            positions: Current positions

        Returns:
            Report dict with sector breakdown
        """
        current_weights = self.calculate_sector_weights(positions)

        sectors = []
        for sector in set(current_weights.keys()) | set(self.DEFAULT_SECTOR_WEIGHTS.keys()):
            current = current_weights.get(sector, 0)
            default = self.DEFAULT_SECTOR_WEIGHTS.get(sector, 0.05)
            diff = current - default

            # Find tokens in this sector
            tokens = [
                token for token, s in self.SECTOR_MAPPING.items()
                if s == sector and token in positions
            ]

            sectors.append({
                'sector': sector,
                'current_weight': round(current, 4),
                'default_weight': round(default, 4),
                'difference': round(diff, 4),
                'status': 'overweight' if diff > 0.05 else ('underweight' if diff < -0.05 else 'balanced'),
                'tokens': tokens
            })

        # Sort by current weight
        sectors.sort(key=lambda x: x['current_weight'], reverse=True)

        return {
            'sectors': sectors,
            'total_sectors': len([s for s in sectors if s['current_weight'] > 0]),
            'diversification_score': self._calculate_diversification_score(current_weights),
            'generated_at': datetime.now().isoformat()
        }

    def _calculate_diversification_score(
        self,
        weights: Dict[str, float]
    ) -> float:
        """
        Calculate a diversification score (0-100).

        Higher score = better diversification across sectors.
        """
        if not weights:
            return 0

        # Use Herfindahl-Hirschman Index (inverse)
        # HHI = sum of squared weights
        # Perfect diversification would have equal weights

        hhi = sum(w ** 2 for w in weights.values())

        # Convert to score (lower HHI = better diversification)
        # With equal weights across N sectors, HHI = 1/N
        # Perfect concentration (1 sector) = HHI = 1

        if hhi >= 1:
            return 0

        # Scale to 0-100 where lower HHI gives higher score
        score = (1 - hhi) * 100

        return round(score, 1)

    def update_sentiment(
        self,
        sentiment: Dict[str, float]
    ):
        """
        Update stored sector sentiment.

        Args:
            sentiment: New sentiment scores by sector
        """
        self._sector_sentiment = sentiment
        self._save_state()

    def _save_state(self):
        """Save sector state to disk."""
        try:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)

            data = {
                'last_rotation': self._last_rotation.isoformat() if self._last_rotation else None,
                'sector_sentiment': self._sector_sentiment,
                'rotation_history': self._rotation_history[-50:],
                'saved_at': datetime.now().isoformat()
            }

            with open(self.storage_path, 'w') as f:
                json.dump(data, f, indent=2)

        except Exception as e:
            logger.error(f"Failed to save sector state: {e}")

    def _load_state(self):
        """Load sector state from disk."""
        if not self.storage_path.exists():
            return

        try:
            with open(self.storage_path) as f:
                data = json.load(f)

            last = data.get('last_rotation')
            if last:
                self._last_rotation = datetime.fromisoformat(last)

            self._sector_sentiment = data.get('sector_sentiment', {})
            self._rotation_history = data.get('rotation_history', [])

        except Exception as e:
            logger.error(f"Failed to load sector state: {e}")


# Singleton instance
_sector_rotation: Optional[SectorRotation] = None


def get_sector_rotation() -> SectorRotation:
    """Get sector rotation singleton."""
    global _sector_rotation

    if _sector_rotation is None:
        _sector_rotation = SectorRotation()

    return _sector_rotation


# Testing
if __name__ == "__main__":
    sr = SectorRotation()

    # Test sector mapping
    print("Sector Mapping:")
    for token in ['JUP', 'SOL', 'BONK', 'RNDR', 'UNKNOWN']:
        print(f"  {token}: {sr.get_sector(token)}")

    # Test positions
    positions = {
        'JUP': {'value': 1000},
        'RAY': {'value': 1000},
        'SOL': {'value': 2000},
        'BONK': {'value': 500},
        'RNDR': {'value': 500},
    }

    # Calculate sector weights
    weights = sr.calculate_sector_weights(positions)
    print("\nSector Weights:")
    for sector, weight in sorted(weights.items(), key=lambda x: x[1], reverse=True):
        print(f"  {sector}: {weight*100:.1f}%")

    # Test sentiment-based recommendations
    sentiment = {
        'DeFi': 0.4,  # Weak
        'Infrastructure': 0.8,  # Strong
        'Meme': 0.5,  # Neutral
    }

    recs = sr.get_recommendations(positions, sentiment)
    print("\nRecommendations:")
    print(f"  Reduce: {[r['sector'] for r in recs['reduce']]}")
    print(f"  Increase: {[r['sector'] for r in recs['increase']]}")
    print(f"  Maintain: {[r['sector'] for r in recs['maintain']]}")

    # Sector report
    report = sr.get_sector_report(positions)
    print(f"\nDiversification Score: {report['diversification_score']}/100")
