import React, { useState, useMemo } from 'react'
import {
  Fuel,
  TrendingUp,
  TrendingDown,
  Clock,
  RefreshCw,
  Zap,
  AlertTriangle,
  CheckCircle,
  DollarSign,
  Activity,
  BarChart3,
  ArrowRight,
  Calculator,
  Bell,
  Info,
  ChevronDown,
  Sun,
  Moon,
  Sunrise,
  Sunset
} from 'lucide-react'

// Networks with gas tracking
const NETWORKS = {
  SOLANA: {
    name: 'Solana',
    symbol: 'SOL',
    color: 'bg-purple-500',
    textColor: 'text-purple-400',
    unit: 'lamports',
    avgTxCost: 0.00025,
    priorityLevels: { slow: 5000, medium: 50000, fast: 200000, turbo: 1000000 }
  },
  ETHEREUM: {
    name: 'Ethereum',
    symbol: 'ETH',
    color: 'bg-blue-500',
    textColor: 'text-blue-400',
    unit: 'gwei',
    avgTxCost: 2.50,
    priorityLevels: { slow: 15, medium: 25, fast: 40, turbo: 80 }
  },
  ARBITRUM: {
    name: 'Arbitrum',
    symbol: 'ETH',
    color: 'bg-cyan-500',
    textColor: 'text-cyan-400',
    unit: 'gwei',
    avgTxCost: 0.15,
    priorityLevels: { slow: 0.1, medium: 0.15, fast: 0.25, turbo: 0.5 }
  },
  BASE: {
    name: 'Base',
    symbol: 'ETH',
    color: 'bg-blue-600',
    textColor: 'text-blue-400',
    unit: 'gwei',
    avgTxCost: 0.05,
    priorityLevels: { slow: 0.05, medium: 0.08, fast: 0.12, turbo: 0.25 }
  },
  POLYGON: {
    name: 'Polygon',
    symbol: 'MATIC',
    color: 'bg-violet-500',
    textColor: 'text-violet-400',
    unit: 'gwei',
    avgTxCost: 0.01,
    priorityLevels: { slow: 30, medium: 50, fast: 100, turbo: 200 }
  },
  BSC: {
    name: 'BNB Chain',
    symbol: 'BNB',
    color: 'bg-yellow-500',
    textColor: 'text-yellow-400',
    unit: 'gwei',
    avgTxCost: 0.10,
    priorityLevels: { slow: 3, medium: 5, fast: 8, turbo: 15 }
  }
}

// Priority levels
const PRIORITY_LEVELS = {
  slow: { label: 'Slow', icon: Clock, color: 'text-slate-400', time: '5-10 min' },
  medium: { label: 'Medium', icon: Activity, color: 'text-blue-400', time: '1-3 min' },
  fast: { label: 'Fast', icon: Zap, color: 'text-yellow-400', time: '< 30 sec' },
  turbo: { label: 'Turbo', icon: Fuel, color: 'text-red-400', time: '< 10 sec' }
}

// Gas condition levels
const GAS_CONDITIONS = {
  LOW: { label: 'Low', color: 'text-green-400', bg: 'bg-green-400/10', icon: CheckCircle },
  NORMAL: { label: 'Normal', color: 'text-blue-400', bg: 'bg-blue-400/10', icon: Activity },
  HIGH: { label: 'High', color: 'text-yellow-400', bg: 'bg-yellow-400/10', icon: AlertTriangle },
  EXTREME: { label: 'Extreme', color: 'text-red-400', bg: 'bg-red-400/10', icon: Fuel }
}

