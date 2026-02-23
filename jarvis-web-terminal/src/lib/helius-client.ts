/**
 * Helius RPC Client with Smart Fallback
 *
 * Handles the common 403 error when Helius API key doesn't have blockchain access.
 * Provides graceful fallback to free public RPCs.
 */

import { Connection, PublicKey, LAMPORTS_PER_SOL, GetProgramAccountsConfig } from '@solana/web3.js';

// RPC endpoints in order of preference
const RPC_ENDPOINTS = {
    helius: (apiKey: string) => `https://mainnet.helius-rpc.com/?api-key=${apiKey}`,
    heliusBlockchain: (apiKey: string) => `https://rpc.helius.xyz/?api-key=${apiKey}`,
    ankr: 'https://rpc.ankr.com/solana',
    solana: 'https://api.mainnet-beta.solana.com',
    quicknode: 'https://solana-mainnet.core.chainstack.com/8a6ade32bf2bd03b5baacda6fdbe7dd1',
};

interface HeliusClientConfig {
    apiKey?: string;
    preferredEndpoint?: 'helius' | 'ankr' | 'solana';
}

interface TokenAccount {
    pubkey: string;
    mint: string;
    amount: number;
    decimals: number;
    symbol?: string;
}

interface TokenBalanceResponse {
    sol: number;
    tokens: TokenAccount[];
}

class HeliusClient {
    private connection: Connection | null = null;
    private apiKey: string | null = null;
    private currentEndpoint: string = RPC_ENDPOINTS.ankr;
    private fallbackAttempted = false;

    constructor(config: HeliusClientConfig = {}) {
        this.apiKey = config.apiKey || process.env.NEXT_PUBLIC_HELIUS_API_KEY || null;
        this.initConnection();
    }

    private initConnection() {
        // Start with Helius if API key available
        if (this.apiKey) {
            this.currentEndpoint = RPC_ENDPOINTS.helius(this.apiKey);
        } else {
            // No API key, use Ankr (reliable free RPC)
            this.currentEndpoint = RPC_ENDPOINTS.ankr;
        }

        this.connection = new Connection(this.currentEndpoint, {
            commitment: 'confirmed',
            confirmTransactionInitialTimeout: 60000,
        });

        console.log(`[Helius] Connected to: ${this.apiKey ? 'Helius RPC' : 'Ankr (fallback)'}`);
    }

    /**
     * Switch to fallback RPC when Helius fails
     */
    private async switchToFallback(): Promise<void> {
        if (this.fallbackAttempted) return;

        this.fallbackAttempted = true;
        console.warn('[Helius] Switching to fallback RPC (Ankr)');

        this.currentEndpoint = RPC_ENDPOINTS.ankr;
        this.connection = new Connection(this.currentEndpoint, {
            commitment: 'confirmed',
        });
    }

    /**
     * Execute RPC call with automatic fallback
     */
    private async withFallback<T>(operation: (conn: Connection) => Promise<T>): Promise<T> {
        if (!this.connection) {
            this.initConnection();
        }

        try {
            return await operation(this.connection!);
        } catch (error: any) {
            const errorStr = error?.message || error?.toString() || '';
            // Trigger fallback on: 403, access denied, NetworkError, fetch failure, timeout
            const shouldFallback = errorStr.includes('403') ||
                errorStr.includes('not allowed to access blockchain') ||
                errorStr.includes('-32052') ||
                errorStr.includes('NetworkError') ||
                errorStr.includes('fetch') ||
                errorStr.includes('ECONNREFUSED') ||
                errorStr.includes('ETIMEDOUT') ||
                errorStr.includes('Failed to fetch');

            if (shouldFallback && !this.fallbackAttempted) {
                console.warn(`[Helius] RPC error detected (${errorStr.slice(0, 80)}), switching to fallback`);
                await this.switchToFallback();
                return await operation(this.connection!);
            }

            throw error;
        }
    }

