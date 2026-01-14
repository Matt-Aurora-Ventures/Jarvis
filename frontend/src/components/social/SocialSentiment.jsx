import React, { useState, useMemo, useCallback } from 'react'
import {
  MessageSquare, TrendingUp, TrendingDown, RefreshCw, Search, Filter,
  Twitter, Users, Eye, Heart, Share2, Repeat2, BarChart3, Activity,
  Flame, Clock, ExternalLink, Hash, AtSign, Bell, Star, AlertTriangle,
  ThumbsUp, ThumbsDown, Minus, Zap, Globe
} from 'lucide-react'

// Social platforms
const PLATFORMS = {
  TWITTER: { name: 'X/Twitter', color: '#1DA1F2', icon: Twitter },
  TELEGRAM: { name: 'Telegram', color: '#0088cc', icon: MessageSquare },
  DISCORD: { name: 'Discord', color: '#5865F2', icon: Users },
  REDDIT: { name: 'Reddit', color: '#FF4500', icon: Globe }
}

// Sentiment levels
const SENTIMENT_LEVELS = {
  VERY_BULLISH: { label: 'Very Bullish', color: '#22C55E', score: [80, 100] },
  BULLISH: { label: 'Bullish', color: '#4ADE80', score: [60, 80] },
  NEUTRAL: { label: 'Neutral', color: '#9CA3AF', score: [40, 60] },
  BEARISH: { label: 'Bearish', color: '#F87171', score: [20, 40] },
  VERY_BEARISH: { label: 'Very Bearish', color: '#EF4444', score: [0, 20] }
}

// Get sentiment level from score
const getSentimentLevel = (score) => {
  for (const [key, level] of Object.entries(SENTIMENT_LEVELS)) {
    if (score >= level.score[0] && score <= level.score[1]) {
      return { key, ...level }
    }
  }
  return { key: 'NEUTRAL', ...SENTIMENT_LEVELS.NEUTRAL }
}

// Mock social data for tokens
const MOCK_TOKEN_SENTIMENT = [
  {
    symbol: 'BTC',
    name: 'Bitcoin',
    sentimentScore: 72,
    sentimentChange24h: 5.2,
    mentions24h: 125000,
    mentionsChange: 15.5,
    engagement24h: 2850000,
    engagementChange: 8.2,
    topInfluencers: 12,
    trendingTopics: ['ETF', 'ATH', 'Halving'],
    platforms: {
      TWITTER: { mentions: 85000, sentiment: 75 },
      TELEGRAM: { mentions: 22000, sentiment: 68 },
      DISCORD: { mentions: 12000, sentiment: 71 },
      REDDIT: { mentions: 6000, sentiment: 65 }
    }
  },
  {
    symbol: 'ETH',
    name: 'Ethereum',
    sentimentScore: 65,
    sentimentChange24h: 2.8,
    mentions24h: 78000,
    mentionsChange: 8.2,
    engagement24h: 1650000,
    engagementChange: 5.5,
    topInfluencers: 8,
    trendingTopics: ['L2', 'Blob', 'Staking'],
    platforms: {
      TWITTER: { mentions: 52000, sentiment: 68 },
      TELEGRAM: { mentions: 14000, sentiment: 62 },
      DISCORD: { mentions: 8000, sentiment: 64 },
      REDDIT: { mentions: 4000, sentiment: 58 }
    }
  },
  {
    symbol: 'SOL',
    name: 'Solana',
    sentimentScore: 78,
    sentimentChange24h: 12.5,
    mentions24h: 95000,
    mentionsChange: 32.5,
    engagement24h: 2100000,
    engagementChange: 45.2,
    topInfluencers: 15,
    trendingTopics: ['Memecoins', 'DePIN', 'ETF'],
    platforms: {
      TWITTER: { mentions: 68000, sentiment: 82 },
      TELEGRAM: { mentions: 15000, sentiment: 75 },
      DISCORD: { mentions: 9000, sentiment: 76 },
      REDDIT: { mentions: 3000, sentiment: 68 }
    }
  },
  {
    symbol: 'PEPE',
    name: 'Pepe',
    sentimentScore: 85,
    sentimentChange24h: 18.2,
    mentions24h: 145000,
    mentionsChange: 65.5,
    engagement24h: 3200000,
    engagementChange: 82.5,
    topInfluencers: 22,
    trendingTopics: ['Pump', 'Meme', 'Viral'],
    platforms: {
      TWITTER: { mentions: 112000, sentiment: 88 },
      TELEGRAM: { mentions: 18000, sentiment: 82 },
      DISCORD: { mentions: 12000, sentiment: 84 },
      REDDIT: { mentions: 3000, sentiment: 75 }
    }
  },
  {
    symbol: 'WIF',
    name: 'Dogwifhat',
    sentimentScore: 68,
    sentimentChange24h: -5.5,
    mentions24h: 42000,
    mentionsChange: -12.2,
    engagement24h: 980000,
    engagementChange: -8.5,
    topInfluencers: 8,
    trendingTopics: ['Correction', 'Buy dip'],
    platforms: {
      TWITTER: { mentions: 32000, sentiment: 65 },
      TELEGRAM: { mentions: 6000, sentiment: 70 },
      DISCORD: { mentions: 3000, sentiment: 72 },
      REDDIT: { mentions: 1000, sentiment: 58 }
    }
  },
  {
    symbol: 'ARB',
    name: 'Arbitrum',
    sentimentScore: 45,
    sentimentChange24h: -8.2,
    mentions24h: 28000,
    mentionsChange: -15.5,
    engagement24h: 520000,
    engagementChange: -22.5,
    topInfluencers: 5,
    trendingTopics: ['Unlock', 'Bearish'],
    platforms: {
      TWITTER: { mentions: 18000, sentiment: 42 },
      TELEGRAM: { mentions: 6000, sentiment: 48 },
      DISCORD: { mentions: 3000, sentiment: 45 },
      REDDIT: { mentions: 1000, sentiment: 38 }
    }
  }
]

