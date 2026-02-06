/**
 * Jito MEV Protection - Bundle transactions for front-running protection
 * 
 * When Shield Reactor is active:
 * - Bundles swap transaction with 0.001 SOL tip to Jito validator
 * - Provides MEV protection against sandwich attacks
 * - Falls back to standard Jupiter if Jito fails
 */

import {
    Connection,
    PublicKey,
    Transaction,
    TransactionInstruction,
    SystemProgram,
    LAMPORTS_PER_SOL,
    VersionedTransaction,
    TransactionMessage,
    AddressLookupTableAccount,
} from '@solana/web3.js';

// Jito tip accounts (any one will work)
const JITO_TIP_ACCOUNTS = [
    '96gYZGLnJYVFmbjzopPSU6QiEV5fGqZNyN9nmNhvrZU5',
    'HFqU5x63VTqvQss8hp11i4bVV2rXvGPe8grz8fDzM3t',
    'Cw8CFyM9FkoMi7K7Crf6HNQqf4uEMzpKw6QNghXLvLkY',
    'ADaUMid9yfUytqMBgopwjb2DTLSokTSzL1zt6iGPaS49',
    'DfXygSm4jCyNCybVYYK6DwvWqjKee8pbDmJGcLWNDXjh',
    'ADuUkR4vqLUMWXxW9gh6D6L8pMSawimctcNZ5pGwDcEt',
    'DttWaMuVvTiduZRnguLF7jNxTgiMBZ1hyAumKUiL2KRL',
    '3AVi9Tg9Uo68tJfuvoKvqKNWKkC5wPdSSdeBnizKZ6jT',
];

// Jito block engine endpoints
const JITO_ENDPOINTS = [
    'https://mainnet.block-engine.jito.wtf/api/v1/bundles',
    'https://amsterdam.mainnet.block-engine.jito.wtf/api/v1/bundles',
    'https://frankfurt.mainnet.block-engine.jito.wtf/api/v1/bundles',
    'https://ny.mainnet.block-engine.jito.wtf/api/v1/bundles',
    'https://tokyo.mainnet.block-engine.jito.wtf/api/v1/bundles',
];

export interface JitoBundleResult {
    success: boolean;
    bundleId?: string;
    signature?: string;
    error?: string;
}

export interface PriorityFeeLevel {
    label: string;
    microLamports: number;
    description: string;
    estimatedTimeMs: number;
}

// Priority fee tiers
export const PRIORITY_FEE_TIERS: Record<string, PriorityFeeLevel> = {
    eco: {
        label: 'Eco',
        microLamports: 1000, // 0.000001 SOL per CU
        description: 'Lowest cost, may take longer',
        estimatedTimeMs: 30000,
    },
    fast: {
        label: 'Fast',
        microLamports: 50000, // 0.00005 SOL per CU
        description: 'Standard priority',
        estimatedTimeMs: 5000,
    },
    turbo: {
        label: 'Turbo',
        microLamports: 200000, // 0.0002 SOL per CU
        description: 'Highest priority + Jito MEV protection',
        estimatedTimeMs: 1000,
    },
};

// Default Jito tip amount (0.001 SOL)
const JITO_TIP_LAMPORTS = 0.001 * LAMPORTS_PER_SOL;

export class JitoClient {
    private connection: Connection;
    private tipAccountIndex = 0;

    constructor(connection: Connection) {
        this.connection = connection;
    }

    /**
     * Get a random Jito tip account
     */
    private getTipAccount(): PublicKey {
        // Round-robin through tip accounts
        const account = JITO_TIP_ACCOUNTS[this.tipAccountIndex];
        this.tipAccountIndex = (this.tipAccountIndex + 1) % JITO_TIP_ACCOUNTS.length;
        return new PublicKey(account);
    }

    /**
     * Create a tip instruction for Jito validator
     */
    createTipInstruction(
        payer: PublicKey,
        tipLamports: number = JITO_TIP_LAMPORTS
    ): TransactionInstruction {
        return SystemProgram.transfer({
            fromPubkey: payer,
            toPubkey: this.getTipAccount(),
            lamports: tipLamports,
        });
    }

    /**
     * Add Jito tip to an existing transaction
     */
    async addTipToTransaction(
        transaction: Transaction,
        payer: PublicKey,
        tipLamports: number = JITO_TIP_LAMPORTS
    ): Promise<Transaction> {
        const tipInstruction = this.createTipInstruction(payer, tipLamports);
        transaction.add(tipInstruction);
        return transaction;
    }

    /**
     * Send transaction as a Jito bundle
     */
    async sendBundle(
        signedTransactions: (Transaction | VersionedTransaction)[],
        timeout: number = 30000
    ): Promise<JitoBundleResult> {
        const serializedTxs = signedTransactions.map(tx => {
            const serialized = tx.serialize();
            return Buffer.from(serialized).toString('base64');
        });

        // Try each Jito endpoint
        for (const endpoint of JITO_ENDPOINTS) {
            try {
                const response = await fetch(endpoint, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        jsonrpc: '2.0',
                        id: 1,
                        method: 'sendBundle',
                        params: [serializedTxs],
                    }),
                });

