"""
Portfolio Rebalancer

Handles portfolio rebalancing to maintain target allocations.
Triggers when drift exceeds threshold.

Prompts #293: Multi-Asset Support and Portfolio Optimization
"""

import logging
import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class RebalanceTrade:
    """A single rebalancing trade."""
    asset: str
    action: str  # 'buy' or 'sell'
    amount_usd: float
    current_weight: float
    target_weight: float
    drift: float
    estimated_fee: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'asset': self.asset,
            'action': self.action,
            'amount_usd': self.amount_usd,
            'current_weight': self.current_weight,
            'target_weight': self.target_weight,
            'drift': self.drift,
            'estimated_fee': self.estimated_fee
        }


@dataclass
class RebalanceResult:
    """Result of a rebalancing operation."""
    trades: List[Dict[str, Any]]
    executed: int = 0
    failed: int = 0
    total_cost: float = 0.0
    executed_at: datetime = field(default_factory=datetime.now)


class Rebalancer:
    """
    Portfolio rebalancer that maintains target allocations.

    Features:
    - Drift threshold (10% default)
    - Monthly rebalancing schedule
    - Trading cost awareness
    - Correlation warnings
    - Minimum trade size
    """

    REBALANCE_STATE_FILE = Path("data/portfolio/rebalance_state.json")

    FREQUENCY_DAYS = {
        'weekly': 7,
        'biweekly': 14,
        'monthly': 30,
        'quarterly': 90,
    }

    def __init__(
        self,
        drift_threshold: float = 0.10,  # 10% drift triggers rebalance
        rebalance_frequency: str = 'monthly',
        trading_fee_pct: float = 0.003,  # 0.3% fee
        min_trade_size: float = 10.0,  # $10 minimum
        correlation_matrix: Optional[Dict[str, Dict[str, float]]] = None,
        max_correlation: float = 0.7,
        storage_path: Optional[str] = None
    ):
        """
        Initialize rebalancer.

        Args:
            drift_threshold: Max drift before rebalancing (0.10 = 10%)
            rebalance_frequency: 'weekly', 'biweekly', 'monthly', 'quarterly'
            trading_fee_pct: Expected trading fee percentage
            min_trade_size: Minimum trade size in USD
            correlation_matrix: Pre-computed correlation matrix
            max_correlation: Max correlation threshold for warnings
            storage_path: Path to store rebalancing state
        """
        self.drift_threshold = drift_threshold
        self.rebalance_frequency = rebalance_frequency
        self.trading_fee_pct = trading_fee_pct
        self.min_trade_size = min_trade_size
        self.correlation_matrix = correlation_matrix or {}
        self.max_correlation = max_correlation
        self.storage_path = Path(storage_path) if storage_path else self.REBALANCE_STATE_FILE

        self._last_rebalance: Optional[datetime] = None
        self._rebalance_history: List[Dict] = []

        self._load_state()

    def calculate_rebalance_trades(
        self,
        current_weights: Dict[str, float],
        target_weights: Dict[str, float],
        portfolio_value: float
    ) -> List[Dict[str, Any]]:
        """
        Calculate trades needed to rebalance portfolio.

        Args:
            current_weights: Current allocation weights
            target_weights: Target allocation weights
            portfolio_value: Total portfolio value in USD

        Returns:
            List of trade dicts with 'asset', 'action', 'amount_usd', etc.
        """
        trades = []

        # Get all assets (union of current and target)
        all_assets = set(current_weights.keys()) | set(target_weights.keys())

        for asset in all_assets:
            current = current_weights.get(asset, 0.0)
            target = target_weights.get(asset, 0.0)

            # Calculate drift
            drift = abs(current - target)

            # Only trade if drift exceeds threshold
            if drift < self.drift_threshold:
                continue

            # Calculate trade amount
            weight_diff = target - current
            amount_usd = abs(weight_diff) * portfolio_value

            # Skip small trades
            if amount_usd < self.min_trade_size:
                continue

            # Determine action
            action = 'buy' if weight_diff > 0 else 'sell'

            # Estimate fee
            estimated_fee = amount_usd * self.trading_fee_pct

            trade = {
                'asset': asset,
                'action': action,
                'amount_usd': round(amount_usd, 2),
                'current_weight': round(current, 4),
                'target_weight': round(target, 4),
                'drift': round(drift, 4),
                'estimated_fee': round(estimated_fee, 2)
            }
            trades.append(trade)

        # Sort by amount (largest first for better execution)
        trades.sort(key=lambda x: x['amount_usd'], reverse=True)

        return trades

    def should_rebalance(
        self,
        last_rebalance: Optional[datetime] = None
    ) -> bool:
        """
        Check if enough time has passed for scheduled rebalancing.

        Args:
            last_rebalance: Time of last rebalance (uses stored if None)

        Returns:
            True if should rebalance based on schedule
        """
        last = last_rebalance or self._last_rebalance

        if last is None:
            return True  # Never rebalanced

        days_since = (datetime.now() - last).days
        required_days = self.FREQUENCY_DAYS.get(self.rebalance_frequency, 30)

        return days_since >= required_days

    def check_correlation_warnings(
        self,
        weights: Dict[str, float]
    ) -> List[Dict[str, Any]]:
        """
        Check for highly correlated asset pairs in portfolio.

        Args:
            weights: Current portfolio weights

        Returns:
            List of warning dicts with 'asset_a', 'asset_b', 'correlation'
        """
        warnings = []

        if not self.correlation_matrix:
            return warnings

        assets = [a for a in weights.keys() if weights[a] > 0.01]

        for i, asset_a in enumerate(assets):
            for j, asset_b in enumerate(assets):
                if j <= i:
                    continue

                corr = abs(self.correlation_matrix.get(asset_a, {}).get(asset_b, 0))

                if corr >= self.max_correlation:
                    warnings.append({
                        'asset_a': asset_a,
                        'asset_b': asset_b,
                        'correlation': round(corr, 3),
                        'combined_weight': round(weights[asset_a] + weights[asset_b], 3),
                        'message': f"{asset_a} and {asset_b} are highly correlated ({corr:.2f})"
                    })

        return warnings

    def calculate_drift_report(
        self,
        current_weights: Dict[str, float],
        target_weights: Dict[str, float]
    ) -> Dict[str, Any]:
        """
        Generate a drift report showing how far from targets.

        Args:
            current_weights: Current allocation
            target_weights: Target allocation

        Returns:
            Dict with drift analysis
        """
        all_assets = set(current_weights.keys()) | set(target_weights.keys())

        drifts = []
        max_drift = 0.0
        total_drift = 0.0

        for asset in all_assets:
            current = current_weights.get(asset, 0.0)
            target = target_weights.get(asset, 0.0)
            drift = current - target

            drifts.append({
                'asset': asset,
                'current': round(current, 4),
                'target': round(target, 4),
                'drift': round(drift, 4),
                'drift_pct': round(drift * 100, 2),
                'needs_rebalance': abs(drift) >= self.drift_threshold
            })

            max_drift = max(max_drift, abs(drift))
            total_drift += abs(drift)

        return {
            'drifts': sorted(drifts, key=lambda x: abs(x['drift']), reverse=True),
            'max_drift': round(max_drift, 4),
            'total_drift': round(total_drift, 4),
            'needs_rebalance': max_drift >= self.drift_threshold,
            'threshold': self.drift_threshold,
            'generated_at': datetime.now().isoformat()
        }

    async def execute_rebalance(
        self,
        trades: List[Dict[str, Any]],
        trading_engine: Any
    ) -> Dict[str, Any]:
        """
        Execute rebalancing trades.

        Args:
            trades: List of trades from calculate_rebalance_trades
            trading_engine: Trading engine with execute_trade method

        Returns:
            Result dict with execution details
        """
        result = {
            'executed': 0,
            'failed': 0,
            'trades': [],
            'total_fees': 0.0,
            'started_at': datetime.now().isoformat()
        }

        for trade in trades:
            try:
                # Execute trade via trading engine
                exec_result = await trading_engine.execute_trade(
                    token=trade['asset'],
                    action=trade['action'],
                    amount_usd=trade['amount_usd']
                )

                if exec_result.get('success'):
                    result['executed'] += 1
                    result['trades'].append({
                        **trade,
                        'status': 'executed',
                        'tx_hash': exec_result.get('tx_hash')
                    })
                    result['total_fees'] += trade.get('estimated_fee', 0)
                else:
                    result['failed'] += 1
                    result['trades'].append({
                        **trade,
                        'status': 'failed',
                        'error': exec_result.get('error', 'Unknown error')
                    })

            except Exception as e:
                logger.error(f"Rebalance trade failed for {trade['asset']}: {e}")
                result['failed'] += 1
                result['trades'].append({
                    **trade,
                    'status': 'failed',
                    'error': str(e)
                })

        # Update state
        if result['executed'] > 0:
            self._last_rebalance = datetime.now()
            self._rebalance_history.append({
                'timestamp': datetime.now().isoformat(),
                'executed': result['executed'],
                'failed': result['failed'],
                'total_fees': result['total_fees']
            })
            self._save_state()

        result['completed_at'] = datetime.now().isoformat()
        return result

    def estimate_rebalance_cost(
        self,
        trades: List[Dict[str, Any]]
    ) -> Dict[str, float]:
        """
        Estimate total cost of rebalancing.

        Args:
            trades: List of proposed trades

        Returns:
            Dict with cost breakdown
        """
        total_volume = sum(t['amount_usd'] for t in trades)
        total_fees = sum(t.get('estimated_fee', 0) for t in trades)

        return {
            'total_volume': round(total_volume, 2),
            'total_fees': round(total_fees, 2),
            'fee_percentage': round(total_fees / total_volume * 100, 3) if total_volume > 0 else 0,
            'trade_count': len(trades)
        }

    def get_rebalance_history(
        self,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Get recent rebalancing history."""
        return self._rebalance_history[-limit:]

    def _save_state(self):
        """Save rebalancing state to disk."""
        try:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)

            data = {
                'last_rebalance': self._last_rebalance.isoformat() if self._last_rebalance else None,
                'rebalance_history': self._rebalance_history[-100:],  # Keep last 100
                'saved_at': datetime.now().isoformat()
            }

            with open(self.storage_path, 'w') as f:
                json.dump(data, f, indent=2)

        except Exception as e:
            logger.error(f"Failed to save rebalance state: {e}")

    def _load_state(self):
        """Load rebalancing state from disk."""
        if not self.storage_path.exists():
            return

        try:
            with open(self.storage_path) as f:
                data = json.load(f)

            last = data.get('last_rebalance')
            if last:
                self._last_rebalance = datetime.fromisoformat(last)

            self._rebalance_history = data.get('rebalance_history', [])

        except Exception as e:
            logger.error(f"Failed to load rebalance state: {e}")


# Singleton instance
_rebalancer: Optional[Rebalancer] = None


def get_rebalancer() -> Rebalancer:
    """Get rebalancer singleton."""
    global _rebalancer

    if _rebalancer is None:
        _rebalancer = Rebalancer()

    return _rebalancer


# Testing
if __name__ == "__main__":
    rebalancer = Rebalancer(drift_threshold=0.10, trading_fee_pct=0.003)

    # Current vs target weights
    current = {'SOL': 0.45, 'ETH': 0.30, 'BTC': 0.25}
    target = {'SOL': 0.33, 'ETH': 0.33, 'BTC': 0.34}

    # Calculate trades
    trades = rebalancer.calculate_rebalance_trades(current, target, portfolio_value=10000)

    print("Rebalancing Trades:")
    for trade in trades:
        print(f"  {trade['action'].upper()} {trade['asset']}: ${trade['amount_usd']:.2f}")
        print(f"    Current: {trade['current_weight']*100:.1f}% -> Target: {trade['target_weight']*100:.1f}%")
        print(f"    Drift: {trade['drift']*100:.1f}%, Fee: ${trade['estimated_fee']:.2f}")

    # Cost estimate
    cost = rebalancer.estimate_rebalance_cost(trades)
    print(f"\nTotal Cost: ${cost['total_fees']:.2f} ({cost['fee_percentage']:.2f}%)")

    # Drift report
    report = rebalancer.calculate_drift_report(current, target)
    print(f"\nDrift Report:")
    print(f"  Max Drift: {report['max_drift']*100:.1f}%")
    print(f"  Needs Rebalance: {report['needs_rebalance']}")
