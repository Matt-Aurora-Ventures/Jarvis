import React, { useState, useEffect, useMemo, useCallback } from 'react'
import {
  ArrowRight, RefreshCw, Clock, DollarSign, Shield, Zap,
  AlertTriangle, CheckCircle, XCircle, ExternalLink, Search,
  ChevronDown, ChevronUp, Filter, Settings, Star, TrendingUp,
  Activity, Layers, GitBranch, Wallet, Copy, Check, Info
} from 'lucide-react'

// Supported chains
const CHAINS = [
  { id: 'ethereum', name: 'Ethereum', symbol: 'ETH', color: '#627EEA', nativeToken: 'ETH' },
  { id: 'arbitrum', name: 'Arbitrum', symbol: 'ARB', color: '#28A0F0', nativeToken: 'ETH' },
  { id: 'optimism', name: 'Optimism', symbol: 'OP', color: '#FF0420', nativeToken: 'ETH' },
  { id: 'polygon', name: 'Polygon', symbol: 'MATIC', color: '#8247E5', nativeToken: 'MATIC' },
  { id: 'base', name: 'Base', symbol: 'BASE', color: '#0052FF', nativeToken: 'ETH' },
  { id: 'bsc', name: 'BNB Chain', symbol: 'BNB', color: '#F0B90B', nativeToken: 'BNB' },
  { id: 'avalanche', name: 'Avalanche', symbol: 'AVAX', color: '#E84142', nativeToken: 'AVAX' },
  { id: 'solana', name: 'Solana', symbol: 'SOL', color: '#14F195', nativeToken: 'SOL' },
  { id: 'zksync', name: 'zkSync Era', symbol: 'ZK', color: '#8C8DFC', nativeToken: 'ETH' },
  { id: 'linea', name: 'Linea', symbol: 'LINEA', color: '#61DFFF', nativeToken: 'ETH' }
]

// Bridge providers
const BRIDGES = [
  {
    id: 'stargate',
    name: 'Stargate',
    logo: '/bridges/stargate.png',
    type: 'liquidity',
    securityScore: 92,
    avgTime: '2-10 min',
    supportedChains: ['ethereum', 'arbitrum', 'optimism', 'polygon', 'base', 'bsc', 'avalanche'],
    features: ['Fast', 'Low fees', 'LayerZero'],
    auditedBy: ['Quantstamp', 'Zellic']
  },
  {
    id: 'across',
    name: 'Across',
    logo: '/bridges/across.png',
    type: 'intent',
    securityScore: 95,
    avgTime: '1-5 min',
    supportedChains: ['ethereum', 'arbitrum', 'optimism', 'polygon', 'base', 'linea', 'zksync'],
    features: ['Fastest', 'UMA oracle', 'Intent-based'],
    auditedBy: ['OpenZeppelin', 'Consensys']
  },
  {
    id: 'hop',
    name: 'Hop Protocol',
    logo: '/bridges/hop.png',
    type: 'liquidity',
    securityScore: 88,
    avgTime: '5-20 min',
    supportedChains: ['ethereum', 'arbitrum', 'optimism', 'polygon', 'base'],
    features: ['Established', 'Bonder network'],
    auditedBy: ['Consensys Diligence']
  },
  {
    id: 'synapse',
    name: 'Synapse',
    logo: '/bridges/synapse.png',
    type: 'liquidity',
    securityScore: 85,
    avgTime: '5-15 min',
    supportedChains: ['ethereum', 'arbitrum', 'optimism', 'polygon', 'bsc', 'avalanche'],
    features: ['Multi-chain', 'Native bridge'],
    auditedBy: ['Quantstamp']
  },
  {
    id: 'cbridge',
    name: 'cBridge',
    logo: '/bridges/celer.png',
    type: 'liquidity',
    securityScore: 87,
    avgTime: '5-20 min',
    supportedChains: ['ethereum', 'arbitrum', 'optimism', 'polygon', 'bsc', 'avalanche'],
    features: ['Celer network', 'SGN'],
    auditedBy: ['CertiK', 'SlowMist']
  },
  {
    id: 'wormhole',
    name: 'Wormhole',
    logo: '/bridges/wormhole.png',
    type: 'messaging',
    securityScore: 80,
    avgTime: '15-30 min',
    supportedChains: ['ethereum', 'solana', 'polygon', 'bsc', 'avalanche', 'arbitrum'],
    features: ['Solana native', 'Wide support'],
    auditedBy: ['Neodyme', 'Kudelski']
  },
  {
    id: 'debridge',
    name: 'deBridge',
    logo: '/bridges/debridge.png',
    type: 'intent',
    securityScore: 90,
    avgTime: '1-5 min',
    supportedChains: ['ethereum', 'arbitrum', 'optimism', 'polygon', 'bsc', 'solana'],
    features: ['DLN', 'Fast settlement'],
    auditedBy: ['Halborn', 'Ackee']
  },
  {
    id: 'lifi',
    name: 'LI.FI',
    logo: '/bridges/lifi.png',
    type: 'aggregator',
    securityScore: 91,
    avgTime: 'Varies',
    supportedChains: ['ethereum', 'arbitrum', 'optimism', 'polygon', 'base', 'bsc', 'avalanche', 'zksync'],
    features: ['Aggregator', 'Best route', 'SDK'],
    auditedBy: ['Ackee', 'Consensys']
  }
]

