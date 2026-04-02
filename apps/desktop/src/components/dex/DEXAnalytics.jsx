import React, { useState, useEffect, useMemo } from 'react'
import {
  BarChart3, TrendingUp, TrendingDown, DollarSign, Activity,
  RefreshCw, Filter, Search, ExternalLink, Clock, Zap,
  Layers, PieChart, ArrowUpRight, ArrowDownRight, ArrowRight,
  ChevronDown, ChevronUp, Users, Droplet, Percent, Target
} from 'lucide-react'

// DEXes
const DEXES = [
  { id: 'uniswap', name: 'Uniswap', version: 'V3', color: '#FF007A', chains: ['ethereum', 'arbitrum', 'optimism', 'polygon', 'base'] },
  { id: 'sushiswap', name: 'SushiSwap', version: 'V2', color: '#FA52A0', chains: ['ethereum', 'arbitrum', 'polygon', 'bsc'] },
  { id: 'curve', name: 'Curve', version: '', color: '#0000FF', chains: ['ethereum', 'arbitrum', 'polygon'] },
  { id: 'balancer', name: 'Balancer', version: 'V2', color: '#1E1E1E', chains: ['ethereum', 'arbitrum', 'polygon'] },
  { id: 'pancakeswap', name: 'PancakeSwap', version: 'V3', color: '#1FC7D4', chains: ['bsc', 'ethereum', 'arbitrum'] },
  { id: 'gmx', name: 'GMX', version: '', color: '#4B68FF', chains: ['arbitrum', 'avalanche'] },
  { id: 'raydium', name: 'Raydium', version: '', color: '#C200FB', chains: ['solana'] },
  { id: 'orca', name: 'Orca', version: '', color: '#FFD15C', chains: ['solana'] },
  { id: 'aerodrome', name: 'Aerodrome', version: '', color: '#0052FF', chains: ['base'] },
  { id: 'camelot', name: 'Camelot', version: '', color: '#FFAF1D', chains: ['arbitrum'] }
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
  { id: 'solana', name: 'Solana', color: '#14F195' }
]

// Generate DEX stats
const generateDEXStats = () => {
  return DEXES.map(dex => {
    const volume24h = Math.random() * 2000000000 + 100000000
    const volume7d = volume24h * (5 + Math.random() * 4)
    const tvl = Math.random() * 5000000000 + 500000000
    const fees24h = volume24h * (0.0025 + Math.random() * 0.002)
    const trades24h = Math.floor(Math.random() * 500000 + 50000)
    const uniqueTraders = Math.floor(Math.random() * 50000 + 5000)

    return {
      ...dex,
      volume24h,
      volume7d,
      tvl,
      fees24h,
      trades24h,
      uniqueTraders,
      volumeChange: (Math.random() - 0.4) * 40,
      tvlChange: (Math.random() - 0.4) * 20,
      avgTradeSize: volume24h / trades24h,
      feeRate: fees24h / volume24h * 100
    }
  }).sort((a, b) => b.volume24h - a.volume24h)
}

// Generate top pairs
const generateTopPairs = () => {
  const pairs = [
    { base: 'ETH', quote: 'USDC' },
    { base: 'WBTC', quote: 'ETH' },
    { base: 'ETH', quote: 'USDT' },
    { base: 'ARB', quote: 'ETH' },
    { base: 'OP', quote: 'ETH' },
    { base: 'LINK', quote: 'ETH' },
    { base: 'UNI', quote: 'ETH' },
    { base: 'PEPE', quote: 'ETH' },
    { base: 'SOL', quote: 'USDC' },
    { base: 'WIF', quote: 'SOL' },
    { base: 'BONK', quote: 'SOL' },
    { base: 'JUP', quote: 'SOL' }
  ]

  return pairs.map((pair, i) => {
    const volume24h = Math.random() * 500000000 + 10000000
    const dex = DEXES[Math.floor(Math.random() * DEXES.length)]

    return {
      id: `pair-${i}`,
      ...pair,
      pairName: `${pair.base}/${pair.quote}`,
      dex,
      volume24h,
      tvl: Math.random() * 100000000 + 5000000,
      price: pair.base === 'ETH' ? 3200 + Math.random() * 100 :
             pair.base === 'WBTC' ? 95000 + Math.random() * 1000 :
             Math.random() * 10 + 0.1,
      priceChange24h: (Math.random() - 0.45) * 20,
      trades24h: Math.floor(Math.random() * 50000 + 1000),
      fee: 0.05 + Math.random() * 0.25
    }
  }).sort((a, b) => b.volume24h - a.volume24h)
}

