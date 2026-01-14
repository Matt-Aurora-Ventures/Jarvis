import React, { useState, useMemo, useCallback } from 'react'
import {
  Newspaper, RefreshCw, ExternalLink, Clock, TrendingUp, TrendingDown,
  MessageSquare, Share2, Bookmark, BookmarkCheck, Filter, Search,
  ChevronDown, ChevronUp, Flame, Zap, AlertTriangle, Bell, BellOff,
  Twitter, Globe, Radio, Hash, Star, Eye, ArrowUpRight, Sparkles
} from 'lucide-react'

// News sources
const SOURCES = {
  COINDESK: { name: 'CoinDesk', color: '#0066FF', trusted: true },
  COINTELEGRAPH: { name: 'Cointelegraph', color: '#7B3FE4', trusted: true },
  THEBLOCK: { name: 'The Block', color: '#FF6B35', trusted: true },
  DECRYPT: { name: 'Decrypt', color: '#00D4AA', trusted: true },
  DEFIANT: { name: 'The Defiant', color: '#F7931A', trusted: true },
  BLOCKWORKS: { name: 'Blockworks', color: '#8B5CF6', trusted: true },
  DLNEWS: { name: 'DL News', color: '#3B82F6', trusted: true },
  TWITTER: { name: 'X/Twitter', color: '#1DA1F2', trusted: false },
  REDDIT: { name: 'Reddit', color: '#FF4500', trusted: false }
}

// Categories
const CATEGORIES = {
  ALL: { label: 'All News', icon: Newspaper },
  BREAKING: { label: 'Breaking', icon: Zap },
  MARKET: { label: 'Market', icon: TrendingUp },
  DEFI: { label: 'DeFi', icon: Globe },
  NFT: { label: 'NFTs', icon: Sparkles },
  REGULATION: { label: 'Regulation', icon: AlertTriangle },
  TECHNOLOGY: { label: 'Technology', icon: Radio },
  SOCIAL: { label: 'Social', icon: Twitter }
}

// Sentiment types
const SENTIMENT = {
  BULLISH: { label: 'Bullish', color: 'text-green-400', bg: 'bg-green-500/20' },
  BEARISH: { label: 'Bearish', color: 'text-red-400', bg: 'bg-red-500/20' },
  NEUTRAL: { label: 'Neutral', color: 'text-gray-400', bg: 'bg-gray-500/20' }
}

