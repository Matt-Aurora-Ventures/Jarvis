import React, { useCallback, useEffect, useMemo, useState } from 'react'
import {
  Activity,
  Flame,
  Globe,
  MessageSquare,
  RefreshCw,
  Search,
  TrendingDown,
  TrendingUp,
  Twitter,
  Users,
} from 'lucide-react'

const PLATFORM_META = {
  TWITTER: { label: 'X/Twitter', icon: Twitter, color: '#1DA1F2' },
  TELEGRAM: { label: 'Telegram', icon: MessageSquare, color: '#0088cc' },
  DISCORD: { label: 'Discord', icon: Users, color: '#5865F2' },
  REDDIT: { label: 'Reddit', icon: Globe, color: '#FF4500' },
}

function formatCompact(value) {
  if (!Number.isFinite(value)) return '--'
  if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`
  if (value >= 1_000) return `${(value / 1_000).toFixed(1)}K`
  return `${Math.round(value)}`
}

function sentimentTone(score) {
  if (score >= 75) return { label: 'Very Bullish', color: 'text-green-400' }
  if (score >= 60) return { label: 'Bullish', color: 'text-emerald-400' }
  if (score >= 40) return { label: 'Neutral', color: 'text-slate-400' }
  if (score >= 25) return { label: 'Bearish', color: 'text-orange-400' }
  return { label: 'Very Bearish', color: 'text-red-400' }
}

function formatAge(unixTs) {
  if (!unixTs) return '--'
  const diff = Math.max(0, Math.floor(Date.now() / 1000 - unixTs))
  if (diff < 60) return `${diff}s ago`
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`
  return `${Math.floor(diff / 86400)}d ago`
}

