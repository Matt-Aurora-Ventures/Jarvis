import React, { useState, useMemo } from 'react'
import {
  Activity,
  TrendingUp,
  TrendingDown,
  BarChart3,
  Volume2,
  Users,
  DollarSign,
  Clock,
  RefreshCw,
  Info,
  ChevronDown,
  AlertTriangle,
  Zap,
  Smile,
  Frown,
  Meh,
  Target,
  Flame,
  Snowflake,
  Twitter,
  MessageCircle,
  Globe
} from 'lucide-react'

// Sentiment zones
const SENTIMENT_ZONES = {
  EXTREME_FEAR: { label: 'Extreme Fear', range: [0, 20], color: 'text-red-500', bg: 'bg-red-500', icon: Frown, advice: 'Potential buying opportunity' },
  FEAR: { label: 'Fear', range: [20, 40], color: 'text-orange-500', bg: 'bg-orange-500', icon: Frown, advice: 'Market is fearful' },
  NEUTRAL: { label: 'Neutral', range: [40, 60], color: 'text-yellow-500', bg: 'bg-yellow-500', icon: Meh, advice: 'Market is undecided' },
  GREED: { label: 'Greed', range: [60, 80], color: 'text-green-500', bg: 'bg-green-500', icon: Smile, advice: 'Market is greedy' },
  EXTREME_GREED: { label: 'Extreme Greed', range: [80, 100], color: 'text-emerald-500', bg: 'bg-emerald-500', icon: Smile, advice: 'Potential selling opportunity' }
}

// Index components
const INDEX_COMPONENTS = {
  VOLATILITY: { label: 'Volatility', icon: Activity, weight: 25, description: 'Market volatility compared to 30/90 day average' },
  MOMENTUM: { label: 'Market Momentum', icon: TrendingUp, weight: 25, description: 'Volume relative to recent averages' },
  VOLUME: { label: 'Trading Volume', icon: Volume2, weight: 15, description: '24h volume compared to 30 day average' },
  DOMINANCE: { label: 'BTC Dominance', icon: DollarSign, weight: 10, description: 'Bitcoin share of total market cap' },
  SOCIAL: { label: 'Social Sentiment', icon: Twitter, weight: 15, description: 'Social media mentions and sentiment' },
  TRENDS: { label: 'Search Trends', icon: Globe, weight: 10, description: 'Google trends for crypto keywords' }
}

// Mock data
const mockCurrentIndex = {
  value: 42,
  change24h: -5,
  change7d: 12,
  timestamp: Date.now()
}

const mockComponents = {
  VOLATILITY: { value: 35, change: -8, contribution: 8.75 },
  MOMENTUM: { value: 55, change: 12, contribution: 13.75 },
  VOLUME: { value: 48, change: -3, contribution: 7.2 },
  DOMINANCE: { value: 38, change: -2, contribution: 3.8 },
  SOCIAL: { value: 45, change: 8, contribution: 6.75 },
  TRENDS: { value: 28, change: -15, contribution: 2.8 }
}

const mockHistoricalData = {
  '24h': [45, 44, 43, 42, 41, 40, 39, 40, 41, 42, 43, 42, 41, 40, 39, 38, 39, 40, 41, 42, 43, 44, 43, 42],
  '7d': [35, 38, 42, 45, 50, 48, 42],
  '30d': [25, 30, 35, 42, 55, 60, 58, 52, 48, 45, 40, 38, 35, 32, 30, 35, 40, 45, 50, 55, 52, 48, 45, 42, 40, 38, 35, 38, 40, 42],
  '90d': Array.from({ length: 90 }, () => Math.floor(Math.random() * 60) + 20)
}

const mockHistoricalComparison = [
  { label: 'Now', value: 42 },
  { label: 'Yesterday', value: 47 },
  { label: 'Last Week', value: 30 },
  { label: 'Last Month', value: 65 },
  { label: 'Last Year', value: 28 }
]

// Get sentiment zone for a value
const getSentimentZone = (value) => {
  for (const [key, zone] of Object.entries(SENTIMENT_ZONES)) {
    if (value >= zone.range[0] && value < zone.range[1]) {
      return { key, ...zone }
    }
  }
  return { key: 'EXTREME_GREED', ...SENTIMENT_ZONES.EXTREME_GREED }
}

