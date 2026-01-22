/**
 * Transaction API Service
 * Handles all transaction-related API calls.
 */
import {
  Transaction,
  TransactionCreate,
  TransactionUpdate,
  TransactionListResponse,
  TransactionFilters,
  TransactionStats
} from '../types/transaction';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
const API_V1_PREFIX = '/api/v1';

class TransactionService {
  private baseUrl: string;

  constructor() {
    this.baseUrl = `${API_BASE_URL}${API_V1_PREFIX}/transactions`;
  }

  /**
   * Build query string from filters
   */
  private buildQueryString(filters: TransactionFilters): string {
    const params = new URLSearchParams();

    Object.entries(filters).forEach(([key, value]) => {
      if (value !== undefined && value !== null) {
        if (value instanceof Date) {
          params.append(key, value.toISOString());
        } else {
          params.append(key, String(value));
        }
      }
    });

    return params.toString();
  }

  /**
   * List transactions with filtering and pagination
   */
  async listTransactions(filters: TransactionFilters = {}): Promise<TransactionListResponse> {
    const queryString = this.buildQueryString(filters);
    const url = queryString ? `${this.baseUrl}?${queryString}` : this.baseUrl;

    const response = await fetch(url, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json'
      }
    });

    if (!response.ok) {
      throw new Error(`Failed to fetch transactions: ${response.statusText}`);
    }

    return response.json();
  }

  /**
   * Get a specific transaction by ID
   */
  async getTransaction(id: number): Promise<Transaction> {
    const response = await fetch(`${this.baseUrl}/${id}`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json'
      }
    });

    if (!response.ok) {
      throw new Error(`Failed to fetch transaction: ${response.statusText}`);
    }

    return response.json();
  }

  /**
   * Get transaction by Solana signature
   */
  async getTransactionBySignature(signature: string): Promise<Transaction> {
    const response = await fetch(`${this.baseUrl}/signature/${signature}`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json'
      }
    });

    if (!response.ok) {
      throw new Error(`Failed to fetch transaction: ${response.statusText}`);
    }

    return response.json();
  }

  /**
   * Create a new transaction
   */
  async createTransaction(transaction: TransactionCreate): Promise<Transaction> {
    const response = await fetch(this.baseUrl, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(transaction)
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Failed to create transaction');
    }

    return response.json();
  }

  /**
   * Update a transaction
   */
  async updateTransaction(id: number, update: TransactionUpdate): Promise<Transaction> {
    const response = await fetch(`${this.baseUrl}/${id}`, {
      method: 'PATCH',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(update)
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Failed to update transaction');
    }

    return response.json();
  }

  /**
   * Delete a transaction
   */
  async deleteTransaction(id: number): Promise<void> {
    const response = await fetch(`${this.baseUrl}/${id}`, {
      method: 'DELETE'
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Failed to delete transaction');
    }
  }

  /**
   * Get transaction statistics
   */
  async getStats(filters: Partial<TransactionFilters> = {}): Promise<TransactionStats> {
    const params = new URLSearchParams();

    if (filters.wallet_address) params.append('wallet_address', filters.wallet_address);
    if (filters.from_date) params.append('from_date', filters.from_date.toISOString());
    if (filters.to_date) params.append('to_date', filters.to_date.toISOString());

    const queryString = params.toString();
    const url = queryString
      ? `${this.baseUrl}/stats/summary?${queryString}`
      : `${this.baseUrl}/stats/summary`;

    const response = await fetch(url, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json'
      }
    });

    if (!response.ok) {
      throw new Error(`Failed to fetch stats: ${response.statusText}`);
    }

    return response.json();
  }
}

export const transactionService = new TransactionService();
