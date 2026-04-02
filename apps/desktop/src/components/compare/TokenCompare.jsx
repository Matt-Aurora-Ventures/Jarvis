import React, { useState, useEffect, useMemo, useCallback } from 'react'
import {
  GitCompare,
  Plus,
  X,
  Search,
  TrendingUp,
  TrendingDown,
  DollarSign,
  BarChart3,
  Activity,
  Users,
  Droplets,
  Clock,
  ExternalLink,
  ArrowUpRight,
  ArrowDownRight,
  ChevronDown,
  ChevronUp,
  Percent,
  Target,
  Shield,
  Zap,
  Award,
  Info,
  RefreshCw,
  Download,
  Share2
} from 'lucide-react'

// Metrics for comparison
const COMPARISON_METRICS = {
  price: { label: 'Price', format: 'currency', icon: DollarSign },
  marketCap: { label: 'Market Cap', format: 'currency', icon: BarChart3 },
  volume24h: { label: '24h Volume', format: 'currency', icon: Activity },
  liquidity: { label: 'Liquidity', format: 'currency', icon: Droplets },
  holders: { label: 'Holders', format: 'number', icon: Users },
  change1h: { label: '1H Change', format: 'percent', icon: Clock },
  change24h: { label: '24H Change', format: 'percent', icon: TrendingUp },
  change7d: { label: '7D Change', format: 'percent', icon: TrendingUp },
  change30d: { label: '30D Change', format: 'percent', icon: TrendingUp },
  fdv: { label: 'FDV', format: 'currency', icon: Target },
  circulatingSupply: { label: 'Circulating Supply', format: 'number', icon: Activity },
  totalSupply: { label: 'Total Supply', format: 'number', icon: Activity },
  ath: { label: 'All-Time High', format: 'currency', icon: Award },
  athChange: { label: 'From ATH', format: 'percent', icon: TrendingDown },
  age: { label: 'Token Age', format: 'days', icon: Clock },
}

// Helper functions
function formatValue(value, format) {
  if (value === undefined || value === null) return 'N/A'

  switch (format) {
    case 'currency':
      if (value >= 1000000000) return `$${(value / 1000000000).toFixed(2)}B`
      if (value >= 1000000) return `$${(value / 1000000).toFixed(2)}M`
      if (value >= 1000) return `$${(value / 1000).toFixed(2)}K`
      if (value < 0.01) return `$${value.toFixed(8)}`
      return `$${value.toFixed(2)}`

    case 'percent':
      const sign = value >= 0 ? '+' : ''
      return `${sign}${value.toFixed(2)}%`

    case 'number':
      if (value >= 1000000000) return `${(value / 1000000000).toFixed(2)}B`
      if (value >= 1000000) return `${(value / 1000000).toFixed(2)}M`
      if (value >= 1000) return `${(value / 1000).toFixed(2)}K`
      return value.toLocaleString()

    case 'days':
      return `${value} days`

    default:
      return String(value)
  }
}

function getComparisonClass(value, format, isWinner) {
  if (format === 'percent') {
    if (value > 0) return 'text-green-400'
    if (value < 0) return 'text-red-400'
    return 'text-gray-400'
  }

  if (isWinner) return 'text-green-400 font-bold'
  return ''
}

