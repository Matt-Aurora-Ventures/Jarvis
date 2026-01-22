/**
 * WebSocket Price Feed Hook
 * Connects to backend WebSocket for real-time price updates.
 *
 * Features:
 * - Auto-connect to WebSocket on mount
 * - Auto-reconnect on disconnect
 * - Price update callbacks
 * - Connection status tracking
 * - Cleanup on unmount
 */
import { useEffect, useRef, useState, useCallback } from 'react';

export interface PriceUpdate {
  token_address: string;
  price: number;
  volume_24h: number;
  price_change_24h: number;
  source: string;
  timestamp: string;
}

interface UsePriceWebSocketOptions {
  tokenAddress: string;
  onPriceUpdate?: (update: PriceUpdate) => void;
  autoConnect?: boolean;
}

interface UsePriceWebSocketReturn {
  latestPrice: PriceUpdate | null;
  isConnected: boolean;
  error: string | null;
  connect: () => void;
  disconnect: () => void;
}

export const usePriceWebSocket = ({
  tokenAddress,
  onPriceUpdate,
  autoConnect = true
}: UsePriceWebSocketOptions): UsePriceWebSocketReturn => {
  const [latestPrice, setLatestPrice] = useState<PriceUpdate | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout>();
  const reconnectAttemptsRef = useRef(0);

  const MAX_RECONNECT_ATTEMPTS = 5;
  const RECONNECT_DELAY_MS = 2000;

  const getWebSocketUrl = useCallback(() => {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = import.meta.env.VITE_API_URL || window.location.host;
    // Remove http:// or https:// from host
    const cleanHost = host.replace(/^https?:\/\//, '');
    return `${protocol}//${cleanHost}/api/v1/ws/prices/${tokenAddress}`;
  }, [tokenAddress]);

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      return; // Already connected
    }

    try {
      const url = getWebSocketUrl();
      const ws = new WebSocket(url);

      ws.onopen = () => {
        console.log(`WebSocket connected to ${tokenAddress.slice(0, 8)}...`);
        setIsConnected(true);
        setError(null);
        reconnectAttemptsRef.current = 0;
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);

          // Handle pong response
          if (data.type === 'pong') {
            return;
          }

          // Price update
          const update: PriceUpdate = data;
          setLatestPrice(update);

          // Call callback if provided
          if (onPriceUpdate) {
            onPriceUpdate(update);
          }
        } catch (err) {
          console.error('Failed to parse WebSocket message:', err);
        }
      };

      ws.onerror = (event) => {
        console.error('WebSocket error:', event);
        setError('WebSocket connection error');
      };

      ws.onclose = () => {
        console.log(`WebSocket disconnected from ${tokenAddress.slice(0, 8)}...`);
        setIsConnected(false);

        // Attempt to reconnect
        if (reconnectAttemptsRef.current < MAX_RECONNECT_ATTEMPTS) {
          reconnectAttemptsRef.current += 1;
          console.log(
            `Attempting to reconnect (${reconnectAttemptsRef.current}/${MAX_RECONNECT_ATTEMPTS})...`
          );

          reconnectTimeoutRef.current = setTimeout(() => {
            connect();
          }, RECONNECT_DELAY_MS * reconnectAttemptsRef.current);
        } else {
          setError('Max reconnection attempts reached');
        }
      };

      wsRef.current = ws;
    } catch (err) {
      console.error('Failed to create WebSocket:', err);
      setError('Failed to connect to price feed');
    }
  }, [tokenAddress, getWebSocketUrl, onPriceUpdate]);

  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
    }

    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }

    setIsConnected(false);
  }, []);

  // Auto-connect on mount
  useEffect(() => {
    if (autoConnect) {
      connect();
    }

    return () => {
      disconnect();
    };
  }, [autoConnect, connect, disconnect]);

  // Send ping every 30 seconds to keep connection alive
  useEffect(() => {
    if (!isConnected || !wsRef.current) return;

    const pingInterval = setInterval(() => {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send('ping');
      }
    }, 30000);

    return () => clearInterval(pingInterval);
  }, [isConnected]);

  return {
    latestPrice,
    isConnected,
    error,
    connect,
    disconnect
  };
};
