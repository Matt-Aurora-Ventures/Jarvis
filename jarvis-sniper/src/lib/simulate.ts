import { Connection, VersionedTransaction } from '@solana/web3.js';

export interface SimulationResult {
  ok: boolean;
  error?: string;
  unitsConsumed?: number;
}

/**
 * Pre-flight simulation of a swap transaction.
 * Catches on-chain failures (insufficient balance, slippage, etc.) before
 * the user signs, saving gas on txs that would revert.
 */
export async function simulateSwap(
  connection: Connection,
  transaction: VersionedTransaction,
): Promise<SimulationResult> {
  try {
    const result = await connection.simulateTransaction(transaction, {
      replaceRecentBlockhash: true,
      commitment: 'processed',
    });

    if (result.value.err) {
      const errStr =
        typeof result.value.err === 'string'
          ? result.value.err
          : JSON.stringify(result.value.err);
      return {
        ok: false,
        error: `Simulation failed: ${errStr}`,
        unitsConsumed: result.value.unitsConsumed ?? undefined,
      };
    }

    return { ok: true, unitsConsumed: result.value.unitsConsumed ?? undefined };
  } catch (err) {
    // If simulation itself fails (network error, etc.), let the tx through
    // rather than blocking trades on a flaky RPC call.
    console.warn('[simulate] Pre-flight simulation error (allowing tx):', err);
    return { ok: true };
  }
}
