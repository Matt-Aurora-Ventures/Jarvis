import React, { useState, useEffect, useCallback, useMemo } from 'react'
import {
  Brain, Zap, TrendingUp, TrendingDown, AlertCircle, RefreshCw, ChevronRight,
  ThumbsUp, ThumbsDown, Target, Shield, Clock, Activity, Star, Eye,
  BarChart3, ArrowUpRight, ArrowDownRight, Lightbulb, Sparkles, Check, X
} from 'lucide-react'

/**
 * AISuggestions - AI-powered trading suggestions
 *
 * Features:
 * - AI-generated trade ideas
 * - Risk/Reward analysis
 * - Confidence scoring
 * - Technical indicators summary
 * - Sentiment analysis integration
 * - Feedback learning
 */

// Suggestion types
const SUGGESTION_TYPES = {
  BUY: { label: 'Buy', color: 'green', icon: TrendingUp },
  SELL: { label: 'Sell', color: 'red', icon: TrendingDown },
  HOLD: { label: 'Hold', color: 'yellow', icon: Clock },
  AVOID: { label: 'Avoid', color: 'gray', icon: AlertCircle },
  WATCH: { label: 'Watch', color: 'blue', icon: Eye },
}

// Confidence levels
const CONFIDENCE_LEVELS = {
  HIGH: { label: 'High', color: 'green', min: 80 },
  MEDIUM: { label: 'Medium', color: 'yellow', min: 50 },
  LOW: { label: 'Low', color: 'red', min: 0 },
}

/**
 * ConfidenceBar - Visual confidence indicator
 */
function ConfidenceBar({ confidence, size = 'md' }) {
  const level = confidence >= 80 ? CONFIDENCE_LEVELS.HIGH
    : confidence >= 50 ? CONFIDENCE_LEVELS.MEDIUM
    : CONFIDENCE_LEVELS.LOW

  const heights = { sm: 'h-1', md: 'h-1.5', lg: 'h-2' }

  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between text-xs">
        <span className="text-gray-400">Confidence</span>
        <span className={`text-${level.color}-400 font-medium`}>{confidence}%</span>
      </div>
      <div className={`${heights[size]} bg-gray-800 rounded-full overflow-hidden`}>
        <div
          className={`h-full bg-${level.color}-500 transition-all duration-500`}
          style={{ width: `${confidence}%` }}
        />
      </div>
    </div>
  )
}

/**
 * RiskRewardCard - Display risk/reward metrics
 */
function RiskRewardCard({ riskReward, className = '' }) {
  const ratio = riskReward.reward / riskReward.risk

  return (
    <div className={`bg-gray-800/50 rounded-lg p-3 ${className}`}>
      <div className="flex items-center justify-between mb-2">
        <span className="text-sm text-gray-400">Risk/Reward</span>
        <span className={`text-sm font-medium ${ratio >= 2 ? 'text-green-400' : ratio >= 1 ? 'text-yellow-400' : 'text-red-400'}`}>
          1:{ratio.toFixed(1)}
        </span>
      </div>

      <div className="grid grid-cols-2 gap-2 text-xs">
        <div className="flex items-center justify-between">
          <span className="text-red-400 flex items-center gap-1">
            <Shield className="w-3 h-3" />
            Risk
          </span>
          <span className="text-white">{riskReward.risk.toFixed(1)}%</span>
        </div>
        <div className="flex items-center justify-between">
          <span className="text-green-400 flex items-center gap-1">
            <Target className="w-3 h-3" />
            Reward
          </span>
          <span className="text-white">{riskReward.reward.toFixed(1)}%</span>
        </div>
      </div>
    </div>
  )
}

/**
 * IndicatorSummary - Technical indicators summary
 */
