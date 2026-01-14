import React, { useState, useMemo, useEffect, useCallback } from 'react'
import {
  Layers, Wallet, TrendingUp, TrendingDown, RefreshCw, Plus,
  Trash2, Eye, EyeOff, ChevronDown, ChevronUp, Search, Filter,
  DollarSign, PieChart, BarChart3, ArrowUpRight, ArrowDownRight,
  Clock, Activity, AlertTriangle, Check, X, Copy, ExternalLink,
  Settings, Zap, Globe, Link2
} from 'lucide-react'

// Supported chains
const CHAINS = {
  ETH: { name: 'Ethereum', color: '#627EEA', symbol: 'ETH', explorer: 'etherscan.io' },
  BSC: { name: 'BNB Chain', color: '#F3BA2F', symbol: 'BNB', explorer: 'bscscan.com' },
  ARB: { name: 'Arbitrum', color: '#28A0F0', symbol: 'ARB', explorer: 'arbiscan.io' },
  BASE: { name: 'Base', color: '#0052FF', symbol: 'ETH', explorer: 'basescan.org' },
  POLYGON: { name: 'Polygon', color: '#8247E5', symbol: 'MATIC', explorer: 'polygonscan.com' },
  AVAX: { name: 'Avalanche', color: '#E84142', symbol: 'AVAX', explorer: 'snowtrace.io' },
  OP: { name: 'Optimism', color: '#FF0420', symbol: 'OP', explorer: 'optimistic.etherscan.io' },
  SOL: { name: 'Solana', color: '#00FFA3', symbol: 'SOL', explorer: 'solscan.io' }
}

// Token list
const TOKENS = {
  ETH: { name: 'Ethereum', symbol: 'ETH', color: '#627EEA' },
  WETH: { name: 'Wrapped Ethereum', symbol: 'WETH', color: '#627EEA' },
  BTC: { name: 'Bitcoin', symbol: 'BTC', color: '#F7931A' },
  WBTC: { name: 'Wrapped Bitcoin', symbol: 'WBTC', color: '#F7931A' },
  USDT: { name: 'Tether', symbol: 'USDT', color: '#50AF95' },
  USDC: { name: 'USD Coin', symbol: 'USDC', color: '#2775CA' },
  DAI: { name: 'Dai', symbol: 'DAI', color: '#F5AC37' },
  LINK: { name: 'Chainlink', symbol: 'LINK', color: '#2A5ADA' },
  UNI: { name: 'Uniswap', symbol: 'UNI', color: '#FF007A' },
  AAVE: { name: 'Aave', symbol: 'AAVE', color: '#B6509E' },
  ARB: { name: 'Arbitrum', symbol: 'ARB', color: '#28A0F0' },
  OP: { name: 'Optimism', symbol: 'OP', color: '#FF0420' },
  SOL: { name: 'Solana', symbol: 'SOL', color: '#00FFA3' },
  MATIC: { name: 'Polygon', symbol: 'MATIC', color: '#8247E5' }
}

// Generate mock holdings for a wallet
const generateWalletHoldings = (address, chain) => {
  const tokenKeys = Object.keys(TOKENS)
  const numTokens = Math.floor(Math.random() * 8) + 3

  return Array.from({ length: numTokens }, (_, idx) => {
    const tokenKey = tokenKeys[Math.floor(Math.random() * tokenKeys.length)]
    const token = TOKENS[tokenKey]
    const amount = Math.random() * 100 + 0.01
    const price = tokenKey === 'BTC' || tokenKey === 'WBTC' ? 65000 + Math.random() * 5000 :
                  tokenKey === 'ETH' || tokenKey === 'WETH' ? 3500 + Math.random() * 500 :
                  tokenKey === 'SOL' ? 150 + Math.random() * 30 :
                  tokenKey.includes('USD') || tokenKey === 'DAI' ? 1 :
                  Math.random() * 50 + 1

    return {
      token: tokenKey,
      name: token.name,
      symbol: token.symbol,
      color: token.color,
      amount,
      price,
      value: amount * price,
      change24h: (Math.random() - 0.5) * 20,
      chain
    }
  }).reduce((acc, holding) => {
    const existing = acc.find(h => h.token === holding.token)
    if (existing) {
      existing.amount += holding.amount
      existing.value += holding.value
    } else {
      acc.push(holding)
    }
    return acc
  }, []).sort((a, b) => b.value - a.value)
}

