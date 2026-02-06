'use client';

import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { ChevronDown } from 'lucide-react';

interface CollapsiblePanelProps {
  title: string;
  icon?: React.ReactNode;
  badge?: string | number;
  defaultExpanded?: boolean;
  children: React.ReactNode;
  className?: string;
  headerExtra?: React.ReactNode;
}

export function CollapsiblePanel({
  title,
  icon,
  badge,
  defaultExpanded = true,
  children,
  className = '',
  headerExtra,
}: CollapsiblePanelProps) {
  const [expanded, setExpanded] = useState(defaultExpanded);

  return (
    <div
      className={`card-glass ${!expanded ? 'border-b border-border-primary/20' : ''} ${className}`}
    >
      <button
        type="button"
        onClick={() => setExpanded((prev) => !prev)}
        className="flex w-full items-center justify-between px-4 py-3 cursor-pointer select-none transition-colors hover:bg-bg-secondary/30 rounded-t-[16px]"
      >
        <div className="flex items-center gap-2">
          {icon && (
            <span className={expanded ? 'text-accent-neon' : 'text-text-muted'}>
              {icon}
            </span>
          )}
          <span className="text-sm font-mono uppercase tracking-wider text-text-muted">
            {title}
          </span>
          {badge !== undefined && (
            <span className="ml-1 px-1.5 py-0.5 text-[10px] font-mono font-semibold uppercase rounded bg-accent-neon/15 text-accent-neon border border-accent-neon/30">
              {badge}
            </span>
          )}
        </div>

        <div className="flex items-center gap-2">
          {headerExtra}
          <motion.span
            animate={{ rotate: expanded ? 180 : 0 }}
            transition={{ duration: 0.2 }}
            className="text-text-muted"
          >
            <ChevronDown className="w-4 h-4" />
          </motion.span>
        </div>
      </button>

      <AnimatePresence initial={false}>
        {expanded && (
          <motion.div
            key="content"
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2, ease: [0.4, 0, 0.2, 1] }}
            style={{ overflow: 'hidden' }}
          >
            <div className="px-4 pb-4">
              {children}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
