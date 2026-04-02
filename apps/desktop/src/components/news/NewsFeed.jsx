import React, { useState, useMemo, useCallback, useEffect } from 'react'
import {
  Newspaper, RefreshCw, Filter, Search, ExternalLink, Clock, TrendingUp,
  TrendingDown, MessageCircle, Share2, Bookmark, BookmarkCheck, Star,
  ChevronDown, AlertCircle, Zap, Flame, Eye, ThumbsUp, X, Settings
} from 'lucide-react'

/**
 * NewsFeed - Crypto news aggregation component
 *
 * Features:
 * - Multi-source news aggregation
 * - Sentiment analysis per article
 * - Token mentions detection
 * - Save/Bookmark articles
 * - Search and filter
 * - Category organization
 */

// News sources
const NEWS_SOURCES = {
  twitter: { label: 'X / Twitter', color: 'blue', icon: MessageCircle },
  reddit: { label: 'Reddit', color: 'orange', icon: MessageCircle },
  cointelegraph: { label: 'CoinTelegraph', color: 'yellow', icon: Newspaper },
  coindesk: { label: 'CoinDesk', color: 'blue', icon: Newspaper },
  theblock: { label: 'The Block', color: 'purple', icon: Newspaper },
  decrypt: { label: 'Decrypt', color: 'cyan', icon: Newspaper },
  defiant: { label: 'The Defiant', color: 'green', icon: Newspaper },
  other: { label: 'Other', color: 'gray', icon: Newspaper },
}

// News categories
const NEWS_CATEGORIES = {
  all: { label: 'All News', icon: Newspaper },
  market: { label: 'Market', icon: TrendingUp },
  defi: { label: 'DeFi', icon: Zap },
  nft: { label: 'NFT', icon: Star },
  regulation: { label: 'Regulation', icon: AlertCircle },
  technology: { label: 'Technology', icon: Settings },
  trending: { label: 'Trending', icon: Flame },
}

// Sentiment types
const SENTIMENT_TYPES = {
  bullish: { label: 'Bullish', color: 'green', icon: TrendingUp },
  bearish: { label: 'Bearish', color: 'red', icon: TrendingDown },
  neutral: { label: 'Neutral', color: 'gray', icon: MessageCircle },
}

/**
 * NewsCard - Single news article card
 */
