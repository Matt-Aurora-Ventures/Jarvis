import React, { useState, useEffect, useMemo, useCallback } from 'react'
import {
  Image,
  Grid,
  List,
  DollarSign,
  TrendingUp,
  TrendingDown,
  Clock,
  Tag,
  ExternalLink,
  RefreshCw,
  Filter,
  Search,
  ChevronDown,
  ChevronUp,
  Star,
  StarOff,
  Eye,
  EyeOff,
  Layers,
  Gem,
  Crown,
  Sparkles,
  BarChart3,
  PieChart,
  ArrowUpRight,
  ArrowDownRight,
  Package,
  ShoppingCart,
  Gavel,
  Send,
  AlertCircle,
  CheckCircle,
  XCircle,
  Info,
  Wallet,
  Activity,
  Calendar,
  Hash,
  Percent
} from 'lucide-react'

// NFT Marketplaces
const MARKETPLACES = {
  MAGIC_EDEN: { name: 'Magic Eden', color: '#e42575', url: 'https://magiceden.io' },
  TENSOR: { name: 'Tensor', color: '#14f195', url: 'https://tensor.trade' },
  SOLANART: { name: 'Solanart', color: '#fc8621', url: 'https://solanart.io' },
  OPENSEA: { name: 'OpenSea', color: '#2081e2', url: 'https://opensea.io' },
}

// Rarity tiers
const RARITY_TIERS = {
  LEGENDARY: { label: 'Legendary', color: '#fbbf24', icon: Crown, percentile: 1 },
  EPIC: { label: 'Epic', color: '#a855f7', icon: Gem, percentile: 5 },
  RARE: { label: 'Rare', color: '#3b82f6', icon: Sparkles, percentile: 15 },
  UNCOMMON: { label: 'Uncommon', color: '#22c55e', icon: Star, percentile: 35 },
  COMMON: { label: 'Common', color: '#6b7280', icon: null, percentile: 100 },
}

// Get rarity tier from rank percentage
function getRarityTier(rankPercent) {
  if (rankPercent <= 1) return 'LEGENDARY'
  if (rankPercent <= 5) return 'EPIC'
  if (rankPercent <= 15) return 'RARE'
  if (rankPercent <= 35) return 'UNCOMMON'
  return 'COMMON'
}

// Format SOL price
function formatSol(amount) {
  if (!amount) return '-'
  if (amount >= 1000) return `${(amount / 1000).toFixed(2)}K`
  return amount.toFixed(2)
}

// Format number with commas
function formatNumber(num) {
  return new Intl.NumberFormat().format(num)
}

// Rarity Badge Component
function RarityBadge({ rank, total, size = 'md' }) {
  const rankPercent = (rank / total) * 100
  const tier = getRarityTier(rankPercent)
  const rarityInfo = RARITY_TIERS[tier]
  const Icon = rarityInfo.icon

  const sizeClasses = {
    sm: 'px-1.5 py-0.5 text-xs',
    md: 'px-2 py-1 text-sm',
    lg: 'px-3 py-1.5 text-base',
  }

  return (
    <span
      className={`inline-flex items-center gap-1 rounded-md font-medium ${sizeClasses[size]}`}
      style={{ backgroundColor: `${rarityInfo.color}20`, color: rarityInfo.color }}
    >
      {Icon && <Icon className="w-3 h-3" />}
      #{rank}
    </span>
  )
}

