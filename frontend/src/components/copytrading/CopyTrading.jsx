import React, { useState, useMemo, useEffect, useCallback } from 'react'
import {
  Users, Copy, TrendingUp, TrendingDown, Star, Shield, Award,
  DollarSign, Percent, BarChart3, Activity, Clock, Target,
  ChevronDown, ChevronUp, Play, Pause, Settings, AlertTriangle,
  Eye, Wallet, ArrowUpRight, ArrowDownRight, Check, X, Filter,
  Search, Zap, UserPlus, UserMinus, RefreshCw
} from 'lucide-react'

// Trader tiers
const TIERS = {
  BRONZE: { name: 'Bronze', color: '#CD7F32', minFollowers: 0, minPnl: 0 },
  SILVER: { name: 'Silver', color: '#C0C0C0', minFollowers: 50, minPnl: 10 },
  GOLD: { name: 'Gold', color: '#FFD700', minFollowers: 200, minPnl: 25 },
  PLATINUM: { name: 'Platinum', color: '#E5E4E2', minFollowers: 500, minPnl: 50 },
  DIAMOND: { name: 'Diamond', color: '#B9F2FF', minFollowers: 1000, minPnl: 100 }
}

// Trading styles
const STYLES = ['Scalper', 'Day Trader', 'Swing Trader', 'Position Trader', 'DeFi Farmer', 'NFT Flipper']

// Assets traded
const ASSETS = ['BTC', 'ETH', 'SOL', 'AVAX', 'ARB', 'OP', 'MATIC', 'LINK', 'UNI', 'AAVE']

// Generate mock trader
const generateTrader = () => {
  const pnl30d = (Math.random() - 0.3) * 200
  const winRate = 40 + Math.random() * 50
  const followers = Math.floor(Math.random() * 2000)
  const aum = Math.floor(Math.random() * 5000000) + 10000

  let tier = 'BRONZE'
  if (followers >= 1000 && pnl30d >= 100) tier = 'DIAMOND'
  else if (followers >= 500 && pnl30d >= 50) tier = 'PLATINUM'
  else if (followers >= 200 && pnl30d >= 25) tier = 'GOLD'
  else if (followers >= 50 && pnl30d >= 10) tier = 'SILVER'

  const names = ['CryptoKing', 'DeFiMaster', 'WhaleHunter', 'AlphaSeeker', 'ChainWizard', 'TokenSage', 'YieldFarmer', 'SwingKing', 'ScalpPro', 'HodlGod', 'MoonShot', 'DiamondHands']
  const name = names[Math.floor(Math.random() * names.length)] + Math.floor(Math.random() * 999)

  return {
    id: Math.random().toString(36).slice(2),
    name,
    avatar: `https://api.dicebear.com/7.x/identicon/svg?seed=${name}`,
    tier,
    pnl7d: (Math.random() - 0.3) * 50,
    pnl30d,
    pnl90d: pnl30d * (1 + (Math.random() - 0.5)),
    pnlAllTime: pnl30d * (2 + Math.random() * 3),
    winRate,
    avgTradeSize: Math.floor(Math.random() * 50000) + 1000,
    totalTrades: Math.floor(Math.random() * 5000) + 100,
    followers,
    following: Math.floor(Math.random() * 50),
    aum,
    maxDrawdown: Math.floor(Math.random() * 30) + 5,
    sharpeRatio: (Math.random() * 3).toFixed(2),
    style: STYLES[Math.floor(Math.random() * STYLES.length)],
    mainAssets: ASSETS.sort(() => Math.random() - 0.5).slice(0, 3),
    verified: Math.random() > 0.7,
    riskScore: Math.floor(Math.random() * 10) + 1,
    avgHoldTime: ['Minutes', 'Hours', 'Days', 'Weeks'][Math.floor(Math.random() * 4)],
    lastActive: new Date(Date.now() - Math.random() * 24 * 60 * 60 * 1000),
    isFollowing: false,
    copyAmount: 0
  }
}