// Generate mock DeFi positions
const generateDefiPositions = (chain) => {
  const protocols = {
    ETH: ['Aave', 'Compound', 'Lido', 'Uniswap', 'Curve'],
    BSC: ['PancakeSwap', 'Venus', 'Alpaca'],
    ARB: ['GMX', 'Radiant', 'Camelot'],
    BASE: ['Aerodrome', 'BaseSwap'],
    POLYGON: ['QuickSwap', 'Aave', 'Balancer'],
    AVAX: ['Trader Joe', 'BENQI', 'Platypus'],
    OP: ['Velodrome', 'Synthetix'],
    SOL: ['Raydium', 'Marinade', 'Orca']
  }

  const types = ['Lending', 'LP', 'Staking', 'Farming']

  return Array.from({ length: Math.floor(Math.random() * 4) + 1 }, () => {
    const chainProtocols = protocols[chain] || protocols.ETH
    const protocol = chainProtocols[Math.floor(Math.random() * chainProtocols.length)]
    const type = types[Math.floor(Math.random() * types.length)]
    const value = Math.random() * 50000 + 1000

    return {
      protocol,
      type,
      chain,
      value,
      apy: Math.random() * 30 + 1,
      rewards: Math.random() * 100,
      healthFactor: type === 'Lending' ? 1.5 + Math.random() * 1.5 : null
    }
  })
}

// Generate mock NFTs
const generateNFTs = (chain) => {
  const collections = ['BAYC', 'CryptoPunks', 'Azuki', 'Doodles', 'Pudgy Penguins', 'Milady']

  return Array.from({ length: Math.floor(Math.random() * 3) }, () => ({
    collection: collections[Math.floor(Math.random() * collections.length)],
    tokenId: Math.floor(Math.random() * 10000),
    chain,
    floorPrice: Math.random() * 50 + 1,
    lastSale: Math.random() * 100 + 5
  }))
}

