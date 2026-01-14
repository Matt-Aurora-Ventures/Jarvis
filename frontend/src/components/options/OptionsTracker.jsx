import React, { useState, useMemo, useCallback } from 'react'
import {
  TrendingUp, TrendingDown, ArrowUpRight, ArrowDownRight, RefreshCw,
  DollarSign, Percent, Activity, BarChart3, Target, Calendar,
  ChevronDown, ChevronUp, Zap, Clock, ExternalLink, Filter,
  Search, Star, StarOff, AlertTriangle, Layers, ArrowLeftRight,
  Circle, Square, Triangle, Info, Settings
} from 'lucide-react'

// Exchanges with options markets
const EXCHANGES = {
  DERIBIT: { name: 'Deribit', color: '#20B26C', marketShare: 85 },
  OKX: { name: 'OKX', color: '#FFFFFF', marketShare: 8 },
  BYBIT: { name: 'Bybit', color: '#F7A600', marketShare: 4 },
  BINANCE: { name: 'Binance', color: '#F0B90B', marketShare: 3 }
}

// Option types
const OPTION_TYPE = {
  CALL: { label: 'Call', color: 'text-green-400', bg: 'bg-green-500/20' },
  PUT: { label: 'Put', color: 'text-red-400', bg: 'bg-red-500/20' }
}

// Format large numbers
const formatValue = (value, decimals = 2) => {
  if (value >= 1e9) return `$${(value / 1e9).toFixed(decimals)}B`
  if (value >= 1e6) return `$${(value / 1e6).toFixed(decimals)}M`
  if (value >= 1e3) return `$${(value / 1e3).toFixed(decimals)}K`
  return `$${value.toFixed(decimals)}`
}

// Mock options chain data for BTC
const MOCK_OPTIONS_CHAIN = [
  { strike: 85000, callBid: 12850, callAsk: 12950, callIV: 52.3, callOI: 2450, callDelta: 0.92, putBid: 320, putAsk: 345, putIV: 48.5, putOI: 1820, putDelta: -0.08 },
  { strike: 90000, callBid: 8420, callAsk: 8520, callIV: 48.7, callOI: 3890, callDelta: 0.85, putBid: 680, putAsk: 720, putIV: 46.2, putOI: 2450, putDelta: -0.15 },
  { strike: 95000, callBid: 4650, callAsk: 4750, callIV: 45.2, callOI: 5420, callDelta: 0.72, putBid: 1450, putAsk: 1520, putIV: 44.8, putOI: 3210, putDelta: -0.28 },
  { strike: 97500, callBid: 3180, callAsk: 3280, callIV: 43.8, callOI: 6820, callDelta: 0.58, putBid: 2380, putAsk: 2480, putIV: 43.5, putOI: 4560, putDelta: -0.42 },
  { strike: 100000, callBid: 1920, callAsk: 2020, callIV: 42.5, callOI: 8950, callDelta: 0.45, putBid: 3680, putAsk: 3780, putIV: 42.8, putOI: 5890, putDelta: -0.55 },
  { strike: 102500, callBid: 1120, callAsk: 1220, callIV: 41.8, callOI: 7230, callDelta: 0.32, putBid: 5320, putAsk: 5420, putIV: 42.2, putOI: 4120, putDelta: -0.68 },
  { strike: 105000, callBid: 620, callAsk: 720, callIV: 41.2, callOI: 5680, callDelta: 0.22, putBid: 7350, putAsk: 7450, putIV: 41.5, putOI: 3450, putDelta: -0.78 },
  { strike: 110000, callBid: 245, callAsk: 320, callIV: 40.5, callOI: 4250, callDelta: 0.12, putBid: 12420, putAsk: 12520, putIV: 40.8, putOI: 2180, putDelta: -0.88 },
  { strike: 115000, callBid: 85, callAsk: 145, callIV: 40.2, callOI: 2890, callDelta: 0.05, putBid: 17580, putAsk: 17680, putIV: 40.5, putOI: 1420, putDelta: -0.95 }
]

