"""
Whale Pattern Analyzer

Detects accumulation/distribution patterns, smart money movements,
and generates trading signals from whale activity.

Prompts #109-112: Whale Watching
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any
from enum import Enum
from collections import defaultdict

from .tracker import (
    WhaleTracker,
    WhaleTransaction,
    WhaleWallet,
    TransactionType,
    get_whale_tracker
)

logger = logging.getLogger(__name__)


class PatternType(str, Enum):
    """Types of whale patterns"""
    ACCUMULATION = "accumulation"
    DISTRIBUTION = "distribution"
    TRANSFER_CLUSTER = "transfer_cluster"
    NEW_POSITION = "new_position"
    POSITION_EXIT = "position_exit"
    ROTATION = "rotation"  # Selling one token, buying another
    COORDINATED = "coordinated"  # Multiple whales same action


class SignalStrength(str, Enum):
    """Signal strength levels"""
    WEAK = "weak"
    MODERATE = "moderate"
    STRONG = "strong"
    VERY_STRONG = "very_strong"


@dataclass
class WhalePattern:
    """A detected whale activity pattern"""
    pattern_id: str
    pattern_type: PatternType
    token: str
    strength: SignalStrength
    confidence: float  # 0-1

    # Pattern details
    wallet_count: int = 0
    transaction_count: int = 0
    total_volume_usd: float = 0.0
    avg_price: float = 0.0
    price_impact_percent: float = 0.0

    # Time frame
    start_time: datetime = field(default_factory=datetime.now)
    end_time: datetime = field(default_factory=datetime.now)
    duration_hours: float = 0.0

    # Related wallets and transactions
    wallet_addresses: List[str] = field(default_factory=list)
    transaction_ids: List[str] = field(default_factory=list)

    # Interpretation
    interpretation: str = ""
    suggested_action: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "pattern_id": self.pattern_id,
            "pattern_type": self.pattern_type.value,
            "token": self.token,
            "strength": self.strength.value,
            "confidence": self.confidence,
            "wallet_count": self.wallet_count,
            "transaction_count": self.transaction_count,
            "total_volume_usd": self.total_volume_usd,
            "avg_price": self.avg_price,
            "price_impact_percent": self.price_impact_percent,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat(),
            "duration_hours": self.duration_hours,
            "wallet_addresses": self.wallet_addresses,
            "transaction_ids": self.transaction_ids,
            "interpretation": self.interpretation,
            "suggested_action": self.suggested_action
        }


@dataclass
class AccumulationSignal:
    """A trading signal derived from whale accumulation"""
    signal_id: str
    token: str
    direction: str  # "buy" or "sell"
    strength: SignalStrength
    confidence: float

    # Supporting data
    whale_buy_volume: float = 0.0
    whale_sell_volume: float = 0.0
    net_whale_flow: float = 0.0
    unique_whales_buying: int = 0
    unique_whales_selling: int = 0

    # Timing
    generated_at: datetime = field(default_factory=datetime.now)
    valid_until: datetime = field(default_factory=lambda: datetime.now() + timedelta(hours=4))

    # Price context
    current_price: float = 0.0
    avg_whale_entry: float = 0.0
    suggested_entry: float = 0.0
    suggested_stop_loss: float = 0.0
    suggested_take_profit: float = 0.0

    # Related patterns
    patterns: List[str] = field(default_factory=list)

    def is_valid(self) -> bool:
        """Check if signal is still valid"""
        return datetime.now() < self.valid_until

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "signal_id": self.signal_id,
            "token": self.token,
            "direction": self.direction,
            "strength": self.strength.value,
            "confidence": self.confidence,
            "whale_buy_volume": self.whale_buy_volume,
            "whale_sell_volume": self.whale_sell_volume,
            "net_whale_flow": self.net_whale_flow,
            "unique_whales_buying": self.unique_whales_buying,
            "unique_whales_selling": self.unique_whales_selling,
            "generated_at": self.generated_at.isoformat(),
            "valid_until": self.valid_until.isoformat(),
            "current_price": self.current_price,
            "avg_whale_entry": self.avg_whale_entry,
            "suggested_entry": self.suggested_entry,
            "suggested_stop_loss": self.suggested_stop_loss,
            "suggested_take_profit": self.suggested_take_profit,
            "patterns": self.patterns
        }


class WhaleAnalyzer:
    """
    Analyzes whale activity patterns

    Detects accumulation, distribution, and coordinated movements.
    Generates trading signals from whale activity.
    """

    def __init__(self, whale_tracker: Optional[WhaleTracker] = None):
        self.tracker = whale_tracker or get_whale_tracker()
        self.detected_patterns: List[WhalePattern] = []
        self.active_signals: Dict[str, AccumulationSignal] = {}

    async def analyze_token(
        self,
        token: str,
        lookback_hours: int = 24
    ) -> Dict[str, Any]:
        """
        Analyze whale activity for a specific token

        Returns analysis results with patterns and signals.
        """
        # Get recent transactions
        transactions = await self.tracker.get_recent_activity(
            token=token,
            hours=lookback_hours
        )

        if not transactions:
            return {
                "token": token,
                "analysis": "insufficient_data",
                "patterns": [],
                "signals": []
            }

        # Group by wallet
        by_wallet = defaultdict(list)
        for tx in transactions:
            by_wallet[tx.wallet_address].append(tx)

        # Calculate metrics
        total_buy_volume = sum(
            tx.amount_usd for tx in transactions
            if tx.tx_type == TransactionType.BUY
        )
        total_sell_volume = sum(
            tx.amount_usd for tx in transactions
            if tx.tx_type == TransactionType.SELL
        )
        net_flow = total_buy_volume - total_sell_volume

        unique_buyers = set(
            tx.wallet_address for tx in transactions
            if tx.tx_type == TransactionType.BUY
        )
        unique_sellers = set(
            tx.wallet_address for tx in transactions
            if tx.tx_type == TransactionType.SELL
        )

        # Detect patterns
        patterns = []

        # Check for accumulation pattern
        if net_flow > 0 and total_buy_volume > total_sell_volume * 1.5:
            pattern = await self._detect_accumulation(token, transactions, by_wallet)
            if pattern:
                patterns.append(pattern)

        # Check for distribution pattern
        if net_flow < 0 and total_sell_volume > total_buy_volume * 1.5:
            pattern = await self._detect_distribution(token, transactions, by_wallet)
            if pattern:
                patterns.append(pattern)

        # Check for coordinated activity
        coord_pattern = await self._detect_coordinated_activity(token, transactions, by_wallet)
        if coord_pattern:
            patterns.append(coord_pattern)

        # Generate signal if patterns detected
        signal = None
        if patterns:
            signal = await self._generate_signal(token, patterns, transactions)
            if signal:
                self.active_signals[signal.signal_id] = signal

        self.detected_patterns.extend(patterns)

        return {
            "token": token,
            "period_hours": lookback_hours,
            "total_buy_volume": total_buy_volume,
            "total_sell_volume": total_sell_volume,
            "net_whale_flow": net_flow,
            "unique_buyers": len(unique_buyers),
            "unique_sellers": len(unique_sellers),
            "transaction_count": len(transactions),
            "patterns": [p.to_dict() for p in patterns],
            "signal": signal.to_dict() if signal else None,
            "sentiment": self._calculate_sentiment(net_flow, total_buy_volume, total_sell_volume)
        }

    async def _detect_accumulation(
        self,
        token: str,
        transactions: List[WhaleTransaction],
        by_wallet: Dict[str, List[WhaleTransaction]]
    ) -> Optional[WhalePattern]:
        """Detect accumulation pattern"""
        buy_txs = [tx for tx in transactions if tx.tx_type == TransactionType.BUY]

        if len(buy_txs) < 3:
            return None

        total_volume = sum(tx.amount_usd for tx in buy_txs)
        wallet_count = len(set(tx.wallet_address for tx in buy_txs))

        # Calculate confidence based on factors
        confidence = 0.5

        # More wallets = higher confidence
        if wallet_count >= 5:
            confidence += 0.2
        elif wallet_count >= 3:
            confidence += 0.1

        # Higher volume = higher confidence
        if total_volume >= 1000000:
            confidence += 0.2
        elif total_volume >= 500000:
            confidence += 0.1

        # Determine strength
        if total_volume >= 1000000 and wallet_count >= 5:
            strength = SignalStrength.VERY_STRONG
        elif total_volume >= 500000 and wallet_count >= 3:
            strength = SignalStrength.STRONG
        elif total_volume >= 100000:
            strength = SignalStrength.MODERATE
        else:
            strength = SignalStrength.WEAK

        # Calculate average price
        total_amount = sum(tx.amount for tx in buy_txs)
        avg_price = total_volume / total_amount if total_amount > 0 else 0

        timestamps = [tx.timestamp for tx in buy_txs]

        return WhalePattern(
            pattern_id=f"ACC-{token}-{datetime.now().strftime('%Y%m%d%H%M')}",
            pattern_type=PatternType.ACCUMULATION,
            token=token,
            strength=strength,
            confidence=min(confidence, 0.95),
            wallet_count=wallet_count,
            transaction_count=len(buy_txs),
            total_volume_usd=total_volume,
            avg_price=avg_price,
            start_time=min(timestamps),
            end_time=max(timestamps),
            duration_hours=(max(timestamps) - min(timestamps)).total_seconds() / 3600,
            wallet_addresses=list(set(tx.wallet_address for tx in buy_txs))[:10],
            transaction_ids=[tx.tx_id for tx in buy_txs][:20],
            interpretation=f"Whales are accumulating {token}. {wallet_count} unique wallets bought ${total_volume:,.0f} worth.",
            suggested_action="Consider entering a long position with proper risk management"
        )

    async def _detect_distribution(
        self,
        token: str,
        transactions: List[WhaleTransaction],
        by_wallet: Dict[str, List[WhaleTransaction]]
    ) -> Optional[WhalePattern]:
        """Detect distribution pattern"""
        sell_txs = [tx for tx in transactions if tx.tx_type == TransactionType.SELL]

        if len(sell_txs) < 3:
            return None

        total_volume = sum(tx.amount_usd for tx in sell_txs)
        wallet_count = len(set(tx.wallet_address for tx in sell_txs))

        confidence = 0.5
        if wallet_count >= 5:
            confidence += 0.2
        if total_volume >= 1000000:
            confidence += 0.2

        if total_volume >= 1000000 and wallet_count >= 5:
            strength = SignalStrength.VERY_STRONG
        elif total_volume >= 500000:
            strength = SignalStrength.STRONG
        else:
            strength = SignalStrength.MODERATE

        timestamps = [tx.timestamp for tx in sell_txs]

        return WhalePattern(
            pattern_id=f"DIST-{token}-{datetime.now().strftime('%Y%m%d%H%M')}",
            pattern_type=PatternType.DISTRIBUTION,
            token=token,
            strength=strength,
            confidence=min(confidence, 0.95),
            wallet_count=wallet_count,
            transaction_count=len(sell_txs),
            total_volume_usd=total_volume,
            start_time=min(timestamps),
            end_time=max(timestamps),
            duration_hours=(max(timestamps) - min(timestamps)).total_seconds() / 3600,
            wallet_addresses=list(set(tx.wallet_address for tx in sell_txs))[:10],
            transaction_ids=[tx.tx_id for tx in sell_txs][:20],
            interpretation=f"Whales are distributing {token}. {wallet_count} unique wallets sold ${total_volume:,.0f} worth.",
            suggested_action="Consider taking profits or avoiding new long positions"
        )

    async def _detect_coordinated_activity(
        self,
        token: str,
        transactions: List[WhaleTransaction],
        by_wallet: Dict[str, List[WhaleTransaction]]
    ) -> Optional[WhalePattern]:
        """Detect coordinated whale activity (multiple whales acting together)"""
        # Group transactions by hour
        by_hour = defaultdict(list)
        for tx in transactions:
            hour_key = tx.timestamp.strftime("%Y%m%d%H")
            by_hour[hour_key].append(tx)

        # Look for hours with multiple whale transactions
        coordinated_hours = [
            (hour, txs) for hour, txs in by_hour.items()
            if len(set(tx.wallet_address for tx in txs)) >= 3
        ]

        if not coordinated_hours:
            return None

        # Find the most active coordinated period
        best_hour, best_txs = max(coordinated_hours, key=lambda x: len(x[1]))
        unique_wallets = set(tx.wallet_address for tx in best_txs)

        # Determine if coordinated buy or sell
        buy_count = sum(1 for tx in best_txs if tx.tx_type == TransactionType.BUY)
        sell_count = sum(1 for tx in best_txs if tx.tx_type == TransactionType.SELL)

        if buy_count > sell_count:
            direction = "buying"
        elif sell_count > buy_count:
            direction = "selling"
        else:
            direction = "mixed activity"

        return WhalePattern(
            pattern_id=f"COORD-{token}-{datetime.now().strftime('%Y%m%d%H%M')}",
            pattern_type=PatternType.COORDINATED,
            token=token,
            strength=SignalStrength.STRONG if len(unique_wallets) >= 5 else SignalStrength.MODERATE,
            confidence=0.7,
            wallet_count=len(unique_wallets),
            transaction_count=len(best_txs),
            total_volume_usd=sum(tx.amount_usd for tx in best_txs),
            wallet_addresses=list(unique_wallets)[:10],
            interpretation=f"Coordinated whale {direction} detected. {len(unique_wallets)} whales acted within the same hour.",
            suggested_action="Monitor closely - coordinated activity often precedes significant price moves"
        )

    async def _generate_signal(
        self,
        token: str,
        patterns: List[WhalePattern],
        transactions: List[WhaleTransaction]
    ) -> Optional[AccumulationSignal]:
        """Generate a trading signal from detected patterns"""
        # Determine direction from patterns
        accumulation_patterns = [p for p in patterns if p.pattern_type == PatternType.ACCUMULATION]
        distribution_patterns = [p for p in patterns if p.pattern_type == PatternType.DISTRIBUTION]

        if accumulation_patterns and not distribution_patterns:
            direction = "buy"
        elif distribution_patterns and not accumulation_patterns:
            direction = "sell"
        else:
            # Mixed signals, don't generate
            return None

        # Calculate metrics
        buy_volume = sum(tx.amount_usd for tx in transactions if tx.tx_type == TransactionType.BUY)
        sell_volume = sum(tx.amount_usd for tx in transactions if tx.tx_type == TransactionType.SELL)

        unique_buyers = len(set(tx.wallet_address for tx in transactions if tx.tx_type == TransactionType.BUY))
        unique_sellers = len(set(tx.wallet_address for tx in transactions if tx.tx_type == TransactionType.SELL))

        # Calculate average whale entry price
        buy_txs = [tx for tx in transactions if tx.tx_type == TransactionType.BUY]
        if buy_txs:
            total_amount = sum(tx.amount for tx in buy_txs)
            avg_entry = buy_volume / total_amount if total_amount > 0 else 0
        else:
            avg_entry = 0

        # Determine strength
        strongest_pattern = max(patterns, key=lambda p: ["weak", "moderate", "strong", "very_strong"].index(p.strength.value))
        strength = strongest_pattern.strength

        # Calculate confidence
        confidence = sum(p.confidence for p in patterns) / len(patterns)

        return AccumulationSignal(
            signal_id=f"SIG-{token}-{datetime.now().strftime('%Y%m%d%H%M%S')}",
            token=token,
            direction=direction,
            strength=strength,
            confidence=confidence,
            whale_buy_volume=buy_volume,
            whale_sell_volume=sell_volume,
            net_whale_flow=buy_volume - sell_volume,
            unique_whales_buying=unique_buyers,
            unique_whales_selling=unique_sellers,
            avg_whale_entry=avg_entry,
            patterns=[p.pattern_id for p in patterns]
        )

    def _calculate_sentiment(
        self,
        net_flow: float,
        buy_volume: float,
        sell_volume: float
    ) -> str:
        """Calculate overall sentiment from whale activity"""
        if buy_volume == 0 and sell_volume == 0:
            return "neutral"

        ratio = buy_volume / (sell_volume + 0.01)

        if ratio >= 2.0:
            return "very_bullish"
        elif ratio >= 1.3:
            return "bullish"
        elif ratio <= 0.5:
            return "very_bearish"
        elif ratio <= 0.77:
            return "bearish"
        else:
            return "neutral"

    async def get_active_signals(self) -> List[AccumulationSignal]:
        """Get all currently valid signals"""
        # Clean up expired signals
        self.active_signals = {
            sid: sig for sid, sig in self.active_signals.items()
            if sig.is_valid()
        }

        return list(self.active_signals.values())

    async def get_smart_money_flow(
        self,
        hours: int = 24
    ) -> Dict[str, Dict[str, float]]:
        """Get smart money flow across all tokens"""
        transactions = await self.tracker.get_recent_activity(hours=hours)

        by_token = defaultdict(lambda: {"buy": 0.0, "sell": 0.0})

        for tx in transactions:
            if tx.tx_type == TransactionType.BUY:
                by_token[tx.token]["buy"] += tx.amount_usd
            elif tx.tx_type == TransactionType.SELL:
                by_token[tx.token]["sell"] += tx.amount_usd

        # Calculate net flow for each token
        result = {}
        for token, volumes in by_token.items():
            result[token] = {
                "buy_volume": volumes["buy"],
                "sell_volume": volumes["sell"],
                "net_flow": volumes["buy"] - volumes["sell"],
                "flow_ratio": volumes["buy"] / (volumes["sell"] + 0.01)
            }

        return result


# Testing
if __name__ == "__main__":
    async def test():
        analyzer = WhaleAnalyzer()

        # Would need real transaction data
        result = await analyzer.analyze_token("SOL", lookback_hours=24)
        print(f"Analysis for SOL: {result}")

        # Get smart money flow
        flow = await analyzer.get_smart_money_flow(hours=24)
        print(f"\nSmart money flow: {flow}")

    asyncio.run(test())