// Mock trending posts
const MOCK_TRENDING_POSTS = [
  {
    id: '1',
    platform: 'TWITTER',
    author: '@CryptoWhale',
    authorFollowers: 1250000,
    content: 'Just loaded up on more $BTC. This breakout is just getting started. Next stop $100K!',
    likes: 12500,
    retweets: 3200,
    comments: 850,
    sentiment: 'BULLISH',
    tokens: ['BTC'],
    timestamp: Date.now() - 1000 * 60 * 30
  },
  {
    id: '2',
    platform: 'TWITTER',
    author: '@SolanaLegend',
    authorFollowers: 520000,
    content: '$SOL ecosystem is on fire! Memecoins, DePIN, gaming - everything pumping. This is just the beginning.',
    likes: 8500,
    retweets: 2100,
    comments: 620,
    sentiment: 'BULLISH',
    tokens: ['SOL'],
    timestamp: Date.now() - 1000 * 60 * 45
  },
  {
    id: '3',
    platform: 'TELEGRAM',
    author: 'CryptoAlerts',
    authorFollowers: 180000,
    content: 'Warning: Large $ARB unlock coming in 3 days. 1.1B tokens hitting the market. Be careful!',
    likes: 3200,
    retweets: 0,
    comments: 450,
    sentiment: 'BEARISH',
    tokens: ['ARB'],
    timestamp: Date.now() - 1000 * 60 * 90
  },
  {
    id: '4',
    platform: 'TWITTER',
    author: '@PepeMaximalist',
    authorFollowers: 320000,
    content: '$PEPE breaking out! Cup and handle pattern complete. Target $0.00003 incoming!',
    likes: 15200,
    retweets: 4500,
    comments: 1200,
    sentiment: 'BULLISH',
    tokens: ['PEPE'],
    timestamp: Date.now() - 1000 * 60 * 120
  },
  {
    id: '5',
    platform: 'DISCORD',
    author: 'ETH Whale',
    authorFollowers: 85000,
    content: 'Layer 2 TVL hitting new ATH. $ETH ecosystem stronger than ever. Accumulate the dips.',
    likes: 2800,
    retweets: 0,
    comments: 380,
    sentiment: 'BULLISH',
    tokens: ['ETH'],
    timestamp: Date.now() - 1000 * 60 * 180
  }
]

// Format numbers
const formatNumber = (num) => {
  if (num >= 1e6) return `${(num / 1e6).toFixed(1)}M`
  if (num >= 1e3) return `${(num / 1e3).toFixed(1)}K`
  return num.toString()
}

// Format time ago
const formatTimeAgo = (timestamp) => {
  const diff = Date.now() - timestamp
  const minutes = Math.floor(diff / (1000 * 60))
  const hours = Math.floor(diff / (1000 * 60 * 60))
  if (minutes < 60) return `${minutes}m ago`
  return `${hours}h ago`
}