// Mock expiration dates
const MOCK_EXPIRATIONS = [
  { date: '2026-01-17', daysToExpiry: 3, label: '3D', volume: 1250000000, oi: 4200000000 },
  { date: '2026-01-24', daysToExpiry: 10, label: '10D', volume: 980000000, oi: 5600000000 },
  { date: '2026-01-31', daysToExpiry: 17, label: '17D', volume: 720000000, oi: 6800000000 },
  { date: '2026-02-28', daysToExpiry: 45, label: '45D', volume: 450000000, oi: 8200000000 },
  { date: '2026-03-28', daysToExpiry: 73, label: '73D', volume: 320000000, oi: 9500000000 },
  { date: '2026-06-26', daysToExpiry: 163, label: '163D', volume: 180000000, oi: 7800000000 }
]

// Mock market overview
const MARKET_OVERVIEW = {
  btcSpot: 97542.50,
  totalOI: 38500000000,
  totalVolume24h: 4200000000,
  putCallRatio: 0.72,
  maxPainStrike: 100000,
  impliedVolatility: {
    atm: 43.5,
    iv25Delta: 48.2,
    iv25DeltaPut: 42.8,
    ivSkew: 5.4
  },
  dvol: 52.8,
  dvolChange: -2.3
}

// Options chain row
const OptionsChainRow = ({ data, spotPrice, onSelectOption }) => {
  const isITMCall = data.strike < spotPrice
  const isITMPut = data.strike > spotPrice
  const isATM = Math.abs(data.strike - spotPrice) / spotPrice < 0.02

  return (
    <div className={`grid grid-cols-11 gap-2 py-2 px-3 text-sm ${
      isATM ? 'bg-yellow-500/10 border-l-2 border-yellow-500' : 'hover:bg-white/5'
    } transition-colors`}>
      {/* Call side */}
      <div className={`text-right ${isITMCall ? 'font-medium text-green-400' : 'text-gray-400'}`}>
        {data.callDelta.toFixed(2)}
      </div>
      <div className="text-right text-gray-400">{data.callIV.toFixed(1)}%</div>
      <div className="text-right font-mono">{data.callOI.toLocaleString()}</div>
      <div className="text-right text-green-400 font-mono">${data.callBid.toLocaleString()}</div>
      <div className="text-right text-red-400 font-mono">${data.callAsk.toLocaleString()}</div>

      {/* Strike */}
      <div className={`text-center font-bold ${isATM ? 'text-yellow-400' : ''}`}>
        ${data.strike.toLocaleString()}
        {isATM && <span className="text-xs ml-1">(ATM)</span>}
      </div>

      {/* Put side */}
      <div className="text-left text-green-400 font-mono">${data.putBid.toLocaleString()}</div>
      <div className="text-left text-red-400 font-mono">${data.putAsk.toLocaleString()}</div>
      <div className="text-left font-mono">{data.putOI.toLocaleString()}</div>
      <div className="text-left text-gray-400">{data.putIV.toFixed(1)}%</div>
      <div className={`text-left ${isITMPut ? 'font-medium text-red-400' : 'text-gray-400'}`}>
        {data.putDelta.toFixed(2)}
      </div>
    </div>
  )
}

// Options chain header
const OptionsChainHeader = () => (
  <div className="grid grid-cols-11 gap-2 py-2 px-3 text-xs text-gray-500 border-b border-white/10 font-medium">
    <div className="text-right">Delta</div>
    <div className="text-right">IV</div>
    <div className="text-right">OI</div>
    <div className="text-right text-green-400">Bid</div>
    <div className="text-right text-red-400">Ask</div>
    <div className="text-center">STRIKE</div>
    <div className="text-left text-green-400">Bid</div>
    <div className="text-left text-red-400">Ask</div>
    <div className="text-left">OI</div>
    <div className="text-left">IV</div>
    <div className="text-left">Delta</div>
  </div>
)

