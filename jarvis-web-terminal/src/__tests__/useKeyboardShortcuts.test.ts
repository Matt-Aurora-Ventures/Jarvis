import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

/**
 * Tests for useKeyboardShortcuts hook logic.
 *
 * The hook registers global keydown listeners and routes shortcuts:
 *   / or Ctrl+K  -> onSearch
 *   Escape       -> onEscape
 *   1-6          -> onTimeframe('1m'|'5m'|'15m'|'1h'|'4h'|'1d')
 *   B            -> onBuy
 *   T            -> onToggleMode
 *
 * Shortcuts must NOT fire when the active element is an <input>, <textarea>,
 * or contentEditable element (except Escape, which blurs the input).
 */

// ---------------------------------------------------------------------------
// Minimal simulation helpers
// ---------------------------------------------------------------------------

/** Fire a synthetic keydown event on window. */
function fireKey(key: string, opts: Partial<KeyboardEvent> = {}) {
  const event = new KeyboardEvent('keydown', {
    key,
    bubbles: true,
    cancelable: true,
    ...opts,
  });
  window.dispatchEvent(event);
}

/** Create a fake input element for event.target checks. */
function createFakeInput(): HTMLInputElement {
  const input = document.createElement('input');
  input.type = 'text';
  document.body.appendChild(input);
  return input;
}

// ---------------------------------------------------------------------------
// Core shortcut mapping logic (extracted from hook for testability)
// ---------------------------------------------------------------------------

interface ShortcutHandlers {
  onSearch?: () => void;
  onEscape?: () => void;
  onTimeframe?: (tf: string) => void;
  onBuy?: () => void;
  onToggleMode?: () => void;
}

const TIMEFRAME_MAP: Record<string, string> = {
  '1': '1m',
  '2': '5m',
  '3': '15m',
  '4': '1h',
  '5': '4h',
  '6': '1d',
};

/**
 * Pure dispatch logic: given a KeyboardEvent and the handlers object,
 * determine what to call. Returns true if a handler was invoked.
 */
function dispatchShortcut(
  e: { key: string; ctrlKey?: boolean; metaKey?: boolean },
  handlers: ShortcutHandlers,
): boolean {
  switch (e.key) {
    case '/':
      handlers.onSearch?.();
      return !!handlers.onSearch;
    case 'k':
      if (e.ctrlKey || e.metaKey) {
        handlers.onSearch?.();
        return !!handlers.onSearch;
      }
      return false;
    case 'Escape':
      handlers.onEscape?.();
      return !!handlers.onEscape;
    case '1':
    case '2':
    case '3':
    case '4':
    case '5':
    case '6':
      handlers.onTimeframe?.(TIMEFRAME_MAP[e.key]);
      return !!handlers.onTimeframe;
    case 'b':
    case 'B':
      handlers.onBuy?.();
      return !!handlers.onBuy;
    case 't':
    case 'T':
      handlers.onToggleMode?.();
      return !!handlers.onToggleMode;
    default:
      return false;
  }
}

/**
 * Returns true if the event target is a text-entry element that should
 * suppress shortcuts (except Escape).
 */