// Gauge component
const SentimentGauge = ({ value }) => {
  const zone = getSentimentZone(value)
  const IconComponent = zone.icon

  // Calculate needle rotation (0 = -90deg, 100 = 90deg)
  const rotation = (value / 100) * 180 - 90

  return (
    <div className="flex flex-col items-center">
      {/* Gauge container */}
      <div className="relative w-64 h-32 overflow-hidden">
        {/* Background arc */}
        <div className="absolute bottom-0 left-0 w-64 h-64 rounded-full border-[20px] border-white/5" style={{ clipPath: 'inset(50% 0 0 0)' }} />

        {/* Colored gradient arc */}
        <svg className="absolute bottom-0 left-0 w-64 h-32" viewBox="0 0 256 128" style={{ overflow: 'visible' }}>
          <defs>
            <linearGradient id="gaugeGradient" x1="0%" y1="0%" x2="100%" y2="0%">
              <stop offset="0%" stopColor="#ef4444" />
              <stop offset="25%" stopColor="#f97316" />
              <stop offset="50%" stopColor="#eab308" />
              <stop offset="75%" stopColor="#22c55e" />
              <stop offset="100%" stopColor="#10b981" />
            </linearGradient>
          </defs>
          <path
            d="M 20 128 A 108 108 0 0 1 236 128"
            fill="none"
            stroke="url(#gaugeGradient)"
            strokeWidth="20"
            strokeLinecap="round"
          />
        </svg>

        {/* Needle */}
        <div
          className="absolute bottom-0 left-1/2 w-1 h-24 bg-white rounded-full origin-bottom transition-transform duration-1000 ease-out"
          style={{ transform: `translateX(-50%) rotate(${rotation}deg)` }}
        />

        {/* Center cap */}
        <div className="absolute bottom-0 left-1/2 w-6 h-6 -translate-x-1/2 translate-y-1/2 bg-slate-800 rounded-full border-4 border-white/20 z-10" />

        {/* Zone labels */}
        <div className="absolute bottom-2 left-4 text-xs text-red-400">0</div>
        <div className="absolute bottom-12 left-12 text-xs text-orange-400">25</div>
        <div className="absolute bottom-16 left-1/2 -translate-x-1/2 text-xs text-yellow-400">50</div>
        <div className="absolute bottom-12 right-12 text-xs text-green-400">75</div>
        <div className="absolute bottom-2 right-4 text-xs text-emerald-400">100</div>
      </div>

      {/* Value display */}
      <div className="mt-6 text-center">
        <div className={`text-6xl font-bold ${zone.color}`}>{value}</div>
        <div className="flex items-center justify-center gap-2 mt-2">
          <IconComponent size={24} className={zone.color} />
          <span className={`text-xl font-medium ${zone.color}`}>{zone.label}</span>
        </div>
        <div className="text-sm text-slate-400 mt-2">{zone.advice}</div>
      </div>
    </div>
  )
}