// Mock gas data
const mockGasData = {
  SOLANA: {
    current: { slow: 5000, medium: 25000, fast: 100000, turbo: 500000 },
    change24h: -12,
    condition: 'LOW',
    txCount24h: 45000000,
    avgTxCostUsd: 0.00025,
    history: [5000, 6000, 8000, 12000, 15000, 10000, 8000, 6000, 5000, 4500, 5000, 5500]
  },
  ETHEREUM: {
    current: { slow: 18, medium: 28, fast: 45, turbo: 90 },
    change24h: 15,
    condition: 'NORMAL',
    txCount24h: 1200000,
    avgTxCostUsd: 3.20,
    history: [25, 28, 35, 45, 55, 48, 42, 38, 32, 28, 25, 28]
  },
  ARBITRUM: {
    current: { slow: 0.08, medium: 0.12, fast: 0.2, turbo: 0.4 },
    change24h: -5,
    condition: 'LOW',
    txCount24h: 890000,
    avgTxCostUsd: 0.12,
    history: [0.1, 0.12, 0.15, 0.18, 0.2, 0.18, 0.15, 0.12, 0.1, 0.09, 0.08, 0.1]
  },
  BASE: {
    current: { slow: 0.04, medium: 0.06, fast: 0.1, turbo: 0.2 },
    change24h: -8,
    condition: 'LOW',
    txCount24h: 2100000,
    avgTxCostUsd: 0.04,
    history: [0.05, 0.06, 0.08, 0.1, 0.12, 0.1, 0.08, 0.06, 0.05, 0.04, 0.04, 0.05]
  },
  POLYGON: {
    current: { slow: 40, medium: 65, fast: 120, turbo: 250 },
    change24h: 22,
    condition: 'HIGH',
    txCount24h: 3500000,
    avgTxCostUsd: 0.015,
    history: [50, 60, 80, 100, 130, 150, 140, 120, 100, 80, 60, 65]
  },
  BSC: {
    current: { slow: 3, medium: 5, fast: 8, turbo: 12 },
    change24h: -3,
    condition: 'NORMAL',
    txCount24h: 4800000,
    avgTxCostUsd: 0.08,
    history: [5, 5, 6, 7, 8, 8, 7, 6, 5, 4, 4, 5]
  }
}

// Best times data
const bestTimesData = [
  { hour: 0, label: '12 AM', activity: 30, icon: Moon },
  { hour: 3, label: '3 AM', activity: 20, icon: Moon },
  { hour: 6, label: '6 AM', activity: 35, icon: Sunrise },
  { hour: 9, label: '9 AM', activity: 65, icon: Sun },
  { hour: 12, label: '12 PM', activity: 85, icon: Sun },
  { hour: 15, label: '3 PM', activity: 95, icon: Sun },
  { hour: 18, label: '6 PM', activity: 80, icon: Sunset },
  { hour: 21, label: '9 PM', activity: 55, icon: Moon }
]

// Format helpers
const formatGasPrice = (price, unit) => {
  if (unit === 'lamports') {
    if (price >= 1000000) return `${(price / 1000000).toFixed(2)}M`
    if (price >= 1000) return `${(price / 1000).toFixed(1)}K`
    return price.toString()
  }
  return price.toFixed(2)
}

const formatUsd = (value) => {
  if (value < 0.01) return `$${value.toFixed(4)}`
  if (value < 1) return `$${value.toFixed(3)}`
  return `$${value.toFixed(2)}`
}

// Network gas card
const NetworkGasCard = ({ network, data, isSelected, onSelect }) => {
  const networkInfo = NETWORKS[network]
  const condition = GAS_CONDITIONS[data.condition]
  const ConditionIcon = condition.icon

  return (
    <div
      onClick={() => onSelect(network)}
      className={`p-4 rounded-xl border cursor-pointer transition-all ${
        isSelected
          ? 'bg-white/10 border-blue-500 ring-1 ring-blue-500'
          : 'bg-white/5 border-white/10 hover:border-white/20'
      }`}
    >
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <div className={`w-8 h-8 rounded-lg ${networkInfo.color} flex items-center justify-center`}>
            <Fuel size={16} className="text-white" />
          </div>
          <div>
            <div className="font-medium text-white">{networkInfo.name}</div>
            <div className="text-xs text-slate-500">{networkInfo.symbol}</div>
          </div>
        </div>
        <div className={`flex items-center gap-1 px-2 py-0.5 rounded ${condition.bg} ${condition.color}`}>
          <ConditionIcon size={12} />
          <span className="text-xs">{condition.label}</span>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-2 mb-3">
        <div className="bg-white/5 rounded-lg p-2">
          <div className="text-xs text-slate-500">Medium</div>
          <div className="font-medium text-white">
            {formatGasPrice(data.current.medium, networkInfo.unit)} {networkInfo.unit}
          </div>
        </div>
        <div className="bg-white/5 rounded-lg p-2">
          <div className="text-xs text-slate-500">Avg Cost</div>
          <div className="font-medium text-green-400">{formatUsd(data.avgTxCostUsd)}</div>
        </div>
      </div>

      <div className="flex items-center justify-between text-xs">
        <span className="text-slate-500">{(data.txCount24h / 1000000).toFixed(1)}M txs/24h</span>
        <span className={data.change24h >= 0 ? 'text-red-400' : 'text-green-400'}>
          {data.change24h >= 0 ? '+' : ''}{data.change24h}%
        </span>
      </div>
    </div>
  )
}

