"""
Whale Tracker

Monitors and tracks whale wallets and their on-chain activity.
Supports watchlist management and real-time alerts.

Prompts #109-112: Whale Watching
"""

import asyncio
import logging
import json
import hashlib
import aiohttp
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any, Set
from enum import Enum
from pathlib import Path

logger = logging.getLogger(__name__)


class WhaleCategory(str, Enum):
    """Category of whale wallet"""
    UNKNOWN = "unknown"
    EXCHANGE = "exchange"
    DEX = "dex"
    FUND = "fund"
    VC = "vc"
    INFLUENCER = "influencer"
    TEAM = "team"
    EARLY_INVESTOR = "early_investor"
    SMART_MONEY = "smart_money"
    PROTOCOL = "protocol"


class TransactionType(str, Enum):
    """Type of whale transaction"""
    BUY = "buy"
    SELL = "sell"
    TRANSFER_IN = "transfer_in"
    TRANSFER_OUT = "transfer_out"
    STAKE = "stake"
    UNSTAKE = "unstake"
    LP_ADD = "lp_add"
    LP_REMOVE = "lp_remove"
    BRIDGE_IN = "bridge_in"
    BRIDGE_OUT = "bridge_out"


class AlertSeverity(str, Enum):
    """Severity of whale alert"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class WhaleWallet:
    """A tracked whale wallet"""
    address: str
    label: str
    category: WhaleCategory = WhaleCategory.UNKNOWN
    balance_usd: float = 0.0
    last_active: datetime = field(default_factory=datetime.now)
    first_seen: datetime = field(default_factory=datetime.now)

    # Holdings
    token_holdings: Dict[str, float] = field(default_factory=dict)

    # Stats
    total_transactions: int = 0
    total_volume_usd: float = 0.0
    win_rate: float = 0.0  # Historical profit %
    avg_hold_time_days: float = 0.0

    # Tracking
    is_watched: bool = False
    watch_reason: str = ""
    notes: str = ""
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "address": self.address,
            "label": self.label,
            "category": self.category.value,
            "balance_usd": self.balance_usd,
            "last_active": self.last_active.isoformat(),
            "first_seen": self.first_seen.isoformat(),
            "token_holdings": self.token_holdings,
            "total_transactions": self.total_transactions,
            "total_volume_usd": self.total_volume_usd,
            "win_rate": self.win_rate,
            "avg_hold_time_days": self.avg_hold_time_days,
            "is_watched": self.is_watched,
            "watch_reason": self.watch_reason,
            "notes": self.notes,
            "tags": self.tags
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WhaleWallet":
        """Create from dictionary"""
        return cls(
            address=data["address"],
            label=data.get("label", "Unknown"),
            category=WhaleCategory(data.get("category", "unknown")),
            balance_usd=data.get("balance_usd", 0.0),
            last_active=datetime.fromisoformat(data["last_active"]) if data.get("last_active") else datetime.now(),
            first_seen=datetime.fromisoformat(data["first_seen"]) if data.get("first_seen") else datetime.now(),
            token_holdings=data.get("token_holdings", {}),
            total_transactions=data.get("total_transactions", 0),
            total_volume_usd=data.get("total_volume_usd", 0.0),
            win_rate=data.get("win_rate", 0.0),
            avg_hold_time_days=data.get("avg_hold_time_days", 0.0),
            is_watched=data.get("is_watched", False),
            watch_reason=data.get("watch_reason", ""),
            notes=data.get("notes", ""),
            tags=data.get("tags", [])
        )


@dataclass
class WhaleTransaction:
    """A whale transaction"""
    tx_id: str
    wallet_address: str
    tx_type: TransactionType
    token: str
    amount: float
    amount_usd: float
    price: float
    timestamp: datetime = field(default_factory=datetime.now)

    # Counterparty
    from_address: str = ""
    to_address: str = ""

    # Metadata
    tx_hash: str = ""
    block_number: int = 0
    gas_used: float = 0.0
    platform: str = ""  # DEX name, exchange, etc.

    def __post_init__(self):
        if not self.tx_id:
            data = f"{self.wallet_address}{self.tx_hash}{self.timestamp.isoformat()}"
            self.tx_id = f"WTX-{hashlib.sha256(data.encode()).hexdigest()[:12].upper()}"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "tx_id": self.tx_id,
            "wallet_address": self.wallet_address,
            "tx_type": self.tx_type.value,
            "token": self.token,
            "amount": self.amount,
            "amount_usd": self.amount_usd,
            "price": self.price,
            "timestamp": self.timestamp.isoformat(),
            "from_address": self.from_address,
            "to_address": self.to_address,
            "tx_hash": self.tx_hash,
            "block_number": self.block_number,
            "gas_used": self.gas_used,
            "platform": self.platform
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WhaleTransaction":
        """Create from dictionary"""
        return cls(
            tx_id=data["tx_id"],
            wallet_address=data["wallet_address"],
            tx_type=TransactionType(data["tx_type"]),
            token=data["token"],
            amount=data["amount"],
            amount_usd=data["amount_usd"],
            price=data["price"],
            timestamp=datetime.fromisoformat(data["timestamp"]) if data.get("timestamp") else datetime.now(),
            from_address=data.get("from_address", ""),
            to_address=data.get("to_address", ""),
            tx_hash=data.get("tx_hash", ""),
            block_number=data.get("block_number", 0),
            gas_used=data.get("gas_used", 0.0),
            platform=data.get("platform", "")
        )


@dataclass
class WhaleAlert:
    """An alert generated from whale activity"""
    alert_id: str
    wallet_address: str
    wallet_label: str
    alert_type: str  # buy, sell, accumulation, dump, new_position, etc.
    severity: AlertSeverity
    title: str
    description: str
    token: str
    amount_usd: float
    timestamp: datetime = field(default_factory=datetime.now)

    # Related data
    transaction_id: Optional[str] = None
    related_transactions: List[str] = field(default_factory=list)
    market_impact_estimate: float = 0.0  # Estimated price impact %

    def __post_init__(self):
        if not self.alert_id:
            data = f"{self.wallet_address}{self.alert_type}{self.timestamp.isoformat()}"
            self.alert_id = f"WHALE-{hashlib.sha256(data.encode()).hexdigest()[:8].upper()}"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "alert_id": self.alert_id,
            "wallet_address": self.wallet_address,
            "wallet_label": self.wallet_label,
            "alert_type": self.alert_type,
            "severity": self.severity.value,
            "title": self.title,
            "description": self.description,
            "token": self.token,
            "amount_usd": self.amount_usd,
            "timestamp": self.timestamp.isoformat(),
            "transaction_id": self.transaction_id,
            "related_transactions": self.related_transactions,
            "market_impact_estimate": self.market_impact_estimate
        }


# Whale thresholds by token
DEFAULT_WHALE_THRESHOLDS = {
    "SOL": 10000,       # $10k+ is whale for SOL
    "ETH": 50000,       # $50k+ for ETH
    "BTC": 100000,      # $100k+ for BTC
    "USDC": 100000,     # $100k+ for stables
    "USDT": 100000,
    "default": 25000    # $25k+ default
}


class WhaleTracker:
    """
    Tracks whale wallet activity

    Monitors large wallets, detects significant transactions,
    and generates alerts for whale movements.
    """

    def __init__(
        self,
        storage_path: str = "data/whale_tracking/whales.json",
        rpc_url: Optional[str] = None,
        thresholds: Optional[Dict[str, float]] = None
    ):
        self.storage_path = Path(storage_path)
        self.rpc_url = rpc_url
        self.thresholds = thresholds or DEFAULT_WHALE_THRESHOLDS
        self.wallets: Dict[str, WhaleWallet] = {}
        self.transactions: List[WhaleTransaction] = []
        self.alerts: List[WhaleAlert] = []
        self.watchlist: Set[str] = set()
        self.alert_callbacks: List = []
        self._load()

    def _load(self):
        """Load whale data from storage"""
        if not self.storage_path.exists():
            return

        try:
            with open(self.storage_path) as f:
                data = json.load(f)

            for wallet_data in data.get("wallets", []):
                wallet = WhaleWallet.from_dict(wallet_data)
                self.wallets[wallet.address] = wallet
                if wallet.is_watched:
                    self.watchlist.add(wallet.address)

            for tx_data in data.get("recent_transactions", []):
                tx = WhaleTransaction.from_dict(tx_data)
                self.transactions.append(tx)

            logger.info(f"Loaded {len(self.wallets)} whale wallets, {len(self.transactions)} recent transactions")

        except Exception as e:
            logger.error(f"Failed to load whale data: {e}")

    def _save(self):
        """Save whale data to storage"""
        try:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)

            # Keep only recent transactions (last 7 days)
            cutoff = datetime.now() - timedelta(days=7)
            recent_txs = [tx for tx in self.transactions if tx.timestamp > cutoff]

            data = {
                "wallets": [w.to_dict() for w in self.wallets.values()],
                "recent_transactions": [tx.to_dict() for tx in recent_txs[-1000:]],
                "updated_at": datetime.now().isoformat()
            }

            with open(self.storage_path, "w") as f:
                json.dump(data, f, indent=2)

        except Exception as e:
            logger.error(f"Failed to save whale data: {e}")
            raise

    def register_alert_callback(self, callback):
        """Register a callback for whale alerts"""
        self.alert_callbacks.append(callback)

    async def add_to_watchlist(
        self,
        address: str,
        label: str = "Unknown",
        category: WhaleCategory = WhaleCategory.UNKNOWN,
        reason: str = ""
    ) -> WhaleWallet:
        """Add a wallet to the watchlist"""
        if address in self.wallets:
            wallet = self.wallets[address]
            wallet.is_watched = True
            wallet.watch_reason = reason or wallet.watch_reason
        else:
            wallet = WhaleWallet(
                address=address,
                label=label,
                category=category,
                is_watched=True,
                watch_reason=reason
            )
            self.wallets[address] = wallet

        self.watchlist.add(address)
        self._save()

        logger.info(f"Added {address} to whale watchlist: {label}")
        return wallet

    async def remove_from_watchlist(self, address: str) -> bool:
        """Remove a wallet from the watchlist"""
        if address in self.watchlist:
            self.watchlist.remove(address)
            if address in self.wallets:
                self.wallets[address].is_watched = False
            self._save()
            return True
        return False

    async def get_wallet(self, address: str) -> Optional[WhaleWallet]:
        """Get a whale wallet by address"""
        return self.wallets.get(address)

    async def get_watchlist(self) -> List[WhaleWallet]:
        """Get all watched wallets"""
        return [
            self.wallets[addr]
            for addr in self.watchlist
            if addr in self.wallets
        ]

    def is_whale_transaction(self, token: str, amount_usd: float) -> bool:
        """Check if a transaction qualifies as whale activity"""
        threshold = self.thresholds.get(token, self.thresholds.get("default", 25000))
        return amount_usd >= threshold

    async def process_transaction(
        self,
        wallet_address: str,
        tx_type: TransactionType,
        token: str,
        amount: float,
        amount_usd: float,
        price: float,
        tx_hash: str = "",
        platform: str = ""
    ) -> Optional[WhaleAlert]:
        """
        Process a new transaction and check for whale activity

        Returns a whale alert if the transaction is significant.
        """
        # Check if this is a whale transaction
        if not self.is_whale_transaction(token, amount_usd):
            return None

        # Get or create wallet
        if wallet_address not in self.wallets:
            self.wallets[wallet_address] = WhaleWallet(
                address=wallet_address,
                label=f"Whale {wallet_address[:8]}..."
            )

        wallet = self.wallets[wallet_address]
        wallet.last_active = datetime.now()
        wallet.total_transactions += 1
        wallet.total_volume_usd += amount_usd

        # Update holdings
        if tx_type in [TransactionType.BUY, TransactionType.TRANSFER_IN]:
            wallet.token_holdings[token] = wallet.token_holdings.get(token, 0) + amount
        elif tx_type in [TransactionType.SELL, TransactionType.TRANSFER_OUT]:
            wallet.token_holdings[token] = wallet.token_holdings.get(token, 0) - amount

        # Create transaction record
        tx = WhaleTransaction(
            tx_id="",
            wallet_address=wallet_address,
            tx_type=tx_type,
            token=token,
            amount=amount,
            amount_usd=amount_usd,
            price=price,
            tx_hash=tx_hash,
            platform=platform
        )
        self.transactions.append(tx)

        # Generate alert
        alert = self._generate_alert(wallet, tx)
        if alert:
            self.alerts.append(alert)

            # Notify callbacks
            for callback in self.alert_callbacks:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(alert)
                    else:
                        callback(alert)
                except Exception as e:
                    logger.error(f"Alert callback failed: {e}")

        self._save()
        return alert

    def _generate_alert(
        self,
        wallet: WhaleWallet,
        tx: WhaleTransaction
    ) -> WhaleAlert:
        """Generate an alert for a whale transaction"""
        # Determine severity
        if tx.amount_usd >= 1000000:
            severity = AlertSeverity.CRITICAL
        elif tx.amount_usd >= 500000:
            severity = AlertSeverity.HIGH
        elif tx.amount_usd >= 100000:
            severity = AlertSeverity.MEDIUM
        else:
            severity = AlertSeverity.LOW

        # Determine alert type and title
        alert_types = {
            TransactionType.BUY: ("whale_buy", "Whale Buy Detected"),
            TransactionType.SELL: ("whale_sell", "Whale Sell Detected"),
            TransactionType.TRANSFER_IN: ("transfer_in", "Large Transfer In"),
            TransactionType.TRANSFER_OUT: ("transfer_out", "Large Transfer Out"),
            TransactionType.STAKE: ("stake", "Large Stake"),
            TransactionType.UNSTAKE: ("unstake", "Large Unstake"),
        }

        alert_type, title_prefix = alert_types.get(
            tx.tx_type,
            ("whale_activity", "Whale Activity")
        )

        title = f"{title_prefix}: {wallet.label}"

        # Generate description
        action = tx.tx_type.value.replace("_", " ").title()
        description = (
            f"{wallet.label} ({wallet.category.value}) {action} "
            f"${tx.amount_usd:,.0f} worth of {tx.token} "
            f"at ${tx.price:,.4f} per token"
        )

        return WhaleAlert(
            alert_id="",
            wallet_address=wallet.address,
            wallet_label=wallet.label,
            alert_type=alert_type,
            severity=severity,
            title=title,
            description=description,
            token=tx.token,
            amount_usd=tx.amount_usd,
            transaction_id=tx.tx_id
        )

    async def get_recent_activity(
        self,
        wallet_address: Optional[str] = None,
        token: Optional[str] = None,
        hours: int = 24,
        limit: int = 100
    ) -> List[WhaleTransaction]:
        """Get recent whale activity"""
        cutoff = datetime.now() - timedelta(hours=hours)

        txs = [tx for tx in self.transactions if tx.timestamp > cutoff]

        if wallet_address:
            txs = [tx for tx in txs if tx.wallet_address == wallet_address]

        if token:
            txs = [tx for tx in txs if tx.token == token]

        txs.sort(key=lambda t: t.timestamp, reverse=True)
        return txs[:limit]

    async def get_token_whale_summary(self, token: str) -> Dict[str, Any]:
        """Get whale activity summary for a token"""
        cutoff = datetime.now() - timedelta(hours=24)
        recent_txs = [
            tx for tx in self.transactions
            if tx.token == token and tx.timestamp > cutoff
        ]

        buy_volume = sum(tx.amount_usd for tx in recent_txs if tx.tx_type == TransactionType.BUY)
        sell_volume = sum(tx.amount_usd for tx in recent_txs if tx.tx_type == TransactionType.SELL)

        unique_buyers = len(set(tx.wallet_address for tx in recent_txs if tx.tx_type == TransactionType.BUY))
        unique_sellers = len(set(tx.wallet_address for tx in recent_txs if tx.tx_type == TransactionType.SELL))

        return {
            "token": token,
            "period_hours": 24,
            "whale_buy_volume": buy_volume,
            "whale_sell_volume": sell_volume,
            "net_flow": buy_volume - sell_volume,
            "unique_whale_buyers": unique_buyers,
            "unique_whale_sellers": unique_sellers,
            "total_transactions": len(recent_txs),
            "sentiment": "bullish" if buy_volume > sell_volume * 1.2 else "bearish" if sell_volume > buy_volume * 1.2 else "neutral"
        }

    async def get_top_wallets(
        self,
        by: str = "volume",  # volume, transactions, holdings
        limit: int = 10
    ) -> List[WhaleWallet]:
        """Get top whale wallets"""
        wallets = list(self.wallets.values())

        if by == "volume":
            wallets.sort(key=lambda w: w.total_volume_usd, reverse=True)
        elif by == "transactions":
            wallets.sort(key=lambda w: w.total_transactions, reverse=True)
        elif by == "holdings":
            wallets.sort(key=lambda w: w.balance_usd, reverse=True)

        return wallets[:limit]

    def get_stats(self) -> Dict[str, Any]:
        """Get whale tracking statistics"""
        return {
            "total_wallets_tracked": len(self.wallets),
            "watchlist_size": len(self.watchlist),
            "recent_transactions": len([
                tx for tx in self.transactions
                if tx.timestamp > datetime.now() - timedelta(hours=24)
            ]),
            "alerts_generated": len(self.alerts),
            "total_volume_24h": sum(
                tx.amount_usd for tx in self.transactions
                if tx.timestamp > datetime.now() - timedelta(hours=24)
            )
        }


# Singleton instance
_whale_tracker: Optional[WhaleTracker] = None


def get_whale_tracker() -> WhaleTracker:
    """Get whale tracker singleton"""
    global _whale_tracker

    if _whale_tracker is None:
        _whale_tracker = WhaleTracker()

    return _whale_tracker


# Known whale wallets (examples)
KNOWN_WHALES = [
    {
        "address": "9WzDXwBbmPdCBxJ7jLQvHRYUfGFqPiD7TgKnvFMm5Vqm",
        "label": "Alameda Research (Legacy)",
        "category": WhaleCategory.FUND
    },
    {
        "address": "H6ARHf6YXhGYeQfUzQNGk6rDNnLBQKrenN712K4AQJEG",
        "label": "Jump Trading",
        "category": WhaleCategory.FUND
    },
]


# Testing
if __name__ == "__main__":
    async def test():
        tracker = WhaleTracker("test_whales.json")

        # Add to watchlist
        await tracker.add_to_watchlist(
            "WHALE_ADDRESS_123",
            label="Test Whale",
            category=WhaleCategory.SMART_MONEY,
            reason="High win rate"
        )

        # Process a whale transaction
        alert = await tracker.process_transaction(
            wallet_address="WHALE_ADDRESS_123",
            tx_type=TransactionType.BUY,
            token="SOL",
            amount=5000,
            amount_usd=750000,
            price=150.0,
            platform="Jupiter"
        )

        if alert:
            print(f"Alert generated: {alert.title}")
            print(f"  Severity: {alert.severity.value}")
            print(f"  Description: {alert.description}")

        # Get summary
        summary = await tracker.get_token_whale_summary("SOL")
        print(f"\nSOL whale summary: {summary}")

        # Stats
        print(f"\nStats: {tracker.get_stats()}")

        # Clean up
        import os
        os.remove("test_whales.json")

    asyncio.run(test())
