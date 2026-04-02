/**
 * Transaction History Component
 * Displays comprehensive transaction history with filtering and sorting.
 */
import React, { useState } from 'react';
import { format } from 'date-fns';
import {
  ArrowUpRight,
  ArrowDownRight,
  RefreshCw,
  Download,
  Filter,
  Search,
  ChevronLeft,
  ChevronRight,
  ExternalLink,
  TrendingUp,
  TrendingDown
} from 'lucide-react';
import clsx from 'clsx';
import { useTransactions } from '../../hooks/useTransactions';
import { Transaction, TransactionType, TransactionStatus } from '../../types/transaction';
import { GlassCard } from '../UI/GlassCard';

interface TransactionHistoryProps {
  walletAddress?: string;
  compact?: boolean;
}

const TransactionRow: React.FC<{ transaction: Transaction; compact?: boolean }> = ({
  transaction,
  compact
}) => {
  const getTypeIcon = () => {
    switch (transaction.transaction_type) {
      case TransactionType.BUY:
        return <ArrowUpRight className="text-success" size={16} />;
      case TransactionType.SELL:
        return <ArrowDownRight className="text-error" size={16} />;
      case TransactionType.SWAP:
        return <RefreshCw className="text-info" size={16} />;
      case TransactionType.TRANSFER_IN:
        return <TrendingUp className="text-success" size={16} />;
      case TransactionType.TRANSFER_OUT:
        return <TrendingDown className="text-error" size={16} />;
      default:
        return null;
    }
  };

  const getStatusBadge = () => {
    const statusColors = {
      [TransactionStatus.CONFIRMED]: 'bg-success/20 text-success',
      [TransactionStatus.PENDING]: 'bg-warning/20 text-warning',
      [TransactionStatus.FAILED]: 'bg-error/20 text-error'
    };

    return (
      <span className={clsx('px-2 py-0.5 rounded-full text-xs font-semibold', statusColors[transaction.status])}>
        {transaction.status}
      </span>
    );
  };

  const formatDate = (dateString?: string) => {
    if (!dateString) return '-';
    return format(new Date(dateString), 'MMM d, yyyy HH:mm');
  };

  const getTokenDisplay = () => {
    if (transaction.transaction_type === TransactionType.SWAP) {
      return (
        <div className="flex items-center gap-2">
          <span className="font-semibold">{transaction.from_token_symbol}</span>
          <span className="text-muted">→</span>
          <span className="font-semibold">{transaction.to_token_symbol}</span>
        </div>
      );
    }
    return transaction.token_symbol || '-';
  };

  const getAmountDisplay = () => {
    if (transaction.transaction_type === TransactionType.SWAP) {
      return (
        <div className="text-right">
          <div className="font-mono text-sm">{transaction.from_amount?.toFixed(4)} → {transaction.to_amount?.toFixed(4)}</div>
          {transaction.amount_usd && (
            <div className="text-xs text-muted">${transaction.amount_usd.toLocaleString('en-US', { minimumFractionDigits: 2 })}</div>
          )}
        </div>
      );
    }

    return (
      <div className="text-right">
        <div className="font-mono text-sm">{transaction.amount.toFixed(4)}</div>
        {transaction.amount_usd && (
          <div className="text-xs text-muted">${transaction.amount_usd.toLocaleString('en-US', { minimumFractionDigits: 2 })}</div>
        )}
      </div>
    );
  };

  if (compact) {
    return (
      <div className="flex items-center justify-between p-2 hover:bg-surface/50 rounded-lg transition-colors">
        <div className="flex items-center gap-2">
          {getTypeIcon()}
          <span className="font-semibold text-sm">{getTokenDisplay()}</span>
        </div>
        <div className="text-right">
          {getAmountDisplay()}
          {getStatusBadge()}
        </div>
      </div>
    );
  }

  return (
    <tr className="hover:bg-surface/50 transition-colors">
      <td className="px-4 py-3">
        <div className="flex items-center gap-2">
          {getTypeIcon()}
          <span className="text-xs text-muted capitalize">{transaction.transaction_type.replace('_', ' ')}</span>
        </div>
      </td>
      <td className="px-4 py-3">
        <div className="flex items-center gap-2">
          <code className="text-xs bg-surface px-2 py-1 rounded">
            {transaction.signature.slice(0, 8)}...{transaction.signature.slice(-4)}
          </code>
          <a
            href={`https://solscan.io/tx/${transaction.signature}`}
            target="_blank"
            rel="noopener noreferrer"
            className="text-accent hover:text-accent-hover"
          >
            <ExternalLink size={12} />
          </a>
        </div>
      </td>
      <td className="px-4 py-3">{getTokenDisplay()}</td>
      <td className="px-4 py-3">{getAmountDisplay()}</td>
      <td className="px-4 py-3 text-xs text-muted">{formatDate(transaction.timestamp)}</td>
      <td className="px-4 py-3">{getStatusBadge()}</td>
      <td className="px-4 py-3 text-right">
        {transaction.fee_sol && (
          <div className="text-xs text-muted">
            ◎ {transaction.fee_sol.toFixed(6)}
          </div>
        )}
      </td>
    </tr>
  );
};

