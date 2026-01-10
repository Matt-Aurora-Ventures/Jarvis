/**
 * Usage History Component
 *
 * Shows credit transaction history:
 * - Purchases
 * - Usage (API calls)
 * - Refunds
 * - Bonus credits
 */

import React, { useState, useEffect } from 'react';

const API_BASE = '/api/credits';

// Transaction type icons and colors
const TRANSACTION_TYPES = {
  purchase: {
    icon: '💳',
    color: 'text-green-400',
    bgColor: 'bg-green-900/30',
    label: 'Purchase',
  },
  consumption: {
    icon: '⚡',
    color: 'text-blue-400',
    bgColor: 'bg-blue-900/30',
    label: 'Usage',
  },
  bonus: {
    icon: '🎁',
    color: 'text-yellow-400',
    bgColor: 'bg-yellow-900/30',
    label: 'Bonus',
  },
  refund: {
    icon: '↩️',
    color: 'text-purple-400',
    bgColor: 'bg-purple-900/30',
    label: 'Refund',
  },
  referral: {
    icon: '👥',
    color: 'text-pink-400',
    bgColor: 'bg-pink-900/30',
    label: 'Referral',
  },
  adjustment: {
    icon: '🔧',
    color: 'text-gray-400',
    bgColor: 'bg-gray-900/30',
    label: 'Adjustment',
  },
};

export default function UsageHistory({ userId }) {
  const [loading, setLoading] = useState(true);
  const [transactions, setTransactions] = useState([]);
  const [filter, setFilter] = useState('all');
  const [page, setPage] = useState(1);
  const [hasMore, setHasMore] = useState(false);
  const [stats, setStats] = useState({
    totalPurchased: 0,
    totalUsed: 0,
    totalBonus: 0,
  });

  // Fetch transactions
  useEffect(() => {
    const fetchHistory = async () => {
      setLoading(true);
      try {
        const params = new URLSearchParams({
          page: page.toString(),
          limit: '20',
        });
        if (filter !== 'all') {
          params.append('type', filter);
        }

        const response = await fetch(`${API_BASE}/history/${userId}?${params}`);
        if (response.ok) {
          const data = await response.json();
          setTransactions(data.transactions || []);
          setHasMore(data.has_more || false);
          setStats(data.stats || stats);
        }
      } catch (err) {
        console.error('Failed to fetch history:', err);
      } finally {
        setLoading(false);
      }
    };

    if (userId) {
      fetchHistory();
    }
  }, [userId, filter, page]);

  const handleFilterChange = (newFilter) => {
    setFilter(newFilter);
    setPage(1);
  };

  return (
    <div className="space-y-6">
      {/* Stats Summary */}
      <div className="grid grid-cols-3 gap-4">
        <StatCard
          label="Total Purchased"
          value={stats.totalPurchased}
          color="green"
          icon="💳"
        />
        <StatCard
          label="Total Used"
          value={stats.totalUsed}
          color="blue"
          icon="⚡"
        />
        <StatCard
          label="Bonus Earned"
          value={stats.totalBonus}
          color="yellow"
          icon="🎁"
        />
      </div>

      {/* Filter Tabs */}
      <div className="flex gap-2 flex-wrap">
        <FilterButton
          active={filter === 'all'}
          onClick={() => handleFilterChange('all')}
        >
          All
        </FilterButton>
        <FilterButton
          active={filter === 'purchase'}
          onClick={() => handleFilterChange('purchase')}
        >
          Purchases
        </FilterButton>
        <FilterButton
          active={filter === 'consumption'}
          onClick={() => handleFilterChange('consumption')}
        >
          Usage
        </FilterButton>
        <FilterButton
          active={filter === 'bonus'}
          onClick={() => handleFilterChange('bonus')}
        >
          Bonuses
        </FilterButton>
      </div>

      {/* Transaction List */}
      {loading ? (
        <div className="flex justify-center py-12">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"></div>
        </div>
      ) : transactions.length === 0 ? (
        <div className="text-center py-12">
          <div className="text-4xl mb-4">📋</div>
          <p className="text-gray-400">No transactions found</p>
          <p className="text-sm text-gray-500 mt-1">
            {filter !== 'all' ? 'Try selecting a different filter' : 'Purchase credits to get started'}
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {transactions.map((tx) => (
            <TransactionRow key={tx.id} transaction={tx} />
          ))}
        </div>
      )}

      {/* Pagination */}
      {!loading && transactions.length > 0 && (
        <div className="flex justify-between items-center pt-4 border-t border-gray-700">
          <button
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page === 1}
            className="px-4 py-2 bg-gray-700 rounded-lg text-white disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-600 transition-colors"
          >
            Previous
          </button>
          <span className="text-gray-400">Page {page}</span>
          <button
            onClick={() => setPage((p) => p + 1)}
            disabled={!hasMore}
            className="px-4 py-2 bg-gray-700 rounded-lg text-white disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-600 transition-colors"
          >
            Next
          </button>
        </div>
      )}
    </div>
  );
}

// Stat card component
function StatCard({ label, value, color, icon }) {
  const colorClasses = {
    green: 'text-green-400',
    blue: 'text-blue-400',
    yellow: 'text-yellow-400',
  };

  return (
    <div className="bg-gray-700/50 rounded-lg p-4">
      <div className="flex items-center gap-2 mb-2">
        <span className="text-lg">{icon}</span>
        <span className="text-sm text-gray-400">{label}</span>
      </div>
      <div className={`text-2xl font-bold ${colorClasses[color]}`}>
        {value.toLocaleString()}
      </div>
    </div>
  );
}

// Filter button component
function FilterButton({ children, active, onClick }) {
  return (
    <button
      onClick={onClick}
      className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
        active
          ? 'bg-blue-600 text-white'
          : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
      }`}
    >
      {children}
    </button>
  );
}

// Transaction row component
function TransactionRow({ transaction }) {
  const type = TRANSACTION_TYPES[transaction.type] || TRANSACTION_TYPES.adjustment;
  const isPositive = ['purchase', 'bonus', 'refund', 'referral'].includes(transaction.type);

  return (
    <div className={`flex items-center gap-4 p-4 rounded-lg ${type.bgColor}`}>
      {/* Icon */}
      <div className="text-2xl">{type.icon}</div>

      {/* Details */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className={`font-medium ${type.color}`}>{type.label}</span>
          {transaction.description && (
            <span className="text-gray-400 text-sm truncate">
              - {transaction.description}
            </span>
          )}
        </div>
        <div className="text-xs text-gray-500 mt-1">
          {new Date(transaction.created_at).toLocaleString()}
        </div>
      </div>

      {/* Amount */}
      <div className={`text-right ${isPositive ? 'text-green-400' : 'text-red-400'}`}>
        <div className="font-bold">
          {isPositive ? '+' : '-'}{Math.abs(transaction.amount).toLocaleString()}
        </div>
        <div className="text-xs text-gray-500">credits</div>
      </div>

      {/* Balance After */}
      <div className="text-right text-gray-400 hidden sm:block">
        <div className="text-sm">{transaction.balance_after?.toLocaleString()}</div>
        <div className="text-xs text-gray-500">balance</div>
      </div>
    </div>
  );
}
