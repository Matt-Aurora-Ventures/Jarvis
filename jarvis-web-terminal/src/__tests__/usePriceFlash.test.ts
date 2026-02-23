import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { usePriceFlash } from '@/hooks/usePriceFlash';

describe('usePriceFlash', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it('should return empty string on initial render', () => {
    const { result } = renderHook(() => usePriceFlash(100));
    expect(result.current).toBe('');
  });

  it('should return flash-green when price increases', () => {
    const { result, rerender } = renderHook(
      ({ price }) => usePriceFlash(price),
      { initialProps: { price: 100 } }
    );

    // Initial render: no flash
    expect(result.current).toBe('');

    // Price goes up
    rerender({ price: 105 });
    expect(result.current).toBe('flash-green');
  });

  it('should return flash-red when price decreases', () => {
    const { result, rerender } = renderHook(
      ({ price }) => usePriceFlash(price),
      { initialProps: { price: 100 } }
    );

    expect(result.current).toBe('');

    // Price goes down
    rerender({ price: 95 });
    expect(result.current).toBe('flash-red');
  });

  it('should clear flash after 600ms timeout', () => {
    const { result, rerender } = renderHook(
      ({ price }) => usePriceFlash(price),
      { initialProps: { price: 100 } }
    );

    // Price goes up
    rerender({ price: 110 });
    expect(result.current).toBe('flash-green');

    // Advance time by 600ms
    act(() => {
      vi.advanceTimersByTime(600);
    });

    expect(result.current).toBe('');
  });

  it('should not flash when price stays the same', () => {
    const { result, rerender } = renderHook(
      ({ price }) => usePriceFlash(price),
      { initialProps: { price: 100 } }
    );

    expect(result.current).toBe('');

    // Same price
    rerender({ price: 100 });
    expect(result.current).toBe('');
  });

  it('should handle multiple consecutive price changes', () => {
    const { result, rerender } = renderHook(
      ({ price }) => usePriceFlash(price),
      { initialProps: { price: 100 } }
    );

    // Price goes up
    rerender({ price: 110 });
    expect(result.current).toBe('flash-green');

    // Price goes down before timeout clears
    rerender({ price: 90 });
    expect(result.current).toBe('flash-red');

    // After timeout, should clear
    act(() => {
      vi.advanceTimersByTime(600);
    });
    expect(result.current).toBe('');
  });
});
