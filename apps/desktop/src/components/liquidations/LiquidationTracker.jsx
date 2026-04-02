import React, { useState, useEffect, useMemo } from 'react'
import {
  AlertTriangle, TrendingDown, DollarSign, Activity, Target,
  Clock, Search, Filter, ExternalLink, RefreshCw, Bell,
  ChevronDown, ArrowDown, Zap, Shield, Skull, BarChart3
} from 'lucide-react'

// Lending protocols
const PROTOCOLS = [
  { id: 'aave', name: 'Aave', version: 'V3', color: '#B6509E', chains: ['ethereum', 'arbitrum', 'optimism', 'polygon', 'base'] },
  { id: 'compound', name: 'Compound', version: 'V3', color: '#00D395', chains: ['ethereum', 'arbitrum', 'polygon', 'base'] },
  { id: 'maker', name: 'MakerDAO', version: '', color: '#1AAB9B', chains: ['ethereum'] },
  { id: 'morpho', name: 'Morpho', version: '', color: '#00A3FF', chains: ['ethereum', 'base'] },
  { id: 'spark', name: 'Spark', version: '', color: '#F7931A', chains: ['ethereum'] },
  { id: 'venus', name: 'Venus', version: '', color: '#F5B300', chains: ['bsc'] },
  { id: 'benqi', name: 'BENQI', version: '', color: '#00CFFF', chains: ['avalanche'] },
  { id: 'radiant', name: 'Radiant', version: 'V2', color: '#00D9FF', chains: ['arbitrum'] }
]

// Chains
const CHAINS = [
  { id: 'all', name: 'All Chains', color: '#FFFFFF' },
  { id: 'ethereum', name: 'Ethereum', color: '#627EEA' },
  { id: 'arbitrum', name: 'Arbitrum', color: '#28A0F0' },
  { id: 'optimism', name: 'Optimism', color: '#FF0420' },
  { id: 'polygon', name: 'Polygon', color: '#8247E5' },
  { id: 'base', name: 'Base', color: '#0052FF' },
  { id: 'bsc', name: 'BNB Chain', color: '#F0B90B' },
  { id: 'avalanche', name: 'Avalanche', color: '#E84142' }
]

// Assets
const ASSETS = ['ETH', 'WBTC', 'USDC', 'USDT', 'DAI', 'WSTETH', 'RETH', 'LINK', 'UNI', 'AAVE', 'ARB', 'OP', 'MATIC']

// Generate liquidation events
const generateLiquidations = () => {
  const liquidations = []

  for (let i = 0; i < 50; i++) {
    const protocol = PROTOCOLS[Math.floor(Math.random() * PROTOCOLS.length)]
    const chain = protocol.chains[Math.floor(Math.random() * protocol.chains.length)]
    const debtAsset = ASSETS[Math.floor(Math.random() * ASSETS.length)]
    const collateralAsset = ASSETS.filter(a => a !== debtAsset)[Math.floor(Math.random() * (ASSETS.length - 1))]
    const debtAmount = Math.random() * 1000000 + 1000
    const collateralAmount = debtAmount * (1.2 + Math.random() * 0.5)
    const liquidatorProfit = debtAmount * (0.05 + Math.random() * 0.1)
    const healthFactor = Math.random() * 0.3 + 0.7

    liquidations.push({
      id: `liq-${i}`,
      protocol,
      chain: CHAINS.find(c => c.id === chain),
      debtAsset,
      collateralAsset,
      debtAmount,
      collateralAmount,
      liquidatorProfit,
      healthFactor,
      timestamp: Date.now() - Math.random() * 86400000,
      txHash: `0x${Math.random().toString(16).substring(2, 18)}`,
      borrower: `0x${Math.random().toString(16).substring(2, 6)}...${Math.random().toString(16).substring(2, 6)}`,
      liquidator: `0x${Math.random().toString(16).substring(2, 6)}...${Math.random().toString(16).substring(2, 6)}`,
      isFlashLoan: Math.random() > 0.6,
      gasCost: Math.random() * 50 + 10
    })
  }

  return liquidations.sort((a, b) => b.timestamp - a.timestamp)
}