// Token Search/Add Component
function TokenSearchModal({ isOpen, onClose, onSelect, existingTokens = [] }) {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState([])
  const [loading, setLoading] = useState(false)

  // Mock search results - in real app, this would be an API call
  const searchTokens = useCallback(async (searchQuery) => {
    setLoading(true)
    // Simulated search - replace with actual API
    await new Promise(resolve => setTimeout(resolve, 300))

    const mockResults = [
      { symbol: 'SOL', name: 'Solana', address: 'So11111111111111111111111111111111111111111' },
      { symbol: 'BONK', name: 'Bonk', address: 'DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263' },
      { symbol: 'JUP', name: 'Jupiter', address: 'JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN' },
      { symbol: 'PYTH', name: 'Pyth Network', address: 'HZ1JovNiVvGrGNiiYvEozEVgZ58xaU3RKwX8eACQBCt3' },
      { symbol: 'RAY', name: 'Raydium', address: '4k3Dyjzvzp8eMZWUXbBCjEvwSkkk59S5iCNLY3QrkX6R' },
      { symbol: 'ORCA', name: 'Orca', address: 'orcaEKTdK7LKz57vaAYr9QeNsVEPfiu6QeMU1kektZE' },
      { symbol: 'WIF', name: 'dogwifhat', address: 'EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm' },
      { symbol: 'RENDER', name: 'Render Token', address: 'rndrizKT3MK1iimdxRdWabcF7Zg7AR5T4nud4EkHBof' },
    ].filter(t =>
      t.symbol.toLowerCase().includes(searchQuery.toLowerCase()) ||
      t.name.toLowerCase().includes(searchQuery.toLowerCase())
    )

    setResults(mockResults)
    setLoading(false)
  }, [])

  useEffect(() => {
    if (query.length >= 1) {
      searchTokens(query)
    } else {
      setResults([])
    }
  }, [query, searchTokens])

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-gray-800 rounded-xl p-6 max-w-md w-full border border-gray-700">
        <div className="flex justify-between items-center mb-4">
          <h3 className="text-lg font-semibold">Add Token to Compare</h3>
          <button onClick={onClose} className="text-gray-400 hover:text-white">
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="relative mb-4">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
          <input
            type="text"
            value={query}
            onChange={e => setQuery(e.target.value)}
            placeholder="Search by name or symbol..."
            className="w-full pl-10 pr-4 py-2 bg-gray-900 border border-gray-700 rounded-lg"
            autoFocus
          />
        </div>

        <div className="max-h-60 overflow-y-auto space-y-1">
          {loading ? (
            <div className="text-center py-4 text-gray-400">Searching...</div>
          ) : results.length > 0 ? (
            results.map(token => {
              const isAdded = existingTokens.some(t => t.address === token.address)
              return (
                <button
                  key={token.address}
                  onClick={() => { onSelect(token); onClose() }}
                  disabled={isAdded}
                  className={`w-full flex items-center gap-3 p-2 rounded-lg ${
                    isAdded
                      ? 'bg-gray-700 opacity-50 cursor-not-allowed'
                      : 'bg-gray-900 hover:bg-gray-700'
                  }`}
                >
                  <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-purple-500 to-pink-500 flex items-center justify-center font-bold text-sm">
                    {token.symbol[0]}
                  </div>
                  <div className="text-left">
                    <div className="font-medium">{token.symbol}</div>
                    <div className="text-xs text-gray-400">{token.name}</div>
                  </div>
                  {isAdded && (
                    <span className="ml-auto text-xs text-gray-500">Added</span>
                  )}
                </button>
              )
            })
          ) : query.length >= 1 ? (
            <div className="text-center py-4 text-gray-400">No tokens found</div>
          ) : (
            <div className="text-center py-4 text-gray-400">Type to search...</div>
          )}
        </div>
      </div>
    </div>
  )
}