// Tokens
const TOKENS = [
  { symbol: 'ETH', name: 'Ethereum', chains: ['ethereum', 'arbitrum', 'optimism', 'base', 'zksync', 'linea'] },
  { symbol: 'USDC', name: 'USD Coin', chains: ['ethereum', 'arbitrum', 'optimism', 'polygon', 'base', 'bsc', 'avalanche', 'solana'] },
  { symbol: 'USDT', name: 'Tether', chains: ['ethereum', 'arbitrum', 'optimism', 'polygon', 'bsc', 'avalanche', 'solana'] },
  { symbol: 'DAI', name: 'Dai', chains: ['ethereum', 'arbitrum', 'optimism', 'polygon', 'base'] },
  { symbol: 'WBTC', name: 'Wrapped BTC', chains: ['ethereum', 'arbitrum', 'optimism', 'polygon'] },
  { symbol: 'MATIC', name: 'Polygon', chains: ['ethereum', 'polygon'] },
  { symbol: 'ARB', name: 'Arbitrum', chains: ['ethereum', 'arbitrum'] },
  { symbol: 'OP', name: 'Optimism', chains: ['ethereum', 'optimism'] }
]

// Generate route quotes
const generateQuotes = (fromChain, toChain, token, amount) => {
  const validBridges = BRIDGES.filter(b =>
    b.supportedChains.includes(fromChain) && b.supportedChains.includes(toChain)
  )

  return validBridges.map(bridge => {
    const feePercent = 0.05 + Math.random() * 0.3
    const fee = amount * feePercent / 100
    const gasCost = Math.random() * 20 + 5
    const timeMin = parseInt(bridge.avgTime.split('-')[0]) || 1
    const timeMax = parseInt(bridge.avgTime.split('-')[1]) || timeMin * 2
    const estimatedTime = Math.floor(timeMin + Math.random() * (timeMax - timeMin))

    return {
      bridge,
      amountIn: amount,
      amountOut: amount - fee,
      fee,
      feePercent,
      gasCost,
      totalCost: fee + gasCost,
      estimatedTime,
      rate: (amount - fee) / amount,
      recommended: Math.random() > 0.7
    }
  }).sort((a, b) => b.amountOut - a.amountOut)
}

// Recent bridges mock data
const generateRecentBridges = () => {
  const bridges = []
  for (let i = 0; i < 10; i++) {
    const fromChain = CHAINS[Math.floor(Math.random() * CHAINS.length)]
    let toChain = CHAINS[Math.floor(Math.random() * CHAINS.length)]
    while (toChain.id === fromChain.id) {
      toChain = CHAINS[Math.floor(Math.random() * CHAINS.length)]
    }
    const token = TOKENS[Math.floor(Math.random() * TOKENS.length)]
    const bridge = BRIDGES[Math.floor(Math.random() * BRIDGES.length)]
    const amount = Math.random() * 50000 + 100
    const status = Math.random() > 0.1 ? 'completed' : Math.random() > 0.5 ? 'pending' : 'failed'

    bridges.push({
      id: `bridge-${i}`,
      fromChain,
      toChain,
      token: token.symbol,
      bridge: bridge.name,
      amount,
      status,
      timestamp: Date.now() - Math.random() * 86400000 * 7,
      txHash: `0x${Math.random().toString(16).substring(2, 18)}`,
      fee: amount * (0.1 + Math.random() * 0.2) / 100
    })
  }
  return bridges.sort((a, b) => b.timestamp - a.timestamp)
}