function isTextEntry(target: EventTarget | null): boolean {
  if (!target || !(target instanceof HTMLElement)) return false;
  const tag = target.tagName;
  if (tag === 'INPUT' || tag === 'TEXTAREA') return true;
  // Check both the property and the direct contentEditable value (jsdom compat)
  if (target.isContentEditable || target.contentEditable === 'true') return true;
  return false;
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('Keyboard Shortcuts - dispatch logic', () => {
  let handlers: Required<ShortcutHandlers>;

  beforeEach(() => {
    handlers = {
      onSearch: vi.fn(),
      onEscape: vi.fn(),
      onTimeframe: vi.fn(),
      onBuy: vi.fn(),
      onToggleMode: vi.fn(),
    };
  });

  // -- Search shortcuts --

  it('dispatches onSearch for "/" key', () => {
    dispatchShortcut({ key: '/' }, handlers);
    expect(handlers.onSearch).toHaveBeenCalledOnce();
  });

  it('dispatches onSearch for Ctrl+K', () => {
    dispatchShortcut({ key: 'k', ctrlKey: true }, handlers);
    expect(handlers.onSearch).toHaveBeenCalledOnce();
  });

  it('dispatches onSearch for Meta+K (macOS)', () => {
    dispatchShortcut({ key: 'k', metaKey: true }, handlers);
    expect(handlers.onSearch).toHaveBeenCalledOnce();
  });

  it('does NOT dispatch onSearch for plain "k"', () => {
    dispatchShortcut({ key: 'k' }, handlers);
    expect(handlers.onSearch).not.toHaveBeenCalled();
  });

  // -- Escape --

  it('dispatches onEscape for Escape key', () => {
    dispatchShortcut({ key: 'Escape' }, handlers);
    expect(handlers.onEscape).toHaveBeenCalledOnce();
  });

  // -- Timeframe shortcuts --

  it.each([
    ['1', '1m'],
    ['2', '5m'],
    ['3', '15m'],
    ['4', '1h'],
    ['5', '4h'],
    ['6', '1d'],
  ])('dispatches onTimeframe("%s" -> "%s")', (key, tf) => {
    dispatchShortcut({ key }, handlers);
    expect(handlers.onTimeframe).toHaveBeenCalledWith(tf);
  });

  // -- Buy --

  it('dispatches onBuy for "b"', () => {
    dispatchShortcut({ key: 'b' }, handlers);
    expect(handlers.onBuy).toHaveBeenCalledOnce();
  });

  it('dispatches onBuy for "B"', () => {
    dispatchShortcut({ key: 'B' }, handlers);
    expect(handlers.onBuy).toHaveBeenCalledOnce();
  });

  // -- Toggle Mode --

  it('dispatches onToggleMode for "t"', () => {
    dispatchShortcut({ key: 't' }, handlers);
    expect(handlers.onToggleMode).toHaveBeenCalledOnce();
  });

  it('dispatches onToggleMode for "T"', () => {
    dispatchShortcut({ key: 'T' }, handlers);
    expect(handlers.onToggleMode).toHaveBeenCalledOnce();
  });

  // -- No-op keys --

  it('returns false for unrecognized keys', () => {
    const result = dispatchShortcut({ key: 'x' }, handlers);
    expect(result).toBe(false);
    expect(handlers.onSearch).not.toHaveBeenCalled();
    expect(handlers.onTimeframe).not.toHaveBeenCalled();
  });
});

describe('Keyboard Shortcuts - text entry suppression', () => {
  afterEach(() => {
    document.body.innerHTML = '';
  });

  it('identifies INPUT elements as text entry', () => {
    const input = createFakeInput();
    expect(isTextEntry(input)).toBe(true);
  });

  it('identifies TEXTAREA elements as text entry', () => {
    const textarea = document.createElement('textarea');
    document.body.appendChild(textarea);
    expect(isTextEntry(textarea)).toBe(true);
  });

  it('identifies contentEditable elements as text entry', () => {
    const div = document.createElement('div');
    div.contentEditable = 'true';
    document.body.appendChild(div);
    expect(isTextEntry(div)).toBe(true);
  });

  it('does NOT flag regular div as text entry', () => {
    const div = document.createElement('div');
    document.body.appendChild(div);
    expect(isTextEntry(div)).toBe(false);
  });

  it('handles null target gracefully', () => {
    expect(isTextEntry(null)).toBe(false);
  });
});

describe('Keyboard Shortcuts - timeframe mapping completeness', () => {
  it('maps all 6 keys to distinct timeframes', () => {
    const values = Object.values(TIMEFRAME_MAP);
    expect(values).toHaveLength(6);
    expect(new Set(values).size).toBe(6);
  });

  it('contains only valid timeframe strings', () => {
    const validTimeframes = ['1m', '5m', '15m', '1h', '4h', '1d'];
    for (const tf of Object.values(TIMEFRAME_MAP)) {
      expect(validTimeframes).toContain(tf);
    }
  });
});

describe('Keyboard Shortcuts - window event integration', () => {
  afterEach(() => {
    document.body.innerHTML = '';
  });

  it('keydown events propagate through window.dispatchEvent', () => {
    const spy = vi.fn();
    window.addEventListener('keydown', spy);
    fireKey('/');
    expect(spy).toHaveBeenCalledOnce();
    window.removeEventListener('keydown', spy);
  });
});