// Generate at-risk positions
const generateAtRiskPositions = () => {
  const positions = []

  for (let i = 0; i < 20; i++) {
    const protocol = PROTOCOLS[Math.floor(Math.random() * PROTOCOLS.length)]
    const chain = protocol.chains[Math.floor(Math.random() * protocol.chains.length)]
    const debtAsset = ASSETS[Math.floor(Math.random() * ASSETS.length)]
    const collateralAsset = ASSETS.filter(a => a !== debtAsset)[Math.floor(Math.random() * (ASSETS.length - 1))]
    const debt = Math.random() * 2000000 + 10000
    const collateral = debt * (1.1 + Math.random() * 0.3)
    const healthFactor = 1 + Math.random() * 0.15

    positions.push({
      id: `position-${i}`,
      protocol,
      chain: CHAINS.find(c => c.id === chain),
      borrower: `0x${Math.random().toString(16).substring(2, 6)}...${Math.random().toString(16).substring(2, 6)}`,
      debtAsset,
      collateralAsset,
      debt,
      collateral,
      healthFactor,
      liquidationPrice: Math.random() * 3000 + 1000,
      distanceToLiq: (healthFactor - 1) * 100,
      riskLevel: healthFactor < 1.05 ? 'CRITICAL' : healthFactor < 1.1 ? 'HIGH' : 'MEDIUM'
    })
  }

  return positions.sort((a, b) => a.healthFactor - b.healthFactor)
}

// Generate protocol stats
const generateProtocolStats = () => {
  return PROTOCOLS.map(protocol => ({
    ...protocol,
    totalLiquidations24h: Math.floor(Math.random() * 100 + 10),
    volumeLiquidated24h: Math.random() * 50000000 + 1000000,
    avgLiquidationSize: Math.random() * 200000 + 10000,
    atRiskPositions: Math.floor(Math.random() * 500 + 50),
    atRiskValue: Math.random() * 100000000 + 10000000
  }))
}

