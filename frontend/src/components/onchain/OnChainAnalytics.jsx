import React, { useState, useMemo, useEffect, useCallback } from 'react'
import {
  Activity, BarChart3, TrendingUp, TrendingDown, Users, Wallet,
  ArrowUpRight, ArrowDownRight, RefreshCw, Clock, DollarSign,
  AlertTriangle, ChevronDown, ChevronUp, Filter, Search, Zap,
  Database, Globe, Layers, Hash, Box, GitBranch, Target, Eye,
  PieChart, Coins, Shield, Lock, Unlock
} from 'lucide-react'

// Supported chains
const CHAINS = {
  ETH: { name: 'Ethereum', color: '#627EEA', symbol: 'ETH' },
  BSC: { name: 'BNB Chain', color: '#F3BA2F', symbol: 'BNB' },
  ARB: { name: 'Arbitrum', color: '#28A0F0', symbol: 'ARB' },
  BASE: { name: 'Base', color: '#0052FF', symbol: 'ETH' },
  POLYGON: { name: 'Polygon', color: '#8247E5', symbol: 'MATIC' },
  AVAX: { name: 'Avalanche', color: '#E84142', symbol: 'AVAX' },
  SOL: { name: 'Solana', color: '#00FFA3', symbol: 'SOL' },
  OP: { name: 'Optimism', color: '#FF0420', symbol: 'OP' }
}

// Metric types
const METRICS = {
  TVL: { name: 'Total Value Locked', icon: Lock, unit: '$' },
  VOLUME: { name: '24h Volume', icon: BarChart3, unit: '$' },
  TXS: { name: 'Transactions', icon: Activity, unit: '' },
  USERS: { name: 'Active Addresses', icon: Users, unit: '' },
  GAS: { name: 'Avg Gas Price', icon: Zap, unit: 'gwei' },
  FEES: { name: 'Total Fees', icon: DollarSign, unit: '$' }
}

// Generate mock chain data
const generateChainData = () => {
  return Object.keys(CHAINS).map(chainKey => ({
    chain: chainKey,
    tvl: Math.random() * 50000000000 + 1000000000,
    volume24h: Math.random() * 5000000000 + 100000000,
    txCount24h: Math.floor(Math.random() * 5000000 + 100000),
    activeAddresses24h: Math.floor(Math.random() * 1000000 + 50000),
    avgGasPrice: Math.random() * 50 + 5,
    totalFees24h: Math.random() * 50000000 + 1000000,
    tvlChange: (Math.random() - 0.5) * 20,
    volumeChange: (Math.random() - 0.5) * 30,
    txChange: (Math.random() - 0.5) * 25,
    blockHeight: Math.floor(Math.random() * 20000000 + 15000000),
    avgBlockTime: Math.random() * 10 + 1
  }))
}

// Generate mock token flows
const generateTokenFlows = () => {
  const tokens = ['USDT', 'USDC', 'WETH', 'WBTC', 'DAI', 'LINK', 'UNI', 'AAVE']
  const flows = []

  for (let i = 0; i < 15; i++) {
    const fromChains = Object.keys(CHAINS)
    const fromChain = fromChains[Math.floor(Math.random() * fromChains.length)]
    let toChain = fromChains[Math.floor(Math.random() * fromChains.length)]
    while (toChain === fromChain) {
      toChain = fromChains[Math.floor(Math.random() * fromChains.length)]
    }

    flows.push({
      id: `flow-${i}`,
      token: tokens[Math.floor(Math.random() * tokens.length)],
      fromChain,
      toChain,
      amount: Math.random() * 10000000 + 10000,
      timestamp: new Date(Date.now() - Math.random() * 24 * 60 * 60 * 1000),
      txHash: `0x${Math.random().toString(16).slice(2, 66)}`
    })
  }

  return flows.sort((a, b) => b.timestamp - a.timestamp)
}