// Token Column Component
function TokenColumn({ token, metrics, onRemove, allTokens }) {
  // Find winner for each metric
  const isWinner = (metric) => {
    const values = allTokens.map(t => t[metric]).filter(v => v !== undefined && v !== null)
    if (values.length === 0) return false

    const metricInfo = COMPARISON_METRICS[metric]
    const tokenValue = token[metric]

    if (tokenValue === undefined || tokenValue === null) return false

    // For percent metrics, higher is better (for gains)
    // For other metrics, higher is generally better
    if (metric === 'athChange') {
      // Closest to ATH wins (least negative)
      return tokenValue === Math.max(...values)
    }

    return tokenValue === Math.max(...values)
  }

  return (
    <div className="flex-1 min-w-[200px]">
      {/* Token Header */}
      <div className="bg-gray-800 rounded-t-xl p-4 border border-gray-700 border-b-0">
        <div className="flex items-start justify-between mb-2">
          <div className="flex items-center gap-2">
            {token.logo ? (
              <img src={token.logo} alt={token.symbol} className="w-10 h-10 rounded-lg" />
            ) : (
              <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-purple-500 to-pink-500 flex items-center justify-center font-bold">
                {token.symbol?.[0]}
              </div>
            )}
            <div>
              <div className="font-bold">{token.symbol}</div>
              <div className="text-xs text-gray-400">{token.name}</div>
            </div>
          </div>
          <button
            onClick={() => onRemove(token.address)}
            className="text-gray-500 hover:text-red-400"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="text-2xl font-bold">{formatValue(token.price, 'currency')}</div>
        <div className={`text-sm flex items-center gap-1 ${
          (token.change24h || 0) >= 0 ? 'text-green-400' : 'text-red-400'
        }`}>
          {(token.change24h || 0) >= 0 ? (
            <ArrowUpRight className="w-4 h-4" />
          ) : (
            <ArrowDownRight className="w-4 h-4" />
          )}
          {formatValue(token.change24h, 'percent')}
        </div>
      </div>

      {/* Metrics */}
      <div className="bg-gray-900 rounded-b-xl border border-gray-700 border-t-0">
        {metrics.map((metric, i) => {
          const metricInfo = COMPARISON_METRICS[metric]
          if (!metricInfo) return null

          const value = token[metric]
          const winner = isWinner(metric)

          return (
            <div
              key={metric}
              className={`p-3 flex items-center justify-between ${
                i < metrics.length - 1 ? 'border-b border-gray-800' : ''
              } ${winner ? 'bg-green-500/5' : ''}`}
            >
              <span className="text-sm text-gray-400 flex items-center gap-1">
                <metricInfo.icon className="w-3 h-3" />
                {metricInfo.label}
              </span>
              <span className={`font-medium ${getComparisonClass(value, metricInfo.format, winner)}`}>
                {formatValue(value, metricInfo.format)}
                {winner && <Award className="w-3 h-3 inline ml-1 text-yellow-400" />}
              </span>
            </div>
          )
        })}
      </div>

      {/* External Links */}
      <div className="flex gap-2 mt-2">
        <a
          href={`https://dexscreener.com/solana/${token.address}`}
          target="_blank"
          rel="noopener noreferrer"
          className="flex-1 py-2 bg-gray-800 text-gray-300 rounded-lg hover:bg-gray-700 flex items-center justify-center gap-1 text-xs"
        >
          Chart <ExternalLink className="w-3 h-3" />
        </a>
        <a
          href={`https://birdeye.so/token/${token.address}`}
          target="_blank"
          rel="noopener noreferrer"
          className="flex-1 py-2 bg-gray-800 text-gray-300 rounded-lg hover:bg-gray-700 flex items-center justify-center gap-1 text-xs"
        >
          Birdeye <ExternalLink className="w-3 h-3" />
        </a>
      </div>
    </div>
  )
}