// Sentiment gauge
const SentimentGauge = ({ score, size = 'md' }) => {
  const level = getSentimentLevel(score)
  const radius = size === 'lg' ? 60 : 40
  const strokeWidth = size === 'lg' ? 8 : 6
  const circumference = 2 * Math.PI * radius
  const progress = (score / 100) * circumference * 0.75 // 270 degrees

  return (
    <div className="relative inline-flex items-center justify-center">
      <svg
        width={radius * 2 + strokeWidth * 2}
        height={radius * 2 + strokeWidth * 2}
        className="transform -rotate-135"
      >
        {/* Background arc */}
        <circle
          cx={radius + strokeWidth}
          cy={radius + strokeWidth}
          r={radius}
          fill="none"
          stroke="rgba(255,255,255,0.1)"
          strokeWidth={strokeWidth}
          strokeDasharray={`${circumference * 0.75} ${circumference * 0.25}`}
        />
        {/* Progress arc */}
        <circle
          cx={radius + strokeWidth}
          cy={radius + strokeWidth}
          r={radius}
          fill="none"
          stroke={level.color}
          strokeWidth={strokeWidth}
          strokeDasharray={`${progress} ${circumference}`}
          strokeLinecap="round"
          className="transition-all duration-500"
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className={`${size === 'lg' ? 'text-3xl' : 'text-xl'} font-bold`} style={{ color: level.color }}>
          {score}
        </span>
        <span className="text-xs text-gray-500">{level.label}</span>
      </div>
    </div>
  )
}

