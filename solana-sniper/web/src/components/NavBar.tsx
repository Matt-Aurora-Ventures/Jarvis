'use client';

import { usePathname } from 'next/navigation';
import Link from 'next/link';

const links = [
  { href: '/', label: 'Dashboard' },
  { href: '/trade', label: 'Trade' },
  { href: '/backtest', label: 'Backtests' },
  { href: '/optimize', label: 'Optimizer' },
];

export function NavBar() {
  const pathname = usePathname();

  return (
    <nav className="flex items-center gap-1">
      {links.map(link => {
        const active = pathname === link.href;
        return (
          <Link
            key={link.href}
            href={link.href}
            className={`text-xs px-3 py-1.5 rounded-lg transition-colors ${
              active
                ? 'bg-[var(--accent-dim)] text-[var(--accent)] border border-[var(--border-accent)]'
                : 'text-[var(--text-muted)] hover:text-[var(--text-secondary)] border border-transparent'
            }`}
          >
            {link.label}
          </Link>
        );
      })}
    </nav>
  );
}
