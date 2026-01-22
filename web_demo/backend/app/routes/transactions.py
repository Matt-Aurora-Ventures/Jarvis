"""
Transaction History API Routes
Provides CRUD operations and filtering for transaction tracking.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc, asc, or_, and_
from typing import Optional, List
from datetime import datetime, timedelta
import logging

from app.database import get_db
from app.models.transaction import Transaction, TransactionType, TransactionStatus
from app.schemas.transaction import (
    TransactionCreate,
    TransactionUpdate,
    TransactionResponse,
    TransactionListResponse,
    TransactionTypeEnum,
    TransactionStatusEnum
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/transactions", tags=["Transactions"])


@router.post("/", response_model=TransactionResponse, status_code=201)
async def create_transaction(
    transaction: TransactionCreate,
    db: Session = Depends(get_db)
):
    """
    Create a new transaction record.

    Args:
        transaction: Transaction data
        db: Database session

    Returns:
        Created transaction

    Raises:
        HTTPException: If signature already exists
    """
    # Check for duplicate signature
    existing = db.query(Transaction).filter(Transaction.signature == transaction.signature).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Transaction {transaction.signature[:8]}... already exists")

    # Create transaction
    db_transaction = Transaction(
        **transaction.model_dump(exclude_unset=True)
    )

    try:
        db.add(db_transaction)
        db.commit()
        db.refresh(db_transaction)
        logger.info(f"Created transaction: {db_transaction.signature[:8]}... ({db_transaction.transaction_type})")
        return db_transaction.to_dict()
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to create transaction: {e}")
        raise HTTPException(status_code=500, detail="Failed to create transaction")


@router.get("/", response_model=TransactionListResponse)
async def list_transactions(
    wallet_address: Optional[str] = Query(None, description="Filter by wallet address"),
    transaction_type: Optional[TransactionTypeEnum] = Query(None, description="Filter by transaction type"),
    status: Optional[TransactionStatusEnum] = Query(None, description="Filter by status"),
    token_symbol: Optional[str] = Query(None, description="Filter by token symbol"),
    from_date: Optional[datetime] = Query(None, description="Start date filter"),
    to_date: Optional[datetime] = Query(None, description="End date filter"),
    min_amount_usd: Optional[float] = Query(None, description="Minimum USD amount"),
    max_amount_usd: Optional[float] = Query(None, description="Maximum USD amount"),
    ai_generated: Optional[bool] = Query(None, description="Filter AI-generated transactions"),
    search: Optional[str] = Query(None, description="Search in notes and signatures"),
    sort_by: str = Query("timestamp", description="Sort field"),
    sort_order: str = Query("desc", description="Sort order (asc/desc)"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page"),
    db: Session = Depends(get_db)
):
    """
    List transactions with filtering, sorting, and pagination.

    Supports comprehensive filtering:
    - Wallet address
    - Transaction type (buy, sell, swap, etc.)
    - Status (pending, confirmed, failed)
    - Token symbol
    - Date range
    - USD amount range
    - AI-generated flag
    - Full-text search

    Returns:
        Paginated list of transactions
    """
    query = db.query(Transaction)

    # Apply filters
    if wallet_address:
        query = query.filter(Transaction.wallet_address == wallet_address)

    if transaction_type:
        query = query.filter(Transaction.transaction_type == transaction_type.value)

    if status:
        query = query.filter(Transaction.status == status.value)

    if token_symbol:
        # Search in both regular token and swap tokens
        query = query.filter(
            or_(
                Transaction.token_symbol == token_symbol,
                Transaction.from_token_symbol == token_symbol,
                Transaction.to_token_symbol == token_symbol
            )
        )

    if from_date:
        query = query.filter(Transaction.timestamp >= from_date)

    if to_date:
        query = query.filter(Transaction.timestamp <= to_date)

    if min_amount_usd is not None:
        query = query.filter(Transaction.amount_usd >= min_amount_usd)

    if max_amount_usd is not None:
        query = query.filter(Transaction.amount_usd <= max_amount_usd)

    if ai_generated is not None:
        query = query.filter(Transaction.ai_generated == ai_generated)

    if search:
        search_pattern = f"%{search}%"
        query = query.filter(
            or_(
                Transaction.signature.ilike(search_pattern),
                Transaction.notes.ilike(search_pattern),
                Transaction.token_symbol.ilike(search_pattern)
            )
        )

    # Get total count before pagination
    total = query.count()

    # Apply sorting
    sort_field = getattr(Transaction, sort_by, Transaction.timestamp)
    if sort_order == "desc":
        query = query.order_by(desc(sort_field))
    else:
        query = query.order_by(asc(sort_field))

    # Apply pagination
    offset = (page - 1) * page_size
    transactions = query.offset(offset).limit(page_size).all()

    # Calculate total pages
    total_pages = (total + page_size - 1) // page_size

    return {
        "transactions": [t.to_dict() for t in transactions],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages
    }


@router.get("/{transaction_id}", response_model=TransactionResponse)
async def get_transaction(
    transaction_id: int,
    db: Session = Depends(get_db)
):
    """
    Get a specific transaction by ID.

    Args:
        transaction_id: Transaction ID
        db: Database session

    Returns:
        Transaction details

    Raises:
        HTTPException: If transaction not found
    """
    transaction = db.query(Transaction).filter(Transaction.id == transaction_id).first()
    if not transaction:
        raise HTTPException(status_code=404, detail=f"Transaction {transaction_id} not found")

    return transaction.to_dict()


@router.get("/signature/{signature}", response_model=TransactionResponse)
async def get_transaction_by_signature(
    signature: str,
    db: Session = Depends(get_db)
):
    """
    Get a transaction by Solana signature.

    Args:
        signature: Solana transaction signature
        db: Database session

    Returns:
        Transaction details

    Raises:
        HTTPException: If transaction not found
    """
    transaction = db.query(Transaction).filter(Transaction.signature == signature).first()
    if not transaction:
        raise HTTPException(status_code=404, detail=f"Transaction {signature[:8]}... not found")

    return transaction.to_dict()


@router.patch("/{transaction_id}", response_model=TransactionResponse)
async def update_transaction(
    transaction_id: int,
    update_data: TransactionUpdate,
    db: Session = Depends(get_db)
):
    """
    Update a transaction (typically status or notes).

    Args:
        transaction_id: Transaction ID
        update_data: Fields to update
        db: Database session

    Returns:
        Updated transaction

    Raises:
        HTTPException: If transaction not found
    """
    transaction = db.query(Transaction).filter(Transaction.id == transaction_id).first()
    if not transaction:
        raise HTTPException(status_code=404, detail=f"Transaction {transaction_id} not found")

    # Apply updates
    for field, value in update_data.model_dump(exclude_unset=True).items():
        setattr(transaction, field, value)

    try:
        db.commit()
        db.refresh(transaction)
        logger.info(f"Updated transaction {transaction_id}")
        return transaction.to_dict()
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to update transaction {transaction_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to update transaction")


@router.delete("/{transaction_id}", status_code=204)
async def delete_transaction(
    transaction_id: int,
    db: Session = Depends(get_db)
):
    """
    Delete a transaction.

    Args:
        transaction_id: Transaction ID
        db: Database session

    Raises:
        HTTPException: If transaction not found
    """
    transaction = db.query(Transaction).filter(Transaction.id == transaction_id).first()
    if not transaction:
        raise HTTPException(status_code=404, detail=f"Transaction {transaction_id} not found")

    try:
        db.delete(transaction)
        db.commit()
        logger.info(f"Deleted transaction {transaction_id}")
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to delete transaction {transaction_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete transaction")


@router.get("/stats/summary")
async def get_transaction_stats(
    wallet_address: Optional[str] = Query(None, description="Filter by wallet address"),
    from_date: Optional[datetime] = Query(None, description="Start date"),
    to_date: Optional[datetime] = Query(None, description="End date"),
    db: Session = Depends(get_db)
):
    """
    Get transaction statistics and summary.

    Returns:
        - Total transactions
        - Total volume (USD)
        - Transaction counts by type
        - Total fees paid
        - Average transaction size
        - Success rate
    """
    query = db.query(Transaction)

    if wallet_address:
        query = query.filter(Transaction.wallet_address == wallet_address)

    if from_date:
        query = query.filter(Transaction.timestamp >= from_date)

    if to_date:
        query = query.filter(Transaction.timestamp <= to_date)

    transactions = query.all()

    # Calculate statistics
    total_count = len(transactions)
    total_volume_usd = sum(t.amount_usd or 0 for t in transactions)
    total_fees_sol = sum(t.fee_sol or 0 for t in transactions)
    total_fees_usd = sum(t.fee_usd or 0 for t in transactions)

    # Count by type
    type_counts = {}
    for t in transactions:
        tx_type = t.transaction_type.value if t.transaction_type else "unknown"
        type_counts[tx_type] = type_counts.get(tx_type, 0) + 1

    # Count by status
    status_counts = {}
    for t in transactions:
        tx_status = t.status.value if t.status else "unknown"
        status_counts[tx_status] = status_counts.get(tx_status, 0) + 1

    # Success rate
    confirmed_count = status_counts.get("confirmed", 0)
    success_rate = (confirmed_count / total_count * 100) if total_count > 0 else 0

    # Average transaction size
    avg_transaction_usd = total_volume_usd / total_count if total_count > 0 else 0

    return {
        "total_transactions": total_count,
        "total_volume_usd": round(total_volume_usd, 2),
        "total_fees_sol": round(total_fees_sol, 6),
        "total_fees_usd": round(total_fees_usd, 2),
        "avg_transaction_usd": round(avg_transaction_usd, 2),
        "success_rate": round(success_rate, 2),
        "transactions_by_type": type_counts,
        "transactions_by_status": status_counts
    }
