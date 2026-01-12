import React from 'react'
import { Bot, Wallet, Keyboard } from 'lucide-react'
import { formatSOL, formatUSD } from '../../lib/format'
import { ThemeToggle } from '../ui/ThemeToggle'

/**
 * TopNav - Main navigation header with theme toggle and shortcuts
 */
function TopNav({ walletData, children, onShowShortcuts }) {
  return (
    <div className="top-nav">
      <div className="nav-brand">
        <Bot size={24} />
        <span>Jarvis Trading</span>
      </div>

      <div className="nav-search">
        <input type="text" placeholder="Search tokens, addresses... (Ctrl+K)" />
      </div>

      <div className="nav-actions">
        <div className="price-ticker">
          <div className="ticker-item">
            <span className="ticker-symbol">SOL</span>
            <span className="ticker-price">
              {formatUSD(walletData?.sol_price)}
            </span>
          </div>
        </div>

        {/* Keyboard shortcuts button */}
        {onShowShortcuts && (
          <button
            className="btn btn-ghost btn-icon"
            onClick={onShowShortcuts}
            title="Keyboard shortcuts (Ctrl+/)"
            aria-label="Show keyboard shortcuts"
          >
            <Keyboard size={18} />
          </button>
        )}

        {/* Theme toggle */}
        <ThemeToggle />

        <button className="btn btn-ghost">
          <Wallet size={18} />
          {formatSOL(walletData?.balance_sol, 3)}
        </button>
        {children}
      </div>
    </div>
  )
}

export default TopNav
