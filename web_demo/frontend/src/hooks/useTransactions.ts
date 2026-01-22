/**
 * Transaction Management Hook
 * Provides transaction data with filtering, sorting, and pagination.
 */
import { useState, useEffect, useCallback } from 'react';
import { transactionService } from '../services/transactionService';
import {
  Transaction,
  TransactionFilters,
  TransactionListResponse,
  TransactionStats
} from '../types/transaction';

export interface UseTransactionsReturn {
  transactions: Transaction[];
  stats: TransactionStats | null;
  loading: boolean;
  error: string | null;
  pagination: {
    page: number;
    pageSize: number;
    total: number;
    totalPages: number;
  };
  filters: TransactionFilters;
  setFilters: (filters: TransactionFilters) => void;
  nextPage: () => void;
  prevPage: () => void;
  goToPage: (page: number) => void;
  setPageSize: (size: number) => void;
  refresh: () => Promise<void>;
}

export const useTransactions = (
  initialFilters: TransactionFilters = {},
  autoLoad = true
): UseTransactionsReturn => {
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [stats, setStats] = useState<TransactionStats | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [filters, setFilters] = useState<TransactionFilters>({
    page: 1,
    page_size: 50,
    sort_by: 'timestamp',
    sort_order: 'desc',
    ...initialFilters
  });
  const [pagination, setPagination] = useState({
    page: 1,
    pageSize: 50,
    total: 0,
    totalPages: 0
  });

  const fetchTransactions = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const response: TransactionListResponse = await transactionService.listTransactions(filters);
      setTransactions(response.transactions);
      setPagination({
        page: response.page,
        pageSize: response.page_size,
        total: response.total,
        totalPages: response.total_pages
      });
    } catch (err: any) {
      setError(err.message || 'Failed to fetch transactions');
      setTransactions([]);
    } finally {
      setLoading(false);
    }
  }, [filters]);

  const fetchStats = useCallback(async () => {
    try {
      const statsData = await transactionService.getStats(filters);
      setStats(statsData);
    } catch (err: any) {
      console.error('Failed to fetch stats:', err);
    }
  }, [filters]);

  useEffect(() => {
    if (autoLoad) {
      fetchTransactions();
      fetchStats();
    }
  }, [fetchTransactions, fetchStats, autoLoad]);

  const nextPage = useCallback(() => {
    if (pagination.page < pagination.totalPages) {
      setFilters(prev => ({ ...prev, page: (prev.page || 1) + 1 }));
    }
  }, [pagination]);

  const prevPage = useCallback(() => {
    if (pagination.page > 1) {
      setFilters(prev => ({ ...prev, page: (prev.page || 1) - 1 }));
    }
  }, [pagination]);

  const goToPage = useCallback((page: number) => {
    if (page >= 1 && page <= pagination.totalPages) {
      setFilters(prev => ({ ...prev, page }));
    }
  }, [pagination]);

  const setPageSize = useCallback((size: number) => {
    setFilters(prev => ({ ...prev, page_size: size, page: 1 }));
  }, []);

  const refresh = useCallback(async () => {
    await fetchTransactions();
    await fetchStats();
  }, [fetchTransactions, fetchStats]);

  return {
    transactions,
    stats,
    loading,
    error,
    pagination,
    filters,
    setFilters,
    nextPage,
    prevPage,
    goToPage,
    setPageSize,
    refresh
  };
};
