import React from 'react';
import { Gift, Users, Flame, ArrowRight, ExternalLink, Clock } from 'lucide-react';

interface Distribution {
  id: string;
  type: 'staking_rewards' | 'buyback_burn' | 'team' | 'development';
  amount: number;
  token: string;
  recipients?: number;
  txSignature?: string;
  timestamp: string;
  status: 'completed' | 'pending' | 'failed';
  details?: string;
}

interface DistributionHistoryProps {
  distributions: Distribution[];
  isLoading?: boolean;
}

export const DistributionHistory: React.FC<DistributionHistoryProps> = ({
  distributions,
  isLoading = false,
}) => {
  const formatAmount = (value: number) => {
    if (value >= 1000000) {
      return `${(value / 1000000).toFixed(2)}M`;
    } else if (value >= 1000) {
      return `${(value / 1000).toFixed(2)}K`;
    }
    return value.toLocaleString();
  };

  const truncateTx = (signature: string) => {
    return `${signature.slice(0, 8)}...${signature.slice(-8)}`;
  };

  const getTypeInfo = (type: Distribution['type']) => {
    switch (type) {
      case 'staking_rewards':
        return {
          icon: Gift,
          label: 'Staking Rewards',
          color: 'text-green-400',
          bgColor: 'bg-green-500/20',
        };
      case 'buyback_burn':
        return {
          icon: Flame,
          label: 'Buyback & Burn',
          color: 'text-orange-400',
          bgColor: 'bg-orange-500/20',
        };
      case 'team':
        return {
          icon: Users,
          label: 'Team Allocation',
          color: 'text-blue-400',
          bgColor: 'bg-blue-500/20',
        };
      case 'development':
        return {
          icon: ArrowRight,
          label: 'Development Fund',
          color: 'text-purple-400',
          bgColor: 'bg-purple-500/20',
        };
    }
  };

  const getStatusColor = (status: Distribution['status']) => {
    switch (status) {
      case 'completed':
        return 'bg-green-500/20 text-green-400';
      case 'pending':
        return 'bg-yellow-500/20 text-yellow-400';
      case 'failed':
        return 'bg-red-500/20 text-red-400';
    }
  };

  const totalsByType = distributions
    .filter(d => d.status === 'completed')
    .reduce((acc, d) => {
      acc[d.type] = (acc[d.type] || 0) + d.amount;
      return acc;
    }, {} as Record<string, number>);

  return (
    <div className="bg-gray-800 rounded-lg p-6">
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-xl font-semibold text-white">Distribution History</h2>
        <div className="flex items-center gap-2 text-gray-400 text-sm">
          <Clock className="w-4 h-4" />
          {distributions.length} distributions
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        {(['staking_rewards', 'buyback_burn', 'team', 'development'] as const).map((type) => {
          const info = getTypeInfo(type);
          const Icon = info.icon;
          return (
            <div key={type} className="bg-gray-700/50 rounded-lg p-4">
              <div className={`inline-flex p-2 rounded-lg ${info.bgColor} mb-2`}>
                <Icon className={`w-5 h-5 ${info.color}`} />
              </div>
              <p className="text-gray-400 text-sm">{info.label}</p>
              <p className={`text-xl font-bold ${info.color}`}>
                {formatAmount(totalsByType[type] || 0)}
              </p>
            </div>
          );
        })}
      </div>

      {/* Timeline */}
      <div className="relative">
        {distributions.map((dist, index) => {
          const typeInfo = getTypeInfo(dist.type);
          const Icon = typeInfo.icon;
          const isLast = index === distributions.length - 1;

          return (
            <div key={dist.id} className="flex gap-4 pb-6">
              {/* Timeline line */}
              <div className="flex flex-col items-center">
                <div className={`p-2 rounded-full ${typeInfo.bgColor}`}>
                  <Icon className={`w-4 h-4 ${typeInfo.color}`} />
                </div>
                {!isLast && (
                  <div className="w-0.5 flex-1 bg-gray-700 mt-2" />
                )}
              </div>

              {/* Content */}
              <div className="flex-1 bg-gray-700/30 rounded-lg p-4">
                <div className="flex items-start justify-between mb-2">
                  <div>
                    <h3 className="text-white font-medium">{typeInfo.label}</h3>
                    <p className="text-gray-400 text-sm">
                      {new Date(dist.timestamp).toLocaleDateString('en-US', {
                        weekday: 'short',
                        month: 'short',
                        day: 'numeric',
                        year: 'numeric',
                        hour: '2-digit',
                        minute: '2-digit',
                      })}
                    </p>
                  </div>
                  <span className={`px-2 py-1 rounded text-xs font-medium ${getStatusColor(dist.status)}`}>
                    {dist.status.charAt(0).toUpperCase() + dist.status.slice(1)}
                  </span>
                </div>

                <div className="flex items-center justify-between">
                  <div>
                    <p className={`text-lg font-bold ${typeInfo.color}`}>
                      {formatAmount(dist.amount)} {dist.token}
                    </p>
                    {dist.recipients && (
                      <p className="text-gray-400 text-sm">
                        {dist.recipients.toLocaleString()} recipients
                      </p>
                    )}
                    {dist.details && (
                      <p className="text-gray-400 text-sm mt-1">{dist.details}</p>
                    )}
                  </div>

                  {dist.txSignature && (
                    <a
                      href={`https://solscan.io/tx/${dist.txSignature}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex items-center gap-1 text-gray-400 hover:text-white transition-colors text-sm"
                    >
                      <span className="font-mono">{truncateTx(dist.txSignature)}</span>
                      <ExternalLink className="w-3 h-3" />
                    </a>
                  )}
                </div>
              </div>
            </div>
          );
        })}

        {distributions.length === 0 && !isLoading && (
          <div className="text-center py-8 text-gray-400">
            No distributions recorded yet
          </div>
        )}

        {isLoading && (
          <div className="flex justify-center py-8">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500" />
          </div>
        )}
      </div>
    </div>
  );
};

export default DistributionHistory;