function IndicatorSummary({ indicators }) {
  if (!indicators || indicators.length === 0) return null

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2 text-sm text-gray-400">
        <BarChart3 className="w-4 h-4" />
        Indicators
      </div>
      <div className="flex flex-wrap gap-2">
        {indicators.map((indicator, i) => (
          <div
            key={i}
            className={`flex items-center gap-1.5 px-2 py-1 rounded-lg text-xs ${
              indicator.signal === 'bullish' ? 'bg-green-500/10 text-green-400' :
              indicator.signal === 'bearish' ? 'bg-red-500/10 text-red-400' :
              'bg-gray-800 text-gray-400'
            }`}
          >
            <span className="font-medium">{indicator.name}</span>
            <span className="opacity-70">{indicator.value}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

/**
 * SuggestionCard - Single AI suggestion
 */
function SuggestionCard({
  suggestion,
  onFeedback,
  onAction,
  expanded = false,
  className = '',
}) {
  const [isExpanded, setIsExpanded] = useState(expanded)
  const [feedbackGiven, setFeedbackGiven] = useState(null)

  const type = SUGGESTION_TYPES[suggestion.type.toUpperCase()] || SUGGESTION_TYPES.WATCH

  const handleFeedback = useCallback((positive) => {
    setFeedbackGiven(positive)
    onFeedback?.(suggestion.id, positive)
  }, [suggestion.id, onFeedback])

  return (
    <div className={`bg-gray-900/50 rounded-xl border border-gray-800 overflow-hidden ${className}`}>
      {/* Header */}
      <div
        onClick={() => setIsExpanded(!isExpanded)}
        className="flex items-center gap-4 p-4 cursor-pointer hover:bg-gray-800/30"
      >
        {/* Token info */}
        <div className="flex items-center gap-3 flex-1">
          <div className={`w-10 h-10 rounded-full bg-${type.color}-500/10 flex items-center justify-center`}>
            <type.icon className={`w-5 h-5 text-${type.color}-400`} />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-semibold text-white">{suggestion.symbol}</span>
              <span className={`px-2 py-0.5 rounded text-xs bg-${type.color}-500/10 text-${type.color}-400`}>
                {type.label}
              </span>
              {suggestion.isNew && (
                <Sparkles className="w-3 h-3 text-yellow-400" />
              )}
            </div>
            <div className="text-sm text-gray-400">{suggestion.name}</div>
          </div>
        </div>

        {/* Confidence */}
        <div className="w-32">
          <ConfidenceBar confidence={suggestion.confidence} size="sm" />
        </div>

        {/* Price */}
        <div className="text-right">
          <div className="font-medium text-white">
            ${suggestion.price?.toFixed(suggestion.price > 1 ? 4 : 8)}
          </div>
          <div className={`text-sm ${suggestion.change24h >= 0 ? 'text-green-400' : 'text-red-400'}`}>
            {suggestion.change24h >= 0 ? '+' : ''}{suggestion.change24h?.toFixed(2)}%
          </div>
        </div>

        {/* Expand icon */}
        <ChevronRight className={`w-5 h-5 text-gray-500 transition-transform ${isExpanded ? 'rotate-90' : ''}`} />
      </div>

      {/* Expanded content */}
      {isExpanded && (
        <div className="px-4 pb-4 space-y-4">
          {/* AI Analysis */}
          <div className="bg-gradient-to-r from-purple-500/5 to-cyan-500/5 border border-purple-500/20 rounded-lg p-4">
            <div className="flex items-center gap-2 mb-2">
              <Brain className="w-4 h-4 text-purple-400" />
              <span className="text-sm font-medium text-purple-400">JARVIS Analysis</span>
            </div>
            <p className="text-sm text-gray-300 leading-relaxed">
              {suggestion.analysis}
            </p>
          </div>

          {/* Metrics row */}
          <div className="grid grid-cols-3 gap-3">
            {/* Risk/Reward */}
            {suggestion.riskReward && (
              <RiskRewardCard riskReward={suggestion.riskReward} />
            )}

            {/* Entry/Target */}
            <div className="bg-gray-800/50 rounded-lg p-3">
              <div className="text-sm text-gray-400 mb-2">Entry Zone</div>
              <div className="text-white font-medium">
                ${suggestion.entryLow?.toFixed(6)} - ${suggestion.entryHigh?.toFixed(6)}
              </div>
            </div>

            {/* Targets */}
            <div className="bg-gray-800/50 rounded-lg p-3">
              <div className="text-sm text-gray-400 mb-2">Targets</div>
              <div className="space-y-1">
                {suggestion.targets?.map((target, i) => (
                  <div key={i} className="flex items-center justify-between text-xs">
                    <span className="text-gray-500">T{i + 1}</span>
                    <span className="text-green-400">${target.toFixed(6)}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Indicators */}
          <IndicatorSummary indicators={suggestion.indicators} />

          {/* Reasons */}
          {suggestion.reasons && suggestion.reasons.length > 0 && (
            <div className="space-y-2">
              <div className="flex items-center gap-2 text-sm text-gray-400">
                <Lightbulb className="w-4 h-4" />
                Key Reasons
              </div>
              <ul className="space-y-1">
                {suggestion.reasons.map((reason, i) => (
                  <li key={i} className="flex items-start gap-2 text-sm text-gray-300">
                    <Check className="w-4 h-4 text-green-400 mt-0.5 flex-shrink-0" />
                    {reason}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Risks */}
          {suggestion.risks && suggestion.risks.length > 0 && (
            <div className="space-y-2">
              <div className="flex items-center gap-2 text-sm text-gray-400">
                <AlertCircle className="w-4 h-4" />
                Risk Factors
              </div>
              <ul className="space-y-1">
                {suggestion.risks.map((risk, i) => (
                  <li key={i} className="flex items-start gap-2 text-sm text-gray-300">
                    <X className="w-4 h-4 text-red-400 mt-0.5 flex-shrink-0" />
                    {risk}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Actions */}
          <div className="flex items-center justify-between pt-3 border-t border-gray-800">
            {/* Feedback */}
            <div className="flex items-center gap-2">
              <span className="text-xs text-gray-500">Was this helpful?</span>
              <button
                onClick={() => handleFeedback(true)}
                disabled={feedbackGiven !== null}
                className={`p-1.5 rounded transition-colors ${
                  feedbackGiven === true
                    ? 'bg-green-500/20 text-green-400'
                    : feedbackGiven !== null
                    ? 'text-gray-600'
                    : 'hover:bg-gray-800 text-gray-400'
                }`}
              >
                <ThumbsUp className="w-4 h-4" />
              </button>
              <button
                onClick={() => handleFeedback(false)}
                disabled={feedbackGiven !== null}
                className={`p-1.5 rounded transition-colors ${
                  feedbackGiven === false
                    ? 'bg-red-500/20 text-red-400'
                    : feedbackGiven !== null
                    ? 'text-gray-600'
                    : 'hover:bg-gray-800 text-gray-400'
                }`}
              >
                <ThumbsDown className="w-4 h-4" />
              </button>
            </div>

            {/* Action buttons */}
            <div className="flex items-center gap-2">
              {suggestion.type.toLowerCase() === 'buy' && (
                <button
                  onClick={() => onAction?.('buy', suggestion)}
                  className="flex items-center gap-2 px-4 py-2 bg-green-500 rounded-lg text-white text-sm hover:bg-green-600"
                >
                  <ArrowUpRight className="w-4 h-4" />
                  Execute Buy
                </button>
              )}
              {suggestion.type.toLowerCase() === 'sell' && (
                <button
                  onClick={() => onAction?.('sell', suggestion)}
                  className="flex items-center gap-2 px-4 py-2 bg-red-500 rounded-lg text-white text-sm hover:bg-red-600"
                >
                  <ArrowDownRight className="w-4 h-4" />
                  Execute Sell
                </button>
              )}
              <button
                onClick={() => onAction?.('watch', suggestion)}
                className="flex items-center gap-2 px-3 py-2 bg-gray-800 rounded-lg text-gray-300 text-sm hover:bg-gray-700"
              >
                <Eye className="w-4 h-4" />
                Add to Watchlist
              </button>
            </div>
          </div>

          {/* Timestamp */}
          <div className="flex items-center gap-1 text-xs text-gray-500">
            <Clock className="w-3 h-3" />
            Generated {new Date(suggestion.timestamp).toLocaleString()}
          </div>
        </div>
      )}
    </div>
  )
}

/**
 * Main AISuggestions Component
 */
export function AISuggestions({
  suggestions = [],
  onRefresh,
  onFeedback,
  onAction,
  isLoading = false,
  className = '',
}) {
  const [filter, setFilter] = useState('all') // all, buy, sell, watch
  const [sortBy, setSortBy] = useState('confidence') // confidence, change, time

  // Filter and sort suggestions
  const filteredSuggestions = useMemo(() => {
    let filtered = suggestions

    if (filter !== 'all') {
      filtered = filtered.filter(s => s.type.toLowerCase() === filter)
    }

    // Sort
    if (sortBy === 'confidence') {
      filtered.sort((a, b) => b.confidence - a.confidence)
    } else if (sortBy === 'change') {
      filtered.sort((a, b) => Math.abs(b.change24h) - Math.abs(a.change24h))
    } else if (sortBy === 'time') {
      filtered.sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp))
    }

    return filtered
  }, [suggestions, filter, sortBy])

  // Stats
  const stats = useMemo(() => {
    const buyCount = suggestions.filter(s => s.type.toLowerCase() === 'buy').length
    const sellCount = suggestions.filter(s => s.type.toLowerCase() === 'sell').length
    const avgConfidence = suggestions.length > 0
      ? suggestions.reduce((sum, s) => sum + s.confidence, 0) / suggestions.length
      : 0

    return { buyCount, sellCount, avgConfidence }
  }, [suggestions])

  return (
    <div className={className}>
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-gradient-to-br from-purple-500/20 to-cyan-500/20 rounded-lg">
            <Brain className="w-6 h-6 text-purple-400" />
          </div>
          <div>
            <h2 className="text-xl font-bold text-white">AI Trade Suggestions</h2>
            <p className="text-sm text-gray-400">Powered by JARVIS market analysis</p>
          </div>
        </div>

        <button
          onClick={onRefresh}
          disabled={isLoading}
          className="flex items-center gap-2 px-4 py-2 bg-purple-500/20 border border-purple-500/30 rounded-lg text-purple-400 hover:bg-purple-500/30 disabled:opacity-50"
        >
          <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
          {isLoading ? 'Analyzing...' : 'Refresh'}
        </button>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-4 gap-4 mb-6">
        <div className="bg-gray-900/50 rounded-lg border border-gray-800 p-4">
          <div className="text-sm text-gray-400 mb-1">Total Suggestions</div>
          <div className="text-2xl font-bold text-white">{suggestions.length}</div>
        </div>
        <div className="bg-gray-900/50 rounded-lg border border-gray-800 p-4">
          <div className="text-sm text-gray-400 mb-1">Buy Signals</div>
          <div className="text-2xl font-bold text-green-400">{stats.buyCount}</div>
        </div>
        <div className="bg-gray-900/50 rounded-lg border border-gray-800 p-4">
          <div className="text-sm text-gray-400 mb-1">Sell Signals</div>
          <div className="text-2xl font-bold text-red-400">{stats.sellCount}</div>
        </div>
        <div className="bg-gray-900/50 rounded-lg border border-gray-800 p-4">
          <div className="text-sm text-gray-400 mb-1">Avg Confidence</div>
          <div className="text-2xl font-bold text-purple-400">{stats.avgConfidence.toFixed(0)}%</div>
        </div>
      </div>

      {/* Filters */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          {['all', 'buy', 'sell', 'watch'].map(f => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={`px-3 py-1.5 rounded-lg text-sm transition-colors ${
                filter === f
                  ? f === 'buy' ? 'bg-green-500/20 text-green-400'
                  : f === 'sell' ? 'bg-red-500/20 text-red-400'
                  : f === 'watch' ? 'bg-blue-500/20 text-blue-400'
                  : 'bg-gray-700 text-white'
                  : 'text-gray-400 hover:text-white'
              }`}
            >
              {f.charAt(0).toUpperCase() + f.slice(1)}
            </button>
          ))}
        </div>

        <select
          value={sortBy}
          onChange={(e) => setSortBy(e.target.value)}
          className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-1.5 text-sm text-white"
        >
          <option value="confidence">Sort by Confidence</option>
          <option value="change">Sort by Change</option>
          <option value="time">Sort by Time</option>
        </select>
      </div>

      {/* Suggestions list */}
      {isLoading ? (
        <div className="flex flex-col items-center justify-center py-16">
          <div className="relative">
            <Brain className="w-12 h-12 text-purple-400 animate-pulse" />
            <Sparkles className="w-4 h-4 text-yellow-400 absolute -top-1 -right-1 animate-ping" />
          </div>
          <p className="text-gray-400 mt-4">JARVIS is analyzing the market...</p>
          <p className="text-sm text-gray-500">This may take a moment</p>
        </div>
      ) : filteredSuggestions.length === 0 ? (
        <div className="text-center py-16">
          <Brain className="w-12 h-12 text-gray-600 mx-auto mb-4" />
          <h3 className="text-lg font-medium text-gray-400 mb-2">No Suggestions Available</h3>
          <p className="text-sm text-gray-500 mb-4">
            {suggestions.length === 0
              ? 'Click refresh to generate AI trading suggestions'
              : 'No suggestions match your filter'}
          </p>
          <button
            onClick={onRefresh}
            className="inline-flex items-center gap-2 px-4 py-2 bg-purple-500 rounded-lg text-white hover:bg-purple-600"
          >
            <Zap className="w-4 h-4" />
            Generate Suggestions
          </button>
        </div>
      ) : (
        <div className="space-y-4">
          {filteredSuggestions.map(suggestion => (
            <SuggestionCard
              key={suggestion.id}
              suggestion={suggestion}
              onFeedback={onFeedback}
              onAction={onAction}
            />
          ))}
        </div>
      )}

      {/* Disclaimer */}
      <div className="mt-6 p-4 bg-yellow-500/5 border border-yellow-500/20 rounded-lg">
        <div className="flex items-start gap-3">
          <AlertCircle className="w-5 h-5 text-yellow-400 flex-shrink-0 mt-0.5" />
          <div className="text-sm text-gray-400">
            <p className="font-medium text-yellow-400 mb-1">Disclaimer</p>
            <p>
              AI suggestions are for informational purposes only and should not be considered financial advice.
              Always do your own research and never invest more than you can afford to lose.
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}

export default AISuggestions