// Priority fee selector
const PriorityFeeSelector = ({ network, data }) => {
  const [selected, setSelected] = useState('medium')
  const networkInfo = NETWORKS[network]

  return (
    <div className="bg-white/5 rounded-xl p-4 border border-white/10">
      <h3 className="font-medium text-white mb-4 flex items-center gap-2">
        <Zap size={18} className="text-yellow-400" />
        Priority Fee
      </h3>

      <div className="grid grid-cols-4 gap-2 mb-4">
        {Object.entries(PRIORITY_LEVELS).map(([key, level]) => {
          const IconComponent = level.icon
          const price = data.current[key]

          return (
            <button
              key={key}
              onClick={() => setSelected(key)}
              className={`p-3 rounded-lg text-center transition-all ${
                selected === key
                  ? 'bg-blue-500/20 border border-blue-500'
                  : 'bg-white/5 border border-transparent hover:bg-white/10'
              }`}
            >
              <IconComponent size={18} className={`mx-auto mb-1 ${level.color}`} />
              <div className="text-xs text-slate-400 mb-1">{level.label}</div>
              <div className="text-sm font-medium text-white">
                {formatGasPrice(price, networkInfo.unit)}
              </div>
              <div className="text-xs text-slate-500">{level.time}</div>
            </button>
          )
        })}
      </div>

      <div className="bg-white/5 rounded-lg p-3">
        <div className="flex items-center justify-between mb-2">
          <span className="text-sm text-slate-400">Estimated Cost</span>
          <span className="font-medium text-white">{formatUsd(data.avgTxCostUsd * (data.current[selected] / data.current.medium))}</span>
        </div>
        <div className="flex items-center justify-between">
          <span className="text-sm text-slate-400">Confirmation Time</span>
          <span className="text-sm text-green-400">{PRIORITY_LEVELS[selected].time}</span>
        </div>
      </div>
    </div>
  )
}

// Gas history chart
const GasHistoryChart = ({ network, data }) => {
  const networkInfo = NETWORKS[network]
  const maxValue = Math.max(...data.history)
  const minValue = Math.min(...data.history)

  const hours = ['12h', '11h', '10h', '9h', '8h', '7h', '6h', '5h', '4h', '3h', '2h', '1h']

  return (
    <div className="bg-white/5 rounded-xl p-4 border border-white/10">
      <h3 className="font-medium text-white mb-4 flex items-center gap-2">
        <BarChart3 size={18} className="text-cyan-400" />
        12 Hour History
      </h3>

      <div className="h-32 flex items-end gap-1 mb-2">
        {data.history.map((value, idx) => {
          const height = ((value - minValue) / (maxValue - minValue) * 100) || 10
          const isLow = value <= minValue * 1.2

          return (
            <div
              key={idx}
              className="flex-1 flex flex-col items-center gap-1"
            >
              <div
                className={`w-full rounded-t transition-all ${isLow ? 'bg-green-500' : 'bg-blue-500'}`}
                style={{ height: `${height}%` }}
              />
            </div>
          )
        })}
      </div>

      <div className="flex justify-between text-xs text-slate-500">
        {hours.map((h, idx) => (
          <span key={idx} className={idx % 3 === 0 ? 'visible' : 'invisible'}>{h}</span>
        ))}
      </div>

      <div className="mt-4 flex items-center justify-between text-sm">
        <div>
          <span className="text-slate-500">Low: </span>
          <span className="text-green-400">{formatGasPrice(minValue, networkInfo.unit)}</span>
        </div>
        <div>
          <span className="text-slate-500">High: </span>
          <span className="text-red-400">{formatGasPrice(maxValue, networkInfo.unit)}</span>
        </div>
      </div>
    </div>
  )
}

