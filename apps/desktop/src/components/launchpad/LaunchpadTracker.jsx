import React, { useState, useEffect, useMemo } from 'react'
import {
  Rocket, TrendingUp, TrendingDown, DollarSign, Clock,
  Users, Target, ExternalLink, Search, Filter, Calendar,
  Star, AlertTriangle, CheckCircle, Timer, Zap, Globe,
  ChevronDown, ArrowUpRight, Shield, Percent
} from 'lucide-react'

// Launchpad platforms
const PLATFORMS = [
  { id: 'binance', name: 'Binance Launchpad', color: '#F0B90B', type: 'CEX' },
  { id: 'coinlist', name: 'CoinList', color: '#0052FF', type: 'CEX' },
  { id: 'bybit', name: 'Bybit Launchpad', color: '#F7A600', type: 'CEX' },
  { id: 'kucoin', name: 'KuCoin Spotlight', color: '#23AF91', type: 'CEX' },
  { id: 'okx', name: 'OKX Jumpstart', color: '#FFFFFF', type: 'CEX' },
  { id: 'dao_maker', name: 'DAO Maker', color: '#00D395', type: 'DEX' },
  { id: 'seedify', name: 'Seedify', color: '#2ECC71', type: 'DEX' },
  { id: 'polkastarter', name: 'Polkastarter', color: '#FF6B6B', type: 'DEX' },
  { id: 'fjord', name: 'Fjord Foundry', color: '#6366F1', type: 'DEX' },
  { id: 'legion', name: 'Legion', color: '#8B5CF6', type: 'DEX' }
]

// Status types
const STATUS = {
  UPCOMING: { label: 'Upcoming', color: '#3b82f6', bg: 'bg-blue-500/20' },
  LIVE: { label: 'Live Now', color: '#22c55e', bg: 'bg-green-500/20' },
  ENDED: { label: 'Ended', color: '#6b7280', bg: 'bg-gray-500/20' },
  TGE_SOON: { label: 'TGE Soon', color: '#f59e0b', bg: 'bg-yellow-500/20' }
}

// Chains
const CHAINS = [
  { id: 'ethereum', name: 'Ethereum', color: '#627EEA' },
  { id: 'solana', name: 'Solana', color: '#14F195' },
  { id: 'arbitrum', name: 'Arbitrum', color: '#28A0F0' },
  { id: 'base', name: 'Base', color: '#0052FF' },
  { id: 'bsc', name: 'BNB Chain', color: '#F0B90B' },
  { id: 'polygon', name: 'Polygon', color: '#8247E5' }
]

