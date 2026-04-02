# Transaction History Tracking - Complete Guide

## Overview

The JARVIS Web Demo now includes **comprehensive transaction history tracking** with filtering, sorting, pagination, and real-time statistics. All wallet transactions (buys, sells, swaps, transfers) are stored in a database for analytics and auditing.

## Architecture

```
┌─────────────────┐
│  Solana Wallet  │
└────────┬────────┘
         │ Transactions
         ▼
┌─────────────────┐
│  FastAPI Backend│──> SQLAlchemy Models
└────────┬────────┘       │
         │                ▼
         │         ┌──────────────┐
         │         │   Database   │
         │         │  (SQLite/    │
         │         │  PostgreSQL) │
         │         └──────────────┘
         │
         │ REST API
         ▼
┌─────────────────┐
│ React Frontend  │──> Transaction History UI
└─────────────────┘       │
                          ▼
                   Filter, Sort, Export
```

## Database Schema

### Transaction Model

| Field | Type | Description |
|-------|------|-------------|
| `id` | Integer | Unique transaction ID (auto-increment) |
| `signature` | String(128) | Solana transaction signature (unique, indexed) |
| `wallet_address` | String(64) | User's wallet address (indexed) |
| `transaction_type` | Enum | buy, sell, swap, transfer_in, transfer_out |
| `status` | Enum | pending, confirmed, failed |
| `token_address` | String(64) | Token mint address |
| `token_symbol` | String(20) | Token symbol (e.g., SOL, USDC) |
| `token_name` | String(100) | Full token name |
| `amount` | Float | Token amount |
| `amount_usd` | Float | USD value at transaction time |
| `price_per_token` | Float | Price per token in USD |
| `fee_sol` | Float | Network fee in SOL |
| `fee_usd` | Float | Network fee in USD |
| `from_token_address` | String(64) | Source token for swaps |
| `from_token_symbol` | String(20) | Source token symbol |
| `from_amount` | Float | Source token amount |
| `to_token_address` | String(64) | Destination token for swaps |
| `to_token_symbol` | String(20) | Destination token symbol |
| `to_amount` | Float | Destination token amount |
| `timestamp` | DateTime | When transaction occurred |
| `block_number` | Integer | Solana block number |
| `notes` | Text | Optional user notes |
| `ai_generated` | Boolean | Whether AI-recommended |
| `created_at` | DateTime | Record creation time |
| `updated_at` | DateTime | Last update time |

## Backend Setup

### 1. Database Configuration

The system supports both SQLite (development) and PostgreSQL (production).

**Default (SQLite)**:
```bash
DATABASE_URL=sqlite:///./jarvis_demo.db
```

**Production (PostgreSQL)**:
```bash
DATABASE_URL=postgresql://postgres:password@localhost:5432/jarvis_demo
```

Add to `web_demo/.env`:
```env
DATABASE_URL=sqlite:///./jarvis_demo.db  # or PostgreSQL URL
```

### 2. Database Initialization