export const SocialSentiment = () => {
  const [payload, setPayload] = useState({ tokens: [], posts: [], overall_score: 0, source: 'unknown' })
  const [sortBy, setSortBy] = useState('sentiment')
  const [query, setQuery] = useState('')
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState(null)

  const fetchData = useCallback(async () => {
    setRefreshing(true)
    try {
      const response = await fetch('/api/intel/sentiment?token_limit=8&post_limit=10')
      if (!response.ok) throw new Error(`HTTP ${response.status}`)
      const data = await response.json()
      setPayload(data)
      setError(null)
    } catch (err) {
      setError(err?.message || 'Failed to load sentiment data')
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }, [])

  useEffect(() => {
    fetchData()
    const timer = setInterval(fetchData, 10000)
    return () => clearInterval(timer)
  }, [fetchData])

  const tokens = useMemo(() => {
    const list = Array.isArray(payload.tokens) ? [...payload.tokens] : []
    let filtered = list
    if (query.trim()) {
      const term = query.toLowerCase()
      filtered = filtered.filter(
        (token) =>
          token.symbol?.toLowerCase().includes(term) ||
          token.name?.toLowerCase().includes(term),
      )
    }
    filtered.sort((left, right) => {
      if (sortBy === 'change') return (right.sentiment_change_24h || 0) - (left.sentiment_change_24h || 0)
      if (sortBy === 'mentions') return (right.mentions_24h || 0) - (left.mentions_24h || 0)
      if (sortBy === 'engagement') return (right.engagement_24h || 0) - (left.engagement_24h || 0)
      return (right.sentiment_score || 0) - (left.sentiment_score || 0)
    })
    return filtered
  }, [payload.tokens, query, sortBy])

  const posts = Array.isArray(payload.posts) ? payload.posts : []
  const overall = Number(payload.overall_score || 0)
  const overallTone = sentimentTone(overall)

  return (
    <div className="min-h-screen bg-[#0a0e14] text-white p-6">
      <div className="max-w-7xl mx-auto space-y-6">
        <header className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold flex items-center gap-2">
              <MessageSquare className="w-6 h-6 text-blue-400" />
              Social Sentiment
            </h1>
            <p className="text-sm text-slate-400">Live sentiment and social flow feed from backend intelligence APIs.</p>
          </div>
          <button
            onClick={fetchData}
            className={`p-2 rounded-lg bg-white/5 border border-white/10 hover:bg-white/10 ${refreshing ? 'animate-spin' : ''}`}
            title="Refresh"
          >
            <RefreshCw className="w-5 h-5" />
          </button>
        </header>

        {error ? (
          <div className="rounded-lg border border-yellow-500/30 bg-yellow-500/10 px-4 py-3 text-yellow-200 text-sm">
            {error}
          </div>
        ) : null}

        <section className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="rounded-lg border border-white/10 bg-white/5 p-4">
            <div className="text-xs text-slate-500">Overall score</div>
            <div className={`text-3xl font-bold ${overallTone.color}`}>{overall.toFixed(1)}</div>
            <div className="text-sm text-slate-400">{overallTone.label}</div>
          </div>
          <div className="rounded-lg border border-white/10 bg-white/5 p-4">
            <div className="text-xs text-slate-500">Tracked tokens</div>
            <div className="text-3xl font-bold">{tokens.length}</div>
            <div className="text-sm text-slate-400">source: {payload.source || 'unknown'}</div>
          </div>
          <div className="rounded-lg border border-white/10 bg-white/5 p-4">
            <div className="text-xs text-slate-500">Trending posts</div>
            <div className="text-3xl font-bold">{posts.length}</div>
            <div className="text-sm text-slate-400">updated continuously</div>
          </div>
        </section>

        <section className="flex flex-wrap items-center gap-3">
          <div className="relative flex-1 min-w-[240px] max-w-lg">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search tokens"
              className="w-full bg-white/5 border border-white/10 rounded-lg pl-10 pr-4 py-2 text-sm placeholder:text-slate-500 focus:outline-none focus:border-blue-500/50"
            />
          </div>
          <select
            value={sortBy}
            onChange={(event) => setSortBy(event.target.value)}
            className="bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-sm"
          >
            <option value="sentiment">Highest sentiment</option>
            <option value="change">Biggest change</option>
            <option value="mentions">Most mentions</option>
            <option value="engagement">Most engagement</option>
          </select>
        </section>

        {loading ? (
          <div className="rounded-lg border border-white/10 bg-white/5 p-10 text-center text-slate-400">
            Loading social sentiment...
          </div>
        ) : (
          <section className="grid lg:grid-cols-4 gap-6">
            <div className="lg:col-span-3 space-y-3">
              {tokens.map((token) => {
                const tone = sentimentTone(Number(token.sentiment_score || 0))
                const delta = Number(token.sentiment_change_24h || 0)
                return (
                  <div key={token.symbol} className="rounded-lg border border-white/10 bg-white/5 p-4">
                    <div className="flex items-center justify-between">
                      <div>
                        <div className="text-lg font-semibold">
                          {token.symbol} <span className="text-sm text-slate-400">{token.name}</span>
                        </div>
                        <div className={`text-sm ${tone.color}`}>{tone.label}</div>
                      </div>
                      <div className="text-right">
                        <div className={`text-xl font-bold ${tone.color}`}>{token.sentiment_score}</div>
                        <div className={`text-xs flex items-center justify-end gap-1 ${delta >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                          {delta >= 0 ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
                          {delta >= 0 ? '+' : ''}
                          {delta.toFixed(2)}% 24h
                        </div>
                      </div>
                    </div>
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mt-3 text-xs">
                      <Stat label="Mentions" value={formatCompact(Number(token.mentions_24h || 0))} />
                      <Stat label="Engagement" value={formatCompact(Number(token.engagement_24h || 0))} />
                      <Stat label="Influencers" value={`${Math.round(token.top_influencers || 0)}`} />
                      <PlatformStat platforms={token.platforms || {}} />
                    </div>
                  </div>
                )
              })}
            </div>
            <div className="space-y-3">
              <div className="rounded-lg border border-white/10 bg-white/5 p-4">
                <h3 className="font-medium mb-3 flex items-center gap-2">
                  <Flame className="w-4 h-4 text-orange-400" />
                  Trending Posts
                </h3>
                <div className="space-y-2">
                  {posts.map((post) => (
                    <PostCard key={post.id} post={post} />
                  ))}
                </div>
              </div>
            </div>
          </section>
        )}
      </div>
    </div>
  )
}

function Stat({ label, value }) {
  return (
    <div>
      <div className="text-slate-500">{label}</div>
      <div className="font-medium">{value}</div>
    </div>
  )
}

function PlatformStat({ platforms }) {
  const strongest = Object.entries(platforms).sort((left, right) => (right[1]?.sentiment || 0) - (left[1]?.sentiment || 0))[0]
  if (!strongest) {
    return <Stat label="Top Platform" value="--" />
  }
  const [platform, values] = strongest
  return <Stat label="Top Platform" value={`${platform}:${values.sentiment}`} />
}

function PostCard({ post }) {
  const platform = PLATFORM_META[post.platform] || { label: post.platform || 'Unknown', icon: Activity, color: '#94a3b8' }
  const Icon = platform.icon
  const sentimentClass = post.sentiment === 'BEARISH' ? 'text-red-400' : 'text-green-400'
  return (
    <div className="rounded border border-white/10 bg-white/5 p-3 text-xs">
      <div className="flex items-center justify-between mb-1">
        <div className="flex items-center gap-2">
          <Icon className="w-3 h-3" style={{ color: platform.color }} />
          <span className="text-slate-400">{platform.label}</span>
        </div>
        <span className="text-slate-500">{formatAge(post.timestamp)}</span>
      </div>
      <div className="text-slate-200 line-clamp-3">{post.content}</div>
      <div className="mt-2 flex items-center justify-between">
        <span className={sentimentClass}>{post.sentiment}</span>
        <span className="text-slate-500">
          {formatCompact(post.likes || 0)} likes
        </span>
      </div>
    </div>
  )
}

export default SocialSentiment