// Generate launchpad projects
const generateProjects = () => {
  const categories = ['DeFi', 'Gaming', 'AI', 'Infrastructure', 'NFT', 'Social', 'L2', 'RWA']
  const statuses = Object.keys(STATUS)
  const projects = []

  const projectNames = [
    'NeuralChain AI', 'MetaVerse Prime', 'DeFi Protocol X', 'GameFi Universe',
    'ZK Layer', 'SocialFi Hub', 'Yield Aggregator Pro', 'NFT Marketplace 2.0',
    'Cross-Chain Bridge', 'AI Trading Bot', 'Real Estate Token', 'Carbon Credits',
    'Gaming Guild DAO', 'Decentralized Identity', 'Perpetual DEX', 'Liquid Staking'
  ]

  projectNames.forEach((name, i) => {
    const platform = PLATFORMS[Math.floor(Math.random() * PLATFORMS.length)]
    const chain = CHAINS[Math.floor(Math.random() * CHAINS.length)]
    const status = statuses[Math.floor(Math.random() * statuses.length)]
    const category = categories[Math.floor(Math.random() * categories.length)]
    const hardCap = Math.random() * 5000000 + 500000
    const raised = status === 'UPCOMING' ? 0 : status === 'LIVE' ? hardCap * (0.3 + Math.random() * 0.6) : hardCap
    const tokenPrice = Math.random() * 0.5 + 0.01
    const totalSupply = Math.floor(Math.random() * 1000000000 + 100000000)
    const fdv = tokenPrice * totalSupply
    const participants = Math.floor(Math.random() * 50000 + 1000)

    // Dates
    const now = Date.now()
    let saleStart, saleEnd, tgeDate
    if (status === 'UPCOMING') {
      saleStart = now + Math.random() * 7 * 86400000 + 86400000
      saleEnd = saleStart + Math.random() * 3 * 86400000 + 86400000
      tgeDate = saleEnd + Math.random() * 7 * 86400000
    } else if (status === 'LIVE') {
      saleStart = now - Math.random() * 2 * 86400000
      saleEnd = now + Math.random() * 2 * 86400000
      tgeDate = saleEnd + Math.random() * 7 * 86400000
    } else {
      saleStart = now - Math.random() * 30 * 86400000 - 7 * 86400000
      saleEnd = saleStart + Math.random() * 3 * 86400000 + 86400000
      tgeDate = saleEnd + Math.random() * 7 * 86400000
    }

    const roi = status === 'ENDED'
      ? (Math.random() > 0.3 ? Math.random() * 2000 + 100 : -(Math.random() * 50 + 10))
      : null

    projects.push({
      id: `project-${i}`,
      name,
      symbol: name.split(' ').map(w => w[0]).join('').toUpperCase().slice(0, 4),
      description: `${category} project building next-gen ${category.toLowerCase()} solutions`,
      platform,
      chain,
      status,
      statusData: STATUS[status],
      category,
      hardCap,
      raised,
      tokenPrice,
      totalSupply,
      fdv,
      participants,
      saleStart,
      saleEnd,
      tgeDate,
      roi,
      allocationPerUser: hardCap / participants,
      vestingSchedule: `${Math.floor(Math.random() * 20 + 10)}% TGE, ${Math.floor(Math.random() * 6 + 6)}mo linear`,
      requirements: platform.type === 'CEX'
        ? `Hold ${Math.floor(Math.random() * 500 + 100)} ${platform.name.split(' ')[0]} tokens`
        : `Stake ${Math.floor(Math.random() * 1000 + 100)} ${platform.name.split(' ')[0]} tokens`,
      socialScore: Math.floor(Math.random() * 100),
      auditScore: Math.floor(Math.random() * 40 + 60),
      teamScore: Math.floor(Math.random() * 40 + 60),
      isHot: Math.random() > 0.7,
      isFeatured: Math.random() > 0.8
    })
  })

  return projects.sort((a, b) => {
    const statusOrder = { LIVE: 0, UPCOMING: 1, TGE_SOON: 2, ENDED: 3 }
    return statusOrder[a.status] - statusOrder[b.status]
  })
}

// Generate performance stats
const generatePerformanceStats = () => {
  return PLATFORMS.map(platform => ({
    ...platform,
    totalProjects: Math.floor(Math.random() * 100 + 20),
    totalRaised: Math.random() * 500000000 + 50000000,
    avgROI: Math.random() * 500 + 100,
    successRate: Math.random() * 30 + 60,
    avgParticipants: Math.floor(Math.random() * 30000 + 5000)
  }))
}