export function LiquidationTracker() {
  const [liquidations, setLiquidations] = useState([])
  const [atRiskPositions, setAtRiskPositions] = useState([])
  const [protocolStats, setProtocolStats] = useState([])
  const [selectedChain, setSelectedChain] = useState('all')
  const [selectedProtocol, setSelectedProtocol] = useState('all')
  const [viewMode, setViewMode] = useState('liquidations') // liquidations, at-risk, stats
  const [searchQuery, setSearchQuery] = useState('')

  // Initialize data
  useEffect(() => {
    setLiquidations(generateLiquidations())
    setAtRiskPositions(generateAtRiskPositions())
    setProtocolStats(generateProtocolStats())

    // Simulate live liquidations
    const interval = setInterval(() => {
      setLiquidations(prev => {
        const protocol = PROTOCOLS[Math.floor(Math.random() * PROTOCOLS.length)]
        const chain = protocol.chains[Math.floor(Math.random() * protocol.chains.length)]
        const debtAsset = ASSETS[Math.floor(Math.random() * ASSETS.length)]
        const collateralAsset = ASSETS.filter(a => a !== debtAsset)[Math.floor(Math.random() * (ASSETS.length - 1))]
        const debtAmount = Math.random() * 500000 + 5000

        const newLiq = {
          id: `liq-${Date.now()}`,
          protocol,
          chain: CHAINS.find(c => c.id === chain),
          debtAsset,
          collateralAsset,
          debtAmount,
          collateralAmount: debtAmount * (1.2 + Math.random() * 0.5),
          liquidatorProfit: debtAmount * (0.05 + Math.random() * 0.1),
          healthFactor: Math.random() * 0.3 + 0.7,
          timestamp: Date.now(),
          txHash: `0x${Math.random().toString(16).substring(2, 18)}`,
          borrower: `0x${Math.random().toString(16).substring(2, 6)}...${Math.random().toString(16).substring(2, 6)}`,
          liquidator: `0x${Math.random().toString(16).substring(2, 6)}...${Math.random().toString(16).substring(2, 6)}`,
          isFlashLoan: Math.random() > 0.6,
          gasCost: Math.random() * 50 + 10,
          isNew: true
        }

        setTimeout(() => {
          setLiquidations(l => l.map(liq => liq.id === newLiq.id ? { ...liq, isNew: false } : liq))
        }, 3000)

        return [newLiq, ...prev.slice(0, 49)]
      })
    }, 6000)

    return () => clearInterval(interval)
  }, [])

  // Filter liquidations
  const filteredLiquidations = useMemo(() => {
    return liquidations.filter(l => {
      if (selectedChain !== 'all' && l.chain.id !== selectedChain) return false
      if (selectedProtocol !== 'all' && l.protocol.id !== selectedProtocol) return false
      if (searchQuery) {
        const query = searchQuery.toLowerCase()
        return (
          l.debtAsset.toLowerCase().includes(query) ||
          l.collateralAsset.toLowerCase().includes(query) ||
          l.borrower.toLowerCase().includes(query) ||
          l.protocol.name.toLowerCase().includes(query)
        )
      }
      return true
    })
  }, [liquidations, selectedChain, selectedProtocol, searchQuery])

  // Filter at-risk positions
  const filteredAtRisk = useMemo(() => {
    return atRiskPositions.filter(p => {
      if (selectedChain !== 'all' && p.chain.id !== selectedChain) return false
      if (selectedProtocol !== 'all' && p.protocol.id !== selectedProtocol) return false
      return true
    })
  }, [atRiskPositions, selectedChain, selectedProtocol])

  // Aggregate stats
  const aggregateStats = useMemo(() => {
    const last24h = liquidations.filter(l => Date.now() - l.timestamp < 86400000)
    return {
      totalCount: last24h.length,
      totalVolume: last24h.reduce((sum, l) => sum + l.debtAmount, 0),
      totalProfit: last24h.reduce((sum, l) => sum + l.liquidatorProfit, 0),
      avgSize: last24h.reduce((sum, l) => sum + l.debtAmount, 0) / last24h.length || 0,
      atRiskCount: atRiskPositions.length,
      atRiskValue: atRiskPositions.reduce((sum, p) => sum + p.debt, 0)
    }
  }, [liquidations, atRiskPositions])

  const formatNumber = (num) => {
    if (num >= 1000000000) return `$${(num / 1000000000).toFixed(2)}B`
    if (num >= 1000000) return `$${(num / 1000000).toFixed(2)}M`
    if (num >= 1000) return `$${(num / 1000).toFixed(1)}K`
    return `$${num.toFixed(2)}`
  }

  const formatTime = (timestamp) => {
    const diff = Date.now() - timestamp
    if (diff < 60000) return 'Just now'
    if (diff < 3600000) return `${Math.floor(diff / 60000)}m ago`
    if (diff < 86400000) return `${Math.floor(diff / 3600000)}h ago`
    return `${Math.floor(diff / 86400000)}d ago`
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Skull className="w-6 h-6 text-red-400" />
          <h2 className="text-xl font-bold text-white">Liquidation Tracker</h2>
          <span className="px-2 py-0.5 bg-red-500/20 text-red-400 text-xs rounded-full animate-pulse">
            LIVE
          </span>
        </div>

        <div className="flex items-center gap-2">
          <div className="flex bg-white/5 rounded-lg p-0.5">
            {['liquidations', 'at-risk', 'stats'].map(mode => (
              <button
                key={mode}
                onClick={() => setViewMode(mode)}
                className={`px-3 py-1.5 text-xs rounded-md transition-all capitalize ${
                  viewMode === mode
                    ? 'bg-red-500 text-white'
                    : 'text-white/60 hover:text-white'
                }`}
              >
                {mode === 'at-risk' ? 'At Risk' : mode}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-6 gap-4">
        <div className="bg-white/5 rounded-xl p-4 border border-white/10">
          <div className="flex items-center gap-2 text-white/60 text-sm mb-2">
            <Activity className="w-4 h-4" />
            <span>24h Liquidations</span>
          </div>
          <div className="text-2xl font-bold text-white">{aggregateStats.totalCount}</div>
        </div>

        <div className="bg-white/5 rounded-xl p-4 border border-white/10">
          <div className="flex items-center gap-2 text-white/60 text-sm mb-2">
            <DollarSign className="w-4 h-4" />
            <span>24h Volume</span>
          </div>
          <div className="text-2xl font-bold text-red-400">{formatNumber(aggregateStats.totalVolume)}</div>
        </div>

        <div className="bg-white/5 rounded-xl p-4 border border-white/10">
          <div className="flex items-center gap-2 text-white/60 text-sm mb-2">
            <Zap className="w-4 h-4" />
            <span>Liquidator Profit</span>
          </div>
          <div className="text-2xl font-bold text-green-400">{formatNumber(aggregateStats.totalProfit)}</div>
        </div>

        <div className="bg-white/5 rounded-xl p-4 border border-white/10">
          <div className="flex items-center gap-2 text-white/60 text-sm mb-2">
            <Target className="w-4 h-4" />
            <span>Avg Size</span>
          </div>
          <div className="text-2xl font-bold text-white">{formatNumber(aggregateStats.avgSize)}</div>
        </div>

        <div className="bg-white/5 rounded-xl p-4 border border-white/10">
          <div className="flex items-center gap-2 text-white/60 text-sm mb-2">
            <AlertTriangle className="w-4 h-4" />
            <span>At Risk</span>
          </div>
          <div className="text-2xl font-bold text-yellow-400">{aggregateStats.atRiskCount}</div>
        </div>

        <div className="bg-white/5 rounded-xl p-4 border border-white/10">
          <div className="flex items-center gap-2 text-white/60 text-sm mb-2">
            <Shield className="w-4 h-4" />
            <span>At Risk Value</span>
          </div>
          <div className="text-2xl font-bold text-orange-400">{formatNumber(aggregateStats.atRiskValue)}</div>
        </div>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-4">
        {viewMode !== 'stats' && (
          <div className="flex-1 relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-white/40" />
            <input
              type="text"
              placeholder="Search by asset, protocol, or address..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-10 pr-4 py-2 bg-white/5 border border-white/10 rounded-lg text-white text-sm placeholder:text-white/40 focus:outline-none focus:border-red-500"
            />
          </div>
        )}

        {/* Chain filter */}
        <div className="flex items-center gap-2">
          {CHAINS.slice(0, 5).map(chain => (
            <button
              key={chain.id}
              onClick={() => setSelectedChain(chain.id)}
              className={`px-3 py-1.5 text-xs rounded-lg transition-all flex items-center gap-1.5 ${
                selectedChain === chain.id
                  ? 'bg-red-500 text-white'
                  : 'bg-white/5 text-white/60 hover:text-white'
              }`}
            >
              {chain.id !== 'all' && (
                <div className="w-2 h-2 rounded-full" style={{ backgroundColor: chain.color }} />
              )}
              {chain.name}
            </button>
          ))}
        </div>

        {/* Protocol filter */}
        <select
          value={selectedProtocol}
          onChange={(e) => setSelectedProtocol(e.target.value)}
          className="px-3 py-1.5 bg-white/5 border border-white/10 rounded-lg text-white text-sm focus:outline-none"
        >
          <option value="all">All Protocols</option>
          {PROTOCOLS.map(p => (
            <option key={p.id} value={p.id}>{p.name}</option>
          ))}
        </select>
      </div>

      {/* Liquidations View */}
      {viewMode === 'liquidations' && (
        <div className="space-y-2">
          {filteredLiquidations.map(liq => (
            <div
              key={liq.id}
              className={`bg-white/5 rounded-xl p-4 border transition-all ${
                liq.isNew ? 'border-red-500 animate-pulse' : 'border-white/10'
              }`}
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-4">
                  {/* Protocol */}
                  <div
                    className="w-10 h-10 rounded-lg flex items-center justify-center"
                    style={{ backgroundColor: `${liq.protocol.color}20` }}
                  >
                    <span className="text-xs font-bold" style={{ color: liq.protocol.color }}>
                      {liq.protocol.name.substring(0, 2).toUpperCase()}
                    </span>
                  </div>

                  <div>
                    <div className="flex items-center gap-2">
                      <span className="text-white font-medium">{liq.protocol.name}</span>
                      <div
                        className="w-4 h-4 rounded flex items-center justify-center"
                        style={{ backgroundColor: `${liq.chain.color}20` }}
                      >
                        <div
                          className="w-2 h-2 rounded-full"
                          style={{ backgroundColor: liq.chain.color }}
                        />
                      </div>
                      {liq.isNew && (
                        <span className="px-1.5 py-0.5 bg-red-500 text-white text-xs rounded animate-pulse">
                          NEW
                        </span>
                      )}
                      {liq.isFlashLoan && (
                        <span className="px-1.5 py-0.5 bg-purple-500/20 text-purple-400 text-xs rounded">
                          Flash Loan
                        </span>
                      )}
                    </div>
                    <div className="flex items-center gap-2 mt-1 text-xs text-white/40">
                      <span>Borrower: {liq.borrower}</span>
                      <span>|</span>
                      <span>HF: {liq.healthFactor.toFixed(2)}</span>
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-6">
                  {/* Assets */}
                  <div className="text-center">
                    <div className="flex items-center gap-2">
                      <span className="text-red-400 font-medium">{liq.debtAsset}</span>
                      <ArrowDown className="w-3 h-3 text-white/40" />
                      <span className="text-green-400 font-medium">{liq.collateralAsset}</span>
                    </div>
                    <div className="text-white/40 text-xs">Debt / Collateral</div>
                  </div>

                  {/* Debt */}
                  <div className="text-right w-28">
                    <div className="text-red-400 font-medium">{formatNumber(liq.debtAmount)}</div>
                    <div className="text-white/40 text-xs">Debt Repaid</div>
                  </div>

                  {/* Collateral */}
                  <div className="text-right w-28">
                    <div className="text-white/80">{formatNumber(liq.collateralAmount)}</div>
                    <div className="text-white/40 text-xs">Collateral Seized</div>
                  </div>

                  {/* Profit */}
                  <div className="text-right w-24">
                    <div className="text-green-400 font-medium">{formatNumber(liq.liquidatorProfit)}</div>
                    <div className="text-white/40 text-xs">Profit</div>
                  </div>

                  {/* Time */}
                  <div className="text-white/40 text-sm w-20 text-right">
                    {formatTime(liq.timestamp)}
                  </div>

                  <a href="#" className="text-white/40 hover:text-white">
                    <ExternalLink className="w-4 h-4" />
                  </a>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* At Risk View */}
      {viewMode === 'at-risk' && (
        <div className="space-y-2">
          {filteredAtRisk.map(position => (
            <div
              key={position.id}
              className={`bg-white/5 rounded-xl p-4 border ${
                position.riskLevel === 'CRITICAL' ? 'border-red-500/50' :
                position.riskLevel === 'HIGH' ? 'border-orange-500/50' : 'border-yellow-500/50'
              }`}
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-4">
                  {/* Risk indicator */}
                  <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${
                    position.riskLevel === 'CRITICAL' ? 'bg-red-500/20' :
                    position.riskLevel === 'HIGH' ? 'bg-orange-500/20' : 'bg-yellow-500/20'
                  }`}>
                    <AlertTriangle className={`w-5 h-5 ${
                      position.riskLevel === 'CRITICAL' ? 'text-red-400' :
                      position.riskLevel === 'HIGH' ? 'text-orange-400' : 'text-yellow-400'
                    }`} />
                  </div>

                  <div>
                    <div className="flex items-center gap-2">
                      <span className={`px-2 py-0.5 text-xs rounded font-medium ${
                        position.riskLevel === 'CRITICAL' ? 'bg-red-500/20 text-red-400' :
                        position.riskLevel === 'HIGH' ? 'bg-orange-500/20 text-orange-400' : 'bg-yellow-500/20 text-yellow-400'
                      }`}>
                        {position.riskLevel}
                      </span>
                      <span className="text-white font-medium">{position.protocol.name}</span>
                      <div
                        className="w-4 h-4 rounded flex items-center justify-center"
                        style={{ backgroundColor: `${position.chain.color}20` }}
                      >
                        <div
                          className="w-2 h-2 rounded-full"
                          style={{ backgroundColor: position.chain.color }}
                        />
                      </div>
                    </div>
                    <div className="text-white/40 text-xs mt-1">
                      Borrower: {position.borrower}
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-6">
                  {/* Assets */}
                  <div className="text-center">
                    <div className="flex items-center gap-2">
                      <span className="text-red-400">{position.debtAsset}</span>
                      <span className="text-white/40">/</span>
                      <span className="text-green-400">{position.collateralAsset}</span>
                    </div>
                    <div className="text-white/40 text-xs">Position</div>
                  </div>

                  {/* Debt */}
                  <div className="text-right w-28">
                    <div className="text-red-400 font-medium">{formatNumber(position.debt)}</div>
                    <div className="text-white/40 text-xs">Debt</div>
                  </div>

                  {/* Collateral */}
                  <div className="text-right w-28">
                    <div className="text-green-400">{formatNumber(position.collateral)}</div>
                    <div className="text-white/40 text-xs">Collateral</div>
                  </div>

                  {/* Health Factor */}
                  <div className="text-right w-24">
                    <div className={`font-medium ${
                      position.healthFactor < 1.05 ? 'text-red-400' :
                      position.healthFactor < 1.1 ? 'text-orange-400' : 'text-yellow-400'
                    }`}>
                      {position.healthFactor.toFixed(3)}
                    </div>
                    <div className="text-white/40 text-xs">Health Factor</div>
                  </div>

                  {/* Distance to liquidation */}
                  <div className="text-right w-24">
                    <div className="text-white/80">{position.distanceToLiq.toFixed(1)}%</div>
                    <div className="text-white/40 text-xs">To Liq.</div>
                  </div>

                  <button className="p-2 bg-white/5 hover:bg-white/10 rounded-lg transition-all">
                    <Bell className="w-4 h-4 text-white/40" />
                  </button>
                </div>
              </div>

              {/* Health factor bar */}
              <div className="mt-3 pt-3 border-t border-white/10">
                <div className="flex items-center gap-4">
                  <span className="text-white/40 text-xs w-20">Liquidation</span>
                  <div className="flex-1 h-2 bg-white/10 rounded-full overflow-hidden relative">
                    <div
                      className={`h-full rounded-full ${
                        position.healthFactor < 1.05 ? 'bg-red-500' :
                        position.healthFactor < 1.1 ? 'bg-orange-500' : 'bg-yellow-500'
                      }`}
                      style={{ width: `${Math.min((position.healthFactor - 1) * 500, 100)}%` }}
                    />
                    <div className="absolute left-0 top-0 bottom-0 w-0.5 bg-red-500" />
                  </div>
                  <span className="text-white/40 text-xs w-12">Safe</span>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Stats View */}
      {viewMode === 'stats' && (
        <div className="grid grid-cols-2 gap-4">
          {protocolStats.map(protocol => (
            <div
              key={protocol.id}
              className="bg-white/5 rounded-xl p-4 border border-white/10"
            >
              <div className="flex items-center gap-3 mb-4">
                <div
                  className="w-10 h-10 rounded-lg flex items-center justify-center"
                  style={{ backgroundColor: `${protocol.color}20` }}
                >
                  <span className="text-xs font-bold" style={{ color: protocol.color }}>
                    {protocol.name.substring(0, 2).toUpperCase()}
                  </span>
                </div>
                <div>
                  <div className="text-white font-medium">{protocol.name}</div>
                  <div className="text-white/40 text-xs">
                    {protocol.chains.length} chains supported
                  </div>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <div className="text-white/40 text-xs mb-1">24h Liquidations</div>
                  <div className="text-white font-medium">{protocol.totalLiquidations24h}</div>
                </div>
                <div>
                  <div className="text-white/40 text-xs mb-1">24h Volume</div>
                  <div className="text-red-400 font-medium">{formatNumber(protocol.volumeLiquidated24h)}</div>
                </div>
                <div>
                  <div className="text-white/40 text-xs mb-1">Avg Size</div>
                  <div className="text-white/80">{formatNumber(protocol.avgLiquidationSize)}</div>
                </div>
                <div>
                  <div className="text-white/40 text-xs mb-1">At Risk</div>
                  <div className="text-yellow-400 font-medium">{protocol.atRiskPositions}</div>
                </div>
              </div>

              <div className="mt-3 pt-3 border-t border-white/10">
                <div className="text-white/40 text-xs mb-1">At Risk Value</div>
                <div className="text-orange-400 font-medium">{formatNumber(protocol.atRiskValue)}</div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

export default LiquidationTracker
