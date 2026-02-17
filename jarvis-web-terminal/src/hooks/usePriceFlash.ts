'use client';

import { useState, useEffect, useRef } from 'react';

/**
 * Returns a CSS class name ('flash-green' | 'flash-red' | '')
 * that briefly flashes when price changes up or down.
 *
 * The flash class is applied for 600ms then cleared.
 * Matches the CSS animations defined in globals.css.
 */
export function usePriceFlash(price: number): string {
  const [flashClass, setFlashClass] = useState('');
  const prevPriceRef = useRef<number>(price);
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    const prevPrice = prevPriceRef.current;

    if (price !== prevPrice) {
      // Clear any pending timeout from a previous flash
      if (timeoutRef.current !== null) {
        clearTimeout(timeoutRef.current);
      }

      // Set flash direction
      setFlashClass(price > prevPrice ? 'flash-green' : 'flash-red');

      // Clear flash after 600ms (matches CSS animation duration)
      timeoutRef.current = setTimeout(() => {
        setFlashClass('');
        timeoutRef.current = null;
      }, 600);

      prevPriceRef.current = price;
    }

    return () => {
      if (timeoutRef.current !== null) {
        clearTimeout(timeoutRef.current);
      }
    };
  }, [price]);

  return flashClass;
}
