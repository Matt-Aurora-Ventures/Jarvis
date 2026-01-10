"""
Portfolio Tracker

Tracks portfolio positions, transactions, and real-time P&L.
Supports multi-wallet aggregation and historical tracking.

Prompts #107-108: Portfolio Tracking
"""

import asyncio
import logging
import json
import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any
from enum import Enum
from pathlib import Path
from collections import defaultdict

logger = logging.getLogger(__name__)


class TransactionType(str, Enum):
    """Types of portfolio transactions"""
    BUY = "buy"
    SELL = "sell"
    TRANSFER_IN = "transfer_in"
    TRANSFER_OUT = "transfer_out"
    STAKE = "stake"
    UNSTAKE = "unstake"
    REWARD = "reward"
    AIRDROP = "airdrop"
    FEE = "fee"


class PositionStatus(str, Enum):
    """Status of a position"""
    OPEN = "open"
    CLOSED = "closed"
    PARTIAL = "partial"


@dataclass
class Transaction:
    """A portfolio transaction"""
    tx_id: str
    wallet: str
    tx_type: TransactionType
    token: str
    amount: float
    price_usd: float
    total_usd: float
    timestamp: datetime = field(default_factory=datetime.now)

    # Additional info
    tx_hash: Optional[str] = None
    platform: str = ""  # Exchange/DEX name
    fee_usd: float = 0.0
    notes: str = ""

    def __post_init__(self):
        if not self.tx_id:
            data = f"{self.wallet}{self.token}{self.timestamp.isoformat()}{self.amount}"
            self.tx_id = f"TX-{hashlib.sha256(data.encode()).hexdigest()[:12].upper()}"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "tx_id": self.tx_id,
            "wallet": self.wallet,
            "tx_type": self.tx_type.value,
            "token": self.token,
            "amount": self.amount,
            "price_usd": self.price_usd,
            "total_usd": self.total_usd,
            "timestamp": self.timestamp.isoformat(),
            "tx_hash": self.tx_hash,
            "platform": self.platform,
            "fee_usd": self.fee_usd,
            "notes": self.notes
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Transaction":
        """Create from dictionary"""
        return cls(
            tx_id=data["tx_id"],
            wallet=data["wallet"],
            tx_type=TransactionType(data["tx_type"]),
            token=data["token"],
            amount=data["amount"],
            price_usd=data["price_usd"],
            total_usd=data["total_usd"],
            timestamp=datetime.fromisoformat(data["timestamp"]) if data.get("timestamp") else datetime.now(),
            tx_hash=data.get("tx_hash"),
            platform=data.get("platform", ""),
            fee_usd=data.get("fee_usd", 0.0),
            notes=data.get("notes", "")
        )