                if (!response.ok) continue;

                const result = await response.json();

                if (result.error) {
                    console.warn(`Jito bundle error from ${endpoint}:`, result.error);
                    continue;
                }

                const bundleId = result.result;

                // Wait for bundle confirmation
                const confirmed = await this.waitForBundleConfirmation(
                    bundleId,
                    endpoint,
                    timeout
                );

                if (confirmed) {
                    return {
                        success: true,
                        bundleId,
                    };
                }
            } catch (error) {
                console.warn(`Jito endpoint ${endpoint} failed:`, error);
                continue;
            }
        }

        return {
            success: false,
            error: 'All Jito endpoints failed',
        };
    }

    /**
     * Wait for bundle confirmation
     */
    private async waitForBundleConfirmation(
        bundleId: string,
        endpoint: string,
        timeout: number
    ): Promise<boolean> {
        const startTime = Date.now();
        const statusEndpoint = endpoint.replace('/bundles', '/bundle_status');

        while (Date.now() - startTime < timeout) {
            try {
                const response = await fetch(statusEndpoint, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        jsonrpc: '2.0',
                        id: 1,
                        method: 'getBundleStatuses',
                        params: [[bundleId]],
                    }),
                });

                const result = await response.json();
                const status = result.result?.value?.[0];

                if (status) {
                    if (status.confirmation_status === 'confirmed' ||
                        status.confirmation_status === 'finalized') {
                        return true;
                    }
                    if (status.err) {
                        console.warn('Bundle failed:', status.err);
                        return false;
                    }
                }
            } catch {
                // Ignore errors during polling
            }

            await new Promise(resolve => setTimeout(resolve, 1000));
        }

        return false;
    }

    /**
     * Get recent priority fees from the network
     */
    async getRecentPriorityFees(): Promise<{
        min: number;
        median: number;
        max: number;
    }> {
        try {
            const fees = await this.connection.getRecentPrioritizationFees();

            if (!fees || fees.length === 0) {
                return { min: 1000, median: 50000, max: 200000 };
            }

            const sortedFees = fees
                .map(f => f.prioritizationFee)
                .sort((a, b) => a - b);

            return {
                min: sortedFees[0],
                median: sortedFees[Math.floor(sortedFees.length / 2)],
                max: sortedFees[sortedFees.length - 1],
            };
        } catch {
            return { min: 1000, median: 50000, max: 200000 };
        }
    }
}

/**
 * Execute trade with waterfall redundancy:
 * 1. Try Jito bundle (if Shield Reactor active)
 * 2. Fall back to standard Jupiter with priority fees
 */
export async function executeTradeWithProtection(
    connection: Connection,
    transaction: Transaction | VersionedTransaction,
    payer: PublicKey,
    signTransaction: (tx: Transaction | VersionedTransaction) => Promise<Transaction | VersionedTransaction>,
    options: {
        useJito: boolean;
        priorityFee: 'eco' | 'fast' | 'turbo';
        jitoTimeout?: number;
    }
): Promise<{ success: boolean; signature?: string; error?: string; method: 'jito' | 'jupiter' }> {
    const jitoClient = new JitoClient(connection);
    const { useJito, priorityFee, jitoTimeout = 30000 } = options;

    // If Jito is enabled (Shield Reactor active)
    if (useJito && priorityFee === 'turbo') {
        console.log('🛡️ Executing with Jito MEV protection...');

        try {
            // Add Jito tip to transaction
            if (transaction instanceof Transaction) {
                await jitoClient.addTipToTransaction(transaction, payer);
            }

            // Sign the transaction
            const signedTx = await signTransaction(transaction);

            // Send via Jito bundle
            const result = await jitoClient.sendBundle([signedTx], jitoTimeout);

            if (result.success) {
                return {
                    success: true,
                    signature: result.bundleId,
                    method: 'jito',
                };
            }

            console.warn('Jito bundle failed, falling back to Jupiter...');
        } catch (error) {
            console.warn('Jito execution failed:', error);
        }
    }

    // Fallback: Standard Jupiter execution with priority fees
    console.log(`📡 Executing with Jupiter (${priorityFee} priority)...`);

    try {
        const signedTx = await signTransaction(transaction);

        const serialized = signedTx.serialize();
        const signature = await connection.sendRawTransaction(serialized, {
            skipPreflight: false,
            preflightCommitment: 'confirmed',
            maxRetries: 3,
        });

        // Wait for confirmation
        const confirmation = await connection.confirmTransaction(signature, 'confirmed');

        if (confirmation.value.err) {
            throw new Error(`Transaction failed: ${JSON.stringify(confirmation.value.err)}`);
        }

        return {
            success: true,
            signature,
            method: 'jupiter',
        };
    } catch (error) {
        return {
            success: false,
            error: error instanceof Error ? error.message : 'Transaction failed',
            method: 'jupiter',
        };
    }
}

export const jitoClient = (connection: Connection) => new JitoClient(connection);
