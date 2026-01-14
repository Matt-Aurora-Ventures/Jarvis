import React, { useState, useMemo, useEffect } from 'react'
import {
  ArrowLeftRight, TrendingUp, DollarSign, Percent, Clock, Zap,
  RefreshCw, Filter, Bell, AlertTriangle, CheckCircle, ArrowRight,
  BarChart3, Settings, Download, Eye, Target, Flame, Building2
} from 'lucide-react'

const EXCHANGES = [
  { id: 'binance', name: 'Binance', type: 'CEX', color: 'text-yellow-400' },
  { id: 'coinbase', name: 'Coinbase', type: 'CEX', color: 'text-blue-400' },
  { id: 'kraken', name: 'Kraken', type: 'CEX', color: 'text-purple-400' },
  { id: 'okx', name: 'OKX', type: 'CEX', color: 'text-white' },
  { id: 'bybit', name: 'Bybit', type: 'CEX', color: 'text-orange-400' },
  { id: 'kucoin', name: 'KuCoin', type: 'CEX', color: 'text-green-400' },
  { id: 'uniswap', name: 'Uniswap', type: 'DEX', color: 'text-pink-400' },
  { id: 'sushiswap', name: 'SushiSwap', type: 'DEX', color: 'text-pink-500' },
  { id: 'pancake', name: 'PancakeSwap', type: 'DEX', color: 'text-yellow-300' },
  { id: 'raydium', name: 'Raydium', type: 'DEX', color: 'text-purple-500' }
]

const TOKENS = ['BTC', 'ETH', 'SOL', 'BNB', 'XRP', 'DOGE', 'AVAX', 'LINK', 'UNI', 'AAVE']

// Generate mock arbitrage opportunities
const generateOpportunities = () => {
  const opportunities = []

  for (let i = 0; i < 15; i++) {
    const token = TOKENS[Math.floor(Math.random() * TOKENS.length)]
    const buyExchange = EXCHANGES[Math.floor(Math.random() * EXCHANGES.length)]
    let sellExchange = EXCHANGES[Math.floor(Math.random() * EXCHANGES.length)]
    while (sellExchange.id === buyExchange.id) {
      sellExchange = EXCHANGES[Math.floor(Math.random() * EXCHANGES.length)]
    }

    const basePrice = token === 'BTC' ? 95420 :
                      token === 'ETH' ? 3280 :
                      token === 'SOL' ? 185 :
                      token === 'BNB' ? 680 :
                      token === 'XRP' ? 2.45 :
                      token === 'DOGE' ? 0.38 :
                      token === 'AVAX' ? 38.50 :
                      token === 'LINK' ? 22.40 :
                      token === 'UNI' ? 13.20 : 285

    const spreadPercent = 0.1 + Math.random() * 1.5
    const buyPrice = basePrice * (1 - spreadPercent / 200)
    const sellPrice = basePrice * (1 + spreadPercent / 200)
    const grossProfit = spreadPercent

    // Fees
    const buyFee = buyExchange.type === 'DEX' ? 0.3 : 0.1
    const sellFee = sellExchange.type === 'DEX' ? 0.3 : 0.1
    const gasCost = buyExchange.type === 'DEX' || sellExchange.type === 'DEX' ? 15 + Math.random() * 30 : 0
    const transferCost = buyExchange.type !== sellExchange.type ? 10 + Math.random() * 20 : 0

    const totalFees = buyFee + sellFee
    const netProfit = grossProfit - totalFees - (gasCost + transferCost) / basePrice * 100

    opportunities.push({
      id: i,
      token,
      buyExchange,
      sellExchange,
      buyPrice,
      sellPrice,
      spreadPercent,
      grossProfit,
      totalFees,
      gasCost,
      transferCost,
      netProfit,
      volume: Math.floor(Math.random() * 1000000) + 100000,
      lastUpdated: new Date(Date.now() - Math.random() * 60000).toLocaleTimeString(),
      status: netProfit > 0.3 ? 'profitable' : netProfit > 0 ? 'marginal' : 'unprofitable'
    })
  }

  return opportunities.sort((a, b) => b.netProfit - a.netProfit)
}