// IV Surface chart (simplified)
const IVSurface = ({ data }) => {
  return (
    <div className="bg-white/5 rounded-xl p-4 border border-white/10">
      <h3 className="text-sm font-medium text-gray-300 mb-4 flex items-center gap-2">
        <BarChart3 className="w-4 h-4" />
        Implied Volatility Surface
      </h3>

      <div className="space-y-3">
        {data.slice(0, 6).map((row, idx) => (
          <div key={idx} className="flex items-center gap-3">
            <span className="w-16 text-xs text-gray-500">${(row.strike / 1000).toFixed(0)}K</span>
            <div className="flex-1 flex gap-1">
              <div
                className="h-6 bg-gradient-to-r from-blue-500 to-purple-500 rounded"
                style={{ width: `${row.callIV}%`, opacity: 0.3 + (row.callIV / 100) * 0.7 }}
                title={`Call IV: ${row.callIV}%`}
              />
              <div
                className="h-6 bg-gradient-to-r from-purple-500 to-red-500 rounded"
                style={{ width: `${row.putIV}%`, opacity: 0.3 + (row.putIV / 100) * 0.7 }}
                title={`Put IV: ${row.putIV}%`}
              />
            </div>
          </div>
        ))}
      </div>

      <div className="flex items-center justify-center gap-6 mt-4 text-xs text-gray-500">
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 rounded bg-gradient-to-r from-blue-500 to-purple-500" />
          Call IV
        </div>
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 rounded bg-gradient-to-r from-purple-500 to-red-500" />
          Put IV
        </div>
      </div>
    </div>
  )
}

// Expiration selector
const ExpirationSelector = ({ expirations, selected, onSelect }) => {
  return (
    <div className="flex gap-2 overflow-x-auto pb-2">
      {expirations.map(exp => (
        <button
          key={exp.date}
          onClick={() => onSelect(exp.date)}
          className={`px-4 py-2 rounded-lg text-sm font-medium whitespace-nowrap transition-colors ${
            selected === exp.date
              ? 'bg-purple-500/20 text-purple-400 border border-purple-500/50'
              : 'bg-white/5 text-gray-400 border border-white/10 hover:bg-white/10'
          }`}
        >
          <div>{exp.label}</div>
          <div className="text-xs opacity-60">{exp.date}</div>
        </button>
      ))}
    </div>
  )
}

// Market metrics
const MarketMetrics = ({ data }) => {
  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
      <div className="bg-white/5 rounded-xl p-4 border border-white/10">
        <div className="text-sm text-gray-400 mb-1 flex items-center gap-2">
          <Layers className="w-4 h-4" />
          Total Open Interest
        </div>
        <div className="text-2xl font-bold">{formatValue(data.totalOI, 1)}</div>
      </div>

      <div className="bg-white/5 rounded-xl p-4 border border-white/10">
        <div className="text-sm text-gray-400 mb-1 flex items-center gap-2">
          <Activity className="w-4 h-4" />
          24h Volume
        </div>
        <div className="text-2xl font-bold">{formatValue(data.totalVolume24h, 1)}</div>
      </div>

      <div className="bg-white/5 rounded-xl p-4 border border-white/10">
        <div className="text-sm text-gray-400 mb-1 flex items-center gap-2">
          <ArrowLeftRight className="w-4 h-4" />
          Put/Call Ratio
        </div>
        <div className={`text-2xl font-bold ${
          data.putCallRatio > 1 ? 'text-red-400' : 'text-green-400'
        }`}>
          {data.putCallRatio.toFixed(2)}
        </div>
        <div className="text-xs text-gray-500">
          {data.putCallRatio > 1 ? 'Bearish bias' : 'Bullish bias'}
        </div>
      </div>

      <div className="bg-white/5 rounded-xl p-4 border border-white/10">
        <div className="text-sm text-gray-400 mb-1 flex items-center gap-2">
          <Target className="w-4 h-4" />
          Max Pain Strike
        </div>
        <div className="text-2xl font-bold">${data.maxPainStrike.toLocaleString()}</div>
        <div className="text-xs text-gray-500">
          {((data.maxPainStrike / data.btcSpot - 1) * 100).toFixed(1)}% from spot
        </div>
      </div>
    </div>
  )
}

