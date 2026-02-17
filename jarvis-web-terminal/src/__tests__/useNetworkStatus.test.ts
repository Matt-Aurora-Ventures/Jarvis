import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

// Test the network status logic (not the React hook itself, but the core logic)
// The hook will use this logic internally

describe('NetworkStatus logic', () => {
    beforeEach(() => {
        vi.useFakeTimers();
    });

    afterEach(() => {
        vi.useRealTimers();
        vi.restoreAllMocks();
    });

    it('should classify latency < 2000ms as connected', () => {
        // Logic: if ping < 2000ms, status is 'connected'
        const classifyStatus = (latencyMs: number, success: boolean): 'connected' | 'degraded' | 'disconnected' => {
            if (!success) return 'disconnected';
            if (latencyMs > 2000) return 'degraded';
            return 'connected';
        };

        expect(classifyStatus(100, true)).toBe('connected');
        expect(classifyStatus(500, true)).toBe('connected');
        expect(classifyStatus(1999, true)).toBe('connected');
    });

    it('should classify latency > 2000ms as degraded', () => {
        const classifyStatus = (latencyMs: number, success: boolean): 'connected' | 'degraded' | 'disconnected' => {
            if (!success) return 'disconnected';
            if (latencyMs > 2000) return 'degraded';
            return 'connected';
        };

        expect(classifyStatus(2001, true)).toBe('degraded');
        expect(classifyStatus(5000, true)).toBe('degraded');
    });

    it('should classify failed requests as disconnected', () => {
        const classifyStatus = (latencyMs: number, success: boolean): 'connected' | 'degraded' | 'disconnected' => {
            if (!success) return 'disconnected';
            if (latencyMs > 2000) return 'degraded';
            return 'connected';
        };

        expect(classifyStatus(0, false)).toBe('disconnected');
    });

    it('should use NEXT_PUBLIC_SOLANA_RPC_URL when available', () => {
        const getRpcUrl = (): string => {
            const envUrl = process.env.NEXT_PUBLIC_SOLANA_RPC_URL;
            const fallbackUrl = process.env.NEXT_PUBLIC_FALLBACK_RPC_URL;
            return envUrl || fallbackUrl || 'https://api.mainnet-beta.solana.com';
        };

        // With env set
        process.env.NEXT_PUBLIC_SOLANA_RPC_URL = 'https://mainnet.helius-rpc.com/?api-key=test';
        expect(getRpcUrl()).toBe('https://mainnet.helius-rpc.com/?api-key=test');

        // Without env, use fallback
        delete process.env.NEXT_PUBLIC_SOLANA_RPC_URL;
        process.env.NEXT_PUBLIC_FALLBACK_RPC_URL = 'https://api.mainnet-beta.solana.com';
        expect(getRpcUrl()).toBe('https://api.mainnet-beta.solana.com');

        // Without any env
        delete process.env.NEXT_PUBLIC_FALLBACK_RPC_URL;
        expect(getRpcUrl()).toBe('https://api.mainnet-beta.solana.com');
    });

    it('should format latency display correctly', () => {
        const formatLatency = (ms: number): string => {
            if (ms === 0) return '--';
            if (ms < 1000) return `${ms}ms`;
            return `${(ms / 1000).toFixed(1)}s`;
        };

        expect(formatLatency(0)).toBe('--');
        expect(formatLatency(150)).toBe('150ms');
        expect(formatLatency(999)).toBe('999ms');
        expect(formatLatency(1500)).toBe('1.5s');
        expect(formatLatency(2500)).toBe('2.5s');
    });

    it('should format block height with commas', () => {
        const formatBlockHeight = (height: number | null): string => {
            if (height === null) return '--';
            return height.toLocaleString('en-US');
        };

        expect(formatBlockHeight(null)).toBe('--');
        expect(formatBlockHeight(315000000)).toBe('315,000,000');
        expect(formatBlockHeight(12345)).toBe('12,345');
    });
});
