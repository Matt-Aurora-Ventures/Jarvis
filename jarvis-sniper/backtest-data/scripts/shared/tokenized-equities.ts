/**
 * Tokenized equities registry used by the live app.
 *
 * Backtest scripts import this so xStock/PreStock/Index strategies operate on the
 * curated mint list (instead of random Solana tokens).
 */

import {
  XSTOCKS,
  PRESTOCKS,
  INDEXES,
  COMMODITIES_TOKENS,
  ALL_TOKENIZED_EQUITIES,
} from '../../../src/lib/xstocks-data';

export { XSTOCKS, PRESTOCKS, INDEXES, COMMODITIES_TOKENS, ALL_TOKENIZED_EQUITIES };

export const XSTOCK_MINTS = new Set<string>(XSTOCKS.map(t => t.mintAddress));
export const PRESTOCK_MINTS = new Set<string>(PRESTOCKS.map(t => t.mintAddress));
export const INDEX_MINTS = new Set<string>(INDEXES.map(t => t.mintAddress));
export const COMMODITY_MINTS = new Set<string>(COMMODITIES_TOKENS.map(t => t.mintAddress));

export const ALL_TOKENIZED_EQUITY_MINTS = new Set<string>([
  ...XSTOCK_MINTS,
  ...PRESTOCK_MINTS,
  ...INDEX_MINTS,
  ...COMMODITY_MINTS,
]);

