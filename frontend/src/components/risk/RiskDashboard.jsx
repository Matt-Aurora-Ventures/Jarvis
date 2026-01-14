import React, { useState, useMemo } from 'react'
import {
  Shield,
  AlertTriangle,
  TrendingDown,
  TrendingUp,
  DollarSign,
  Percent,
  Activity,
  PieChart,
  BarChart3,
  Target,
  Flame,
  Thermometer,
  AlertCircle,
  CheckCircle,
  XCircle,
  RefreshCw,
  Settings,
  ChevronDown,
  ChevronUp,
  Info,
  Wallet,
  Zap,
  Scale,
  Clock,
  ArrowDown,
  ArrowUp,
  Minus
} from 'lucide-react'

// Risk severity levels
const RISK_SEVERITY = {
  LOW: { label: 'Low', color: 'text-green-400', bg: 'bg-green-400/10', border: 'border-green-400/30' },
  MODERATE: { label: 'Moderate', color: 'text-yellow-400', bg: 'bg-yellow-400/10', border: 'border-yellow-400/30' },
  HIGH: { label: 'High', color: 'text-orange-400', bg: 'bg-orange-400/10', border: 'border-orange-400/30' },
  CRITICAL: { label: 'Critical', color: 'text-red-400', bg: 'bg-red-400/10', border: 'border-red-400/30' }
}

// Asset sectors
const SECTORS = {
  DEFI: { label: 'DeFi', color: 'bg-blue-500' },
  MEME: { label: 'Meme', color: 'bg-pink-500' },
  L1: { label: 'Layer 1', color: 'bg-purple-500' },
  AI: { label: 'AI', color: 'bg-cyan-500' },
  GAMING: { label: 'Gaming', color: 'bg-orange-500' },
  STABLE: { label: 'Stablecoins', color: 'bg-green-500' },
  NFT: { label: 'NFT', color: 'bg-violet-500' }
}

// Mock portfolio positions
const mockPositions = [
  {
    id: 'p1',
    token: 'SOL',
    sector: 'L1',
    value: 15000,
    entryPrice: 150,
    currentPrice: 180,
    quantity: 83.33,
    pnl: 2500,
    pnlPercent: 20,
    risk: 'MODERATE',
    stopLoss: 160,
    volatility: 45,
    correlation: { BTC: 0.82, ETH: 0.78 }
  },
  {
    id: 'p2',
    token: 'JUP',
    sector: 'DEFI',
    value: 8000,
    entryPrice: 0.80,
    currentPrice: 0.90,
    quantity: 8888.89,
    pnl: 888.89,
    pnlPercent: 12.5,
    risk: 'MODERATE',
    stopLoss: 0.75,
    volatility: 65,
    correlation: { SOL: 0.75, BTC: 0.55 }
  },
  {
    id: 'p3',
    token: 'WIF',
    sector: 'MEME',
    value: 5000,
    entryPrice: 2.50,
    currentPrice: 2.80,
    quantity: 1785.71,
    pnl: 535.71,
    pnlPercent: 12,
    risk: 'HIGH',
    stopLoss: 2.20,
    volatility: 120,
    correlation: { SOL: 0.60, BONK: 0.85 }
  },
  {
    id: 'p4',
    token: 'BONK',
    sector: 'MEME',
    value: 3000,
    entryPrice: 0.000022,
    currentPrice: 0.000018,
    quantity: 166666667,
    pnl: -666.67,
    pnlPercent: -18.18,
    risk: 'CRITICAL',
    stopLoss: 0.000015,
    volatility: 150,
    correlation: { WIF: 0.85, SOL: 0.50 }
  },
  {
    id: 'p5',
    token: 'RENDER',
    sector: 'AI',
    value: 6000,
    entryPrice: 8.00,
    currentPrice: 8.50,
    quantity: 705.88,
    pnl: 352.94,
    pnlPercent: 6.25,
    risk: 'LOW',
    stopLoss: 7.50,
    volatility: 55,
    correlation: { BTC: 0.60, ETH: 0.65 }
  },
  {
    id: 'p6',
    token: 'USDC',
    sector: 'STABLE',
    value: 10000,
    entryPrice: 1.00,
    currentPrice: 1.00,
    quantity: 10000,
    pnl: 0,
    pnlPercent: 0,
    risk: 'LOW',
    stopLoss: null,
    volatility: 0.1,
    correlation: {}
  }
]

