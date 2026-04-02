"""
Transaction Model
Stores transaction history for portfolio tracking.
"""
from sqlalchemy import Column, String, Float, Integer, DateTime, Boolean, Text, Enum
from datetime import datetime
from enum import Enum as PyEnum
from app.database import Base


class TransactionType(str, PyEnum):
    """Transaction type enumeration"""
    BUY = "buy"
    SELL = "sell"
    SWAP = "swap"
    TRANSFER_IN = "transfer_in"
    TRANSFER_OUT = "transfer_out"


class TransactionStatus(str, PyEnum):
    """Transaction status enumeration"""
    PENDING = "pending"
    CONFIRMED = "confirmed"
    FAILED = "failed"


class Transaction(Base):
    """
    Transaction model for tracking all wallet transactions.

    Attributes:
        id: Unique transaction ID (auto-increment)
        signature: Solana transaction signature (unique)
        wallet_address: User's wallet address
        transaction_type: Type of transaction (buy, sell, swap, etc.)
        status: Transaction status (pending, confirmed, failed)

        # Token Information
        token_address: Address of the token involved
        token_symbol: Token symbol (e.g., SOL, USDC)
        token_name: Full token name

        # Amounts
        amount: Token amount (in token units)
        amount_usd: USD value at time of transaction
        price_per_token: Price per token in USD

        # Fees
        fee_sol: Network fee in SOL
        fee_usd: Network fee in USD

        # Swap specific (if applicable)
        from_token_address: Source token for swaps
        from_token_symbol: Source token symbol
        from_amount: Source token amount
        to_token_address: Destination token for swaps
        to_token_symbol: Destination token symbol
        to_amount: Destination token amount

        # Metadata
        timestamp: When transaction occurred
        block_number: Solana block number
        notes: Optional user notes
        ai_generated: Whether this was AI-recommended
        created_at: When record was created
        updated_at: When record was last updated
    """
    __tablename__ = "transactions"

    # Primary key
    id = Column(Integer, primary_key=True, index=True)

    # Unique transaction identifier
    signature = Column(String(128), unique=True, index=True, nullable=False)

    # Wallet and type
    wallet_address = Column(String(64), index=True, nullable=False)
    transaction_type = Column(Enum(TransactionType), nullable=False, index=True)
    status = Column(Enum(TransactionStatus), default=TransactionStatus.PENDING, nullable=False)

    # Token information
    token_address = Column(String(64), index=True)
    token_symbol = Column(String(20))
    token_name = Column(String(100))

    # Amounts
    amount = Column(Float, nullable=False)
    amount_usd = Column(Float)
    price_per_token = Column(Float)

    # Fees
    fee_sol = Column(Float, default=0.0)
    fee_usd = Column(Float, default=0.0)

    # Swap specific fields
    from_token_address = Column(String(64))
    from_token_symbol = Column(String(20))
    from_amount = Column(Float)
    to_token_address = Column(String(64))
    to_token_symbol = Column(String(20))
    to_amount = Column(Float)

    # Metadata
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    block_number = Column(Integer)
    notes = Column(Text)
    ai_generated = Column(Boolean, default=False)

    # Audit fields
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self) -> dict:
        """Convert transaction to dictionary for API responses"""
        return {
            "id": self.id,
            "signature": self.signature,
            "wallet_address": self.wallet_address,
            "transaction_type": self.transaction_type.value if self.transaction_type else None,
            "status": self.status.value if self.status else None,
            "token_address": self.token_address,
            "token_symbol": self.token_symbol,
            "token_name": self.token_name,
            "amount": self.amount,
            "amount_usd": self.amount_usd,
            "price_per_token": self.price_per_token,
            "fee_sol": self.fee_sol,
            "fee_usd": self.fee_usd,
            "from_token_address": self.from_token_address,
            "from_token_symbol": self.from_token_symbol,
            "from_amount": self.from_amount,
            "to_token_address": self.to_token_address,
            "to_token_symbol": self.to_token_symbol,
            "to_amount": self.to_amount,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "block_number": self.block_number,
            "notes": self.notes,
            "ai_generated": self.ai_generated,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self):
        return f"<Transaction {self.signature[:8]}... {self.transaction_type} {self.amount} {self.token_symbol}>"