// Generate recent swaps
const generateRecentSwaps = () => {
  const swaps = []
  const tokens = ['ETH', 'USDC', 'USDT', 'WBTC', 'ARB', 'OP', 'LINK', 'PEPE', 'SOL', 'WIF']

  for (let i = 0; i < 30; i++) {
    const fromToken = tokens[Math.floor(Math.random() * tokens.length)]
    let toToken = tokens[Math.floor(Math.random() * tokens.length)]
    while (toToken === fromToken) {
      toToken = tokens[Math.floor(Math.random() * tokens.length)]
    }
    const dex = DEXES[Math.floor(Math.random() * DEXES.length)]
    const amountUSD = Math.random() * 500000 + 100

    swaps.push({
      id: `swap-${i}`,
      fromToken,
      toToken,
      amountUSD,
      dex,
      timestamp: Date.now() - Math.random() * 3600000,
      txHash: `0x${Math.random().toString(16).substring(2, 18)}`,
      wallet: `0x${Math.random().toString(16).substring(2, 6)}...${Math.random().toString(16).substring(2, 6)}`,
      slippage: Math.random() * 2,
      isWhale: amountUSD > 100000
    })
  }

  return swaps.sort((a, b) => b.timestamp - a.timestamp)
}

export function DEXAnalytics() {
  const [dexStats, setDexStats] = useState([])
  const [topPairs, setTopPairs] = useState([])
  const [recentSwaps, setRecentSwaps] = useState([])
  const [selectedChain, setSelectedChain] = useState('all')
  const [selectedDex, setSelectedDex] = useState(null)
  const [viewMode, setViewMode] = useState('overview') // overview, pairs, swaps
  const [searchQuery, setSearchQuery] = useState('')
  const [sortBy, setSortBy] = useState('volume')

  // Initialize data
  useEffect(() => {
    setDexStats(generateDEXStats())
    setTopPairs(generateTopPairs())
    setRecentSwaps(generateRecentSwaps())

    // Simulate live updates
    const interval = setInterval(() => {
      setRecentSwaps(prev => {
        const tokens = ['ETH', 'USDC', 'ARB', 'SOL', 'PEPE']
        const fromToken = tokens[Math.floor(Math.random() * tokens.length)]
        let toToken = tokens[Math.floor(Math.random() * tokens.length)]
        while (toToken === fromToken) {
          toToken = tokens[Math.floor(Math.random() * tokens.length)]
        }
        const dex = DEXES[Math.floor(Math.random() * DEXES.length)]
        const amountUSD = Math.random() * 200000 + 500

        const newSwap = {
          id: `swap-${Date.now()}`,
          fromToken,
          toToken,
          amountUSD,
          dex,
          timestamp: Date.now(),
          txHash: `0x${Math.random().toString(16).substring(2, 18)}`,
          wallet: `0x${Math.random().toString(16).substring(2, 6)}...${Math.random().toString(16).substring(2, 6)}`,
          slippage: Math.random() * 1.5,
          isWhale: amountUSD > 100000,
          isNew: true
        }

        setTimeout(() => {
          setRecentSwaps(s => s.map(sw => sw.id === newSwap.id ? { ...sw, isNew: false } : sw))
        }, 3000)

        return [newSwap, ...prev.slice(0, 29)]
      })
    }, 4000)

    return () => clearInterval(interval)
  }, [])

  // Filter DEX stats by chain
  const filteredDexStats = useMemo(() => {
    if (selectedChain === 'all') return dexStats
    return dexStats.filter(d => d.chains.includes(selectedChain))
  }, [dexStats, selectedChain])

  // Filter pairs
  const filteredPairs = useMemo(() => {
    return topPairs.filter(p => {
      if (searchQuery) {
        const query = searchQuery.toLowerCase()
        return p.pairName.toLowerCase().includes(query) ||
               p.dex.name.toLowerCase().includes(query)
      }
      if (selectedDex) {
        return p.dex.id === selectedDex.id
      }
      return true
    })
  }, [topPairs, searchQuery, selectedDex])

  // Aggregate stats
  const aggregateStats = useMemo(() => {
    const stats = filteredDexStats
    return {
      totalVolume24h: stats.reduce((sum, d) => sum + d.volume24h, 0),
      totalTVL: stats.reduce((sum, d) => sum + d.tvl, 0),
      totalFees24h: stats.reduce((sum, d) => sum + d.fees24h, 0),
      totalTrades24h: stats.reduce((sum, d) => sum + d.trades24h, 0),
      totalTraders: stats.reduce((sum, d) => sum + d.uniqueTraders, 0)
    }
  }, [filteredDexStats])

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
    return `${Math.floor(diff / 3600000)}h ago`
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <BarChart3 className="w-6 h-6 text-purple-400" />
          <h2 className="text-xl font-bold text-white">DEX Analytics</h2>
          <span className="px-2 py-0.5 bg-purple-500/20 text-purple-400 text-xs rounded-full animate-pulse">
            LIVE
          </span>
        </div>

        <div className="flex items-center gap-2">
          <div className="flex bg-white/5 rounded-lg p-0.5">
            {['overview', 'pairs', 'swaps'].map(mode => (
              <button
                key={mode}
                onClick={() => setViewMode(mode)}
                className={`px-3 py-1.5 text-xs rounded-md transition-all capitalize ${
                  viewMode === mode
                    ? 'bg-purple-500 text-white'
                    : 'text-white/60 hover:text-white'
                }`}
              >
                {mode}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Aggregate Stats */}
      <div className="grid grid-cols-5 gap-4">
        <div className="bg-white/5 rounded-xl p-4 border border-white/10">
          <div className="flex items-center gap-2 text-white/60 text-sm mb-2">
            <DollarSign className="w-4 h-4" />
            <span>24h Volume</span>
          </div>
          <div className="text-2xl font-bold text-white">{formatNumber(aggregateStats.totalVolume24h)}</div>
        </div>

        <div className="bg-white/5 rounded-xl p-4 border border-white/10">
          <div className="flex items-center gap-2 text-white/60 text-sm mb-2">
            <Droplet className="w-4 h-4" />
            <span>Total TVL</span>
          </div>
          <div className="text-2xl font-bold text-blue-400">{formatNumber(aggregateStats.totalTVL)}</div>
        </div>

        <div className="bg-white/5 rounded-xl p-4 border border-white/10">
          <div className="flex items-center gap-2 text-white/60 text-sm mb-2">
            <Percent className="w-4 h-4" />
            <span>24h Fees</span>
          </div>
          <div className="text-2xl font-bold text-green-400">{formatNumber(aggregateStats.totalFees24h)}</div>
        </div>

        <div className="bg-white/5 rounded-xl p-4 border border-white/10">
          <div className="flex items-center gap-2 text-white/60 text-sm mb-2">
            <Activity className="w-4 h-4" />
            <span>24h Trades</span>
          </div>
          <div className="text-2xl font-bold text-white">{(aggregateStats.totalTrades24h / 1000000).toFixed(2)}M</div>
        </div>

        <div className="bg-white/5 rounded-xl p-4 border border-white/10">
          <div className="flex items-center gap-2 text-white/60 text-sm mb-2">
            <Users className="w-4 h-4" />
            <span>Unique Traders</span>
          </div>
          <div className="text-2xl font-bold text-purple-400">{(aggregateStats.totalTraders / 1000).toFixed(0)}K</div>
        </div>
      </div>

      {/* Chain Filter */}
      <div className="flex items-center gap-2">
        {CHAINS.map(chain => (
          <button
            key={chain.id}
            onClick={() => setSelectedChain(chain.id)}
            className={`px-3 py-1.5 text-xs rounded-lg transition-all flex items-center gap-1.5 ${
              selectedChain === chain.id
                ? 'bg-purple-500 text-white'
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

      {/* Overview View */}
      {viewMode === 'overview' && (
        <div className="space-y-2">
          {filteredDexStats.map((dex, index) => (
            <div
              key={dex.id}
              onClick={() => setSelectedDex(selectedDex?.id === dex.id ? null : dex)}
              className={`bg-white/5 rounded-xl p-4 border transition-all cursor-pointer hover:bg-white/10 ${
                selectedDex?.id === dex.id ? 'border-purple-500' : 'border-white/10'
              }`}
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-4">
                  <div className="text-white/40 text-sm w-6">#{index + 1}</div>
                  <div
                    className="w-10 h-10 rounded-lg flex items-center justify-center"
                    style={{ backgroundColor: `${dex.color}20` }}
                  >
                    <span className="text-xs font-bold" style={{ color: dex.color }}>
                      {dex.name.substring(0, 2).toUpperCase()}
                    </span>
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="text-white font-medium">{dex.name}</span>
                      {dex.version && (
                        <span className="px-1.5 py-0.5 bg-white/10 text-white/60 text-xs rounded">
                          {dex.version}
                        </span>
                      )}
                    </div>
                    <div className="flex items-center gap-2 mt-1">
                      {dex.chains.slice(0, 3).map(chain => {
                        const chainData = CHAINS.find(c => c.id === chain)
                        return chainData ? (
                          <div
                            key={chain}
                            className="w-4 h-4 rounded flex items-center justify-center"
                            style={{ backgroundColor: `${chainData.color}20` }}
                          >
                            <div
                              className="w-2 h-2 rounded-full"
                              style={{ backgroundColor: chainData.color }}
                            />
                          </div>
                        ) : null
                      })}
                      {dex.chains.length > 3 && (
                        <span className="text-white/40 text-xs">+{dex.chains.length - 3}</span>
                      )}
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-8">
                  {/* Volume */}
                  <div className="text-right">
                    <div className="text-white font-medium">{formatNumber(dex.volume24h)}</div>
                    <div className={`text-xs ${dex.volumeChange >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                      {dex.volumeChange >= 0 ? '+' : ''}{dex.volumeChange.toFixed(1)}%
                    </div>
                  </div>

                  {/* TVL */}
                  <div className="text-right w-24">
                    <div className="text-blue-400 font-medium">{formatNumber(dex.tvl)}</div>
                    <div className="text-white/40 text-xs">TVL</div>
                  </div>

                  {/* Fees */}
                  <div className="text-right w-24">
                    <div className="text-green-400 font-medium">{formatNumber(dex.fees24h)}</div>
                    <div className="text-white/40 text-xs">Fees 24h</div>
                  </div>

                  {/* Trades */}
                  <div className="text-right w-20">
                    <div className="text-white/80">{(dex.trades24h / 1000).toFixed(0)}K</div>
                    <div className="text-white/40 text-xs">Trades</div>
                  </div>

                  {/* Market share bar */}
                  <div className="w-32">
                    <div className="text-white/40 text-xs mb-1 text-right">
                      {((dex.volume24h / aggregateStats.totalVolume24h) * 100).toFixed(1)}%
                    </div>
                    <div className="h-2 bg-white/10 rounded-full overflow-hidden">
                      <div
                        className="h-full rounded-full transition-all"
                        style={{
                          width: `${(dex.volume24h / aggregateStats.totalVolume24h) * 100}%`,
                          backgroundColor: dex.color
                        }}
                      />
                    </div>
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Pairs View */}
      {viewMode === 'pairs' && (
        <div className="space-y-4">
          {/* Search */}
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-white/40" />
            <input
              type="text"
              placeholder="Search pairs or DEX..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-10 pr-4 py-2 bg-white/5 border border-white/10 rounded-lg text-white text-sm placeholder:text-white/40 focus:outline-none focus:border-purple-500"
            />
          </div>

          <div className="space-y-2">
            {filteredPairs.map((pair, index) => (
              <div
                key={pair.id}
                className="bg-white/5 rounded-xl p-4 border border-white/10 hover:border-white/30 transition-all"
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-4">
                    <div className="text-white/40 text-sm w-6">#{index + 1}</div>
                    <div className="flex items-center gap-2">
                      <div className="flex -space-x-2">
                        <div className="w-8 h-8 rounded-full bg-white/10 flex items-center justify-center text-xs font-bold text-white border-2 border-[#0a0e14]">
                          {pair.base.substring(0, 2)}
                        </div>
                        <div className="w-8 h-8 rounded-full bg-white/10 flex items-center justify-center text-xs font-bold text-white/60 border-2 border-[#0a0e14]">
                          {pair.quote.substring(0, 2)}
                        </div>
                      </div>
                      <div>
                        <span className="text-white font-medium">{pair.pairName}</span>
                        <div className="flex items-center gap-1 mt-0.5">
                          <div
                            className="w-3 h-3 rounded"
                            style={{ backgroundColor: `${pair.dex.color}40` }}
                          />
                          <span className="text-white/40 text-xs">{pair.dex.name}</span>
                        </div>
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center gap-6">
                    {/* Price */}
                    <div className="text-right">
                      <div className="text-white font-medium">${pair.price.toFixed(2)}</div>
                      <div className={`text-xs ${pair.priceChange24h >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                        {pair.priceChange24h >= 0 ? '+' : ''}{pair.priceChange24h.toFixed(2)}%
                      </div>
                    </div>

                    {/* Volume */}
                    <div className="text-right w-28">
                      <div className="text-white/80">{formatNumber(pair.volume24h)}</div>
                      <div className="text-white/40 text-xs">24h Volume</div>
                    </div>

                    {/* TVL */}
                    <div className="text-right w-24">
                      <div className="text-blue-400">{formatNumber(pair.tvl)}</div>
                      <div className="text-white/40 text-xs">TVL</div>
                    </div>

                    {/* Fee */}
                    <div className="text-right w-16">
                      <div className="text-green-400">{pair.fee.toFixed(2)}%</div>
                      <div className="text-white/40 text-xs">Fee</div>
                    </div>

                    <a href="#" className="text-white/40 hover:text-white">
                      <ExternalLink className="w-4 h-4" />
                    </a>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Swaps View */}
      {viewMode === 'swaps' && (
        <div className="space-y-2">
          {recentSwaps.map(swap => (
            <div
              key={swap.id}
              className={`bg-white/5 rounded-xl p-4 border transition-all ${
                swap.isNew ? 'border-purple-500 animate-pulse' : 'border-white/10'
              }`}
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-4">
                  {/* Swap direction */}
                  <div className="flex items-center gap-2">
                    <div className="w-8 h-8 rounded-lg bg-white/10 flex items-center justify-center text-xs font-bold text-white">
                      {swap.fromToken.substring(0, 2)}
                    </div>
                    <ArrowRight className="w-4 h-4 text-white/40" />
                    <div className="w-8 h-8 rounded-lg bg-white/10 flex items-center justify-center text-xs font-bold text-white">
                      {swap.toToken.substring(0, 2)}
                    </div>
                  </div>

                  <div>
                    <div className="flex items-center gap-2">
                      <span className="text-white font-medium">
                        {swap.fromToken} to {swap.toToken}
                      </span>
                      {swap.isWhale && (
                        <span className="px-1.5 py-0.5 bg-yellow-500/20 text-yellow-400 text-xs rounded">
                          WHALE
                        </span>
                      )}
                      {swap.isNew && (
                        <span className="px-1.5 py-0.5 bg-purple-500 text-white text-xs rounded animate-pulse">
                          NEW
                        </span>
                      )}
                    </div>
                    <div className="flex items-center gap-2 mt-0.5">
                      <span className="text-white/40 text-xs font-mono">{swap.wallet}</span>
                      <span className="text-white/20">|</span>
                      <span className="text-white/40 text-xs">via {swap.dex.name}</span>
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-6">
                  {/* Amount */}
                  <div className="text-right">
                    <div className="text-white font-medium">{formatNumber(swap.amountUSD)}</div>
                    <div className="text-white/40 text-xs">Value</div>
                  </div>

                  {/* Slippage */}
                  <div className="text-right w-20">
                    <div className={`${swap.slippage > 1 ? 'text-yellow-400' : 'text-white/60'}`}>
                      {swap.slippage.toFixed(2)}%
                    </div>
                    <div className="text-white/40 text-xs">Slippage</div>
                  </div>

                  {/* Time */}
                  <div className="text-white/40 text-sm w-20 text-right">
                    {formatTime(swap.timestamp)}
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
    </div>
  )
}

export default DEXAnalytics
