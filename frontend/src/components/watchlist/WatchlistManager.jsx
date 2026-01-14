import React, { useState, useMemo, useEffect, useCallback } from 'react'
import {
  Star, Plus, Search, Filter, Trash2, Edit3, Copy, Download, Upload,
  TrendingUp, TrendingDown, Bell, BellOff, Tag, FolderPlus, ChevronDown,
  MoreVertical, Eye, EyeOff, ArrowUpDown, Grid, List, Settings,
  AlertTriangle, Check, X, RefreshCw, Share2, Clock, Target
} from 'lucide-react'

const SUPPORTED_TOKENS = [
  { symbol: 'BTC', name: 'Bitcoin', category: 'Layer 1' },
  { symbol: 'ETH', name: 'Ethereum', category: 'Layer 1' },
  { symbol: 'SOL', name: 'Solana', category: 'Layer 1' },
  { symbol: 'BNB', name: 'BNB Chain', category: 'Layer 1' },
  { symbol: 'XRP', name: 'Ripple', category: 'Payments' },
  { symbol: 'ADA', name: 'Cardano', category: 'Layer 1' },
  { symbol: 'AVAX', name: 'Avalanche', category: 'Layer 1' },
  { symbol: 'DOT', name: 'Polkadot', category: 'Layer 0' },
  { symbol: 'MATIC', name: 'Polygon', category: 'Layer 2' },
  { symbol: 'LINK', name: 'Chainlink', category: 'Oracle' },
  { symbol: 'UNI', name: 'Uniswap', category: 'DeFi' },
  { symbol: 'AAVE', name: 'Aave', category: 'DeFi' },
  { symbol: 'LDO', name: 'Lido DAO', category: 'DeFi' },
  { symbol: 'ARB', name: 'Arbitrum', category: 'Layer 2' },
  { symbol: 'OP', name: 'Optimism', category: 'Layer 2' },
  { symbol: 'ATOM', name: 'Cosmos', category: 'Layer 0' },
  { symbol: 'FTM', name: 'Fantom', category: 'Layer 1' },
  { symbol: 'NEAR', name: 'NEAR Protocol', category: 'Layer 1' },
  { symbol: 'INJ', name: 'Injective', category: 'DeFi' },
  { symbol: 'APT', name: 'Aptos', category: 'Layer 1' },
  { symbol: 'SUI', name: 'Sui', category: 'Layer 1' },
  { symbol: 'SEI', name: 'Sei', category: 'Layer 1' },
  { symbol: 'DOGE', name: 'Dogecoin', category: 'Meme' },
  { symbol: 'SHIB', name: 'Shiba Inu', category: 'Meme' },
  { symbol: 'PEPE', name: 'Pepe', category: 'Meme' },
  { symbol: 'WIF', name: 'dogwifhat', category: 'Meme' },
  { symbol: 'BONK', name: 'Bonk', category: 'Meme' },
  { symbol: 'MKR', name: 'Maker', category: 'DeFi' },
  { symbol: 'CRV', name: 'Curve', category: 'DeFi' },
  { symbol: 'SNX', name: 'Synthetix', category: 'DeFi' }
]

const CATEGORIES = ['All', 'Layer 1', 'Layer 2', 'Layer 0', 'DeFi', 'Oracle', 'Payments', 'Meme']

const SORT_OPTIONS = [
  { value: 'name', label: 'Name' },
  { value: 'price', label: 'Price' },
  { value: 'change24h', label: '24h Change' },
  { value: 'change7d', label: '7d Change' },
  { value: 'volume', label: 'Volume' },
  { value: 'marketCap', label: 'Market Cap' },
  { value: 'dateAdded', label: 'Date Added' }
]