// Volatility metrics
const VolatilityMetrics = ({ iv }) => {
  return (
    <div className="bg-white/5 rounded-xl p-4 border border-white/10">
      <h3 className="text-sm font-medium text-gray-300 mb-4 flex items-center gap-2">
        <Percent className="w-4 h-4" />
        Volatility Metrics
      </h3>

      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <span className="text-gray-400">ATM IV</span>
          <span className="font-mono font-medium">{iv.atm}%</span>
        </div>

        <div className="flex items-center justify-between">
          <span className="text-gray-400">25D Call IV</span>
          <span className="font-mono font-medium">{iv.iv25Delta}%</span>
        </div>

        <div className="flex items-center justify-between">
          <span className="text-gray-400">25D Put IV</span>
          <span className="font-mono font-medium">{iv.iv25DeltaPut}%</span>
        </div>

        <div className="border-t border-white/10 pt-3">
          <div className="flex items-center justify-between">
            <span className="text-gray-400">IV Skew</span>
            <span className={`font-mono font-medium ${
              iv.ivSkew > 0 ? 'text-green-400' : 'text-red-400'
            }`}>
              {iv.ivSkew > 0 ? '+' : ''}{iv.ivSkew}%
            </span>
          </div>
          <div className="text-xs text-gray-500 mt-1">
            {iv.ivSkew > 0 ? 'Calls more expensive (bullish sentiment)' : 'Puts more expensive (bearish sentiment)'}
          </div>
        </div>
      </div>
    </div>
  )
}

// DVOL Index
const DvolIndex = ({ dvol, dvolChange }) => {
  return (
    <div className="bg-white/5 rounded-xl p-4 border border-white/10">
      <h3 className="text-sm font-medium text-gray-300 mb-4 flex items-center gap-2">
        <Zap className="w-4 h-4 text-yellow-400" />
        Deribit DVOL Index
      </h3>

      <div className="text-center py-4">
        <div className="text-4xl font-bold">{dvol}</div>
        <div className={`flex items-center justify-center gap-1 mt-2 ${
          dvolChange > 0 ? 'text-green-400' : 'text-red-400'
        }`}>
          {dvolChange > 0 ? <TrendingUp className="w-4 h-4" /> : <TrendingDown className="w-4 h-4" />}
          {dvolChange > 0 ? '+' : ''}{dvolChange}%
        </div>
        <div className="text-xs text-gray-500 mt-2">30-day BTC implied volatility</div>
      </div>

      <div className="mt-4 pt-4 border-t border-white/10">
        <div className="text-xs text-gray-500 mb-2">Volatility Range</div>
        <div className="h-2 bg-white/10 rounded-full relative">
          <div
            className="absolute h-full bg-gradient-to-r from-green-500 via-yellow-500 to-red-500 rounded-full"
            style={{ width: '100%', opacity: 0.5 }}
          />
          <div
            className="absolute w-3 h-3 bg-white rounded-full -top-0.5 transform -translate-x-1/2"
            style={{ left: `${Math.min(dvol, 100)}%` }}
          />
        </div>
        <div className="flex justify-between text-xs text-gray-500 mt-1">
          <span>Low</span>
          <span>High</span>
        </div>
      </div>
    </div>
  )
}

// Open Interest by Strike
const OIByStrike = ({ data }) => {
  const maxOI = Math.max(...data.map(d => Math.max(d.callOI, d.putOI)))

  return (
    <div className="bg-white/5 rounded-xl p-4 border border-white/10">
      <h3 className="text-sm font-medium text-gray-300 mb-4 flex items-center gap-2">
        <BarChart3 className="w-4 h-4" />
        Open Interest by Strike
      </h3>

      <div className="space-y-2">
        {data.map((row, idx) => (
          <div key={idx} className="flex items-center gap-2">
            <div className="w-16 text-xs text-gray-500 text-right">
              ${(row.strike / 1000).toFixed(0)}K
            </div>
            <div className="flex-1 flex gap-0.5">
              <div
                className="h-4 bg-green-500/60 rounded-l"
                style={{ width: `${(row.callOI / maxOI) * 50}%` }}
              />
              <div
                className="h-4 bg-red-500/60 rounded-r"
                style={{ width: `${(row.putOI / maxOI) * 50}%` }}
              />
            </div>
          </div>
        ))}
      </div>

      <div className="flex items-center justify-center gap-6 mt-4 text-xs text-gray-500">
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 rounded bg-green-500/60" />
          Calls
        </div>
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 rounded bg-red-500/60" />
          Puts
        </div>
      </div>
    </div>
  )
}

