'use client';

import { useState, useEffect, useCallback } from 'react';

export type NetworkState = 'connected' | 'degraded' | 'disconnected';

export interface NetworkStatusData {
    status: NetworkState;
    latency: number;
    blockHeight: number | null;
    lastChecked: Date | null;
}

function getRpcUrl(): string {
    const envUrl = process.env.NEXT_PUBLIC_SOLANA_RPC_URL;
    const fallbackUrl = process.env.NEXT_PUBLIC_FALLBACK_RPC_URL;
    return envUrl || fallbackUrl || 'https://api.mainnet-beta.solana.com';
}

export function classifyStatus(latencyMs: number, success: boolean): NetworkState {
    if (!success) return 'disconnected';
    if (latencyMs > 2000) return 'degraded';
    return 'connected';
}

export function formatLatency(ms: number): string {
    if (ms === 0) return '--';
    if (ms < 1000) return `${ms}ms`;
    return `${(ms / 1000).toFixed(1)}s`;
}

export function formatBlockHeight(height: number | null): string {
    if (height === null) return '--';
    return height.toLocaleString('en-US');
}

const CHECK_INTERVAL = 15_000; // 15 seconds

export function useNetworkStatus(): NetworkStatusData & { refresh: () => void } {
    const [status, setStatus] = useState<NetworkState>('connected');
    const [latency, setLatency] = useState<number>(0);
    const [blockHeight, setBlockHeight] = useState<number | null>(null);
    const [lastChecked, setLastChecked] = useState<Date | null>(null);

    const checkStatus = useCallback(async () => {
        const rpcUrl = getRpcUrl();
        const start = Date.now();

        try {
            // Use getHealth for a lightweight check
            const res = await fetch(rpcUrl, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ jsonrpc: '2.0', id: 1, method: 'getHealth' }),
            });

            const ms = Date.now() - start;
            setLatency(ms);
            setLastChecked(new Date());

            if (res.ok) {
                setStatus(classifyStatus(ms, true));
            } else {
                setStatus('degraded');
            }

            // Also fetch block height in a separate non-blocking call
            try {
                const slotRes = await fetch(rpcUrl, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ jsonrpc: '2.0', id: 2, method: 'getSlot' }),
                });
                const slotData = await slotRes.json();
                if (slotData?.result) {
                    setBlockHeight(slotData.result);
                }
            } catch {
                // Block height fetch is best-effort, don't fail the whole check
            }
        } catch {
            setLatency(0);
            setStatus('disconnected');
            setLastChecked(new Date());
        }
    }, []);

    useEffect(() => {
        checkStatus();
        const interval = setInterval(checkStatus, CHECK_INTERVAL);
        return () => clearInterval(interval);
    }, [checkStatus]);

    return { status, latency, blockHeight, lastChecked, refresh: checkStatus };
}
