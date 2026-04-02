import React, { useState, useMemo, useEffect, useCallback } from 'react'
import {
  BarChart3, TrendingUp, TrendingDown, Activity, DollarSign,
  Target, Percent, ArrowUpRight, ArrowDownRight, RefreshCw,
  AlertTriangle, Clock, ChevronDown, ChevronUp, Zap, Scale,
  PieChart, LineChart, Users, Wallet, Shield, Eye, Filter
} from 'lucide-react'

// Exchanges for derivatives
const EXCHANGES = {
  BINANCE: { name: 'Binance', color: '#F3BA2F' },
  BYBIT: { name: 'Bybit', color: '#F7A600' },
  OKX: { name: 'OKX', color: '#FFFFFF' },
  DYDX: { name: 'dYdX', color: '#6966FF' },
  GMX: { name: 'GMX', color: '#4D6EFF' },
  HYPERLIQUID: { name: 'Hyperliquid', color: '#00D4AA' },
  VERTEX: { name: 'Vertex', color: '#FF6B6B' },
  AEVO: { name: 'Aevo', color: '#7B61FF' }
}

// Trading pairs
const PAIRS = ['BTC-PERP', 'ETH-PERP', 'SOL-PERP', 'ARB-PERP', 'AVAX-PERP', 'MATIC-PERP', 'LINK-PERP', 'OP-PERP']

// Generate mock open interest data
const generateOpenInterestData = () => {
  return PAIRS.map(pair => ({
    pair,
    oi: Math.random() * 5000000000 + 500000000,
    oiChange24h: (Math.random() - 0.5) * 30,
    longRatio: 40 + Math.random() * 20,
    shortRatio: 40 + Math.random() * 20,
    volume24h: Math.random() * 20000000000 + 1000000000,
    trades24h: Math.floor(Math.random() * 500000 + 50000),
    price: pair.includes('BTC') ? 65000 + Math.random() * 5000 :
           pair.includes('ETH') ? 3500 + Math.random() * 500 :
           pair.includes('SOL') ? 150 + Math.random() * 30 :
           Math.random() * 50 + 5,
    priceChange24h: (Math.random() - 0.5) * 15,
    fundingRate: (Math.random() - 0.5) * 0.1,
    nextFunding: new Date(Date.now() + Math.random() * 8 * 60 * 60 * 1000),
    predictedFunding: (Math.random() - 0.5) * 0.1
  })).sort((a, b) => b.oi - a.oi)
}

// Generate exchange comparison data
const generateExchangeData = () => {
  return Object.keys(EXCHANGES).map(exchange => ({
    exchange,
    oi: Math.random() * 10000000000 + 1000000000,
    volume24h: Math.random() * 50000000000 + 5000000000,
    traders: Math.floor(Math.random() * 500000 + 50000),
    avgLeverage: Math.floor(Math.random() * 20 + 5),
    liquidations24h: Math.random() * 100000000 + 10000000,
    fees24h: Math.random() * 10000000 + 1000000,
    topPair: PAIRS[Math.floor(Math.random() * PAIRS.length)],
    fundingRevenue: Math.random() * 5000000 + 500000
  })).sort((a, b) => b.volume24h - a.volume24h)
}

// Generate liquidation data
const generateLiquidationData = () => {
  return Array.from({ length: 24 }, (_, i) => ({
    hour: new Date(Date.now() - (23 - i) * 60 * 60 * 1000),
    longLiqs: Math.random() * 50000000 + 5000000,
    shortLiqs: Math.random() * 50000000 + 5000000,
    totalLiqs: 0,
    largestLiq: Math.random() * 5000000 + 500000,
    liquidatedTraders: Math.floor(Math.random() * 1000 + 100)
  })).map(d => ({
    ...d,
    totalLiqs: d.longLiqs + d.shortLiqs
  }))
}