// NFT Card Component
function NFTCard({ nft, viewMode, onSelect, onList, onTransfer, isFavorite, onToggleFavorite }) {
  const [showDetails, setShowDetails] = useState(false)
  const rankPercent = nft.rank && nft.totalSupply
    ? (nft.rank / nft.totalSupply) * 100
    : null
  const tier = rankPercent ? getRarityTier(rankPercent) : null
  const rarityInfo = tier ? RARITY_TIERS[tier] : null

  const pnl = nft.estimatedValue && nft.purchasePrice
    ? ((nft.estimatedValue - nft.purchasePrice) / nft.purchasePrice) * 100
    : null

  if (viewMode === 'list') {
    return (
      <div
        className="bg-gray-800 rounded-lg border border-gray-700 hover:border-gray-600 transition-colors p-3 flex items-center gap-4 cursor-pointer"
        onClick={() => onSelect?.(nft)}
      >
        {/* Thumbnail */}
        <div className="w-16 h-16 rounded-lg overflow-hidden bg-gray-900 flex-shrink-0">
          {nft.image ? (
            <img src={nft.image} alt={nft.name} className="w-full h-full object-cover" />
          ) : (
            <div className="w-full h-full flex items-center justify-center text-gray-600">
              <Image className="w-6 h-6" />
            </div>
          )}
        </div>

        {/* Info */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <h3 className="font-semibold truncate">{nft.name}</h3>
            {rarityInfo && <RarityBadge rank={nft.rank} total={nft.totalSupply} size="sm" />}
          </div>
          <div className="text-sm text-gray-400">{nft.collection}</div>
        </div>

        {/* Estimated Value */}
        <div className="text-right">
          <div className="font-semibold">{formatSol(nft.estimatedValue)} SOL</div>
          {pnl !== null && (
            <div className={`text-sm flex items-center justify-end gap-1 ${
              pnl >= 0 ? 'text-green-400' : 'text-red-400'
            }`}>
              {pnl >= 0 ? <ArrowUpRight className="w-3 h-3" /> : <ArrowDownRight className="w-3 h-3" />}
              {Math.abs(pnl).toFixed(1)}%
            </div>
          )}
        </div>

        {/* Actions */}
        <div className="flex items-center gap-2">
          <button
            onClick={e => { e.stopPropagation(); onToggleFavorite?.(nft.mint) }}
            className="p-2 text-gray-400 hover:text-yellow-400 transition-colors"
          >
            {isFavorite ? (
              <Star className="w-4 h-4 fill-yellow-400 text-yellow-400" />
            ) : (
              <StarOff className="w-4 h-4" />
            )}
          </button>
        </div>
      </div>
    )
  }

  // Grid view
  return (
    <div
      className="bg-gray-800 rounded-xl border border-gray-700 overflow-hidden hover:border-gray-600 transition-all hover:shadow-lg group"
      style={rarityInfo ? { borderColor: `${rarityInfo.color}30` } : {}}
    >
      {/* Image Container */}
      <div className="relative aspect-square bg-gray-900">
        {nft.image ? (
          <img src={nft.image} alt={nft.name} className="w-full h-full object-cover" />
        ) : (
          <div className="w-full h-full flex items-center justify-center text-gray-600">
            <Image className="w-16 h-16" />
          </div>
        )}

        {/* Hover Overlay */}
        <div className="absolute inset-0 bg-black/60 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center gap-2">
          <button
            onClick={() => onSelect?.(nft)}
            className="p-2 bg-white/20 rounded-lg hover:bg-white/30 transition-colors"
          >
            <Eye className="w-5 h-5" />
          </button>
          <button
            onClick={() => onList?.(nft)}
            className="p-2 bg-purple-500/80 rounded-lg hover:bg-purple-500 transition-colors"
          >
            <Tag className="w-5 h-5" />
          </button>
          <button
            onClick={() => onTransfer?.(nft)}
            className="p-2 bg-blue-500/80 rounded-lg hover:bg-blue-500 transition-colors"
          >
            <Send className="w-5 h-5" />
          </button>
        </div>

        {/* Rarity Badge */}
        {rarityInfo && (
          <div
            className="absolute top-2 left-2 px-2 py-1 rounded-md text-xs font-bold flex items-center gap-1"
            style={{ backgroundColor: rarityInfo.color, color: '#000' }}
          >
            {rarityInfo.icon && <rarityInfo.icon className="w-3 h-3" />}
            {rarityInfo.label}
          </div>
        )}

        {/* Favorite Button */}
        <button
          onClick={e => { e.stopPropagation(); onToggleFavorite?.(nft.mint) }}
          className="absolute top-2 right-2 p-1.5 bg-black/50 rounded-full hover:bg-black/70 transition-colors"
        >
          {isFavorite ? (
            <Star className="w-4 h-4 fill-yellow-400 text-yellow-400" />
          ) : (
            <StarOff className="w-4 h-4 text-white/70" />
          )}
        </button>

        {/* Listed Badge */}
        {nft.listed && (
          <div className="absolute bottom-2 right-2 px-2 py-1 bg-green-500 rounded text-xs font-bold">
            Listed
          </div>
        )}
      </div>

      {/* Info */}
      <div className="p-3">
        <div className="flex items-start justify-between mb-2">
          <div className="min-w-0">
            <h3 className="font-semibold truncate">{nft.name}</h3>
            <div className="text-xs text-gray-400 truncate">{nft.collection}</div>
          </div>
          {nft.rank && (
            <RarityBadge rank={nft.rank} total={nft.totalSupply} size="sm" />
          )}
        </div>

        {/* Price Info */}
        <div className="flex items-center justify-between">
          <div>
            <div className="text-xs text-gray-500">Est. Value</div>
            <div className="font-bold">{formatSol(nft.estimatedValue)} SOL</div>
          </div>
          {pnl !== null && (
            <div className={`text-right ${pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
              <div className="text-xs opacity-70">P&L</div>
              <div className="font-medium flex items-center gap-1">
                {pnl >= 0 ? <ArrowUpRight className="w-3 h-3" /> : <ArrowDownRight className="w-3 h-3" />}
                {Math.abs(pnl).toFixed(1)}%
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

// NFT Details Modal
function NFTDetailsModal({ nft, isOpen, onClose, onList, onTransfer }) {
  if (!isOpen || !nft) return null

  const rankPercent = nft.rank && nft.totalSupply
    ? (nft.rank / nft.totalSupply) * 100
    : null
  const tier = rankPercent ? getRarityTier(rankPercent) : null
  const rarityInfo = tier ? RARITY_TIERS[tier] : null

  return (
    <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50 p-4">
      <div className="bg-gray-800 rounded-xl max-w-4xl w-full max-h-[90vh] overflow-y-auto border border-gray-700">
        <div className="grid md:grid-cols-2 gap-6 p-6">
          {/* Image */}
          <div>
            <div className="aspect-square rounded-xl overflow-hidden bg-gray-900">
              {nft.image ? (
                <img src={nft.image} alt={nft.name} className="w-full h-full object-cover" />
              ) : (
                <div className="w-full h-full flex items-center justify-center text-gray-600">
                  <Image className="w-24 h-24" />
                </div>
              )}
            </div>

            {/* Actions */}
            <div className="flex gap-2 mt-4">
              <button
                onClick={() => onList?.(nft)}
                className="flex-1 py-2 bg-purple-500 text-white rounded-lg hover:bg-purple-600 transition-colors flex items-center justify-center gap-2"
              >
                <Tag className="w-4 h-4" />
                List for Sale
              </button>
              <button
                onClick={() => onTransfer?.(nft)}
                className="flex-1 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 transition-colors flex items-center justify-center gap-2"
              >
                <Send className="w-4 h-4" />
                Transfer
              </button>
            </div>
          </div>

          {/* Details */}
          <div>
            <div className="flex justify-between items-start mb-4">
              <div>
                <h2 className="text-2xl font-bold">{nft.name}</h2>
                <div className="text-gray-400">{nft.collection}</div>
              </div>
              <button onClick={onClose} className="text-gray-400 hover:text-white">
                <XCircle className="w-6 h-6" />
              </button>
            </div>

            {/* Rarity */}
            {rarityInfo && (
              <div
                className="p-4 rounded-lg mb-4"
                style={{ backgroundColor: `${rarityInfo.color}15` }}
              >
                <div className="flex items-center gap-3">
                  {rarityInfo.icon && (
                    <rarityInfo.icon className="w-8 h-8" style={{ color: rarityInfo.color }} />
                  )}
                  <div>
                    <div className="text-sm text-gray-400">Rarity Rank</div>
                    <div className="text-xl font-bold" style={{ color: rarityInfo.color }}>
                      #{nft.rank} / {formatNumber(nft.totalSupply)}
                    </div>
                    <div className="text-sm text-gray-400">Top {rankPercent.toFixed(1)}%</div>
                  </div>
                </div>
              </div>
            )}

            {/* Price Info */}
            <div className="grid grid-cols-2 gap-4 mb-4">
              <div className="bg-gray-900 rounded-lg p-3">
                <div className="text-xs text-gray-500 mb-1">Estimated Value</div>
                <div className="text-xl font-bold">{formatSol(nft.estimatedValue)} SOL</div>
              </div>
              <div className="bg-gray-900 rounded-lg p-3">
                <div className="text-xs text-gray-500 mb-1">Purchase Price</div>
                <div className="text-xl font-bold">{formatSol(nft.purchasePrice)} SOL</div>
              </div>
              <div className="bg-gray-900 rounded-lg p-3">
                <div className="text-xs text-gray-500 mb-1">Floor Price</div>
                <div className="text-xl font-bold">{formatSol(nft.floorPrice)} SOL</div>
              </div>
              <div className="bg-gray-900 rounded-lg p-3">
                <div className="text-xs text-gray-500 mb-1">Last Sale</div>
                <div className="text-xl font-bold">{formatSol(nft.lastSale)} SOL</div>
              </div>
            </div>

            {/* Attributes */}
            {nft.attributes && nft.attributes.length > 0 && (
              <div className="mb-4">
                <div className="text-sm text-gray-400 mb-2">Attributes</div>
                <div className="grid grid-cols-2 gap-2">
                  {nft.attributes.map((attr, i) => (
                    <div key={i} className="bg-gray-900 rounded-lg p-2">
                      <div className="text-xs text-gray-500">{attr.trait_type}</div>
                      <div className="font-medium">{attr.value}</div>
                      {attr.rarity && (
                        <div className="text-xs text-purple-400">{attr.rarity}% have this</div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* External Links */}
            <div className="flex gap-2">
              {Object.entries(MARKETPLACES).map(([key, marketplace]) => (
                <a
                  key={key}
                  href={`${marketplace.url}/item/${nft.mint}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex-1 py-2 text-sm text-gray-400 hover:text-white border border-gray-700 rounded-lg flex items-center justify-center gap-1 hover:border-gray-600 transition-colors"
                >
                  {marketplace.name} <ExternalLink className="w-3 h-3" />
                </a>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

// Portfolio Summary Component
function PortfolioSummary({ nfts, solPrice = 0 }) {
  const stats = useMemo(() => {
    const totalValue = nfts.reduce((sum, n) => sum + (n.estimatedValue || 0), 0)
    const totalCost = nfts.reduce((sum, n) => sum + (n.purchasePrice || 0), 0)
    const unrealizedPnL = totalValue - totalCost
    const pnlPercent = totalCost > 0 ? (unrealizedPnL / totalCost) * 100 : 0

    // Group by collection
    const collections = {}
    nfts.forEach(nft => {
      if (!collections[nft.collection]) {
        collections[nft.collection] = { count: 0, value: 0 }
      }
      collections[nft.collection].count++
      collections[nft.collection].value += nft.estimatedValue || 0
    })

    const topCollections = Object.entries(collections)
      .sort((a, b) => b[1].value - a[1].value)
      .slice(0, 5)

    return {
      totalNFTs: nfts.length,
      totalValue,
      totalValueUSD: totalValue * solPrice,
      unrealizedPnL,
      pnlPercent,
      listedCount: nfts.filter(n => n.listed).length,
      topCollections,
    }
  }, [nfts, solPrice])

  return (
    <div className="bg-gradient-to-r from-purple-900/30 to-pink-900/30 rounded-xl p-6 border border-purple-500/20">
      <div className="flex items-center gap-2 mb-4">
        <Package className="w-5 h-5 text-purple-400" />
        <h2 className="text-lg font-semibold">NFT Portfolio</h2>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-5 gap-6">
        <div>
          <div className="text-sm text-gray-400 mb-1">Total NFTs</div>
          <div className="text-2xl font-bold">{stats.totalNFTs}</div>
          {stats.listedCount > 0 && (
            <div className="text-sm text-green-400">{stats.listedCount} listed</div>
          )}
        </div>
        <div>
          <div className="text-sm text-gray-400 mb-1">Portfolio Value</div>
          <div className="text-2xl font-bold">{formatSol(stats.totalValue)} SOL</div>
          <div className="text-sm text-gray-500">${formatNumber(Math.round(stats.totalValueUSD))}</div>
        </div>
        <div>
          <div className="text-sm text-gray-400 mb-1">Unrealized P&L</div>
          <div className={`text-2xl font-bold ${stats.unrealizedPnL >= 0 ? 'text-green-400' : 'text-red-400'}`}>
            {stats.unrealizedPnL >= 0 ? '+' : ''}{formatSol(stats.unrealizedPnL)} SOL
          </div>
          <div className={`text-sm flex items-center gap-1 ${stats.pnlPercent >= 0 ? 'text-green-400' : 'text-red-400'}`}>
            {stats.pnlPercent >= 0 ? <ArrowUpRight className="w-3 h-3" /> : <ArrowDownRight className="w-3 h-3" />}
            {Math.abs(stats.pnlPercent).toFixed(1)}%
          </div>
        </div>
        <div className="col-span-2">
          <div className="text-sm text-gray-400 mb-2">Top Collections</div>
          <div className="flex flex-wrap gap-2">
            {stats.topCollections.map(([name, data], i) => (
              <div key={name} className="px-2 py-1 bg-gray-800 rounded text-sm">
                {name} <span className="text-gray-400">({data.count})</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}

// Collection Filter Card
function CollectionFilter({ collections, selected, onSelect }) {
  return (
    <div className="flex flex-wrap gap-2">
      <button
        onClick={() => onSelect('all')}
        className={`px-3 py-1.5 rounded-lg text-sm ${
          selected === 'all'
            ? 'bg-purple-500/20 text-purple-400 border border-purple-500/50'
            : 'bg-gray-800 text-gray-400 border border-gray-700 hover:border-gray-600'
        }`}
      >
        All ({collections.reduce((sum, c) => sum + c.count, 0)})
      </button>
      {collections.map(collection => (
        <button
          key={collection.name}
          onClick={() => onSelect(collection.name)}
          className={`px-3 py-1.5 rounded-lg text-sm flex items-center gap-2 ${
            selected === collection.name
              ? 'bg-purple-500/20 text-purple-400 border border-purple-500/50'
              : 'bg-gray-800 text-gray-400 border border-gray-700 hover:border-gray-600'
          }`}
        >
          {collection.image && (
            <img src={collection.image} alt="" className="w-5 h-5 rounded" />
          )}
          {collection.name} ({collection.count})
        </button>
      ))}
    </div>
  )
}

// Main NFT Portfolio Component
export function NFTPortfolio({
  nfts = [],
  solPrice = 0,
  onRefresh,
  onList,
  onTransfer,
  isLoading = false
}) {
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedCollection, setSelectedCollection] = useState('all')
  const [selectedRarity, setSelectedRarity] = useState('all')
  const [sortBy, setSortBy] = useState('value')
  const [sortOrder, setSortOrder] = useState('desc')
  const [viewMode, setViewMode] = useState('grid')
  const [favorites, setFavorites] = useState(new Set())
  const [showFavoritesOnly, setShowFavoritesOnly] = useState(false)
  const [selectedNFT, setSelectedNFT] = useState(null)
  const [showListedOnly, setShowListedOnly] = useState(false)

  // Get unique collections with counts
  const collections = useMemo(() => {
    const collectionMap = {}
    nfts.forEach(nft => {
      if (!collectionMap[nft.collection]) {
        collectionMap[nft.collection] = { name: nft.collection, count: 0, image: nft.collectionImage }
      }
      collectionMap[nft.collection].count++
    })
    return Object.values(collectionMap).sort((a, b) => b.count - a.count)
  }, [nfts])

  // Filter and sort NFTs
  const filteredNFTs = useMemo(() => {
    let result = [...nfts]

    // Search filter
    if (searchQuery) {
      const query = searchQuery.toLowerCase()
      result = result.filter(n =>
        n.name.toLowerCase().includes(query) ||
        n.collection.toLowerCase().includes(query)
      )
    }

    // Collection filter
    if (selectedCollection !== 'all') {
      result = result.filter(n => n.collection === selectedCollection)
    }

    // Rarity filter
    if (selectedRarity !== 'all') {
      result = result.filter(n => {
        if (!n.rank || !n.totalSupply) return false
        const rankPercent = (n.rank / n.totalSupply) * 100
        return getRarityTier(rankPercent) === selectedRarity
      })
    }

    // Favorites filter
    if (showFavoritesOnly) {
      result = result.filter(n => favorites.has(n.mint))
    }

    // Listed filter
    if (showListedOnly) {
      result = result.filter(n => n.listed)
    }

    // Sort
    result.sort((a, b) => {
      let comparison = 0
      switch (sortBy) {
        case 'value': comparison = (a.estimatedValue || 0) - (b.estimatedValue || 0); break
        case 'rank': comparison = (a.rank || 9999) - (b.rank || 9999); break
        case 'name': comparison = a.name.localeCompare(b.name); break
        case 'recent': comparison = new Date(a.acquiredAt || 0) - new Date(b.acquiredAt || 0); break
        default: comparison = 0
      }
      return sortOrder === 'desc' ? -comparison : comparison
    })

    return result
  }, [nfts, searchQuery, selectedCollection, selectedRarity, sortBy, sortOrder, showFavoritesOnly, favorites, showListedOnly])

  const toggleFavorite = useCallback((mint) => {
    setFavorites(prev => {
      const newFavs = new Set(prev)
      if (newFavs.has(mint)) {
        newFavs.delete(mint)
      } else {
        newFavs.add(mint)
      }
      return newFavs
    })
  }, [])

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-purple-500/20 rounded-lg">
            <Package className="w-6 h-6 text-purple-400" />
          </div>
          <div>
            <h1 className="text-2xl font-bold">NFT Portfolio</h1>
            <p className="text-sm text-gray-400">Track and manage your NFT collection</p>
          </div>
        </div>
        <button
          onClick={onRefresh}
          disabled={isLoading}
          className="px-4 py-2 bg-gray-700 text-gray-300 rounded-lg hover:bg-gray-600 transition-colors flex items-center gap-2"
        >
          <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
          Refresh
        </button>
      </div>

      {/* Portfolio Summary */}
      <PortfolioSummary nfts={nfts} solPrice={solPrice} />

      {/* Collection Filter */}
      {collections.length > 1 && (
        <CollectionFilter
          collections={collections}
          selected={selectedCollection}
          onSelect={setSelectedCollection}
        />
      )}

      {/* Filters */}
      <div className="bg-gray-800 rounded-xl p-4 border border-gray-700">
        <div className="flex flex-col md:flex-row gap-4">
          {/* Search */}
          <div className="flex-1 relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
            <input
              type="text"
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              placeholder="Search NFTs..."
              className="w-full pl-10 pr-4 py-2 bg-gray-900 border border-gray-700 rounded-lg"
            />
          </div>

          {/* Rarity Filter */}
          <select
            value={selectedRarity}
            onChange={e => setSelectedRarity(e.target.value)}
            className="px-3 py-2 bg-gray-900 border border-gray-700 rounded-lg"
          >
            <option value="all">All Rarities</option>
            {Object.entries(RARITY_TIERS).map(([key, { label }]) => (
              <option key={key} value={key}>{label}</option>
            ))}
          </select>

          {/* Sort */}
          <select
            value={sortBy}
            onChange={e => setSortBy(e.target.value)}
            className="px-3 py-2 bg-gray-900 border border-gray-700 rounded-lg"
          >
            <option value="value">Value</option>
            <option value="rank">Rarity Rank</option>
            <option value="name">Name</option>
            <option value="recent">Recently Acquired</option>
          </select>

          <button
            onClick={() => setSortOrder(o => o === 'desc' ? 'asc' : 'desc')}
            className="p-2 bg-gray-700 rounded-lg"
          >
            {sortOrder === 'desc' ? <ChevronDown className="w-5 h-5" /> : <ChevronUp className="w-5 h-5" />}
          </button>
        </div>

        {/* View Options */}
        <div className="flex items-center justify-between mt-4 pt-4 border-t border-gray-700">
          <div className="flex items-center gap-2">
            <button
              onClick={() => setShowFavoritesOnly(!showFavoritesOnly)}
              className={`flex items-center gap-1 px-2 py-1 rounded text-sm ${
                showFavoritesOnly ? 'bg-yellow-500/20 text-yellow-400' : 'bg-gray-700 text-gray-400'
              }`}
            >
              <Star className="w-4 h-4" />
              Favorites
            </button>
            <button
              onClick={() => setShowListedOnly(!showListedOnly)}
              className={`flex items-center gap-1 px-2 py-1 rounded text-sm ${
                showListedOnly ? 'bg-green-500/20 text-green-400' : 'bg-gray-700 text-gray-400'
              }`}
            >
              <Tag className="w-4 h-4" />
              Listed
            </button>
          </div>

          <div className="flex items-center gap-2">
            <span className="text-sm text-gray-400">{filteredNFTs.length} NFTs</span>
            <div className="flex bg-gray-700 rounded-lg p-1">
              <button
                onClick={() => setViewMode('grid')}
                className={`p-1.5 rounded ${viewMode === 'grid' ? 'bg-gray-600 text-white' : 'text-gray-400'}`}
              >
                <Grid className="w-4 h-4" />
              </button>
              <button
                onClick={() => setViewMode('list')}
                className={`p-1.5 rounded ${viewMode === 'list' ? 'bg-gray-600 text-white' : 'text-gray-400'}`}
              >
                <List className="w-4 h-4" />
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* NFT Grid/List */}
      {viewMode === 'grid' ? (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-4">
          {filteredNFTs.map(nft => (
            <NFTCard
              key={nft.mint}
              nft={nft}
              viewMode={viewMode}
              onSelect={setSelectedNFT}
              onList={onList}
              onTransfer={onTransfer}
              isFavorite={favorites.has(nft.mint)}
              onToggleFavorite={toggleFavorite}
            />
          ))}
        </div>
      ) : (
        <div className="space-y-2">
          {filteredNFTs.map(nft => (
            <NFTCard
              key={nft.mint}
              nft={nft}
              viewMode={viewMode}
              onSelect={setSelectedNFT}
              onList={onList}
              onTransfer={onTransfer}
              isFavorite={favorites.has(nft.mint)}
              onToggleFavorite={toggleFavorite}
            />
          ))}
        </div>
      )}

      {filteredNFTs.length === 0 && (
        <div className="text-center py-12 text-gray-400">
          <Package className="w-12 h-12 mx-auto mb-4 opacity-50" />
          <p>No NFTs found matching your criteria</p>
        </div>
      )}

      {/* Details Modal */}
      <NFTDetailsModal
        nft={selectedNFT}
        isOpen={!!selectedNFT}
        onClose={() => setSelectedNFT(null)}
        onList={onList}
        onTransfer={onTransfer}
      />
    </div>
  )
}

export default NFTPortfolio