function NewsCard({
  article,
  onBookmark,
  onShare,
  onTokenClick,
  compact = false,
  className = '',
}) {
  const [isExpanded, setIsExpanded] = useState(false)

  const source = NEWS_SOURCES[article.source] || NEWS_SOURCES.other
  const sentiment = SENTIMENT_TYPES[article.sentiment] || SENTIMENT_TYPES.neutral

  const formatTime = (timestamp) => {
    const date = new Date(timestamp)
    const now = new Date()
    const diffMs = now - date
    const diffMins = Math.floor(diffMs / 60000)
    const diffHours = Math.floor(diffMs / 3600000)
    const diffDays = Math.floor(diffMs / 86400000)

    if (diffMins < 60) return `${diffMins}m ago`
    if (diffHours < 24) return `${diffHours}h ago`
    if (diffDays < 7) return `${diffDays}d ago`
    return date.toLocaleDateString()
  }

  return (
    <div className={`bg-gray-900/50 rounded-lg border border-gray-800 overflow-hidden hover:border-gray-700 transition-colors ${className}`}>
      {/* Image if available and not compact */}
      {article.image && !compact && (
        <div className="aspect-video bg-gray-800 overflow-hidden">
          <img
            src={article.image}
            alt={article.title}
            className="w-full h-full object-cover"
            onError={(e) => e.target.style.display = 'none'}
          />
        </div>
      )}

      <div className="p-4">
        {/* Header */}
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-2">
            {/* Source */}
            <span className={`flex items-center gap-1 px-2 py-0.5 rounded text-xs bg-${source.color}-500/10 text-${source.color}-400`}>
              <source.icon className="w-3 h-3" />
              {source.label}
            </span>

            {/* Category */}
            {article.category && (
              <span className="px-2 py-0.5 bg-gray-800 rounded text-xs text-gray-400">
                {NEWS_CATEGORIES[article.category]?.label || article.category}
              </span>
            )}

            {/* Hot indicator */}
            {article.isHot && (
              <Flame className="w-4 h-4 text-orange-400" />
            )}
          </div>

          {/* Sentiment */}
          <span className={`flex items-center gap-1 text-xs text-${sentiment.color}-400`}>
            <sentiment.icon className="w-3 h-3" />
            {sentiment.label}
          </span>
        </div>

        {/* Title */}
        <a
          href={article.url}
          target="_blank"
          rel="noopener noreferrer"
          className="block group"
        >
          <h3 className="font-semibold text-white group-hover:text-purple-400 transition-colors line-clamp-2 mb-2">
            {article.title}
          </h3>
        </a>

        {/* Summary */}
        {!compact && article.summary && (
          <p className={`text-sm text-gray-400 mb-3 ${isExpanded ? '' : 'line-clamp-2'}`}>
            {article.summary}
          </p>
        )}

        {/* Token mentions */}
        {article.tokens && article.tokens.length > 0 && (
          <div className="flex flex-wrap gap-1 mb-3">
            {article.tokens.map((token, i) => (
              <button
                key={i}
                onClick={() => onTokenClick?.(token)}
                className="px-2 py-0.5 bg-purple-500/10 text-purple-400 rounded text-xs hover:bg-purple-500/20"
              >
                ${token}
              </button>
            ))}
          </div>
        )}

        {/* Footer */}
        <div className="flex items-center justify-between text-xs">
          <div className="flex items-center gap-3 text-gray-500">
            <span className="flex items-center gap-1">
              <Clock className="w-3 h-3" />
              {formatTime(article.publishedAt)}
            </span>

            {article.author && (
              <span className="truncate max-w-24">by {article.author}</span>
            )}

            {article.views !== undefined && (
              <span className="flex items-center gap-1">
                <Eye className="w-3 h-3" />
                {article.views.toLocaleString()}
              </span>
            )}
          </div>

          <div className="flex items-center gap-1">
            {/* Bookmark */}
            <button
              onClick={() => onBookmark?.(article.id)}
              className={`p-1.5 rounded hover:bg-gray-800 ${
                article.isBookmarked ? 'text-yellow-400' : 'text-gray-500'
              }`}
            >
              {article.isBookmarked ? (
                <BookmarkCheck className="w-4 h-4" />
              ) : (
                <Bookmark className="w-4 h-4" />
              )}
            </button>

            {/* Share */}
            <button
              onClick={() => onShare?.(article)}
              className="p-1.5 rounded hover:bg-gray-800 text-gray-500 hover:text-white"
            >
              <Share2 className="w-4 h-4" />
            </button>

            {/* External link */}
            <a
              href={article.url}
              target="_blank"
              rel="noopener noreferrer"
              className="p-1.5 rounded hover:bg-gray-800 text-gray-500 hover:text-white"
            >
              <ExternalLink className="w-4 h-4" />
            </a>
          </div>
        </div>
      </div>
    </div>
  )
}

/**
 * TrendingTopics - Trending topics sidebar
 */
function TrendingTopics({ topics = [], onTopicClick, className = '' }) {
  if (topics.length === 0) return null

  return (
    <div className={`bg-gray-900/50 rounded-lg border border-gray-800 p-4 ${className}`}>
      <div className="flex items-center gap-2 mb-4">
        <Flame className="w-4 h-4 text-orange-400" />
        <span className="font-medium text-white">Trending</span>
      </div>

      <div className="space-y-2">
        {topics.map((topic, i) => (
          <button
            key={i}
            onClick={() => onTopicClick?.(topic.term)}
            className="w-full flex items-center justify-between p-2 rounded-lg hover:bg-gray-800 transition-colors"
          >
            <div className="flex items-center gap-2">
              <span className="text-sm text-gray-500">#{i + 1}</span>
              <span className="text-sm text-white">{topic.term}</span>
            </div>
            <span className="text-xs text-gray-500">{topic.count} mentions</span>
          </button>
        ))}
      </div>
    </div>
  )
}

/**
 * SourceFilter - Filter by news source
 */
