"""
Credit System Data Models.

Database schema for the normie-friendly credit/payment system.

Tables:
- users: User accounts (fiat-only initially)
- credit_packages: Available credit purchase options
- credit_balances: Current credit balance per user
- credit_transactions: Full transaction history
- api_usage: Detailed API usage logging
"""

import os
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

# =============================================================================
# Enums
# =============================================================================


class TransactionType(Enum):
    """Types of credit transactions."""
    PURCHASE = "purchase"          # Credits bought with $
    CONSUMPTION = "consumption"    # Credits used for API
    REFUND = "refund"             # Credits returned
    BONUS = "bonus"               # Promotional credits
    TRANSFER = "transfer"         # User-to-user transfer
    EXPIRY = "expiry"             # Credits expired
    ADJUSTMENT = "adjustment"     # Admin adjustment


class UserTier(Enum):
    """User subscription tiers."""
    FREE = "free"           # Limited free tier
    STARTER = "starter"     # Basic paid tier
    PRO = "pro"            # Professional tier
    ENTERPRISE = "enterprise"  # Custom tier


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class User:
    """User account (fiat-focused)."""
    id: str
    email: str
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    tier: UserTier = UserTier.FREE
    stripe_customer_id: Optional[str] = None
    wallet_address: Optional[str] = None  # Optional crypto wallet link
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "email": self.email,
            "created_at": self.created_at.isoformat(),
            "tier": self.tier.value,
            "stripe_customer_id": self.stripe_customer_id,
            "wallet_address": self.wallet_address,
            "metadata": self.metadata,
        }


@dataclass
class CreditPackage:
    """A purchasable credit package."""
    id: str
    name: str
    credits: int
    price_cents: int = 0  # Price in cents USD
    description: str = ""
    active: bool = True
    popular: bool = False  # Show as recommended
    bonus_credits: int = 0  # Extra credits included
    stripe_price_id: Optional[str] = None  # Stripe price ID
    tier: str = ""  # For test compatibility
    price_usd: float = 0.0  # Alias for test compatibility

    def __post_init__(self):
        # Convert price_usd to price_cents if provided
        if self.price_usd and not self.price_cents:
            self.price_cents = int(self.price_usd * 100)

    @property
    def price_dollars(self) -> float:
        return self.price_cents / 100

    @property
    def total_credits(self) -> int:
        return self.credits + self.bonus_credits

    @property
    def cost_per_credit(self) -> float:
        return self.price_cents / self.total_credits if self.total_credits > 0 else 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "credits": self.credits,
            "bonus_credits": self.bonus_credits,
            "total_credits": self.total_credits,
            "price_cents": self.price_cents,
            "price_dollars": self.price_dollars,
            "cost_per_credit": self.cost_per_credit,
            "description": self.description,
            "active": self.active,
            "popular": self.popular,
        }


@dataclass
class CreditBalance:
    """User's current credit balance."""
    user_id: str
    balance: int
    lifetime_purchased: int = 0
    lifetime_consumed: int = 0
    lifetime_bonus: int = 0
    last_purchase_at: Optional[datetime] = None
    last_consumption_at: Optional[datetime] = None
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "balance": self.balance,
            "lifetime_purchased": self.lifetime_purchased,
            "lifetime_consumed": self.lifetime_consumed,
            "lifetime_bonus": self.lifetime_bonus,
            "last_purchase_at": self.last_purchase_at.isoformat() if self.last_purchase_at else None,
            "last_consumption_at": self.last_consumption_at.isoformat() if self.last_consumption_at else None,
            "updated_at": self.updated_at.isoformat(),
        }


@dataclass
class CreditTransaction:
    """A credit transaction record."""
    id: int
    user_id: str
    type: TransactionType
    amount: int  # Positive for credits in, negative for credits out
    balance_after: int
    description: str
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    stripe_payment_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "type": self.type.value,
            "amount": self.amount,
            "balance_after": self.balance_after,
            "description": self.description,
            "created_at": self.created_at.isoformat(),
            "stripe_payment_id": self.stripe_payment_id,
            "metadata": self.metadata,
        }


@dataclass
class ApiUsage:
    """API usage record for billing."""
    id: int
    user_id: str
    endpoint: str
    credits_consumed: int
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    request_id: str = ""
    duration_ms: int = 0
    success: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "endpoint": self.endpoint,
            "credits_consumed": self.credits_consumed,
            "timestamp": self.timestamp.isoformat(),
            "request_id": self.request_id,
            "duration_ms": self.duration_ms,
            "success": self.success,
        }


# =============================================================================
# Default Credit Packages
# =============================================================================

