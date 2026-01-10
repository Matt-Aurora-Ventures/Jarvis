"""
Trading Journal

Track and analyze trading decisions with notes, emotions, and lessons.

Prompts #114: Trading Journal
"""

import asyncio
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
import json

logger = logging.getLogger(__name__)


class TradeEmotion(str, Enum):
    """Emotional state during trade"""
    CONFIDENT = "confident"
    FEARFUL = "fearful"
    GREEDY = "greedy"
    FOMO = "fomo"          # Fear of missing out
    CALM = "calm"
    ANXIOUS = "anxious"
    EXCITED = "excited"
    FRUSTRATED = "frustrated"
    NEUTRAL = "neutral"


class TradeReason(str, Enum):
    """Reason for taking trade"""
    TECHNICAL = "technical"
    FUNDAMENTAL = "fundamental"
    SIGNAL = "signal"
    WHALE_FOLLOW = "whale_follow"
    COPY_TRADE = "copy_trade"
    NEWS = "news"
    SENTIMENT = "sentiment"
    GUT_FEELING = "gut_feeling"
    STRATEGY = "strategy"
    OTHER = "other"


class TradeMistake(str, Enum):
    """Common trading mistakes"""
    FOMO_ENTRY = "fomo_entry"
    NO_STOP_LOSS = "no_stop_loss"
    MOVED_STOP_LOSS = "moved_stop_loss"
    REVENGE_TRADE = "revenge_trade"
    OVERSIZED_POSITION = "oversized_position"
    EARLY_EXIT = "early_exit"
    LATE_EXIT = "late_exit"
    IGNORED_SIGNAL = "ignored_signal"
    CHASED_PRICE = "chased_price"
    NO_PLAN = "no_plan"
    NONE = "none"


@dataclass
class TradeSetup:
    """Trade setup analysis"""
    entry_reason: TradeReason
    entry_trigger: str              # What triggered the entry
    support_level: Optional[float] = None
    resistance_level: Optional[float] = None
    target_price: Optional[float] = None
    stop_loss_price: Optional[float] = None
    risk_reward_ratio: Optional[float] = None
    confidence_level: int = 50      # 0-100
    market_condition: str = ""      # Bull/Bear/Ranging
    notes: str = ""


@dataclass
class JournalEntry:
    """A trading journal entry"""
    entry_id: str
    user_id: str
    tx_hash: Optional[str] = None   # Link to transaction

    # Trade details
    token: str = ""
    direction: str = "long"         # long/short
    entry_price: float = 0.0
    exit_price: Optional[float] = None
    position_size: float = 0.0
    pnl: float = 0.0
    pnl_percent: float = 0.0

    # Timestamps
    entry_time: datetime = field(default_factory=datetime.utcnow)
    exit_time: Optional[datetime] = None

    # Analysis
    setup: Optional[TradeSetup] = None
    emotion_before: TradeEmotion = TradeEmotion.NEUTRAL
    emotion_during: TradeEmotion = TradeEmotion.NEUTRAL
    emotion_after: TradeEmotion = TradeEmotion.NEUTRAL

    # Reflection
    what_went_well: str = ""
    what_went_wrong: str = ""
    lessons_learned: str = ""
    mistakes: List[TradeMistake] = field(default_factory=list)
    would_take_again: bool = True
    follow_up_actions: str = ""

    # Notes
    pre_trade_notes: str = ""
    during_trade_notes: str = ""
    post_trade_notes: str = ""

    # Tags
    tags: List[str] = field(default_factory=list)
    screenshot_urls: List[str] = field(default_factory=list)

    # Meta
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    @property
    def is_winner(self) -> bool:
        return self.pnl > 0

    @property
    def is_complete(self) -> bool:
        return self.exit_time is not None

    @property
    def holding_period(self) -> Optional[timedelta]:
        if not self.exit_time:
            return None
        return self.exit_time - self.entry_time

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entry_id": self.entry_id,
            "token": self.token,
            "direction": self.direction,
            "entry_price": self.entry_price,
            "exit_price": self.exit_price,
            "position_size": self.position_size,
            "pnl": self.pnl,
            "pnl_percent": self.pnl_percent,
            "entry_time": self.entry_time.isoformat(),
            "exit_time": self.exit_time.isoformat() if self.exit_time else None,
            "setup": {
                "entry_reason": self.setup.entry_reason.value,
                "entry_trigger": self.setup.entry_trigger,
                "target_price": self.setup.target_price,
                "stop_loss_price": self.setup.stop_loss_price,
                "confidence_level": self.setup.confidence_level
            } if self.setup else None,
            "emotions": {
                "before": self.emotion_before.value,
                "during": self.emotion_during.value,
                "after": self.emotion_after.value
            },
            "reflection": {
                "what_went_well": self.what_went_well,
                "what_went_wrong": self.what_went_wrong,
                "lessons_learned": self.lessons_learned,
                "mistakes": [m.value for m in self.mistakes],
                "would_take_again": self.would_take_again
            },
            "tags": self.tags,
            "is_winner": self.is_winner,
            "is_complete": self.is_complete
        }