export const TransactionHistory: React.FC<TransactionHistoryProps> = ({
  walletAddress,
  compact = false
}) => {
  const [searchQuery, setSearchQuery] = useState('');
  const [showFilters, setShowFilters] = useState(false);

  const {
    transactions,
    stats,
    loading,
    error,
    pagination,
    filters,
    setFilters,
    nextPage,
    prevPage,
    refresh
  } = useTransactions({ wallet_address: walletAddress });

  const handleSearch = (query: string) => {
    setSearchQuery(query);
    setFilters({ ...filters, search: query, page: 1 });
  };

  const handleTypeFilter = (type: TransactionType | undefined) => {
    setFilters({ ...filters, transaction_type: type, page: 1 });
  };

  const handleStatusFilter = (status: TransactionStatus | undefined) => {
    setFilters({ ...filters, status, page: 1 });
  };

  if (error) {
    return (
      <GlassCard className="p-6">
        <div className="text-error">Error loading transactions: {error}</div>
      </GlassCard>
    );
  }

  return (
    <GlassCard className="overflow-hidden">
      {/* Header */}
      <div className="p-6 border-b border-border">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-2xl font-display font-bold">Transaction History</h2>
            {stats && (
              <div className="text-sm text-muted mt-1">
                {stats.total_transactions} transactions · ${stats.total_volume_usd.toLocaleString()} volume
              </div>
            )}
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setShowFilters(!showFilters)}
              className={clsx(
                'btn btn-secondary flex items-center gap-2',
                showFilters && 'bg-accent text-bg-dark'
              )}
            >
              <Filter size={16} />
              Filters
            </button>
            <button onClick={refresh} className="btn btn-secondary flex items-center gap-2">
              <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
              Refresh
            </button>
            <button className="btn btn-secondary flex items-center gap-2">
              <Download size={16} />
              Export
            </button>
          </div>
        </div>

        {/* Search */}
        <div className="relative">
          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-muted" size={16} />
          <input
            type="text"
            placeholder="Search transactions..."
            value={searchQuery}
            onChange={(e) => handleSearch(e.target.value)}
            className="w-full pl-10 pr-4 py-2 bg-surface border border-border rounded-lg focus:outline-none focus:border-accent"
          />
        </div>

        {/* Filters */}
        {showFilters && (
          <div className="mt-4 grid grid-cols-4 gap-4">
            <div>
              <label className="text-xs text-muted mb-1 block">Type</label>
              <select
                value={filters.transaction_type || ''}
                onChange={(e) => handleTypeFilter(e.target.value as TransactionType || undefined)}
                className="w-full px-3 py-2 bg-surface border border-border rounded-lg text-sm"
              >
                <option value="">All Types</option>
                <option value={TransactionType.BUY}>Buy</option>
                <option value={TransactionType.SELL}>Sell</option>
                <option value={TransactionType.SWAP}>Swap</option>
                <option value={TransactionType.TRANSFER_IN}>Transfer In</option>
                <option value={TransactionType.TRANSFER_OUT}>Transfer Out</option>
              </select>
            </div>
            <div>
              <label className="text-xs text-muted mb-1 block">Status</label>
              <select
                value={filters.status || ''}
                onChange={(e) => handleStatusFilter(e.target.value as TransactionStatus || undefined)}
                className="w-full px-3 py-2 bg-surface border border-border rounded-lg text-sm"
              >
                <option value="">All Status</option>
                <option value={TransactionStatus.CONFIRMED}>Confirmed</option>
                <option value={TransactionStatus.PENDING}>Pending</option>
                <option value={TransactionStatus.FAILED}>Failed</option>
              </select>
            </div>
          </div>
        )}
      </div>

      {/* Table */}
      {loading ? (
        <div className="p-12 text-center text-muted">
          <RefreshCw className="animate-spin mx-auto mb-2" size={24} />
          Loading transactions...
        </div>
      ) : transactions.length === 0 ? (
        <div className="p-12 text-center text-muted">
          No transactions found
        </div>
      ) : compact ? (
        <div className="p-4 space-y-2">
          {transactions.map(tx => (
            <TransactionRow key={tx.id} transaction={tx} compact />
          ))}
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-surface/50 border-b border-border">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-semibold text-muted uppercase">Type</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-muted uppercase">Signature</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-muted uppercase">Token</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-muted uppercase">Amount</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-muted uppercase">Time</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-muted uppercase">Status</th>
                <th className="px-4 py-3 text-right text-xs font-semibold text-muted uppercase">Fee</th>
              </tr>
            </thead>
            <tbody>
              {transactions.map(tx => (
                <TransactionRow key={tx.id} transaction={tx} />
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Pagination */}
      {!loading && transactions.length > 0 && (
        <div className="p-4 border-t border-border flex items-center justify-between">
          <div className="text-sm text-muted">
            Showing {(pagination.page - 1) * pagination.pageSize + 1} to{' '}
            {Math.min(pagination.page * pagination.pageSize, pagination.total)} of {pagination.total} transactions
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={prevPage}
              disabled={pagination.page === 1}
              className="btn btn-secondary flex items-center gap-1 disabled:opacity-50"
            >
              <ChevronLeft size={16} />
              Previous
            </button>
            <span className="px-3 py-1 bg-surface rounded-lg text-sm">
              Page {pagination.page} of {pagination.totalPages}
            </span>
            <button
              onClick={nextPage}
              disabled={pagination.page === pagination.totalPages}
              className="btn btn-secondary flex items-center gap-1 disabled:opacity-50"
            >
              Next
              <ChevronRight size={16} />
            </button>
          </div>
        </div>
      )}
    </GlassCard>
  );
};