// Token sentiment card
const TokenSentimentCard = ({ token, expanded, onExpand }) => {
  const level = getSentimentLevel(token.sentimentScore)

  return (
    <div className="bg-white/5 rounded-xl border border-white/10 overflow-hidden">
      <div
        className="p-4 cursor-pointer hover:bg-white/[0.02] transition-colors"
        onClick={() => onExpand(expanded ? null : token.symbol)}
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <SentimentGauge score={token.sentimentScore} />
            <div>
              <div className="flex items-center gap-2">
                <span className="font-bold text-lg">{token.symbol}</span>
                <span className="text-sm text-gray-500">{token.name}</span>
              </div>
              <div className={`flex items-center gap-1 text-sm ${
                token.sentimentChange24h > 0 ? 'text-green-400' : 'text-red-400'
              }`}>
                {token.sentimentChange24h > 0 ? <TrendingUp className="w-4 h-4" /> : <TrendingDown className="w-4 h-4" />}
                {token.sentimentChange24h > 0 ? '+' : ''}{token.sentimentChange24h}% (24h)
              </div>
            </div>
          </div>

          <div className="flex items-center gap-6">
            <div className="text-right">
              <div className="text-sm text-gray-500">Mentions</div>
              <div className="font-medium">{formatNumber(token.mentions24h)}</div>
              <div className={`text-xs ${token.mentionsChange > 0 ? 'text-green-400' : 'text-red-400'}`}>
                {token.mentionsChange > 0 ? '+' : ''}{token.mentionsChange}%
              </div>
            </div>

            <div className="text-right">
              <div className="text-sm text-gray-500">Engagement</div>
              <div className="font-medium">{formatNumber(token.engagement24h)}</div>
              <div className={`text-xs ${token.engagementChange > 0 ? 'text-green-400' : 'text-red-400'}`}>
                {token.engagementChange > 0 ? '+' : ''}{token.engagementChange}%
              </div>
            </div>

            <div className="text-right">
              <div className="text-sm text-gray-500">Influencers</div>
              <div className="font-medium">{token.topInfluencers}</div>
            </div>
          </div>
        </div>

        {/* Trending topics */}
        <div className="flex items-center gap-2 mt-3">
          <Flame className="w-4 h-4 text-orange-400" />
          {token.trendingTopics.map((topic, idx) => (
            <span key={idx} className="px-2 py-0.5 bg-white/10 rounded text-xs">
              #{topic}
            </span>
          ))}
        </div>
      </div>

      {/* Expanded platform breakdown */}
      {expanded && (
        <div className="p-4 bg-white/[0.02] border-t border-white/10">
          <div className="text-sm text-gray-500 mb-3">Platform Breakdown</div>
          <div className="grid grid-cols-4 gap-4">
            {Object.entries(PLATFORMS).map(([key, platform]) => {
              const data = token.platforms[key]
              const Icon = platform.icon
              const platformLevel = getSentimentLevel(data.sentiment)

              return (
                <div key={key} className="bg-white/5 rounded-lg p-3">
                  <div className="flex items-center gap-2 mb-2">
                    <Icon className="w-4 h-4" style={{ color: platform.color }} />
                    <span className="text-sm font-medium">{platform.name}</span>
                  </div>
                  <div className="space-y-2">
                    <div className="flex justify-between text-xs">
                      <span className="text-gray-500">Mentions</span>
                      <span>{formatNumber(data.mentions)}</span>
                    </div>
                    <div className="flex justify-between text-xs">
                      <span className="text-gray-500">Sentiment</span>
                      <span style={{ color: platformLevel.color }}>{data.sentiment}</span>
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}

// Trending post card
const TrendingPostCard = ({ post }) => {
  const platform = PLATFORMS[post.platform]
  const Icon = platform.icon
  const sentimentColor = post.sentiment === 'BULLISH' ? 'text-green-400' : post.sentiment === 'BEARISH' ? 'text-red-400' : 'text-gray-400'

  return (
    <div className="bg-white/5 rounded-lg p-4 border border-white/10">
      <div className="flex items-start gap-3">
        <div
          className="w-10 h-10 rounded-full flex items-center justify-center"
          style={{ backgroundColor: `${platform.color}20` }}
        >
          <Icon className="w-5 h-5" style={{ color: platform.color }} />
        </div>

        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className="font-medium">{post.author}</span>
            <span className="text-xs text-gray-500">{formatNumber(post.authorFollowers)} followers</span>
            <span className="text-xs text-gray-500">{formatTimeAgo(post.timestamp)}</span>
          </div>

          <p className="text-sm text-gray-300 mb-2">{post.content}</p>

          <div className="flex items-center gap-4 text-xs text-gray-500">
            <span className="flex items-center gap-1">
              <Heart className="w-4 h-4" />
              {formatNumber(post.likes)}
            </span>
            {post.retweets > 0 && (
              <span className="flex items-center gap-1">
                <Repeat2 className="w-4 h-4" />
                {formatNumber(post.retweets)}
              </span>
            )}
            <span className="flex items-center gap-1">
              <MessageSquare className="w-4 h-4" />
              {formatNumber(post.comments)}
            </span>
            <span className={`ml-auto ${sentimentColor} font-medium`}>
              {post.sentiment === 'BULLISH' ? <ThumbsUp className="w-4 h-4" /> : post.sentiment === 'BEARISH' ? <ThumbsDown className="w-4 h-4" /> : <Minus className="w-4 h-4" />}
            </span>
          </div>
        </div>
      </div>
    </div>
  )
}

// Overall market sentiment
const MarketSentiment = ({ tokens }) => {
  const overall = useMemo(() => {
    const avg = tokens.reduce((sum, t) => sum + t.sentimentScore, 0) / tokens.length
    const totalMentions = tokens.reduce((sum, t) => sum + t.mentions24h, 0)
    const totalEngagement = tokens.reduce((sum, t) => sum + t.engagement24h, 0)
    return { avg, totalMentions, totalEngagement }
  }, [tokens])

  return (
    <div className="bg-white/5 rounded-xl p-6 border border-white/10 text-center">
      <h3 className="text-lg font-medium text-gray-300 mb-4">Overall Market Sentiment</h3>
      <SentimentGauge score={Math.round(overall.avg)} size="lg" />
      <div className="grid grid-cols-2 gap-4 mt-6">
        <div>
          <div className="text-sm text-gray-500">Total Mentions</div>
          <div className="text-xl font-bold">{formatNumber(overall.totalMentions)}</div>
        </div>
        <div>
          <div className="text-sm text-gray-500">Total Engagement</div>
          <div className="text-xl font-bold">{formatNumber(overall.totalEngagement)}</div>
        </div>
      </div>
    </div>
  )
}

// Top gainers/losers sentiment
const SentimentMovers = ({ tokens }) => {
  const gainers = useMemo(() =>
    [...tokens].sort((a, b) => b.sentimentChange24h - a.sentimentChange24h).slice(0, 3),
    [tokens]
  )

  const losers = useMemo(() =>
    [...tokens].sort((a, b) => a.sentimentChange24h - b.sentimentChange24h).slice(0, 3),
    [tokens]
  )

  return (
    <div className="bg-white/5 rounded-xl p-4 border border-white/10">
      <h3 className="text-sm font-medium text-gray-300 mb-4 flex items-center gap-2">
        <Activity className="w-4 h-4" />
        Sentiment Movers (24h)
      </h3>

      <div className="space-y-4">
        <div>
          <div className="text-xs text-green-400 mb-2">TOP GAINERS</div>
          {gainers.filter(t => t.sentimentChange24h > 0).map(token => (
            <div key={token.symbol} className="flex items-center justify-between py-1.5">
              <span className="font-medium">{token.symbol}</span>
              <span className="text-green-400">+{token.sentimentChange24h}%</span>
            </div>
          ))}
        </div>

        <div>
          <div className="text-xs text-red-400 mb-2">TOP LOSERS</div>
          {losers.filter(t => t.sentimentChange24h < 0).map(token => (
            <div key={token.symbol} className="flex items-center justify-between py-1.5">
              <span className="font-medium">{token.symbol}</span>
              <span className="text-red-400">{token.sentimentChange24h}%</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

// Main component
export const SocialSentiment = () => {
  const [tokens] = useState(MOCK_TOKEN_SENTIMENT)
  const [posts] = useState(MOCK_TRENDING_POSTS)
  const [searchQuery, setSearchQuery] = useState('')
  const [expandedToken, setExpandedToken] = useState(null)
  const [sortBy, setSortBy] = useState('sentiment')
  const [refreshing, setRefreshing] = useState(false)

  const handleRefresh = useCallback(() => {
    setRefreshing(true)
    setTimeout(() => setRefreshing(false), 1500)
  }, [])

  const filteredTokens = useMemo(() => {
    let result = [...tokens]

    if (searchQuery) {
      const query = searchQuery.toLowerCase()
      result = result.filter(t =>
        t.symbol.toLowerCase().includes(query) ||
        t.name.toLowerCase().includes(query)
      )
    }

    switch (sortBy) {
      case 'sentiment':
        result.sort((a, b) => b.sentimentScore - a.sentimentScore)
        break
      case 'change':
        result.sort((a, b) => b.sentimentChange24h - a.sentimentChange24h)
        break
      case 'mentions':
        result.sort((a, b) => b.mentions24h - a.mentions24h)
        break
      case 'engagement':
        result.sort((a, b) => b.engagement24h - a.engagement24h)
        break
    }

    return result
  }, [tokens, searchQuery, sortBy])

  return (
    <div className="min-h-screen bg-[#0a0e14] text-white p-6">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-bold flex items-center gap-3">
              <MessageSquare className="w-7 h-7 text-blue-400" />
              Social Sentiment
            </h1>
            <p className="text-gray-400 mt-1">Track crypto sentiment across social platforms</p>
          </div>

          <div className="flex items-center gap-3">
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

        {/* Main grid */}
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
          {/* Token sentiment list */}
          <div className="lg:col-span-3 space-y-4">
            {/* Filters */}
            <div className="flex items-center gap-4 mb-4">
              <div className="relative flex-1 max-w-md">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                <input
                  type="text"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="Search tokens..."
                  className="w-full bg-white/5 border border-white/10 rounded-lg pl-10 pr-4 py-2 text-white placeholder-gray-500 focus:outline-none focus:border-blue-500/50"
                />
              </div>

              <select
                value={sortBy}
                onChange={(e) => setSortBy(e.target.value)}
                className="bg-white/5 border border-white/10 rounded-lg px-4 py-2 text-white"
              >
                <option value="sentiment">Highest Sentiment</option>
                <option value="change">Biggest Change</option>
                <option value="mentions">Most Mentions</option>
                <option value="engagement">Most Engagement</option>
              </select>
            </div>

            {filteredTokens.map(token => (
              <TokenSentimentCard
                key={token.symbol}
                token={token}
                expanded={expandedToken === token.symbol}
                onExpand={setExpandedToken}
              />
            ))}
          </div>

          {/* Sidebar */}
          <div className="space-y-6">
            <MarketSentiment tokens={tokens} />
            <SentimentMovers tokens={tokens} />
          </div>
        </div>

        {/* Trending posts */}
        <div className="mt-8">
          <h2 className="text-lg font-medium mb-4 flex items-center gap-2">
            <Flame className="w-5 h-5 text-orange-400" />
            Trending Posts
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {posts.map(post => (
              <TrendingPostCard key={post.id} post={post} />
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}

export default SocialSentiment