// Mock news data
const MOCK_NEWS = [
  {
    id: '1',
    title: 'Bitcoin Surges Past $98,000 as ETF Inflows Hit Record High',
    summary: 'Spot Bitcoin ETFs saw over $1.2 billion in net inflows yesterday, pushing BTC to new all-time highs. Institutional demand shows no signs of slowing.',
    source: 'COINDESK',
    category: 'MARKET',
    sentiment: 'BULLISH',
    timestamp: Date.now() - 1000 * 60 * 15, // 15 min ago
    url: '#',
    image: null,
    tags: ['Bitcoin', 'ETF', 'ATH'],
    engagement: { views: 45200, comments: 328, shares: 1250 },
    isBreaking: true,
    relatedTokens: ['BTC']
  },
  {
    id: '2',
    title: 'SEC Delays Decision on Solana ETF Applications',
    summary: 'The Securities and Exchange Commission has pushed back its ruling on multiple Solana ETF applications, citing need for additional review period.',
    source: 'THEBLOCK',
    category: 'REGULATION',
    sentiment: 'BEARISH',
    timestamp: Date.now() - 1000 * 60 * 45, // 45 min ago
    url: '#',
    image: null,
    tags: ['SEC', 'Solana', 'ETF', 'Regulation'],
    engagement: { views: 28500, comments: 195, shares: 820 },
    isBreaking: false,
    relatedTokens: ['SOL']
  },
  {
    id: '3',
    title: 'Jupiter DEX Announces Major V4 Protocol Upgrade',
    summary: 'Jupiter Exchange reveals comprehensive V4 upgrade including limit orders, DCA improvements, and new perpetuals features launching next month.',
    source: 'DECRYPT',
    category: 'DEFI',
    sentiment: 'BULLISH',
    timestamp: Date.now() - 1000 * 60 * 90, // 1.5h ago
    url: '#',
    image: null,
    tags: ['Jupiter', 'DEX', 'Solana', 'DeFi'],
    engagement: { views: 18900, comments: 142, shares: 560 },
    isBreaking: false,
    relatedTokens: ['JUP', 'SOL']
  },
  {
    id: '4',
    title: 'Ethereum Layer 2 TVL Reaches $50 Billion Milestone',
    summary: 'Combined total value locked across Ethereum L2 networks hits historic $50B mark, with Arbitrum and Base leading growth.',
    source: 'DEFIANT',
    category: 'DEFI',
    sentiment: 'BULLISH',
    timestamp: Date.now() - 1000 * 60 * 120, // 2h ago
    url: '#',
    image: null,
    tags: ['Ethereum', 'L2', 'TVL', 'Arbitrum', 'Base'],
    engagement: { views: 22100, comments: 98, shares: 445 },
    isBreaking: false,
    relatedTokens: ['ETH', 'ARB']
  },
  {
    id: '5',
    title: 'Major Whale Accumulates 500M PEPE Tokens',
    summary: 'On-chain data reveals a whale wallet has accumulated over 500 million PEPE tokens in the past 24 hours amid rising memecoin activity.',
    source: 'TWITTER',
    category: 'SOCIAL',
    sentiment: 'BULLISH',
    timestamp: Date.now() - 1000 * 60 * 180, // 3h ago
    url: '#',
    image: null,
    tags: ['PEPE', 'Whale', 'Memecoin'],
    engagement: { views: 35600, comments: 412, shares: 890 },
    isBreaking: false,
    relatedTokens: ['PEPE']
  },
  {
    id: '6',
    title: 'US Treasury Proposes New Crypto Tax Reporting Rules',
    summary: 'New proposed regulations would require all crypto exchanges to report user transactions above $600 to the IRS starting 2026.',
    source: 'COINTELEGRAPH',
    category: 'REGULATION',
    sentiment: 'BEARISH',
    timestamp: Date.now() - 1000 * 60 * 240, // 4h ago
    url: '#',
    image: null,
    tags: ['Regulation', 'Tax', 'Treasury', 'IRS'],
    engagement: { views: 41200, comments: 567, shares: 1120 },
    isBreaking: false,
    relatedTokens: []
  },
  {
    id: '7',
    title: 'Raydium Launches Concentrated Liquidity V3 Pools',
    summary: 'Solana DEX Raydium introduces concentrated liquidity pools with up to 4000x capital efficiency improvements for liquidity providers.',
    source: 'BLOCKWORKS',
    category: 'DEFI',
    sentiment: 'BULLISH',
    timestamp: Date.now() - 1000 * 60 * 300, // 5h ago
    url: '#',
    image: null,
    tags: ['Raydium', 'Solana', 'DeFi', 'Liquidity'],
    engagement: { views: 12800, comments: 86, shares: 320 },
    isBreaking: false,
    relatedTokens: ['RAY', 'SOL']
  },
  {
    id: '8',
    title: 'OpenAI Partners with Blockchain Project for AI Verification',
    summary: 'OpenAI announces partnership with decentralized identity protocol to verify AI-generated content using blockchain technology.',
    source: 'DLNEWS',
    category: 'TECHNOLOGY',
    sentiment: 'NEUTRAL',
    timestamp: Date.now() - 1000 * 60 * 360, // 6h ago
    url: '#',
    image: null,
    tags: ['AI', 'OpenAI', 'Blockchain', 'Technology'],
    engagement: { views: 28900, comments: 234, shares: 780 },
    isBreaking: false,
    relatedTokens: []
  },
  {
    id: '9',
    title: 'Pudgy Penguins Floor Price Hits New ATH',
    summary: 'Pudgy Penguins NFT collection reaches 25 ETH floor price, becoming the second highest-valued PFP collection after CryptoPunks.',
    source: 'COINDESK',
    category: 'NFT',
    sentiment: 'BULLISH',
    timestamp: Date.now() - 1000 * 60 * 420, // 7h ago
    url: '#',
    image: null,
    tags: ['NFT', 'Pudgy Penguins', 'Ethereum'],
    engagement: { views: 19500, comments: 178, shares: 520 },
    isBreaking: false,
    relatedTokens: ['ETH', 'PENGU']
  },
  {
    id: '10',
    title: 'FTX Creditors to Receive 118% Recovery in Restructuring',
    summary: 'Bankrupt crypto exchange FTX announces creditors will receive full principal plus 18% interest in approved restructuring plan.',
    source: 'THEBLOCK',
    category: 'MARKET',
    sentiment: 'BULLISH',
    timestamp: Date.now() - 1000 * 60 * 480, // 8h ago
    url: '#',
    image: null,
    tags: ['FTX', 'Bankruptcy', 'Recovery'],
    engagement: { views: 52300, comments: 623, shares: 1450 },
    isBreaking: false,
    relatedTokens: []
  }
]

