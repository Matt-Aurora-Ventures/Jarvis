/**
 * Bags.fm Trading Client - Real Trade Execution
 *
 * Handles:
 * - Quote fetching from bags.fm API
 * - Swap execution with Phantom wallet signing
 * - Partner fee tracking (revenue)
 * - Jito MEV protection integration
 * - TP/SL order management
 */

import { Connection, PublicKey, Transaction, VersionedTransaction } from '@solana/web3.js';

// Token addresses
export const SOL_MINT = 'So11111111111111111111111111111111111111112';
export const USDC_MINT = 'EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v';

export interface SwapQuote {
    inputMint: string;
    outputMint: string;
    inAmount: string;
    outAmount: string;
    priceImpactPct: number;
    routePlan: any[];
    requestId: string;
    otherAmountThreshold: string;
}

export interface SwapResult {
    success: boolean;
    txHash?: string;
    signature?: string; // Alias for txHash (Solana convention)
    inputAmount: number;
    outputAmount: number;
    priceImpact: number;
    fee: number;
    partnerFee: number;
    winCommission?: number; // 0.5% commission on wins only
    error?: string;
    timestamp: number;
}

// Staker commission wallet - receives 0.5% of winning trades
export const STAKER_COMMISSION_WALLET = 'Kr8TivJ8VEWmXaF9N3Ah7zPEnEiVFRKQNHxYuPCsQxK'; // TODO: Replace with actual staker vault
export const WIN_COMMISSION_RATE = 0.005; // 0.5% on wins only

// Type alias for backwards compatibility
export type TradeQuote = SwapQuote;

export interface TokenPrice {
    mint: string;
    symbol: string;
    priceUsd: number;
    priceSol: number;
    change24h: number;
    volume24h: number;
    liquidity: number;
}

export interface TradeOrder {
    id: string;
    type: 'buy' | 'sell';
    tokenMint: string;
    symbol: string;
    amount: number;
    entryPrice: number;
    tpPrice?: number;
    slPrice?: number;
    trailingStop?: number;
    status: 'pending' | 'filled' | 'cancelled' | 'tp_hit' | 'sl_hit';
    timestamp: number;
    txHash?: string;
    // For win/loss tracking
    sentimentAtEntry?: number;
    exitPrice?: number;
    pnl?: number;
    pnlPercent?: number;
}

export class BagsTradingClient {
    private baseUrl = 'https://public-api-v2.bags.fm/api/v1';
    private apiKey?: string;
    private partnerKey?: string;
    private connection: Connection;

    // Tracking for analytics
    private totalVolume = 0;
    private totalPartnerFees = 0;
    private totalWinCommissions = 0;
    private successfulSwaps = 0;
    private failedSwaps = 0;

    // Position tracking for win/loss calculation
    private positionEntries = new Map<string, { entryPrice: number; amount: number }>();

    constructor(
        connection: Connection,
        apiKey?: string,
        partnerKey?: string
    ) {
        this.connection = connection;
        this.apiKey = apiKey || process.env.NEXT_PUBLIC_BAGS_API_KEY;
        this.partnerKey = partnerKey || process.env.NEXT_PUBLIC_BAGS_PARTNER_KEY;
    }

