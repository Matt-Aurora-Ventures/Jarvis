import React, { useState, useEffect, useCallback } from 'react'

// Layout components
import { TopNav, Sidebar } from '@/components/layout'

// Trading components
import { StatsGrid, PositionCard, TokenScanner } from '@/components/trading'
import TradingChart from '@/components/TradingChart'
import OrderPanel from '@/components/OrderPanel'

// Chat
import { FloatingChat } from '@/components/chat'

// Hooks
import { useWallet, useSniper, usePosition } from '@/hooks'

// Constants
import { DEFAULT_TOKEN } from '@/lib/constants'

/**
 * Trading - Main Trading Dashboard
 * Refactored to use modular components and custom hooks
 */
function Trading() {
  // View state
  const [activeView, setActiveView] = useState('trading')
  const [selectedToken, setSelectedToken] = useState(DEFAULT_TOKEN)
  const [currentPrice, setCurrentPrice] = useState(0)

  // Data hooks with auto-refresh
  const { wallet, refresh: refreshWallet } = useWallet(true)
  const { sniper, refresh: refreshSniper } = useSniper(true)
  const { position, exit: exitPosition, refresh: refreshPosition } = usePosition(true)

  // Jarvis status (manual fetch for now)
  const [jarvisStatus, setJarvisStatus] = useState(null)

  const fetchJarvis = useCallback(async () => {
    try {
      const res = await fetch('/api/jarvis/status')
      if (res.ok) setJarvisStatus(await res.json())
    } catch (e) {
      console.error('Jarvis fetch error:', e)
    }
  }, [])

  useEffect(() => {
    fetchJarvis()
    const interval = setInterval(fetchJarvis, 30000)
    return () => clearInterval(interval)
  }, [fetchJarvis])

  // Handle token selection from scanner
  const handleTokenSelect = useCallback((token) => {
    setSelectedToken(token)
  }, [])

  // Handle price updates from chart
  const handlePriceUpdate = useCallback((price) => {
    setCurrentPrice(price)
  }, [])

  return (
    <div className="trading-dashboard">
      <TopNav walletData={wallet} />

      <div className="dashboard-container">
        <Sidebar 
          activeView={activeView} 
          onViewChange={setActiveView} 
        />

        <main className="main-content">
          {/* Page Header */}
          <header className="page-header">
            <h1 className="page-title">Trading Command Center</h1>
            <p className="page-subtitle">Real-time Solana trading with Jarvis AI</p>
          </header>

          {/* Stats Grid */}
          <StatsGrid walletData={wallet} sniperData={sniper} />

          {/* Chart + Order Panel Row */}
          <section className="grid-2-1" style={{ marginBottom: '24px' }}>
            <TradingChart
              mint={selectedToken.mint}
              symbol={selectedToken.symbol}
              onPriceUpdate={handlePriceUpdate}
            />
            <OrderPanel
              mint={selectedToken.mint}
              symbol={selectedToken.symbol}
              currentPrice={currentPrice}
              walletBalance={wallet?.balance_sol || 0}
            />
          </section>

          {/* Position + Tools Row */}
          <section className="grid-1-1" style={{ marginBottom: '24px' }}>
            <PositionCard
              position={position}
              onExit={exitPosition}
              onRefresh={refreshPosition}
            />
            <TokenScanner onTokenSelect={handleTokenSelect} />
          </section>
        </main>
      </div>

      {/* Floating Chat */}
      <FloatingChat jarvisStatus={jarvisStatus} />
    </div>
  )
}

export default Trading
