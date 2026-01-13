/**
 * Keyboard shortcuts hook
 */
import { useEffect, useCallback } from 'react';

export const useKeyboardShortcuts = (shortcuts) => {
  const handleKeyDown = useCallback((event) => {
    const key = [
      event.ctrlKey && 'ctrl',
      event.metaKey && 'meta',
      event.shiftKey && 'shift',
      event.altKey && 'alt',
      event.key.toLowerCase()
    ].filter(Boolean).join('+');

    const handler = shortcuts[key];
    if (handler) {
      event.preventDefault();
      handler(event);
    }
  }, [shortcuts]);

  useEffect(() => {
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [handleKeyDown]);
};

export const useGlobalShortcuts = () => {
  useKeyboardShortcuts({
    'ctrl+k': () => document.getElementById('search-input')?.focus(),
    'ctrl+/': () => document.getElementById('help-modal')?.showModal(),
    'escape': () => document.activeElement?.blur(),
  });
};

export default useKeyboardShortcuts;
