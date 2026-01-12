"""
Analytics Module - Prediction tracking, portfolio analytics, and performance metrics.
"""

import logging
import json
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone, timedelta
from pathlib import Path
from collections import defaultdict
import statistics

logger = logging.getLogger(__name__)


# === PREDICTION ACCURACY TRACKER ===

@dataclass
class Prediction:
    """A prediction record."""
    id: str
    timestamp: str
    token_symbol: str
    token_mint: str
    prediction_type: str  # BULLISH, BEARISH, NEUTRAL
    confidence: float
    price_at_prediction: float
    target_price: Optional[float] = None
    stop_loss: Optional[float] = None
    timeframe_hours: int = 24
    outcome: str = "PENDING"  # PENDING, WIN, LOSS, EXPIRED
    outcome_price: Optional[float] = None
    outcome_timestamp: Optional[str] = None
    pnl_percent: float = 0.0
    source: str = "grok"  # grok, sentiment, manual


class PredictionTracker:
    """
    Track prediction accuracy over time.

    Usage:
        tracker = PredictionTracker()

        # Record a prediction
        pred_id = tracker.record_prediction(
            token_symbol="$BONK",
            token_mint="DezX...",
            prediction_type="BULLISH",
            confidence=0.85,
            price_at_prediction=0.00001234,
            target_price=0.00001500,
            stop_loss=0.00001000
        )

        # Later, update outcome
        tracker.update_outcome(pred_id, current_price=0.00001600)

        # Get accuracy stats
        stats = tracker.get_accuracy_stats(days=7)
    """

    def __init__(self, storage_path: Optional[Path] = None):
        self.storage_path = storage_path or Path(__file__).parent.parent / "data" / "predictions.json"
        self.predictions: Dict[str, Prediction] = {}
        self._load()

    def _load(self):
        """Load predictions from storage."""
        if self.storage_path.exists():
            try:
                with open(self.storage_path) as f:
                    data = json.load(f)
                    for pred_data in data.get("predictions", []):
                        pred = Prediction(**pred_data)
                        self.predictions[pred.id] = pred
                logger.info(f"Loaded {len(self.predictions)} predictions")
            except Exception as e:
                logger.error(f"Failed to load predictions: {e}")

    def _save(self):
        """Save predictions to storage."""
        try:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "predictions": [asdict(p) for p in self.predictions.values()],
                "last_updated": datetime.now(timezone.utc).isoformat()
            }
            with open(self.storage_path, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save predictions: {e}")

    def record_prediction(
        self,
        token_symbol: str,
        token_mint: str,
        prediction_type: str,
        confidence: float,
        price_at_prediction: float,
        target_price: Optional[float] = None,
        stop_loss: Optional[float] = None,
        timeframe_hours: int = 24,
        source: str = "grok"
    ) -> str:
        """Record a new prediction. Returns prediction ID."""
        import uuid

        pred_id = str(uuid.uuid4())[:8]

        pred = Prediction(
            id=pred_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            token_symbol=token_symbol,
            token_mint=token_mint,
            prediction_type=prediction_type.upper(),
            confidence=confidence,
            price_at_prediction=price_at_prediction,
            target_price=target_price,
            stop_loss=stop_loss,
            timeframe_hours=timeframe_hours,
            source=source
        )

        self.predictions[pred_id] = pred
        self._save()

        logger.info(f"Recorded prediction {pred_id}: {token_symbol} {prediction_type}")
        return pred_id

    def update_outcome(self, pred_id: str, current_price: float) -> Optional[str]:
        """
        Update prediction outcome based on current price.
        Returns outcome (WIN, LOSS, PENDING) or None if not found.
        """
        if pred_id not in self.predictions:
            return None

        pred = self.predictions[pred_id]

        if pred.outcome != "PENDING":
            return pred.outcome

        # Calculate PnL
        if pred.price_at_prediction > 0:
            pnl = ((current_price - pred.price_at_prediction) / pred.price_at_prediction) * 100
        else:
            pnl = 0

        # For bearish predictions, invert the PnL
        if pred.prediction_type == "BEARISH":
            pnl = -pnl

        pred.pnl_percent = pnl
        pred.outcome_price = current_price
        pred.outcome_timestamp = datetime.now(timezone.utc).isoformat()

        # Determine outcome
        if pred.prediction_type == "BULLISH":
            if pred.target_price and current_price >= pred.target_price:
                pred.outcome = "WIN"
            elif pred.stop_loss and current_price <= pred.stop_loss:
                pred.outcome = "LOSS"
            elif pnl > 0:
                pred.outcome = "WIN"
            else:
                pred.outcome = "LOSS"

        elif pred.prediction_type == "BEARISH":
            if pred.target_price and current_price <= pred.target_price:
                pred.outcome = "WIN"
            elif pred.stop_loss and current_price >= pred.stop_loss:
                pred.outcome = "LOSS"
            elif pnl > 0:
                pred.outcome = "WIN"
            else:
                pred.outcome = "LOSS"

        else:  # NEUTRAL
            pred.outcome = "WIN" if abs(pnl) < 5 else "LOSS"

        self._save()
        logger.info(f"Updated prediction {pred_id}: {pred.outcome} ({pred.pnl_percent:.2f}%)")
        return pred.outcome

    def check_expired_predictions(self):
        """Mark expired predictions as EXPIRED."""
        now = datetime.now(timezone.utc)

        for pred in self.predictions.values():
            if pred.outcome != "PENDING":
                continue

            pred_time = datetime.fromisoformat(pred.timestamp.replace('Z', '+00:00'))
            expiry = pred_time + timedelta(hours=pred.timeframe_hours)

            if now > expiry:
                pred.outcome = "EXPIRED"
                pred.outcome_timestamp = now.isoformat()
                logger.info(f"Prediction {pred.id} expired")

        self._save()

    def get_pending_predictions(self) -> List[Prediction]:
        """Get all pending predictions."""
        return [p for p in self.predictions.values() if p.outcome == "PENDING"]

    def get_accuracy_stats(self, days: int = 7) -> Dict[str, Any]:
        """Get prediction accuracy statistics."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

        recent = [
            p for p in self.predictions.values()
            if datetime.fromisoformat(p.timestamp.replace('Z', '+00:00')) > cutoff
            and p.outcome != "PENDING"
        ]

        if not recent:
            return {
                "period_days": days,
                "total_predictions": 0,
                "wins": 0,
                "losses": 0,
                "expired": 0,
                "accuracy_percent": 0,
                "avg_pnl_percent": 0,
                "by_type": {},
                "by_source": {}
            }

        wins = sum(1 for p in recent if p.outcome == "WIN")
        losses = sum(1 for p in recent if p.outcome == "LOSS")
        expired = sum(1 for p in recent if p.outcome == "EXPIRED")
        total = len(recent)

        # By prediction type
        by_type = defaultdict(lambda: {"total": 0, "wins": 0, "pnl": []})
        for p in recent:
            by_type[p.prediction_type]["total"] += 1
            if p.outcome == "WIN":
                by_type[p.prediction_type]["wins"] += 1
            by_type[p.prediction_type]["pnl"].append(p.pnl_percent)

        type_stats = {}
        for ptype, data in by_type.items():
            type_stats[ptype] = {
                "total": data["total"],
                "wins": data["wins"],
                "accuracy": (data["wins"] / data["total"] * 100) if data["total"] > 0 else 0,
                "avg_pnl": statistics.mean(data["pnl"]) if data["pnl"] else 0
            }

        # By source
        by_source = defaultdict(lambda: {"total": 0, "wins": 0})
        for p in recent:
            by_source[p.source]["total"] += 1
            if p.outcome == "WIN":
                by_source[p.source]["wins"] += 1

        source_stats = {
            source: {
                "total": data["total"],
                "wins": data["wins"],
                "accuracy": (data["wins"] / data["total"] * 100) if data["total"] > 0 else 0
            }
            for source, data in by_source.items()
        }

        return {
            "period_days": days,
            "total_predictions": total,
            "wins": wins,
            "losses": losses,
            "expired": expired,
            "accuracy_percent": (wins / (wins + losses) * 100) if (wins + losses) > 0 else 0,
            "avg_pnl_percent": statistics.mean([p.pnl_percent for p in recent]) if recent else 0,
            "by_type": type_stats,
            "by_source": source_stats
        }


# === PORTFOLIO ANALYTICS ===

@dataclass
class Trade:
    """A trade record."""
    id: str
    timestamp: str
    token_symbol: str
    token_mint: str
    side: str  # BUY, SELL
    amount: float
    price: float
    value_usd: float
    fee_usd: float = 0.0
    tx_signature: str = ""


@dataclass
class Position:
    """A portfolio position."""
    token_symbol: str
    token_mint: str
    amount: float
    avg_entry_price: float
    current_price: float = 0.0
    value_usd: float = 0.0
    unrealized_pnl: float = 0.0
    unrealized_pnl_percent: float = 0.0


class PortfolioAnalytics:
    """
    Portfolio analytics and performance tracking.

    Usage:
        analytics = PortfolioAnalytics()

        # Record trades
        analytics.record_trade("BUY", "$SOL", "So11...", 10.0, 150.0)
        analytics.record_trade("SELL", "$SOL", "So11...", 5.0, 160.0)

        # Get metrics
        performance = analytics.get_performance(days=30)
        positions = analytics.get_positions()
    """

    def __init__(self, storage_path: Optional[Path] = None):
        self.storage_path = storage_path or Path(__file__).parent.parent / "data" / "trades.json"
        self.trades: List[Trade] = []
        self._load()

    def _load(self):
        """Load trades from storage."""
        if self.storage_path.exists():
            try:
                with open(self.storage_path) as f:
                    data = json.load(f)
                    self.trades = [Trade(**t) for t in data.get("trades", [])]
                logger.info(f"Loaded {len(self.trades)} trades")
            except Exception as e:
                logger.error(f"Failed to load trades: {e}")

    def _save(self):
        """Save trades to storage."""
        try:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "trades": [asdict(t) for t in self.trades],
                "last_updated": datetime.now(timezone.utc).isoformat()
            }
            with open(self.storage_path, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save trades: {e}")

    def record_trade(
        self,
        side: str,
        token_symbol: str,
        token_mint: str,
        amount: float,
        price: float,
        fee_usd: float = 0.0,
        tx_signature: str = ""
    ) -> str:
        """Record a trade. Returns trade ID."""
        import uuid

        trade_id = str(uuid.uuid4())[:8]

        trade = Trade(
            id=trade_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            token_symbol=token_symbol,
            token_mint=token_mint,
            side=side.upper(),
            amount=amount,
            price=price,
            value_usd=amount * price,
            fee_usd=fee_usd,
            tx_signature=tx_signature
        )

        self.trades.append(trade)
        self._save()

        logger.info(f"Recorded trade {trade_id}: {side} {amount} {token_symbol} @ {price}")
        return trade_id

    def get_positions(self, current_prices: Dict[str, float] = None) -> List[Position]:
        """Calculate current positions from trade history."""
        current_prices = current_prices or {}
        positions: Dict[str, Position] = {}

        for trade in self.trades:
            mint = trade.token_mint

            if mint not in positions:
                positions[mint] = Position(
                    token_symbol=trade.token_symbol,
                    token_mint=mint,
                    amount=0,
                    avg_entry_price=0
                )

            pos = positions[mint]

            if trade.side == "BUY":
                # Update average entry price
                total_value = pos.amount * pos.avg_entry_price + trade.amount * trade.price
                pos.amount += trade.amount
                pos.avg_entry_price = total_value / pos.amount if pos.amount > 0 else 0
            else:  # SELL
                pos.amount -= trade.amount

        # Calculate unrealized PnL
        result = []
        for mint, pos in positions.items():
            if pos.amount <= 0:
                continue

            current_price = current_prices.get(mint, pos.avg_entry_price)
            pos.current_price = current_price
            pos.value_usd = pos.amount * current_price
            pos.unrealized_pnl = pos.value_usd - (pos.amount * pos.avg_entry_price)
            pos.unrealized_pnl_percent = (
                (current_price - pos.avg_entry_price) / pos.avg_entry_price * 100
                if pos.avg_entry_price > 0 else 0
            )
            result.append(pos)

        return result

    def get_performance(self, days: int = 30) -> Dict[str, Any]:
        """Get portfolio performance metrics."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

        recent_trades = [
            t for t in self.trades
            if datetime.fromisoformat(t.timestamp.replace('Z', '+00:00')) > cutoff
        ]

        if not recent_trades:
            return {
                "period_days": days,
                "total_trades": 0,
                "buy_trades": 0,
                "sell_trades": 0,
                "total_volume_usd": 0,
                "total_fees_usd": 0,
                "realized_pnl_usd": 0,
                "win_rate": 0
            }

        buys = [t for t in recent_trades if t.side == "BUY"]
        sells = [t for t in recent_trades if t.side == "SELL"]

        total_volume = sum(t.value_usd for t in recent_trades)
        total_fees = sum(t.fee_usd for t in recent_trades)

        # Calculate realized PnL (simplified - assumes FIFO)
        realized_pnl = 0
        buy_history: Dict[str, List[Trade]] = defaultdict(list)

        for trade in sorted(recent_trades, key=lambda t: t.timestamp):
            if trade.side == "BUY":
                buy_history[trade.token_mint].append(trade)
            elif trade.side == "SELL":
                mint_buys = buy_history.get(trade.token_mint, [])
                remaining = trade.amount

                while remaining > 0 and mint_buys:
                    buy = mint_buys[0]
                    matched = min(remaining, buy.amount)
                    realized_pnl += matched * (trade.price - buy.price)
                    remaining -= matched
                    buy.amount -= matched

                    if buy.amount <= 0:
                        mint_buys.pop(0)

        return {
            "period_days": days,
            "total_trades": len(recent_trades),
            "buy_trades": len(buys),
            "sell_trades": len(sells),
            "total_volume_usd": total_volume,
            "total_fees_usd": total_fees,
            "realized_pnl_usd": realized_pnl,
            "avg_trade_size_usd": total_volume / len(recent_trades) if recent_trades else 0
        }

    def export_trades_csv(self, path: Path = None) -> Path:
        """Export trades to CSV."""
        import csv

        path = path or self.storage_path.with_suffix(".csv")

        with open(path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                "ID", "Timestamp", "Symbol", "Mint", "Side",
                "Amount", "Price", "Value USD", "Fee USD", "TX Signature"
            ])

            for trade in self.trades:
                writer.writerow([
                    trade.id, trade.timestamp, trade.token_symbol, trade.token_mint,
                    trade.side, trade.amount, trade.price, trade.value_usd,
                    trade.fee_usd, trade.tx_signature
                ])

        logger.info(f"Exported {len(self.trades)} trades to {path}")
        return path


# === SINGLETON INSTANCES ===

_prediction_tracker: Optional[PredictionTracker] = None
_portfolio_analytics: Optional[PortfolioAnalytics] = None


def get_prediction_tracker() -> PredictionTracker:
    """Get singleton prediction tracker."""
    global _prediction_tracker
    if _prediction_tracker is None:
        _prediction_tracker = PredictionTracker()
    return _prediction_tracker


def get_portfolio_analytics() -> PortfolioAnalytics:
    """Get singleton portfolio analytics."""
    global _portfolio_analytics
    if _portfolio_analytics is None:
        _portfolio_analytics = PortfolioAnalytics()
    return _portfolio_analytics