@dataclass
class Position:
    """A portfolio position in a single token"""
    token: str
    amount: float
    avg_cost_basis: float  # Average cost per token
    total_cost_basis: float  # Total invested
    current_price: float = 0.0
    current_value: float = 0.0
    unrealized_pnl: float = 0.0
    unrealized_pnl_pct: float = 0.0
    realized_pnl: float = 0.0

    # Position details
    first_buy: Optional[datetime] = None
    last_update: datetime = field(default_factory=datetime.now)
    status: PositionStatus = PositionStatus.OPEN

    # Breakdown by wallet
    by_wallet: Dict[str, float] = field(default_factory=dict)

    def update_price(self, price: float):
        """Update position with current price"""
        self.current_price = price
        self.current_value = self.amount * price

        if self.total_cost_basis > 0:
            self.unrealized_pnl = self.current_value - self.total_cost_basis
            self.unrealized_pnl_pct = (self.unrealized_pnl / self.total_cost_basis) * 100
        else:
            self.unrealized_pnl = self.current_value
            self.unrealized_pnl_pct = 0.0

        self.last_update = datetime.now()

    def add_tokens(self, amount: float, price: float, wallet: str = "default"):
        """Add tokens to position (buy)"""
        cost = amount * price

        # Update cost basis
        new_total_cost = self.total_cost_basis + cost
        new_amount = self.amount + amount

        if new_amount > 0:
            self.avg_cost_basis = new_total_cost / new_amount

        self.amount = new_amount
        self.total_cost_basis = new_total_cost

        # Update wallet breakdown
        self.by_wallet[wallet] = self.by_wallet.get(wallet, 0) + amount

        if not self.first_buy:
            self.first_buy = datetime.now()

        self.last_update = datetime.now()
        self.status = PositionStatus.OPEN

    def remove_tokens(self, amount: float, price: float, wallet: str = "default") -> float:
        """Remove tokens from position (sell), returns realized PnL"""
        if amount > self.amount:
            amount = self.amount

        # Calculate realized P&L
        cost_of_sold = amount * self.avg_cost_basis
        proceeds = amount * price
        realized = proceeds - cost_of_sold

        self.realized_pnl += realized
        self.amount -= amount

        # Update cost basis (proportional reduction)
        if self.amount > 0:
            self.total_cost_basis = self.amount * self.avg_cost_basis
        else:
            self.total_cost_basis = 0
            self.status = PositionStatus.CLOSED

        # Update wallet breakdown
        if wallet in self.by_wallet:
            self.by_wallet[wallet] = max(0, self.by_wallet[wallet] - amount)

        self.last_update = datetime.now()
        return realized

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "token": self.token,
            "amount": self.amount,
            "avg_cost_basis": self.avg_cost_basis,
            "total_cost_basis": self.total_cost_basis,
            "current_price": self.current_price,
            "current_value": self.current_value,
            "unrealized_pnl": self.unrealized_pnl,
            "unrealized_pnl_pct": self.unrealized_pnl_pct,
            "realized_pnl": self.realized_pnl,
            "first_buy": self.first_buy.isoformat() if self.first_buy else None,
            "last_update": self.last_update.isoformat(),
            "status": self.status.value,
            "by_wallet": self.by_wallet
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Position":
        """Create from dictionary"""
        return cls(
            token=data["token"],
            amount=data["amount"],
            avg_cost_basis=data["avg_cost_basis"],
            total_cost_basis=data["total_cost_basis"],
            current_price=data.get("current_price", 0.0),
            current_value=data.get("current_value", 0.0),
            unrealized_pnl=data.get("unrealized_pnl", 0.0),
            unrealized_pnl_pct=data.get("unrealized_pnl_pct", 0.0),
            realized_pnl=data.get("realized_pnl", 0.0),
            first_buy=datetime.fromisoformat(data["first_buy"]) if data.get("first_buy") else None,
            last_update=datetime.fromisoformat(data["last_update"]) if data.get("last_update") else datetime.now(),
            status=PositionStatus(data.get("status", "open")),
            by_wallet=data.get("by_wallet", {})
        )


