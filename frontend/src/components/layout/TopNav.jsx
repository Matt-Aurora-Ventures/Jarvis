import React from 'react'
import { Bot, Wallet } from 'lucide-react'
import { formatSOL, formatUSD } from '../../lib/format'

/**
 * TopNav - Main navigation header
 */
function TopNav({ walletData, children }) {
  return (
    <div className="top-nav">
      <div className="nav-brand">
        <Bot size={24} />
        <span>Jarvis Trading</span>
      </div>

      <div className="nav-search">
        <input type="text" placeholder="Search tokens, addresses..." />
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