// Generate mock whale movements
const generateWhaleMovements = () => {
  const movements = []
  const types = ['deposit', 'withdrawal', 'transfer', 'bridge']
  const protocols = ['Binance', 'Coinbase', 'Kraken', 'Aave', 'Compound', 'Unknown']

  for (let i = 0; i < 20; i++) {
    const type = types[Math.floor(Math.random() * types.length)]
    movements.push({
      id: `whale-${i}`,
      address: `0x${Math.random().toString(16).slice(2, 10)}...${Math.random().toString(16).slice(2, 6)}`,
      type,
      asset: ['ETH', 'BTC', 'USDT', 'USDC'][Math.floor(Math.random() * 4)],
      amount: Math.random() * 50000000 + 1000000,
      from: type === 'withdrawal' ? protocols[Math.floor(Math.random() * protocols.length)] : 'Wallet',
      to: type === 'deposit' ? protocols[Math.floor(Math.random() * protocols.length)] : 'Wallet',
      chain: Object.keys(CHAINS)[Math.floor(Math.random() * Object.keys(CHAINS).length)],
      timestamp: new Date(Date.now() - Math.random() * 2 * 60 * 60 * 1000),
      isSmartMoney: Math.random() > 0.5
    })
  }

  return movements.sort((a, b) => b.timestamp - a.timestamp)
}

// Generate mock protocol data
const generateProtocolData = () => {
  const protocols = [
    { name: 'Uniswap', category: 'DEX' },
    { name: 'Aave', category: 'Lending' },
    { name: 'Lido', category: 'Staking' },
    { name: 'Curve', category: 'DEX' },
    { name: 'MakerDAO', category: 'CDP' },
    { name: 'Compound', category: 'Lending' },
    { name: 'Convex', category: 'Yield' },
    { name: 'GMX', category: 'Perps' },
    { name: 'Rocket Pool', category: 'Staking' },
    { name: 'Balancer', category: 'DEX' }
  ]

  return protocols.map(p => ({
    ...p,
    tvl: Math.random() * 10000000000 + 100000000,
    tvlChange: (Math.random() - 0.5) * 20,
    volume24h: Math.random() * 1000000000 + 10000000,
    users24h: Math.floor(Math.random() * 50000 + 1000),
    fees24h: Math.random() * 5000000 + 100000,
    revenue24h: Math.random() * 1000000 + 10000,
    chains: Object.keys(CHAINS).filter(() => Math.random() > 0.5)
  })).sort((a, b) => b.tvl - a.tvl)
}

// Generate mock stablecoin data
const generateStablecoinData = () => {
  const stables = [
    { symbol: 'USDT', name: 'Tether', color: '#50AF95' },
    { symbol: 'USDC', name: 'USD Coin', color: '#2775CA' },
    { symbol: 'DAI', name: 'Dai', color: '#F5AC37' },
    { symbol: 'BUSD', name: 'Binance USD', color: '#F0B90B' },
    { symbol: 'FRAX', name: 'Frax', color: '#000000' },
    { symbol: 'TUSD', name: 'TrueUSD', color: '#1A5AFF' }
  ]

  return stables.map(s => ({
    ...s,
    marketCap: Math.random() * 80000000000 + 1000000000,
    volume24h: Math.random() * 10000000000 + 100000000,
    peg: 0.998 + Math.random() * 0.004,
    dominance: Math.random() * 50,
    chainDistribution: Object.keys(CHAINS).reduce((acc, chain) => {
      acc[chain] = Math.random()
      return acc
    }, {})
  })).sort((a, b) => b.marketCap - a.marketCap)
}