// Best times to transact
const BestTimesChart = () => {
  const currentHour = new Date().getHours()
  const currentPeriod = Math.floor(currentHour / 3)

  return (
    <div className="bg-white/5 rounded-xl p-4 border border-white/10">
      <h3 className="font-medium text-white mb-4 flex items-center gap-2">
        <Clock size={18} className="text-green-400" />
        Best Times to Transact (UTC)
      </h3>

      <div className="space-y-2">
        {bestTimesData.map((period, idx) => {
          const IconComponent = period.icon
          const isNow = idx === currentPeriod
          const isBest = period.activity <= 35

          return (
            <div
              key={idx}
              className={`flex items-center gap-3 p-2 rounded-lg ${isNow ? 'bg-blue-500/20 border border-blue-500' : ''}`}
            >
              <IconComponent size={16} className="text-slate-400" />
              <span className="text-sm text-white w-16">{period.label}</span>
              <div className="flex-1 h-2 bg-white/10 rounded-full overflow-hidden">
                <div
                  className={`h-full rounded-full transition-all ${
                    isBest ? 'bg-green-500' : period.activity > 80 ? 'bg-red-500' : 'bg-yellow-500'
                  }`}
                  style={{ width: `${period.activity}%` }}
                />
              </div>
              <span className={`text-xs w-16 text-right ${isBest ? 'text-green-400' : 'text-slate-500'}`}>
                {isBest ? 'Best' : period.activity > 80 ? 'Avoid' : 'Normal'}
              </span>
            </div>
          )
        })}
      </div>

      <div className="mt-4 p-3 bg-green-400/10 border border-green-400/30 rounded-lg">
        <div className="flex items-center gap-2 text-green-400 text-sm">
          <CheckCircle size={16} />
          <span>Best time: 12 AM - 6 AM UTC (lowest gas)</span>
        </div>
      </div>
    </div>
  )
}

// Transaction cost calculator
const TxCostCalculator = ({ network, data }) => {
  const [txType, setTxType] = useState('transfer')
  const [amount, setAmount] = useState(1)
  const networkInfo = NETWORKS[network]

  const txTypes = {
    transfer: { label: 'Token Transfer', multiplier: 1 },
    swap: { label: 'DEX Swap', multiplier: 1.5 },
    nft: { label: 'NFT Mint', multiplier: 2 },
    stake: { label: 'Stake/Unstake', multiplier: 1.2 },
    bridge: { label: 'Bridge', multiplier: 3 }
  }

  const estimatedCost = data.avgTxCostUsd * txTypes[txType].multiplier * amount

  return (
    <div className="bg-white/5 rounded-xl p-4 border border-white/10">
      <h3 className="font-medium text-white mb-4 flex items-center gap-2">
        <Calculator size={18} className="text-purple-400" />
        Transaction Cost Calculator
      </h3>

      <div className="space-y-4">
        <div>
          <label className="text-sm text-slate-400 mb-2 block">Transaction Type</label>
          <select
            value={txType}
            onChange={(e) => setTxType(e.target.value)}
            className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2.5 text-white"
          >
            {Object.entries(txTypes).map(([key, type]) => (
              <option key={key} value={key}>{type.label}</option>
            ))}
          </select>
        </div>

        <div>
          <label className="text-sm text-slate-400 mb-2 block">Number of Transactions</label>
          <input
            type="number"
            value={amount}
            onChange={(e) => setAmount(Math.max(1, parseInt(e.target.value) || 1))}
            min="1"
            className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2.5 text-white"
          />
        </div>

        <div className="bg-gradient-to-br from-purple-500/10 to-blue-500/10 rounded-lg p-4 border border-purple-500/20">
          <div className="text-sm text-slate-400 mb-1">Estimated Cost</div>
          <div className="text-2xl font-bold text-white">{formatUsd(estimatedCost)}</div>
          <div className="text-xs text-slate-500 mt-1">
            Based on current {networkInfo.name} gas prices
          </div>
        </div>
      </div>
    </div>
  )
}