// Comparison Table Component (Alternative View)
function ComparisonTable({ tokens, metrics }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full">
        <thead>
          <tr className="border-b border-gray-700">
            <th className="text-left p-3 text-gray-400 font-medium">Metric</th>
            {tokens.map(token => (
              <th key={token.address} className="text-right p-3 font-medium">
                <div className="flex items-center justify-end gap-2">
                  {token.logo ? (
                    <img src={token.logo} alt={token.symbol} className="w-5 h-5 rounded" />
                  ) : (
                    <div className="w-5 h-5 rounded bg-gradient-to-br from-purple-500 to-pink-500 flex items-center justify-center text-xs font-bold">
                      {token.symbol?.[0]}
                    </div>
                  )}
                  {token.symbol}
                </div>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {metrics.map((metric, i) => {
            const metricInfo = COMPARISON_METRICS[metric]
            if (!metricInfo) return null

            // Find winner
            const values = tokens.map(t => ({ address: t.address, value: t[metric] }))
              .filter(v => v.value !== undefined && v.value !== null)
            const maxValue = values.length > 0 ? Math.max(...values.map(v => v.value)) : null
            const winnerAddress = metric === 'athChange'
              ? values.find(v => v.value === maxValue)?.address
              : values.find(v => v.value === maxValue)?.address

            return (
              <tr key={metric} className={`border-b border-gray-800 ${i % 2 === 0 ? 'bg-gray-900/50' : ''}`}>
                <td className="p-3 text-gray-400">
                  <div className="flex items-center gap-2">
                    <metricInfo.icon className="w-4 h-4" />
                    {metricInfo.label}
                  </div>
                </td>
                {tokens.map(token => {
                  const isWinner = token.address === winnerAddress
                  return (
                    <td
                      key={token.address}
                      className={`p-3 text-right ${
                        isWinner ? 'bg-green-500/10 font-bold' : ''
                      } ${getComparisonClass(token[metric], metricInfo.format, isWinner)}`}
                    >
                      {formatValue(token[metric], metricInfo.format)}
                      {isWinner && <Award className="w-3 h-3 inline ml-1 text-yellow-400" />}
                    </td>
                  )
                })}
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

// Main Token Compare Component
export function TokenCompare({
  initialTokens = [],
  onRefresh,
  isLoading = false,
}) {
  const [tokens, setTokens] = useState(initialTokens)
  const [showSearch, setShowSearch] = useState(false)
  const [viewMode, setViewMode] = useState('columns') // columns, table
  const [selectedMetrics, setSelectedMetrics] = useState([
    'price', 'marketCap', 'volume24h', 'liquidity',
    'change1h', 'change24h', 'change7d', 'change30d',
    'holders', 'fdv', 'athChange'
  ])

  // Update tokens when prop changes
  useEffect(() => {
    setTokens(initialTokens)
  }, [initialTokens])

  const addToken = useCallback((token) => {
    // In real app, fetch full token data here
    const mockFullToken = {
      ...token,
      price: Math.random() * 100,
      marketCap: Math.random() * 1000000000,
      volume24h: Math.random() * 100000000,
      liquidity: Math.random() * 50000000,
      holders: Math.floor(Math.random() * 100000),
      change1h: (Math.random() - 0.5) * 10,
      change24h: (Math.random() - 0.5) * 20,
      change7d: (Math.random() - 0.5) * 40,
      change30d: (Math.random() - 0.5) * 80,
      fdv: Math.random() * 2000000000,
      circulatingSupply: Math.random() * 1000000000,
      totalSupply: Math.random() * 2000000000,
      ath: Math.random() * 200,
      athChange: -(Math.random() * 90),
      age: Math.floor(Math.random() * 1000),
    }
    setTokens(prev => [...prev, mockFullToken])
  }, [])

  const removeToken = useCallback((address) => {
    setTokens(prev => prev.filter(t => t.address !== address))
  }, [])

  const toggleMetric = useCallback((metric) => {
    setSelectedMetrics(prev => {
      if (prev.includes(metric)) {
        return prev.filter(m => m !== metric)
      }
      return [...prev, metric]
    })
  }, [])

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-cyan-500/20 rounded-lg">
            <GitCompare className="w-6 h-6 text-cyan-400" />
          </div>
          <div>
            <h1 className="text-2xl font-bold">Token Compare</h1>
            <p className="text-sm text-gray-400">Compare tokens side by side</p>
          </div>
        </div>
        <div className="flex gap-2">
          <button
            onClick={onRefresh}
            disabled={isLoading}
            className="px-4 py-2 bg-gray-700 text-gray-300 rounded-lg hover:bg-gray-600 flex items-center gap-2"
          >
            <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
          </button>
          <button
            onClick={() => setShowSearch(true)}
            disabled={tokens.length >= 5}
            className="px-4 py-2 bg-cyan-500 text-white rounded-lg hover:bg-cyan-600 flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <Plus className="w-4 h-4" />
            Add Token
          </button>
        </div>
      </div>

      {/* View Mode Toggle & Metric Selection */}
      <div className="bg-gray-800 rounded-xl p-4 border border-gray-700">
        <div className="flex flex-wrap items-center gap-4">
          {/* View Mode */}
          <div className="flex bg-gray-700 rounded-lg p-1">
            <button
              onClick={() => setViewMode('columns')}
              className={`px-3 py-1.5 rounded text-sm ${
                viewMode === 'columns' ? 'bg-cyan-500 text-white' : 'text-gray-400 hover:text-white'
              }`}
            >
              Columns
            </button>
            <button
              onClick={() => setViewMode('table')}
              className={`px-3 py-1.5 rounded text-sm ${
                viewMode === 'table' ? 'bg-cyan-500 text-white' : 'text-gray-400 hover:text-white'
              }`}
            >
              Table
            </button>
          </div>

          <div className="flex-1" />

          {/* Metric Toggles */}
          <div className="flex items-center gap-2">
            <span className="text-sm text-gray-400">Metrics:</span>
            <div className="flex flex-wrap gap-1">
              {Object.entries(COMPARISON_METRICS).map(([key, { label }]) => (
                <button
                  key={key}
                  onClick={() => toggleMetric(key)}
                  className={`px-2 py-1 rounded text-xs ${
                    selectedMetrics.includes(key)
                      ? 'bg-cyan-500/20 text-cyan-400 border border-cyan-500/50'
                      : 'bg-gray-700 text-gray-400 border border-gray-600'
                  }`}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Empty State */}
      {tokens.length === 0 ? (
        <div className="text-center py-16 bg-gray-800 rounded-xl border border-gray-700">
          <GitCompare className="w-16 h-16 mx-auto mb-4 text-gray-600" />
          <h3 className="text-xl font-semibold mb-2">No tokens to compare</h3>
          <p className="text-gray-400 mb-4">Add at least 2 tokens to start comparing</p>
          <button
            onClick={() => setShowSearch(true)}
            className="px-6 py-2 bg-cyan-500 text-white rounded-lg hover:bg-cyan-600 inline-flex items-center gap-2"
          >
            <Plus className="w-4 h-4" />
            Add Token
          </button>
        </div>
      ) : (
        <>
          {/* Comparison View */}
          {viewMode === 'columns' ? (
            <div className="flex gap-4 overflow-x-auto pb-4">
              {tokens.map(token => (
                <TokenColumn
                  key={token.address}
                  token={token}
                  metrics={selectedMetrics}
                  onRemove={removeToken}
                  allTokens={tokens}
                />
              ))}

              {/* Add More Button */}
              {tokens.length < 5 && (
                <button
                  onClick={() => setShowSearch(true)}
                  className="flex-shrink-0 w-48 border-2 border-dashed border-gray-700 rounded-xl flex flex-col items-center justify-center gap-2 text-gray-500 hover:border-cyan-500 hover:text-cyan-400 transition-colors"
                  style={{ minHeight: '400px' }}
                >
                  <Plus className="w-8 h-8" />
                  <span>Add Token</span>
                </button>
              )}
            </div>
          ) : (
            <div className="bg-gray-800 rounded-xl border border-gray-700 overflow-hidden">
              <ComparisonTable tokens={tokens} metrics={selectedMetrics} />
            </div>
          )}

          {/* Quick Summary */}
          {tokens.length >= 2 && (
            <div className="bg-gray-800 rounded-xl p-4 border border-gray-700">
              <h3 className="font-semibold mb-3 flex items-center gap-2">
                <Info className="w-5 h-5 text-cyan-400" />
                Quick Insights
              </h3>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                <div>
                  <span className="text-gray-400">Highest Market Cap:</span>
                  <div className="font-medium">
                    {tokens.sort((a, b) => (b.marketCap || 0) - (a.marketCap || 0))[0]?.symbol}
                  </div>
                </div>
                <div>
                  <span className="text-gray-400">Best 24H Performance:</span>
                  <div className="font-medium text-green-400">
                    {tokens.sort((a, b) => (b.change24h || 0) - (a.change24h || 0))[0]?.symbol}
                    {' '}({formatValue(tokens.sort((a, b) => (b.change24h || 0) - (a.change24h || 0))[0]?.change24h, 'percent')})
                  </div>
                </div>
                <div>
                  <span className="text-gray-400">Most Holders:</span>
                  <div className="font-medium">
                    {tokens.sort((a, b) => (b.holders || 0) - (a.holders || 0))[0]?.symbol}
                  </div>
                </div>
                <div>
                  <span className="text-gray-400">Highest Liquidity:</span>
                  <div className="font-medium">
                    {tokens.sort((a, b) => (b.liquidity || 0) - (a.liquidity || 0))[0]?.symbol}
                  </div>
                </div>
              </div>
            </div>
          )}
        </>
      )}

      {/* Search Modal */}
      <TokenSearchModal
        isOpen={showSearch}
        onClose={() => setShowSearch(false)}
        onSelect={addToken}
        existingTokens={tokens}
      />
    </div>
  )
}

export default TokenCompare