The database tables are automatically created on app startup via [`backend/app/main.py:54`](backend/app/main.py#L54):

```python
# Initialize database connection pool and create tables
init_db()
logger.info("✓ Database initialized successfully")
```

No manual migration steps required - tables are created automatically.

### 3. API Endpoints

All endpoints are prefixed with `/api/v1/transactions`:

#### **POST /api/v1/transactions**
Create a new transaction.

**Request Body**:
```json
{
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
```

#### **GET /api/v1/transactions**
List transactions with filtering and pagination.

**Query Parameters**:
- `wallet_address` - Filter by wallet
- `transaction_type` - Filter by type (buy, sell, swap, etc.)
- `status` - Filter by status (pending, confirmed, failed)
- `token_symbol` - Filter by token (checks all token fields)
- `from_date` - Start date (ISO 8601)
- `to_date` - End date (ISO 8601)
- `min_amount_usd` - Minimum USD amount
- `max_amount_usd` - Maximum USD amount
- `ai_generated` - Filter AI-generated transactions
- `search` - Full-text search (signature, notes, symbols)
- `sort_by` - Sort field (default: timestamp)
- `sort_order` - Sort order: asc/desc (default: desc)
- `page` - Page number (default: 1)
- `page_size` - Items per page (default: 50, max: 100)

**Example**:
```bash
GET /api/v1/transactions?wallet_address=7xKXtg...&token_symbol=SOL&sort_order=desc&page=1&page_size=50
```

**Response**:
```json
{
  "transactions": [
    {
      "id": 1,
      "signature": "5VPy7RqL...",
      "transaction_type": "swap",
      "status": "confirmed",
      "amount": 10.5,
      "amount_usd": 1314.91,
      "timestamp": "2026-01-22T14:30:00Z",
      ...
    }
  ],
  "total": 152,
  "page": 1,
  "page_size": 50,
  "total_pages": 4
}
```

#### **GET /api/v1/transactions/{id}**
Get a specific transaction by ID.

#### **GET /api/v1/transactions/signature/{signature}**
Get a transaction by Solana signature.

#### **PATCH /api/v1/transactions/{id}**
Update a transaction (status, notes, block_number).

**Request Body**:
```json
{
  "status": "confirmed",
  "block_number": 123456,
  "notes": "Updated status from pending"
}
```

#### **DELETE /api/v1/transactions/{id}**
Delete a transaction.

#### **GET /api/v1/transactions/stats/summary**
Get transaction statistics.

**Query Parameters**:
- `wallet_address` - Filter by wallet
- `from_date` - Start date
- `to_date` - End date

**Response**:
```json
{
  "total_transactions": 152,
  "total_volume_usd": 250000.50,
  "total_fees_sol": 0.015,
  "total_fees_usd": 1.89,
  "avg_transaction_usd": 1644.74,
  "success_rate": 98.68,
  "transactions_by_type": {
    "swap": 85,
    "buy": 42,
    "sell": 25
  },
  "transactions_by_status": {
    "confirmed": 150,
    "pending": 1,
    "failed": 1
  }
}
```

## Frontend Usage

### 1. Using the TransactionHistory Component

```typescript
import { TransactionHistory } from './components/Transaction';

const Dashboard = () => {
  return (
    <div>
      <h1>My Portfolio</h1>
      {/* Full transaction history with filters */}
      <TransactionHistory walletAddress="7xKXtg..." />
    </div>
  );
};
```

### 2. Compact Mode

```typescript
<TransactionHistory walletAddress="7xKXtg..." compact />
```

### 3. Using the Hook Directly

```typescript
import { useTransactions } from '../hooks/useTransactions';

const MyComponent = () => {
  const {
    transactions,
    stats,
    loading,
    error,
    filters,
    setFilters,
    refresh
  } = useTransactions({
    wallet_address: '7xKXtg...',
    transaction_type: 'swap',
    sort_order: 'desc'
  });

  return (
    <div>
      {stats && (
        <div>Total Volume: ${stats.total_volume_usd}</div>
      )}
      {transactions.map(tx => (
        <div key={tx.id}>{tx.signature}</div>
      ))}
    </div>
  );
};
```

## Recording Transactions

### Automatic Recording (Recommended)

When a swap/trade is executed, automatically create a transaction record:

```typescript
import { transactionService } from '../services/transactionService';

const executeSwap = async (from, to, amount) => {
  // Execute swap via Jupiter/Bags API
  const result = await jupiterSwap(from, to, amount);

  // Record transaction
  await transactionService.createTransaction({
    signature: result.signature,
    wallet_address: userWallet,
    transaction_type: 'swap',
    status: 'pending',
    from_token_symbol: from.symbol,
    from_token_address: from.address,
    from_amount: amount,
    to_token_symbol: to.symbol,
    to_token_address: to.address,
    to_amount: result.outputAmount,
    amount: result.outputAmount,
    amount_usd: result.outputAmount * to.priceUSD,
    fee_sol: result.fee,
    timestamp: new Date().toISOString()
  });

  // Later, confirm the transaction
  await transactionService.updateTransaction(txId, {
    status: 'confirmed',
    block_number: confirmedBlock
  });
};
```

### Manual Recording

```typescript
import { transactionService } from '../services/transactionService';

const recordManualSwap = async () => {
  const tx = await transactionService.createTransaction({
    signature: '5VPy7RqLExF4K7f9N1qGtBNB1q3H9hK8Lf4J3G5H2K9...',
    wallet_address: '7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU',
    transaction_type: 'buy',
    status: 'confirmed',
    token_symbol: 'SOL',
    token_address: 'So11111111111111111111111111111111111111112',
    amount: 10.5,
    amount_usd: 1314.91,
    price_per_token: 125.23,
    fee_sol: 0.000005
  });
};
```

## Filtering Examples

### Filter by Transaction Type

```typescript
setFilters({ transaction_type: 'swap' });
```

### Filter by Date Range

```typescript
setFilters({
  from_date: new Date('2026-01-01'),
  to_date: new Date('2026-01-31')
});
```

### Filter by Amount Range

```typescript
setFilters({
  min_amount_usd: 100,
  max_amount_usd: 10000
});
```

### Search by Signature or Notes

```typescript
setFilters({ search: '5VPy7RqL' });
```

### AI-Generated Transactions Only

```typescript
setFilters({ ai_generated: true });
```

## Export Functionality

(Coming Soon)

Export transactions to CSV:

```typescript
const exportTransactions = async () => {
  const { transactions } = await transactionService.listTransactions(filters);

  // Convert to CSV
  const csv = convertToCSV(transactions);

  // Download
  downloadFile(csv, 'transactions.csv');
};
```

## Performance Considerations

### Indexing

The database has indexes on:
- `signature` (unique)
- `wallet_address`
- `transaction_type`
- `timestamp`

These ensure fast filtering and sorting.

### Pagination

Default page size is 50 transactions. Maximum is 100.

For large datasets, use pagination:
```typescript
const { transactions, pagination } = useTransactions({
  page: 1,
  page_size: 50
});
```

### Caching

Consider implementing client-side caching for frequently accessed data:

```typescript
const cache = new Map();

const getCachedTransactions = async (filters) => {
  const key = JSON.stringify(filters);
  if (cache.has(key)) return cache.get(key);

  const data = await transactionService.listTransactions(filters);
  cache.set(key, data);
  return data;
};
```

## Security

### Input Validation

All inputs are validated server-side using Pydantic:
- Signature length: 64-128 characters
- Wallet address length: 32-64 characters
- Amount: Must be positive
- Transaction type: Must be valid enum value

### SQL Injection Protection

SQLAlchemy ORM protects against SQL injection automatically.

### Authorization

(To be implemented)

Ensure users can only:
- View their own transactions
- Create transactions for their own wallet
- Update/delete their own transactions

## Monitoring

### Check Transaction Count

```bash
curl http://localhost:8000/api/v1/transactions/stats/summary
```

### View Recent Transactions

```bash
curl "http://localhost:8000/api/v1/transactions?page=1&page_size=10&sort_order=desc"
```

### Database Inspection

**SQLite**:
```bash
sqlite3 jarvis_demo.db
SELECT COUNT(*) FROM transactions;
SELECT * FROM transactions LIMIT 10;
```

**PostgreSQL**:
```bash
psql -U postgres -d jarvis_demo
SELECT COUNT(*) FROM transactions;
SELECT * FROM transactions LIMIT 10;
```

## Troubleshooting

### Transactions Not Appearing

1. Check database connection:
   ```bash
   curl http://localhost:8000/health
   ```

2. Verify transaction was created:
   ```bash
   curl http://localhost:8000/api/v1/transactions/signature/<signature>
   ```

3. Check backend logs for errors

### Duplicate Signature Error

If you get "Transaction already exists", the signature has been used:
```json
{
  "detail": "Transaction 5VPy7RqL... already exists"
}
```

Solution: Check if transaction exists first, or use PATCH to update it.

### Pagination Not Working

Ensure `page` and `page_size` are provided:
```typescript
setFilters({ page: 1, page_size: 50 });
```

## API Reference

See [`backend/app/routes/transactions.py`](backend/app/routes/transactions.py) for complete API implementation.

## Future Enhancements

Planned for next iterations:
- [ ] Real-time transaction sync from Solana blockchain
- [ ] CSV/Excel export
- [ ] Transaction categorization (manual tagging)
- [ ] P&L calculation per transaction
- [ ] Tax reporting (Form 8949 generation)
- [ ] Transaction analytics dashboard
- [ ] Automatic status updates via WebSocket
- [ ] Multi-wallet support
- [ ] Advanced filtering (token categories, profit range)

---

**Questions?** Check the main documentation at [IMPLEMENTATION_COMPLETE.md](IMPLEMENTATION_COMPLETE.md)
