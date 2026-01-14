import React, { useState, useMemo, useEffect } from 'react'
import {
  Rocket, Calendar, Clock, Globe, Twitter, MessageCircle, ExternalLink,
  TrendingUp, TrendingDown, Star, StarOff, Filter, Search, Bell, BellOff,
  AlertTriangle, CheckCircle, XCircle, Users, DollarSign, Coins, Lock,
  Zap, Target, Shield, ChevronDown, MoreVertical, Eye, Share2
} from 'lucide-react'

const LAUNCH_PLATFORMS = [
  { value: 'all', label: 'All Platforms' },
  { value: 'pump_fun', label: 'Pump.fun' },
  { value: 'raydium', label: 'Raydium' },
  { value: 'orca', label: 'Orca' },
  { value: 'jupiter', label: 'Jupiter' },
  { value: 'uniswap', label: 'Uniswap' },
  { value: 'pancakeswap', label: 'PancakeSwap' },
  { value: 'pinksale', label: 'PinkSale' },
  { value: 'gempad', label: 'GemPad' }
]

const CHAINS = ['All', 'Solana', 'Ethereum', 'BSC', 'Arbitrum', 'Base', 'Polygon']

const LAUNCH_TYPES = [
  { value: 'all', label: 'All Types' },
  { value: 'fair_launch', label: 'Fair Launch' },
  { value: 'presale', label: 'Presale' },
  { value: 'ido', label: 'IDO' },
  { value: 'ilo', label: 'ILO' },
  { value: 'stealth', label: 'Stealth Launch' }
]

const RISK_LEVELS = ['All', 'Low', 'Medium', 'High', 'Very High']