@dataclass
class Portfolio:
    """A user's complete portfolio"""
    portfolio_id: str
    user_id: str
    positions: Dict[str, Position] = field(default_factory=dict)
    transactions: List[Transaction] = field(default_factory=list)

    # Aggregated values
    total_value: float = 0.0
    total_cost_basis: float = 0.0
    total_unrealized_pnl: float = 0.0
    total_realized_pnl: float = 0.0
    total_pnl_pct: float = 0.0

    # Wallets
    wallets: List[str] = field(default_factory=list)

    # Metadata
    created_at: datetime = field(default_factory=datetime.now)
    last_updated: datetime = field(default_factory=datetime.now)

    def __post_init__(self):
        if not self.portfolio_id:
            data = f"{self.user_id}{self.created_at.isoformat()}"
            self.portfolio_id = f"PORT-{hashlib.sha256(data.encode()).hexdigest()[:8].upper()}"

    def recalculate(self):
        """Recalculate portfolio totals"""
        self.total_value = sum(p.current_value for p in self.positions.values())
        self.total_cost_basis = sum(p.total_cost_basis for p in self.positions.values())
        self.total_unrealized_pnl = sum(p.unrealized_pnl for p in self.positions.values())
        self.total_realized_pnl = sum(p.realized_pnl for p in self.positions.values())

        if self.total_cost_basis > 0:
            self.total_pnl_pct = (self.total_unrealized_pnl / self.total_cost_basis) * 100
        else:
            self.total_pnl_pct = 0.0

        self.last_updated = datetime.now()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "portfolio_id": self.portfolio_id,
            "user_id": self.user_id,
            "positions": {k: v.to_dict() for k, v in self.positions.items()},
            "transactions": [t.to_dict() for t in self.transactions[-1000:]],  # Last 1000
            "total_value": self.total_value,
            "total_cost_basis": self.total_cost_basis,
            "total_unrealized_pnl": self.total_unrealized_pnl,
            "total_realized_pnl": self.total_realized_pnl,
            "total_pnl_pct": self.total_pnl_pct,
            "wallets": self.wallets,
            "created_at": self.created_at.isoformat(),
            "last_updated": self.last_updated.isoformat()
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Portfolio":
        """Create from dictionary"""
        positions = {
            k: Position.from_dict(v)
            for k, v in data.get("positions", {}).items()
        }
        transactions = [
            Transaction.from_dict(t)
            for t in data.get("transactions", [])
        ]

        return cls(
            portfolio_id=data["portfolio_id"],
            user_id=data["user_id"],
            positions=positions,
            transactions=transactions,
            total_value=data.get("total_value", 0.0),
            total_cost_basis=data.get("total_cost_basis", 0.0),
            total_unrealized_pnl=data.get("total_unrealized_pnl", 0.0),
            total_realized_pnl=data.get("total_realized_pnl", 0.0),
            total_pnl_pct=data.get("total_pnl_pct", 0.0),
            wallets=data.get("wallets", []),
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else datetime.now(),
            last_updated=datetime.fromisoformat(data["last_updated"]) if data.get("last_updated") else datetime.now()
        )