// Component breakdown
const ComponentBreakdown = ({ components }) => {
  return (
    <div className="bg-white/5 rounded-xl p-4 border border-white/10">
      <h3 className="font-medium text-white mb-4 flex items-center gap-2">
        <BarChart3 size={18} className="text-blue-400" />
        Index Components
      </h3>

      <div className="space-y-4">
        {Object.entries(INDEX_COMPONENTS).map(([key, component]) => {
          const data = components[key]
          const IconComponent = component.icon
          const zone = getSentimentZone(data.value)

          return (
            <div key={key} className="space-y-2">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <IconComponent size={16} className="text-slate-400" />
                  <span className="text-sm text-white">{component.label}</span>
                  <span className="text-xs text-slate-500">({component.weight}%)</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className={`text-sm font-medium ${zone.color}`}>{data.value}</span>
                  <span className={`text-xs ${data.change >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                    {data.change >= 0 ? '+' : ''}{data.change}%
                  </span>
                </div>
              </div>

              <div className="w-full h-2 bg-white/10 rounded-full overflow-hidden">
                <div
                  className={`h-full rounded-full ${zone.bg} transition-all duration-500`}
                  style={{ width: `${data.value}%` }}
                />
              </div>

              <div className="text-xs text-slate-500">{component.description}</div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

// Historical chart
const HistoricalChart = ({ data, period }) => {
  const maxValue = Math.max(...data)
  const minValue = Math.min(...data)

  return (
    <div className="bg-white/5 rounded-xl p-4 border border-white/10">
      <h3 className="font-medium text-white mb-4 flex items-center gap-2">
        <TrendingUp size={18} className="text-green-400" />
        Historical Trend ({period})
      </h3>

      <div className="h-40 flex items-end gap-1">
        {data.map((value, idx) => {
          const height = ((value - minValue) / (maxValue - minValue) * 100) || 10
          const zone = getSentimentZone(value)

          return (
            <div
              key={idx}
              className="flex-1 min-w-[2px] relative group"
            >
              <div
                className={`w-full rounded-t transition-all ${zone.bg}`}
                style={{ height: `${height}%`, opacity: 0.7 }}
              />
              <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 px-2 py-1 bg-slate-800 rounded text-xs text-white opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap">
                {value}
              </div>
            </div>
          )
        })}
      </div>

      {/* Period labels */}
      <div className="flex justify-between mt-2 text-xs text-slate-500">
        <span>Start</span>
        <span>Now</span>
      </div>
    </div>
  )
}

// Historical comparison
const HistoricalComparison = ({ data }) => {
  return (
    <div className="bg-white/5 rounded-xl p-4 border border-white/10">
      <h3 className="font-medium text-white mb-4 flex items-center gap-2">
        <Clock size={18} className="text-cyan-400" />
        Historical Comparison
      </h3>

      <div className="space-y-3">
        {data.map((item, idx) => {
          const zone = getSentimentZone(item.value)
          const IconComponent = zone.icon

          return (
            <div key={idx} className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="text-sm text-slate-400">{item.label}</span>
              </div>
              <div className="flex items-center gap-2">
                <IconComponent size={14} className={zone.color} />
                <span className={`text-sm font-medium ${zone.color}`}>{item.value}</span>
                <span className="text-xs text-slate-500">{zone.label}</span>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

// Zone distribution
const ZoneDistribution = () => {
  return (
    <div className="bg-white/5 rounded-xl p-4 border border-white/10">
      <h3 className="font-medium text-white mb-4 flex items-center gap-2">
        <Target size={18} className="text-purple-400" />
        Sentiment Zones
      </h3>

      <div className="space-y-2">
        {Object.entries(SENTIMENT_ZONES).map(([key, zone]) => {
          const IconComponent = zone.icon

          return (
            <div key={key} className="flex items-center gap-3 p-2 rounded-lg hover:bg-white/5">
              <div className={`w-3 h-8 rounded ${zone.bg}`} />
              <IconComponent size={18} className={zone.color} />
              <div className="flex-1">
                <div className={`text-sm font-medium ${zone.color}`}>{zone.label}</div>
                <div className="text-xs text-slate-500">{zone.range[0]} - {zone.range[1]}</div>
              </div>
              <div className="text-xs text-slate-400">{zone.advice}</div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

// Quick stats
const QuickStats = ({ data }) => {
  return (
    <div className="grid grid-cols-2 gap-4">
      <div className="bg-white/5 rounded-xl p-4 border border-white/10">
        <div className="flex items-center gap-2 text-slate-400 mb-2">
          <Clock size={16} />
          <span className="text-xs">24h Change</span>
        </div>
        <div className={`text-2xl font-bold ${data.change24h >= 0 ? 'text-green-400' : 'text-red-400'}`}>
          {data.change24h >= 0 ? '+' : ''}{data.change24h}
        </div>
      </div>

      <div className="bg-white/5 rounded-xl p-4 border border-white/10">
        <div className="flex items-center gap-2 text-slate-400 mb-2">
          <BarChart3 size={16} />
          <span className="text-xs">7d Change</span>
        </div>
        <div className={`text-2xl font-bold ${data.change7d >= 0 ? 'text-green-400' : 'text-red-400'}`}>
          {data.change7d >= 0 ? '+' : ''}{data.change7d}
        </div>
      </div>
    </div>
  )
}

// Advice card
const AdviceCard = ({ value }) => {
  const zone = getSentimentZone(value)
  const IconComponent = zone.icon

  const getDetailedAdvice = () => {
    if (value < 25) {
      return {
        title: 'Extreme Fear Market',
        points: [
          'Historically good buying opportunity',
          'DCA into positions cautiously',
          'Focus on quality assets',
          'Set clear entry targets'
        ],
        icon: Snowflake
      }
    }
    if (value < 45) {
      return {
        title: 'Fearful Market',
        points: [
          'Consider accumulating slowly',
          'Research undervalued projects',
          'Keep cash reserves ready',
          'Monitor for trend reversals'
        ],
        icon: Frown
      }
    }
    if (value < 55) {
      return {
        title: 'Neutral Market',
        points: [
          'Market is undecided',
          'Wait for clearer signals',
          'Maintain existing positions',
          'Watch key support/resistance'
        ],
        icon: Meh
      }
    }
    if (value < 75) {
      return {
        title: 'Greedy Market',
        points: [
          'Be cautious with new entries',
          'Consider taking some profits',
          'Tighten stop losses',
          'Watch for overextension'
        ],
        icon: Smile
      }
    }
    return {
      title: 'Extreme Greed Market',
      points: [
        'High probability of correction',
        'Take profits on winners',
        'Reduce position sizes',
        'Prepare for volatility'
      ],
      icon: Flame
    }
  }

  const advice = getDetailedAdvice()
  const AdviceIcon = advice.icon

  return (
    <div className={`rounded-xl p-4 border ${zone.bg.replace('bg-', 'border-')}/30 ${zone.bg}`}>
      <div className="flex items-center gap-2 mb-3">
        <AdviceIcon size={20} className={zone.color} />
        <span className={`font-medium ${zone.color}`}>{advice.title}</span>
      </div>

      <ul className="space-y-2">
        {advice.points.map((point, idx) => (
          <li key={idx} className="flex items-start gap-2 text-sm text-white/80">
            <span className={`mt-1.5 w-1.5 h-1.5 rounded-full ${zone.bg.replace('/10', '')}`} />
            {point}
          </li>
        ))}
      </ul>
    </div>
  )
}

// Main FearGreedIndex component
export const FearGreedIndex = () => {
  const [currentIndex] = useState(mockCurrentIndex)
  const [components] = useState(mockComponents)
  const [selectedPeriod, setSelectedPeriod] = useState('7d')

  const periods = ['24h', '7d', '30d', '90d']

  return (
    <div className="min-h-screen bg-[#0a0e14] text-white p-6">
      <div className="max-w-6xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold text-white mb-1 flex items-center gap-2">
              <Activity className="text-yellow-400" />
              Crypto Fear & Greed Index
            </h1>
            <p className="text-slate-400">Market sentiment indicator based on multiple factors</p>
          </div>

          <div className="flex items-center gap-3">
            <div className="text-xs text-slate-500">
              Last updated: {new Date(currentIndex.timestamp).toLocaleTimeString()}
            </div>
            <button className="p-2 bg-white/5 hover:bg-white/10 rounded-lg transition-colors">
              <RefreshCw size={18} />
            </button>
          </div>
        </div>

        {/* Main gauge */}
        <div className="bg-white/5 rounded-xl p-8 border border-white/10">
          <SentimentGauge value={currentIndex.value} />
        </div>

        {/* Quick stats and advice */}
        <div className="grid md:grid-cols-2 gap-6">
          <QuickStats data={currentIndex} />
          <AdviceCard value={currentIndex.value} />
        </div>

        {/* Main content */}
        <div className="grid lg:grid-cols-3 gap-6">
          {/* Left column */}
          <div className="lg:col-span-2 space-y-6">
            {/* Period selector and chart */}
            <div className="bg-white/5 rounded-xl p-4 border border-white/10">
              <div className="flex items-center justify-between mb-4">
                <h3 className="font-medium text-white">Historical Trend</h3>
                <div className="flex gap-2">
                  {periods.map(period => (
                    <button
                      key={period}
                      onClick={() => setSelectedPeriod(period)}
                      className={`px-3 py-1 rounded text-sm transition-colors ${
                        selectedPeriod === period
                          ? 'bg-blue-500 text-white'
                          : 'bg-white/5 text-slate-400 hover:bg-white/10'
                      }`}
                    >
                      {period}
                    </button>
                  ))}
                </div>
              </div>

              <div className="h-48 flex items-end gap-1">
                {mockHistoricalData[selectedPeriod].map((value, idx) => {
                  const height = value
                  const zone = getSentimentZone(value)

                  return (
                    <div
                      key={idx}
                      className="flex-1 min-w-[2px] relative group cursor-pointer"
                    >
                      <div
                        className={`w-full rounded-t transition-all hover:opacity-100 ${zone.bg}`}
                        style={{ height: `${height}%`, opacity: 0.6 }}
                      />
                      <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 px-2 py-1 bg-slate-800 rounded text-xs text-white opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap z-10">
                        {value} - {zone.label}
                      </div>
                    </div>
                  )
                })}
              </div>
            </div>

            {/* Component breakdown */}
            <ComponentBreakdown components={components} />
          </div>

          {/* Right column */}
          <div className="space-y-6">
            <HistoricalComparison data={mockHistoricalComparison} />
            <ZoneDistribution />
          </div>
        </div>
      </div>
    </div>
  )
}

export default FearGreedIndex