// Generate mock trades
const generateRecentTrades = (traderId) => {
  return Array.from({ length: 10 }, () => ({
    id: Math.random().toString(36).slice(2),
    asset: ASSETS[Math.floor(Math.random() * ASSETS.length)],
    type: Math.random() > 0.5 ? 'LONG' : 'SHORT',
    entry: (Math.random() * 1000 + 100).toFixed(2),
    exit: Math.random() > 0.3 ? (Math.random() * 1000 + 100).toFixed(2) : null,
    size: (Math.random() * 10000 + 500).toFixed(2),
    pnl: (Math.random() - 0.4) * 500,
    pnlPercent: (Math.random() - 0.4) * 20,
    timestamp: new Date(Date.now() - Math.random() * 7 * 24 * 60 * 60 * 1000),
    status: Math.random() > 0.3 ? 'CLOSED' : 'OPEN',
    leverage: Math.floor(Math.random() * 10) + 1
  }))
}

// Generate top traders list
const generateTopTraders = () => {
  return Array.from({ length: 20 }, generateTrader)
    .sort((a, b) => b.pnl30d - a.pnl30d)
}

export function CopyTrading() {
  const [traders, setTraders] = useState([])
  const [selectedTrader, setSelectedTrader] = useState(null)
  const [traderTrades, setTraderTrades] = useState([])
  const [followedTraders, setFollowedTraders] = useState([])
  const [searchQuery, setSearchQuery] = useState('')
  const [sortBy, setSortBy] = useState('pnl30d')
  const [filterTier, setFilterTier] = useState('ALL')
  const [filterStyle, setFilterStyle] = useState('ALL')
  const [showCopyModal, setShowCopyModal] = useState(false)
  const [copySettings, setCopySettings] = useState({
    amount: 1000,
    maxDrawdown: 20,
    copyRatio: 100,
    stopLoss: 10,
    takeProfit: 50
  })
  const [activeTab, setActiveTab] = useState('discover')

  useEffect(() => {
    setTraders(generateTopTraders())
  }, [])

  const filteredTraders = useMemo(() => {
    return traders
      .filter(t => {
        if (searchQuery && !t.name.toLowerCase().includes(searchQuery.toLowerCase())) return false
        if (filterTier !== 'ALL' && t.tier !== filterTier) return false
        if (filterStyle !== 'ALL' && t.style !== filterStyle) return false
        return true
      })
      .sort((a, b) => {
        switch (sortBy) {
          case 'pnl7d': return b.pnl7d - a.pnl7d
          case 'pnl30d': return b.pnl30d - a.pnl30d
          case 'pnl90d': return b.pnl90d - a.pnl90d
          case 'winRate': return b.winRate - a.winRate
          case 'followers': return b.followers - a.followers
          case 'aum': return b.aum - a.aum
          default: return b.pnl30d - a.pnl30d
        }
      })
  }, [traders, searchQuery, sortBy, filterTier, filterStyle])

  const handleSelectTrader = (trader) => {
    setSelectedTrader(trader)
    setTraderTrades(generateRecentTrades(trader.id))
  }

  const handleFollow = (trader) => {
    setSelectedTrader(trader)
    setShowCopyModal(true)
  }

  const handleStartCopy = () => {
    if (!selectedTrader) return

    const updatedTrader = {
      ...selectedTrader,
      isFollowing: true,
      copyAmount: copySettings.amount
    }

    setTraders(prev => prev.map(t => t.id === selectedTrader.id ? updatedTrader : t))
    setFollowedTraders(prev => [...prev, updatedTrader])
    setSelectedTrader(updatedTrader)
    setShowCopyModal(false)
  }

  const handleUnfollow = (traderId) => {
    setTraders(prev => prev.map(t =>
      t.id === traderId ? { ...t, isFollowing: false, copyAmount: 0 } : t
    ))
    setFollowedTraders(prev => prev.filter(t => t.id !== traderId))
    if (selectedTrader?.id === traderId) {
      setSelectedTrader({ ...selectedTrader, isFollowing: false, copyAmount: 0 })
    }
  }

  const formatCurrency = (value) => {
    if (Math.abs(value) >= 1e6) return '$' + (value / 1e6).toFixed(2) + 'M'
    if (Math.abs(value) >= 1e3) return '$' + (value / 1e3).toFixed(2) + 'K'
    return '$' + value.toFixed(2)
  }

  const formatPnl = (value) => {
    const prefix = value >= 0 ? '+' : ''
    return prefix + value.toFixed(2) + '%'
  }

  const totalCopiedAmount = followedTraders.reduce((sum, t) => sum + t.copyAmount, 0)
  const avgPnl = followedTraders.length > 0
    ? followedTraders.reduce((sum, t) => sum + t.pnl30d, 0) / followedTraders.length
    : 0

  return (
    <div className="min-h-screen bg-[#0a0e14] text-white p-6">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold mb-2 flex items-center gap-3">
          <Copy className="w-8 h-8 text-cyan-400" />
          Copy Trading
        </h1>
        <p className="text-white/60">Follow top traders and automatically copy their positions</p>
      </div>

      {/* Stats Overview */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
        <div className="bg-white/5 rounded-xl border border-white/10 p-4">
          <div className="flex items-center gap-2 text-white/60 mb-2">
            <Users className="w-4 h-4" />
            Following
          </div>
          <div className="text-2xl font-bold">{followedTraders.length}</div>
          <div className="text-sm text-white/60">traders</div>
        </div>

        <div className="bg-white/5 rounded-xl border border-white/10 p-4">
          <div className="flex items-center gap-2 text-white/60 mb-2">
            <DollarSign className="w-4 h-4" />
            Total Copied
          </div>
          <div className="text-2xl font-bold">{formatCurrency(totalCopiedAmount)}</div>
          <div className="text-sm text-white/60">allocated</div>
        </div>

        <div className="bg-white/5 rounded-xl border border-white/10 p-4">
          <div className="flex items-center gap-2 text-white/60 mb-2">
            <TrendingUp className="w-4 h-4" />
            Avg PnL (30d)
          </div>
          <div className={`text-2xl font-bold ${avgPnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
            {formatPnl(avgPnl)}
          </div>
          <div className="text-sm text-white/60">of followed traders</div>
        </div>

        <div className="bg-white/5 rounded-xl border border-white/10 p-4">
          <div className="flex items-center gap-2 text-white/60 mb-2">
            <Activity className="w-4 h-4" />
            Active Copies
          </div>
          <div className="text-2xl font-bold">{followedTraders.filter(t => t.isFollowing).length}</div>
          <div className="text-sm text-white/60">positions mirrored</div>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-4 mb-6 border-b border-white/10">
        <button
          onClick={() => setActiveTab('discover')}
          className={`pb-3 px-2 font-medium transition-colors ${
            activeTab === 'discover'
              ? 'text-cyan-400 border-b-2 border-cyan-400'
              : 'text-white/60 hover:text-white'
          }`}
        >
          Discover Traders
        </button>
        <button
          onClick={() => setActiveTab('following')}
          className={`pb-3 px-2 font-medium transition-colors ${
            activeTab === 'following'
              ? 'text-cyan-400 border-b-2 border-cyan-400'
              : 'text-white/60 hover:text-white'
          }`}
        >
          Following ({followedTraders.length})
        </button>
        <button
          onClick={() => setActiveTab('portfolio')}
          className={`pb-3 px-2 font-medium transition-colors ${
            activeTab === 'portfolio'
              ? 'text-cyan-400 border-b-2 border-cyan-400'
              : 'text-white/60 hover:text-white'
          }`}
        >
          Copy Portfolio
        </button>
      </div>

      {activeTab === 'discover' && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Traders List */}
          <div className="lg:col-span-2 space-y-4">
            {/* Filters */}
            <div className="bg-white/5 rounded-xl border border-white/10 p-4">
              <div className="flex flex-col md:flex-row gap-4">
                <div className="flex-1 relative">
                  <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-white/40" />
                  <input
                    type="text"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    placeholder="Search traders..."
                    className="w-full bg-white/5 border border-white/10 rounded-lg pl-10 pr-4 py-2 focus:outline-none focus:border-cyan-500/50"
                  />
                </div>

                <select
                  value={sortBy}
                  onChange={(e) => setSortBy(e.target.value)}
                  className="bg-white/5 border border-white/10 rounded-lg px-4 py-2 focus:outline-none"
                >
                  <option value="pnl7d" className="bg-[#0a0e14]">PnL 7D</option>
                  <option value="pnl30d" className="bg-[#0a0e14]">PnL 30D</option>
                  <option value="pnl90d" className="bg-[#0a0e14]">PnL 90D</option>
                  <option value="winRate" className="bg-[#0a0e14]">Win Rate</option>
                  <option value="followers" className="bg-[#0a0e14]">Followers</option>
                  <option value="aum" className="bg-[#0a0e14]">AUM</option>
                </select>

                <select
                  value={filterTier}
                  onChange={(e) => setFilterTier(e.target.value)}
                  className="bg-white/5 border border-white/10 rounded-lg px-4 py-2 focus:outline-none"
                >
                  <option value="ALL" className="bg-[#0a0e14]">All Tiers</option>
                  {Object.entries(TIERS).map(([key, tier]) => (
                    <option key={key} value={key} className="bg-[#0a0e14]">{tier.name}</option>
                  ))}
                </select>

                <select
                  value={filterStyle}
                  onChange={(e) => setFilterStyle(e.target.value)}
                  className="bg-white/5 border border-white/10 rounded-lg px-4 py-2 focus:outline-none"
                >
                  <option value="ALL" className="bg-[#0a0e14]">All Styles</option>
                  {STYLES.map(style => (
                    <option key={style} value={style} className="bg-[#0a0e14]">{style}</option>
                  ))}
                </select>
              </div>
            </div>

            {/* Traders Grid */}
            <div className="space-y-3">
              {filteredTraders.map((trader, idx) => (
                <div
                  key={trader.id}
                  className={`bg-white/5 rounded-xl border border-white/10 p-4 cursor-pointer transition-colors hover:bg-white/10 ${
                    selectedTrader?.id === trader.id ? 'border-cyan-500/50' : ''
                  }`}
                  onClick={() => handleSelectTrader(trader)}
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-4">
                      <div className="relative">
                        <div className="w-12 h-12 rounded-full bg-white/10 flex items-center justify-center overflow-hidden">
                          <img src={trader.avatar} alt={trader.name} className="w-full h-full" />
                        </div>
                        {trader.verified && (
                          <div className="absolute -bottom-1 -right-1 w-5 h-5 bg-cyan-500 rounded-full flex items-center justify-center">
                            <Check className="w-3 h-3 text-white" />
                          </div>
                        )}
                      </div>
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="font-medium">{trader.name}</span>
                          <span
                            className="px-2 py-0.5 rounded text-xs font-medium"
                            style={{ backgroundColor: TIERS[trader.tier].color + '30', color: TIERS[trader.tier].color }}
                          >
                            {TIERS[trader.tier].name}
                          </span>
                        </div>
                        <div className="flex items-center gap-3 text-sm text-white/60">
                          <span>{trader.style}</span>
                          <span>|</span>
                          <span className="flex items-center gap-1">
                            <Users className="w-3 h-3" />
                            {trader.followers}
                          </span>
                        </div>
                      </div>
                    </div>

                    <div className="flex items-center gap-6">
                      <div className="text-center">
                        <div className={`font-bold ${trader.pnl7d >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                          {formatPnl(trader.pnl7d)}
                        </div>
                        <div className="text-xs text-white/60">7D</div>
                      </div>
                      <div className="text-center">
                        <div className={`font-bold ${trader.pnl30d >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                          {formatPnl(trader.pnl30d)}
                        </div>
                        <div className="text-xs text-white/60">30D</div>
                      </div>
                      <div className="text-center">
                        <div className="font-bold">{trader.winRate.toFixed(1)}%</div>
                        <div className="text-xs text-white/60">Win</div>
                      </div>
                      <button
                        onClick={(e) => {
                          e.stopPropagation()
                          trader.isFollowing ? handleUnfollow(trader.id) : handleFollow(trader)
                        }}
                        className={`px-4 py-2 rounded-lg font-medium flex items-center gap-2 transition-colors ${
                          trader.isFollowing
                            ? 'bg-red-500/20 text-red-400 hover:bg-red-500/30'
                            : 'bg-cyan-500 text-white hover:bg-cyan-600'
                        }`}
                      >
                        {trader.isFollowing ? (
                          <>
                            <UserMinus className="w-4 h-4" />
                            Unfollow
                          </>
                        ) : (
                          <>
                            <UserPlus className="w-4 h-4" />
                            Copy
                          </>
                        )}
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Trader Details */}
          <div className="space-y-4">
            {selectedTrader ? (
              <>
                {/* Profile Card */}
                <div className="bg-white/5 rounded-xl border border-white/10 p-4">
                  <div className="flex items-center gap-4 mb-4">
                    <div className="w-16 h-16 rounded-full bg-white/10 flex items-center justify-center overflow-hidden">
                      <img src={selectedTrader.avatar} alt={selectedTrader.name} className="w-full h-full" />
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="text-xl font-bold">{selectedTrader.name}</span>
                        {selectedTrader.verified && <Check className="w-5 h-5 text-cyan-400" />}
                      </div>
                      <div className="flex items-center gap-2">
                        <span
                          className="px-2 py-0.5 rounded text-xs font-medium"
                          style={{ backgroundColor: TIERS[selectedTrader.tier].color + '30', color: TIERS[selectedTrader.tier].color }}
                        >
                          {TIERS[selectedTrader.tier].name}
                        </span>
                        <span className="text-sm text-white/60">{selectedTrader.style}</span>
                      </div>
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-3 mb-4">
                    <div className="bg-white/5 rounded-lg p-3">
                      <div className="text-white/60 text-xs mb-1">Win Rate</div>
                      <div className="font-bold">{selectedTrader.winRate.toFixed(1)}%</div>
                    </div>
                    <div className="bg-white/5 rounded-lg p-3">
                      <div className="text-white/60 text-xs mb-1">Total Trades</div>
                      <div className="font-bold">{selectedTrader.totalTrades}</div>
                    </div>
                    <div className="bg-white/5 rounded-lg p-3">
                      <div className="text-white/60 text-xs mb-1">Max Drawdown</div>
                      <div className="font-bold text-orange-400">-{selectedTrader.maxDrawdown}%</div>
                    </div>
                    <div className="bg-white/5 rounded-lg p-3">
                      <div className="text-white/60 text-xs mb-1">Sharpe Ratio</div>
                      <div className="font-bold">{selectedTrader.sharpeRatio}</div>
                    </div>
                    <div className="bg-white/5 rounded-lg p-3">
                      <div className="text-white/60 text-xs mb-1">AUM</div>
                      <div className="font-bold">{formatCurrency(selectedTrader.aum)}</div>
                    </div>
                    <div className="bg-white/5 rounded-lg p-3">
                      <div className="text-white/60 text-xs mb-1">Avg Hold Time</div>
                      <div className="font-bold">{selectedTrader.avgHoldTime}</div>
                    </div>
                  </div>

                  <div className="mb-4">
                    <div className="text-white/60 text-xs mb-2">Main Assets</div>
                    <div className="flex gap-2">
                      {selectedTrader.mainAssets.map(asset => (
                        <span key={asset} className="px-2 py-1 bg-white/10 rounded text-sm">
                          {asset}
                        </span>
                      ))}
                    </div>
                  </div>

                  <div className="flex items-center justify-between p-3 bg-white/5 rounded-lg">
                    <div className="flex items-center gap-2">
                      <Shield className="w-4 h-4 text-white/60" />
                      <span className="text-sm text-white/60">Risk Score</span>
                    </div>
                    <div className="flex items-center gap-1">
                      {Array.from({ length: 10 }, (_, i) => (
                        <div
                          key={i}
                          className={`w-2 h-4 rounded ${
                            i < selectedTrader.riskScore
                              ? selectedTrader.riskScore <= 3 ? 'bg-green-400' :
                                selectedTrader.riskScore <= 6 ? 'bg-yellow-400' : 'bg-red-400'
                              : 'bg-white/10'
                          }`}
                        />
                      ))}
                    </div>
                  </div>
                </div>

                {/* Performance Chart */}
                <div className="bg-white/5 rounded-xl border border-white/10 p-4">
                  <h3 className="font-medium mb-4">Performance</h3>
                  <div className="space-y-3">
                    {[
                      { label: '7 Days', value: selectedTrader.pnl7d },
                      { label: '30 Days', value: selectedTrader.pnl30d },
                      { label: '90 Days', value: selectedTrader.pnl90d },
                      { label: 'All Time', value: selectedTrader.pnlAllTime }
                    ].map(period => (
                      <div key={period.label} className="flex items-center justify-between">
                        <span className="text-white/60">{period.label}</span>
                        <span className={`font-medium ${period.value >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                          {formatPnl(period.value)}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Recent Trades */}
                <div className="bg-white/5 rounded-xl border border-white/10 p-4">
                  <h3 className="font-medium mb-4">Recent Trades</h3>
                  <div className="space-y-2 max-h-64 overflow-y-auto">
                    {traderTrades.map((trade, idx) => (
                      <div key={idx} className="flex items-center justify-between p-2 bg-white/5 rounded-lg">
                        <div className="flex items-center gap-2">
                          <div className={`w-8 h-8 rounded flex items-center justify-center ${
                            trade.type === 'LONG' ? 'bg-green-500/20' : 'bg-red-500/20'
                          }`}>
                            {trade.type === 'LONG' ? (
                              <ArrowUpRight className="w-4 h-4 text-green-400" />
                            ) : (
                              <ArrowDownRight className="w-4 h-4 text-red-400" />
                            )}
                          </div>
                          <div>
                            <div className="font-medium text-sm">{trade.asset}</div>
                            <div className="text-xs text-white/60">{trade.leverage}x</div>
                          </div>
                        </div>
                        <div className="text-right">
                          <div className={`font-medium text-sm ${trade.pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                            {trade.pnl >= 0 ? '+' : ''}{formatCurrency(trade.pnl)}
                          </div>
                          <div className={`text-xs ${trade.status === 'OPEN' ? 'text-yellow-400' : 'text-white/60'}`}>
                            {trade.status}
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </>
            ) : (
              <div className="bg-white/5 rounded-xl border border-white/10 p-8 text-center">
                <Eye className="w-12 h-12 mx-auto mb-4 text-white/40" />
                <p className="text-white/60">Select a trader to view details</p>
              </div>
            )}
          </div>
        </div>
      )}

      {activeTab === 'following' && (
        <div className="space-y-4">
          {followedTraders.length === 0 ? (
            <div className="bg-white/5 rounded-xl border border-white/10 p-12 text-center">
              <Users className="w-16 h-16 mx-auto mb-4 text-white/40" />
              <h3 className="text-xl font-bold mb-2">No traders followed yet</h3>
              <p className="text-white/60 mb-4">Start copying top traders to grow your portfolio</p>
              <button
                onClick={() => setActiveTab('discover')}
                className="px-6 py-3 bg-cyan-500 hover:bg-cyan-600 rounded-lg font-medium"
              >
                Discover Traders
              </button>
            </div>
          ) : (
            followedTraders.map((trader, idx) => (
              <div key={trader.id} className="bg-white/5 rounded-xl border border-white/10 p-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-4">
                    <div className="w-12 h-12 rounded-full bg-white/10 overflow-hidden">
                      <img src={trader.avatar} alt={trader.name} className="w-full h-full" />
                    </div>
                    <div>
                      <div className="font-medium">{trader.name}</div>
                      <div className="text-sm text-white/60">
                        Copying: {formatCurrency(trader.copyAmount)}
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center gap-6">
                    <div className="text-center">
                      <div className={`font-bold ${trader.pnl30d >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                        {formatPnl(trader.pnl30d)}
                      </div>
                      <div className="text-xs text-white/60">30D PnL</div>
                    </div>
                    <div className="flex items-center gap-2">
                      <button className="p-2 bg-white/10 hover:bg-white/20 rounded-lg">
                        <Settings className="w-4 h-4" />
                      </button>
                      <button
                        onClick={() => handleUnfollow(trader.id)}
                        className="px-4 py-2 bg-red-500/20 text-red-400 hover:bg-red-500/30 rounded-lg font-medium"
                      >
                        Stop Copy
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
      )}

      {activeTab === 'portfolio' && (
        <div className="bg-white/5 rounded-xl border border-white/10 p-6">
          <h3 className="text-xl font-bold mb-4">Copy Trading Portfolio</h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div className="bg-white/5 rounded-lg p-4">
              <div className="text-white/60 text-sm mb-2">Total Allocated</div>
              <div className="text-2xl font-bold">{formatCurrency(totalCopiedAmount)}</div>
            </div>
            <div className="bg-white/5 rounded-lg p-4">
              <div className="text-white/60 text-sm mb-2">Unrealized PnL</div>
              <div className={`text-2xl font-bold ${avgPnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                {formatCurrency(totalCopiedAmount * avgPnl / 100)}
              </div>
            </div>
            <div className="bg-white/5 rounded-lg p-4">
              <div className="text-white/60 text-sm mb-2">Active Positions</div>
              <div className="text-2xl font-bold">{followedTraders.length * 3}</div>
            </div>
          </div>
        </div>
      )}

      {/* Copy Modal */}
      {showCopyModal && selectedTrader && (
        <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50 p-4">
          <div className="bg-[#0a0e14] border border-white/10 rounded-xl max-w-md w-full">
            <div className="p-4 border-b border-white/10 flex items-center justify-between">
              <h2 className="text-xl font-bold">Copy {selectedTrader.name}</h2>
              <button onClick={() => setShowCopyModal(false)} className="text-white/60 hover:text-white">
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="p-4 space-y-4">
              <div>
                <label className="block text-sm text-white/60 mb-2">Copy Amount (USD)</label>
                <input
                  type="number"
                  value={copySettings.amount}
                  onChange={(e) => setCopySettings(prev => ({ ...prev, amount: parseFloat(e.target.value) || 0 }))}
                  className="w-full bg-white/5 border border-white/10 rounded-lg px-4 py-3 focus:outline-none focus:border-cyan-500/50"
                />
              </div>

              <div>
                <label className="block text-sm text-white/60 mb-2">Copy Ratio (%)</label>
                <input
                  type="range"
                  min="10"
                  max="100"
                  value={copySettings.copyRatio}
                  onChange={(e) => setCopySettings(prev => ({ ...prev, copyRatio: parseInt(e.target.value) }))}
                  className="w-full"
                />
                <div className="text-center">{copySettings.copyRatio}%</div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm text-white/60 mb-2">Max Drawdown (%)</label>
                  <input
                    type="number"
                    value={copySettings.maxDrawdown}
                    onChange={(e) => setCopySettings(prev => ({ ...prev, maxDrawdown: parseFloat(e.target.value) || 0 }))}
                    className="w-full bg-white/5 border border-white/10 rounded-lg px-4 py-2 focus:outline-none"
                  />
                </div>
                <div>
                  <label className="block text-sm text-white/60 mb-2">Stop Loss (%)</label>
                  <input
                    type="number"
                    value={copySettings.stopLoss}
                    onChange={(e) => setCopySettings(prev => ({ ...prev, stopLoss: parseFloat(e.target.value) || 0 }))}
                    className="w-full bg-white/5 border border-white/10 rounded-lg px-4 py-2 focus:outline-none"
                  />
                </div>
              </div>

              <div className="bg-yellow-500/10 border border-yellow-500/20 rounded-lg p-3">
                <div className="flex items-start gap-2">
                  <AlertTriangle className="w-4 h-4 text-yellow-400 flex-shrink-0 mt-0.5" />
                  <div className="text-sm text-white/70">
                    Copy trading involves risk. Past performance does not guarantee future results.
                  </div>
                </div>
              </div>
            </div>

            <div className="p-4 border-t border-white/10 flex gap-3">
              <button
                onClick={() => setShowCopyModal(false)}
                className="flex-1 px-4 py-3 bg-white/10 hover:bg-white/20 rounded-lg font-medium"
              >
                Cancel
              </button>
              <button
                onClick={handleStartCopy}
                className="flex-1 px-4 py-3 bg-cyan-500 hover:bg-cyan-600 rounded-lg font-medium flex items-center justify-center gap-2"
              >
                <Zap className="w-5 h-5" />
                Start Copying
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default CopyTrading
