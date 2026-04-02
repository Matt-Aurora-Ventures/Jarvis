/**
 * Fast Transaction Confirmation Polling
 *
 * After a transaction is signed and submitted, poll for on-chain confirmation
 * with aggressive short intervals instead of waiting for a long timeout.
 *
 * Confirmation pattern inspired by dexbotsdev/sol-trade-sdk `wait_for_confirm`:
 *   https://github.com/dexbotsdev/sol-trade-sdk
 *
 * dexbotsdev uses a 10-second confirmation window with 1s polling intervals.
 * We adapt this for the browser environment with configurable parameters.
 */

import { Connection, type TransactionSignature } from '@solana/web3.js';

export interface ConfirmOptions {
  /** Max seconds to wait for confirmation.  Default: 15. */
  maxWaitSeconds?: number;
  /** Polling interval in ms.  Default: 1000 (1s). */
  pollIntervalMs?: number;
  /** Solana commitment level.  Default: 'confirmed'. */
  commitment?: 'processed' | 'confirmed' | 'finalized';
  /** Called on each poll with elapsed seconds, for UI progress. */
  onPoll?: (elapsedSec: number) => void;
}

export type ConfirmResult =
  | { status: 'confirmed'; slot: number; elapsedMs: number }
  | { status: 'timeout'; elapsedMs: number }
  | { status: 'error'; error: string; elapsedMs: number };

/**
 * Poll for transaction confirmation with short intervals.
 *
 * Returns as soon as the transaction lands or the timeout is reached,
 * whichever comes first.  Does NOT throw — caller inspects `status`.
 */
export async function confirmTransaction(
  connection: Connection,
  signature: TransactionSignature,
  opts: ConfirmOptions = {},
): Promise<ConfirmResult> {
  const maxWaitMs = (opts.maxWaitSeconds ?? 15) * 1000;
  const pollMs = opts.pollIntervalMs ?? 1_000;
  const commitment = opts.commitment ?? 'confirmed';
  const start = Date.now();

  while (Date.now() - start < maxWaitMs) {
    try {
      const status = await connection.getSignatureStatus(signature, {
        searchTransactionHistory: false,
      });

      const value = status?.value;
      if (value) {
        if (value.err) {
          return {
            status: 'error',
            error: JSON.stringify(value.err),
            elapsedMs: Date.now() - start,
          };
        }

        const reached =
          commitment === 'processed'
            ? true
            : commitment === 'confirmed'
              ? value.confirmationStatus === 'confirmed' || value.confirmationStatus === 'finalized'
              : value.confirmationStatus === 'finalized';

        if (reached) {
          return {
            status: 'confirmed',
            slot: value.slot,
            elapsedMs: Date.now() - start,
          };
        }
      }
    } catch {
      // Transient RPC error — keep polling.
    }

    opts.onPoll?.(Math.round((Date.now() - start) / 1000));
    await new Promise((r) => setTimeout(r, pollMs));
  }

  return { status: 'timeout', elapsedMs: Date.now() - start };
}