// Format time ago
const formatTimeAgo = (timestamp) => {
  const diff = Date.now() - timestamp
  const minutes = Math.floor(diff / (1000 * 60))
  const hours = Math.floor(diff / (1000 * 60 * 60))
  const days = Math.floor(diff / (1000 * 60 * 60 * 24))

  if (minutes < 60) return `${minutes}m ago`
  if (hours < 24) return `${hours}h ago`
  return `${days}d ago`
}

// Source badge
const SourceBadge = ({ source }) => {
  const sourceData = SOURCES[source]
  return (
    <div
      className="flex items-center gap-1.5 px-2 py-1 rounded text-xs font-medium"
      style={{ backgroundColor: `${sourceData.color}20`, color: sourceData.color }}
    >
      {sourceData.trusted && <Star className="w-3 h-3" />}
      {sourceData.name}
    </div>
  )
}

// Sentiment badge
const SentimentBadge = ({ sentiment }) => {
  const data = SENTIMENT[sentiment]
  return (
    <span className={`px-2 py-0.5 rounded text-xs font-medium ${data.bg} ${data.color}`}>
      {data.label}
    </span>
  )
}

// News card component
const NewsCard = ({ article, isCompact, onBookmark, bookmarked }) => {
  const [expanded, setExpanded] = useState(false)

  if (isCompact) {
    return (
      <div className="flex items-start gap-3 p-3 bg-white/5 hover:bg-white/[0.07] rounded-lg transition-colors cursor-pointer">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <SourceBadge source={article.source} />
            <span className="text-xs text-gray-500">{formatTimeAgo(article.timestamp)}</span>
            {article.isBreaking && (
              <span className="px-1.5 py-0.5 bg-red-500/20 text-red-400 text-xs font-medium rounded animate-pulse">
                BREAKING
              </span>
            )}
          </div>
          <h3 className="font-medium text-sm line-clamp-2">{article.title}</h3>
        </div>
        <SentimentBadge sentiment={article.sentiment} />
      </div>
    )
  }

  return (
    <div className="bg-white/5 rounded-xl border border-white/10 overflow-hidden hover:border-white/20 transition-colors">
      <div className="p-4">
        {/* Header */}
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <SourceBadge source={article.source} />
            <span className="text-xs text-gray-500 flex items-center gap-1">
              <Clock className="w-3 h-3" />
              {formatTimeAgo(article.timestamp)}
            </span>
            {article.isBreaking && (
              <span className="px-2 py-0.5 bg-red-500/20 text-red-400 text-xs font-bold rounded animate-pulse flex items-center gap-1">
                <Zap className="w-3 h-3" />
                BREAKING
              </span>
            )}
          </div>
          <div className="flex items-center gap-2">
            <SentimentBadge sentiment={article.sentiment} />
            <button
              onClick={() => onBookmark(article.id)}
              className={`p-1.5 rounded-lg transition-colors ${
                bookmarked ? 'text-yellow-400 bg-yellow-500/20' : 'text-gray-500 hover:text-white hover:bg-white/10'
              }`}
            >
              {bookmarked ? <BookmarkCheck className="w-4 h-4" /> : <Bookmark className="w-4 h-4" />}
            </button>
          </div>
        </div>

        {/* Title & Summary */}
        <h2 className="text-lg font-semibold mb-2 hover:text-blue-400 cursor-pointer">
          {article.title}
        </h2>
        <p className={`text-gray-400 text-sm ${expanded ? '' : 'line-clamp-2'}`}>
          {article.summary}
        </p>

        {article.summary.length > 150 && (
          <button
            onClick={() => setExpanded(!expanded)}
            className="text-blue-400 text-sm mt-1 hover:underline"
          >
            {expanded ? 'Show less' : 'Read more'}
          </button>
        )}

        {/* Tags */}
        <div className="flex flex-wrap gap-2 mt-3">
          {article.tags.map((tag, idx) => (
            <span
              key={idx}
              className="px-2 py-0.5 bg-white/10 rounded text-xs text-gray-400 hover:bg-white/20 cursor-pointer"
            >
              #{tag}
            </span>
          ))}
        </div>

        {/* Related tokens */}
        {article.relatedTokens.length > 0 && (
          <div className="flex items-center gap-2 mt-3 pt-3 border-t border-white/10">
            <span className="text-xs text-gray-500">Related:</span>
            {article.relatedTokens.map((token, idx) => (
              <span
                key={idx}
                className="px-2 py-0.5 bg-blue-500/20 text-blue-400 rounded text-xs font-medium"
              >
                ${token}
              </span>
            ))}
          </div>
        )}

        {/* Engagement */}
        <div className="flex items-center justify-between mt-4 pt-3 border-t border-white/10">
          <div className="flex items-center gap-4 text-xs text-gray-500">
            <span className="flex items-center gap-1">
              <Eye className="w-4 h-4" />
              {(article.engagement.views / 1000).toFixed(1)}K
            </span>
            <span className="flex items-center gap-1">
              <MessageSquare className="w-4 h-4" />
              {article.engagement.comments}
            </span>
            <span className="flex items-center gap-1">
              <Share2 className="w-4 h-4" />
              {article.engagement.shares}
            </span>
          </div>

          <a
            href={article.url}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-1 text-sm text-blue-400 hover:text-blue-300"
          >
            Read full article
            <ExternalLink className="w-4 h-4" />
          </a>
        </div>
      </div>
    </div>
  )
}

