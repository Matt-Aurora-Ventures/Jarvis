import React from 'react';
import { Wallet, TrendingUp, TrendingDown, RefreshCw } from 'lucide-react';

interface WalletBalance {
  address: string;
  name: string;
  type: 'hot' | 'cold' | 'multisig';
  balances: {
    token: string;
    amount: number;
    usdValue: number;
    change24h: number;
  }[];
  totalUsdValue: number;
}

interface WalletBalancesProps {
  wallets: WalletBalance[];
  isLoading?: boolean;
  onRefresh?: () => void;
}

export const WalletBalances: React.FC<WalletBalancesProps> = ({
  wallets,
  isLoading = false,
  onRefresh,
}) => {
  const totalValue = wallets.reduce((sum, w) => sum + w.totalUsdValue, 0);

  const formatUsd = (value: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(value);
  };

  const formatAmount = (value: number) => {
    if (value >= 1000000) {
      return `${(value / 1000000).toFixed(2)}M`;
    } else if (value >= 1000) {
      return `${(value / 1000).toFixed(2)}K`;
    }
    return value.toFixed(4);
  };

  const truncateAddress = (address: string) => {
    return `${address.slice(0, 4)}...${address.slice(-4)}`;
  };

  const getTypeColor = (type: WalletBalance['type']) => {
    switch (type) {
      case 'hot':
        return 'bg-orange-500/20 text-orange-400';
      case 'cold':
        return 'bg-blue-500/20 text-blue-400';
      case 'multisig':
        return 'bg-purple-500/20 text-purple-400';
    }
  };

  return (
    <div className="bg-gray-800 rounded-lg p-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-xl font-semibold text-white">Treasury Wallets</h2>
          <p className="text-gray-400 text-sm mt-1">
            Total Value: {formatUsd(totalValue)}
          </p>
        </div>
        {onRefresh && (
          <button
            onClick={onRefresh}
            disabled={isLoading}
            className="p-2 rounded-lg bg-gray-700 hover:bg-gray-600 transition-colors disabled:opacity-50"
          >
            <RefreshCw className={`w-5 h-5 text-gray-300 ${isLoading ? 'animate-spin' : ''}`} />
          </button>
        )}
      </div>

      <div className="space-y-4">
        {wallets.map((wallet) => (
          <div
            key={wallet.address}
            className="bg-gray-700/50 rounded-lg p-4"
          >
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-gray-600 rounded-lg">
                  <Wallet className="w-5 h-5 text-gray-300" />
                </div>
                <div>
                  <h3 className="text-white font-medium">{wallet.name}</h3>
                  <p className="text-gray-400 text-sm font-mono">
                    {truncateAddress(wallet.address)}
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <span className={`px-2 py-1 rounded text-xs font-medium ${getTypeColor(wallet.type)}`}>
                  {wallet.type.toUpperCase()}
                </span>
                <span className="text-white font-semibold">
                  {formatUsd(wallet.totalUsdValue)}
                </span>
              </div>
            </div>

            <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
              {wallet.balances.map((balance) => (
                <div
                  key={balance.token}
                  className="bg-gray-800/50 rounded p-2"
                >
                  <div className="flex items-center justify-between">
                    <span className="text-gray-400 text-xs">{balance.token}</span>
                    {balance.change24h !== 0 && (
                      <span className={`flex items-center text-xs ${
                        balance.change24h > 0 ? 'text-green-400' : 'text-red-400'
                      }`}>
                        {balance.change24h > 0 ? (
                          <TrendingUp className="w-3 h-3 mr-1" />
                        ) : (
                          <TrendingDown className="w-3 h-3 mr-1" />
                        )}
                        {Math.abs(balance.change24h).toFixed(1)}%
                      </span>
                    )}
                  </div>
                  <p className="text-white font-medium text-sm">
                    {formatAmount(balance.amount)}
                  </p>
                  <p className="text-gray-500 text-xs">
                    {formatUsd(balance.usdValue)}
                  </p>
                </div>
              ))}
            </div>
          </div>
        ))}

        {wallets.length === 0 && (
          <div className="text-center py-8 text-gray-400">
            No wallets configured
          </div>
        )}
      </div>
    </div>
  );
};

export default WalletBalances;