// Mock risk alerts
const mockAlerts = [
  {
    id: 'a1',
    type: 'STOP_LOSS_NEAR',
    severity: 'HIGH',
    message: 'BONK is 16.7% away from stop loss',
    token: 'BONK',
    timestamp: Date.now() - 1000 * 60 * 5
  },
  {
    id: 'a2',
    type: 'HIGH_CORRELATION',
    severity: 'MODERATE',
    message: 'WIF and BONK have 85% correlation - consider diversifying',
    token: 'WIF/BONK',
    timestamp: Date.now() - 1000 * 60 * 30
  },
  {
    id: 'a3',
    type: 'CONCENTRATION',
    severity: 'MODERATE',
    message: 'Meme sector represents 17% of portfolio',
    token: 'MEME',
    timestamp: Date.now() - 1000 * 60 * 60
  },
  {
    id: 'a4',
    type: 'VOLATILITY',
    severity: 'HIGH',
    message: 'BONK volatility at 150% - extreme risk',
    token: 'BONK',
    timestamp: Date.now() - 1000 * 60 * 120
  }
]

// Format helpers
const formatCurrency = (value) => {
  if (Math.abs(value) >= 1000000) return `$${(value / 1000000).toFixed(2)}M`
  if (Math.abs(value) >= 1000) return `$${(value / 1000).toFixed(2)}K`
  return `$${value.toFixed(2)}`
}

const formatPercent = (value) => `${value >= 0 ? '+' : ''}${value.toFixed(2)}%`

const formatTime = (timestamp) => {
  const diff = Date.now() - timestamp
  if (diff < 60000) return 'Just now'
  if (diff < 3600000) return `${Math.floor(diff / 60000)}m ago`
  if (diff < 86400000) return `${Math.floor(diff / 3600000)}h ago`
  return `${Math.floor(diff / 86400000)}d ago`
}

// Get risk severity from score
const getRiskSeverity = (score) => {
  if (score >= 80) return RISK_SEVERITY.CRITICAL
  if (score >= 60) return RISK_SEVERITY.HIGH
  if (score >= 40) return RISK_SEVERITY.MODERATE
  return RISK_SEVERITY.LOW
}

// Risk score gauge component
const RiskGauge = ({ score, label }) => {
  const severity = getRiskSeverity(score)
  const rotation = (score / 100) * 180 - 90

  return (
    <div className="flex flex-col items-center">
      <div className="relative w-32 h-16 overflow-hidden">
        {/* Background arc */}
        <div className="absolute bottom-0 left-0 w-32 h-32 rounded-full border-8 border-white/10" style={{ clipPath: 'inset(50% 0 0 0)' }} />

        {/* Colored segments */}
        <div className="absolute bottom-0 left-0 w-32 h-32 rounded-full border-8 border-transparent"
          style={{
            clipPath: 'inset(50% 0 0 0)',
            background: `conic-gradient(from 180deg,
              rgb(34, 197, 94) 0deg,
              rgb(234, 179, 8) 60deg,
              rgb(249, 115, 22) 120deg,
              rgb(239, 68, 68) 180deg,
              transparent 180deg)`
          }}
        />

        {/* Needle */}
        <div
          className="absolute bottom-0 left-1/2 w-1 h-12 bg-white rounded-full origin-bottom transition-transform"
          style={{ transform: `translateX(-50%) rotate(${rotation}deg)` }}
        />

        {/* Center cap */}
        <div className="absolute bottom-0 left-1/2 w-4 h-4 -translate-x-1/2 translate-y-1/2 bg-slate-800 rounded-full border-2 border-white/20" />
      </div>

      <div className="mt-2 text-center">
        <div className={`text-2xl font-bold ${severity.color}`}>{score}</div>
        <div className="text-xs text-slate-500">{label}</div>
      </div>
    </div>
  )
}

