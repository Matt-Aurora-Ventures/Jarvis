import React, { useState, useEffect, useMemo } from 'react'
import {
  Landmark, TrendingUp, TrendingDown, DollarSign, Percent,
  Shield, AlertTriangle, RefreshCw, Search, Filter, ExternalLink,
  ChevronDown, ArrowUpRight, ArrowDownRight, Zap, Target,
  PieChart, Activity, Clock, Lock, Unlock
} from 'lucide-react'

// Lending protocols
const PROTOCOLS = [
  { id: 'aave', name: 'Aave', version: 'V3', color: '#B6509E', chains: ['ethereum', 'arbitrum', 'optimism', 'polygon', 'base', 'avalanche'] },
  { id: 'compound', name: 'Compound', version: 'V3', color: '#00D395', chains: ['ethereum', 'arbitrum', 'polygon', 'base'] },
  { id: 'morpho', name: 'Morpho', version: 'Blue', color: '#00A3FF', chains: ['ethereum', 'base'] },
  { id: 'spark', name: 'Spark', version: '', color: '#F7931A', chains: ['ethereum'] },
  { id: 'radiant', name: 'Radiant', version: 'V2', color: '#00D9FF', chains: ['arbitrum'] },
  { id: 'benqi', name: 'BENQI', version: '', color: '#00CFFF', chains: ['avalanche'] },
  { id: 'venus', name: 'Venus', version: '', color: '#F5B300', chains: ['bsc'] },
  { id: 'kamino', name: 'Kamino', version: '', color: '#00FF88', chains: ['solana'] }
]

// Chains
const CHAINS = [
  { id: 'all', name: 'All Chains', color: '#FFFFFF' },
  { id: 'ethereum', name: 'Ethereum', color: '#627EEA' },
  { id: 'arbitrum', name: 'Arbitrum', color: '#28A0F0' },
  { id: 'polygon', name: 'Polygon', color: '#8247E5' },
  { id: 'base', name: 'Base', color: '#0052FF' },
  { id: 'avalanche', name: 'Avalanche', color: '#E84142' },
  { id: 'solana', name: 'Solana', color: '#14F195' }
]

// Assets
const ASSETS = ['ETH', 'WBTC', 'USDC', 'USDT', 'DAI', 'WSTETH', 'RETH', 'CBETH', 'LINK', 'UNI', 'AAVE', 'ARB', 'OP', 'SOL']

// Generate market data
const generateMarkets = () => {
  const markets = []

  PROTOCOLS.forEach(protocol => {
    protocol.chains.forEach(chainId => {
      ASSETS.slice(0, 8).forEach(asset => {
        const supplyAPY = Math.random() * 8 + 0.5
        const borrowAPY = Math.random() * 12 + 2
        const utilization = Math.random() * 40 + 40
        const totalSupply = Math.random() * 500000000 + 10000000
        const totalBorrow = totalSupply * (utilization / 100)

        markets.push({
          id: `${protocol.id}-${chainId}-${asset}`,
          protocol,
          chain: CHAINS.find(c => c.id === chainId),
          asset,
          supplyAPY,
          borrowAPY,
          utilization,
          totalSupply,
          totalBorrow,
          availableLiquidity: totalSupply - totalBorrow,
          ltv: 0.6 + Math.random() * 0.2,
          liquidationThreshold: 0.75 + Math.random() * 0.1,
          liquidationPenalty: 0.05 + Math.random() * 0.05,
          supplyRewardAPY: Math.random() > 0.6 ? Math.random() * 3 : 0,
          borrowRewardAPY: Math.random() > 0.7 ? Math.random() * 2 : 0
        })
      })
    })
  })

  return markets
}

// Generate protocol stats
const generateProtocolStats = () => {
  return PROTOCOLS.map(protocol => ({
    ...protocol,
    tvl: Math.random() * 10000000000 + 500000000,
    totalSupply: Math.random() * 15000000000 + 1000000000,
    totalBorrow: Math.random() * 8000000000 + 500000000,
    uniqueUsers: Math.floor(Math.random() * 100000 + 10000),
    avgSupplyAPY: Math.random() * 5 + 1,
    avgBorrowAPY: Math.random() * 8 + 3,
    revenue24h: Math.random() * 500000 + 50000
  }))
}

