'use client';

import { useState, useEffect, useRef } from 'react';
import { Keyboard } from 'lucide-react';

const SHORTCUTS = [
  { label: 'Search', keys: ['/', 'Ctrl+K'] },
  { label: 'Chart 1m-1d', keys: ['1', '-', '6'] },
  { label: 'Buy', keys: ['B'] },
  { label: 'Toggle Mode', keys: ['T'] },
  { label: 'Close / Blur', keys: ['Esc'] },
] as const;

export function KeyboardShortcutsHelp() {
  const [isOpen, setIsOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  // Close on outside click
  useEffect(() => {
    if (!isOpen) return;
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, [isOpen]);

  // Close on Escape
  useEffect(() => {
    if (!isOpen) return;
    function handleKey(e: KeyboardEvent) {
      if (e.key === 'Escape') setIsOpen(false);
    }
    window.addEventListener('keydown', handleKey);
    return () => window.removeEventListener('keydown', handleKey);
  }, [isOpen]);

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="p-2.5 rounded-full bg-bg-tertiary hover:bg-bg-secondary border border-border-primary hover:border-border-hover transition-all group"
        aria-label="Keyboard shortcuts"
        aria-expanded={isOpen}
        title="Keyboard shortcuts"
      >
        <Keyboard className="w-4 h-4 text-text-secondary group-hover:text-text-primary transition-colors" />
      </button>

      {isOpen && (
        <div
          className="absolute top-full right-0 mt-2 card-glass p-4 w-64 z-50 animate-fade-in"
          role="dialog"
          aria-label="Keyboard shortcuts reference"
        >
          <h4 className="text-sm font-bold text-text-primary mb-3 flex items-center gap-2">
            <Keyboard className="w-3.5 h-3.5 text-accent-neon" />
            Keyboard Shortcuts
          </h4>
          <div className="space-y-2">
            {SHORTCUTS.map(({ label, keys }) => (
              <div key={label} className="flex items-center justify-between text-xs">
                <span className="text-text-secondary">{label}</span>
                <div className="flex items-center gap-1">
                  {keys.map((key) =>
                    key === '-' ? (
                      <span key={key} className="text-text-muted">-</span>
                    ) : (
                      <kbd key={key} className="kbd-key">{key}</kbd>
                    )
                  )}
                </div>
              </div>
            ))}
          </div>
          <div className="mt-3 pt-2 border-t border-border-primary">
            <p className="text-[10px] text-text-muted font-mono">
              Shortcuts disabled while typing in inputs
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
