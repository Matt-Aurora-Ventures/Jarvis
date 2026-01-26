"""
Metrics tracking for bags.fm integration.

Tracks:
- bags.fm vs Jupiter usage
- Success rates
- Volume
- Partner fees
- TP/SL trigger rates
"""
from dataclasses import dataclass, asdict
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)


@dataclass
class BagsMetrics:
    """bags.fm usage metrics."""
    bags_trades: int = 0
    jupiter_trades: int = 0
    bags_failures: int = 0
    jupiter_failures: int = 0
    total_volume_sol: float = 0.0
    partner_fees_earned: float = 0.0

    tp_triggers: int = 0
    sl_triggers: int = 0
    trailing_triggers: int = 0

    def bags_success_rate(self) -> float:
        """Calculate bags.fm success rate."""
        total = self.bags_trades + self.bags_failures
        return self.bags_trades / total if total > 0 else 0.0

    def jupiter_success_rate(self) -> float:
        """Calculate Jupiter success rate."""
        total = self.jupiter_trades + self.jupiter_failures
        return self.jupiter_trades / total if total > 0 else 0.0

    def bags_usage_pct(self) -> float:
        """Percentage of trades via bags.fm."""
        total = self.bags_trades + self.jupiter_trades
        return (self.bags_trades / total * 100) if total > 0 else 0.0

    def total_trades(self) -> int:
        """Total successful trades."""
        return self.bags_trades + self.jupiter_trades

    def total_attempts(self) -> int:
        """Total trade attempts (including failures)."""
        return self.bags_trades + self.jupiter_trades + self.bags_failures + self.jupiter_failures

    def overall_success_rate(self) -> float:
        """Overall success rate across both DEXes."""
        total_attempts = self.total_attempts()
        total_success = self.bags_trades + self.jupiter_trades
        return (total_success / total_attempts) if total_attempts > 0 else 0.0

    def total_triggers(self) -> int:
        """Total TP/SL triggers."""
        return self.tp_triggers + self.sl_triggers + self.trailing_triggers

    def tp_trigger_rate(self) -> float:
        """Percentage of exits via take-profit."""
        total = self.total_triggers()
        return (self.tp_triggers / total * 100) if total > 0 else 0.0

    def sl_trigger_rate(self) -> float:
        """Percentage of exits via stop-loss."""
        total = self.total_triggers()
        return (self.sl_triggers / total * 100) if total > 0 else 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict with computed metrics."""
        return {
            # Raw counts
            "bags_trades": self.bags_trades,
            "jupiter_trades": self.jupiter_trades,
            "bags_failures": self.bags_failures,
            "jupiter_failures": self.jupiter_failures,
            "total_volume_sol": round(self.total_volume_sol, 4),
            "partner_fees_earned": round(self.partner_fees_earned, 6),
            "tp_triggers": self.tp_triggers,
            "sl_triggers": self.sl_triggers,
            "trailing_triggers": self.trailing_triggers,

            # Computed metrics
            "total_trades": self.total_trades(),
            "total_attempts": self.total_attempts(),
            "bags_usage_pct": round(self.bags_usage_pct(), 2),
            "bags_success_rate": round(self.bags_success_rate(), 4),
            "jupiter_success_rate": round(self.jupiter_success_rate(), 4),
            "overall_success_rate": round(self.overall_success_rate(), 4),
            "total_triggers": self.total_triggers(),
            "tp_trigger_rate": round(self.tp_trigger_rate(), 2),
            "sl_trigger_rate": round(self.sl_trigger_rate(), 2),
        }


# Singleton instance
_metrics = BagsMetrics()


def get_bags_metrics() -> BagsMetrics:
    """Get the global metrics instance."""
    return _metrics


def reset_metrics() -> None:
    """Reset all metrics to zero (for testing)."""
    global _metrics
    _metrics = BagsMetrics()


def log_trade(via: str, success: bool, volume_sol: float = 0, partner_fee: float = 0) -> None:
    """
    Log a trade execution.

    Args:
        via: "bags" or "jupiter"
        success: True if trade succeeded
        volume_sol: SOL amount traded
        partner_fee: Partner fee earned (SOL)
    """
    if via.lower() == "bags" or via.lower() == "bags_fm":
        if success:
            _metrics.bags_trades += 1
            _metrics.total_volume_sol += volume_sol
            _metrics.partner_fees_earned += partner_fee
            logger.info(f"Bags trade: +{volume_sol:.4f} SOL (fee: {partner_fee:.6f})")
        else:
            _metrics.bags_failures += 1
            logger.warning("Bags trade failed")
    elif via.lower() == "jupiter":
        if success:
            _metrics.jupiter_trades += 1
            _metrics.total_volume_sol += volume_sol
            logger.info(f"Jupiter trade: +{volume_sol:.4f} SOL")
        else:
            _metrics.jupiter_failures += 1
            logger.warning("Jupiter trade failed")
    else:
        logger.warning(f"Unknown DEX: {via}")


def log_exit_trigger(trigger_type: str) -> None:
    """
    Log a TP/SL/trailing trigger.

    Args:
        trigger_type: "take_profit", "stop_loss", or "trailing_stop"
    """
    if trigger_type == "take_profit":
        _metrics.tp_triggers += 1
        logger.info("TP triggered")
    elif trigger_type == "stop_loss":
        _metrics.sl_triggers += 1
        logger.info("SL triggered")
    elif trigger_type == "trailing_stop":
        _metrics.trailing_triggers += 1
        logger.info("Trailing stop triggered")
    else:
        logger.warning(f"Unknown trigger type: {trigger_type}")


def log_metrics_summary() -> None:
    """Log a summary of current metrics."""
    metrics_dict = _metrics.to_dict()
    logger.info("=== Bags.fm Metrics Summary ===")
    logger.info(f"Total trades: {metrics_dict['total_trades']} ({metrics_dict['total_attempts']} attempts)")
    logger.info(f"Bags usage: {metrics_dict['bags_usage_pct']:.1f}%")
    logger.info(f"Overall success rate: {metrics_dict['overall_success_rate']:.1%}")
    logger.info(f"Volume: {metrics_dict['total_volume_sol']:.2f} SOL")
    logger.info(f"Partner fees: {metrics_dict['partner_fees_earned']:.6f} SOL")
    logger.info(f"TP triggers: {metrics_dict['tp_triggers']} ({metrics_dict['tp_trigger_rate']:.1f}%)")
    logger.info(f"SL triggers: {metrics_dict['sl_triggers']} ({metrics_dict['sl_trigger_rate']:.1f}%)")
    logger.info("==============================")