// Trending topics
const TrendingTopics = ({ news }) => {
  const topics = useMemo(() => {
    const tagCounts = {}
    news.forEach(article => {
      article.tags.forEach(tag => {
        tagCounts[tag] = (tagCounts[tag] || 0) + 1
      })
    })

    return Object.entries(tagCounts)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 10)
      .map(([tag, count]) => ({ tag, count }))
  }, [news])

  return (
    <div className="bg-white/5 rounded-xl p-4 border border-white/10">
      <h3 className="text-sm font-medium text-gray-300 mb-4 flex items-center gap-2">
        <Flame className="w-4 h-4 text-orange-400" />
        Trending Topics
      </h3>

      <div className="space-y-2">
        {topics.map(({ tag, count }, idx) => (
          <div
            key={tag}
            className="flex items-center justify-between p-2 hover:bg-white/5 rounded-lg cursor-pointer transition-colors"
          >
            <div className="flex items-center gap-2">
              <span className="text-gray-500 text-sm w-5">{idx + 1}</span>
              <Hash className="w-4 h-4 text-gray-500" />
              <span className="font-medium">{tag}</span>
            </div>
            <span className="text-xs text-gray-500">{count} articles</span>
          </div>
        ))}
      </div>
    </div>
  )
}

// Market sentiment summary
const SentimentSummary = ({ news }) => {
  const summary = useMemo(() => {
    const counts = { BULLISH: 0, BEARISH: 0, NEUTRAL: 0 }
    news.forEach(article => {
      counts[article.sentiment]++
    })
    const total = news.length
    return {
      bullish: (counts.BULLISH / total) * 100,
      bearish: (counts.BEARISH / total) * 100,
      neutral: (counts.NEUTRAL / total) * 100
    }
  }, [news])

  return (
    <div className="bg-white/5 rounded-xl p-4 border border-white/10">
      <h3 className="text-sm font-medium text-gray-300 mb-4 flex items-center gap-2">
        <TrendingUp className="w-4 h-4 text-green-400" />
        News Sentiment
      </h3>

      <div className="space-y-3">
        <div>
          <div className="flex justify-between text-sm mb-1">
            <span className="text-green-400">Bullish</span>
            <span>{summary.bullish.toFixed(0)}%</span>
          </div>
          <div className="h-2 bg-white/10 rounded-full overflow-hidden">
            <div
              className="h-full bg-green-500 rounded-full transition-all duration-500"
              style={{ width: `${summary.bullish}%` }}
            />
          </div>
        </div>

        <div>
          <div className="flex justify-between text-sm mb-1">
            <span className="text-red-400">Bearish</span>
            <span>{summary.bearish.toFixed(0)}%</span>
          </div>
          <div className="h-2 bg-white/10 rounded-full overflow-hidden">
            <div
              className="h-full bg-red-500 rounded-full transition-all duration-500"
              style={{ width: `${summary.bearish}%` }}
            />
          </div>
        </div>

        <div>
          <div className="flex justify-between text-sm mb-1">
            <span className="text-gray-400">Neutral</span>
            <span>{summary.neutral.toFixed(0)}%</span>
          </div>
          <div className="h-2 bg-white/10 rounded-full overflow-hidden">
            <div
              className="h-full bg-gray-500 rounded-full transition-all duration-500"
              style={{ width: `${summary.neutral}%` }}
            />
          </div>
        </div>
      </div>
    </div>
  )
}