DEFAULT_PACKAGES = [
    CreditPackage(
        id="starter_10",
        name="Starter Pack",
        credits=100,
        price_cents=1000,  # $10
        description="Perfect for trying out Jarvis",
    ),
    CreditPackage(
        id="basic_50",
        name="Basic Pack",
        credits=600,
        bonus_credits=50,
        price_cents=5000,  # $50
        description="Great for regular use",
    ),
    CreditPackage(
        id="pro_100",
        name="Pro Pack",
        credits=1400,
        bonus_credits=200,
        price_cents=10000,  # $100
        description="Best value for power users",
        popular=True,
    ),
    CreditPackage(
        id="enterprise_500",
        name="Enterprise Pack",
        credits=8000,
        bonus_credits=2000,
        price_cents=50000,  # $500
        description="For teams and high-volume users",
    ),
]

# Alias for backwards compatibility
CREDIT_PACKAGES = DEFAULT_PACKAGES


# =============================================================================
# API Endpoint Costs
# =============================================================================

ENDPOINT_COSTS = {
    # Trading endpoints
    "/api/trade/quote": 1,
    "/api/trade/execute": 5,
    "/api/trade/history": 1,

    # Analysis endpoints
    "/api/analyze/token": 10,
    "/api/analyze/portfolio": 15,
    "/api/analyze/sentiment": 5,

    # Data endpoints
    "/api/data/price": 1,
    "/api/data/ohlcv": 2,
    "/api/data/trending": 2,

    # Strategy endpoints
    "/api/strategy/backtest": 50,
    "/api/strategy/optimize": 100,
    "/api/strategy/signals": 5,

    # AI endpoints
    "/api/ai/chat": 3,
    "/api/ai/summarize": 5,
    "/api/ai/reasoning": 10,

    # Default
    "default": 1,
}


def get_endpoint_cost(endpoint: str) -> int:
    """Get credit cost for an endpoint."""
    # Exact match
    if endpoint in ENDPOINT_COSTS:
        return ENDPOINT_COSTS[endpoint]

    # Prefix match
    for path, cost in ENDPOINT_COSTS.items():
        if endpoint.startswith(path):
            return cost

    return ENDPOINT_COSTS["default"]


# =============================================================================
# Database Schema
# =============================================================================


def init_database(db_path: str = None) -> sqlite3.Connection:
    """Initialize the credit system database."""
    if db_path is None:
        data_dir = Path(os.getenv("DATA_DIR", "data"))
        db_path = str(data_dir / "credits.db")

    os.makedirs(os.path.dirname(db_path), exist_ok=True)

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Users table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            email TEXT UNIQUE NOT NULL,
            created_at TEXT NOT NULL,
            tier TEXT DEFAULT 'free',
            stripe_customer_id TEXT,
            wallet_address TEXT,
            metadata_json TEXT DEFAULT '{}',
            updated_at TEXT
        )
    """)

    # Credit packages table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS credit_packages (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            credits INTEGER NOT NULL,
            bonus_credits INTEGER DEFAULT 0,
            price_cents INTEGER NOT NULL,
            description TEXT,
            active INTEGER DEFAULT 1,
            popular INTEGER DEFAULT 0,
            stripe_price_id TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Credit balances table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS credit_balances (
            user_id TEXT PRIMARY KEY REFERENCES users(id),
            balance INTEGER NOT NULL DEFAULT 0,
            lifetime_purchased INTEGER DEFAULT 0,
            lifetime_consumed INTEGER DEFAULT 0,
            lifetime_bonus INTEGER DEFAULT 0,
            last_purchase_at TEXT,
            last_consumption_at TEXT,
            updated_at TEXT
        )
    """)

    # Credit transactions table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS credit_transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL REFERENCES users(id),
            type TEXT NOT NULL,
            amount INTEGER NOT NULL,
            balance_after INTEGER NOT NULL,
            description TEXT,
            stripe_payment_id TEXT,
            metadata_json TEXT DEFAULT '{}',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # API usage table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS api_usage (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL REFERENCES users(id),
            endpoint TEXT NOT NULL,
            credits_consumed INTEGER NOT NULL,
            request_id TEXT,
            duration_ms INTEGER,
            success INTEGER DEFAULT 1,
            metadata_json TEXT DEFAULT '{}',
            timestamp TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Indexes
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_transactions_user
        ON credit_transactions(user_id)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_transactions_created
        ON credit_transactions(created_at)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_usage_user
        ON api_usage(user_id)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_usage_timestamp
        ON api_usage(timestamp)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_usage_endpoint
        ON api_usage(endpoint)
    """)

    # Insert default packages if not exist
    for pkg in DEFAULT_PACKAGES:
        cursor.execute(
            """
            INSERT OR IGNORE INTO credit_packages
            (id, name, credits, bonus_credits, price_cents, description, active, popular)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                pkg.id,
                pkg.name,
                pkg.credits,
                pkg.bonus_credits,
                pkg.price_cents,
                pkg.description,
                1 if pkg.active else 0,
                1 if pkg.popular else 0,
            ),
        )

    conn.commit()

    return conn