class PortfolioTracker:
    """
    Tracks user portfolios

    Manages positions, transactions, and P&L across multiple wallets.
    """

    def __init__(
        self,
        storage_path: str = "data/portfolios/portfolios.json",
        price_fetcher: Any = None
    ):
        self.storage_path = Path(storage_path)
        self.price_fetcher = price_fetcher  # Injected price service
        self.portfolios: Dict[str, Portfolio] = {}
        self._load()

    def _load(self):
        """Load portfolios from storage"""
        if not self.storage_path.exists():
            return

        try:
            with open(self.storage_path) as f:
                data = json.load(f)

            for port_data in data.get("portfolios", []):
                portfolio = Portfolio.from_dict(port_data)
                self.portfolios[portfolio.user_id] = portfolio

            logger.info(f"Loaded {len(self.portfolios)} portfolios")

        except Exception as e:
            logger.error(f"Failed to load portfolios: {e}")

    def _save(self):
        """Save portfolios to storage"""
        try:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)

            data = {
                "portfolios": [p.to_dict() for p in self.portfolios.values()],
                "updated_at": datetime.now().isoformat()
            }

            with open(self.storage_path, "w") as f:
                json.dump(data, f, indent=2)

        except Exception as e:
            logger.error(f"Failed to save portfolios: {e}")
            raise

    async def get_or_create_portfolio(self, user_id: str) -> Portfolio:
        """Get or create a portfolio for a user"""
        if user_id in self.portfolios:
            return self.portfolios[user_id]

        portfolio = Portfolio(
            portfolio_id="",
            user_id=user_id
        )
        self.portfolios[user_id] = portfolio
        self._save()

        return portfolio

    async def record_transaction(
        self,
        user_id: str,
        tx_type: TransactionType,
        token: str,
        amount: float,
        price_usd: float,
        wallet: str = "default",
        tx_hash: Optional[str] = None,
        platform: str = "",
        fee_usd: float = 0.0,
        notes: str = ""
    ) -> Transaction:
        """Record a new transaction"""
        portfolio = await self.get_or_create_portfolio(user_id)

        total_usd = amount * price_usd

        # Create transaction
        tx = Transaction(
            tx_id="",
            wallet=wallet,
            tx_type=tx_type,
            token=token,
            amount=amount,
            price_usd=price_usd,
            total_usd=total_usd,
            tx_hash=tx_hash,
            platform=platform,
            fee_usd=fee_usd,
            notes=notes
        )

        portfolio.transactions.append(tx)

        # Update wallet list
        if wallet not in portfolio.wallets:
            portfolio.wallets.append(wallet)

        # Update position
        if token not in portfolio.positions:
            portfolio.positions[token] = Position(
                token=token,
                amount=0,
                avg_cost_basis=0,
                total_cost_basis=0
            )

        position = portfolio.positions[token]

        if tx_type in [TransactionType.BUY, TransactionType.TRANSFER_IN, TransactionType.REWARD, TransactionType.AIRDROP]:
            position.add_tokens(amount, price_usd, wallet)

        elif tx_type in [TransactionType.SELL, TransactionType.TRANSFER_OUT]:
            position.remove_tokens(amount, price_usd, wallet)

        elif tx_type == TransactionType.FEE:
            position.remove_tokens(amount, price_usd, wallet)

        # Recalculate portfolio
        portfolio.recalculate()
        self._save()

        logger.info(f"Recorded {tx_type.value} for {user_id}: {amount} {token} @ ${price_usd}")
        return tx

    async def update_prices(self, user_id: str, prices: Dict[str, float]):
        """Update position prices"""
        portfolio = self.portfolios.get(user_id)
        if not portfolio:
            return

        for token, price in prices.items():
            if token in portfolio.positions:
                portfolio.positions[token].update_price(price)

        portfolio.recalculate()
        self._save()

    async def get_portfolio_summary(self, user_id: str) -> Dict[str, Any]:
        """Get portfolio summary"""
        portfolio = self.portfolios.get(user_id)
        if not portfolio:
            return {"error": "Portfolio not found"}

        # Sort positions by value
        positions_by_value = sorted(
            portfolio.positions.values(),
            key=lambda p: p.current_value,
            reverse=True
        )

        return {
            "portfolio_id": portfolio.portfolio_id,
            "total_value": portfolio.total_value,
            "total_cost_basis": portfolio.total_cost_basis,
            "total_unrealized_pnl": portfolio.total_unrealized_pnl,
            "total_unrealized_pnl_pct": portfolio.total_pnl_pct,
            "total_realized_pnl": portfolio.total_realized_pnl,
            "total_pnl": portfolio.total_unrealized_pnl + portfolio.total_realized_pnl,
            "position_count": len([p for p in portfolio.positions.values() if p.status == PositionStatus.OPEN]),
            "top_positions": [
                {
                    "token": p.token,
                    "value": p.current_value,
                    "pnl": p.unrealized_pnl,
                    "pnl_pct": p.unrealized_pnl_pct
                }
                for p in positions_by_value[:5]
            ],
            "wallets": portfolio.wallets,
            "last_updated": portfolio.last_updated.isoformat()
        }

    async def get_position(self, user_id: str, token: str) -> Optional[Position]:
        """Get a specific position"""
        portfolio = self.portfolios.get(user_id)
        if not portfolio:
            return None
        return portfolio.positions.get(token)

    async def get_transaction_history(
        self,
        user_id: str,
        token: Optional[str] = None,
        tx_type: Optional[TransactionType] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100
    ) -> List[Transaction]:
        """Get transaction history with filters"""
        portfolio = self.portfolios.get(user_id)
        if not portfolio:
            return []

        txs = portfolio.transactions.copy()

        if token:
            txs = [t for t in txs if t.token == token]

        if tx_type:
            txs = [t for t in txs if t.tx_type == tx_type]

        if start_date:
            txs = [t for t in txs if t.timestamp >= start_date]

        if end_date:
            txs = [t for t in txs if t.timestamp <= end_date]

        txs.sort(key=lambda t: t.timestamp, reverse=True)
        return txs[:limit]

    async def get_daily_pnl(
        self,
        user_id: str,
        days: int = 30
    ) -> List[Dict[str, Any]]:
        """Get daily P&L history"""
        portfolio = self.portfolios.get(user_id)
        if not portfolio:
            return []

        # Group transactions by day
        by_day = defaultdict(lambda: {"realized": 0.0, "volume": 0.0})
        cutoff = datetime.now() - timedelta(days=days)

        for tx in portfolio.transactions:
            if tx.timestamp < cutoff:
                continue

            day_key = tx.timestamp.strftime("%Y-%m-%d")
            by_day[day_key]["volume"] += tx.total_usd

            if tx.tx_type == TransactionType.SELL:
                # Would need to track actual P&L per transaction
                pass

        return [
            {"date": day, "realized_pnl": data["realized"], "volume": data["volume"]}
            for day, data in sorted(by_day.items())
        ]

    async def get_allocation(self, user_id: str) -> List[Dict[str, Any]]:
        """Get portfolio allocation breakdown"""
        portfolio = self.portfolios.get(user_id)
        if not portfolio or portfolio.total_value == 0:
            return []

        allocations = []
        for token, position in portfolio.positions.items():
            if position.current_value > 0:
                allocations.append({
                    "token": token,
                    "value": position.current_value,
                    "percentage": (position.current_value / portfolio.total_value) * 100,
                    "amount": position.amount
                })

        allocations.sort(key=lambda x: x["value"], reverse=True)
        return allocations


