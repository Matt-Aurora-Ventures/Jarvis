"""
Transaction Pydantic Schemas
Request/response validation for transaction API.
"""
from pydantic import BaseModel, Field, validator
from typing import Optional
from datetime import datetime
from enum import Enum


class TransactionTypeEnum(str, Enum):
    """Transaction type for API"""
    BUY = "buy"
    SELL = "sell"
    SWAP = "swap"
    TRANSFER_IN = "transfer_in"
    TRANSFER_OUT = "transfer_out"


class TransactionStatusEnum(str, Enum):
    """Transaction status for API"""
    PENDING = "pending"
    CONFIRMED = "confirmed"
    FAILED = "failed"


class TransactionCreate(BaseModel):
    """Schema for creating a new transaction"""
    signature: str = Field(..., min_length=64, max_length=128, description="Solana transaction signature")
    wallet_address: str = Field(..., min_length=32, max_length=64, description="User's wallet address")
    transaction_type: TransactionTypeEnum = Field(..., description="Type of transaction")
    status: TransactionStatusEnum = Field(default=TransactionStatusEnum.PENDING, description="Transaction status")

    # Token information
    token_address: Optional[str] = Field(None, max_length=64)
    token_symbol: Optional[str] = Field(None, max_length=20)
    token_name: Optional[str] = Field(None, max_length=100)

    # Amounts
    amount: float = Field(..., gt=0, description="Token amount")
    amount_usd: Optional[float] = Field(None, ge=0)
    price_per_token: Optional[float] = Field(None, ge=0)

    # Fees
    fee_sol: Optional[float] = Field(0.0, ge=0)
    fee_usd: Optional[float] = Field(0.0, ge=0)

    # Swap specific
    from_token_address: Optional[str] = None
    from_token_symbol: Optional[str] = None
    from_amount: Optional[float] = None
    to_token_address: Optional[str] = None
    to_token_symbol: Optional[str] = None
    to_amount: Optional[float] = None

    # Metadata
    timestamp: Optional[datetime] = None
    block_number: Optional[int] = None
    notes: Optional[str] = None
    ai_generated: Optional[bool] = False

    @validator('signature')
    def validate_signature(cls, v):
        """Validate signature format"""
        if not v or len(v) < 64:
            raise ValueError("Invalid transaction signature")
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "signature": "5VPy7RqLExF4K7f9N1qGtBNB1q3H9hK8Lf4J3G5H2K9...",
                "wallet_address": "7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU",
                "transaction_type": "swap",
                "status": "confirmed",
                "amount": 10.5,
                "amount_usd": 1314.91,
                "token_symbol": "SOL",
                "from_token_symbol": "USDC",
                "from_amount": 1300,
                "to_token_symbol": "SOL",
                "to_amount": 10.5,
                "fee_sol": 0.000005,
                "fee_usd": 0.0006
            }
        }


class TransactionUpdate(BaseModel):
    """Schema for updating a transaction"""
    status: Optional[TransactionStatusEnum] = None
    notes: Optional[str] = None
    block_number: Optional[int] = None


class TransactionResponse(BaseModel):
    """Schema for transaction API responses"""
    id: int
    signature: str
    wallet_address: str
    transaction_type: str
    status: str

    token_address: Optional[str] = None
    token_symbol: Optional[str] = None
    token_name: Optional[str] = None

    amount: float
    amount_usd: Optional[float] = None
    price_per_token: Optional[float] = None

    fee_sol: Optional[float] = None
    fee_usd: Optional[float] = None

    from_token_address: Optional[str] = None
    from_token_symbol: Optional[str] = None
    from_amount: Optional[float] = None
    to_token_address: Optional[str] = None
    to_token_symbol: Optional[str] = None
    to_amount: Optional[float] = None

    timestamp: Optional[str] = None
    block_number: Optional[int] = None
    notes: Optional[str] = None
    ai_generated: bool = False

    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    class Config:
        from_attributes = True


class TransactionListResponse(BaseModel):
    """Schema for paginated transaction list"""
    transactions: list[TransactionResponse]
    total: int
    page: int
    page_size: int
    total_pages: int