// Generate funding rate history
const generateFundingHistory = () => {
  return Array.from({ length: 30 }, (_, i) => ({
    time: new Date(Date.now() - (29 - i) * 8 * 60 * 60 * 1000),
    btc: (Math.random() - 0.5) * 0.1,
    eth: (Math.random() - 0.5) * 0.1,
    sol: (Math.random() - 0.5) * 0.15,
    avg: (Math.random() - 0.5) * 0.08
  }))
}

// Generate long/short ratio history
const generateLSRatioHistory = () => {
  return Array.from({ length: 24 }, (_, i) => ({
    time: new Date(Date.now() - (23 - i) * 60 * 60 * 1000),
    longRatio: 45 + Math.random() * 15,
    shortRatio: 0,
    topTraders: 40 + Math.random() * 20
  })).map(d => ({
    ...d,
    shortRatio: 100 - d.longRatio
  }))
}

export function DerivativesAnalytics() {
  const [openInterest, setOpenInterest] = useState([])
  const [exchangeData, setExchangeData] = useState([])
  const [liquidationData, setLiquidationData] = useState([])
  const [fundingHistory, setFundingHistory] = useState([])
  const [lsRatioHistory, setLSRatioHistory] = useState([])
  const [selectedPair, setSelectedPair] = useState('BTC-PERP')
  const [activeTab, setActiveTab] = useState('overview')
  const [isRefreshing, setIsRefreshing] = useState(false)

  useEffect(() => {
    setOpenInterest(generateOpenInterestData())
    setExchangeData(generateExchangeData())
    setLiquidationData(generateLiquidationData())
    setFundingHistory(generateFundingHistory())
    setLSRatioHistory(generateLSRatioHistory())
  }, [])

  // Auto-refresh every 30 seconds
  useEffect(() => {
    const interval = setInterval(() => {
      setOpenInterest(generateOpenInterestData())
      setLiquidationData(generateLiquidationData())
    }, 30000)
    return () => clearInterval(interval)
  }, [])

  const handleRefresh = useCallback(() => {
    setIsRefreshing(true)
    setTimeout(() => {
      setOpenInterest(generateOpenInterestData())
      setExchangeData(generateExchangeData())
      setLiquidationData(generateLiquidationData())
      setIsRefreshing(false)
    }, 1500)
  }, [])

  const totalOI = useMemo(() =>
    openInterest.reduce((sum, p) => sum + p.oi, 0),
    [openInterest]
  )

  const totalVolume = useMemo(() =>
    openInterest.reduce((sum, p) => sum + p.volume24h, 0),
    [openInterest]
  )

  const totalLiquidations = useMemo(() =>
    liquidationData.reduce((sum, d) => sum + d.totalLiqs, 0),
    [liquidationData]
  )

  const avgFunding = useMemo(() => {
    if (openInterest.length === 0) return 0
    return openInterest.reduce((sum, p) => sum + p.fundingRate, 0) / openInterest.length
  }, [openInterest])

  const selectedPairData = openInterest.find(p => p.pair === selectedPair)

  const formatNumber = (num, decimals = 2) => {
    if (Math.abs(num) >= 1e12) return (num / 1e12).toFixed(decimals) + 'T'
    if (Math.abs(num) >= 1e9) return (num / 1e9).toFixed(decimals) + 'B'
    if (Math.abs(num) >= 1e6) return (num / 1e6).toFixed(decimals) + 'M'
    if (Math.abs(num) >= 1e3) return (num / 1e3).toFixed(decimals) + 'K'
    return num.toFixed(decimals)
  }

  const formatCurrency = (num) => '$' + formatNumber(num)

  const formatPercent = (num) => {
    const prefix = num >= 0 ? '+' : ''
    return prefix + num.toFixed(2) + '%'
  }

  return (
    <div className="min-h-screen bg-[#0a0e14] text-white p-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold mb-2 flex items-center gap-3">
            <BarChart3 className="w-8 h-8 text-cyan-400" />
            Derivatives Analytics
          </h1>
          <p className="text-white/60">Open interest, funding rates, liquidations, and market sentiment</p>
        </div>

        <div className="flex items-center gap-4">
          <select
            value={selectedPair}
            onChange={(e) => setSelectedPair(e.target.value)}
            className="bg-white/5 border border-white/10 rounded-lg px-4 py-2 focus:outline-none"
          >
            {PAIRS.map(pair => (
              <option key={pair} value={pair} className="bg-[#0a0e14]">{pair}</option>
            ))}
          </select>

          <button
            onClick={handleRefresh}
            disabled={isRefreshing}
            className="p-2 bg-white/10 hover:bg-white/20 rounded-lg transition-colors"
          >
            <RefreshCw className={`w-5 h-5 ${isRefreshing ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {/* Global Stats */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
        <div className="bg-white/5 rounded-xl border border-white/10 p-4">
          <div className="flex items-center gap-2 text-white/60 mb-2">
            <Target className="w-4 h-4" />
            Total Open Interest
          </div>
          <div className="text-2xl font-bold">{formatCurrency(totalOI)}</div>
          <div className="text-sm text-green-400">+4.2% (24h)</div>
        </div>

        <div className="bg-white/5 rounded-xl border border-white/10 p-4">
          <div className="flex items-center gap-2 text-white/60 mb-2">
            <Activity className="w-4 h-4" />
            24h Volume
          </div>
          <div className="text-2xl font-bold">{formatCurrency(totalVolume)}</div>
          <div className="text-sm text-red-400">-2.8% (24h)</div>
        </div>

        <div className="bg-white/5 rounded-xl border border-white/10 p-4">
          <div className="flex items-center gap-2 text-white/60 mb-2">
            <Zap className="w-4 h-4" />
            24h Liquidations
          </div>
          <div className="text-2xl font-bold text-orange-400">{formatCurrency(totalLiquidations)}</div>
          <div className="text-sm text-white/60">across all pairs</div>
        </div>

        <div className="bg-white/5 rounded-xl border border-white/10 p-4">
          <div className="flex items-center gap-2 text-white/60 mb-2">
            <Percent className="w-4 h-4" />
            Avg Funding Rate
          </div>
          <div className={`text-2xl font-bold ${avgFunding >= 0 ? 'text-green-400' : 'text-red-400'}`}>
            {(avgFunding * 100).toFixed(4)}%
          </div>
          <div className="text-sm text-white/60">8h interval</div>
        </div>
      </div>

      {/* Selected Pair Detail */}
      {selectedPairData && (
        <div className="bg-white/5 rounded-xl border border-white/10 p-4 mb-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-xl font-bold">{selectedPair}</h2>
            <div className={`text-2xl font-bold ${selectedPairData.priceChange24h >= 0 ? 'text-green-400' : 'text-red-400'}`}>
              ${selectedPairData.price.toFixed(2)}
              <span className="text-sm ml-2">{formatPercent(selectedPairData.priceChange24h)}</span>
            </div>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-6 gap-4">
            <div>
              <div className="text-white/60 text-sm">Open Interest</div>
              <div className="font-bold">{formatCurrency(selectedPairData.oi)}</div>
              <div className={`text-xs ${selectedPairData.oiChange24h >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                {formatPercent(selectedPairData.oiChange24h)}
              </div>
            </div>
            <div>
              <div className="text-white/60 text-sm">24h Volume</div>
              <div className="font-bold">{formatCurrency(selectedPairData.volume24h)}</div>
            </div>
            <div>
              <div className="text-white/60 text-sm">Funding Rate</div>
              <div className={`font-bold ${selectedPairData.fundingRate >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                {(selectedPairData.fundingRate * 100).toFixed(4)}%
              </div>
            </div>
            <div>
              <div className="text-white/60 text-sm">Next Funding</div>
              <div className="font-bold">
                {selectedPairData.nextFunding.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
              </div>
            </div>
            <div>
              <div className="text-white/60 text-sm">Long Ratio</div>
              <div className="font-bold text-green-400">{selectedPairData.longRatio.toFixed(1)}%</div>
            </div>
            <div>
              <div className="text-white/60 text-sm">Short Ratio</div>
              <div className="font-bold text-red-400">{selectedPairData.shortRatio.toFixed(1)}%</div>
            </div>
          </div>

          {/* Long/Short Bar */}
          <div className="mt-4">
            <div className="flex h-4 rounded-full overflow-hidden">
              <div
                className="bg-green-500 transition-all"
                style={{ width: `${selectedPairData.longRatio}%` }}
              />
              <div
                className="bg-red-500 transition-all"
                style={{ width: `${selectedPairData.shortRatio}%` }}
              />
            </div>
            <div className="flex justify-between mt-1 text-xs text-white/60">
              <span className="text-green-400">Longs: {selectedPairData.longRatio.toFixed(1)}%</span>
              <span className="text-red-400">Shorts: {selectedPairData.shortRatio.toFixed(1)}%</span>
            </div>
          </div>
        </div>
      )}

      {/* Tabs */}
      <div className="flex gap-4 mb-6 border-b border-white/10 overflow-x-auto">
        {['overview', 'liquidations', 'funding', 'exchanges'].map(tab => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`pb-3 px-2 font-medium capitalize whitespace-nowrap transition-colors ${
              activeTab === tab
                ? 'text-cyan-400 border-b-2 border-cyan-400'
                : 'text-white/60 hover:text-white'
            }`}
          >
            {tab}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      {activeTab === 'overview' && (
        <div className="bg-white/5 rounded-xl border border-white/10 overflow-hidden">
          <div className="p-4 border-b border-white/10">
            <h2 className="font-semibold flex items-center gap-2">
              <Target className="w-5 h-5 text-cyan-400" />
              Open Interest by Pair
            </h2>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-white/10">
                  <th className="text-left p-4 text-white/60 font-medium">Pair</th>
                  <th className="text-right p-4 text-white/60 font-medium">Price</th>
                  <th className="text-right p-4 text-white/60 font-medium">24h Change</th>
                  <th className="text-right p-4 text-white/60 font-medium">Open Interest</th>
                  <th className="text-right p-4 text-white/60 font-medium">OI Change</th>
                  <th className="text-right p-4 text-white/60 font-medium">Volume</th>
                  <th className="text-right p-4 text-white/60 font-medium">Funding</th>
                  <th className="text-center p-4 text-white/60 font-medium">Long/Short</th>
                </tr>
              </thead>
              <tbody>
                {openInterest.map((data, idx) => (
                  <tr
                    key={data.pair}
                    className={`border-b border-white/5 hover:bg-white/5 cursor-pointer ${
                      data.pair === selectedPair ? 'bg-cyan-500/10' : ''
                    }`}
                    onClick={() => setSelectedPair(data.pair)}
                  >
                    <td className="p-4 font-medium">{data.pair}</td>
                    <td className="p-4 text-right font-medium">${data.price.toFixed(2)}</td>
                    <td className={`p-4 text-right ${data.priceChange24h >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                      {formatPercent(data.priceChange24h)}
                    </td>
                    <td className="p-4 text-right font-medium">{formatCurrency(data.oi)}</td>
                    <td className={`p-4 text-right ${data.oiChange24h >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                      {formatPercent(data.oiChange24h)}
                    </td>
                    <td className="p-4 text-right">{formatCurrency(data.volume24h)}</td>
                    <td className={`p-4 text-right ${data.fundingRate >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                      {(data.fundingRate * 100).toFixed(4)}%
                    </td>
                    <td className="p-4">
                      <div className="flex h-2 rounded-full overflow-hidden">
                        <div className="bg-green-500" style={{ width: `${data.longRatio}%` }} />
                        <div className="bg-red-500" style={{ width: `${data.shortRatio}%` }} />
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {activeTab === 'liquidations' && (
        <div className="space-y-6">
          {/* Liquidation Summary */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="bg-white/5 rounded-xl border border-white/10 p-4">
              <div className="flex items-center gap-2 text-white/60 mb-2">
                <ArrowDownRight className="w-4 h-4 text-green-400" />
                Long Liquidations (24h)
              </div>
              <div className="text-2xl font-bold text-red-400">
                {formatCurrency(liquidationData.reduce((sum, d) => sum + d.longLiqs, 0))}
              </div>
            </div>

            <div className="bg-white/5 rounded-xl border border-white/10 p-4">
              <div className="flex items-center gap-2 text-white/60 mb-2">
                <ArrowUpRight className="w-4 h-4 text-red-400" />
                Short Liquidations (24h)
              </div>
              <div className="text-2xl font-bold text-green-400">
                {formatCurrency(liquidationData.reduce((sum, d) => sum + d.shortLiqs, 0))}
              </div>
            </div>

            <div className="bg-white/5 rounded-xl border border-white/10 p-4">
              <div className="flex items-center gap-2 text-white/60 mb-2">
                <Zap className="w-4 h-4" />
                Largest Liquidation
              </div>
              <div className="text-2xl font-bold text-orange-400">
                {formatCurrency(Math.max(...liquidationData.map(d => d.largestLiq)))}
              </div>
            </div>
          </div>

          {/* Liquidation Timeline */}
          <div className="bg-white/5 rounded-xl border border-white/10 p-4">
            <h3 className="font-medium mb-4">Liquidations by Hour</h3>
            <div className="space-y-2">
              {liquidationData.slice(-12).map((data, idx) => (
                <div key={idx} className="flex items-center gap-4">
                  <div className="w-16 text-sm text-white/60">
                    {data.hour.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                  </div>
                  <div className="flex-1 flex gap-1">
                    <div
                      className="h-6 bg-red-500 rounded-l"
                      style={{ width: `${(data.longLiqs / (data.totalLiqs || 1)) * 100}%` }}
                    />
                    <div
                      className="h-6 bg-green-500 rounded-r"
                      style={{ width: `${(data.shortLiqs / (data.totalLiqs || 1)) * 100}%` }}
                    />
                  </div>
                  <div className="w-24 text-right text-sm">{formatCurrency(data.totalLiqs)}</div>
                </div>
              ))}
            </div>
            <div className="flex items-center gap-4 mt-4 text-sm">
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 rounded bg-red-500" />
                <span className="text-white/60">Long Liquidations</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 rounded bg-green-500" />
                <span className="text-white/60">Short Liquidations</span>
              </div>
            </div>
          </div>
        </div>
      )}

      {activeTab === 'funding' && (
        <div className="space-y-6">
          {/* Current Funding Rates */}
          <div className="bg-white/5 rounded-xl border border-white/10 overflow-hidden">
            <div className="p-4 border-b border-white/10">
              <h2 className="font-semibold flex items-center gap-2">
                <Percent className="w-5 h-5 text-cyan-400" />
                Current Funding Rates
              </h2>
            </div>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 p-4">
              {openInterest.slice(0, 8).map((data, idx) => (
                <div key={data.pair} className="bg-white/5 rounded-lg p-4">
                  <div className="text-sm text-white/60 mb-1">{data.pair}</div>
                  <div className={`text-xl font-bold ${data.fundingRate >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                    {(data.fundingRate * 100).toFixed(4)}%
                  </div>
                  <div className="text-xs text-white/60 mt-1">
                    Predicted: {(data.predictedFunding * 100).toFixed(4)}%
                  </div>
                  <div className="text-xs text-white/60">
                    Next: {data.nextFunding.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Funding Analysis */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="bg-white/5 rounded-xl border border-white/10 p-4">
              <h3 className="font-medium mb-4 flex items-center gap-2">
                <TrendingUp className="w-5 h-5 text-green-400" />
                Positive Funding (Longs Pay)
              </h3>
              <div className="space-y-2">
                {openInterest.filter(p => p.fundingRate > 0).slice(0, 5).map((data, idx) => (
                  <div key={data.pair} className="flex items-center justify-between p-2 bg-white/5 rounded">
                    <span>{data.pair}</span>
                    <span className="text-green-400">{(data.fundingRate * 100).toFixed(4)}%</span>
                  </div>
                ))}
              </div>
            </div>

            <div className="bg-white/5 rounded-xl border border-white/10 p-4">
              <h3 className="font-medium mb-4 flex items-center gap-2">
                <TrendingDown className="w-5 h-5 text-red-400" />
                Negative Funding (Shorts Pay)
              </h3>
              <div className="space-y-2">
                {openInterest.filter(p => p.fundingRate < 0).slice(0, 5).map((data, idx) => (
                  <div key={data.pair} className="flex items-center justify-between p-2 bg-white/5 rounded">
                    <span>{data.pair}</span>
                    <span className="text-red-400">{(data.fundingRate * 100).toFixed(4)}%</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      {activeTab === 'exchanges' && (
        <div className="bg-white/5 rounded-xl border border-white/10 overflow-hidden">
          <div className="p-4 border-b border-white/10">
            <h2 className="font-semibold flex items-center gap-2">
              <Scale className="w-5 h-5 text-cyan-400" />
              Exchange Comparison
            </h2>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-white/10">
                  <th className="text-left p-4 text-white/60 font-medium">Exchange</th>
                  <th className="text-right p-4 text-white/60 font-medium">Open Interest</th>
                  <th className="text-right p-4 text-white/60 font-medium">24h Volume</th>
                  <th className="text-right p-4 text-white/60 font-medium">Traders</th>
                  <th className="text-right p-4 text-white/60 font-medium">Avg Leverage</th>
                  <th className="text-right p-4 text-white/60 font-medium">Liquidations</th>
                  <th className="text-left p-4 text-white/60 font-medium">Top Pair</th>
                </tr>
              </thead>
              <tbody>
                {exchangeData.map((data, idx) => (
                  <tr key={data.exchange} className="border-b border-white/5 hover:bg-white/5">
                    <td className="p-4">
                      <div className="flex items-center gap-3">
                        <div
                          className="w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold"
                          style={{ backgroundColor: EXCHANGES[data.exchange].color + '30', color: EXCHANGES[data.exchange].color }}
                        >
                          {data.exchange.slice(0, 2)}
                        </div>
                        <span className="font-medium">{EXCHANGES[data.exchange].name}</span>
                      </div>
                    </td>
                    <td className="p-4 text-right font-medium">{formatCurrency(data.oi)}</td>
                    <td className="p-4 text-right">{formatCurrency(data.volume24h)}</td>
                    <td className="p-4 text-right">{formatNumber(data.traders, 0)}</td>
                    <td className="p-4 text-right">{data.avgLeverage}x</td>
                    <td className="p-4 text-right text-orange-400">{formatCurrency(data.liquidations24h)}</td>
                    <td className="p-4">
                      <span className="px-2 py-1 bg-white/10 rounded text-sm">{data.topPair}</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Market Insight */}
      <div className="mt-6 p-4 bg-white/5 rounded-xl border border-white/10">
        <div className="flex items-start gap-3">
          <AlertTriangle className="w-5 h-5 text-yellow-400 flex-shrink-0 mt-0.5" />
          <div className="text-sm">
            <div className="font-medium text-yellow-400 mb-1">Market Insight</div>
            <p className="text-white/70">
              {avgFunding > 0.01 ? (
                "High positive funding rates indicate bullish sentiment. Longs are paying shorts, which could lead to a correction if overleveraged positions are liquidated."
              ) : avgFunding < -0.01 ? (
                "Negative funding rates indicate bearish sentiment. Shorts are paying longs, suggesting potential for a short squeeze."
              ) : (
                "Funding rates are neutral, indicating balanced market sentiment between longs and shorts."
              )}
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}

export default DerivativesAnalytics