// Network comparison
const NetworkComparison = ({ gasData }) => {
  const sortedNetworks = Object.entries(gasData)
    .map(([key, data]) => ({
      network: key,
      ...data,
      info: NETWORKS[key]
    }))
    .sort((a, b) => a.avgTxCostUsd - b.avgTxCostUsd)

  return (
    <div className="bg-white/5 rounded-xl border border-white/10 overflow-hidden">
      <div className="p-4 border-b border-white/10">
        <h3 className="font-medium text-white flex items-center gap-2">
          <ArrowRight size={18} className="text-blue-400" />
          Network Comparison (by cost)
        </h3>
      </div>

      <div className="divide-y divide-white/5">
        {sortedNetworks.map((item, idx) => (
          <div key={item.network} className="p-3 flex items-center gap-4 hover:bg-white/5">
            <span className={`w-6 h-6 rounded flex items-center justify-center text-xs font-medium ${
              idx === 0 ? 'bg-green-400/20 text-green-400' :
              idx === sortedNetworks.length - 1 ? 'bg-red-400/20 text-red-400' :
              'bg-white/10 text-slate-400'
            }`}>
              {idx + 1}
            </span>

            <div className={`w-8 h-8 rounded-lg ${item.info.color} flex items-center justify-center`}>
              <span className="text-white text-xs font-bold">{item.info.symbol.slice(0, 2)}</span>
            </div>

            <div className="flex-1">
              <div className="font-medium text-white">{item.info.name}</div>
              <div className="text-xs text-slate-500">{item.info.symbol}</div>
            </div>

            <div className="text-right">
              <div className="font-medium text-white">{formatUsd(item.avgTxCostUsd)}</div>
              <div className={`text-xs ${item.change24h >= 0 ? 'text-red-400' : 'text-green-400'}`}>
                {item.change24h >= 0 ? '+' : ''}{item.change24h}%
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

// Main GasTracker component
export const GasTracker = () => {
  const [selectedNetwork, setSelectedNetwork] = useState('SOLANA')
  const [gasData] = useState(mockGasData)

  const selectedData = gasData[selectedNetwork]

  return (
    <div className="min-h-screen bg-[#0a0e14] text-white p-6">
      <div className="max-w-7xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold text-white mb-1 flex items-center gap-2">
              <Fuel className="text-orange-400" />
              Gas Tracker
            </h1>
            <p className="text-slate-400">Monitor gas prices across multiple networks</p>
          </div>

          <div className="flex items-center gap-3">
            <button className="flex items-center gap-2 px-4 py-2 bg-white/5 hover:bg-white/10 rounded-lg transition-colors">
              <Bell size={18} />
              <span>Set Alert</span>
            </button>
            <button className="p-2 bg-white/5 hover:bg-white/10 rounded-lg transition-colors">
              <RefreshCw size={18} />
            </button>
          </div>
        </div>

        {/* Network cards */}
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
          {Object.entries(gasData).map(([network, data]) => (
            <NetworkGasCard
              key={network}
              network={network}
              data={data}
              isSelected={selectedNetwork === network}
              onSelect={setSelectedNetwork}
            />
          ))}
        </div>

        {/* Main content */}
        <div className="grid lg:grid-cols-3 gap-6">
          {/* Left column */}
          <div className="lg:col-span-2 space-y-6">
            <PriorityFeeSelector network={selectedNetwork} data={selectedData} />
            <GasHistoryChart network={selectedNetwork} data={selectedData} />
          </div>

          {/* Right column */}
          <div className="space-y-6">
            <TxCostCalculator network={selectedNetwork} data={selectedData} />
            <BestTimesChart />
            <NetworkComparison gasData={gasData} />
          </div>
        </div>
      </div>
    </div>
  )
}

export default GasTracker