export function WatchlistManager() {
  const [watchlists, setWatchlists] = useState([
    { id: 1, name: 'Main Portfolio', color: '#3b82f6', tokens: ['BTC', 'ETH', 'SOL', 'LINK', 'AAVE'], isDefault: true },
    { id: 2, name: 'DeFi Gems', color: '#10b981', tokens: ['UNI', 'AAVE', 'CRV', 'MKR', 'LDO'], isDefault: false },
    { id: 3, name: 'Layer 2 Plays', color: '#8b5cf6', tokens: ['ARB', 'OP', 'MATIC'], isDefault: false },
    { id: 4, name: 'Meme Watch', color: '#f59e0b', tokens: ['DOGE', 'SHIB', 'PEPE', 'WIF', 'BONK'], isDefault: false }
  ])

  const [selectedWatchlist, setSelectedWatchlist] = useState(1)
  const [tokenPrices, setTokenPrices] = useState({})
  const [searchQuery, setSearchQuery] = useState('')
  const [categoryFilter, setCategoryFilter] = useState('All')
  const [sortBy, setSortBy] = useState('name')
  const [sortOrder, setSortOrder] = useState('asc')
  const [viewMode, setViewMode] = useState('list')
  const [showAddToken, setShowAddToken] = useState(false)
  const [showCreateList, setShowCreateList] = useState(false)
  const [newListName, setNewListName] = useState('')
  const [newListColor, setNewListColor] = useState('#3b82f6')
  const [tokenAlerts, setTokenAlerts] = useState({})
  const [tokenNotes, setTokenNotes] = useState({})
  const [editingNote, setEditingNote] = useState(null)
  const [noteText, setNoteText] = useState('')

  // Generate mock prices
  useEffect(() => {
    const generatePrices = () => {
      const prices = {}
      const basePrices = {
        BTC: 67500, ETH: 3450, SOL: 145, BNB: 580, XRP: 0.52,
        ADA: 0.45, AVAX: 35, DOT: 7.2, MATIC: 0.72, LINK: 14.5,
        UNI: 9.8, AAVE: 168, LDO: 2.1, ARB: 1.15, OP: 2.45,
        ATOM: 8.9, FTM: 0.68, NEAR: 5.2, INJ: 24, APT: 9.5,
        SUI: 1.35, SEI: 0.42, DOGE: 0.12, SHIB: 0.000022, PEPE: 0.0000095,
        WIF: 2.45, BONK: 0.000028, MKR: 2850, CRV: 0.52, SNX: 2.8
      }

      SUPPORTED_TOKENS.forEach(token => {
        const base = basePrices[token.symbol] || 1
        const change24h = (Math.random() - 0.5) * 20
        const change7d = (Math.random() - 0.5) * 40
        prices[token.symbol] = {
          price: base * (1 + (Math.random() - 0.5) * 0.02),
          change24h,
          change7d,
          volume24h: base * 1000000 * (Math.random() * 10 + 1),
          marketCap: base * 1000000000 * (Math.random() * 0.5 + 0.5),
          high24h: base * 1.05,
          low24h: base * 0.95,
          ath: base * 1.5,
          athDate: '2024-03-14'
        }
      })
      setTokenPrices(prices)
    }

    generatePrices()
    const interval = setInterval(generatePrices, 10000)
    return () => clearInterval(interval)
  }, [])

  const currentWatchlist = useMemo(() => {
    return watchlists.find(w => w.id === selectedWatchlist)
  }, [watchlists, selectedWatchlist])

  const watchlistTokens = useMemo(() => {
    if (!currentWatchlist) return []

    let tokens = currentWatchlist.tokens.map(symbol => {
      const tokenInfo = SUPPORTED_TOKENS.find(t => t.symbol === symbol)
      const priceData = tokenPrices[symbol] || {}
      return {
        ...tokenInfo,
        ...priceData,
        hasAlert: tokenAlerts[symbol],
        note: tokenNotes[symbol],
        dateAdded: new Date(Date.now() - Math.random() * 30 * 24 * 60 * 60 * 1000)
      }
    })

    // Filter by category
    if (categoryFilter !== 'All') {
      tokens = tokens.filter(t => t.category === categoryFilter)
    }

    // Filter by search
    if (searchQuery) {
      tokens = tokens.filter(t =>
        t.symbol.toLowerCase().includes(searchQuery.toLowerCase()) ||
        t.name.toLowerCase().includes(searchQuery.toLowerCase())
      )
    }

    // Sort
    tokens.sort((a, b) => {
      let comparison = 0
      switch (sortBy) {
        case 'name':
          comparison = a.name.localeCompare(b.name)
          break
        case 'price':
          comparison = (a.price || 0) - (b.price || 0)
          break
        case 'change24h':
          comparison = (a.change24h || 0) - (b.change24h || 0)
          break
        case 'change7d':
          comparison = (a.change7d || 0) - (b.change7d || 0)
          break
        case 'volume':
          comparison = (a.volume24h || 0) - (b.volume24h || 0)
          break
        case 'marketCap':
          comparison = (a.marketCap || 0) - (b.marketCap || 0)
          break
        case 'dateAdded':
          comparison = a.dateAdded - b.dateAdded
          break
        default:
          comparison = 0
      }
      return sortOrder === 'asc' ? comparison : -comparison
    })

    return tokens
  }, [currentWatchlist, tokenPrices, categoryFilter, searchQuery, sortBy, sortOrder, tokenAlerts, tokenNotes])

  const availableTokens = useMemo(() => {
    if (!currentWatchlist) return SUPPORTED_TOKENS
    return SUPPORTED_TOKENS.filter(t => !currentWatchlist.tokens.includes(t.symbol))
  }, [currentWatchlist])

  const formatPrice = (price) => {
    if (!price) return '$0.00'
    if (price < 0.0001) return `$${price.toFixed(8)}`
    if (price < 1) return `$${price.toFixed(4)}`
    if (price < 100) return `$${price.toFixed(2)}`
    return `$${price.toLocaleString(undefined, { maximumFractionDigits: 0 })}`
  }

  const formatVolume = (vol) => {
    if (!vol) return '$0'
    if (vol >= 1e9) return `$${(vol / 1e9).toFixed(2)}B`
    if (vol >= 1e6) return `$${(vol / 1e6).toFixed(2)}M`
    return `$${vol.toLocaleString()}`
  }

  const addTokenToWatchlist = (symbol) => {
    setWatchlists(prev => prev.map(w => {
      if (w.id === selectedWatchlist && !w.tokens.includes(symbol)) {
        return { ...w, tokens: [...w.tokens, symbol] }
      }
      return w
    }))
    setShowAddToken(false)
  }

  const removeTokenFromWatchlist = (symbol) => {
    setWatchlists(prev => prev.map(w => {
      if (w.id === selectedWatchlist) {
        return { ...w, tokens: w.tokens.filter(t => t !== symbol) }
      }
      return w
    }))
  }

  const createWatchlist = () => {
    if (!newListName.trim()) return
    const newId = Math.max(...watchlists.map(w => w.id)) + 1
    setWatchlists(prev => [...prev, {
      id: newId,
      name: newListName,
      color: newListColor,
      tokens: [],
      isDefault: false
    }])
    setSelectedWatchlist(newId)
    setNewListName('')
    setShowCreateList(false)
  }

  const deleteWatchlist = (id) => {
    if (watchlists.length <= 1) return
    const listToDelete = watchlists.find(w => w.id === id)
    if (listToDelete?.isDefault) return

    setWatchlists(prev => prev.filter(w => w.id !== id))
    if (selectedWatchlist === id) {
      setSelectedWatchlist(watchlists[0].id)
    }
  }

  const toggleAlert = (symbol) => {
    setTokenAlerts(prev => ({
      ...prev,
      [symbol]: !prev[symbol]
    }))
  }

  const saveNote = (symbol) => {
    setTokenNotes(prev => ({
      ...prev,
      [symbol]: noteText
    }))
    setEditingNote(null)
    setNoteText('')
  }

  const exportWatchlist = () => {
    const data = {
      name: currentWatchlist?.name,
      tokens: currentWatchlist?.tokens,
      exportDate: new Date().toISOString()
    }
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${currentWatchlist?.name || 'watchlist'}.json`
    a.click()
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Star className="w-6 h-6 text-yellow-400" />
          <h2 className="text-xl font-bold">Watchlist Manager</h2>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={exportWatchlist}
            className="px-3 py-2 bg-white/5 rounded-lg hover:bg-white/10 transition flex items-center gap-2"
          >
            <Download className="w-4 h-4" />
            Export
          </button>
          <button
            onClick={() => setShowCreateList(true)}
            className="px-4 py-2 bg-blue-500/20 text-blue-400 rounded-lg hover:bg-blue-500/30 transition flex items-center gap-2"
          >
            <FolderPlus className="w-4 h-4" />
            New List
          </button>
        </div>
      </div>

      {/* Watchlist Tabs */}
      <div className="flex items-center gap-2 overflow-x-auto pb-2">
        {watchlists.map(list => (
          <button
            key={list.id}
            onClick={() => setSelectedWatchlist(list.id)}
            className={`px-4 py-2 rounded-lg transition flex items-center gap-2 whitespace-nowrap ${
              selectedWatchlist === list.id
                ? 'bg-white/10 border border-white/20'
                : 'bg-white/5 hover:bg-white/10'
            }`}
          >
            <div
              className="w-3 h-3 rounded-full"
              style={{ backgroundColor: list.color }}
            />
            <span>{list.name}</span>
            <span className="text-white/40 text-sm">({list.tokens.length})</span>
            {!list.isDefault && selectedWatchlist === list.id && (
              <button
                onClick={(e) => {
                  e.stopPropagation()
                  deleteWatchlist(list.id)
                }}
                className="ml-1 p-1 hover:bg-white/10 rounded"
              >
                <X className="w-3 h-3" />
              </button>
            )}
          </button>
        ))}
      </div>

      {/* Controls */}
      <div className="flex flex-wrap items-center gap-4">
        <div className="flex-1 min-w-[200px] relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-white/40" />
          <input
            type="text"
            placeholder="Search tokens..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-10 pr-4 py-2 bg-white/5 border border-white/10 rounded-lg focus:outline-none focus:border-white/20"
          />
        </div>

        <select
          value={categoryFilter}
          onChange={(e) => setCategoryFilter(e.target.value)}
          className="px-4 py-2 bg-white/5 border border-white/10 rounded-lg focus:outline-none"
        >
          {CATEGORIES.map(cat => (
            <option key={cat} value={cat} className="bg-[#0a0e14]">{cat}</option>
          ))}
        </select>

        <div className="flex items-center gap-2">
          <select
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value)}
            className="px-4 py-2 bg-white/5 border border-white/10 rounded-lg focus:outline-none"
          >
            {SORT_OPTIONS.map(opt => (
              <option key={opt.value} value={opt.value} className="bg-[#0a0e14]">{opt.label}</option>
            ))}
          </select>
          <button
            onClick={() => setSortOrder(prev => prev === 'asc' ? 'desc' : 'asc')}
            className="p-2 bg-white/5 rounded-lg hover:bg-white/10 transition"
          >
            <ArrowUpDown className="w-4 h-4" />
          </button>
        </div>

        <div className="flex items-center gap-1 bg-white/5 rounded-lg p-1">
          <button
            onClick={() => setViewMode('list')}
            className={`p-2 rounded ${viewMode === 'list' ? 'bg-white/10' : 'hover:bg-white/10'}`}
          >
            <List className="w-4 h-4" />
          </button>
          <button
            onClick={() => setViewMode('grid')}
            className={`p-2 rounded ${viewMode === 'grid' ? 'bg-white/10' : 'hover:bg-white/10'}`}
          >
            <Grid className="w-4 h-4" />
          </button>
        </div>

        <button
          onClick={() => setShowAddToken(true)}
          className="px-4 py-2 bg-green-500/20 text-green-400 rounded-lg hover:bg-green-500/30 transition flex items-center gap-2"
        >
          <Plus className="w-4 h-4" />
          Add Token
        </button>
      </div>

      {/* Token List */}
      {viewMode === 'list' ? (
        <div className="bg-white/5 border border-white/10 rounded-xl overflow-hidden">
          <table className="w-full">
            <thead>
              <tr className="border-b border-white/10 text-left text-sm text-white/60">
                <th className="px-4 py-3">Token</th>
                <th className="px-4 py-3">Price</th>
                <th className="px-4 py-3">24h</th>
                <th className="px-4 py-3">7d</th>
                <th className="px-4 py-3">Volume</th>
                <th className="px-4 py-3">Market Cap</th>
                <th className="px-4 py-3">24h Range</th>
                <th className="px-4 py-3">Actions</th>
              </tr>
            </thead>
            <tbody>
              {watchlistTokens.map((token, idx) => (
                <tr key={token.symbol} className="border-b border-white/5 hover:bg-white/5">
                  <td className="px-4 py-4">
                    <div className="flex items-center gap-3">
                      <div className="w-8 h-8 rounded-full bg-gradient-to-br from-blue-500 to-purple-500 flex items-center justify-center text-xs font-bold">
                        {token.symbol.slice(0, 2)}
                      </div>
                      <div>
                        <div className="font-medium">{token.symbol}</div>
                        <div className="text-sm text-white/40">{token.name}</div>
                      </div>
                      {token.note && (
                        <div className="ml-2 text-yellow-400" title={token.note}>
                          <Edit3 className="w-3 h-3" />
                        </div>
                      )}
                    </div>
                  </td>
                  <td className="px-4 py-4 font-mono">{formatPrice(token.price)}</td>
                  <td className={`px-4 py-4 ${token.change24h >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                    <div className="flex items-center gap-1">
                      {token.change24h >= 0 ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
                      {Math.abs(token.change24h || 0).toFixed(2)}%
                    </div>
                  </td>
                  <td className={`px-4 py-4 ${token.change7d >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                    {token.change7d >= 0 ? '+' : ''}{(token.change7d || 0).toFixed(2)}%
                  </td>
                  <td className="px-4 py-4 text-white/60">{formatVolume(token.volume24h)}</td>
                  <td className="px-4 py-4 text-white/60">{formatVolume(token.marketCap)}</td>
                  <td className="px-4 py-4">
                    <div className="text-xs text-white/40">
                      {formatPrice(token.low24h)} - {formatPrice(token.high24h)}
                    </div>
                  </td>
                  <td className="px-4 py-4">
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => toggleAlert(token.symbol)}
                        className={`p-2 rounded-lg transition ${
                          token.hasAlert ? 'bg-yellow-500/20 text-yellow-400' : 'hover:bg-white/10'
                        }`}
                        title={token.hasAlert ? 'Disable alerts' : 'Enable alerts'}
                      >
                        {token.hasAlert ? <Bell className="w-4 h-4" /> : <BellOff className="w-4 h-4 text-white/40" />}
                      </button>
                      <button
                        onClick={() => {
                          setEditingNote(token.symbol)
                          setNoteText(token.note || '')
                        }}
                        className="p-2 rounded-lg hover:bg-white/10 transition"
                        title="Add note"
                      >
                        <Edit3 className="w-4 h-4 text-white/40" />
                      </button>
                      <button
                        onClick={() => removeTokenFromWatchlist(token.symbol)}
                        className="p-2 rounded-lg hover:bg-red-500/20 hover:text-red-400 transition"
                        title="Remove"
                      >
                        <Trash2 className="w-4 h-4 text-white/40" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          {watchlistTokens.length === 0 && (
            <div className="text-center py-12 text-white/40">
              <Star className="w-12 h-12 mx-auto mb-4 opacity-50" />
              <p>No tokens in this watchlist</p>
              <button
                onClick={() => setShowAddToken(true)}
                className="mt-4 px-4 py-2 bg-blue-500/20 text-blue-400 rounded-lg hover:bg-blue-500/30 transition"
              >
                Add Your First Token
              </button>
            </div>
          )}
        </div>
      ) : (
        /* Grid View */
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {watchlistTokens.map(token => (
            <div
              key={token.symbol}
              className="bg-white/5 border border-white/10 rounded-xl p-4 hover:bg-white/[0.07] transition"
            >
              <div className="flex items-start justify-between mb-4">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-full bg-gradient-to-br from-blue-500 to-purple-500 flex items-center justify-center text-sm font-bold">
                    {token.symbol.slice(0, 2)}
                  </div>
                  <div>
                    <div className="font-medium">{token.symbol}</div>
                    <div className="text-sm text-white/40">{token.name}</div>
                  </div>
                </div>
                <div className="flex items-center gap-1">
                  <button
                    onClick={() => toggleAlert(token.symbol)}
                    className={`p-1 rounded ${token.hasAlert ? 'text-yellow-400' : 'text-white/40'}`}
                  >
                    <Bell className="w-4 h-4" />
                  </button>
                  <button
                    onClick={() => removeTokenFromWatchlist(token.symbol)}
                    className="p-1 rounded text-white/40 hover:text-red-400"
                  >
                    <X className="w-4 h-4" />
                  </button>
                </div>
              </div>

              <div className="text-2xl font-bold mb-2">{formatPrice(token.price)}</div>

              <div className="flex items-center gap-4 mb-4">
                <div className={`flex items-center gap-1 ${token.change24h >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                  {token.change24h >= 0 ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
                  <span className="text-sm">{Math.abs(token.change24h || 0).toFixed(2)}% (24h)</span>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-2 text-sm">
                <div className="bg-white/5 rounded-lg p-2">
                  <div className="text-white/40">Volume</div>
                  <div className="font-medium">{formatVolume(token.volume24h)}</div>
                </div>
                <div className="bg-white/5 rounded-lg p-2">
                  <div className="text-white/40">MCap</div>
                  <div className="font-medium">{formatVolume(token.marketCap)}</div>
                </div>
              </div>

              {token.note && (
                <div className="mt-3 p-2 bg-yellow-500/10 border border-yellow-500/20 rounded-lg text-xs text-yellow-200">
                  {token.note}
                </div>
              )}
            </div>
          ))}

          {watchlistTokens.length === 0 && (
            <div className="col-span-full text-center py-12 text-white/40">
              <Star className="w-12 h-12 mx-auto mb-4 opacity-50" />
              <p>No tokens in this watchlist</p>
            </div>
          )}
        </div>
      )}

      {/* Watchlist Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-white/5 border border-white/10 rounded-xl p-4">
          <div className="text-white/60 text-sm mb-1">Total Tokens</div>
          <div className="text-2xl font-bold">{currentWatchlist?.tokens.length || 0}</div>
        </div>
        <div className="bg-white/5 border border-white/10 rounded-xl p-4">
          <div className="text-white/60 text-sm mb-1">Gainers (24h)</div>
          <div className="text-2xl font-bold text-green-400">
            {watchlistTokens.filter(t => (t.change24h || 0) > 0).length}
          </div>
        </div>
        <div className="bg-white/5 border border-white/10 rounded-xl p-4">
          <div className="text-white/60 text-sm mb-1">Losers (24h)</div>
          <div className="text-2xl font-bold text-red-400">
            {watchlistTokens.filter(t => (t.change24h || 0) < 0).length}
          </div>
        </div>
        <div className="bg-white/5 border border-white/10 rounded-xl p-4">
          <div className="text-white/60 text-sm mb-1">Alerts Active</div>
          <div className="text-2xl font-bold text-yellow-400">
            {Object.values(tokenAlerts).filter(Boolean).length}
          </div>
        </div>
      </div>

      {/* Add Token Modal */}
      {showAddToken && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-[#0a0e14] border border-white/10 rounded-xl p-6 w-full max-w-lg max-h-[80vh] overflow-y-auto">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-bold">Add Token to {currentWatchlist?.name}</h3>
              <button onClick={() => setShowAddToken(false)} className="p-2 hover:bg-white/10 rounded-lg">
                <X className="w-5 h-5" />
              </button>
            </div>

            <input
              type="text"
              placeholder="Search tokens..."
              className="w-full px-4 py-2 bg-white/5 border border-white/10 rounded-lg mb-4 focus:outline-none"
            />

            <div className="space-y-2">
              {availableTokens.map(token => (
                <button
                  key={token.symbol}
                  onClick={() => addTokenToWatchlist(token.symbol)}
                  className="w-full flex items-center justify-between p-3 bg-white/5 rounded-lg hover:bg-white/10 transition"
                >
                  <div className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded-full bg-gradient-to-br from-blue-500 to-purple-500 flex items-center justify-center text-xs font-bold">
                      {token.symbol.slice(0, 2)}
                    </div>
                    <div className="text-left">
                      <div className="font-medium">{token.symbol}</div>
                      <div className="text-sm text-white/40">{token.name}</div>
                    </div>
                  </div>
                  <div className="text-sm text-white/40">{token.category}</div>
                </button>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Create Watchlist Modal */}
      {showCreateList && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-[#0a0e14] border border-white/10 rounded-xl p-6 w-full max-w-md">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-bold">Create New Watchlist</h3>
              <button onClick={() => setShowCreateList(false)} className="p-2 hover:bg-white/10 rounded-lg">
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="space-y-4">
              <div>
                <label className="block text-sm text-white/60 mb-2">List Name</label>
                <input
                  type="text"
                  value={newListName}
                  onChange={(e) => setNewListName(e.target.value)}
                  placeholder="My Watchlist"
                  className="w-full px-4 py-2 bg-white/5 border border-white/10 rounded-lg focus:outline-none"
                />
              </div>

              <div>
                <label className="block text-sm text-white/60 mb-2">Color</label>
                <div className="flex items-center gap-2">
                  {['#3b82f6', '#10b981', '#8b5cf6', '#f59e0b', '#ef4444', '#ec4899'].map(color => (
                    <button
                      key={color}
                      onClick={() => setNewListColor(color)}
                      className={`w-8 h-8 rounded-full transition ${
                        newListColor === color ? 'ring-2 ring-white ring-offset-2 ring-offset-[#0a0e14]' : ''
                      }`}
                      style={{ backgroundColor: color }}
                    />
                  ))}
                </div>
              </div>

              <button
                onClick={createWatchlist}
                disabled={!newListName.trim()}
                className="w-full py-3 bg-blue-500 text-white rounded-lg hover:bg-blue-600 transition disabled:opacity-50"
              >
                Create Watchlist
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Note Editor Modal */}
      {editingNote && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-[#0a0e14] border border-white/10 rounded-xl p-6 w-full max-w-md">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-bold">Note for {editingNote}</h3>
              <button onClick={() => setEditingNote(null)} className="p-2 hover:bg-white/10 rounded-lg">
                <X className="w-5 h-5" />
              </button>
            </div>

            <textarea
              value={noteText}
              onChange={(e) => setNoteText(e.target.value)}
              placeholder="Add your notes..."
              className="w-full h-32 px-4 py-2 bg-white/5 border border-white/10 rounded-lg focus:outline-none resize-none"
            />

            <div className="flex justify-end gap-2 mt-4">
              <button
                onClick={() => setEditingNote(null)}
                className="px-4 py-2 bg-white/5 rounded-lg hover:bg-white/10 transition"
              >
                Cancel
              </button>
              <button
                onClick={() => saveNote(editingNote)}
                className="px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 transition"
              >
                Save Note
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default WatchlistManager
