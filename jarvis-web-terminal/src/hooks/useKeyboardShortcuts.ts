'use client';

import { useEffect } from 'react';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface ShortcutHandlers {
  onSearch?: () => void;
  onEscape?: () => void;
  onTimeframe?: (tf: string) => void;
  onBuy?: () => void;
  onToggleMode?: () => void;
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

export const TIMEFRAME_MAP: Record<string, string> = {
  '1': '1m',
  '2': '5m',
  '3': '15m',
  '4': '1h',
  '5': '4h',
  '6': '1d',
};

// ---------------------------------------------------------------------------
// Helpers (exported for testing)
// ---------------------------------------------------------------------------

/**
 * Returns true if the event target is an input/textarea/contentEditable
 * element where regular typing should not trigger shortcuts.
 */
export function isTextEntry(target: EventTarget | null): boolean {
  if (!target || !(target instanceof HTMLElement)) return false;
  const tag = target.tagName;
  if (tag === 'INPUT' || tag === 'TEXTAREA') return true;
  if (target.isContentEditable || target.contentEditable === 'true') return true;
  return false;
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

/**
 * Registers global keyboard shortcuts for the trading terminal.
 *
 * Shortcuts:
 *   / or Ctrl+K  -- Focus token search
 *   Escape       -- Close search/modals, blur active input
 *   1-6          -- Switch chart timeframe (1m, 5m, 15m, 1h, 4h, 1d)
 *   B            -- Focus buy amount input
 *   T            -- Toggle between Spot/Perps mode
 *
 * All shortcuts except Escape are suppressed when the user is typing in an
 * input, textarea, or contentEditable element.
 */
export function useKeyboardShortcuts(handlers: ShortcutHandlers) {
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement;

      // When user is typing in a text field, only allow Escape through
      if (isTextEntry(target)) {
        if (e.key === 'Escape') {
          handlers.onEscape?.();
          (target as HTMLInputElement).blur();
        }
        return;
      }

      switch (e.key) {
        case '/':
          e.preventDefault();
          handlers.onSearch?.();
          break;
        case 'k':
          if (e.ctrlKey || e.metaKey) {
            e.preventDefault();
            handlers.onSearch?.();
          }
          break;
        case 'Escape':
          handlers.onEscape?.();
          break;
        case '1':
        case '2':
        case '3':
        case '4':
        case '5':
        case '6':
          handlers.onTimeframe?.(TIMEFRAME_MAP[e.key]);
          break;
        case 'b':
        case 'B':
          handlers.onBuy?.();
          break;
        case 't':
        case 'T':
          handlers.onToggleMode?.();
          break;
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [handlers]);
}