export function OnChainAnalytics() {
  const [chainData, setChainData] = useState([])
  const [tokenFlows, setTokenFlows] = useState([])
  const [whaleMovements, setWhaleMovements] = useState([])
  const [protocolData, setProtocolData] = useState([])
  const [stablecoinData, setStablecoinData] = useState([])
  const [selectedChain, setSelectedChain] = useState('ALL')
  const [activeTab, setActiveTab] = useState('overview')
  const [timeframe, setTimeframe] = useState('24h')
  const [isRefreshing, setIsRefreshing] = useState(false)

  useEffect(() => {
    setChainData(generateChainData())
    setTokenFlows(generateTokenFlows())
    setWhaleMovements(generateWhaleMovements())
    setProtocolData(generateProtocolData())
    setStablecoinData(generateStablecoinData())
  }, [])

  const handleRefresh = useCallback(() => {
    setIsRefreshing(true)
    setTimeout(() => {
      setChainData(generateChainData())
      setTokenFlows(generateTokenFlows())
      setWhaleMovements(generateWhaleMovements())
      setIsRefreshing(false)
    }, 1500)
  }, [])

  const totalTVL = useMemo(() =>
    chainData.reduce((sum, c) => sum + c.tvl, 0),
    [chainData]
  )

  const totalVolume = useMemo(() =>
    chainData.reduce((sum, c) => sum + c.volume24h, 0),
    [chainData]
  )

  const totalTxs = useMemo(() =>
    chainData.reduce((sum, c) => sum + c.txCount24h, 0),
    [chainData]
  )

  const filteredData = useMemo(() => {
    if (selectedChain === 'ALL') return chainData
    return chainData.filter(c => c.chain === selectedChain)
  }, [chainData, selectedChain])

  const formatNumber = (num, decimals = 2) => {
    if (num >= 1e12) return (num / 1e12).toFixed(decimals) + 'T'
    if (num >= 1e9) return (num / 1e9).toFixed(decimals) + 'B'
    if (num >= 1e6) return (num / 1e6).toFixed(decimals) + 'M'
    if (num >= 1e3) return (num / 1e3).toFixed(decimals) + 'K'
    return num.toFixed(decimals)
  }

  const formatCurrency = (num) => '$' + formatNumber(num)

  const formatChange = (change) => {
    const prefix = change >= 0 ? '+' : ''
    return prefix + change.toFixed(2) + '%'
  }

  return (
    <div className="min-h-screen bg-[#0a0e14] text-white p-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold mb-2 flex items-center gap-3">
            <Database className="w-8 h-8 text-cyan-400" />
            On-Chain Analytics
          </h1>
          <p className="text-white/60">Real-time blockchain data, flows, and protocol metrics</p>
        </div>

        <div className="flex items-center gap-4">
          <select
            value={selectedChain}
            onChange={(e) => setSelectedChain(e.target.value)}
            className="bg-white/5 border border-white/10 rounded-lg px-4 py-2 focus:outline-none"
          >
            <option value="ALL" className="bg-[#0a0e14]">All Chains</option>
            {Object.entries(CHAINS).map(([key, chain]) => (
              <option key={key} value={key} className="bg-[#0a0e14]">{chain.name}</option>
            ))}
          </select>

          <select
            value={timeframe}
            onChange={(e) => setTimeframe(e.target.value)}
            className="bg-white/5 border border-white/10 rounded-lg px-4 py-2 focus:outline-none"
          >
            <option value="24h" className="bg-[#0a0e14]">24 Hours</option>
            <option value="7d" className="bg-[#0a0e14]">7 Days</option>
            <option value="30d" className="bg-[#0a0e14]">30 Days</option>
          </select>

          <button
            onClick={handleRefresh}
            disabled={isRefreshing}
            className="p-2 bg-white/10 hover:bg-white/20 rounded-lg transition-colors"
          >
            <RefreshCw className={`w-5 h-5 ${isRefreshing ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {/* Global Stats */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
        <div className="bg-white/5 rounded-xl border border-white/10 p-4">
          <div className="flex items-center gap-2 text-white/60 mb-2">
            <Lock className="w-4 h-4" />
            Total Value Locked
          </div>
          <div className="text-2xl font-bold">{formatCurrency(totalTVL)}</div>
          <div className="text-sm text-green-400">+5.2% (24h)</div>
        </div>

        <div className="bg-white/5 rounded-xl border border-white/10 p-4">
          <div className="flex items-center gap-2 text-white/60 mb-2">
            <BarChart3 className="w-4 h-4" />
            24h Volume
          </div>
          <div className="text-2xl font-bold">{formatCurrency(totalVolume)}</div>
          <div className="text-sm text-red-400">-3.1% (24h)</div>
        </div>

        <div className="bg-white/5 rounded-xl border border-white/10 p-4">
          <div className="flex items-center gap-2 text-white/60 mb-2">
            <Activity className="w-4 h-4" />
            Transactions
          </div>
          <div className="text-2xl font-bold">{formatNumber(totalTxs, 0)}</div>
          <div className="text-sm text-green-400">+8.7% (24h)</div>
        </div>

        <div className="bg-white/5 rounded-xl border border-white/10 p-4">
          <div className="flex items-center gap-2 text-white/60 mb-2">
            <Layers className="w-4 h-4" />
            Active Chains
          </div>
          <div className="text-2xl font-bold">{Object.keys(CHAINS).length}</div>
          <div className="text-sm text-white/60">Networks tracked</div>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-4 mb-6 border-b border-white/10 overflow-x-auto">
        {['overview', 'flows', 'whales', 'protocols', 'stablecoins'].map(tab => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`pb-3 px-2 font-medium capitalize whitespace-nowrap transition-colors ${
              activeTab === tab
                ? 'text-cyan-400 border-b-2 border-cyan-400'
                : 'text-white/60 hover:text-white'
            }`}
          >
            {tab}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      {activeTab === 'overview' && (
        <div className="space-y-6">
          {/* Chain Metrics */}
          <div className="bg-white/5 rounded-xl border border-white/10 overflow-hidden">
            <div className="p-4 border-b border-white/10">
              <h2 className="font-semibold flex items-center gap-2">
                <Globe className="w-5 h-5 text-cyan-400" />
                Chain Metrics
              </h2>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-white/10">
                    <th className="text-left p-4 text-white/60 font-medium">Chain</th>
                    <th className="text-right p-4 text-white/60 font-medium">TVL</th>
                    <th className="text-right p-4 text-white/60 font-medium">24h Volume</th>
                    <th className="text-right p-4 text-white/60 font-medium">Transactions</th>
                    <th className="text-right p-4 text-white/60 font-medium">Active Addresses</th>
                    <th className="text-right p-4 text-white/60 font-medium">Avg Gas</th>
                    <th className="text-right p-4 text-white/60 font-medium">Fees</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredData.map((data, idx) => (
                    <tr key={data.chain} className="border-b border-white/5 hover:bg-white/5">
                      <td className="p-4">
                        <div className="flex items-center gap-3">
                          <div
                            className="w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold"
                            style={{ backgroundColor: CHAINS[data.chain].color + '30', color: CHAINS[data.chain].color }}
                          >
                            {data.chain.slice(0, 2)}
                          </div>
                          <span className="font-medium">{CHAINS[data.chain].name}</span>
                        </div>
                      </td>
                      <td className="p-4 text-right">
                        <div className="font-medium">{formatCurrency(data.tvl)}</div>
                        <div className={`text-xs ${data.tvlChange >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                          {formatChange(data.tvlChange)}
                        </div>
                      </td>
                      <td className="p-4 text-right">
                        <div className="font-medium">{formatCurrency(data.volume24h)}</div>
                        <div className={`text-xs ${data.volumeChange >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                          {formatChange(data.volumeChange)}
                        </div>
                      </td>
                      <td className="p-4 text-right">
                        <div className="font-medium">{formatNumber(data.txCount24h, 0)}</div>
                        <div className={`text-xs ${data.txChange >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                          {formatChange(data.txChange)}
                        </div>
                      </td>
                      <td className="p-4 text-right">{formatNumber(data.activeAddresses24h, 0)}</td>
                      <td className="p-4 text-right">{data.avgGasPrice.toFixed(1)} gwei</td>
                      <td className="p-4 text-right">{formatCurrency(data.totalFees24h)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {activeTab === 'flows' && (
        <div className="space-y-6">
          <div className="bg-white/5 rounded-xl border border-white/10 overflow-hidden">
            <div className="p-4 border-b border-white/10">
              <h2 className="font-semibold flex items-center gap-2">
                <GitBranch className="w-5 h-5 text-cyan-400" />
                Cross-Chain Token Flows
              </h2>
            </div>
            <div className="divide-y divide-white/5">
              {tokenFlows.map((flow, idx) => (
                <div key={flow.id} className="p-4 flex items-center justify-between hover:bg-white/5">
                  <div className="flex items-center gap-4">
                    <div className="flex items-center gap-2">
                      <div
                        className="w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold"
                        style={{ backgroundColor: CHAINS[flow.fromChain].color + '30', color: CHAINS[flow.fromChain].color }}
                      >
                        {flow.fromChain.slice(0, 2)}
                      </div>
                      <ArrowUpRight className="w-4 h-4 text-white/40" />
                      <div
                        className="w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold"
                        style={{ backgroundColor: CHAINS[flow.toChain].color + '30', color: CHAINS[flow.toChain].color }}
                      >
                        {flow.toChain.slice(0, 2)}
                      </div>
                    </div>
                    <div>
                      <div className="font-medium">{flow.token}</div>
                      <div className="text-sm text-white/60">
                        {CHAINS[flow.fromChain].name} → {CHAINS[flow.toChain].name}
                      </div>
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="font-medium">{formatCurrency(flow.amount)}</div>
                    <div className="text-sm text-white/60">
                      {flow.timestamp.toLocaleTimeString()}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {activeTab === 'whales' && (
        <div className="space-y-6">
          <div className="bg-white/5 rounded-xl border border-white/10 overflow-hidden">
            <div className="p-4 border-b border-white/10">
              <h2 className="font-semibold flex items-center gap-2">
                <Target className="w-5 h-5 text-cyan-400" />
                Whale Movements
              </h2>
            </div>
            <div className="divide-y divide-white/5">
              {whaleMovements.map((move, idx) => (
                <div key={move.id} className="p-4 hover:bg-white/5">
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-3">
                      <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${
                        move.type === 'deposit' ? 'bg-red-500/20' :
                        move.type === 'withdrawal' ? 'bg-green-500/20' :
                        'bg-blue-500/20'
                      }`}>
                        {move.type === 'deposit' ? (
                          <ArrowDownRight className="w-5 h-5 text-red-400" />
                        ) : move.type === 'withdrawal' ? (
                          <ArrowUpRight className="w-5 h-5 text-green-400" />
                        ) : (
                          <RefreshCw className="w-5 h-5 text-blue-400" />
                        )}
                      </div>
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="font-medium capitalize">{move.type}</span>
                          {move.isSmartMoney && (
                            <span className="px-2 py-0.5 bg-purple-500/20 text-purple-400 text-xs rounded">
                              Smart Money
                            </span>
                          )}
                        </div>
                        <div className="text-sm text-white/60">{move.address}</div>
                      </div>
                    </div>
                    <div className="text-right">
                      <div className="font-bold">{formatCurrency(move.amount)}</div>
                      <div className="text-sm text-white/60">{move.asset}</div>
                    </div>
                  </div>
                  <div className="flex items-center justify-between text-sm text-white/60 ml-13">
                    <span>{move.from} → {move.to}</span>
                    <span className="flex items-center gap-2">
                      <span
                        className="px-2 py-0.5 rounded text-xs"
                        style={{ backgroundColor: CHAINS[move.chain].color + '30', color: CHAINS[move.chain].color }}
                      >
                        {CHAINS[move.chain].name}
                      </span>
                      {move.timestamp.toLocaleTimeString()}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {activeTab === 'protocols' && (
        <div className="bg-white/5 rounded-xl border border-white/10 overflow-hidden">
          <div className="p-4 border-b border-white/10">
            <h2 className="font-semibold flex items-center gap-2">
              <Box className="w-5 h-5 text-cyan-400" />
              Top Protocols by TVL
            </h2>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-white/10">
                  <th className="text-left p-4 text-white/60 font-medium">#</th>
                  <th className="text-left p-4 text-white/60 font-medium">Protocol</th>
                  <th className="text-left p-4 text-white/60 font-medium">Category</th>
                  <th className="text-right p-4 text-white/60 font-medium">TVL</th>
                  <th className="text-right p-4 text-white/60 font-medium">24h Volume</th>
                  <th className="text-right p-4 text-white/60 font-medium">Users (24h)</th>
                  <th className="text-right p-4 text-white/60 font-medium">Fees (24h)</th>
                  <th className="text-left p-4 text-white/60 font-medium">Chains</th>
                </tr>
              </thead>
              <tbody>
                {protocolData.map((protocol, idx) => (
                  <tr key={protocol.name} className="border-b border-white/5 hover:bg-white/5">
                    <td className="p-4 text-white/60">{idx + 1}</td>
                    <td className="p-4 font-medium">{protocol.name}</td>
                    <td className="p-4">
                      <span className="px-2 py-1 bg-white/10 rounded text-sm">{protocol.category}</span>
                    </td>
                    <td className="p-4 text-right">
                      <div className="font-medium">{formatCurrency(protocol.tvl)}</div>
                      <div className={`text-xs ${protocol.tvlChange >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                        {formatChange(protocol.tvlChange)}
                      </div>
                    </td>
                    <td className="p-4 text-right">{formatCurrency(protocol.volume24h)}</td>
                    <td className="p-4 text-right">{formatNumber(protocol.users24h, 0)}</td>
                    <td className="p-4 text-right">{formatCurrency(protocol.fees24h)}</td>
                    <td className="p-4">
                      <div className="flex gap-1">
                        {protocol.chains.slice(0, 4).map(chain => (
                          <div
                            key={chain}
                            className="w-6 h-6 rounded-full flex items-center justify-center text-xs"
                            style={{ backgroundColor: CHAINS[chain].color + '30', color: CHAINS[chain].color }}
                            title={CHAINS[chain].name}
                          >
                            {chain.slice(0, 1)}
                          </div>
                        ))}
                        {protocol.chains.length > 4 && (
                          <div className="w-6 h-6 rounded-full bg-white/10 flex items-center justify-center text-xs">
                            +{protocol.chains.length - 4}
                          </div>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {activeTab === 'stablecoins' && (
        <div className="space-y-6">
          <div className="bg-white/5 rounded-xl border border-white/10 overflow-hidden">
            <div className="p-4 border-b border-white/10">
              <h2 className="font-semibold flex items-center gap-2">
                <Coins className="w-5 h-5 text-cyan-400" />
                Stablecoin Overview
              </h2>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-white/10">
                    <th className="text-left p-4 text-white/60 font-medium">Stablecoin</th>
                    <th className="text-right p-4 text-white/60 font-medium">Market Cap</th>
                    <th className="text-right p-4 text-white/60 font-medium">24h Volume</th>
                    <th className="text-right p-4 text-white/60 font-medium">Peg</th>
                    <th className="text-right p-4 text-white/60 font-medium">Dominance</th>
                  </tr>
                </thead>
                <tbody>
                  {stablecoinData.map((stable, idx) => (
                    <tr key={stable.symbol} className="border-b border-white/5 hover:bg-white/5">
                      <td className="p-4">
                        <div className="flex items-center gap-3">
                          <div
                            className="w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold"
                            style={{ backgroundColor: stable.color + '30', color: stable.color === '#000000' ? '#fff' : stable.color }}
                          >
                            {stable.symbol.slice(0, 2)}
                          </div>
                          <div>
                            <div className="font-medium">{stable.symbol}</div>
                            <div className="text-sm text-white/60">{stable.name}</div>
                          </div>
                        </div>
                      </td>
                      <td className="p-4 text-right font-medium">{formatCurrency(stable.marketCap)}</td>
                      <td className="p-4 text-right">{formatCurrency(stable.volume24h)}</td>
                      <td className="p-4 text-right">
                        <span className={stable.peg >= 0.999 && stable.peg <= 1.001 ? 'text-green-400' : 'text-yellow-400'}>
                          ${stable.peg.toFixed(4)}
                        </span>
                      </td>
                      <td className="p-4 text-right">{stable.dominance.toFixed(2)}%</td>
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

export default OnChainAnalytics