@dataclass
class JournalStats:
    """Trading journal statistics"""
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float = 0.0
    total_pnl: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    profit_factor: float = 0.0
    largest_win: float = 0.0
    largest_loss: float = 0.0
    avg_holding_period_hours: float = 0.0

    # Emotional analysis
    most_profitable_emotion: str = ""
    least_profitable_emotion: str = ""
    emotion_win_rates: Dict[str, float] = field(default_factory=dict)

    # Mistake analysis
    most_common_mistakes: List[Tuple[str, int]] = field(default_factory=list)
    mistake_cost: Dict[str, float] = field(default_factory=dict)

    # Reason analysis
    best_performing_reason: str = ""
    reason_win_rates: Dict[str, float] = field(default_factory=dict)


class TradingJournal:
    """
    Trading journal for tracking and analyzing trades.

    Features:
    - Trade logging with setup analysis
    - Emotional tracking
    - Mistake identification
    - Performance analytics
    - Pattern recognition
    """

    def __init__(self, storage_path: str = "data/trading_journal.json"):
        self.storage_path = storage_path
        self._entries: Dict[str, JournalEntry] = {}
        self._user_entries: Dict[str, List[str]] = {}  # user_id -> entry_ids
        self._load()

    def _load(self):
        """Load journal from storage"""
        try:
            if os.path.exists(self.storage_path):
                with open(self.storage_path, "r") as f:
                    data = json.load(f)

                for item in data.get("entries", []):
                    setup = None
                    if item.get("setup"):
                        s = item["setup"]
                        setup = TradeSetup(
                            entry_reason=TradeReason(s.get("entry_reason", "other")),
                            entry_trigger=s.get("entry_trigger", ""),
                            target_price=s.get("target_price"),
                            stop_loss_price=s.get("stop_loss_price"),
                            confidence_level=s.get("confidence_level", 50)
                        )

                    entry = JournalEntry(
                        entry_id=item["entry_id"],
                        user_id=item["user_id"],
                        tx_hash=item.get("tx_hash"),
                        token=item.get("token", ""),
                        direction=item.get("direction", "long"),
                        entry_price=item.get("entry_price", 0),
                        exit_price=item.get("exit_price"),
                        position_size=item.get("position_size", 0),
                        pnl=item.get("pnl", 0),
                        pnl_percent=item.get("pnl_percent", 0),
                        entry_time=datetime.fromisoformat(item["entry_time"]),
                        exit_time=(
                            datetime.fromisoformat(item["exit_time"])
                            if item.get("exit_time") else None
                        ),
                        setup=setup,
                        emotion_before=TradeEmotion(
                            item.get("emotion_before", "neutral")
                        ),
                        emotion_during=TradeEmotion(
                            item.get("emotion_during", "neutral")
                        ),
                        emotion_after=TradeEmotion(
                            item.get("emotion_after", "neutral")
                        ),
                        what_went_well=item.get("what_went_well", ""),
                        what_went_wrong=item.get("what_went_wrong", ""),
                        lessons_learned=item.get("lessons_learned", ""),
                        mistakes=[
                            TradeMistake(m) for m in item.get("mistakes", [])
                        ],
                        tags=item.get("tags", []),
                        created_at=datetime.fromisoformat(item["created_at"])
                    )

                    self._entries[entry.entry_id] = entry

                    if entry.user_id not in self._user_entries:
                        self._user_entries[entry.user_id] = []
                    self._user_entries[entry.user_id].append(entry.entry_id)

        except Exception as e:
            logger.error(f"Failed to load journal: {e}")

    def _save(self):
        """Save journal to storage"""
        try:
            os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)
            entries = []

            for entry in self._entries.values():
                item = {
                    "entry_id": entry.entry_id,
                    "user_id": entry.user_id,
                    "tx_hash": entry.tx_hash,
                    "token": entry.token,
                    "direction": entry.direction,
                    "entry_price": entry.entry_price,
                    "exit_price": entry.exit_price,
                    "position_size": entry.position_size,
                    "pnl": entry.pnl,
                    "pnl_percent": entry.pnl_percent,
                    "entry_time": entry.entry_time.isoformat(),
                    "exit_time": (
                        entry.exit_time.isoformat() if entry.exit_time else None
                    ),
                    "emotion_before": entry.emotion_before.value,
                    "emotion_during": entry.emotion_during.value,
                    "emotion_after": entry.emotion_after.value,
                    "what_went_well": entry.what_went_well,
                    "what_went_wrong": entry.what_went_wrong,
                    "lessons_learned": entry.lessons_learned,
                    "mistakes": [m.value for m in entry.mistakes],
                    "tags": entry.tags,
                    "created_at": entry.created_at.isoformat()
                }

                if entry.setup:
                    item["setup"] = {
                        "entry_reason": entry.setup.entry_reason.value,
                        "entry_trigger": entry.setup.entry_trigger,
                        "target_price": entry.setup.target_price,
                        "stop_loss_price": entry.setup.stop_loss_price,
                        "confidence_level": entry.setup.confidence_level
                    }

                entries.append(item)

            with open(self.storage_path, "w") as f:
                json.dump({"entries": entries}, f, indent=2)

        except Exception as e:
            logger.error(f"Failed to save journal: {e}")

    # =========================================================================
    # ENTRY MANAGEMENT
    # =========================================================================

    async def create_entry(
        self,
        user_id: str,
        token: str,
        direction: str,
        entry_price: float,
        position_size: float,
        setup: Optional[TradeSetup] = None,
        emotion_before: TradeEmotion = TradeEmotion.NEUTRAL,
        pre_trade_notes: str = "",
        tx_hash: Optional[str] = None,
        tags: Optional[List[str]] = None
    ) -> JournalEntry:
        """Create a new journal entry"""
        import secrets

        entry_id = f"je_{secrets.token_hex(8)}"

        entry = JournalEntry(
            entry_id=entry_id,
            user_id=user_id,
            tx_hash=tx_hash,
            token=token,
            direction=direction,
            entry_price=entry_price,
            position_size=position_size,
            setup=setup,
            emotion_before=emotion_before,
            pre_trade_notes=pre_trade_notes,
            tags=tags or []
        )

        self._entries[entry_id] = entry

        if user_id not in self._user_entries:
            self._user_entries[user_id] = []
        self._user_entries[user_id].append(entry_id)

        self._save()

        logger.info(f"Created journal entry {entry_id} for {token}")
        return entry

    async def close_entry(
        self,
        entry_id: str,
        exit_price: float,
        exit_time: Optional[datetime] = None,
        emotion_during: TradeEmotion = TradeEmotion.NEUTRAL,
        emotion_after: TradeEmotion = TradeEmotion.NEUTRAL,
        during_trade_notes: str = "",
        post_trade_notes: str = ""
    ) -> Optional[JournalEntry]:
        """Close a journal entry with exit details"""
        entry = self._entries.get(entry_id)
        if not entry:
            return None

        entry.exit_price = exit_price
        entry.exit_time = exit_time or datetime.utcnow()
        entry.emotion_during = emotion_during
        entry.emotion_after = emotion_after
        entry.during_trade_notes = during_trade_notes
        entry.post_trade_notes = post_trade_notes
        entry.updated_at = datetime.utcnow()

        # Calculate P&L
        if entry.direction == "long":
            entry.pnl = (exit_price - entry.entry_price) * entry.position_size
            entry.pnl_percent = (
                (exit_price - entry.entry_price) / entry.entry_price * 100
            )
        else:
            entry.pnl = (entry.entry_price - exit_price) * entry.position_size
            entry.pnl_percent = (
                (entry.entry_price - exit_price) / entry.entry_price * 100
            )

        self._save()

        logger.info(
            f"Closed journal entry {entry_id}: "
            f"P&L ${entry.pnl:,.2f} ({entry.pnl_percent:.1f}%)"
        )
        return entry

    async def add_reflection(
        self,
        entry_id: str,
        what_went_well: str = "",
        what_went_wrong: str = "",
        lessons_learned: str = "",
        mistakes: Optional[List[TradeMistake]] = None,
        would_take_again: bool = True,
        follow_up_actions: str = ""
    ) -> Optional[JournalEntry]:
        """Add post-trade reflection"""
        entry = self._entries.get(entry_id)
        if not entry:
            return None

        entry.what_went_well = what_went_well
        entry.what_went_wrong = what_went_wrong
        entry.lessons_learned = lessons_learned
        entry.mistakes = mistakes or []
        entry.would_take_again = would_take_again
        entry.follow_up_actions = follow_up_actions
        entry.updated_at = datetime.utcnow()

        self._save()
        return entry

    async def get_entry(self, entry_id: str) -> Optional[JournalEntry]:
        """Get a journal entry"""
        return self._entries.get(entry_id)

    async def get_user_entries(
        self,
        user_id: str,
        limit: int = 100,
        offset: int = 0,
        token: Optional[str] = None,
        winners_only: bool = False,
        losers_only: bool = False
    ) -> List[JournalEntry]:
        """Get entries for a user with filters"""
        entry_ids = self._user_entries.get(user_id, [])
        entries = [self._entries[eid] for eid in entry_ids if eid in self._entries]

        # Apply filters
        if token:
            entries = [e for e in entries if e.token == token]
        if winners_only:
            entries = [e for e in entries if e.is_winner and e.is_complete]
        if losers_only:
            entries = [e for e in entries if not e.is_winner and e.is_complete]

        # Sort by entry time
        entries.sort(key=lambda e: e.entry_time, reverse=True)

        return entries[offset:offset + limit]

    async def delete_entry(self, entry_id: str):
        """Delete a journal entry"""
        entry = self._entries.pop(entry_id, None)
        if entry and entry.user_id in self._user_entries:
            self._user_entries[entry.user_id] = [
                eid for eid in self._user_entries[entry.user_id]
                if eid != entry_id
            ]
        self._save()

    # =========================================================================
    # ANALYTICS
    # =========================================================================

    async def get_stats(
        self,
        user_id: str,
        days: int = 30
    ) -> JournalStats:
        """Get trading statistics"""
        cutoff = datetime.utcnow() - timedelta(days=days)
        entries = await self.get_user_entries(user_id, limit=10000)
        entries = [e for e in entries if e.is_complete and e.entry_time >= cutoff]

        if not entries:
            return JournalStats()

        stats = JournalStats(total_trades=len(entries))

        # Win/Loss
        winners = [e for e in entries if e.is_winner]
        losers = [e for e in entries if not e.is_winner]

        stats.winning_trades = len(winners)
        stats.losing_trades = len(losers)
        stats.win_rate = len(winners) / len(entries) * 100 if entries else 0

        # P&L
        stats.total_pnl = sum(e.pnl for e in entries)
        stats.avg_win = (
            sum(e.pnl for e in winners) / len(winners) if winners else 0
        )
        stats.avg_loss = (
            sum(e.pnl for e in losers) / len(losers) if losers else 0
        )

        gross_profit = sum(e.pnl for e in winners)
        gross_loss = abs(sum(e.pnl for e in losers))
        stats.profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0

        if winners:
            stats.largest_win = max(e.pnl for e in winners)
        if losers:
            stats.largest_loss = min(e.pnl for e in losers)

        # Holding period
        periods = [
            e.holding_period.total_seconds() / 3600
            for e in entries if e.holding_period
        ]
        stats.avg_holding_period_hours = sum(periods) / len(periods) if periods else 0

        # Emotion analysis
        emotion_pnl: Dict[str, List[float]] = {}
        for entry in entries:
            emotion = entry.emotion_before.value
            if emotion not in emotion_pnl:
                emotion_pnl[emotion] = []
            emotion_pnl[emotion].append(entry.pnl)

        for emotion, pnls in emotion_pnl.items():
            wins = sum(1 for p in pnls if p > 0)
            stats.emotion_win_rates[emotion] = wins / len(pnls) * 100

        if emotion_pnl:
            avg_by_emotion = {
                e: sum(pnls) / len(pnls) for e, pnls in emotion_pnl.items()
            }
            stats.most_profitable_emotion = max(avg_by_emotion, key=avg_by_emotion.get)
            stats.least_profitable_emotion = min(avg_by_emotion, key=avg_by_emotion.get)

        # Mistake analysis
        mistake_counts: Dict[str, int] = {}
        mistake_losses: Dict[str, float] = {}

        for entry in entries:
            for mistake in entry.mistakes:
                m = mistake.value
                mistake_counts[m] = mistake_counts.get(m, 0) + 1
                if entry.pnl < 0:
                    mistake_losses[m] = mistake_losses.get(m, 0) + entry.pnl

        stats.most_common_mistakes = sorted(
            mistake_counts.items(), key=lambda x: x[1], reverse=True
        )[:5]
        stats.mistake_cost = mistake_losses

        # Reason analysis
        reason_wins: Dict[str, int] = {}
        reason_total: Dict[str, int] = {}

        for entry in entries:
            if entry.setup:
                r = entry.setup.entry_reason.value
                reason_total[r] = reason_total.get(r, 0) + 1
                if entry.is_winner:
                    reason_wins[r] = reason_wins.get(r, 0) + 1

        for reason, total in reason_total.items():
            wins = reason_wins.get(reason, 0)
            stats.reason_win_rates[reason] = wins / total * 100

        if stats.reason_win_rates:
            stats.best_performing_reason = max(
                stats.reason_win_rates, key=stats.reason_win_rates.get
            )

        return stats

    async def get_lessons(
        self,
        user_id: str,
        limit: int = 20
    ) -> List[str]:
        """Get recent lessons learned"""
        entries = await self.get_user_entries(user_id, limit=100)

        lessons = [
            e.lessons_learned for e in entries
            if e.lessons_learned and e.lessons_learned.strip()
        ]

        return lessons[:limit]

    async def get_recurring_mistakes(
        self,
        user_id: str
    ) -> List[Tuple[str, int, float]]:
        """Get recurring mistakes with counts and costs"""
        entries = await self.get_user_entries(user_id, limit=1000)

        mistake_data: Dict[str, Dict] = {}

        for entry in entries:
            if not entry.is_complete:
                continue

            for mistake in entry.mistakes:
                m = mistake.value
                if m not in mistake_data:
                    mistake_data[m] = {"count": 0, "cost": 0.0}
                mistake_data[m]["count"] += 1
                if entry.pnl < 0:
                    mistake_data[m]["cost"] += entry.pnl

        return sorted(
            [
                (m, data["count"], data["cost"])
                for m, data in mistake_data.items()
            ],
            key=lambda x: x[1],
            reverse=True
        )