export function LaunchpadTracker() {
  const [projects, setProjects] = useState([])
  const [platformStats, setPlatformStats] = useState([])
  const [selectedPlatform, setSelectedPlatform] = useState('all')
  const [selectedStatus, setSelectedStatus] = useState('all')
  const [selectedChain, setSelectedChain] = useState('all')
  const [viewMode, setViewMode] = useState('projects') // projects, calendar, performance
  const [searchQuery, setSearchQuery] = useState('')
  const [sortBy, setSortBy] = useState('status') // status, roi, raised

  // Initialize data
  useEffect(() => {
    setProjects(generateProjects())
    setPlatformStats(generatePerformanceStats())
  }, [])

  // Filter projects
  const filteredProjects = useMemo(() => {
    return projects.filter(p => {
      if (selectedPlatform !== 'all' && p.platform.id !== selectedPlatform) return false
      if (selectedStatus !== 'all' && p.status !== selectedStatus) return false
      if (selectedChain !== 'all' && p.chain.id !== selectedChain) return false
      if (searchQuery) {
        const query = searchQuery.toLowerCase()
        return p.name.toLowerCase().includes(query) ||
               p.symbol.toLowerCase().includes(query) ||
               p.category.toLowerCase().includes(query)
      }
      return true
    }).sort((a, b) => {
      switch (sortBy) {
        case 'roi': return (b.roi || 0) - (a.roi || 0)
        case 'raised': return b.raised - a.raised
        default: {
          const statusOrder = { LIVE: 0, UPCOMING: 1, TGE_SOON: 2, ENDED: 3 }
          return statusOrder[a.status] - statusOrder[b.status]
        }
      }
    })
  }, [projects, selectedPlatform, selectedStatus, selectedChain, searchQuery, sortBy])

  // Stats
  const stats = useMemo(() => {
    const live = projects.filter(p => p.status === 'LIVE').length
    const upcoming = projects.filter(p => p.status === 'UPCOMING').length
    const totalRaised = projects.reduce((sum, p) => sum + p.raised, 0)
    const avgROI = projects.filter(p => p.roi && p.roi > 0)
      .reduce((sum, p) => sum + p.roi, 0) / projects.filter(p => p.roi && p.roi > 0).length || 0

    return { live, upcoming, totalRaised, avgROI }
  }, [projects])

  const formatNumber = (num) => {
    if (num >= 1000000000) return `$${(num / 1000000000).toFixed(2)}B`
    if (num >= 1000000) return `$${(num / 1000000).toFixed(2)}M`
    if (num >= 1000) return `$${(num / 1000).toFixed(1)}K`
    return `$${num.toFixed(2)}`
  }

  const formatDate = (timestamp) => {
    return new Date(timestamp).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    })
  }

  const getTimeRemaining = (timestamp) => {
    const diff = timestamp - Date.now()
    if (diff < 0) return 'Ended'
    const days = Math.floor(diff / 86400000)
    const hours = Math.floor((diff % 86400000) / 3600000)
    if (days > 0) return `${days}d ${hours}h`
    const minutes = Math.floor((diff % 3600000) / 60000)
    return `${hours}h ${minutes}m`
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Rocket className="w-6 h-6 text-orange-400" />
          <h2 className="text-xl font-bold text-white">Launchpad Tracker</h2>
          <span className="px-2 py-0.5 bg-orange-500/20 text-orange-400 text-xs rounded-full">
            {projects.length} Projects
          </span>
        </div>

        <div className="flex items-center gap-2">
          <div className="flex bg-white/5 rounded-lg p-0.5">
            {['projects', 'calendar', 'performance'].map(mode => (
              <button
                key={mode}
                onClick={() => setViewMode(mode)}
                className={`px-3 py-1.5 text-xs rounded-md transition-all capitalize ${
                  viewMode === mode
                    ? 'bg-orange-500 text-white'
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
      <div className="grid grid-cols-4 gap-4">
        <div className="bg-white/5 rounded-xl p-4 border border-white/10">
          <div className="flex items-center gap-2 text-white/60 text-sm mb-2">
            <Zap className="w-4 h-4" />
            <span>Live Sales</span>
          </div>
          <div className="text-2xl font-bold text-green-400">{stats.live}</div>
        </div>

        <div className="bg-white/5 rounded-xl p-4 border border-white/10">
          <div className="flex items-center gap-2 text-white/60 text-sm mb-2">
            <Calendar className="w-4 h-4" />
            <span>Upcoming</span>
          </div>
          <div className="text-2xl font-bold text-blue-400">{stats.upcoming}</div>
        </div>

        <div className="bg-white/5 rounded-xl p-4 border border-white/10">
          <div className="flex items-center gap-2 text-white/60 text-sm mb-2">
            <DollarSign className="w-4 h-4" />
            <span>Total Raised</span>
          </div>
          <div className="text-2xl font-bold text-white">{formatNumber(stats.totalRaised)}</div>
        </div>

        <div className="bg-white/5 rounded-xl p-4 border border-white/10">
          <div className="flex items-center gap-2 text-white/60 text-sm mb-2">
            <TrendingUp className="w-4 h-4" />
            <span>Avg ROI</span>
          </div>
          <div className="text-2xl font-bold text-green-400">+{stats.avgROI.toFixed(0)}%</div>
        </div>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-4">
        <div className="flex-1 relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-white/40" />
          <input
            type="text"
            placeholder="Search projects..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-10 pr-4 py-2 bg-white/5 border border-white/10 rounded-lg text-white text-sm placeholder:text-white/40 focus:outline-none focus:border-orange-500"
          />
        </div>

        {/* Status filter */}
        <div className="flex items-center gap-2">
          <button
            onClick={() => setSelectedStatus('all')}
            className={`px-3 py-1.5 text-xs rounded-lg transition-all ${
              selectedStatus === 'all'
                ? 'bg-orange-500 text-white'
                : 'bg-white/5 text-white/60 hover:text-white'
            }`}
          >
            All
          </button>
          {Object.entries(STATUS).map(([key, value]) => (
            <button
              key={key}
              onClick={() => setSelectedStatus(key)}
              className={`px-3 py-1.5 text-xs rounded-lg transition-all ${
                selectedStatus === key
                  ? `${value.bg} text-white`
                  : 'bg-white/5 text-white/60 hover:text-white'
              }`}
              style={{ color: selectedStatus === key ? value.color : undefined }}
            >
              {value.label}
            </button>
          ))}
        </div>

        {/* Platform filter */}
        <select
          value={selectedPlatform}
          onChange={(e) => setSelectedPlatform(e.target.value)}
          className="px-3 py-1.5 bg-white/5 border border-white/10 rounded-lg text-white text-sm focus:outline-none"
        >
          <option value="all">All Platforms</option>
          {PLATFORMS.map(p => (
            <option key={p.id} value={p.id}>{p.name}</option>
          ))}
        </select>

        {/* Sort */}
        <select
          value={sortBy}
          onChange={(e) => setSortBy(e.target.value)}
          className="px-3 py-1.5 bg-white/5 border border-white/10 rounded-lg text-white text-sm focus:outline-none"
        >
          <option value="status">By Status</option>
          <option value="roi">By ROI</option>
          <option value="raised">By Raised</option>
        </select>
      </div>

      {/* Projects View */}
      {viewMode === 'projects' && (
        <div className="space-y-3">
          {filteredProjects.map(project => (
            <div
              key={project.id}
              className={`bg-white/5 rounded-xl p-4 border transition-all hover:border-white/30 ${
                project.status === 'LIVE' ? 'border-green-500/50' : 'border-white/10'
              }`}
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-4">
                  {/* Project info */}
                  <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-orange-500/20 to-purple-500/20 flex items-center justify-center">
                    <span className="text-lg font-bold text-white">{project.symbol.substring(0, 2)}</span>
                  </div>

                  <div>
                    <div className="flex items-center gap-2">
                      <span className="text-white font-medium">{project.name}</span>
                      <span className="text-white/40 text-sm">${project.symbol}</span>
                      {project.isHot && (
                        <span className="px-1.5 py-0.5 bg-red-500/20 text-red-400 text-xs rounded">
                          HOT
                        </span>
                      )}
                      {project.isFeatured && (
                        <Star className="w-4 h-4 text-yellow-400" />
                      )}
                    </div>
                    <div className="flex items-center gap-2 mt-1">
                      <span
                        className="px-2 py-0.5 text-xs rounded"
                        style={{
                          backgroundColor: `${project.statusData.color}20`,
                          color: project.statusData.color
                        }}
                      >
                        {project.statusData.label}
                      </span>
                      <span
                        className="text-xs"
                        style={{ color: project.platform.color }}
                      >
                        {project.platform.name}
                      </span>
                      <div
                        className="w-4 h-4 rounded flex items-center justify-center"
                        style={{ backgroundColor: `${project.chain.color}20` }}
                      >
                        <div
                          className="w-2 h-2 rounded-full"
                          style={{ backgroundColor: project.chain.color }}
                        />
                      </div>
                      <span className="text-white/40 text-xs">{project.category}</span>
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-6">
                  {/* Progress */}
                  {project.status !== 'UPCOMING' && (
                    <div className="w-32">
                      <div className="flex justify-between text-xs mb-1">
                        <span className="text-white/40">Raised</span>
                        <span className="text-white/60">
                          {((project.raised / project.hardCap) * 100).toFixed(0)}%
                        </span>
                      </div>
                      <div className="h-1.5 bg-white/10 rounded-full overflow-hidden">
                        <div
                          className="h-full bg-green-500 rounded-full"
                          style={{ width: `${(project.raised / project.hardCap) * 100}%` }}
                        />
                      </div>
                      <div className="text-xs text-white/40 mt-1">
                        {formatNumber(project.raised)} / {formatNumber(project.hardCap)}
                      </div>
                    </div>
                  )}

                  {/* Token price */}
                  <div className="text-right w-24">
                    <div className="text-white font-medium">${project.tokenPrice.toFixed(4)}</div>
                    <div className="text-white/40 text-xs">Token Price</div>
                  </div>

                  {/* FDV */}
                  <div className="text-right w-24">
                    <div className="text-white/80">{formatNumber(project.fdv)}</div>
                    <div className="text-white/40 text-xs">FDV</div>
                  </div>

                  {/* ROI or Time */}
                  {project.roi !== null ? (
                    <div className="text-right w-24">
                      <div className={`font-medium ${project.roi >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                        {project.roi >= 0 ? '+' : ''}{project.roi.toFixed(0)}%
                      </div>
                      <div className="text-white/40 text-xs">ATH ROI</div>
                    </div>
                  ) : (
                    <div className="text-right w-24">
                      <div className="text-cyan-400 font-medium">
                        {project.status === 'LIVE'
                          ? getTimeRemaining(project.saleEnd)
                          : getTimeRemaining(project.saleStart)
                        }
                      </div>
                      <div className="text-white/40 text-xs">
                        {project.status === 'LIVE' ? 'Ends in' : 'Starts in'}
                      </div>
                    </div>
                  )}

                  {/* Participants */}
                  <div className="text-center w-20">
                    <div className="text-white/80">{(project.participants / 1000).toFixed(1)}K</div>
                    <div className="text-white/40 text-xs">Users</div>
                  </div>

                  <a href="#" className="text-white/40 hover:text-white">
                    <ExternalLink className="w-4 h-4" />
                  </a>
                </div>
              </div>

              {/* Expanded info */}
              <div className="mt-3 pt-3 border-t border-white/10 flex items-center gap-6 text-xs">
                <div className="flex items-center gap-2">
                  <span className="text-white/40">Allocation:</span>
                  <span className="text-white/60">{formatNumber(project.allocationPerUser)}</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-white/40">Vesting:</span>
                  <span className="text-white/60">{project.vestingSchedule}</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-white/40">TGE:</span>
                  <span className="text-white/60">{formatDate(project.tgeDate)}</span>
                </div>
                <div className="flex items-center gap-2 ml-auto">
                  <Shield className="w-3 h-3 text-green-400" />
                  <span className="text-green-400">Audit: {project.auditScore}/100</span>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Calendar View */}
      {viewMode === 'calendar' && (
        <div className="space-y-4">
          {/* Upcoming this week */}
          <div className="bg-white/5 rounded-xl p-4 border border-white/10">
            <h3 className="text-white font-medium mb-4 flex items-center gap-2">
              <Calendar className="w-4 h-4 text-blue-400" />
              Upcoming This Week
            </h3>
            <div className="space-y-2">
              {projects.filter(p => p.status === 'UPCOMING' && p.saleStart - Date.now() < 7 * 86400000)
                .slice(0, 5).map(project => (
                  <div key={project.id} className="flex items-center justify-between p-3 bg-white/5 rounded-lg">
                    <div className="flex items-center gap-3">
                      <div className="w-8 h-8 rounded-lg bg-blue-500/20 flex items-center justify-center">
                        <span className="text-xs font-bold text-blue-400">{project.symbol.substring(0, 2)}</span>
                      </div>
                      <div>
                        <div className="text-white text-sm">{project.name}</div>
                        <div className="text-white/40 text-xs">{project.platform.name}</div>
                      </div>
                    </div>
                    <div className="text-right">
                      <div className="text-white text-sm">{formatDate(project.saleStart)}</div>
                      <div className="text-cyan-400 text-xs">{getTimeRemaining(project.saleStart)}</div>
                    </div>
                  </div>
                ))}
            </div>
          </div>

          {/* TGE This Week */}
          <div className="bg-white/5 rounded-xl p-4 border border-white/10">
            <h3 className="text-white font-medium mb-4 flex items-center gap-2">
              <Rocket className="w-4 h-4 text-orange-400" />
              TGE This Week
            </h3>
            <div className="space-y-2">
              {projects.filter(p => p.tgeDate - Date.now() < 7 * 86400000 && p.tgeDate > Date.now())
                .slice(0, 5).map(project => (
                  <div key={project.id} className="flex items-center justify-between p-3 bg-white/5 rounded-lg">
                    <div className="flex items-center gap-3">
                      <div className="w-8 h-8 rounded-lg bg-orange-500/20 flex items-center justify-center">
                        <span className="text-xs font-bold text-orange-400">{project.symbol.substring(0, 2)}</span>
                      </div>
                      <div>
                        <div className="text-white text-sm">{project.name}</div>
                        <div className="text-white/40 text-xs">${project.tokenPrice.toFixed(4)}</div>
                      </div>
                    </div>
                    <div className="text-right">
                      <div className="text-white text-sm">{formatDate(project.tgeDate)}</div>
                      <div className="text-orange-400 text-xs">{getTimeRemaining(project.tgeDate)}</div>
                    </div>
                  </div>
                ))}
            </div>
          </div>
        </div>
      )}

      {/* Performance View */}
      {viewMode === 'performance' && (
        <div className="grid grid-cols-2 gap-4">
          {platformStats.map(platform => (
            <div
              key={platform.id}
              className="bg-white/5 rounded-xl p-4 border border-white/10"
            >
              <div className="flex items-center gap-3 mb-4">
                <div
                  className="w-10 h-10 rounded-lg flex items-center justify-center"
                  style={{ backgroundColor: `${platform.color}20` }}
                >
                  <span className="text-xs font-bold" style={{ color: platform.color }}>
                    {platform.name.split(' ')[0].substring(0, 2).toUpperCase()}
                  </span>
                </div>
                <div>
                  <div className="text-white font-medium">{platform.name}</div>
                  <div className="text-white/40 text-xs">{platform.type} Launchpad</div>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <div className="text-white/40 text-xs mb-1">Projects</div>
                  <div className="text-white font-medium">{platform.totalProjects}</div>
                </div>
                <div>
                  <div className="text-white/40 text-xs mb-1">Total Raised</div>
                  <div className="text-white font-medium">{formatNumber(platform.totalRaised)}</div>
                </div>
                <div>
                  <div className="text-white/40 text-xs mb-1">Avg ROI</div>
                  <div className="text-green-400 font-medium">+{platform.avgROI.toFixed(0)}%</div>
                </div>
                <div>
                  <div className="text-white/40 text-xs mb-1">Success Rate</div>
                  <div className="text-cyan-400 font-medium">{platform.successRate.toFixed(0)}%</div>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

export default LaunchpadTracker