function SourceFilter({ selected, onChange, className = '' }) {
  return (
    <div className={`flex flex-wrap gap-2 ${className}`}>
      <button
        onClick={() => onChange('all')}
        className={`px-3 py-1.5 rounded-lg text-sm transition-colors ${
          selected === 'all'
            ? 'bg-gray-700 text-white'
            : 'text-gray-400 hover:text-white'
        }`}
      >
        All Sources
      </button>
      {Object.entries(NEWS_SOURCES).map(([key, source]) => (
        <button
          key={key}
          onClick={() => onChange(key)}
          className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm transition-colors ${
            selected === key
              ? `bg-${source.color}-500/20 text-${source.color}-400`
              : 'text-gray-400 hover:text-white'
          }`}
        >
          <source.icon className="w-3 h-3" />
          {source.label}
        </button>
      ))}
    </div>
  )
}

/**
 * Main NewsFeed Component
 */
export function NewsFeed({
  initialNews = [],
  trendingTopics = [],
  onRefresh,
  onBookmark,
  onShare,
  onTokenClick,
  isLoading = false,
  className = '',
}) {
  const [news, setNews] = useState(initialNews)
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedCategory, setSelectedCategory] = useState('all')
  const [selectedSource, setSelectedSource] = useState('all')
  const [selectedSentiment, setSelectedSentiment] = useState('all')
  const [showBookmarkedOnly, setShowBookmarkedOnly] = useState(false)
  const [viewMode, setViewMode] = useState('mixed') // mixed, compact, cards

  // Filter news
  const filteredNews = useMemo(() => {
    let filtered = news

    // Search
    if (searchQuery) {
      const query = searchQuery.toLowerCase()
      filtered = filtered.filter(article =>
        article.title?.toLowerCase().includes(query) ||
        article.summary?.toLowerCase().includes(query) ||
        article.tokens?.some(t => t.toLowerCase().includes(query))
      )
    }

    // Category
    if (selectedCategory !== 'all') {
      filtered = filtered.filter(article => article.category === selectedCategory)
    }

    // Source
    if (selectedSource !== 'all') {
      filtered = filtered.filter(article => article.source === selectedSource)
    }

    // Sentiment
    if (selectedSentiment !== 'all') {
      filtered = filtered.filter(article => article.sentiment === selectedSentiment)
    }

    // Bookmarked
    if (showBookmarkedOnly) {
      filtered = filtered.filter(article => article.isBookmarked)
    }

    // Sort by date (newest first)
    filtered.sort((a, b) => new Date(b.publishedAt) - new Date(a.publishedAt))

    return filtered
  }, [news, searchQuery, selectedCategory, selectedSource, selectedSentiment, showBookmarkedOnly])

  // Handle bookmark toggle
  const handleBookmark = useCallback((articleId) => {
    setNews(prev => prev.map(article =>
      article.id === articleId
        ? { ...article, isBookmarked: !article.isBookmarked }
        : article
    ))
    onBookmark?.(articleId)
  }, [onBookmark])

  // Stats
  const stats = useMemo(() => {
    const bullish = news.filter(a => a.sentiment === 'bullish').length
    const bearish = news.filter(a => a.sentiment === 'bearish').length
    const neutral = news.filter(a => a.sentiment === 'neutral').length
    const bookmarked = news.filter(a => a.isBookmarked).length

    return { total: news.length, bullish, bearish, neutral, bookmarked }
  }, [news])

  return (
    <div className={className}>
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-xl font-bold text-white">News Feed</h2>
          <p className="text-sm text-gray-400">
            {stats.total} articles | {stats.bullish} bullish | {stats.bearish} bearish
          </p>
        </div>

        <button
          onClick={onRefresh}
          disabled={isLoading}
          className="flex items-center gap-2 px-4 py-2 bg-purple-500/20 border border-purple-500/30 rounded-lg text-purple-400 hover:bg-purple-500/30 disabled:opacity-50"
        >
          <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
          Refresh
        </button>
      </div>

      {/* Sentiment bar */}
      <div className="flex items-center gap-4 mb-6">
        <div className="flex-1 h-2 bg-gray-800 rounded-full overflow-hidden flex">
          {stats.total > 0 && (
            <>
              <div
                className="bg-green-500 transition-all"
                style={{ width: `${(stats.bullish / stats.total) * 100}%` }}
              />
              <div
                className="bg-gray-500 transition-all"
                style={{ width: `${(stats.neutral / stats.total) * 100}%` }}
              />
              <div
                className="bg-red-500 transition-all"
                style={{ width: `${(stats.bearish / stats.total) * 100}%` }}
              />
            </>
          )}
        </div>
        <div className="flex items-center gap-4 text-xs">
          <span className="flex items-center gap-1 text-green-400">
            <TrendingUp className="w-3 h-3" />
            {((stats.bullish / stats.total) * 100 || 0).toFixed(0)}%
          </span>
          <span className="flex items-center gap-1 text-red-400">
            <TrendingDown className="w-3 h-3" />
            {((stats.bearish / stats.total) * 100 || 0).toFixed(0)}%
          </span>
        </div>
      </div>

      {/* Filters */}
      <div className="space-y-4 mb-6">
        {/* Search */}
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search news..."
            className="w-full pl-10 pr-4 py-2.5 bg-gray-800 border border-gray-700 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:border-purple-500"
          />
        </div>

        {/* Category tabs */}
        <div className="flex items-center gap-2 overflow-x-auto pb-2">
          {Object.entries(NEWS_CATEGORIES).map(([key, category]) => (
            <button
              key={key}
              onClick={() => setSelectedCategory(key)}
              className={`flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm whitespace-nowrap transition-colors ${
                selectedCategory === key
                  ? 'bg-purple-500/20 text-purple-400'
                  : 'text-gray-400 hover:text-white hover:bg-gray-800'
              }`}
            >
              <category.icon className="w-4 h-4" />
              {category.label}
            </button>
          ))}
        </div>

        {/* Additional filters */}
        <div className="flex items-center gap-4">
          {/* Sentiment filter */}
          <div className="flex items-center gap-2">
            <span className="text-sm text-gray-500">Sentiment:</span>
            <select
              value={selectedSentiment}
              onChange={(e) => setSelectedSentiment(e.target.value)}
              className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-1.5 text-sm text-white"
            >
              <option value="all">All</option>
              <option value="bullish">Bullish</option>
              <option value="neutral">Neutral</option>
              <option value="bearish">Bearish</option>
            </select>
          </div>

          {/* Source filter */}
          <div className="flex items-center gap-2">
            <span className="text-sm text-gray-500">Source:</span>
            <select
              value={selectedSource}
              onChange={(e) => setSelectedSource(e.target.value)}
              className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-1.5 text-sm text-white"
            >
              <option value="all">All Sources</option>
              {Object.entries(NEWS_SOURCES).map(([key, source]) => (
                <option key={key} value={key}>{source.label}</option>
              ))}
            </select>
          </div>

          {/* Bookmarks toggle */}
          <button
            onClick={() => setShowBookmarkedOnly(!showBookmarkedOnly)}
            className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm transition-colors ${
              showBookmarkedOnly
                ? 'bg-yellow-500/20 text-yellow-400'
                : 'text-gray-400 hover:text-white'
            }`}
          >
            <Bookmark className={`w-4 h-4 ${showBookmarkedOnly ? 'fill-current' : ''}`} />
            Saved ({stats.bookmarked})
          </button>

          {/* View mode */}
          <div className="flex items-center gap-1 ml-auto">
            <button
              onClick={() => setViewMode('cards')}
              className={`p-2 rounded ${viewMode === 'cards' ? 'bg-gray-700 text-white' : 'text-gray-500'}`}
              title="Cards view"
            >
              <Newspaper className="w-4 h-4" />
            </button>
            <button
              onClick={() => setViewMode('compact')}
              className={`p-2 rounded ${viewMode === 'compact' ? 'bg-gray-700 text-white' : 'text-gray-500'}`}
              title="Compact view"
            >
              <Filter className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>

      {/* Main content */}
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* News list */}
        <div className="lg:col-span-3">
          {isLoading ? (
            <div className="flex items-center justify-center py-16">
              <RefreshCw className="w-8 h-8 text-purple-400 animate-spin" />
            </div>
          ) : filteredNews.length === 0 ? (
            <div className="text-center py-16 bg-gray-900/50 rounded-xl border border-gray-800">
              <Newspaper className="w-12 h-12 text-gray-600 mx-auto mb-4" />
              <h3 className="text-lg font-medium text-gray-400 mb-2">No News Found</h3>
              <p className="text-sm text-gray-500">
                {news.length === 0
                  ? 'Click refresh to load the latest news'
                  : 'Try adjusting your filters'}
              </p>
            </div>
          ) : (
            <div className={
              viewMode === 'cards'
                ? 'grid grid-cols-1 md:grid-cols-2 gap-4'
                : 'space-y-3'
            }>
              {filteredNews.map(article => (
                <NewsCard
                  key={article.id}
                  article={article}
                  onBookmark={handleBookmark}
                  onShare={onShare}
                  onTokenClick={onTokenClick}
                  compact={viewMode === 'compact'}
                />
              ))}
            </div>
          )}
        </div>

        {/* Sidebar */}
        <div className="space-y-4">
          {/* Trending topics */}
          <TrendingTopics
            topics={trendingTopics}
            onTopicClick={(term) => setSearchQuery(term)}
          />

          {/* Quick stats */}
          <div className="bg-gray-900/50 rounded-lg border border-gray-800 p-4">
            <div className="flex items-center gap-2 mb-4">
              <Zap className="w-4 h-4 text-yellow-400" />
              <span className="font-medium text-white">Quick Stats</span>
            </div>

            <div className="space-y-3 text-sm">
              <div className="flex items-center justify-between">
                <span className="text-gray-400">Total Articles</span>
                <span className="text-white font-medium">{stats.total}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-gray-400">Bullish Sentiment</span>
                <span className="text-green-400 font-medium">{stats.bullish}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-gray-400">Bearish Sentiment</span>
                <span className="text-red-400 font-medium">{stats.bearish}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-gray-400">Saved Articles</span>
                <span className="text-yellow-400 font-medium">{stats.bookmarked}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

export default NewsFeed