    /**
     * Get SOL balance for a wallet
     */
    async getBalance(publicKey: string | PublicKey): Promise<number> {
        const pk = typeof publicKey === 'string' ? new PublicKey(publicKey) : publicKey;

        return this.withFallback(async (conn) => {
            const balance = await conn.getBalance(pk);
            return balance / LAMPORTS_PER_SOL;
        });
    }

    /**
     * Get all token accounts and SOL balance
     */
    async getTokenBalances(publicKey: string | PublicKey): Promise<TokenBalanceResponse> {
        const pk = typeof publicKey === 'string' ? new PublicKey(publicKey) : publicKey;

        return this.withFallback(async (conn) => {
            // Get SOL balance
            const solBalance = await conn.getBalance(pk);

            // Get token accounts
            const tokenAccounts = await conn.getParsedTokenAccountsByOwner(pk, {
                programId: new PublicKey('TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA'),
            });

            const tokens: TokenAccount[] = tokenAccounts.value
                .filter((account) => {
                    const amount = account.account.data.parsed?.info?.tokenAmount?.uiAmount;
                    return amount && amount > 0;
                })
                .map((account) => {
                    const parsed = account.account.data.parsed?.info;
                    return {
                        pubkey: account.pubkey.toBase58(),
                        mint: parsed?.mint || '',
                        amount: parsed?.tokenAmount?.uiAmount || 0,
                        decimals: parsed?.tokenAmount?.decimals || 0,
                    };
                });

            return {
                sol: solBalance / LAMPORTS_PER_SOL,
                tokens,
            };
        });
    }

    /**
     * Get recent transactions for a wallet
     */
    async getRecentTransactions(publicKey: string | PublicKey, limit = 10) {
        const pk = typeof publicKey === 'string' ? new PublicKey(publicKey) : publicKey;

        return this.withFallback(async (conn) => {
            const signatures = await conn.getSignaturesForAddress(pk, { limit });
            return signatures.map((sig) => ({
                signature: sig.signature,
                slot: sig.slot,
                err: sig.err,
                memo: sig.memo,
                blockTime: sig.blockTime,
            }));
        });
    }

    /**
     * Get current Solana price (uses CoinGecko API)
     */
    async getSolPrice(): Promise<number> {
        try {
            const response = await fetch(
                'https://api.coingecko.com/api/v3/simple/price?ids=solana&vs_currencies=usd',
                { next: { revalidate: 60 } } // Cache for 60 seconds
            );
            const data = await response.json();
            return data?.solana?.usd || 0;
        } catch (error) {
            console.error('[Helius] Failed to fetch SOL price:', error);
            return 0;
        }
    }

    /**
     * Get token metadata (symbol, name, decimals)
     */
    async getTokenMetadata(mintAddress: string) {
        // For now, return basic info. In production, use Metaplex or Helius DAS API
        return this.withFallback(async (conn) => {
            const mint = new PublicKey(mintAddress);
            const info = await conn.getParsedAccountInfo(mint);

            if (info.value?.data && 'parsed' in info.value.data) {
                return {
                    mint: mintAddress,
                    decimals: info.value.data.parsed?.info?.decimals || 9,
                    supply: info.value.data.parsed?.info?.supply || '0',
                };
            }

            return { mint: mintAddress, decimals: 9, supply: '0' };
        });
    }

    /**
     * Get raw connection for advanced use
     */
    getConnection(): Connection {
        if (!this.connection) {
            this.initConnection();
        }
        return this.connection!;
    }

    /**
     * Get current endpoint info
     */
    getEndpointInfo() {
        return {
            current: this.currentEndpoint.includes('helius') ? 'helius' : 'fallback',
            fallbackUsed: this.fallbackAttempted,
        };
    }
}

// Singleton instance
let heliusClientInstance: HeliusClient | null = null;

export function getHeliusClient(config?: HeliusClientConfig): HeliusClient {
    if (!heliusClientInstance) {
        heliusClientInstance = new HeliusClient(config);
    }
    return heliusClientInstance;
}

export { HeliusClient };
export type { HeliusClientConfig, TokenAccount, TokenBalanceResponse };
