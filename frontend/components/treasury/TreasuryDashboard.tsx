/**
 * Treasury Transparency Dashboard
 * Prompt #86: Real-time public dashboard for treasury operations
 */

import React, { useState, useEffect, useCallback } from 'react';

// Types
interface WalletBalance {
  type: string;
  address: string;
  sol_balance: number;
  last_updated: string;
}

interface RiskStatus {
  circuit_breaker: string;
  daily_pnl: number;
  weekly_pnl: number;
  monthly_pnl: number;
  active_positions: number;
  total_exposure_pct: number;
}

interface PnLReport {
  daily: { pnl: number; starting: number; current: number };
  weekly: { pnl: number; starting: number; current: number };
  monthly: { pnl: number; starting: number; current: number };
}

interface TreasuryData {
  wallets: Record<string, WalletBalance>;
  risk: RiskStatus;
  running: boolean;
  pnl: PnLReport;
}

interface Distribution {
  id: string;
  timestamp: string;
  total_amount: number;
  staking_amount: number;
  operations_amount: number;
  development_amount: number;
  signature: string;
}

// Custom hook for WebSocket connection
function useTreasuryWebSocket() {
  const [data, setData] = useState<TreasuryData | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const wsUrl = process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8000/ws/treasury';
    let ws: WebSocket | null = null;
    let reconnectTimeout: NodeJS.Timeout;

    const connect = () => {
      try {
        ws = new WebSocket(wsUrl);

        ws.onopen = () => {
          setIsConnected(true);
          setError(null);
        };

        ws.onmessage = (event) => {
          try {
            const message = JSON.parse(event.data);
            if (message.type === 'treasury_update') {
              setData(message.data);
            }
          } catch (e) {
            console.error('Parse error:', e);
          }
        };

        ws.onclose = () => {
          setIsConnected(false);
          reconnectTimeout = setTimeout(connect, 5000);
        };

        ws.onerror = () => {
          setError('Connection error');
          setIsConnected(false);
        };
      } catch (e) {
        setError('Failed to connect');
      }
    };

    connect();

    return () => {
      clearTimeout(reconnectTimeout);
      ws?.close();
    };
  }, []);

  return { data, isConnected, error };
}

// Connection Status Indicator
function ConnectionStatus({ connected }: { connected: boolean }) {
  return (
    <div className="flex items-center gap-2 text-sm">
      <div
        className={`w-2 h-2 rounded-full ${
          connected ? 'bg-green-500 animate-pulse' : 'bg-red-500'
        }`}
      />
      <span className={connected ? 'text-green-600' : 'text-red-600'}>
        {connected ? 'Live' : 'Disconnected'}
      </span>
    </div>
  );
}

// Wallet Balance Card
function WalletCard({
  type,
  balance,
  allocation,
}: {
  type: string;
  balance: number;
  allocation: string;
}) {
  const labels: Record<string, string> = {
    reserve: 'Reserve Vault',
    active: 'Active Trading',
    profit: 'Profit Buffer',
  };

  const colors: Record<string, string> = {
    reserve: 'from-blue-500 to-blue-600',
    active: 'from-green-500 to-green-600',
    profit: 'from-purple-500 to-purple-600',
  };

  return (
    <div className="bg-gray-800 rounded-xl p-6 border border-gray-700">
      <div className="flex justify-between items-start mb-4">
        <div>
          <p className="text-gray-400 text-sm">{labels[type] || type}</p>
          <p className="text-2xl font-bold text-white mt-1">
            {balance.toFixed(4)} SOL
          </p>
        </div>
        <div
          className={`px-3 py-1 rounded-full text-xs font-medium bg-gradient-to-r ${
            colors[type] || 'from-gray-500 to-gray-600'
          }`}
        >
          {allocation}
        </div>
      </div>
      <div className="h-1 bg-gray-700 rounded-full overflow-hidden">
        <div
          className={`h-full bg-gradient-to-r ${colors[type]} transition-all duration-500`}
          style={{ width: allocation }}
        />
      </div>
    </div>
  );
}