// Portfolio overview card
const PortfolioOverview = ({ positions }) => {
  const stats = useMemo(() => {
    const totalValue = positions.reduce((sum, p) => sum + p.value, 0)
    const totalPnl = positions.reduce((sum, p) => sum + p.pnl, 0)
    const atRisk = positions.filter(p => p.risk === 'HIGH' || p.risk === 'CRITICAL')
      .reduce((sum, p) => sum + p.value, 0)
    const avgVolatility = positions.reduce((sum, p) => sum + p.volatility, 0) / positions.length

    // Calculate max drawdown scenario
    const maxDrawdown = positions.reduce((sum, p) => {
      if (!p.stopLoss) return sum
      const drawdown = ((p.currentPrice - p.stopLoss) / p.currentPrice) * p.value
      return sum + drawdown
    }, 0)

    return { totalValue, totalPnl, atRisk, avgVolatility, maxDrawdown }
  }, [positions])

  return (
    <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
      <div className="bg-white/5 rounded-xl p-4 border border-white/10">
        <div className="flex items-center gap-2 text-slate-400 mb-2">
          <Wallet size={16} />
          <span className="text-xs">Portfolio Value</span>
        </div>
        <div className="text-2xl font-bold text-white">{formatCurrency(stats.totalValue)}</div>
      </div>

      <div className="bg-white/5 rounded-xl p-4 border border-white/10">
        <div className="flex items-center gap-2 text-slate-400 mb-2">
          <TrendingUp size={16} />
          <span className="text-xs">Total P&L</span>
        </div>
        <div className={`text-2xl font-bold ${stats.totalPnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
          {formatCurrency(stats.totalPnl)}
        </div>
      </div>

      <div className="bg-white/5 rounded-xl p-4 border border-white/10">
        <div className="flex items-center gap-2 text-slate-400 mb-2">
          <AlertTriangle size={16} />
          <span className="text-xs">Capital at Risk</span>
        </div>
        <div className="text-2xl font-bold text-orange-400">{formatCurrency(stats.atRisk)}</div>
        <div className="text-xs text-slate-500">{((stats.atRisk / stats.totalValue) * 100).toFixed(1)}% of portfolio</div>
      </div>

      <div className="bg-white/5 rounded-xl p-4 border border-white/10">
        <div className="flex items-center gap-2 text-slate-400 mb-2">
          <Activity size={16} />
          <span className="text-xs">Avg Volatility</span>
        </div>
        <div className={`text-2xl font-bold ${stats.avgVolatility > 100 ? 'text-red-400' : stats.avgVolatility > 50 ? 'text-yellow-400' : 'text-green-400'}`}>
          {stats.avgVolatility.toFixed(0)}%
        </div>
      </div>

      <div className="bg-white/5 rounded-xl p-4 border border-white/10">
        <div className="flex items-center gap-2 text-slate-400 mb-2">
          <ArrowDown size={16} />
          <span className="text-xs">Max Drawdown</span>
        </div>
        <div className="text-2xl font-bold text-red-400">-{formatCurrency(stats.maxDrawdown)}</div>
        <div className="text-xs text-slate-500">If all stops hit</div>
      </div>
    </div>
  )
}

// Position risk card
const PositionRiskCard = ({ position }) => {
  const severity = RISK_SEVERITY[position.risk]
  const sector = SECTORS[position.sector]

  const distanceToStop = position.stopLoss
    ? ((position.currentPrice - position.stopLoss) / position.currentPrice * 100)
    : null

  return (
    <div className={`bg-white/5 rounded-xl p-4 border ${severity.border}`}>
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-3">
          <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${severity.bg}`}>
            <span className="font-bold text-white">{position.token.slice(0, 2)}</span>
          </div>
          <div>
            <div className="font-medium text-white">{position.token}</div>
            <div className="flex items-center gap-2">
              <span className={`w-2 h-2 rounded-full ${sector.color}`} />
              <span className="text-xs text-slate-500">{sector.label}</span>
            </div>
          </div>
        </div>
        <span className={`px-2 py-0.5 rounded text-xs font-medium ${severity.bg} ${severity.color}`}>
          {severity.label}
        </span>
      </div>

      <div className="grid grid-cols-3 gap-3 mb-3">
        <div>
          <div className="text-xs text-slate-500">Value</div>
          <div className="text-sm font-medium text-white">{formatCurrency(position.value)}</div>
        </div>
        <div>
          <div className="text-xs text-slate-500">P&L</div>
          <div className={`text-sm font-medium ${position.pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
            {formatPercent(position.pnlPercent)}
          </div>
        </div>
        <div>
          <div className="text-xs text-slate-500">Volatility</div>
          <div className={`text-sm font-medium ${position.volatility > 100 ? 'text-red-400' : position.volatility > 50 ? 'text-yellow-400' : 'text-green-400'}`}>
            {position.volatility}%
          </div>
        </div>
      </div>

      {distanceToStop !== null && (
        <div className="pt-3 border-t border-white/5">
          <div className="flex items-center justify-between text-xs mb-1">
            <span className="text-slate-500">Distance to Stop</span>
            <span className={distanceToStop < 10 ? 'text-red-400' : distanceToStop < 20 ? 'text-yellow-400' : 'text-green-400'}>
              {distanceToStop.toFixed(1)}%
            </span>
          </div>
          <div className="w-full bg-white/10 rounded-full h-2 overflow-hidden">
            <div
              className={`h-full rounded-full ${distanceToStop < 10 ? 'bg-red-500' : distanceToStop < 20 ? 'bg-yellow-500' : 'bg-green-500'}`}
              style={{ width: `${Math.min(distanceToStop, 100)}%` }}
            />
          </div>
        </div>
      )}
    </div>
  )
}

// Sector allocation chart
const SectorAllocation = ({ positions }) => {
  const sectorData = useMemo(() => {
    const totalValue = positions.reduce((sum, p) => sum + p.value, 0)
    const sectors = {}

    positions.forEach(p => {
      if (!sectors[p.sector]) {
        sectors[p.sector] = { value: 0, count: 0 }
      }
      sectors[p.sector].value += p.value
      sectors[p.sector].count++
    })

    return Object.entries(sectors)
      .map(([key, data]) => ({
        sector: key,
        ...SECTORS[key],
        ...data,
        percent: (data.value / totalValue) * 100
      }))
      .sort((a, b) => b.value - a.value)
  }, [positions])

  return (
    <div className="bg-white/5 rounded-xl p-4 border border-white/10">
      <h3 className="font-medium text-white mb-4 flex items-center gap-2">
        <PieChart size={18} className="text-purple-400" />
        Sector Allocation
      </h3>

      <div className="space-y-3">
        {sectorData.map(sector => (
          <div key={sector.sector}>
            <div className="flex items-center justify-between text-sm mb-1">
              <div className="flex items-center gap-2">
                <span className={`w-3 h-3 rounded ${sector.color}`} />
                <span className="text-white">{sector.label}</span>
                <span className="text-slate-500">({sector.count})</span>
              </div>
              <span className="text-white font-medium">{sector.percent.toFixed(1)}%</span>
            </div>
            <div className="w-full bg-white/10 rounded-full h-2 overflow-hidden">
              <div
                className={`h-full rounded-full ${sector.color}`}
                style={{ width: `${sector.percent}%` }}
              />
            </div>
          </div>
        ))}
      </div>

      {/* Concentration warning */}
      {sectorData.some(s => s.percent > 30 && s.sector !== 'STABLE') && (
        <div className="mt-4 p-3 bg-yellow-400/10 border border-yellow-400/30 rounded-lg flex items-start gap-2">
          <AlertTriangle size={16} className="text-yellow-400 mt-0.5" />
          <div className="text-sm text-yellow-400">
            High concentration detected. Consider diversifying sectors above 30%.
          </div>
        </div>
      )}
    </div>
  )
}

// Risk alerts panel
const RiskAlerts = ({ alerts }) => {
  const getIcon = (severity) => {
    switch (severity) {
      case 'CRITICAL': return <XCircle size={16} className="text-red-400" />
      case 'HIGH': return <AlertTriangle size={16} className="text-orange-400" />
      case 'MODERATE': return <AlertCircle size={16} className="text-yellow-400" />
      default: return <Info size={16} className="text-blue-400" />
    }
  }

  return (
    <div className="bg-white/5 rounded-xl border border-white/10 overflow-hidden">
      <div className="p-4 border-b border-white/10 flex items-center justify-between">
        <h3 className="font-medium text-white flex items-center gap-2">
          <AlertTriangle size={18} className="text-orange-400" />
          Risk Alerts
        </h3>
        <span className="px-2 py-0.5 bg-orange-400/20 text-orange-400 rounded text-xs">
          {alerts.length} active
        </span>
      </div>

      <div className="max-h-[300px] overflow-y-auto">
        {alerts.length === 0 ? (
          <div className="p-8 text-center text-slate-500">
            <CheckCircle size={32} className="mx-auto mb-2 text-green-400" />
            <div>No active risk alerts</div>
          </div>
        ) : (
          alerts.map(alert => {
            const severity = RISK_SEVERITY[alert.severity]
            return (
              <div key={alert.id} className={`p-3 border-b border-white/5 last:border-0 ${severity.bg}`}>
                <div className="flex items-start gap-3">
                  {getIcon(alert.severity)}
                  <div className="flex-1">
                    <div className="text-sm text-white">{alert.message}</div>
                    <div className="flex items-center gap-2 mt-1">
                      <span className={`text-xs ${severity.color}`}>{severity.label}</span>
                      <span className="text-xs text-slate-500">{formatTime(alert.timestamp)}</span>
                    </div>
                  </div>
                </div>
              </div>
            )
          })
        )}
      </div>
    </div>
  )
}

// Correlation matrix
const CorrelationMatrix = ({ positions }) => {
  const tokens = positions.filter(p => p.sector !== 'STABLE').slice(0, 5)

  const getCorrelationColor = (value) => {
    if (value >= 0.8) return 'bg-red-500'
    if (value >= 0.6) return 'bg-orange-500'
    if (value >= 0.4) return 'bg-yellow-500'
    if (value >= 0.2) return 'bg-green-500'
    return 'bg-slate-500'
  }

  // Generate mock correlation matrix
  const matrix = tokens.map((t1, i) =>
    tokens.map((t2, j) => {
      if (i === j) return 1
      // Use existing correlation data or generate
      return t1.correlation?.[t2.token] || Math.random() * 0.5 + 0.2
    })
  )

  return (
    <div className="bg-white/5 rounded-xl p-4 border border-white/10">
      <h3 className="font-medium text-white mb-4 flex items-center gap-2">
        <Scale size={18} className="text-cyan-400" />
        Correlation Matrix
      </h3>

      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr>
              <th className="p-2 text-xs text-slate-500"></th>
              {tokens.map(t => (
                <th key={t.token} className="p-2 text-xs text-slate-400">{t.token}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {tokens.map((t1, i) => (
              <tr key={t1.token}>
                <td className="p-2 text-xs text-slate-400">{t1.token}</td>
                {matrix[i].map((corr, j) => (
                  <td key={j} className="p-1">
                    <div
                      className={`w-full h-8 rounded flex items-center justify-center text-xs font-medium text-white ${getCorrelationColor(corr)}`}
                      style={{ opacity: 0.3 + corr * 0.7 }}
                    >
                      {corr.toFixed(2)}
                    </div>
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="mt-4 flex items-center justify-center gap-4 text-xs">
        <div className="flex items-center gap-1">
          <div className="w-3 h-3 rounded bg-green-500" />
          <span className="text-slate-500">Low (&lt;0.4)</span>
        </div>
        <div className="flex items-center gap-1">
          <div className="w-3 h-3 rounded bg-yellow-500" />
          <span className="text-slate-500">Medium (0.4-0.6)</span>
        </div>
        <div className="flex items-center gap-1">
          <div className="w-3 h-3 rounded bg-red-500" />
          <span className="text-slate-500">High (&gt;0.8)</span>
        </div>
      </div>
    </div>
  )
}

// Drawdown tracker
const DrawdownTracker = () => {
  // Mock drawdown history
  const drawdownHistory = [
    { date: '2024-01', drawdown: -5.2, recovery: 100 },
    { date: '2024-02', drawdown: -12.8, recovery: 100 },
    { date: '2024-03', drawdown: -8.5, recovery: 100 },
    { date: '2024-04', drawdown: -3.2, recovery: 100 },
    { date: '2024-05', drawdown: -15.6, recovery: 85 },
    { date: '2024-06', drawdown: -6.4, recovery: 92 }
  ]

  const maxDrawdown = Math.min(...drawdownHistory.map(d => d.drawdown))
  const avgDrawdown = drawdownHistory.reduce((sum, d) => sum + d.drawdown, 0) / drawdownHistory.length
  const currentDrawdown = drawdownHistory[drawdownHistory.length - 1]

  return (
    <div className="bg-white/5 rounded-xl p-4 border border-white/10">
      <h3 className="font-medium text-white mb-4 flex items-center gap-2">
        <TrendingDown size={18} className="text-red-400" />
        Drawdown History
      </h3>

      <div className="grid grid-cols-3 gap-3 mb-4">
        <div className="bg-white/5 rounded-lg p-3 text-center">
          <div className="text-xs text-slate-500 mb-1">Current</div>
          <div className="text-lg font-bold text-yellow-400">{currentDrawdown.drawdown.toFixed(1)}%</div>
        </div>
        <div className="bg-white/5 rounded-lg p-3 text-center">
          <div className="text-xs text-slate-500 mb-1">Max</div>
          <div className="text-lg font-bold text-red-400">{maxDrawdown.toFixed(1)}%</div>
        </div>
        <div className="bg-white/5 rounded-lg p-3 text-center">
          <div className="text-xs text-slate-500 mb-1">Average</div>
          <div className="text-lg font-bold text-orange-400">{avgDrawdown.toFixed(1)}%</div>
        </div>
      </div>

      {/* Visual drawdown bars */}
      <div className="space-y-2">
        {drawdownHistory.map(d => (
          <div key={d.date} className="flex items-center gap-3">
            <span className="text-xs text-slate-500 w-16">{d.date}</span>
            <div className="flex-1 h-4 bg-white/5 rounded-full overflow-hidden">
              <div
                className={`h-full ${d.recovery === 100 ? 'bg-green-500' : 'bg-red-500'}`}
                style={{ width: `${Math.abs(d.drawdown)}%` }}
              />
            </div>
            <span className={`text-xs w-12 text-right ${d.recovery === 100 ? 'text-green-400' : 'text-red-400'}`}>
              {d.drawdown.toFixed(1)}%
            </span>
          </div>
        ))}
      </div>

      <div className="mt-4 text-xs text-slate-500 text-center">
        Recovery status: {currentDrawdown.recovery === 100 ? (
          <span className="text-green-400">Fully recovered</span>
        ) : (
          <span className="text-yellow-400">{currentDrawdown.recovery}% recovered</span>
        )}
      </div>
    </div>
  )
}

// Risk settings panel
const RiskSettings = ({ settings, onChange }) => {
  const [isOpen, setIsOpen] = useState(false)

  return (
    <div className="bg-white/5 rounded-xl border border-white/10">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="w-full p-4 flex items-center justify-between text-left"
      >
        <div className="flex items-center gap-2">
          <Settings size={18} className="text-slate-400" />
          <span className="font-medium text-white">Risk Parameters</span>
        </div>
        {isOpen ? <ChevronUp size={18} className="text-slate-400" /> : <ChevronDown size={18} className="text-slate-400" />}
      </button>

      {isOpen && (
        <div className="p-4 pt-0 space-y-4">
          <div>
            <label className="text-sm text-slate-400 mb-2 block">Max Portfolio Risk</label>
            <div className="flex items-center gap-3">
              <input
                type="range"
                min="5"
                max="50"
                value={settings.maxRisk}
                onChange={(e) => onChange({ ...settings, maxRisk: parseInt(e.target.value) })}
                className="flex-1"
              />
              <span className="text-white font-medium w-12">{settings.maxRisk}%</span>
            </div>
          </div>

          <div>
            <label className="text-sm text-slate-400 mb-2 block">Max Per Position</label>
            <div className="flex items-center gap-3">
              <input
                type="range"
                min="5"
                max="30"
                value={settings.maxPosition}
                onChange={(e) => onChange({ ...settings, maxPosition: parseInt(e.target.value) })}
                className="flex-1"
              />
              <span className="text-white font-medium w-12">{settings.maxPosition}%</span>
            </div>
          </div>

          <div>
            <label className="text-sm text-slate-400 mb-2 block">Max Sector Concentration</label>
            <div className="flex items-center gap-3">
              <input
                type="range"
                min="10"
                max="50"
                value={settings.maxSector}
                onChange={(e) => onChange({ ...settings, maxSector: parseInt(e.target.value) })}
                className="flex-1"
              />
              <span className="text-white font-medium w-12">{settings.maxSector}%</span>
            </div>
          </div>

          <div>
            <label className="text-sm text-slate-400 mb-2 block">Max Drawdown Tolerance</label>
            <div className="flex items-center gap-3">
              <input
                type="range"
                min="10"
                max="50"
                value={settings.maxDrawdown}
                onChange={(e) => onChange({ ...settings, maxDrawdown: parseInt(e.target.value) })}
                className="flex-1"
              />
              <span className="text-white font-medium w-12">{settings.maxDrawdown}%</span>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

// Main RiskDashboard component
export const RiskDashboard = () => {
  const [positions] = useState(mockPositions)
  const [alerts] = useState(mockAlerts)
  const [riskSettings, setRiskSettings] = useState({
    maxRisk: 20,
    maxPosition: 15,
    maxSector: 30,
    maxDrawdown: 25
  })

  // Calculate overall risk score
  const riskScore = useMemo(() => {
    let score = 0

    // Position risk contribution
    const criticalPositions = positions.filter(p => p.risk === 'CRITICAL').length
    const highPositions = positions.filter(p => p.risk === 'HIGH').length
    score += criticalPositions * 20 + highPositions * 10

    // Volatility contribution
    const avgVol = positions.reduce((sum, p) => sum + p.volatility, 0) / positions.length
    score += Math.min(avgVol / 3, 30)

    // Concentration contribution
    const totalValue = positions.reduce((sum, p) => sum + p.value, 0)
    const maxPositionPct = Math.max(...positions.map(p => (p.value / totalValue) * 100))
    if (maxPositionPct > riskSettings.maxPosition) score += 15

    // Active alerts contribution
    score += alerts.length * 5

    return Math.min(Math.round(score), 100)
  }, [positions, alerts, riskSettings])

  return (
    <div className="min-h-screen bg-[#0a0e14] text-white p-6">
      <div className="max-w-7xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold text-white mb-1 flex items-center gap-2">
              <Shield className="text-green-400" />
              Risk Management
            </h1>
            <p className="text-slate-400">Monitor and manage portfolio risk exposure</p>
          </div>

          <div className="flex items-center gap-4">
            <RiskGauge score={riskScore} label="Risk Score" />
            <button className="p-2 bg-white/5 hover:bg-white/10 rounded-lg transition-colors">
              <RefreshCw size={18} />
            </button>
          </div>
        </div>

        {/* Portfolio overview */}
        <PortfolioOverview positions={positions} />

        {/* Main grid */}
        <div className="grid lg:grid-cols-3 gap-6">
          {/* Left column */}
          <div className="lg:col-span-2 space-y-6">
            {/* Position risk cards */}
            <div>
              <h2 className="text-lg font-semibold text-white mb-4">Position Risk Analysis</h2>
              <div className="grid md:grid-cols-2 gap-4">
                {positions
                  .sort((a, b) => {
                    const order = { CRITICAL: 0, HIGH: 1, MODERATE: 2, LOW: 3 }
                    return order[a.risk] - order[b.risk]
                  })
                  .map(position => (
                    <PositionRiskCard key={position.id} position={position} />
                  ))
                }
              </div>
            </div>

            {/* Correlation matrix */}
            <CorrelationMatrix positions={positions} />
          </div>

          {/* Right column */}
          <div className="space-y-6">
            {/* Risk alerts */}
            <RiskAlerts alerts={alerts} />

            {/* Sector allocation */}
            <SectorAllocation positions={positions} />

            {/* Drawdown tracker */}
            <DrawdownTracker />

            {/* Risk settings */}
            <RiskSettings settings={riskSettings} onChange={setRiskSettings} />
          </div>
        </div>
      </div>
    </div>
  )
}

export default RiskDashboard
