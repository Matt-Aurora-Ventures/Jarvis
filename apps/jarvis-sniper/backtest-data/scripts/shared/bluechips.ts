/**
 * Bluechip Solana registry used by the live app.
 *
 * Backtest scripts import this so "bluechip" strategies operate on the curated
 * mint list (instead of "high score + high liquidity" random tokens).
 */

import { ALL_BLUECHIPS } from '../../../src/lib/bluechip-data';

export { ALL_BLUECHIPS };

export const BLUECHIP_MINTS = new Set<string>(ALL_BLUECHIPS.map(t => t.mintAddress));