# Singleton
_journal: Optional[TradingJournal] = None


def get_trading_journal() -> TradingJournal:
    """Get the trading journal singleton"""
    global _journal
    if _journal is None:
        _journal = TradingJournal()
    return _journal


# Testing
if __name__ == "__main__":
    async def test():
        journal = TradingJournal("data/test_journal.json")

        # Create entry
        setup = TradeSetup(
            entry_reason=TradeReason.TECHNICAL,
            entry_trigger="Breakout above 200 SMA",
            target_price=160.0,
            stop_loss_price=135.0,
            confidence_level=75
        )

        entry = await journal.create_entry(
            user_id="test_user",
            token="SOL",
            direction="long",
            entry_price=150.0,
            position_size=10.0,
            setup=setup,
            emotion_before=TradeEmotion.CONFIDENT,
            pre_trade_notes="Good setup, trend is strong",
            tags=["breakout", "trend_following"]
        )
        print(f"Created entry: {entry.entry_id}")

        # Close entry
        entry = await journal.close_entry(
            entry_id=entry.entry_id,
            exit_price=165.0,
            emotion_during=TradeEmotion.CALM,
            emotion_after=TradeEmotion.EXCITED,
            post_trade_notes="Hit target, good trade"
        )
        print(f"P&L: ${entry.pnl:,.2f} ({entry.pnl_percent:.1f}%)")

        # Add reflection
        await journal.add_reflection(
            entry_id=entry.entry_id,
            what_went_well="Followed the plan, stuck to stop loss",
            what_went_wrong="Could have let runner go longer",
            lessons_learned="Trust the process, targets are there for a reason",
            mistakes=[],
            would_take_again=True
        )

        # Get stats
        stats = await journal.get_stats("test_user", days=30)
        print(f"\nStats:")
        print(f"  Win Rate: {stats.win_rate:.1f}%")
        print(f"  Total P&L: ${stats.total_pnl:,.2f}")
        print(f"  Profit Factor: {stats.profit_factor:.2f}")

    asyncio.run(test())