# Singleton instance
_portfolio_tracker: Optional[PortfolioTracker] = None


def get_portfolio_tracker() -> PortfolioTracker:
    """Get portfolio tracker singleton"""
    global _portfolio_tracker

    if _portfolio_tracker is None:
        _portfolio_tracker = PortfolioTracker()

    return _portfolio_tracker


# Testing
if __name__ == "__main__":
    async def test():
        tracker = PortfolioTracker("test_portfolios.json")

        user_id = "TEST_USER"

        # Record some transactions
        await tracker.record_transaction(
            user_id=user_id,
            tx_type=TransactionType.BUY,
            token="SOL",
            amount=10,
            price_usd=100.0,
            platform="Jupiter"
        )

        await tracker.record_transaction(
            user_id=user_id,
            tx_type=TransactionType.BUY,
            token="SOL",
            amount=5,
            price_usd=120.0,
            platform="Jupiter"
        )

        await tracker.record_transaction(
            user_id=user_id,
            tx_type=TransactionType.BUY,
            token="ETH",
            amount=2,
            price_usd=3000.0,
            platform="Jupiter"
        )

        # Update prices
        await tracker.update_prices(user_id, {"SOL": 150.0, "ETH": 3200.0})

        # Get summary
        summary = await tracker.get_portfolio_summary(user_id)
        print("Portfolio Summary:")
        print(f"  Total Value: ${summary['total_value']:,.2f}")
        print(f"  Unrealized P&L: ${summary['total_unrealized_pnl']:,.2f} ({summary['total_unrealized_pnl_pct']:.1f}%)")
        print(f"  Positions: {summary['position_count']}")

        # Get allocation
        allocation = await tracker.get_allocation(user_id)
        print("\nAllocation:")
        for a in allocation:
            print(f"  {a['token']}: ${a['value']:,.2f} ({a['percentage']:.1f}%)")

        # Clean up
        import os
        os.remove("test_portfolios.json")

    asyncio.run(test())