// Source filter
const SourceFilter = ({ sources, selected, onChange }) => {
  return (
    <div className="bg-white/5 rounded-xl p-4 border border-white/10">
      <h3 className="text-sm font-medium text-gray-300 mb-4 flex items-center gap-2">
        <Radio className="w-4 h-4" />
        Sources
      </h3>

      <div className="space-y-2">
        {Object.entries(SOURCES).map(([key, source]) => (
          <label
            key={key}
            className="flex items-center gap-3 p-2 hover:bg-white/5 rounded-lg cursor-pointer transition-colors"
          >
            <input
              type="checkbox"
              checked={selected.includes(key)}
              onChange={() => {
                if (selected.includes(key)) {
                  onChange(selected.filter(s => s !== key))
                } else {
                  onChange([...selected, key])
                }
              }}
              className="rounded border-white/20 bg-white/5 text-blue-500 focus:ring-blue-500"
            />
            <span
              className="w-2 h-2 rounded-full"
              style={{ backgroundColor: source.color }}
            />
            <span className="flex-1">{source.name}</span>
            {source.trusted && <Star className="w-3 h-3 text-yellow-400" />}
          </label>
        ))}
      </div>
    </div>
  )
}

// Main component
export const NewsAggregator = () => {
  const [news] = useState(MOCK_NEWS)
  const [selectedCategory, setSelectedCategory] = useState('ALL')
  const [selectedSources, setSelectedSources] = useState(Object.keys(SOURCES))
  const [searchQuery, setSearchQuery] = useState('')
  const [bookmarks, setBookmarks] = useState([])
  const [showBookmarksOnly, setShowBookmarksOnly] = useState(false)
  const [sortBy, setSortBy] = useState('recent')
  const [viewMode, setViewMode] = useState('cards') // cards or compact
  const [refreshing, setRefreshing] = useState(false)

  const handleRefresh = useCallback(() => {
    setRefreshing(true)
    setTimeout(() => setRefreshing(false), 1500)
  }, [])

  const toggleBookmark = useCallback((id) => {
    setBookmarks(prev =>
      prev.includes(id)
        ? prev.filter(b => b !== id)
        : [...prev, id]
    )
  }, [])

  const filteredNews = useMemo(() => {
    let result = [...news]

    // Category filter
    if (selectedCategory !== 'ALL') {
      result = result.filter(a => a.category === selectedCategory)
    }

    // Source filter
    result = result.filter(a => selectedSources.includes(a.source))

    // Search filter
    if (searchQuery) {
      const query = searchQuery.toLowerCase()
      result = result.filter(a =>
        a.title.toLowerCase().includes(query) ||
        a.summary.toLowerCase().includes(query) ||
        a.tags.some(t => t.toLowerCase().includes(query))
      )
    }

    // Bookmarks only
    if (showBookmarksOnly) {
      result = result.filter(a => bookmarks.includes(a.id))
    }

    // Sort
    switch (sortBy) {
      case 'recent':
        result.sort((a, b) => b.timestamp - a.timestamp)
        break
      case 'popular':
        result.sort((a, b) => b.engagement.views - a.engagement.views)
        break
      case 'discussed':
        result.sort((a, b) => b.engagement.comments - a.engagement.comments)
        break
    }

    return result
  }, [news, selectedCategory, selectedSources, searchQuery, showBookmarksOnly, bookmarks, sortBy])

  const breakingNews = useMemo(() => filteredNews.filter(a => a.isBreaking), [filteredNews])

  return (
    <div className="min-h-screen bg-[#0a0e14] text-white p-6">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-bold flex items-center gap-3">
              <Newspaper className="w-7 h-7 text-blue-400" />
              Crypto News Aggregator
            </h1>
            <p className="text-gray-400 mt-1">Stay informed with the latest crypto news from top sources</p>
          </div>

          <div className="flex items-center gap-3">
            <button
              onClick={() => setViewMode(viewMode === 'cards' ? 'compact' : 'cards')}
              className="p-2 bg-white/5 hover:bg-white/10 rounded-lg transition-colors"
              title={viewMode === 'cards' ? 'Compact view' : 'Card view'}
            >
              {viewMode === 'cards' ? <Filter className="w-5 h-5" /> : <Newspaper className="w-5 h-5" />}
            </button>

            <button
              onClick={handleRefresh}
              className={`p-2 bg-white/5 hover:bg-white/10 rounded-lg transition-colors ${
                refreshing ? 'animate-spin' : ''
              }`}
            >
              <RefreshCw className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Breaking news banner */}
        {breakingNews.length > 0 && (
          <div className="mb-6 p-4 bg-red-500/10 border border-red-500/30 rounded-xl">
            <div className="flex items-center gap-2 text-red-400 mb-3">
              <Zap className="w-5 h-5" />
              <span className="font-bold">BREAKING NEWS</span>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {breakingNews.slice(0, 2).map(article => (
                <div key={article.id} className="flex items-start gap-3">
                  <div className="flex-1">
                    <h3 className="font-medium text-sm">{article.title}</h3>
                    <span className="text-xs text-gray-500">{formatTimeAgo(article.timestamp)}</span>
                  </div>
                  <ArrowUpRight className="w-4 h-4 text-red-400 flex-shrink-0" />
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Category tabs */}
        <div className="flex flex-wrap gap-2 mb-6">
          {Object.entries(CATEGORIES).map(([key, category]) => {
            const Icon = category.icon
            return (
              <button
                key={key}
                onClick={() => setSelectedCategory(key)}
                className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                  selectedCategory === key
                    ? 'bg-blue-500/20 text-blue-400 border border-blue-500/50'
                    : 'bg-white/5 text-gray-400 border border-white/10 hover:bg-white/10'
                }`}
              >
                <Icon className="w-4 h-4" />
                {category.label}
              </button>
            )
          })}
        </div>

        {/* Search and filters */}
        <div className="flex items-center gap-4 mb-6">
          <div className="relative flex-1 max-w-md">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search news..."
              className="w-full bg-white/5 border border-white/10 rounded-lg pl-10 pr-4 py-2 text-white placeholder-gray-500 focus:outline-none focus:border-blue-500/50"
            />
          </div>

          <button
            onClick={() => setShowBookmarksOnly(!showBookmarksOnly)}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg transition-colors ${
              showBookmarksOnly
                ? 'bg-yellow-500/20 text-yellow-400 border border-yellow-500/50'
                : 'bg-white/5 text-gray-400 border border-white/10 hover:bg-white/10'
            }`}
          >
            <Bookmark className="w-4 h-4" />
            Saved ({bookmarks.length})
          </button>

          <select
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value)}
            className="bg-white/5 border border-white/10 rounded-lg px-4 py-2 text-white"
          >
            <option value="recent">Most Recent</option>
            <option value="popular">Most Popular</option>
            <option value="discussed">Most Discussed</option>
          </select>
        </div>

        {/* Main content */}
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
          {/* News feed */}
          <div className="lg:col-span-3 space-y-4">
            {viewMode === 'cards' ? (
              filteredNews.map(article => (
                <NewsCard
                  key={article.id}
                  article={article}
                  onBookmark={toggleBookmark}
                  bookmarked={bookmarks.includes(article.id)}
                />
              ))
            ) : (
              <div className="space-y-2">
                {filteredNews.map(article => (
                  <NewsCard
                    key={article.id}
                    article={article}
                    isCompact
                    onBookmark={toggleBookmark}
                    bookmarked={bookmarks.includes(article.id)}
                  />
                ))}
              </div>
            )}

            {filteredNews.length === 0 && (
              <div className="text-center py-12 bg-white/5 rounded-xl border border-white/10">
                <Newspaper className="w-12 h-12 text-gray-600 mx-auto mb-4" />
                <p className="text-gray-400">No news articles match your filters</p>
              </div>
            )}
          </div>

          {/* Sidebar */}
          <div className="space-y-6">
            <SentimentSummary news={news} />
            <TrendingTopics news={news} />
            <SourceFilter
              sources={SOURCES}
              selected={selectedSources}
              onChange={setSelectedSources}
            />
          </div>
        </div>
      </div>
    </div>
  )
}

export default NewsAggregator
