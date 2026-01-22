/**
 * Transaction Types
 * TypeScript interfaces matching backend schemas
 */

export enum TransactionType {
  BUY = 'buy',
  SELL = 'sell',
  SWAP = 'swap',
  TRANSFER_IN = 'transfer_in',
  TRANSFER_OUT = 'transfer_out'
}

export enum TransactionStatus {
  PENDING = 'pending',
  CONFIRMED = 'confirmed',
  FAILED = 'failed'
}

export interface Transaction {
  id: number;
  signature: string;
  wallet_address: string;
  transaction_type: TransactionType;
  status: TransactionStatus;

  // Token information
  token_address?: string;
  token_symbol?: string;
  token_name?: string;

  // Amounts
  amount: number;
  amount_usd?: number;
  price_per_token?: number;

  // Fees
  fee_sol?: number;
  fee_usd?: number;

  // Swap specific
  from_token_address?: string;
  from_token_symbol?: string;
  from_amount?: number;
  to_token_address?: string;
  to_token_symbol?: string;
  to_amount?: number;

  // Metadata
  timestamp?: string;
  block_number?: number;
  notes?: string;
  ai_generated: boolean;

  // Audit fields
  created_at?: string;
  updated_at?: string;
}

export interface TransactionCreate {
  signature: string;
  wallet_address: string;
  transaction_type: TransactionType;
  status?: TransactionStatus;

  token_address?: string;
  token_symbol?: string;
  token_name?: string;

  amount: number;
  amount_usd?: number;
  price_per_token?: number;

  fee_sol?: number;
  fee_usd?: number;

  from_token_address?: string;
  from_token_symbol?: string;
  from_amount?: number;
  to_token_address?: string;
  to_token_symbol?: string;
  to_amount?: number;

  timestamp?: string;
  block_number?: number;
  notes?: string;
  ai_generated?: boolean;
}

export interface TransactionUpdate {
  status?: TransactionStatus;
  notes?: string;
  block_number?: number;
}

export interface TransactionListResponse {
  transactions: Transaction[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface TransactionFilters {
  wallet_address?: string;
  transaction_type?: TransactionType;
  status?: TransactionStatus;
  token_symbol?: string;
  from_date?: Date;
  to_date?: Date;
  min_amount_usd?: number;
  max_amount_usd?: number;
  ai_generated?: boolean;
  search?: string;
  sort_by?: string;
  sort_order?: 'asc' | 'desc';
  page?: number;
  page_size?: number;
}

export interface TransactionStats {
  total_transactions: number;
  total_volume_usd: number;
  total_fees_sol: number;
  total_fees_usd: number;
  avg_transaction_usd: number;
  success_rate: number;
  transactions_by_type: Record<string, number>;
  transactions_by_status: Record<string, number>;
}