export function TokenLaunchTracker() {
  const [launches, setLaunches] = useState([])
  const [selectedPlatform, setSelectedPlatform] = useState('all')
  const [selectedChain, setSelectedChain] = useState('All')
  const [selectedType, setSelectedType] = useState('all')
  const [selectedRisk, setSelectedRisk] = useState('All')
  const [searchQuery, setSearchQuery] = useState('')
  const [activeTab, setActiveTab] = useState('upcoming')
  const [watchlist, setWatchlist] = useState(new Set())
  const [alertsEnabled, setAlertsEnabled] = useState(new Set())
  const [selectedLaunch, setSelectedLaunch] = useState(null)

  // Generate mock launches
  useEffect(() => {
    const mockLaunches = [
      {
        id: 1,
        name: 'CatCoin',
        symbol: 'CAT',
        chain: 'Solana',
        platform: 'pump_fun',
        type: 'fair_launch',
        status: 'upcoming',
        launchDate: new Date(Date.now() + 2 * 60 * 60 * 1000),
        softCap: 50,
        hardCap: 100,
        raised: 0,
        price: 0.0001,
        totalSupply: 1000000000,
        liquidityPercent: 80,
        lockDuration: 180,
        riskLevel: 'High',
        socialScore: 72,
        twitter: '@catcoin_sol',
        telegram: 't.me/catcoin',
        website: 'catcoin.io',
        audit: false,
        kyc: false,
        description: 'The next big meme coin on Solana'
      },
      {
        id: 2,
        name: 'DeFi Protocol X',
        symbol: 'DPX',
        chain: 'Ethereum',
        platform: 'uniswap',
        type: 'presale',
        status: 'live',
        launchDate: new Date(Date.now() - 1 * 60 * 60 * 1000),
        softCap: 200,
        hardCap: 500,
        raised: 345,
        price: 0.05,
        totalSupply: 10000000,
        liquidityPercent: 60,
        lockDuration: 365,
        riskLevel: 'Medium',
        socialScore: 85,
        twitter: '@defi_protocol_x',
        telegram: 't.me/dpx_official',
        website: 'dpx.finance',
        audit: true,
        kyc: true,
        description: 'Revolutionary DeFi lending protocol'
      },
      {
        id: 3,
        name: 'GameFi World',
        symbol: 'GFW',
        chain: 'BSC',
        platform: 'pinksale',
        type: 'ido',
        status: 'upcoming',
        launchDate: new Date(Date.now() + 24 * 60 * 60 * 1000),
        softCap: 100,
        hardCap: 300,
        raised: 0,
        price: 0.02,
        totalSupply: 100000000,
        liquidityPercent: 70,
        lockDuration: 270,
        riskLevel: 'Medium',
        socialScore: 68,
        twitter: '@gamefi_world',
        telegram: 't.me/gamefiworld',
        website: 'gamefiworld.io',
        audit: true,
        kyc: false,
        description: 'Play-to-earn gaming ecosystem'
      },
      {
        id: 4,
        name: 'AI Trading Bot',
        symbol: 'AIBOT',
        chain: 'Arbitrum',
        platform: 'gempad',
        type: 'presale',
        status: 'live',
        launchDate: new Date(Date.now() - 12 * 60 * 60 * 1000),
        softCap: 75,
        hardCap: 150,
        raised: 142,
        price: 0.1,
        totalSupply: 5000000,
        liquidityPercent: 75,
        lockDuration: 180,
        riskLevel: 'Low',
        socialScore: 91,
        twitter: '@aibot_arb',
        telegram: 't.me/aibot_official',
        website: 'aibot.trade',
        audit: true,
        kyc: true,
        description: 'AI-powered trading automation'
      },
      {
        id: 5,
        name: 'Pepe 2.0',
        symbol: 'PEPE2',
        chain: 'Base',
        platform: 'uniswap',
        type: 'stealth',
        status: 'ended',
        launchDate: new Date(Date.now() - 48 * 60 * 60 * 1000),
        softCap: 0,
        hardCap: 0,
        raised: 0,
        price: 0.000001,
        totalSupply: 420690000000,
        liquidityPercent: 100,
        lockDuration: 0,
        riskLevel: 'Very High',
        socialScore: 45,
        twitter: '@pepe2_base',
        telegram: '',
        website: '',
        audit: false,
        kyc: false,
        currentPrice: 0.0000025,
        priceChange: 150,
        description: 'Stealth launched meme token'
      },
      {
        id: 6,
        name: 'Cross Chain Bridge',
        symbol: 'XBRIDGE',
        chain: 'Polygon',
        platform: 'gempad',
        type: 'ilo',
        status: 'upcoming',
        launchDate: new Date(Date.now() + 72 * 60 * 60 * 1000),
        softCap: 500,
        hardCap: 1000,
        raised: 0,
        price: 0.25,
        totalSupply: 20000000,
        liquidityPercent: 55,
        lockDuration: 365,
        riskLevel: 'Low',
        socialScore: 88,
        twitter: '@xbridge_poly',
        telegram: 't.me/xbridge',
        website: 'xbridge.network',
        audit: true,
        kyc: true,
        description: 'Multi-chain bridge infrastructure'
      },
      {
        id: 7,
        name: 'Moon Dog',
        symbol: 'MDOG',
        chain: 'Solana',
        platform: 'raydium',
        type: 'fair_launch',
        status: 'live',
        launchDate: new Date(Date.now() - 30 * 60 * 1000),
        softCap: 25,
        hardCap: 50,
        raised: 38,
        price: 0.00005,
        totalSupply: 5000000000,
        liquidityPercent: 90,
        lockDuration: 90,
        riskLevel: 'High',
        socialScore: 62,
        twitter: '@moondog_sol',
        telegram: 't.me/moondogsol',
        website: 'moondog.fun',
        audit: false,
        kyc: false,
        description: 'Community-driven meme token'
      },
      {
        id: 8,
        name: 'NFT Marketplace Pro',
        symbol: 'NFTM',
        chain: 'Ethereum',
        platform: 'pinksale',
        type: 'presale',
        status: 'ended',
        launchDate: new Date(Date.now() - 96 * 60 * 60 * 1000),
        softCap: 300,
        hardCap: 600,
        raised: 600,
        price: 0.08,
        totalSupply: 15000000,
        liquidityPercent: 65,
        lockDuration: 365,
        riskLevel: 'Medium',
        socialScore: 78,
        twitter: '@nftm_pro',
        telegram: 't.me/nftmpro',
        website: 'nftmpro.io',
        audit: true,
        kyc: true,
        currentPrice: 0.12,
        priceChange: 50,
        description: 'Next-gen NFT marketplace'
      }
    ]
    setLaunches(mockLaunches)
  }, [])

  const filteredLaunches = useMemo(() => {
    let filtered = launches

    // Filter by status/tab
    if (activeTab === 'upcoming') {
      filtered = filtered.filter(l => l.status === 'upcoming')
    } else if (activeTab === 'live') {
      filtered = filtered.filter(l => l.status === 'live')
    } else if (activeTab === 'ended') {
      filtered = filtered.filter(l => l.status === 'ended')
    } else if (activeTab === 'watchlist') {
      filtered = filtered.filter(l => watchlist.has(l.id))
    }

    // Filter by platform
    if (selectedPlatform !== 'all') {
      filtered = filtered.filter(l => l.platform === selectedPlatform)
    }

    // Filter by chain
    if (selectedChain !== 'All') {
      filtered = filtered.filter(l => l.chain === selectedChain)
    }

    // Filter by type
    if (selectedType !== 'all') {
      filtered = filtered.filter(l => l.type === selectedType)
    }

    // Filter by risk
    if (selectedRisk !== 'All') {
      filtered = filtered.filter(l => l.riskLevel === selectedRisk)
    }

    // Search
    if (searchQuery) {
      filtered = filtered.filter(l =>
        l.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        l.symbol.toLowerCase().includes(searchQuery.toLowerCase())
      )
    }

    return filtered
  }, [launches, activeTab, selectedPlatform, selectedChain, selectedType, selectedRisk, searchQuery, watchlist])

  const stats = useMemo(() => {
    const upcoming = launches.filter(l => l.status === 'upcoming').length
    const live = launches.filter(l => l.status === 'live').length
    const ended = launches.filter(l => l.status === 'ended').length
    const totalRaised = launches.filter(l => l.status === 'live').reduce((sum, l) => sum + l.raised, 0)

    return { upcoming, live, ended, totalRaised }
  }, [launches])

  const formatDate = (date) => {
    const now = new Date()
    const diff = date - now

    if (diff < 0) {
      // Past
      const hours = Math.abs(Math.floor(diff / (1000 * 60 * 60)))
      if (hours < 24) return `${hours}h ago`
      return date.toLocaleDateString()
    }

    // Future
    const hours = Math.floor(diff / (1000 * 60 * 60))
    const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60))

    if (hours < 1) return `${minutes}m`
    if (hours < 24) return `${hours}h ${minutes}m`
    const days = Math.floor(hours / 24)
    return `${days}d ${hours % 24}h`
  }

  const toggleWatchlist = (id) => {
    setWatchlist(prev => {
      const newSet = new Set(prev)
      if (newSet.has(id)) {
        newSet.delete(id)
      } else {
        newSet.add(id)
      }
      return newSet
    })
  }

  const toggleAlert = (id) => {
    setAlertsEnabled(prev => {
      const newSet = new Set(prev)
      if (newSet.has(id)) {
        newSet.delete(id)
      } else {
        newSet.add(id)
      }
      return newSet
    })
  }

  const getRiskBadge = (risk) => {
    switch (risk) {
      case 'Low':
        return <span className="px-2 py-1 bg-green-500/20 text-green-400 rounded text-xs">Low Risk</span>
      case 'Medium':
        return <span className="px-2 py-1 bg-yellow-500/20 text-yellow-400 rounded text-xs">Medium Risk</span>
      case 'High':
        return <span className="px-2 py-1 bg-orange-500/20 text-orange-400 rounded text-xs">High Risk</span>
      case 'Very High':
        return <span className="px-2 py-1 bg-red-500/20 text-red-400 rounded text-xs">Very High</span>
      default:
        return null
    }
  }

  const getStatusBadge = (status) => {
    switch (status) {
      case 'upcoming':
        return <span className="px-2 py-1 bg-blue-500/20 text-blue-400 rounded text-xs flex items-center gap-1"><Clock className="w-3 h-3" /> Upcoming</span>
      case 'live':
        return <span className="px-2 py-1 bg-green-500/20 text-green-400 rounded text-xs flex items-center gap-1"><Zap className="w-3 h-3" /> Live</span>
      case 'ended':
        return <span className="px-2 py-1 bg-white/20 text-white/60 rounded text-xs flex items-center gap-1"><CheckCircle className="w-3 h-3" /> Ended</span>
      default:
        return null
    }
  }

  const getProgressPercent = (raised, hardCap) => {
    if (!hardCap) return 0
    return Math.min((raised / hardCap) * 100, 100)
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Rocket className="w-6 h-6 text-purple-400" />
          <h2 className="text-xl font-bold">Token Launch Tracker</h2>
        </div>
        <div className="text-sm text-white/40">
          Tracking {launches.length} launches
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-blue-500/10 border border-blue-500/20 rounded-xl p-4">
          <div className="flex items-center gap-2 text-blue-400 mb-1">
            <Clock className="w-4 h-4" />
            <span className="text-sm">Upcoming</span>
          </div>
          <div className="text-2xl font-bold">{stats.upcoming}</div>
        </div>
        <div className="bg-green-500/10 border border-green-500/20 rounded-xl p-4">
          <div className="flex items-center gap-2 text-green-400 mb-1">
            <Zap className="w-4 h-4" />
            <span className="text-sm">Live Now</span>
          </div>
          <div className="text-2xl font-bold">{stats.live}</div>
        </div>
        <div className="bg-white/5 border border-white/10 rounded-xl p-4">
          <div className="flex items-center gap-2 text-white/60 mb-1">
            <CheckCircle className="w-4 h-4" />
            <span className="text-sm">Ended</span>
          </div>
          <div className="text-2xl font-bold">{stats.ended}</div>
        </div>
        <div className="bg-purple-500/10 border border-purple-500/20 rounded-xl p-4">
          <div className="flex items-center gap-2 text-purple-400 mb-1">
            <DollarSign className="w-4 h-4" />
            <span className="text-sm">Being Raised</span>
          </div>
          <div className="text-2xl font-bold">${stats.totalRaised.toLocaleString()}</div>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex items-center gap-4 border-b border-white/10 overflow-x-auto">
        {[
          { key: 'upcoming', label: 'Upcoming', count: stats.upcoming },
          { key: 'live', label: 'Live', count: stats.live },
          { key: 'ended', label: 'Ended', count: stats.ended },
          { key: 'watchlist', label: 'Watchlist', count: watchlist.size },
          { key: 'all', label: 'All', count: launches.length }
        ].map(tab => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={`pb-3 px-4 transition whitespace-nowrap ${
              activeTab === tab.key
                ? 'text-purple-400 border-b-2 border-purple-400'
                : 'text-white/60 hover:text-white'
            }`}
          >
            {tab.label} ({tab.count})
          </button>
        ))}
      </div>

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-4">
        <div className="flex-1 min-w-[200px] relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-white/40" />
          <input
            type="text"
            placeholder="Search tokens..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-10 pr-4 py-2 bg-white/5 border border-white/10 rounded-lg focus:outline-none"
          />
        </div>

        <select
          value={selectedPlatform}
          onChange={(e) => setSelectedPlatform(e.target.value)}
          className="px-4 py-2 bg-white/5 border border-white/10 rounded-lg focus:outline-none"
        >
          {LAUNCH_PLATFORMS.map(p => (
            <option key={p.value} value={p.value} className="bg-[#0a0e14]">{p.label}</option>
          ))}
        </select>

        <select
          value={selectedChain}
          onChange={(e) => setSelectedChain(e.target.value)}
          className="px-4 py-2 bg-white/5 border border-white/10 rounded-lg focus:outline-none"
        >
          {CHAINS.map(c => (
            <option key={c} value={c} className="bg-[#0a0e14]">{c}</option>
          ))}
        </select>

        <select
          value={selectedType}
          onChange={(e) => setSelectedType(e.target.value)}
          className="px-4 py-2 bg-white/5 border border-white/10 rounded-lg focus:outline-none"
        >
          {LAUNCH_TYPES.map(t => (
            <option key={t.value} value={t.value} className="bg-[#0a0e14]">{t.label}</option>
          ))}
        </select>

        <select
          value={selectedRisk}
          onChange={(e) => setSelectedRisk(e.target.value)}
          className="px-4 py-2 bg-white/5 border border-white/10 rounded-lg focus:outline-none"
        >
          {RISK_LEVELS.map(r => (
            <option key={r} value={r} className="bg-[#0a0e14]">{r} Risk</option>
          ))}
        </select>
      </div>

      {/* Launch Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {filteredLaunches.map(launch => (
          <div
            key={launch.id}
            className="bg-white/5 border border-white/10 rounded-xl p-5 hover:bg-white/[0.07] transition"
          >
            {/* Header */}
            <div className="flex items-start justify-between mb-4">
              <div className="flex items-center gap-3">
                <div className="w-12 h-12 rounded-full bg-gradient-to-br from-purple-500 to-pink-500 flex items-center justify-center text-lg font-bold">
                  {launch.symbol.slice(0, 2)}
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <span className="font-bold">{launch.name}</span>
                    <span className="text-white/40">${launch.symbol}</span>
                  </div>
                  <div className="flex items-center gap-2 text-sm text-white/60">
                    <span>{launch.chain}</span>
                    <span>•</span>
                    <span className="capitalize">{launch.type.replace('_', ' ')}</span>
                  </div>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => toggleWatchlist(launch.id)}
                  className={`p-2 rounded-lg transition ${
                    watchlist.has(launch.id)
                      ? 'bg-yellow-500/20 text-yellow-400'
                      : 'hover:bg-white/10 text-white/40'
                  }`}
                >
                  {watchlist.has(launch.id) ? <Star className="w-4 h-4" /> : <StarOff className="w-4 h-4" />}
                </button>
                <button
                  onClick={() => toggleAlert(launch.id)}
                  className={`p-2 rounded-lg transition ${
                    alertsEnabled.has(launch.id)
                      ? 'bg-blue-500/20 text-blue-400'
                      : 'hover:bg-white/10 text-white/40'
                  }`}
                >
                  {alertsEnabled.has(launch.id) ? <Bell className="w-4 h-4" /> : <BellOff className="w-4 h-4" />}
                </button>
              </div>
            </div>

            {/* Status & Time */}
            <div className="flex items-center gap-3 mb-4">
              {getStatusBadge(launch.status)}
              {getRiskBadge(launch.riskLevel)}
              <div className="flex items-center gap-1 text-sm text-white/60">
                <Calendar className="w-3 h-3" />
                {launch.status === 'upcoming' ? (
                  <span className="text-blue-400">Starts in {formatDate(launch.launchDate)}</span>
                ) : launch.status === 'live' ? (
                  <span className="text-green-400">Started {formatDate(launch.launchDate)}</span>
                ) : (
                  <span>Ended {formatDate(launch.launchDate)}</span>
                )}
              </div>
            </div>

            {/* Progress (for presales) */}
            {launch.hardCap > 0 && (
              <div className="mb-4">
                <div className="flex justify-between text-sm mb-1">
                  <span className="text-white/60">Progress</span>
                  <span>{launch.raised} / {launch.hardCap} SOL</span>
                </div>
                <div className="h-2 bg-white/10 rounded-full overflow-hidden">
                  <div
                    className={`h-full rounded-full transition-all ${
                      getProgressPercent(launch.raised, launch.hardCap) >= 100
                        ? 'bg-green-500'
                        : getProgressPercent(launch.raised, launch.hardCap) >= 50
                        ? 'bg-blue-500'
                        : 'bg-purple-500'
                    }`}
                    style={{ width: `${getProgressPercent(launch.raised, launch.hardCap)}%` }}
                  />
                </div>
                <div className="flex justify-between text-xs text-white/40 mt-1">
                  <span>Soft: {launch.softCap} SOL</span>
                  <span>{getProgressPercent(launch.raised, launch.hardCap).toFixed(0)}%</span>
                </div>
              </div>
            )}

            {/* Token Info */}
            <div className="grid grid-cols-3 gap-2 mb-4 text-sm">
              <div className="bg-white/5 rounded-lg p-2 text-center">
                <div className="text-white/40 text-xs">Price</div>
                <div className="font-medium">${launch.price}</div>
              </div>
              <div className="bg-white/5 rounded-lg p-2 text-center">
                <div className="text-white/40 text-xs">Liquidity</div>
                <div className="font-medium">{launch.liquidityPercent}%</div>
              </div>
              <div className="bg-white/5 rounded-lg p-2 text-center">
                <div className="text-white/40 text-xs">Lock</div>
                <div className="font-medium">{launch.lockDuration}d</div>
              </div>
            </div>

            {/* Price change for ended launches */}
            {launch.status === 'ended' && launch.currentPrice && (
              <div className={`p-3 rounded-lg mb-4 ${
                launch.priceChange >= 0 ? 'bg-green-500/10 border border-green-500/20' : 'bg-red-500/10 border border-red-500/20'
              }`}>
                <div className="flex items-center justify-between">
                  <span className="text-white/60">Current Price</span>
                  <span className="font-medium">${launch.currentPrice}</span>
                </div>
                <div className="flex items-center justify-between mt-1">
                  <span className="text-white/60">Since Launch</span>
                  <span className={`flex items-center gap-1 ${launch.priceChange >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                    {launch.priceChange >= 0 ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
                    {launch.priceChange >= 0 ? '+' : ''}{launch.priceChange}%
                  </span>
                </div>
              </div>
            )}

            {/* Audit/KYC badges */}
            <div className="flex items-center gap-2 mb-4">
              <div className={`flex items-center gap-1 px-2 py-1 rounded text-xs ${
                launch.audit ? 'bg-green-500/20 text-green-400' : 'bg-white/10 text-white/40'
              }`}>
                {launch.audit ? <CheckCircle className="w-3 h-3" /> : <XCircle className="w-3 h-3" />}
                Audit
              </div>
              <div className={`flex items-center gap-1 px-2 py-1 rounded text-xs ${
                launch.kyc ? 'bg-green-500/20 text-green-400' : 'bg-white/10 text-white/40'
              }`}>
                {launch.kyc ? <CheckCircle className="w-3 h-3" /> : <XCircle className="w-3 h-3" />}
                KYC
              </div>
              <div className="flex items-center gap-1 px-2 py-1 bg-purple-500/20 text-purple-400 rounded text-xs">
                <Users className="w-3 h-3" />
                {launch.socialScore} Social
              </div>
            </div>

            {/* Social Links */}
            <div className="flex items-center gap-2">
              {launch.twitter && (
                <a href="#" className="p-2 bg-white/5 rounded-lg hover:bg-white/10 transition">
                  <Twitter className="w-4 h-4" />
                </a>
              )}
              {launch.telegram && (
                <a href="#" className="p-2 bg-white/5 rounded-lg hover:bg-white/10 transition">
                  <MessageCircle className="w-4 h-4" />
                </a>
              )}
              {launch.website && (
                <a href="#" className="p-2 bg-white/5 rounded-lg hover:bg-white/10 transition">
                  <Globe className="w-4 h-4" />
                </a>
              )}
              <button
                onClick={() => setSelectedLaunch(launch)}
                className="ml-auto px-3 py-2 bg-purple-500/20 text-purple-400 rounded-lg hover:bg-purple-500/30 transition text-sm"
              >
                View Details
              </button>
            </div>
          </div>
        ))}
      </div>

      {filteredLaunches.length === 0 && (
        <div className="text-center py-12 text-white/40">
          <Rocket className="w-12 h-12 mx-auto mb-4 opacity-50" />
          <p>No launches found matching your criteria</p>
        </div>
      )}

      {/* Detail Modal */}
      {selectedLaunch && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-[#0a0e14] border border-white/10 rounded-xl p-6 w-full max-w-2xl max-h-[90vh] overflow-y-auto">
            <div className="flex items-start justify-between mb-6">
              <div className="flex items-center gap-3">
                <div className="w-14 h-14 rounded-full bg-gradient-to-br from-purple-500 to-pink-500 flex items-center justify-center text-xl font-bold">
                  {selectedLaunch.symbol.slice(0, 2)}
                </div>
                <div>
                  <h3 className="text-xl font-bold">{selectedLaunch.name}</h3>
                  <p className="text-white/60">${selectedLaunch.symbol}</p>
                </div>
              </div>
              <button
                onClick={() => setSelectedLaunch(null)}
                className="p-2 hover:bg-white/10 rounded-lg"
              >
                <XCircle className="w-5 h-5" />
              </button>
            </div>

            <p className="text-white/70 mb-6">{selectedLaunch.description}</p>

            <div className="grid grid-cols-2 md:grid-cols-3 gap-4 mb-6">
              <div className="bg-white/5 rounded-lg p-3">
                <div className="text-xs text-white/40">Chain</div>
                <div className="font-medium">{selectedLaunch.chain}</div>
              </div>
              <div className="bg-white/5 rounded-lg p-3">
                <div className="text-xs text-white/40">Platform</div>
                <div className="font-medium capitalize">{selectedLaunch.platform.replace('_', ' ')}</div>
              </div>
              <div className="bg-white/5 rounded-lg p-3">
                <div className="text-xs text-white/40">Launch Type</div>
                <div className="font-medium capitalize">{selectedLaunch.type.replace('_', ' ')}</div>
              </div>
              <div className="bg-white/5 rounded-lg p-3">
                <div className="text-xs text-white/40">Launch Price</div>
                <div className="font-medium">${selectedLaunch.price}</div>
              </div>
              <div className="bg-white/5 rounded-lg p-3">
                <div className="text-xs text-white/40">Total Supply</div>
                <div className="font-medium">{selectedLaunch.totalSupply.toLocaleString()}</div>
              </div>
              <div className="bg-white/5 rounded-lg p-3">
                <div className="text-xs text-white/40">Market Cap</div>
                <div className="font-medium">${(selectedLaunch.price * selectedLaunch.totalSupply).toLocaleString()}</div>
              </div>
              <div className="bg-white/5 rounded-lg p-3">
                <div className="text-xs text-white/40">Liquidity %</div>
                <div className="font-medium">{selectedLaunch.liquidityPercent}%</div>
              </div>
              <div className="bg-white/5 rounded-lg p-3">
                <div className="text-xs text-white/40">Lock Duration</div>
                <div className="font-medium">{selectedLaunch.lockDuration} days</div>
              </div>
              <div className="bg-white/5 rounded-lg p-3">
                <div className="text-xs text-white/40">Risk Level</div>
                {getRiskBadge(selectedLaunch.riskLevel)}
              </div>
            </div>

            <div className="flex gap-2">
              <button
                onClick={() => toggleWatchlist(selectedLaunch.id)}
                className={`flex-1 py-3 rounded-lg font-medium transition ${
                  watchlist.has(selectedLaunch.id)
                    ? 'bg-yellow-500/20 text-yellow-400'
                    : 'bg-white/5 hover:bg-white/10'
                }`}
              >
                {watchlist.has(selectedLaunch.id) ? 'Remove from Watchlist' : 'Add to Watchlist'}
              </button>
              {selectedLaunch.website && (
                <a
                  href="#"
                  className="flex-1 py-3 bg-purple-500 text-white rounded-lg font-medium hover:bg-purple-600 transition text-center"
                >
                  Visit Website
                </a>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default TokenLaunchTracker
