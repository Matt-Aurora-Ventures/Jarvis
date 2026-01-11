import { useState, useEffect, useCallback, useRef } from 'react';

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

interface TradeRecord {
  id: string;
  strategy: string;
  token: string;
  side: 'buy' | 'sell';
  entryPrice: number;
  exitPrice?: number;
  amount: number;
  pnl: number;
  pnlPercent: number;
  timestamp: string;
  status: 'open' | 'closed' | 'stopped';
}

interface StrategyPerformance {
  name: string;
  totalTrades: number;
  winRate: number;
  totalPnl: number;
  avgPnl: number;
  maxDrawdown: number;
  sharpeRatio: number;
}

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

interface TreasuryData {
  wallets: WalletBalance[];
  trades: TradeRecord[];
  strategies: StrategyPerformance[];
  distributions: Distribution[];
  lastUpdate: string | null;
}

interface UseTreasuryDataOptions {
  wsUrl?: string;
  apiUrl?: string;
  autoConnect?: boolean;
  reconnectInterval?: number;
}

interface UseTreasuryDataReturn {
  data: TreasuryData;
  isLoading: boolean;
  isConnected: boolean;
  error: string | null;
  refresh: () => Promise<void>;
  connect: () => void;
  disconnect: () => void;
}

const DEFAULT_DATA: TreasuryData = {
  wallets: [],
  trades: [],
  strategies: [],
  distributions: [],
  lastUpdate: null,
};

export function useTreasuryData(options: UseTreasuryDataOptions = {}): UseTreasuryDataReturn {
  const {
    wsUrl = 'ws://localhost:8766/ws/treasury',
    apiUrl = '/api/treasury',
    autoConnect = true,
    reconnectInterval = 5000,
  } = options;

  const [data, setData] = useState<TreasuryData>(DEFAULT_DATA);
  const [isLoading, setIsLoading] = useState(true);
  const [isConnected, setIsConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  // Fetch initial data via REST API
  const fetchInitialData = useCallback(async () => {
    setIsLoading(true);
    setError(null);

    try {
      const [walletsRes, tradesRes, strategiesRes, distributionsRes] = await Promise.all([
        fetch(`${apiUrl}/wallets`),
        fetch(`${apiUrl}/trades`),
        fetch(`${apiUrl}/strategies`),
        fetch(`${apiUrl}/distributions`),
      ]);

      const [wallets, trades, strategies, distributions] = await Promise.all([
        walletsRes.ok ? walletsRes.json() : [],
        tradesRes.ok ? tradesRes.json() : [],
        strategiesRes.ok ? strategiesRes.json() : [],
        distributionsRes.ok ? distributionsRes.json() : [],
      ]);

      setData({
        wallets,
        trades,
        strategies,
        distributions,
        lastUpdate: new Date().toISOString(),
      });
    } catch (err) {
      console.error('Failed to fetch treasury data:', err);
      setError(err instanceof Error ? err.message : 'Failed to fetch data');
    } finally {
      setIsLoading(false);
    }
  }, [apiUrl]);

  // Handle WebSocket messages
  const handleMessage = useCallback((event: MessageEvent) => {
    try {
      const message = JSON.parse(event.data);

      switch (message.type) {
        case 'wallet_update':
          setData(prev => ({
            ...prev,
            wallets: prev.wallets.map(w =>
              w.address === message.data.address ? { ...w, ...message.data } : w
            ),
            lastUpdate: new Date().toISOString(),
          }));
          break;

        case 'trade_update':
          setData(prev => ({
            ...prev,
            trades: message.data.id
              ? prev.trades.some(t => t.id === message.data.id)
                ? prev.trades.map(t => t.id === message.data.id ? { ...t, ...message.data } : t)
                : [message.data, ...prev.trades]
              : prev.trades,
            lastUpdate: new Date().toISOString(),
          }));
          break;

        case 'strategy_update':
          setData(prev => ({
            ...prev,
            strategies: prev.strategies.map(s =>
              s.name === message.data.name ? { ...s, ...message.data } : s
            ),
            lastUpdate: new Date().toISOString(),
          }));
          break;

        case 'distribution_update':
          setData(prev => ({
            ...prev,
            distributions: message.data.id
              ? prev.distributions.some(d => d.id === message.data.id)
                ? prev.distributions.map(d => d.id === message.data.id ? { ...d, ...message.data } : d)
                : [message.data, ...prev.distributions]
              : prev.distributions,
            lastUpdate: new Date().toISOString(),
          }));
          break;

        case 'full_update':
          setData({
            ...message.data,
            lastUpdate: new Date().toISOString(),
          });
          break;

        default:
          console.log('Unknown message type:', message.type);
      }
    } catch (err) {
      console.error('Failed to parse WebSocket message:', err);
    }
  }, []);

  // Connect to WebSocket
  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      return;
    }

    try {
      const ws = new WebSocket(wsUrl);

      ws.onopen = () => {
        console.log('Treasury WebSocket connected');
        setIsConnected(true);
        setError(null);

        // Request initial data
        ws.send(JSON.stringify({ type: 'subscribe', channel: 'treasury' }));
      };

      ws.onmessage = handleMessage;

      ws.onclose = () => {
        console.log('Treasury WebSocket disconnected');
        setIsConnected(false);

        // Auto-reconnect
        if (autoConnect) {
          reconnectTimeoutRef.current = setTimeout(() => {
            console.log('Attempting to reconnect...');
            connect();
          }, reconnectInterval);
        }
      };

      ws.onerror = (err) => {
        console.error('Treasury WebSocket error:', err);
        setError('WebSocket connection error');
      };

      wsRef.current = ws;
    } catch (err) {
      console.error('Failed to create WebSocket:', err);
      setError(err instanceof Error ? err.message : 'Failed to connect');
    }
  }, [wsUrl, autoConnect, reconnectInterval, handleMessage]);

  // Disconnect from WebSocket
  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }

    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }

    setIsConnected(false);
  }, []);

  // Refresh data
  const refresh = useCallback(async () => {
    await fetchInitialData();

    // Also request fresh data via WebSocket if connected
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: 'refresh' }));
    }
  }, [fetchInitialData]);

  // Initialize
  useEffect(() => {
    fetchInitialData();

    if (autoConnect) {
      connect();
    }

    return () => {
      disconnect();
    };
  }, [fetchInitialData, autoConnect, connect, disconnect]);

  return {
    data,
    isLoading,
    isConnected,
    error,
    refresh,
    connect,
    disconnect,
  };
}

export default useTreasuryData;