export function CrossChainTracker() {
  const [wallets, setWallets] = useState([])
  const [newWalletAddress, setNewWalletAddress] = useState('')
  const [newWalletChain, setNewWalletChain] = useState('ETH')
  const [newWalletLabel, setNewWalletLabel] = useState('')
  const [selectedWallet, setSelectedWallet] = useState(null)
  const [viewMode, setViewMode] = useState('all')
  const [showAddWallet, setShowAddWallet] = useState(false)
  const [isRefreshing, setIsRefreshing] = useState(false)
  const [activeTab, setActiveTab] = useState('tokens')

  useEffect(() => {
    // Initialize with sample wallets
    const sampleWallets = [
      { address: '0x742d35Cc6634C0532925a3b844Bc9e7595f8fE89', chain: 'ETH', label: 'Main Wallet' },
      { address: '0x1234567890123456789012345678901234567890', chain: 'ARB', label: 'Arbitrum DeFi' },
      { address: '0xabcdef1234567890abcdef1234567890abcdef12', chain: 'BASE', label: 'Base Portfolio' }
    ].map(w => ({
      ...w,
      holdings: generateWalletHoldings(w.address, w.chain),
      defiPositions: generateDefiPositions(w.chain),
      nfts: generateNFTs(w.chain),
      lastUpdated: new Date()
    }))

    setWallets(sampleWallets)
  }, [])

  const handleAddWallet = useCallback(() => {
    if (!newWalletAddress) return

    const newWallet = {
      address: newWalletAddress,
      chain: newWalletChain,
      label: newWalletLabel || `Wallet ${wallets.length + 1}`,
      holdings: generateWalletHoldings(newWalletAddress, newWalletChain),
      defiPositions: generateDefiPositions(newWalletChain),
      nfts: generateNFTs(newWalletChain),
      lastUpdated: new Date()
    }

    setWallets(prev => [...prev, newWallet])
    setNewWalletAddress('')
    setNewWalletLabel('')
    setShowAddWallet(false)
  }, [newWalletAddress, newWalletChain, newWalletLabel, wallets])

  const handleRemoveWallet = useCallback((address) => {
    setWallets(prev => prev.filter(w => w.address !== address))
    if (selectedWallet?.address === address) {
      setSelectedWallet(null)
    }
  }, [selectedWallet])

  const handleRefresh = useCallback(() => {
    setIsRefreshing(true)
    setTimeout(() => {
      setWallets(prev => prev.map(w => ({
        ...w,
        holdings: generateWalletHoldings(w.address, w.chain),
        defiPositions: generateDefiPositions(w.chain),
        lastUpdated: new Date()
      })))
      setIsRefreshing(false)
    }, 2000)
  }, [])

  // Aggregated metrics
  const totalPortfolioValue = useMemo(() =>
    wallets.reduce((sum, w) => sum + w.holdings.reduce((s, h) => s + h.value, 0), 0),
    [wallets]
  )

  const totalDefiValue = useMemo(() =>
    wallets.reduce((sum, w) => sum + w.defiPositions.reduce((s, p) => s + p.value, 0), 0),
    [wallets]
  )

  const aggregatedHoldings = useMemo(() => {
    const holdings = {}
    wallets.forEach(wallet => {
      wallet.holdings.forEach(h => {
        if (holdings[h.token]) {
          holdings[h.token].amount += h.amount
          holdings[h.token].value += h.value
          holdings[h.token].chains.add(wallet.chain)
        } else {
          holdings[h.token] = {
            ...h,
            chains: new Set([wallet.chain])
          }
        }
      })
    })
    return Object.values(holdings)
      .map(h => ({ ...h, chains: Array.from(h.chains) }))
      .sort((a, b) => b.value - a.value)
  }, [wallets])

  const chainDistribution = useMemo(() => {
    const dist = {}
    wallets.forEach(w => {
      const chainValue = w.holdings.reduce((s, h) => s + h.value, 0)
      dist[w.chain] = (dist[w.chain] || 0) + chainValue
    })
    return Object.entries(dist)
      .map(([chain, value]) => ({ chain, value, percent: (value / totalPortfolioValue) * 100 }))
      .sort((a, b) => b.value - a.value)
  }, [wallets, totalPortfolioValue])

  const formatCurrency = (value) => {
    if (value >= 1e6) return '$' + (value / 1e6).toFixed(2) + 'M'
    if (value >= 1e3) return '$' + (value / 1e3).toFixed(2) + 'K'
    return '$' + value.toFixed(2)
  }

  const formatAddress = (addr) => `${addr.slice(0, 6)}...${addr.slice(-4)}`

  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text)
  }

  return (
    <div className="min-h-screen bg-[#0a0e14] text-white p-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold mb-2 flex items-center gap-3">
            <Layers className="w-8 h-8 text-cyan-400" />
            Cross-Chain Tracker
          </h1>
          <p className="text-white/60">Track your entire crypto portfolio across all chains in one place</p>
        </div>

        <div className="flex items-center gap-4">
          <button
            onClick={() => setShowAddWallet(true)}
            className="px-4 py-2 bg-cyan-500 hover:bg-cyan-600 rounded-lg font-medium flex items-center gap-2"
          >
            <Plus className="w-4 h-4" />
            Add Wallet
          </button>

          <button
            onClick={handleRefresh}
            disabled={isRefreshing}
            className="p-2 bg-white/10 hover:bg-white/20 rounded-lg transition-colors"
          >
            <RefreshCw className={`w-5 h-5 ${isRefreshing ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {/* Portfolio Overview */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
        <div className="bg-white/5 rounded-xl border border-white/10 p-4">
          <div className="flex items-center gap-2 text-white/60 mb-2">
            <DollarSign className="w-4 h-4" />
            Total Portfolio
          </div>
          <div className="text-2xl font-bold">{formatCurrency(totalPortfolioValue + totalDefiValue)}</div>
          <div className="text-sm text-green-400">+5.2% (24h)</div>
        </div>

        <div className="bg-white/5 rounded-xl border border-white/10 p-4">
          <div className="flex items-center gap-2 text-white/60 mb-2">
            <Wallet className="w-4 h-4" />
            Token Holdings
          </div>
          <div className="text-2xl font-bold">{formatCurrency(totalPortfolioValue)}</div>
          <div className="text-sm text-white/60">{aggregatedHoldings.length} tokens</div>
        </div>

        <div className="bg-white/5 rounded-xl border border-white/10 p-4">
          <div className="flex items-center gap-2 text-white/60 mb-2">
            <Activity className="w-4 h-4" />
            DeFi Positions
          </div>
          <div className="text-2xl font-bold">{formatCurrency(totalDefiValue)}</div>
          <div className="text-sm text-white/60">{wallets.reduce((s, w) => s + w.defiPositions.length, 0)} positions</div>
        </div>

        <div className="bg-white/5 rounded-xl border border-white/10 p-4">
          <div className="flex items-center gap-2 text-white/60 mb-2">
            <Globe className="w-4 h-4" />
            Chains
          </div>
          <div className="text-2xl font-bold">{new Set(wallets.map(w => w.chain)).size}</div>
          <div className="text-sm text-white/60">{wallets.length} wallets</div>
        </div>
      </div>

      {/* Chain Distribution */}
      <div className="bg-white/5 rounded-xl border border-white/10 p-4 mb-6">
        <h3 className="font-medium mb-4 flex items-center gap-2">
          <PieChart className="w-5 h-5 text-cyan-400" />
          Chain Distribution
        </h3>
        <div className="flex items-center gap-4 overflow-x-auto pb-2">
          {chainDistribution.map((item, idx) => (
            <div key={item.chain} className="flex items-center gap-3 min-w-fit">
              <div
                className="w-10 h-10 rounded-full flex items-center justify-center font-bold"
                style={{ backgroundColor: CHAINS[item.chain].color + '30', color: CHAINS[item.chain].color }}
              >
                {item.chain.slice(0, 2)}
              </div>
              <div>
                <div className="font-medium">{CHAINS[item.chain].name}</div>
                <div className="text-sm text-white/60">
                  {formatCurrency(item.value)} ({item.percent.toFixed(1)}%)
                </div>
              </div>
            </div>
          ))}
        </div>
        <div className="mt-4 h-3 rounded-full overflow-hidden flex">
          {chainDistribution.map((item, idx) => (
            <div
              key={item.chain}
              style={{
                width: `${item.percent}%`,
                backgroundColor: CHAINS[item.chain].color
              }}
              title={`${CHAINS[item.chain].name}: ${item.percent.toFixed(1)}%`}
            />
          ))}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Wallets List */}
        <div className="space-y-4">
          <h3 className="font-medium flex items-center gap-2">
            <Wallet className="w-5 h-5 text-cyan-400" />
            Wallets ({wallets.length})
          </h3>

          {wallets.map((wallet, idx) => (
            <div
              key={wallet.address}
              className={`bg-white/5 rounded-xl border border-white/10 p-4 cursor-pointer transition-colors ${
                selectedWallet?.address === wallet.address ? 'border-cyan-500/50 bg-cyan-500/5' : 'hover:bg-white/10'
              }`}
              onClick={() => setSelectedWallet(wallet)}
            >
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-3">
                  <div
                    className="w-10 h-10 rounded-full flex items-center justify-center font-bold"
                    style={{ backgroundColor: CHAINS[wallet.chain].color + '30', color: CHAINS[wallet.chain].color }}
                  >
                    {wallet.chain.slice(0, 2)}
                  </div>
                  <div>
                    <div className="font-medium">{wallet.label}</div>
                    <div className="flex items-center gap-2 text-sm text-white/60">
                      <span>{formatAddress(wallet.address)}</span>
                      <button
                        onClick={(e) => { e.stopPropagation(); copyToClipboard(wallet.address) }}
                        className="hover:text-white"
                      >
                        <Copy className="w-3 h-3" />
                      </button>
                    </div>
                  </div>
                </div>
                <button
                  onClick={(e) => { e.stopPropagation(); handleRemoveWallet(wallet.address) }}
                  className="p-1 text-white/40 hover:text-red-400"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>

              <div className="flex items-center justify-between">
                <div>
                  <div className="text-lg font-bold">
                    {formatCurrency(wallet.holdings.reduce((s, h) => s + h.value, 0))}
                  </div>
                  <div className="text-xs text-white/60">
                    {wallet.holdings.length} tokens
                  </div>
                </div>
                <div className="text-right">
                  <div className="text-sm text-green-400">+3.2%</div>
                  <div className="text-xs text-white/60">24h</div>
                </div>
              </div>
            </div>
          ))}

          {wallets.length === 0 && (
            <div className="bg-white/5 rounded-xl border border-white/10 p-8 text-center">
              <Wallet className="w-12 h-12 mx-auto mb-4 text-white/40" />
              <p className="text-white/60">No wallets added yet</p>
              <button
                onClick={() => setShowAddWallet(true)}
                className="mt-4 px-4 py-2 bg-cyan-500 hover:bg-cyan-600 rounded-lg font-medium"
              >
                Add Wallet
              </button>
            </div>
          )}
        </div>

        {/* Main Content */}
        <div className="lg:col-span-2">
          {/* Tabs */}
          <div className="flex gap-4 mb-4 border-b border-white/10">
            {['tokens', 'defi', 'nfts'].map(tab => (
              <button
                key={tab}
                onClick={() => setActiveTab(tab)}
                className={`pb-3 px-2 font-medium capitalize transition-colors ${
                  activeTab === tab
                    ? 'text-cyan-400 border-b-2 border-cyan-400'
                    : 'text-white/60 hover:text-white'
                }`}
              >
                {tab === 'defi' ? 'DeFi' : tab === 'nfts' ? 'NFTs' : 'Tokens'}
              </button>
            ))}
          </div>

          {activeTab === 'tokens' && (
            <div className="bg-white/5 rounded-xl border border-white/10 overflow-hidden">
              <div className="p-4 border-b border-white/10">
                <h3 className="font-medium">
                  {selectedWallet ? `${selectedWallet.label} Holdings` : 'All Token Holdings'}
                </h3>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead>
                    <tr className="border-b border-white/10">
                      <th className="text-left p-4 text-white/60 font-medium">Token</th>
                      <th className="text-right p-4 text-white/60 font-medium">Balance</th>
                      <th className="text-right p-4 text-white/60 font-medium">Price</th>
                      <th className="text-right p-4 text-white/60 font-medium">Value</th>
                      <th className="text-right p-4 text-white/60 font-medium">24h</th>
                      {!selectedWallet && <th className="text-left p-4 text-white/60 font-medium">Chains</th>}
                    </tr>
                  </thead>
                  <tbody>
                    {(selectedWallet ? selectedWallet.holdings : aggregatedHoldings).map((holding, idx) => (
                      <tr key={holding.token + idx} className="border-b border-white/5 hover:bg-white/5">
                        <td className="p-4">
                          <div className="flex items-center gap-3">
                            <div
                              className="w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold"
                              style={{ backgroundColor: holding.color + '30', color: holding.color }}
                            >
                              {holding.symbol.slice(0, 2)}
                            </div>
                            <div>
                              <div className="font-medium">{holding.symbol}</div>
                              <div className="text-xs text-white/60">{holding.name}</div>
                            </div>
                          </div>
                        </td>
                        <td className="p-4 text-right">{holding.amount.toFixed(4)}</td>
                        <td className="p-4 text-right">${holding.price.toFixed(2)}</td>
                        <td className="p-4 text-right font-medium">{formatCurrency(holding.value)}</td>
                        <td className={`p-4 text-right ${holding.change24h >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                          {holding.change24h >= 0 ? '+' : ''}{holding.change24h.toFixed(2)}%
                        </td>
                        {!selectedWallet && (
                          <td className="p-4">
                            <div className="flex gap-1">
                              {holding.chains?.map(chain => (
                                <div
                                  key={chain}
                                  className="w-6 h-6 rounded-full flex items-center justify-center text-xs"
                                  style={{ backgroundColor: CHAINS[chain].color + '30', color: CHAINS[chain].color }}
                                  title={CHAINS[chain].name}
                                >
                                  {chain.slice(0, 1)}
                                </div>
                              ))}
                            </div>
                          </td>
                        )}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {activeTab === 'defi' && (
            <div className="bg-white/5 rounded-xl border border-white/10 overflow-hidden">
              <div className="p-4 border-b border-white/10">
                <h3 className="font-medium">
                  {selectedWallet ? `${selectedWallet.label} DeFi Positions` : 'All DeFi Positions'}
                </h3>
              </div>
              <div className="divide-y divide-white/5">
                {(selectedWallet ? selectedWallet.defiPositions : wallets.flatMap(w => w.defiPositions)).map((position, idx) => (
                  <div key={idx} className="p-4 hover:bg-white/5">
                    <div className="flex items-center justify-between mb-2">
                      <div className="flex items-center gap-3">
                        <div
                          className="w-10 h-10 rounded-lg flex items-center justify-center"
                          style={{ backgroundColor: CHAINS[position.chain].color + '20' }}
                        >
                          <Activity className="w-5 h-5" style={{ color: CHAINS[position.chain].color }} />
                        </div>
                        <div>
                          <div className="font-medium">{position.protocol}</div>
                          <div className="flex items-center gap-2 text-sm text-white/60">
                            <span className="px-2 py-0.5 bg-white/10 rounded">{position.type}</span>
                            <span>{CHAINS[position.chain].name}</span>
                          </div>
                        </div>
                      </div>
                      <div className="text-right">
                        <div className="font-bold">{formatCurrency(position.value)}</div>
                        <div className="text-sm text-green-400">{position.apy.toFixed(2)}% APY</div>
                      </div>
                    </div>
                    {position.healthFactor && (
                      <div className="flex items-center gap-2 mt-2">
                        <span className="text-sm text-white/60">Health Factor:</span>
                        <span className={`font-medium ${
                          position.healthFactor > 2 ? 'text-green-400' :
                          position.healthFactor > 1.5 ? 'text-yellow-400' : 'text-red-400'
                        }`}>
                          {position.healthFactor.toFixed(2)}
                        </span>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {activeTab === 'nfts' && (
            <div className="bg-white/5 rounded-xl border border-white/10 p-4">
              <h3 className="font-medium mb-4">NFT Holdings</h3>
              <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
                {(selectedWallet ? selectedWallet.nfts : wallets.flatMap(w => w.nfts)).map((nft, idx) => (
                  <div key={idx} className="bg-white/5 rounded-lg p-4">
                    <div className="aspect-square bg-white/10 rounded-lg mb-3 flex items-center justify-center">
                      <span className="text-2xl font-bold text-white/40">#{nft.tokenId}</span>
                    </div>
                    <div className="font-medium">{nft.collection}</div>
                    <div className="text-sm text-white/60">#{nft.tokenId}</div>
                    <div className="mt-2 flex justify-between text-sm">
                      <span className="text-white/60">Floor</span>
                      <span>{nft.floorPrice.toFixed(2)} ETH</span>
                    </div>
                  </div>
                ))}
                {(selectedWallet ? selectedWallet.nfts : wallets.flatMap(w => w.nfts)).length === 0 && (
                  <div className="col-span-3 text-center py-8 text-white/60">
                    No NFTs found
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Add Wallet Modal */}
      {showAddWallet && (
        <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50 p-4">
          <div className="bg-[#0a0e14] border border-white/10 rounded-xl max-w-md w-full">
            <div className="p-4 border-b border-white/10 flex items-center justify-between">
              <h2 className="text-xl font-bold">Add Wallet</h2>
              <button onClick={() => setShowAddWallet(false)} className="text-white/60 hover:text-white">
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="p-4 space-y-4">
              <div>
                <label className="block text-sm text-white/60 mb-2">Wallet Address</label>
                <input
                  type="text"
                  value={newWalletAddress}
                  onChange={(e) => setNewWalletAddress(e.target.value)}
                  placeholder="0x..."
                  className="w-full bg-white/5 border border-white/10 rounded-lg px-4 py-3 focus:outline-none focus:border-cyan-500/50"
                />
              </div>

              <div>
                <label className="block text-sm text-white/60 mb-2">Chain</label>
                <select
                  value={newWalletChain}
                  onChange={(e) => setNewWalletChain(e.target.value)}
                  className="w-full bg-white/5 border border-white/10 rounded-lg px-4 py-3 focus:outline-none"
                >
                  {Object.entries(CHAINS).map(([key, chain]) => (
                    <option key={key} value={key} className="bg-[#0a0e14]">{chain.name}</option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-sm text-white/60 mb-2">Label (optional)</label>
                <input
                  type="text"
                  value={newWalletLabel}
                  onChange={(e) => setNewWalletLabel(e.target.value)}
                  placeholder="My Main Wallet"
                  className="w-full bg-white/5 border border-white/10 rounded-lg px-4 py-3 focus:outline-none focus:border-cyan-500/50"
                />
              </div>
            </div>

            <div className="p-4 border-t border-white/10 flex gap-3">
              <button
                onClick={() => setShowAddWallet(false)}
                className="flex-1 px-4 py-3 bg-white/10 hover:bg-white/20 rounded-lg font-medium"
              >
                Cancel
              </button>
              <button
                onClick={handleAddWallet}
                disabled={!newWalletAddress}
                className="flex-1 px-4 py-3 bg-cyan-500 hover:bg-cyan-600 disabled:bg-white/10 disabled:cursor-not-allowed rounded-lg font-medium"
              >
                Add Wallet
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default CrossChainTracker
