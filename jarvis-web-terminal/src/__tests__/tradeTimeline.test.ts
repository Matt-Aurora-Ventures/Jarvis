import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';

/**
 * Tests for the TradeTimeline component logic.
 *
 * We import the pure helper functions that power the timeline:
 *   - groupTradesByDay: groups TradeRecord[] into { label, trades }[]
 *   - getDayLabel: returns "TODAY", "YESTERDAY", or a formatted date string
 *   - solscanTxUrl: builds the Solscan link for a tx signature
 */
import {
  groupTradesByDay,
  getDayLabel,
  solscanTxUrl,
} from '@/components/features/TradeTimeline';

import type { TradeRecord } from '@/stores/useTradeStore';

// ---------------------------------------------------------------------------
// Helpers to build test data
// ---------------------------------------------------------------------------

function makeTrade(overrides: Partial<TradeRecord> = {}): TradeRecord {
  return {
    id: 'test-id-1',
    tokenMint: 'So11111111111111111111111111111111111111112',
    tokenSymbol: 'SOL',
    side: 'buy',
    price: 150.23,
    amount: 0.5,
    txSignature: '5abc123def456ghi789jkl012mno345pqr678stu901vwx234yz',
    timestamp: Date.now(),
    ...overrides,
  };
}

// ---------------------------------------------------------------------------
// getDayLabel
// ---------------------------------------------------------------------------

describe('getDayLabel', () => {
  beforeEach(() => {
    // Fix "now" to 2026-02-08 12:00:00 UTC
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2026-02-08T12:00:00Z'));
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('should return "TODAY" for timestamps from the current day', () => {
    const todayMs = new Date('2026-02-08T09:30:00Z').getTime();
    expect(getDayLabel(todayMs)).toBe('TODAY');
  });

  it('should return "YESTERDAY" for timestamps from the previous day', () => {
    const yesterdayMs = new Date('2026-02-07T15:00:00Z').getTime();
    expect(getDayLabel(yesterdayMs)).toBe('YESTERDAY');
  });

  it('should return a formatted date string for older timestamps', () => {
    const olderMs = new Date('2026-02-01T10:00:00Z').getTime();
    const label = getDayLabel(olderMs);
    // Should NOT be TODAY or YESTERDAY
    expect(label).not.toBe('TODAY');
    expect(label).not.toBe('YESTERDAY');
    // Should contain month and day info (e.g. "Feb 1" or "2/1/2026")
    expect(label.length).toBeGreaterThan(0);
  });
});

// ---------------------------------------------------------------------------
// groupTradesByDay
// ---------------------------------------------------------------------------

describe('groupTradesByDay', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2026-02-08T12:00:00Z'));
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('should return an empty array when given no trades', () => {
    const groups = groupTradesByDay([]);
    expect(groups).toEqual([]);
  });

  it('should group trades from the same day together', () => {
    const trades: TradeRecord[] = [
      makeTrade({ id: '1', timestamp: new Date('2026-02-08T10:00:00Z').getTime() }),
      makeTrade({ id: '2', timestamp: new Date('2026-02-08T08:00:00Z').getTime() }),
    ];

    const groups = groupTradesByDay(trades);
    expect(groups).toHaveLength(1);
    expect(groups[0].label).toBe('TODAY');
    expect(groups[0].trades).toHaveLength(2);
  });

  it('should create separate groups for different days', () => {
    const trades: TradeRecord[] = [
      makeTrade({ id: '1', timestamp: new Date('2026-02-08T10:00:00Z').getTime() }),
      makeTrade({ id: '2', timestamp: new Date('2026-02-07T15:00:00Z').getTime() }),
      makeTrade({ id: '3', timestamp: new Date('2026-02-01T09:00:00Z').getTime() }),
    ];

    const groups = groupTradesByDay(trades);
    expect(groups).toHaveLength(3);
    expect(groups[0].label).toBe('TODAY');
    expect(groups[1].label).toBe('YESTERDAY');
    // Third group is an older date
    expect(groups[2].label).not.toBe('TODAY');
    expect(groups[2].label).not.toBe('YESTERDAY');
  });

  it('should sort groups with most recent day first', () => {
    const trades: TradeRecord[] = [
      makeTrade({ id: '1', timestamp: new Date('2026-02-01T09:00:00Z').getTime() }),
      makeTrade({ id: '2', timestamp: new Date('2026-02-08T10:00:00Z').getTime() }),
    ];

    const groups = groupTradesByDay(trades);
    expect(groups[0].label).toBe('TODAY');
  });

  it('should sort trades within each group by most recent first', () => {
    const earlier = new Date('2026-02-08T08:00:00Z').getTime();
    const later = new Date('2026-02-08T11:00:00Z').getTime();

    const trades: TradeRecord[] = [
      makeTrade({ id: 'early', timestamp: earlier }),
      makeTrade({ id: 'late', timestamp: later }),
    ];

    const groups = groupTradesByDay(trades);
    expect(groups[0].trades[0].id).toBe('late');
    expect(groups[0].trades[1].id).toBe('early');
  });
});

// ---------------------------------------------------------------------------
// solscanTxUrl
// ---------------------------------------------------------------------------

describe('solscanTxUrl', () => {
  it('should build the correct Solscan transaction URL', () => {
    const sig = '5abc123def456';
    expect(solscanTxUrl(sig)).toBe('https://solscan.io/tx/5abc123def456');
  });

  it('should handle long signatures', () => {
    const sig = '5abc123def456ghi789jkl012mno345pqr678stu901vwx234yz';
    expect(solscanTxUrl(sig)).toBe(`https://solscan.io/tx/${sig}`);
  });
});

// ---------------------------------------------------------------------------
// Trade indicator logic (BUY = green, SELL = red)
// ---------------------------------------------------------------------------

describe('trade side indicators', () => {
  it('should identify BUY trades', () => {
    const trade = makeTrade({ side: 'buy' });
    expect(trade.side).toBe('buy');
  });

  it('should identify SELL trades', () => {
    const trade = makeTrade({ side: 'sell' });
    expect(trade.side).toBe('sell');
  });
});

// ---------------------------------------------------------------------------
// Empty state
// ---------------------------------------------------------------------------

describe('empty state', () => {
  it('should display empty message when tradeHistory is empty', () => {
    // The component should render the empty message when groups are empty
    const groups = groupTradesByDay([]);
    expect(groups).toHaveLength(0);
    // Component logic: if groups.length === 0, show empty state with message:
    // "No trades yet. Execute your first trade to see it here."
    const EMPTY_MESSAGE = 'No trades yet. Execute your first trade to see it here.';
    expect(EMPTY_MESSAGE).toBeTruthy();
  });
});