export function BridgeAggregator() {
  // Bridge form state
  const [fromChain, setFromChain] = useState(CHAINS[0])
  const [toChain, setToChain] = useState(CHAINS[1])
  const [selectedToken, setSelectedToken] = useState(TOKENS[1]) // USDC
  const [amount, setAmount] = useState('')
  const [quotes, setQuotes] = useState([])
  const [selectedQuote, setSelectedQuote] = useState(null)
  const [isLoading, setIsLoading] = useState(false)

  // UI state
  const [viewMode, setViewMode] = useState('bridge') // bridge, history, compare
  const [recentBridges, setRecentBridges] = useState([])
  const [showFromChains, setShowFromChains] = useState(false)
  const [showToChains, setShowToChains] = useState(false)
  const [showTokens, setShowTokens] = useState(false)
  const [sortBy, setSortBy] = useState('output') // output, speed, security

  // Initialize
  useEffect(() => {
    setRecentBridges(generateRecentBridges())
  }, [])

  // Get quotes when params change
  useEffect(() => {
    if (amount && parseFloat(amount) > 0) {
      setIsLoading(true)
      // Simulate API call
      setTimeout(() => {
        const newQuotes = generateQuotes(fromChain.id, toChain.id, selectedToken.symbol, parseFloat(amount))
        setQuotes(newQuotes)
        setSelectedQuote(newQuotes[0] || null)
        setIsLoading(false)
      }, 800)
    } else {
      setQuotes([])
      setSelectedQuote(null)
    }
  }, [fromChain, toChain, selectedToken, amount])

  // Swap chains
  const swapChains = useCallback(() => {
    const temp = fromChain
    setFromChain(toChain)
    setToChain(temp)
  }, [fromChain, toChain])

  // Sort quotes
  const sortedQuotes = useMemo(() => {
    return [...quotes].sort((a, b) => {
      switch (sortBy) {
        case 'output': return b.amountOut - a.amountOut
        case 'speed': return a.estimatedTime - b.estimatedTime
        case 'security': return b.bridge.securityScore - a.bridge.securityScore
        default: return 0
      }
    })
  }, [quotes, sortBy])

  const formatNumber = (num) => {
    if (num >= 1000000) return `${(num / 1000000).toFixed(2)}M`
    if (num >= 1000) return `${(num / 1000).toFixed(2)}K`
    return num.toFixed(2)
  }

  const formatTime = (timestamp) => {
    const diff = Date.now() - timestamp
    if (diff < 3600000) return `${Math.floor(diff / 60000)}m ago`
    if (diff < 86400000) return `${Math.floor(diff / 3600000)}h ago`
    return `${Math.floor(diff / 86400000)}d ago`
  }

  // Available tokens for selected chains
  const availableTokens = useMemo(() => {
    return TOKENS.filter(t =>
      t.chains.includes(fromChain.id) && t.chains.includes(toChain.id)
    )
  }, [fromChain, toChain])

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <GitBranch className="w-6 h-6 text-blue-400" />
          <h2 className="text-xl font-bold text-white">Bridge Aggregator</h2>
          <span className="px-2 py-0.5 bg-blue-500/20 text-blue-400 text-xs rounded-full">
            {BRIDGES.length} Bridges
          </span>
        </div>

        <div className="flex items-center gap-2">
          <div className="flex bg-white/5 rounded-lg p-0.5">
            {['bridge', 'history', 'compare'].map(mode => (
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

      {/* Bridge View */}
      {viewMode === 'bridge' && (
        <div className="grid grid-cols-2 gap-6">
          {/* Bridge Form */}
          <div className="bg-white/5 rounded-xl p-6 border border-white/10">
            <h3 className="text-white font-medium mb-4">Bridge Assets</h3>

            {/* From Chain */}
            <div className="mb-4">
              <label className="text-white/60 text-sm mb-2 block">From</label>
              <div className="relative">
                <button
                  onClick={() => setShowFromChains(!showFromChains)}
                  className="w-full flex items-center justify-between p-3 bg-white/5 border border-white/10 rounded-lg hover:border-blue-500/50 transition-all"
                >
                  <div className="flex items-center gap-3">
                    <div
                      className="w-8 h-8 rounded-lg flex items-center justify-center"
                      style={{ backgroundColor: `${fromChain.color}20` }}
                    >
                      <span className="text-xs font-bold" style={{ color: fromChain.color }}>
                        {fromChain.symbol}
                      </span>
                    </div>
                    <span className="text-white">{fromChain.name}</span>
                  </div>
                  <ChevronDown className="w-4 h-4 text-white/40" />
                </button>

                {showFromChains && (
                  <div className="absolute top-full left-0 right-0 mt-2 bg-[#0a0e14] border border-white/10 rounded-lg p-2 z-20 max-h-60 overflow-y-auto">
                    {CHAINS.filter(c => c.id !== toChain.id).map(chain => (
                      <button
                        key={chain.id}
                        onClick={() => {
                          setFromChain(chain)
                          setShowFromChains(false)
                        }}
                        className="w-full flex items-center gap-3 p-2 hover:bg-white/10 rounded-lg transition-all"
                      >
                        <div
                          className="w-6 h-6 rounded flex items-center justify-center"
                          style={{ backgroundColor: `${chain.color}20` }}
                        >
                          <span className="text-[10px] font-bold" style={{ color: chain.color }}>
                            {chain.symbol}
                          </span>
                        </div>
                        <span className="text-white text-sm">{chain.name}</span>
                      </button>
                    ))}
                  </div>
                )}
              </div>
            </div>

            {/* Swap Button */}
            <div className="flex justify-center my-2">
              <button
                onClick={swapChains}
                className="p-2 bg-white/5 hover:bg-white/10 rounded-lg transition-all"
              >
                <RefreshCw className="w-4 h-4 text-white/60" />
              </button>
            </div>

            {/* To Chain */}
            <div className="mb-4">
              <label className="text-white/60 text-sm mb-2 block">To</label>
              <div className="relative">
                <button
                  onClick={() => setShowToChains(!showToChains)}
                  className="w-full flex items-center justify-between p-3 bg-white/5 border border-white/10 rounded-lg hover:border-blue-500/50 transition-all"
                >
                  <div className="flex items-center gap-3">
                    <div
                      className="w-8 h-8 rounded-lg flex items-center justify-center"
                      style={{ backgroundColor: `${toChain.color}20` }}
                    >
                      <span className="text-xs font-bold" style={{ color: toChain.color }}>
                        {toChain.symbol}
                      </span>
                    </div>
                    <span className="text-white">{toChain.name}</span>
                  </div>
                  <ChevronDown className="w-4 h-4 text-white/40" />
                </button>

                {showToChains && (
                  <div className="absolute top-full left-0 right-0 mt-2 bg-[#0a0e14] border border-white/10 rounded-lg p-2 z-20 max-h-60 overflow-y-auto">
                    {CHAINS.filter(c => c.id !== fromChain.id).map(chain => (
                      <button
                        key={chain.id}
                        onClick={() => {
                          setToChain(chain)
                          setShowToChains(false)
                        }}
                        className="w-full flex items-center gap-3 p-2 hover:bg-white/10 rounded-lg transition-all"
                      >
                        <div
                          className="w-6 h-6 rounded flex items-center justify-center"
                          style={{ backgroundColor: `${chain.color}20` }}
                        >
                          <span className="text-[10px] font-bold" style={{ color: chain.color }}>
                            {chain.symbol}
                          </span>
                        </div>
                        <span className="text-white text-sm">{chain.name}</span>
                      </button>
                    ))}
                  </div>
                )}
              </div>
            </div>

            {/* Token & Amount */}
            <div className="mb-4">
              <label className="text-white/60 text-sm mb-2 block">Token & Amount</label>
              <div className="flex gap-2">
                <div className="relative">
                  <button
                    onClick={() => setShowTokens(!showTokens)}
                    className="flex items-center gap-2 px-4 py-3 bg-white/5 border border-white/10 rounded-lg hover:border-blue-500/50 transition-all"
                  >
                    <span className="text-white font-medium">{selectedToken.symbol}</span>
                    <ChevronDown className="w-4 h-4 text-white/40" />
                  </button>

                  {showTokens && (
                    <div className="absolute top-full left-0 mt-2 bg-[#0a0e14] border border-white/10 rounded-lg p-2 z-20 min-w-[150px]">
                      {availableTokens.map(token => (
                        <button
                          key={token.symbol}
                          onClick={() => {
                            setSelectedToken(token)
                            setShowTokens(false)
                          }}
                          className="w-full flex items-center gap-2 p-2 hover:bg-white/10 rounded-lg transition-all"
                        >
                          <span className="text-white text-sm">{token.symbol}</span>
                          <span className="text-white/40 text-xs">{token.name}</span>
                        </button>
                      ))}
                    </div>
                  )}
                </div>

                <input
                  type="number"
                  placeholder="0.00"
                  value={amount}
                  onChange={(e) => setAmount(e.target.value)}
                  className="flex-1 px-4 py-3 bg-white/5 border border-white/10 rounded-lg text-white text-right focus:outline-none focus:border-blue-500"
                />
              </div>
            </div>

            {/* Selected Quote Summary */}
            {selectedQuote && (
              <div className="p-4 bg-blue-500/10 border border-blue-500/30 rounded-lg mb-4">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-blue-400 text-sm">Best Route via {selectedQuote.bridge.name}</span>
                  <span className="text-white font-medium">
                    {formatNumber(selectedQuote.amountOut)} {selectedToken.symbol}
                  </span>
                </div>
                <div className="flex items-center gap-4 text-xs text-white/60">
                  <span>Fee: ${selectedQuote.totalCost.toFixed(2)}</span>
                  <span>Time: ~{selectedQuote.estimatedTime} min</span>
                  <span>Security: {selectedQuote.bridge.securityScore}/100</span>
                </div>
              </div>
            )}

            {/* Bridge Button */}
            <button
              disabled={!selectedQuote || isLoading}
              className={`w-full py-3 rounded-lg font-medium transition-all ${
                selectedQuote && !isLoading
                  ? 'bg-blue-500 hover:bg-blue-600 text-white'
                  : 'bg-white/10 text-white/40 cursor-not-allowed'
              }`}
            >
              {isLoading ? 'Finding Routes...' : selectedQuote ? 'Bridge Assets' : 'Enter Amount'}
            </button>
          </div>

          {/* Quotes List */}
          <div className="bg-white/5 rounded-xl p-6 border border-white/10">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-white font-medium">Available Routes</h3>
              <select
                value={sortBy}
                onChange={(e) => setSortBy(e.target.value)}
                className="px-3 py-1 bg-white/5 border border-white/10 rounded-lg text-white text-sm focus:outline-none"
              >
                <option value="output">Best Output</option>
                <option value="speed">Fastest</option>
                <option value="security">Most Secure</option>
              </select>
            </div>

            {isLoading ? (
              <div className="flex items-center justify-center py-12">
                <RefreshCw className="w-6 h-6 text-blue-400 animate-spin" />
              </div>
            ) : sortedQuotes.length > 0 ? (
              <div className="space-y-2">
                {sortedQuotes.map((quote, index) => (
                  <button
                    key={quote.bridge.id}
                    onClick={() => setSelectedQuote(quote)}
                    className={`w-full p-4 rounded-lg border transition-all text-left ${
                      selectedQuote?.bridge.id === quote.bridge.id
                        ? 'bg-blue-500/20 border-blue-500'
                        : 'bg-white/5 border-white/10 hover:border-white/30'
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-lg bg-white/10 flex items-center justify-center">
                          <GitBranch className="w-5 h-5 text-white/60" />
                        </div>
                        <div>
                          <div className="flex items-center gap-2">
                            <span className="text-white font-medium">{quote.bridge.name}</span>
                            {index === 0 && (
                              <span className="px-1.5 py-0.5 bg-green-500/20 text-green-400 text-xs rounded">
                                BEST
                              </span>
                            )}
                            {quote.recommended && index !== 0 && (
                              <Star className="w-3.5 h-3.5 text-yellow-400" />
                            )}
                          </div>
                          <div className="flex items-center gap-2 mt-1">
                            {quote.bridge.features.slice(0, 2).map(f => (
                              <span key={f} className="text-xs text-white/40">{f}</span>
                            ))}
                          </div>
                        </div>
                      </div>

                      <div className="text-right">
                        <div className="text-white font-medium">
                          {formatNumber(quote.amountOut)} {selectedToken.symbol}
                        </div>
                        <div className="flex items-center gap-3 mt-1 text-xs text-white/40">
                          <span className="flex items-center gap-1">
                            <Clock className="w-3 h-3" />
                            ~{quote.estimatedTime}m
                          </span>
                          <span className="flex items-center gap-1">
                            <Shield className="w-3 h-3" />
                            {quote.bridge.securityScore}
                          </span>
                        </div>
                      </div>
                    </div>

                    {/* Fee breakdown */}
                    <div className="mt-3 pt-3 border-t border-white/10 flex items-center justify-between text-xs">
                      <span className="text-white/40">
                        Fee: {quote.feePercent.toFixed(3)}% (${quote.fee.toFixed(2)})
                      </span>
                      <span className="text-white/40">
                        Gas: ~${quote.gasCost.toFixed(2)}
                      </span>
                      <span className="text-white/60">
                        Total: ${quote.totalCost.toFixed(2)}
                      </span>
                    </div>
                  </button>
                ))}
              </div>
            ) : amount ? (
              <div className="text-center py-12 text-white/40">
                No routes available for this pair
              </div>
            ) : (
              <div className="text-center py-12 text-white/40">
                Enter an amount to see available routes
              </div>
            )}
          </div>
        </div>
      )}

      {/* History View */}
      {viewMode === 'history' && (
        <div className="bg-white/5 rounded-xl border border-white/10">
          <div className="p-4 border-b border-white/10">
            <h3 className="text-white font-medium">Recent Bridges</h3>
          </div>
          <div className="divide-y divide-white/10">
            {recentBridges.map(bridge => (
              <div key={bridge.id} className="p-4 flex items-center justify-between">
                <div className="flex items-center gap-4">
                  {/* Status */}
                  <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${
                    bridge.status === 'completed'
                      ? 'bg-green-500/20'
                      : bridge.status === 'pending'
                        ? 'bg-yellow-500/20'
                        : 'bg-red-500/20'
                  }`}>
                    {bridge.status === 'completed' ? (
                      <CheckCircle className="w-5 h-5 text-green-400" />
                    ) : bridge.status === 'pending' ? (
                      <Clock className="w-5 h-5 text-yellow-400" />
                    ) : (
                      <XCircle className="w-5 h-5 text-red-400" />
                    )}
                  </div>

                  {/* Route */}
                  <div>
                    <div className="flex items-center gap-2">
                      <div className="flex items-center gap-1">
                        <div
                          className="w-5 h-5 rounded flex items-center justify-center"
                          style={{ backgroundColor: `${bridge.fromChain.color}20` }}
                        >
                          <span className="text-[8px] font-bold" style={{ color: bridge.fromChain.color }}>
                            {bridge.fromChain.symbol}
                          </span>
                        </div>
                        <span className="text-white/60 text-sm">{bridge.fromChain.name}</span>
                      </div>
                      <ArrowRight className="w-4 h-4 text-white/40" />
                      <div className="flex items-center gap-1">
                        <div
                          className="w-5 h-5 rounded flex items-center justify-center"
                          style={{ backgroundColor: `${bridge.toChain.color}20` }}
                        >
                          <span className="text-[8px] font-bold" style={{ color: bridge.toChain.color }}>
                            {bridge.toChain.symbol}
                          </span>
                        </div>
                        <span className="text-white/60 text-sm">{bridge.toChain.name}</span>
                      </div>
                    </div>
                    <div className="text-white/40 text-xs mt-1">via {bridge.bridge}</div>
                  </div>
                </div>

                <div className="flex items-center gap-6">
                  <div className="text-right">
                    <div className="text-white font-medium">
                      {formatNumber(bridge.amount)} {bridge.token}
                    </div>
                    <div className="text-white/40 text-xs">
                      Fee: ${bridge.fee.toFixed(2)}
                    </div>
                  </div>

                  <div className="text-white/40 text-sm w-20 text-right">
                    {formatTime(bridge.timestamp)}
                  </div>

                  <a href="#" className="text-white/40 hover:text-white">
                    <ExternalLink className="w-4 h-4" />
                  </a>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Compare View */}
      {viewMode === 'compare' && (
        <div className="space-y-4">
          <div className="grid grid-cols-4 gap-4">
            {BRIDGES.map(bridge => (
              <div
                key={bridge.id}
                className="bg-white/5 rounded-xl p-4 border border-white/10 hover:border-blue-500/50 transition-all"
              >
                <div className="flex items-center gap-3 mb-4">
                  <div className="w-12 h-12 rounded-xl bg-white/10 flex items-center justify-center">
                    <GitBranch className="w-6 h-6 text-white/60" />
                  </div>
                  <div>
                    <div className="text-white font-medium">{bridge.name}</div>
                    <div className="text-white/40 text-xs capitalize">{bridge.type}</div>
                  </div>
                </div>

                {/* Security score */}
                <div className="mb-3">
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-white/40 text-xs">Security</span>
                    <span className={`text-sm font-medium ${
                      bridge.securityScore >= 90 ? 'text-green-400' :
                      bridge.securityScore >= 80 ? 'text-yellow-400' : 'text-orange-400'
                    }`}>
                      {bridge.securityScore}/100
                    </span>
                  </div>
                  <div className="h-1.5 bg-white/10 rounded-full overflow-hidden">
                    <div
                      className={`h-full rounded-full ${
                        bridge.securityScore >= 90 ? 'bg-green-500' :
                        bridge.securityScore >= 80 ? 'bg-yellow-500' : 'bg-orange-500'
                      }`}
                      style={{ width: `${bridge.securityScore}%` }}
                    />
                  </div>
                </div>

                {/* Stats */}
                <div className="space-y-2 text-sm">
                  <div className="flex items-center justify-between">
                    <span className="text-white/40">Avg Time</span>
                    <span className="text-white">{bridge.avgTime}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-white/40">Chains</span>
                    <span className="text-white">{bridge.supportedChains.length}</span>
                  </div>
                </div>

                {/* Features */}
                <div className="mt-3 flex flex-wrap gap-1">
                  {bridge.features.map(f => (
                    <span key={f} className="px-2 py-0.5 bg-white/10 text-white/60 text-xs rounded">
                      {f}
                    </span>
                  ))}
                </div>

                {/* Audits */}
                <div className="mt-3 pt-3 border-t border-white/10">
                  <div className="text-white/40 text-xs mb-1">Audited by</div>
                  <div className="text-white/60 text-xs">
                    {bridge.auditedBy.join(', ')}
                  </div>
                </div>
              </div>
            ))}
          </div>

          {/* Chain support matrix */}
          <div className="bg-white/5 rounded-xl p-6 border border-white/10">
            <h3 className="text-white font-medium mb-4">Chain Support Matrix</h3>
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr>
                    <th className="text-left text-white/40 text-sm py-2 pr-4">Bridge</th>
                    {CHAINS.map(chain => (
                      <th key={chain.id} className="text-center text-white/40 text-xs py-2 px-2">
                        <div
                          className="w-6 h-6 rounded mx-auto flex items-center justify-center"
                          style={{ backgroundColor: `${chain.color}20` }}
                        >
                          <span className="text-[8px] font-bold" style={{ color: chain.color }}>
                            {chain.symbol}
                          </span>
                        </div>
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {BRIDGES.map(bridge => (
                    <tr key={bridge.id} className="border-t border-white/10">
                      <td className="text-white text-sm py-3 pr-4">{bridge.name}</td>
                      {CHAINS.map(chain => (
                        <td key={chain.id} className="text-center py-3 px-2">
                          {bridge.supportedChains.includes(chain.id) ? (
                            <CheckCircle className="w-4 h-4 text-green-400 mx-auto" />
                          ) : (
                            <XCircle className="w-4 h-4 text-white/20 mx-auto" />
                          )}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default BridgeAggregator