// P&L Chart (simplified inline SVG)
function PnLChart({ pnl }: { pnl: PnLReport }) {
  const data = [
    { label: 'Daily', value: pnl.daily.pnl },
    { label: 'Weekly', value: pnl.weekly.pnl },
    { label: 'Monthly', value: pnl.monthly.pnl },
  ];

  const maxAbs = Math.max(...data.map((d) => Math.abs(d.value)), 0.1);

  return (
    <div className="bg-gray-800 rounded-xl p-6 border border-gray-700">
      <h3 className="text-lg font-semibold text-white mb-4">P&L Performance</h3>
      <div className="space-y-4">
        {data.map((item) => {
          const isPositive = item.value >= 0;
          const width = (Math.abs(item.value) / maxAbs) * 100;

          return (
            <div key={item.label}>
              <div className="flex justify-between text-sm mb-1">
                <span className="text-gray-400">{item.label}</span>
                <span
                  className={isPositive ? 'text-green-400' : 'text-red-400'}
                >
                  {isPositive ? '+' : ''}
                  {item.value.toFixed(4)} SOL
                </span>
              </div>
              <div className="h-2 bg-gray-700 rounded-full overflow-hidden">
                <div
                  className={`h-full transition-all duration-500 ${
                    isPositive ? 'bg-green-500' : 'bg-red-500'
                  }`}
                  style={{ width: `${width}%` }}
                />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// Risk Monitor
function RiskMonitor({ risk }: { risk: RiskStatus }) {
  const circuitStatus = risk.circuit_breaker || 'closed';
  const isOpen = circuitStatus.toLowerCase() !== 'closed';

  return (
    <div className="bg-gray-800 rounded-xl p-6 border border-gray-700">
      <h3 className="text-lg font-semibold text-white mb-4">Risk Status</h3>

      {/* Circuit Breaker */}
      <div
        className={`p-4 rounded-lg mb-4 ${
          isOpen ? 'bg-red-900/30 border border-red-500' : 'bg-green-900/30 border border-green-500'
        }`}
      >
        <div className="flex items-center gap-2">
          <div
            className={`w-3 h-3 rounded-full ${
              isOpen ? 'bg-red-500 animate-pulse' : 'bg-green-500'
            }`}
          />
          <span className={isOpen ? 'text-red-400' : 'text-green-400'}>
            Circuit Breaker: {circuitStatus.toUpperCase()}
          </span>
        </div>
      </div>

      {/* Metrics */}
      <div className="grid grid-cols-2 gap-4">
        <div>
          <p className="text-gray-400 text-sm">Active Positions</p>
          <p className="text-xl font-bold text-white">{risk.active_positions}</p>
        </div>
        <div>
          <p className="text-gray-400 text-sm">Total Exposure</p>
          <p className="text-xl font-bold text-white">
            {(risk.total_exposure_pct * 100).toFixed(1)}%
          </p>
        </div>
      </div>

      {/* Exposure Bar */}
      <div className="mt-4">
        <div className="flex justify-between text-xs text-gray-400 mb-1">
          <span>Exposure</span>
          <span>Max 50%</span>
        </div>
        <div className="h-2 bg-gray-700 rounded-full overflow-hidden">
          <div
            className={`h-full transition-all duration-500 ${
              risk.total_exposure_pct > 0.4
                ? 'bg-red-500'
                : risk.total_exposure_pct > 0.25
                ? 'bg-yellow-500'
                : 'bg-green-500'
            }`}
            style={{ width: `${Math.min(risk.total_exposure_pct * 200, 100)}%` }}
          />
        </div>
      </div>
    </div>
  );
}

// Distribution History (would fetch from API)
function DistributionHistory() {
  const [distributions, setDistributions] = useState<Distribution[]>([]);

  useEffect(() => {
    // Fetch distribution history
    fetch('/api/treasury/distributions?limit=10')
      .then((res) => res.json())
      .then(setDistributions)
      .catch(console.error);
  }, []);

  return (
    <div className="bg-gray-800 rounded-xl p-6 border border-gray-700">
      <h3 className="text-lg font-semibold text-white mb-4">
        Recent Distributions
      </h3>

      <div className="space-y-3">
        {distributions.length === 0 ? (
          <p className="text-gray-500 text-sm">No distributions yet</p>
        ) : (
          distributions.map((dist) => (
            <div
              key={dist.id}
              className="flex justify-between items-center py-2 border-b border-gray-700"
            >
              <div>
                <p className="text-white font-medium">
                  {dist.total_amount.toFixed(4)} SOL
                </p>
                <p className="text-gray-400 text-xs">
                  {new Date(dist.timestamp).toLocaleDateString()}
                </p>
              </div>
              <a
                href={`https://solscan.io/tx/${dist.signature}`}
                target="_blank"
                rel="noopener noreferrer"
                className="text-blue-400 text-sm hover:underline"
              >
                View TX
              </a>
            </div>
          ))
        )}
      </div>
    </div>
  );
}

// Main Dashboard Component
export default function TreasuryDashboard() {
  const { data, isConnected, error } = useTreasuryWebSocket();

  if (error) {
    return (
      <div className="p-6 bg-red-900/20 rounded-lg border border-red-500">
        <p className="text-red-400">Error: {error}</p>
        <p className="text-gray-400 text-sm mt-2">
          Unable to connect to treasury. Retrying...
        </p>
      </div>
    );
  }

  const wallets = data?.wallets || {};
  const risk = data?.risk || {
    circuit_breaker: 'unknown',
    active_positions: 0,
    total_exposure_pct: 0,
  };
  const pnl = data?.pnl || {
    daily: { pnl: 0 },
    weekly: { pnl: 0 },
    monthly: { pnl: 0 },
  };

  // Calculate total
  const totalBalance = Object.values(wallets).reduce(
    (sum, w) => sum + (w.sol_balance || 0),
    0
  );

  return (
    <div className="min-h-screen bg-gray-900 p-6">
      {/* Header */}
      <div className="flex justify-between items-center mb-8">
        <div>
          <h1 className="text-3xl font-bold text-white">Treasury Dashboard</h1>
          <p className="text-gray-400 mt-1">
            Real-time transparency into JARVIS treasury operations
          </p>
        </div>
        <ConnectionStatus connected={isConnected} />
      </div>

      {/* Total Value */}
      <div className="bg-gradient-to-r from-indigo-600 to-purple-600 rounded-xl p-6 mb-8">
        <p className="text-indigo-200">Total Treasury Value</p>
        <p className="text-4xl font-bold text-white mt-2">
          {totalBalance.toFixed(4)} SOL
        </p>
        <p className="text-indigo-200 text-sm mt-1">
          Last updated: {new Date().toLocaleTimeString()}
        </p>
      </div>

      {/* Wallet Balances */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
        <WalletCard
          type="reserve"
          balance={wallets.reserve?.sol_balance || 0}
          allocation="60%"
        />
        <WalletCard
          type="active"
          balance={wallets.active?.sol_balance || 0}
          allocation="30%"
        />
        <WalletCard
          type="profit"
          balance={wallets.profit?.sol_balance || 0}
          allocation="10%"
        />
      </div>

      {/* Performance & Risk */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
        <PnLChart pnl={pnl} />
        <RiskMonitor risk={risk} />
      </div>

      {/* Distributions */}
      <DistributionHistory />

      {/* Footer */}
      <div className="mt-8 text-center text-gray-500 text-sm">
        <p>All data is on-chain verifiable</p>
        <p className="mt-1">
          View smart contract:{' '}
          <a
            href="https://solscan.io"
            className="text-blue-400 hover:underline"
          >
            Solscan
          </a>
        </p>
      </div>
    </div>
  );
}