// Main component
export const OptionsTracker = () => {
  const [selectedAsset, setSelectedAsset] = useState('BTC')
  const [selectedExpiration, setSelectedExpiration] = useState(MOCK_EXPIRATIONS[1].date)
  const [optionsChain] = useState(MOCK_OPTIONS_CHAIN)
  const [marketData] = useState(MARKET_OVERVIEW)
  const [refreshing, setRefreshing] = useState(false)
  const [showGreeks, setShowGreeks] = useState(true)

  const handleRefresh = useCallback(() => {
    setRefreshing(true)
    setTimeout(() => setRefreshing(false), 1500)
  }, [])

  return (
    <div className="min-h-screen bg-[#0a0e14] text-white p-6">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-bold flex items-center gap-3">
              <Triangle className="w-7 h-7 text-purple-400" />
              Options Tracker
            </h1>
            <p className="text-gray-400 mt-1">Track crypto options markets and volatility</p>
          </div>

          <div className="flex items-center gap-3">
            <div className="flex bg-white/5 rounded-lg p-1">
              {['BTC', 'ETH'].map(asset => (
                <button
                  key={asset}
                  onClick={() => setSelectedAsset(asset)}
                  className={`px-4 py-1.5 rounded text-sm font-medium transition-colors ${
                    selectedAsset === asset
                      ? 'bg-purple-500/20 text-purple-400'
                      : 'text-gray-400 hover:text-white'
                  }`}
                >
                  {asset}
                </button>
              ))}
            </div>

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

        {/* Spot price banner */}
        <div className="bg-white/5 rounded-xl p-4 border border-white/10 mb-6">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <div>
                <div className="text-sm text-gray-400">BTC Spot Price</div>
                <div className="text-2xl font-bold font-mono">${marketData.btcSpot.toLocaleString()}</div>
              </div>
            </div>
            <div className="flex items-center gap-6 text-sm">
              {Object.entries(EXCHANGES).slice(0, 4).map(([key, ex]) => (
                <div key={key} className="text-center">
                  <div className="text-gray-500">{ex.name}</div>
                  <div className="font-medium" style={{ color: ex.color }}>
                    {ex.marketShare}% share
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Market Metrics */}
        <MarketMetrics data={marketData} />

        {/* Expiration selector */}
        <div className="mb-6">
          <h3 className="text-sm font-medium text-gray-400 mb-3">Select Expiration</h3>
          <ExpirationSelector
            expirations={MOCK_EXPIRATIONS}
            selected={selectedExpiration}
            onSelect={setSelectedExpiration}
          />
        </div>

        {/* Main content grid */}
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
          {/* Options Chain - 3 columns */}
          <div className="lg:col-span-3 bg-white/5 rounded-xl border border-white/10 overflow-hidden">
            <div className="p-4 border-b border-white/10 flex items-center justify-between">
              <h3 className="font-medium flex items-center gap-2">
                <Layers className="w-4 h-4" />
                Options Chain - {selectedExpiration}
              </h3>
              <div className="flex items-center gap-2">
                <span className="text-xs text-gray-500">CALLS</span>
                <ArrowLeftRight className="w-4 h-4 text-gray-500" />
                <span className="text-xs text-gray-500">PUTS</span>
              </div>
            </div>

            <OptionsChainHeader />

            <div className="max-h-96 overflow-y-auto">
              {optionsChain.map((row, idx) => (
                <OptionsChainRow
                  key={idx}
                  data={row}
                  spotPrice={marketData.btcSpot}
                />
              ))}
            </div>
          </div>

          {/* Sidebar */}
          <div className="space-y-6">
            <DvolIndex dvol={marketData.dvol} dvolChange={marketData.dvolChange} />
            <VolatilityMetrics iv={marketData.impliedVolatility} />
            <OIByStrike data={optionsChain} />
          </div>
        </div>

        {/* IV Surface */}
        <div className="mt-6">
          <IVSurface data={optionsChain} />
        </div>
      </div>
    </div>
  )
}

export default OptionsTracker