export function ArbitrageFinder() {
  const [mode, setMode] = useState('opportunities') // opportunities, triangular, history
  const [opportunities, setOpportunities] = useState(() => generateOpportunities())
  const [selectedToken, setSelectedToken] = useState('all')
  const [minProfit, setMinProfit] = useState(0)
  const [exchangeType, setExchangeType] = useState('all') // all, cex-cex, cex-dex, dex-dex
  const [isLive, setIsLive] = useState(true)

  // Simulate live updates
  useEffect(() => {
    if (!isLive) return

    const interval = setInterval(() => {
      setOpportunities(generateOpportunities())
    }, 10000)

    return () => clearInterval(interval)
  }, [isLive])

  // Filter opportunities
  const filteredOpps = useMemo(() => {
    return opportunities.filter(opp => {
      if (selectedToken !== 'all' && opp.token !== selectedToken) return false
      if (opp.netProfit < minProfit) return false
      if (exchangeType === 'cex-cex' &&
          (opp.buyExchange.type !== 'CEX' || opp.sellExchange.type !== 'CEX')) return false
      if (exchangeType === 'cex-dex' &&
          !((opp.buyExchange.type === 'CEX' && opp.sellExchange.type === 'DEX') ||
            (opp.buyExchange.type === 'DEX' && opp.sellExchange.type === 'CEX'))) return false
      if (exchangeType === 'dex-dex' &&
          (opp.buyExchange.type !== 'DEX' || opp.sellExchange.type !== 'DEX')) return false
      return true
    })
  }, [opportunities, selectedToken, minProfit, exchangeType])

  // Statistics
  const stats = useMemo(() => {
    const profitable = filteredOpps.filter(o => o.status === 'profitable')
    const avgProfit = filteredOpps.length > 0
      ? filteredOpps.reduce((sum, o) => sum + o.netProfit, 0) / filteredOpps.length
      : 0
    const bestOpp = filteredOpps[0]
    const cexCex = filteredOpps.filter(o => o.buyExchange.type === 'CEX' && o.sellExchange.type === 'CEX')
    const cexDex = filteredOpps.filter(o =>
      (o.buyExchange.type === 'CEX' && o.sellExchange.type === 'DEX') ||
      (o.buyExchange.type === 'DEX' && o.sellExchange.type === 'CEX')
    )

    return {
      total: filteredOpps.length,
      profitable: profitable.length,
      avgProfit,
      bestOpp,
      cexCex: cexCex.length,
      cexDex: cexDex.length
    }
  }, [filteredOpps])

  // Triangular arbitrage mock data
  const [triangularOpps] = useState(() => {
    const opps = []
    const pairs = [
      { path: ['ETH', 'BTC', 'USDT'], profit: 0.45, exchanges: 'Binance' },
      { path: ['SOL', 'ETH', 'USDT'], profit: 0.32, exchanges: 'Binance' },
      { path: ['BNB', 'ETH', 'USDT'], profit: 0.28, exchanges: 'Binance' },
      { path: ['AVAX', 'BTC', 'USDT'], profit: 0.21, exchanges: 'OKX' },
      { path: ['LINK', 'ETH', 'USDT'], profit: 0.18, exchanges: 'Coinbase' }
    ]
    return pairs.map((p, idx) => ({
      id: idx,
      ...p,
      volume: Math.floor(Math.random() * 500000) + 50000
    }))
  })

  const formatPrice = (price) => {
    if (price < 1) return `$${price.toFixed(6)}`
    return `$${price.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
  }

  return (
    <div className="p-6 bg-[#0a0e14] min-h-screen">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-green-500/20 rounded-lg">
            <ArrowLeftRight className="w-6 h-6 text-green-400" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-white">Arbitrage Finder</h1>
            <p className="text-sm text-gray-400">Find cross-exchange price differences</p>
          </div>
        </div>
        <div className="flex gap-2">
          {['opportunities', 'triangular', 'history'].map(m => (
            <button
              key={m}
              onClick={() => setMode(m)}
              className={`px-4 py-2 rounded-lg text-sm font-medium capitalize transition-colors ${
                mode === m ? 'bg-green-500 text-black' : 'bg-white/10 text-white hover:bg-white/20'
              }`}
            >
              {m}
            </button>
          ))}
        </div>
      </div>

      {/* Stats Bar */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mb-6">
        <div className="bg-white/5 rounded-xl p-4 border border-white/10">
          <div className="text-sm text-gray-400">Total Opportunities</div>
          <div className="text-2xl font-bold text-white">{stats.total}</div>
        </div>
        <div className="bg-green-500/10 rounded-xl p-4 border border-green-500/30">
          <div className="text-sm text-gray-400">Profitable</div>
          <div className="text-2xl font-bold text-green-400">{stats.profitable}</div>
        </div>
        <div className="bg-blue-500/10 rounded-xl p-4 border border-blue-500/30">
          <div className="text-sm text-gray-400">Avg Profit</div>
          <div className="text-2xl font-bold text-blue-400">{stats.avgProfit.toFixed(3)}%</div>
        </div>
        <div className="bg-purple-500/10 rounded-xl p-4 border border-purple-500/30">
          <div className="text-sm text-gray-400">CEX-CEX</div>
          <div className="text-2xl font-bold text-purple-400">{stats.cexCex}</div>
        </div>
        <div className="bg-pink-500/10 rounded-xl p-4 border border-pink-500/30">
          <div className="text-sm text-gray-400">CEX-DEX</div>
          <div className="text-2xl font-bold text-pink-400">{stats.cexDex}</div>
        </div>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-4 mb-6 flex-wrap">
        <select
          value={selectedToken}
          onChange={(e) => setSelectedToken(e.target.value)}
          className="bg-white/10 border border-white/20 rounded-lg px-3 py-2 text-white"
        >
          <option value="all">All Tokens</option>
          {TOKENS.map(t => (
            <option key={t} value={t}>{t}</option>
          ))}
        </select>

        <select
          value={exchangeType}
          onChange={(e) => setExchangeType(e.target.value)}
          className="bg-white/10 border border-white/20 rounded-lg px-3 py-2 text-white"
        >
          <option value="all">All Types</option>
          <option value="cex-cex">CEX to CEX</option>
          <option value="cex-dex">CEX to DEX</option>
          <option value="dex-dex">DEX to DEX</option>
        </select>

        <div className="flex items-center gap-2">
          <span className="text-sm text-gray-400">Min Profit:</span>
          <input
            type="number"
            value={minProfit}
            onChange={(e) => setMinProfit(Number(e.target.value))}
            step="0.1"
            className="w-20 bg-white/10 border border-white/20 rounded px-2 py-1 text-white"
          />
          <span className="text-gray-400">%</span>
        </div>

        <button
          onClick={() => setIsLive(!isLive)}
          className={`px-4 py-2 rounded-lg flex items-center gap-2 ${
            isLive ? 'bg-green-500 text-black' : 'bg-white/10 text-white'
          }`}
        >
          <div className={`w-2 h-2 rounded-full ${isLive ? 'bg-black animate-pulse' : 'bg-gray-400'}`} />
          {isLive ? 'Live' : 'Paused'}
        </button>

        <button className="ml-auto p-2 bg-white/10 rounded-lg hover:bg-white/20">
          <RefreshCw className={`w-5 h-5 text-gray-400 ${isLive ? 'animate-spin' : ''}`} />
        </button>
      </div>

      {/* Opportunities Mode */}
      {mode === 'opportunities' && (
        <div className="space-y-4">
          {filteredOpps.length === 0 ? (
            <div className="text-center py-12 text-gray-500">
              <ArrowLeftRight className="w-12 h-12 mx-auto mb-3 opacity-50" />
              <p>No arbitrage opportunities found with current filters</p>
            </div>
          ) : (
            filteredOpps.map(opp => (
              <div
                key={opp.id}
                className={`bg-white/5 rounded-xl border p-6 ${
                  opp.status === 'profitable' ? 'border-green-500/30' :
                  opp.status === 'marginal' ? 'border-yellow-500/30' : 'border-white/10'
                }`}
              >
                <div className="flex items-center justify-between mb-4">
                  <div className="flex items-center gap-4">
                    <div className="text-2xl font-bold text-white">{opp.token}</div>
                    <span className={`px-2 py-0.5 rounded text-xs font-medium ${
                      opp.status === 'profitable' ? 'bg-green-500/20 text-green-400' :
                      opp.status === 'marginal' ? 'bg-yellow-500/20 text-yellow-400' :
                      'bg-red-500/20 text-red-400'
                    }`}>
                      {opp.status.toUpperCase()}
                    </span>
                  </div>
                  <div className="flex items-center gap-2 text-sm text-gray-400">
                    <Clock className="w-4 h-4" />
                    {opp.lastUpdated}
                  </div>
                </div>

                {/* Exchange Flow */}
                <div className="flex items-center justify-center gap-4 mb-6">
                  <div className="text-center">
                    <div className={`text-sm ${opp.buyExchange.color}`}>{opp.buyExchange.name}</div>
                    <div className="text-xs text-gray-500">{opp.buyExchange.type}</div>
                    <div className="text-lg font-semibold text-white mt-1">{formatPrice(opp.buyPrice)}</div>
                    <div className="text-xs text-gray-400">Buy</div>
                  </div>

                  <div className="flex flex-col items-center">
                    <ArrowRight className="w-8 h-8 text-green-400" />
                    <div className="text-sm font-semibold text-green-400">+{opp.spreadPercent.toFixed(3)}%</div>
                  </div>

                  <div className="text-center">
                    <div className={`text-sm ${opp.sellExchange.color}`}>{opp.sellExchange.name}</div>
                    <div className="text-xs text-gray-500">{opp.sellExchange.type}</div>
                    <div className="text-lg font-semibold text-white mt-1">{formatPrice(opp.sellPrice)}</div>
                    <div className="text-xs text-gray-400">Sell</div>
                  </div>
                </div>

                {/* Profit Breakdown */}
                <div className="grid grid-cols-2 md:grid-cols-5 gap-4 p-4 bg-white/5 rounded-lg">
                  <div>
                    <div className="text-xs text-gray-400">Gross Spread</div>
                    <div className="text-white font-semibold">+{opp.grossProfit.toFixed(3)}%</div>
                  </div>
                  <div>
                    <div className="text-xs text-gray-400">Trading Fees</div>
                    <div className="text-red-400 font-semibold">-{opp.totalFees.toFixed(2)}%</div>
                  </div>
                  <div>
                    <div className="text-xs text-gray-400">Gas Cost</div>
                    <div className="text-orange-400 font-semibold">${opp.gasCost.toFixed(2)}</div>
                  </div>
                  <div>
                    <div className="text-xs text-gray-400">Transfer Cost</div>
                    <div className="text-orange-400 font-semibold">${opp.transferCost.toFixed(2)}</div>
                  </div>
                  <div>
                    <div className="text-xs text-gray-400">Net Profit</div>
                    <div className={`font-bold text-lg ${
                      opp.netProfit > 0 ? 'text-green-400' : 'text-red-400'
                    }`}>
                      {opp.netProfit > 0 ? '+' : ''}{opp.netProfit.toFixed(3)}%
                    </div>
                  </div>
                </div>

                {/* Actions */}
                <div className="flex items-center justify-between mt-4">
                  <div className="text-sm text-gray-400">
                    Volume: ${(opp.volume / 1000).toFixed(0)}K
                  </div>
                  <div className="flex gap-2">
                    <button className="px-4 py-2 bg-white/10 text-white rounded-lg text-sm hover:bg-white/20 flex items-center gap-2">
                      <Eye className="w-4 h-4" />
                      Details
                    </button>
                    <button className="px-4 py-2 bg-white/10 text-white rounded-lg text-sm hover:bg-white/20 flex items-center gap-2">
                      <Bell className="w-4 h-4" />
                      Alert
                    </button>
                    {opp.status === 'profitable' && (
                      <button className="px-4 py-2 bg-green-500 text-black rounded-lg text-sm font-semibold hover:bg-green-400 flex items-center gap-2">
                        <Zap className="w-4 h-4" />
                        Execute
                      </button>
                    )}
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
      )}

      {/* Triangular Mode */}
      {mode === 'triangular' && (
        <div className="space-y-6">
          <div className="bg-white/5 rounded-xl border border-white/10 p-6">
            <h3 className="font-semibold text-white mb-4 flex items-center gap-2">
              <Target className="w-5 h-5 text-purple-400" />
              Triangular Arbitrage Opportunities
            </h3>
            <p className="text-sm text-gray-400 mb-6">
              Profit from price inefficiencies across three trading pairs within the same exchange.
            </p>

            <div className="space-y-4">
              {triangularOpps.map(opp => (
                <div key={opp.id} className="flex items-center justify-between p-4 bg-white/5 rounded-lg border border-white/10">
                  <div className="flex items-center gap-6">
                    <div className="flex items-center gap-2">
                      {opp.path.map((token, idx) => (
                        <React.Fragment key={token}>
                          <span className="text-white font-semibold">{token}</span>
                          {idx < opp.path.length - 1 && (
                            <ArrowRight className="w-4 h-4 text-gray-500" />
                          )}
                        </React.Fragment>
                      ))}
                    </div>
                    <span className="text-sm text-gray-400">{opp.exchanges}</span>
                  </div>
                  <div className="flex items-center gap-4">
                    <div className="text-right">
                      <div className="text-sm text-gray-400">Est. Profit</div>
                      <div className="text-green-400 font-bold">+{opp.profit}%</div>
                    </div>
                    <div className="text-right">
                      <div className="text-sm text-gray-400">Volume</div>
                      <div className="text-white">${(opp.volume / 1000).toFixed(0)}K</div>
                    </div>
                    <button className="px-3 py-1.5 bg-purple-500/20 text-purple-400 rounded text-sm hover:bg-purple-500/30">
                      Execute
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Info Box */}
          <div className="bg-purple-500/10 rounded-xl border border-purple-500/30 p-6">
            <h3 className="font-semibold text-white mb-2">How Triangular Arbitrage Works</h3>
            <p className="text-sm text-gray-400 mb-4">
              Trade through three pairs to capture pricing inefficiencies. Example: ETH → BTC → USDT → ETH
            </p>
            <ol className="list-decimal list-inside text-sm text-gray-400 space-y-1">
              <li>Start with USDT, buy ETH</li>
              <li>Trade ETH for BTC</li>
              <li>Sell BTC for USDT</li>
              <li>End up with more USDT than you started</li>
            </ol>
          </div>
        </div>
      )}

      {/* History Mode */}
      {mode === 'history' && (
        <div className="space-y-6">
          <div className="bg-white/5 rounded-xl border border-white/10 overflow-hidden">
            <div className="p-4 border-b border-white/10 flex items-center justify-between">
              <h3 className="font-semibold text-white">Arbitrage History</h3>
              <button className="px-3 py-1.5 bg-white/10 text-gray-300 rounded text-sm hover:bg-white/20 flex items-center gap-2">
                <Download className="w-4 h-4" />
                Export
              </button>
            </div>
            <table className="w-full">
              <thead>
                <tr className="text-left text-xs text-gray-400 border-b border-white/10 bg-white/5">
                  <th className="p-4">Time</th>
                  <th className="p-4">Token</th>
                  <th className="p-4">Route</th>
                  <th className="p-4">Spread</th>
                  <th className="p-4">Net Profit</th>
                  <th className="p-4">Status</th>
                </tr>
              </thead>
              <tbody>
                {[
                  { time: '2 hours ago', token: 'ETH', route: 'Binance → Uniswap', spread: 0.85, profit: 0.42, status: 'executed' },
                  { time: '4 hours ago', token: 'SOL', route: 'OKX → Raydium', spread: 1.2, profit: 0.65, status: 'executed' },
                  { time: '6 hours ago', token: 'BTC', route: 'Coinbase → Binance', spread: 0.32, profit: 0.18, status: 'missed' },
                  { time: '8 hours ago', token: 'AVAX', route: 'Kraken → PancakeSwap', spread: 0.95, profit: 0.38, status: 'executed' },
                  { time: '12 hours ago', token: 'LINK', route: 'Binance → SushiSwap', spread: 0.72, profit: 0.28, status: 'executed' }
                ].map((item, idx) => (
                  <tr key={idx} className="border-b border-white/5 hover:bg-white/5">
                    <td className="p-4 text-gray-400">{item.time}</td>
                    <td className="p-4 text-white font-semibold">{item.token}</td>
                    <td className="p-4 text-gray-300">{item.route}</td>
                    <td className="p-4 text-blue-400">+{item.spread}%</td>
                    <td className="p-4 text-green-400 font-semibold">+{item.profit}%</td>
                    <td className="p-4">
                      <span className={`px-2 py-0.5 rounded text-xs ${
                        item.status === 'executed' ? 'bg-green-500/20 text-green-400' :
                        'bg-red-500/20 text-red-400'
                      }`}>
                        {item.status}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Summary Stats */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="bg-green-500/10 rounded-xl p-4 border border-green-500/30">
              <div className="text-sm text-gray-400">Total Executed</div>
              <div className="text-2xl font-bold text-green-400">24</div>
            </div>
            <div className="bg-blue-500/10 rounded-xl p-4 border border-blue-500/30">
              <div className="text-sm text-gray-400">Avg Profit</div>
              <div className="text-2xl font-bold text-blue-400">0.38%</div>
            </div>
            <div className="bg-purple-500/10 rounded-xl p-4 border border-purple-500/30">
              <div className="text-sm text-gray-400">Total Profit</div>
              <div className="text-2xl font-bold text-purple-400">$1,284</div>
            </div>
            <div className="bg-yellow-500/10 rounded-xl p-4 border border-yellow-500/30">
              <div className="text-sm text-gray-400">Success Rate</div>
              <div className="text-2xl font-bold text-yellow-400">87%</div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default ArbitrageFinder