// Generate user positions
const generatePositions = () => {
  const positions = []

  for (let i = 0; i < 5; i++) {
    const protocol = PROTOCOLS[Math.floor(Math.random() * PROTOCOLS.length)]
    const chain = CHAINS[Math.floor(Math.random() * (CHAINS.length - 1)) + 1]
    const supplyAsset = ASSETS[Math.floor(Math.random() * ASSETS.length)]
    const borrowAsset = ASSETS.filter(a => a !== supplyAsset)[Math.floor(Math.random() * (ASSETS.length - 1))]

    const supplied = Math.random() * 100000 + 1000
    const borrowed = supplied * (0.3 + Math.random() * 0.4)
    const healthFactor = 1.2 + Math.random() * 1.5

    positions.push({
      id: `position-${i}`,
      protocol,
      chain,
      supplied: {
        asset: supplyAsset,
        amount: supplied,
        apy: Math.random() * 5 + 1
      },
      borrowed: {
        asset: borrowAsset,
        amount: borrowed,
        apy: Math.random() * 10 + 3
      },
      healthFactor,
      netAPY: (Math.random() - 0.3) * 8,
      liquidationPrice: Math.random() * 2000 + 1000,
      rewards: Math.random() * 100 + 10
    })
  }

  return positions
}

export function LendingDashboard() {
  const [markets, setMarkets] = useState([])
  const [protocolStats, setProtocolStats] = useState([])
  const [positions, setPositions] = useState([])
  const [selectedChain, setSelectedChain] = useState('all')
  const [selectedProtocol, setSelectedProtocol] = useState('all')
  const [selectedAsset, setSelectedAsset] = useState('all')
  const [viewMode, setViewMode] = useState('rates') // rates, protocols, positions
  const [searchQuery, setSearchQuery] = useState('')
  const [sortBy, setSortBy] = useState('supplyAPY') // supplyAPY, borrowAPY, tvl

  // Initialize data
  useEffect(() => {
    setMarkets(generateMarkets())
    setProtocolStats(generateProtocolStats())
    setPositions(generatePositions())
  }, [])

  // Filter markets
  const filteredMarkets = useMemo(() => {
    const uniqueByAsset = new Map()

    markets
      .filter(m => {
        if (selectedChain !== 'all' && m.chain.id !== selectedChain) return false
        if (selectedProtocol !== 'all' && m.protocol.id !== selectedProtocol) return false
        if (selectedAsset !== 'all' && m.asset !== selectedAsset) return false
        if (searchQuery) {
          const query = searchQuery.toLowerCase()
          return m.asset.toLowerCase().includes(query) ||
                 m.protocol.name.toLowerCase().includes(query)
        }
        return true
      })
      .forEach(m => {
        const key = `${m.asset}-${m.protocol.id}-${m.chain.id}`
        if (!uniqueByAsset.has(key)) {
          uniqueByAsset.set(key, m)
        }
      })

    return Array.from(uniqueByAsset.values()).sort((a, b) => {
      switch (sortBy) {
        case 'supplyAPY': return b.supplyAPY - a.supplyAPY
        case 'borrowAPY': return a.borrowAPY - b.borrowAPY
        case 'tvl': return b.totalSupply - a.totalSupply
        default: return 0
      }
    })
  }, [markets, selectedChain, selectedProtocol, selectedAsset, searchQuery, sortBy])

  // Filter protocol stats
  const filteredProtocols = useMemo(() => {
    if (selectedChain === 'all') return protocolStats
    return protocolStats.filter(p => p.chains.includes(selectedChain))
  }, [protocolStats, selectedChain])

  // Aggregate stats
  const aggregateStats = useMemo(() => {
    const totalTVL = protocolStats.reduce((sum, p) => sum + p.tvl, 0)
    const totalSupply = protocolStats.reduce((sum, p) => sum + p.totalSupply, 0)
    const totalBorrow = protocolStats.reduce((sum, p) => sum + p.totalBorrow, 0)
    const avgSupplyAPY = protocolStats.reduce((sum, p) => sum + p.avgSupplyAPY, 0) / protocolStats.length
    const avgBorrowAPY = protocolStats.reduce((sum, p) => sum + p.avgBorrowAPY, 0) / protocolStats.length

    return { totalTVL, totalSupply, totalBorrow, avgSupplyAPY, avgBorrowAPY }
  }, [protocolStats])

  // Position stats
  const positionStats = useMemo(() => {
    const totalSupplied = positions.reduce((sum, p) => sum + p.supplied.amount, 0)
    const totalBorrowed = positions.reduce((sum, p) => sum + p.borrowed.amount, 0)
    const avgHealthFactor = positions.reduce((sum, p) => sum + p.healthFactor, 0) / positions.length
    const totalRewards = positions.reduce((sum, p) => sum + p.rewards, 0)

    return { totalSupplied, totalBorrowed, avgHealthFactor, totalRewards }
  }, [positions])

  const formatNumber = (num) => {
    if (num >= 1000000000) return `$${(num / 1000000000).toFixed(2)}B`
    if (num >= 1000000) return `$${(num / 1000000).toFixed(2)}M`
    if (num >= 1000) return `$${(num / 1000).toFixed(1)}K`
    return `$${num.toFixed(2)}`
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Landmark className="w-6 h-6 text-blue-400" />
          <h2 className="text-xl font-bold text-white">Lending Dashboard</h2>
          <span className="px-2 py-0.5 bg-blue-500/20 text-blue-400 text-xs rounded-full">
            {PROTOCOLS.length} Protocols
          </span>
        </div>

        <div className="flex items-center gap-2">
          <div className="flex bg-white/5 rounded-lg p-0.5">
            {['rates', 'protocols', 'positions'].map(mode => (
              <button
                key={mode}
                onClick={() => setViewMode(mode)}
                className={`px-3 py-1.5 text-xs rounded-md transition-all capitalize ${
                  viewMode === mode
                    ? 'bg-blue-500 text-white'
                    : 'text-white/60 hover:text-white'
                }`}
              >
                {mode}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-5 gap-4">
        <div className="bg-white/5 rounded-xl p-4 border border-white/10">
          <div className="flex items-center gap-2 text-white/60 text-sm mb-2">
            <DollarSign className="w-4 h-4" />
            <span>Total TVL</span>
          </div>
          <div className="text-2xl font-bold text-white">{formatNumber(aggregateStats.totalTVL)}</div>
        </div>

        <div className="bg-white/5 rounded-xl p-4 border border-white/10">
          <div className="flex items-center gap-2 text-white/60 text-sm mb-2">
            <Lock className="w-4 h-4" />
            <span>Total Supply</span>
          </div>
          <div className="text-2xl font-bold text-green-400">{formatNumber(aggregateStats.totalSupply)}</div>
        </div>

        <div className="bg-white/5 rounded-xl p-4 border border-white/10">
          <div className="flex items-center gap-2 text-white/60 text-sm mb-2">
            <Unlock className="w-4 h-4" />
            <span>Total Borrow</span>
          </div>
          <div className="text-2xl font-bold text-red-400">{formatNumber(aggregateStats.totalBorrow)}</div>
        </div>

        <div className="bg-white/5 rounded-xl p-4 border border-white/10">
          <div className="flex items-center gap-2 text-white/60 text-sm mb-2">
            <TrendingUp className="w-4 h-4" />
            <span>Avg Supply APY</span>
          </div>
          <div className="text-2xl font-bold text-cyan-400">{aggregateStats.avgSupplyAPY.toFixed(2)}%</div>
        </div>

        <div className="bg-white/5 rounded-xl p-4 border border-white/10">
          <div className="flex items-center gap-2 text-white/60 text-sm mb-2">
            <TrendingDown className="w-4 h-4" />
            <span>Avg Borrow APY</span>
          </div>
          <div className="text-2xl font-bold text-orange-400">{aggregateStats.avgBorrowAPY.toFixed(2)}%</div>
        </div>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-4">
        {viewMode !== 'positions' && (
          <div className="flex-1 relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-white/40" />
            <input
              type="text"
              placeholder="Search by asset or protocol..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-10 pr-4 py-2 bg-white/5 border border-white/10 rounded-lg text-white text-sm placeholder:text-white/40 focus:outline-none focus:border-blue-500"
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
                  ? 'bg-blue-500 text-white'
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

        {viewMode === 'rates' && (
          <>
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

            {/* Sort */}
            <select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value)}
              className="px-3 py-1.5 bg-white/5 border border-white/10 rounded-lg text-white text-sm focus:outline-none"
            >
              <option value="supplyAPY">Highest Supply APY</option>
              <option value="borrowAPY">Lowest Borrow APY</option>
              <option value="tvl">Highest TVL</option>
            </select>
          </>
        )}
      </div>

      {/* Rates View */}
      {viewMode === 'rates' && (
        <div className="space-y-2">
          {filteredMarkets.slice(0, 20).map(market => (
            <div
              key={market.id}
              className="bg-white/5 rounded-xl p-4 border border-white/10 hover:border-white/30 transition-all"
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-4">
                  {/* Asset */}
                  <div className="w-10 h-10 rounded-lg bg-white/10 flex items-center justify-center text-sm font-bold text-white">
                    {market.asset.substring(0, 2)}
                  </div>

                  <div>
                    <div className="flex items-center gap-2">
                      <span className="text-white font-medium">{market.asset}</span>
                      <div
                        className="w-4 h-4 rounded flex items-center justify-center"
                        style={{ backgroundColor: `${market.chain.color}20` }}
                      >
                        <div
                          className="w-2 h-2 rounded-full"
                          style={{ backgroundColor: market.chain.color }}
                        />
                      </div>
                    </div>
                    <div className="flex items-center gap-2 mt-0.5">
                      <span
                        className="text-xs"
                        style={{ color: market.protocol.color }}
                      >
                        {market.protocol.name}
                      </span>
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-8">
                  {/* Supply APY */}
                  <div className="text-center w-28">
                    <div className="text-green-400 font-medium text-lg">
                      {market.supplyAPY.toFixed(2)}%
                      {market.supplyRewardAPY > 0 && (
                        <span className="text-purple-400 text-xs ml-1">
                          +{market.supplyRewardAPY.toFixed(1)}%
                        </span>
                      )}
                    </div>
                    <div className="text-white/40 text-xs">Supply APY</div>
                  </div>

                  {/* Borrow APY */}
                  <div className="text-center w-28">
                    <div className="text-red-400 font-medium text-lg">
                      {market.borrowAPY.toFixed(2)}%
                      {market.borrowRewardAPY > 0 && (
                        <span className="text-purple-400 text-xs ml-1">
                          -{market.borrowRewardAPY.toFixed(1)}%
                        </span>
                      )}
                    </div>
                    <div className="text-white/40 text-xs">Borrow APY</div>
                  </div>

                  {/* Utilization */}
                  <div className="w-32">
                    <div className="flex justify-between text-xs mb-1">
                      <span className="text-white/40">Utilization</span>
                      <span className="text-white/60">{market.utilization.toFixed(1)}%</span>
                    </div>
                    <div className="h-1.5 bg-white/10 rounded-full overflow-hidden">
                      <div
                        className={`h-full rounded-full ${
                          market.utilization > 80 ? 'bg-red-500' :
                          market.utilization > 60 ? 'bg-yellow-500' : 'bg-green-500'
                        }`}
                        style={{ width: `${market.utilization}%` }}
                      />
                    </div>
                  </div>

                  {/* TVL */}
                  <div className="text-right w-28">
                    <div className="text-white">{formatNumber(market.totalSupply)}</div>
                    <div className="text-white/40 text-xs">Total Supply</div>
                  </div>

                  {/* LTV */}
                  <div className="text-center w-16">
                    <div className="text-white/80">{(market.ltv * 100).toFixed(0)}%</div>
                    <div className="text-white/40 text-xs">LTV</div>
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

      {/* Protocols View */}
      {viewMode === 'protocols' && (
        <div className="grid grid-cols-2 gap-4">
          {filteredProtocols.map(protocol => (
            <div
              key={protocol.id}
              className="bg-white/5 rounded-xl p-4 border border-white/10"
            >
              <div className="flex items-center gap-3 mb-4">
                <div
                  className="w-12 h-12 rounded-xl flex items-center justify-center"
                  style={{ backgroundColor: `${protocol.color}20` }}
                >
                  <span className="text-sm font-bold" style={{ color: protocol.color }}>
                    {protocol.name.substring(0, 2).toUpperCase()}
                  </span>
                </div>
                <div>
                  <div className="text-white font-medium">{protocol.name} {protocol.version}</div>
                  <div className="flex items-center gap-1 mt-1">
                    {protocol.chains.slice(0, 4).map(chainId => {
                      const chain = CHAINS.find(c => c.id === chainId)
                      return chain ? (
                        <div
                          key={chainId}
                          className="w-4 h-4 rounded flex items-center justify-center"
                          style={{ backgroundColor: `${chain.color}20` }}
                        >
                          <div
                            className="w-2 h-2 rounded-full"
                            style={{ backgroundColor: chain.color }}
                          />
                        </div>
                      ) : null
                    })}
                    {protocol.chains.length > 4 && (
                      <span className="text-white/40 text-xs">+{protocol.chains.length - 4}</span>
                    )}
                  </div>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <div className="text-white/40 text-xs mb-1">TVL</div>
                  <div className="text-white font-medium">{formatNumber(protocol.tvl)}</div>
                </div>
                <div>
                  <div className="text-white/40 text-xs mb-1">Users</div>
                  <div className="text-white font-medium">{(protocol.uniqueUsers / 1000).toFixed(1)}K</div>
                </div>
                <div>
                  <div className="text-white/40 text-xs mb-1">Avg Supply APY</div>
                  <div className="text-green-400 font-medium">{protocol.avgSupplyAPY.toFixed(2)}%</div>
                </div>
                <div>
                  <div className="text-white/40 text-xs mb-1">Avg Borrow APY</div>
                  <div className="text-red-400 font-medium">{protocol.avgBorrowAPY.toFixed(2)}%</div>
                </div>
              </div>

              <div className="mt-4 pt-4 border-t border-white/10 grid grid-cols-2 gap-4">
                <div>
                  <div className="text-white/40 text-xs mb-1">Total Supply</div>
                  <div className="text-green-400">{formatNumber(protocol.totalSupply)}</div>
                </div>
                <div>
                  <div className="text-white/40 text-xs mb-1">Total Borrow</div>
                  <div className="text-red-400">{formatNumber(protocol.totalBorrow)}</div>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Positions View */}
      {viewMode === 'positions' && (
        <div className="space-y-4">
          {/* Position Stats */}
          <div className="grid grid-cols-4 gap-4">
            <div className="bg-white/5 rounded-xl p-4 border border-white/10">
              <div className="text-white/40 text-sm mb-1">Total Supplied</div>
              <div className="text-xl font-bold text-green-400">{formatNumber(positionStats.totalSupplied)}</div>
            </div>
            <div className="bg-white/5 rounded-xl p-4 border border-white/10">
              <div className="text-white/40 text-sm mb-1">Total Borrowed</div>
              <div className="text-xl font-bold text-red-400">{formatNumber(positionStats.totalBorrowed)}</div>
            </div>
            <div className="bg-white/5 rounded-xl p-4 border border-white/10">
              <div className="text-white/40 text-sm mb-1">Avg Health Factor</div>
              <div className={`text-xl font-bold ${
                positionStats.avgHealthFactor < 1.5 ? 'text-yellow-400' : 'text-green-400'
              }`}>
                {positionStats.avgHealthFactor.toFixed(2)}
              </div>
            </div>
            <div className="bg-white/5 rounded-xl p-4 border border-white/10">
              <div className="text-white/40 text-sm mb-1">Pending Rewards</div>
              <div className="text-xl font-bold text-purple-400">{formatNumber(positionStats.totalRewards)}</div>
            </div>
          </div>

          {/* Position List */}
          {positions.map(position => (
            <div
              key={position.id}
              className={`bg-white/5 rounded-xl p-4 border ${
                position.healthFactor < 1.5 ? 'border-yellow-500/50' : 'border-white/10'
              }`}
            >
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-3">
                  <div
                    className="w-10 h-10 rounded-lg flex items-center justify-center"
                    style={{ backgroundColor: `${position.protocol.color}20` }}
                  >
                    <span className="text-xs font-bold" style={{ color: position.protocol.color }}>
                      {position.protocol.name.substring(0, 2).toUpperCase()}
                    </span>
                  </div>
                  <div>
                    <div className="text-white font-medium">{position.protocol.name}</div>
                    <div className="flex items-center gap-1 mt-0.5">
                      <div
                        className="w-3 h-3 rounded"
                        style={{ backgroundColor: position.chain.color }}
                      />
                      <span className="text-white/40 text-xs">{position.chain.name}</span>
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  {position.healthFactor < 1.5 && (
                    <span className="px-2 py-1 bg-yellow-500/20 text-yellow-400 text-xs rounded flex items-center gap-1">
                      <AlertTriangle className="w-3 h-3" />
                      Low Health
                    </span>
                  )}
                </div>
              </div>

              <div className="grid grid-cols-5 gap-4">
                {/* Supplied */}
                <div className="bg-green-500/10 rounded-lg p-3">
                  <div className="text-green-400 text-xs mb-1">Supplied</div>
                  <div className="text-white font-medium">{formatNumber(position.supplied.amount)}</div>
                  <div className="flex items-center gap-2 mt-1">
                    <span className="text-white/60 text-sm">{position.supplied.asset}</span>
                    <span className="text-green-400 text-xs">+{position.supplied.apy.toFixed(2)}%</span>
                  </div>
                </div>

                {/* Borrowed */}
                <div className="bg-red-500/10 rounded-lg p-3">
                  <div className="text-red-400 text-xs mb-1">Borrowed</div>
                  <div className="text-white font-medium">{formatNumber(position.borrowed.amount)}</div>
                  <div className="flex items-center gap-2 mt-1">
                    <span className="text-white/60 text-sm">{position.borrowed.asset}</span>
                    <span className="text-red-400 text-xs">-{position.borrowed.apy.toFixed(2)}%</span>
                  </div>
                </div>

                {/* Net APY */}
                <div className="bg-white/5 rounded-lg p-3">
                  <div className="text-white/40 text-xs mb-1">Net APY</div>
                  <div className={`font-medium text-lg ${
                    position.netAPY >= 0 ? 'text-green-400' : 'text-red-400'
                  }`}>
                    {position.netAPY >= 0 ? '+' : ''}{position.netAPY.toFixed(2)}%
                  </div>
                </div>

                {/* Health Factor */}
                <div className="bg-white/5 rounded-lg p-3">
                  <div className="text-white/40 text-xs mb-1">Health Factor</div>
                  <div className={`font-medium text-lg ${
                    position.healthFactor < 1.3 ? 'text-red-400' :
                    position.healthFactor < 1.5 ? 'text-yellow-400' : 'text-green-400'
                  }`}>
                    {position.healthFactor.toFixed(2)}
                  </div>
                </div>

                {/* Rewards */}
                <div className="bg-purple-500/10 rounded-lg p-3">
                  <div className="text-purple-400 text-xs mb-1">Rewards</div>
                  <div className="text-white font-medium">{formatNumber(position.rewards)}</div>
                  <button className="mt-1 text-purple-400 text-xs hover:text-purple-300">
                    Claim
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

export default LendingDashboard