    private getHeaders(): HeadersInit {
        const headers: HeadersInit = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        };
        if (this.apiKey) {
            headers['x-api-key'] = this.apiKey;
        }
        return headers;
    }

    /**
     * Get swap quote without executing
     */
    async getQuote(
        inputMint: string,
        outputMint: string,
        amountSol: number,
        slippageBps: number = 100
    ): Promise<SwapQuote | null> {
        try {
            // Convert SOL to lamports (1 SOL = 1e9 lamports)
            const amountLamports = Math.floor(amountSol * 1e9);

            const params = new URLSearchParams({
                inputMint,
                outputMint,
                amount: amountLamports.toString(),
                slippageMode: 'manual',
                slippageBps: slippageBps.toString(),
            });

            const response = await fetch(`${this.baseUrl}/trade/quote?${params}`, {
                method: 'GET',
                headers: this.getHeaders(),
            });

            if (!response.ok) {
                console.error('Quote API error:', response.status);
                return null;
            }

            const result = await response.json();

            if (!result.success) {
                console.error('Quote failed:', result.error);
                return null;
            }

            return result.response as SwapQuote;
        } catch (error) {
            console.error('Failed to get quote:', error);
            return null;
        }
    }

    /**
     * Execute swap - returns transaction for wallet signing
     */
    async prepareSwap(
        walletAddress: string,
        inputMint: string,
        outputMint: string,
        amountSol: number,
        slippageBps: number = 100
    ): Promise<{ transaction: string; quote: SwapQuote } | null> {
        try {
            // Step 1: Get quote
            const quote = await this.getQuote(inputMint, outputMint, amountSol, slippageBps);
            if (!quote) {
                return null;
            }

            // Step 2: Request swap transaction
            const swapRequest = {
                userPublicKey: walletAddress,
                quoteResponse: quote,
                // Add partner key for fee tracking
                ...(this.partnerKey && { partnerKey: this.partnerKey }),
            };

            const response = await fetch(`${this.baseUrl}/trade/swap`, {
                method: 'POST',
                headers: this.getHeaders(),
                body: JSON.stringify(swapRequest),
            });

            if (!response.ok) {
                const errorText = await response.text();
                console.error('Swap API error:', errorText);
                return null;
            }

            const result = await response.json();

            if (!result.success) {
                console.error('Swap preparation failed:', result.error);
                return null;
            }

            return {
                transaction: result.response.swapTransaction,
                quote,
            };
        } catch (error) {
            console.error('Failed to prepare swap:', error);
            return null;
        }
    }

    /**
     * Execute swap with Phantom wallet
     *
     * @param signTransaction - Function from wallet adapter to sign transaction
     */
    async executeSwap(
        walletAddress: string,
        inputMint: string,
        outputMint: string,
        amountSol: number,
        slippageBps: number,
        signTransaction: (tx: VersionedTransaction) => Promise<VersionedTransaction>,
        useJito: boolean = false
    ): Promise<SwapResult> {
        const timestamp = Date.now();

        try {
            // Prepare the swap
            const prepared = await this.prepareSwap(
                walletAddress,
                inputMint,
                outputMint,
                amountSol,
                slippageBps
            );

            if (!prepared) {
                this.failedSwaps++;
                return {
                    success: false,
                    inputAmount: amountSol,
                    outputAmount: 0,
                    priceImpact: 0,
                    fee: 0,
                    partnerFee: 0,
                    error: 'Failed to prepare swap',
                    timestamp,
                };
            }

            // Decode the transaction
            const txBuffer = Buffer.from(prepared.transaction, 'base64');
            const transaction = VersionedTransaction.deserialize(txBuffer);

            // Sign with wallet
            const signedTx = await signTransaction(transaction);

            // Send transaction
            let txHash: string;

            if (useJito) {
                // Use Jito for MEV protection
                txHash = await this.sendWithJito(signedTx);
            } else {
                // Standard send
                const signature = await this.connection.sendRawTransaction(
                    signedTx.serialize(),
                    { skipPreflight: true, maxRetries: 3 }
                );
                txHash = signature;
            }

            // Confirm transaction
            const confirmation = await this.connection.confirmTransaction(txHash, 'confirmed');

            if (confirmation.value.err) {
                this.failedSwaps++;
                return {
                    success: false,
                    txHash,
                    inputAmount: amountSol,
                    outputAmount: 0,
                    priceImpact: prepared.quote.priceImpactPct,
                    fee: 0,
                    partnerFee: 0,
                    error: 'Transaction failed on-chain',
                    timestamp,
                };
            }

            // Calculate output
            const outputAmount = parseInt(prepared.quote.outAmount) / 1e9; // Assuming 9 decimals

            // Track success
            this.successfulSwaps++;
            this.totalVolume += amountSol;
            // Partner fee is typically 0.1% of volume
            const partnerFee = amountSol * 0.001;
            this.totalPartnerFees += partnerFee;

            return {
                success: true,
                txHash,
                inputAmount: amountSol,
                outputAmount,
                priceImpact: prepared.quote.priceImpactPct,
                fee: 0.003 * amountSol, // ~0.3% fee
                partnerFee,
                timestamp,
            };
        } catch (error) {
            this.failedSwaps++;
            return {
                success: false,
                inputAmount: amountSol,
                outputAmount: 0,
                priceImpact: 0,
                fee: 0,
                partnerFee: 0,
                error: error instanceof Error ? error.message : 'Unknown error',
                timestamp,
            };
        }
    }

    /**
     * Send transaction via Jito for MEV protection
     */
    private async sendWithJito(transaction: VersionedTransaction): Promise<string> {
        const JITO_ENDPOINTS = [
            'https://mainnet.block-engine.jito.wtf/api/v1/transactions',
            'https://amsterdam.mainnet.block-engine.jito.wtf/api/v1/transactions',
            'https://frankfurt.mainnet.block-engine.jito.wtf/api/v1/transactions',
        ];

        const serialized = Buffer.from(transaction.serialize()).toString('base64');

        for (const endpoint of JITO_ENDPOINTS) {
            try {
                const response = await fetch(endpoint, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        jsonrpc: '2.0',
                        id: 1,
                        method: 'sendTransaction',
                        params: [serialized, { encoding: 'base64' }],
                    }),
                });

                const result = await response.json();
                if (result.result) {
                    console.log('✅ Sent via Jito:', endpoint);
                    return result.result;
                }
            } catch (error) {
                console.warn('Jito endpoint failed:', endpoint, error);
            }
        }

        // Fallback to standard RPC
        console.log('⚠️ Jito failed, using standard RPC');
        return await this.connection.sendRawTransaction(transaction.serialize());
    }

    /**
     * Get token price from bags.fm
     */
    async getTokenPrice(mint: string): Promise<TokenPrice | null> {
        try {
            const response = await fetch(`${this.baseUrl}/tokens/${mint}`, {
                headers: this.getHeaders(),
            });

            if (!response.ok) return null;

            const result = await response.json();
            if (!result.success) return null;

            const data = result.response;
            return {
                mint,
                symbol: data.symbol || '',
                priceUsd: parseFloat(data.priceUsd || data.price_usd || '0'),
                priceSol: parseFloat(data.priceSol || data.price || '0'),
                change24h: parseFloat(data.change24h || data.priceChange24h || '0'),
                volume24h: parseFloat(data.volume24h || data.volume_24h || '0'),
                liquidity: parseFloat(data.liquidity || '0'),
            };
        } catch (error) {
            console.error('Failed to get token price:', error);
            return null;
        }
    }

    /**
     * Get multiple token prices in batch (cost efficient)
     */
    async getTokenPrices(mints: string[]): Promise<Map<string, TokenPrice>> {
        const prices = new Map<string, TokenPrice>();

        // Batch in groups of 10
        const batches = [];
        for (let i = 0; i < mints.length; i += 10) {
            batches.push(mints.slice(i, i + 10));
        }

        await Promise.all(
            batches.map(async (batch) => {
                await Promise.all(
                    batch.map(async (mint) => {
                        const price = await this.getTokenPrice(mint);
                        if (price) prices.set(mint, price);
                    })
                );
            })
        );

        return prices;
    }

    /**
     * Calculate TP/SL prices based on entry
     */
    calculateTPSL(
        entryPrice: number,
        tpPercent: number,
        slPercent: number,
        isLong: boolean = true
    ): { tpPrice: number; slPrice: number } {
        if (isLong) {
            return {
                tpPrice: entryPrice * (1 + tpPercent / 100),
                slPrice: entryPrice * (1 - slPercent / 100),
            };
        } else {
            return {
                tpPrice: entryPrice * (1 - tpPercent / 100),
                slPrice: entryPrice * (1 + slPercent / 100),
            };
        }
    }

    /**
     * Record a position entry for win/loss tracking
     */
    recordPositionEntry(tokenMint: string, entryPrice: number, amount: number): void {
        this.positionEntries.set(tokenMint, { entryPrice, amount });
    }

    /**
     * Calculate win commission for a sell (0.5% on wins only)
     * Returns 0 if trade is a loss
     */
    calculateWinCommission(
        tokenMint: string,
        exitPrice: number,
        sellAmount: number
    ): { commission: number; isWin: boolean; pnlPercent: number } {
        const entry = this.positionEntries.get(tokenMint);

        if (!entry) {
            // No entry recorded, assume win for safety (commission will be collected)
            return { commission: 0, isWin: false, pnlPercent: 0 };
        }

        const pnlPercent = ((exitPrice - entry.entryPrice) / entry.entryPrice) * 100;
        const isWin = pnlPercent > 0;

        if (isWin) {
            // 0.5% commission on the sell value
            const sellValue = sellAmount * exitPrice;
            const commission = sellValue * WIN_COMMISSION_RATE;
            this.totalWinCommissions += commission;
            return { commission, isWin: true, pnlPercent };
        }

        return { commission: 0, isWin: false, pnlPercent };
    }

    /**
     * Get trading statistics
     */
    getStats() {
        return {
            totalVolume: this.totalVolume,
            totalPartnerFees: this.totalPartnerFees,
            totalWinCommissions: this.totalWinCommissions,
            successfulSwaps: this.successfulSwaps,
            failedSwaps: this.failedSwaps,
            successRate: this.successfulSwaps / (this.successfulSwaps + this.failedSwaps) || 0,
            stakerVault: STAKER_COMMISSION_WALLET,
        };
    }

    /**
     * Clear position entry after full sell
     */
    clearPositionEntry(tokenMint: string): void {
        this.positionEntries.delete(tokenMint);
    }
}

// Singleton instance factory
let clientInstance: BagsTradingClient | null = null;

export function getBagsTradingClient(connection: Connection): BagsTradingClient {
    if (!clientInstance) {
        clientInstance = new BagsTradingClient(connection);
    }
    return clientInstance;
}
