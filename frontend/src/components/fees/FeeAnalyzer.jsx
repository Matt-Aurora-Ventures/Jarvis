import React, { useState, useMemo } from 'react'
import {
  Receipt, Calculator, TrendingUp, TrendingDown, DollarSign,
  Percent, BarChart3, ArrowRight, Clock, Zap, Building2,
  ArrowUpDown, Filter, Download, RefreshCw, ChevronDown,
  AlertTriangle, CheckCircle, Info, Layers, Wallet
} from 'lucide-react'

const EXCHANGES = [
  { id: 'binance', name: 'Binance', maker: 0.1, taker: 0.1, withdrawal: { BTC: 0.0005, ETH: 0.005, USDT: 1 }, tiers: true },
  { id: 'coinbase', name: 'Coinbase Pro', maker: 0.4, taker: 0.6, withdrawal: { BTC: 0.0001, ETH: 0.001, USDT: 0 }, tiers: true },
  { id: 'kraken', name: 'Kraken', maker: 0.16, taker: 0.26, withdrawal: { BTC: 0.0002, ETH: 0.0025, USDT: 2.5 }, tiers: true },
  { id: 'kucoin', name: 'KuCoin', maker: 0.1, taker: 0.1, withdrawal: { BTC: 0.0004, ETH: 0.004, USDT: 1 }, tiers: true },
  { id: 'bybit', name: 'Bybit', maker: 0.1, taker: 0.1, withdrawal: { BTC: 0.0002, ETH: 0.003, USDT: 1 }, tiers: true },
  { id: 'okx', name: 'OKX', maker: 0.08, taker: 0.1, withdrawal: { BTC: 0.0002, ETH: 0.002, USDT: 1 }, tiers: true },
  { id: 'gate', name: 'Gate.io', maker: 0.2, taker: 0.2, withdrawal: { BTC: 0.001, ETH: 0.01, USDT: 2 }, tiers: false },
  { id: 'mexc', name: 'MEXC', maker: 0.0, taker: 0.1, withdrawal: { BTC: 0.0003, ETH: 0.003, USDT: 1 }, tiers: false },
  { id: 'htx', name: 'HTX', maker: 0.2, taker: 0.2, withdrawal: { BTC: 0.0005, ETH: 0.005, USDT: 1 }, tiers: true },
  { id: 'bitget', name: 'Bitget', maker: 0.1, taker: 0.1, withdrawal: { BTC: 0.0004, ETH: 0.004, USDT: 1 }, tiers: true }
]

const FEE_TIERS = {
  binance: [
    { level: 'VIP 0', volume: 0, maker: 0.1, taker: 0.1 },
    { level: 'VIP 1', volume: 1000000, maker: 0.09, taker: 0.1 },
    { level: 'VIP 2', volume: 5000000, maker: 0.08, taker: 0.1 },
    { level: 'VIP 3', volume: 20000000, maker: 0.07, taker: 0.09 },
    { level: 'VIP 4', volume: 100000000, maker: 0.05, taker: 0.07 },
    { level: 'VIP 5', volume: 150000000, maker: 0.04, taker: 0.06 }
  ],
  coinbase: [
    { level: 'Tier 1', volume: 0, maker: 0.4, taker: 0.6 },
    { level: 'Tier 2', volume: 10000, maker: 0.25, taker: 0.4 },
    { level: 'Tier 3', volume: 50000, maker: 0.15, taker: 0.25 },
    { level: 'Tier 4', volume: 100000, maker: 0.1, taker: 0.2 },
    { level: 'Tier 5', volume: 1000000, maker: 0.08, taker: 0.15 }
  ],
  kraken: [
    { level: 'Starter', volume: 0, maker: 0.16, taker: 0.26 },
    { level: 'Intermediate', volume: 50000, maker: 0.14, taker: 0.24 },
    { level: 'Pro', volume: 100000, maker: 0.12, taker: 0.22 },
    { level: 'Expert', volume: 250000, maker: 0.1, taker: 0.2 }
  ]
}

const DEX_FEES = [
  { id: 'uniswap', name: 'Uniswap V3', fee: 0.3, pools: '0.05/0.3/1%', chain: 'Ethereum' },
  { id: 'sushiswap', name: 'SushiSwap', fee: 0.3, pools: '0.3%', chain: 'Multi' },
  { id: 'pancake', name: 'PancakeSwap', fee: 0.25, pools: '0.01/0.05/0.25/1%', chain: 'BSC' },
  { id: 'curve', name: 'Curve', fee: 0.04, pools: '0.04%', chain: 'Ethereum' },
  { id: 'balancer', name: 'Balancer', fee: 0.3, pools: 'Dynamic', chain: 'Ethereum' },
  { id: 'raydium', name: 'Raydium', fee: 0.25, pools: '0.25%', chain: 'Solana' },
  { id: 'orca', name: 'Orca', fee: 0.3, pools: '0.01/0.05/0.3/1%', chain: 'Solana' },
  { id: 'jupiter', name: 'Jupiter', fee: 0.0, pools: 'Aggregator', chain: 'Solana' }
]

const GAS_ESTIMATES = {
  ethereum: { swap: 150000, transfer: 21000, approve: 45000, gasPrice: 25 },
  bsc: { swap: 200000, transfer: 21000, approve: 45000, gasPrice: 3 },
  polygon: { swap: 200000, transfer: 21000, approve: 45000, gasPrice: 50 },
  arbitrum: { swap: 500000, transfer: 21000, approve: 45000, gasPrice: 0.1 },
  optimism: { swap: 500000, transfer: 21000, approve: 45000, gasPrice: 0.001 },
  solana: { swap: 5000, transfer: 5000, approve: 0, gasPrice: 0.000005 }
}

export function FeeAnalyzer() {
  const [mode, setMode] = useState('compare') // compare, calculator, optimizer
  const [tradeSize, setTradeSize] = useState(10000)
  const [selectedExchanges, setSelectedExchanges] = useState(['binance', 'coinbase', 'kraken'])
  const [orderType, setOrderType] = useState('taker') // maker, taker, mixed
  const [monthlyVolume, setMonthlyVolume] = useState(50000)
  const [includeWithdrawal, setIncludeWithdrawal] = useState(true)
  const [withdrawalAsset, setWithdrawalAsset] = useState('USDT')
  const [chain, setChain] = useState('ethereum')
  const [tradesPerMonth, setTradesPerMonth] = useState(20)

  // Compare exchange fees
  const exchangeComparison = useMemo(() => {
    return EXCHANGES.map(exchange => {
      const feeRate = orderType === 'maker' ? exchange.maker :
                      orderType === 'taker' ? exchange.taker :
                      (exchange.maker + exchange.taker) / 2

      const tradingFee = (tradeSize * feeRate) / 100
      const withdrawalFee = includeWithdrawal ? (exchange.withdrawal[withdrawalAsset] || 0) *
                            (withdrawalAsset === 'USDT' ? 1 : withdrawalAsset === 'ETH' ? 3200 : 95000) : 0
      const totalFee = tradingFee + withdrawalFee

      // Check if better tier available
      let effectiveFee = feeRate
      if (exchange.tiers && FEE_TIERS[exchange.id]) {
        const tiers = FEE_TIERS[exchange.id]
        for (let i = tiers.length - 1; i >= 0; i--) {
          if (monthlyVolume >= tiers[i].volume) {
            effectiveFee = orderType === 'maker' ? tiers[i].maker : tiers[i].taker
            break
          }
        }
      }

      const effectiveTradingFee = (tradeSize * effectiveFee) / 100

      return {
        ...exchange,
        feeRate,
        tradingFee,
        withdrawalFee,
        totalFee,
        effectiveFee,
        effectiveTradingFee,
        savings: tradingFee - effectiveTradingFee
      }
    }).sort((a, b) => a.totalFee - b.totalFee)
  }, [tradeSize, orderType, monthlyVolume, includeWithdrawal, withdrawalAsset])

  // Monthly cost projection
  const monthlyCosts = useMemo(() => {
    return exchangeComparison.slice(0, 5).map(exchange => {
      const tradingCosts = exchange.effectiveTradingFee * tradesPerMonth
      const withdrawalCosts = includeWithdrawal ? exchange.withdrawalFee * 4 : 0 // 4 withdrawals/month
      const totalMonthly = tradingCosts + withdrawalCosts
      const annualCost = totalMonthly * 12

      return {
        exchange: exchange.name,
        tradingCosts,
        withdrawalCosts,
        totalMonthly,
        annualCost
      }
    })
  }, [exchangeComparison, tradesPerMonth, includeWithdrawal])

  // DEX vs CEX comparison
  const dexComparison = useMemo(() => {
    const gasEstimate = GAS_ESTIMATES[chain]
    const nativePrice = chain === 'ethereum' ? 3200 :
                        chain === 'bsc' ? 600 :
                        chain === 'polygon' ? 0.5 :
                        chain === 'solana' ? 200 : 1

    return DEX_FEES.map(dex => {
      const swapFee = (tradeSize * dex.fee) / 100
      const gasCost = (gasEstimate.swap * gasEstimate.gasPrice * nativePrice) / 1e9
      const totalCost = swapFee + gasCost

      return {
        ...dex,
        swapFee,
        gasCost,
        totalCost
      }
    }).sort((a, b) => a.totalCost - b.totalCost)
  }, [tradeSize, chain])

  // Optimization recommendations
  const recommendations = useMemo(() => {
    const recs = []

    const cheapestCEX = exchangeComparison[0]
    const cheapestDEX = dexComparison[0]

    if (cheapestCEX.totalFee < cheapestDEX.totalCost) {
      recs.push({
        type: 'cex',
        message: `${cheapestCEX.name} is cheapest at $${cheapestCEX.totalFee.toFixed(2)} total`,
        savings: cheapestDEX.totalCost - cheapestCEX.totalFee
      })
    } else {
      recs.push({
        type: 'dex',
        message: `${cheapestDEX.name} is cheapest at $${cheapestDEX.totalCost.toFixed(2)} total`,
        savings: cheapestCEX.totalFee - cheapestDEX.totalCost
      })
    }

    // Maker vs taker recommendation
    const makerSavings = exchangeComparison.map(e => e.tradingFee - (tradeSize * e.maker) / 100)
    const avgMakerSavings = makerSavings.reduce((a, b) => a + b, 0) / makerSavings.length
    if (avgMakerSavings > 5 && orderType === 'taker') {
      recs.push({
        type: 'tip',
        message: `Use limit orders (maker) to save ~$${avgMakerSavings.toFixed(2)} per trade`,
        savings: avgMakerSavings
      })
    }

    // Volume tier recommendation
    const tierUpgrades = EXCHANGES.filter(e => FEE_TIERS[e.id]).map(e => {
      const tiers = FEE_TIERS[e.id]
      const currentTier = tiers.find((t, i) => {
        const nextTier = tiers[i + 1]
        return !nextTier || monthlyVolume < nextTier.volume
      })
      const nextTier = tiers[tiers.indexOf(currentTier) + 1]

      if (nextTier) {
        const volumeNeeded = nextTier.volume - monthlyVolume
        const feeSavings = (currentTier.taker - nextTier.taker) * tradeSize * tradesPerMonth / 100
        return { exchange: e.name, volumeNeeded, feeSavings, nextLevel: nextTier.level }
      }
      return null
    }).filter(Boolean).sort((a, b) => a.volumeNeeded - b.volumeNeeded)

    if (tierUpgrades.length > 0 && tierUpgrades[0].volumeNeeded < monthlyVolume * 2) {
      const upgrade = tierUpgrades[0]
      recs.push({
        type: 'tier',
        message: `Reach ${upgrade.nextLevel} on ${upgrade.exchange} with $${upgrade.volumeNeeded.toLocaleString()} more volume`,
        savings: upgrade.feeSavings
      })
    }

    // Low gas time recommendation
    if (chain === 'ethereum' && tradeSize > 1000) {
      recs.push({
        type: 'timing',
        message: 'Trade during low gas periods (weekends, off-peak) for 30-50% gas savings',
        savings: (GAS_ESTIMATES.ethereum.swap * 10 * 3200) / 1e9
      })
    }

    return recs
  }, [exchangeComparison, dexComparison, orderType, tradeSize, monthlyVolume, chain, tradesPerMonth])

  // Trade history simulation
  const [tradeHistory] = useState(() => {
    const history = []
    const exchanges = ['Binance', 'KuCoin', 'Uniswap']
    for (let i = 0; i < 10; i++) {
      const size = Math.floor(Math.random() * 10000) + 1000
      const exchange = exchanges[Math.floor(Math.random() * exchanges.length)]
      const isDeX = exchange === 'Uniswap'
      const fee = isDeX ? size * 0.003 + 15 : size * 0.001
      history.push({
        id: i + 1,
        date: new Date(Date.now() - i * 86400000).toLocaleDateString(),
        exchange,
        size,
        fee,
        type: isDeX ? 'DEX' : 'CEX'
      })
    }
    return history
  })

  const totalHistoricalFees = tradeHistory.reduce((sum, t) => sum + t.fee, 0)

  return (
    <div className="p-6 bg-[#0a0e14] min-h-screen">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-yellow-500/20 rounded-lg">
            <Receipt className="w-6 h-6 text-yellow-400" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-white">Fee Analyzer</h1>
            <p className="text-sm text-gray-400">Compare and optimize trading fees</p>
          </div>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => setMode('compare')}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
              mode === 'compare' ? 'bg-yellow-500 text-black' : 'bg-white/10 text-white hover:bg-white/20'
            }`}
          >
            Compare
          </button>
          <button
            onClick={() => setMode('calculator')}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
              mode === 'calculator' ? 'bg-yellow-500 text-black' : 'bg-white/10 text-white hover:bg-white/20'
            }`}
          >
            Calculator
          </button>
          <button
            onClick={() => setMode('optimizer')}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
              mode === 'optimizer' ? 'bg-yellow-500 text-black' : 'bg-white/10 text-white hover:bg-white/20'
            }`}
          >
            Optimizer
          </button>
        </div>
      </div>

      {/* Input Controls */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <div className="bg-white/5 rounded-lg p-4 border border-white/10">
          <label className="text-xs text-gray-400 block mb-2">Trade Size ($)</label>
          <input
            type="number"
            value={tradeSize}
            onChange={(e) => setTradeSize(Number(e.target.value))}
            className="w-full bg-white/10 border border-white/20 rounded px-3 py-2 text-white"
          />
        </div>
        <div className="bg-white/5 rounded-lg p-4 border border-white/10">
          <label className="text-xs text-gray-400 block mb-2">Order Type</label>
          <select
            value={orderType}
            onChange={(e) => setOrderType(e.target.value)}
            className="w-full bg-white/10 border border-white/20 rounded px-3 py-2 text-white"
          >
            <option value="maker">Maker (Limit)</option>
            <option value="taker">Taker (Market)</option>
            <option value="mixed">Mixed</option>
          </select>
        </div>
        <div className="bg-white/5 rounded-lg p-4 border border-white/10">
          <label className="text-xs text-gray-400 block mb-2">Monthly Volume ($)</label>
          <input
            type="number"
            value={monthlyVolume}
            onChange={(e) => setMonthlyVolume(Number(e.target.value))}
            className="w-full bg-white/10 border border-white/20 rounded px-3 py-2 text-white"
          />
        </div>
        <div className="bg-white/5 rounded-lg p-4 border border-white/10">
          <label className="text-xs text-gray-400 block mb-2">Trades/Month</label>
          <input
            type="number"
            value={tradesPerMonth}
            onChange={(e) => setTradesPerMonth(Number(e.target.value))}
            className="w-full bg-white/10 border border-white/20 rounded px-3 py-2 text-white"
          />
        </div>
      </div>

      {/* Compare Mode */}
      {mode === 'compare' && (
        <div className="space-y-6">
          {/* CEX Comparison */}
          <div className="bg-white/5 rounded-xl border border-white/10 overflow-hidden">
            <div className="p-4 border-b border-white/10 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Building2 className="w-5 h-5 text-blue-400" />
                <h2 className="font-semibold text-white">CEX Fee Comparison</h2>
              </div>
              <div className="flex items-center gap-2">
                <label className="flex items-center gap-2 text-sm text-gray-400">
                  <input
                    type="checkbox"
                    checked={includeWithdrawal}
                    onChange={(e) => setIncludeWithdrawal(e.target.checked)}
                    className="rounded bg-white/10"
                  />
                  Include Withdrawal
                </label>
                {includeWithdrawal && (
                  <select
                    value={withdrawalAsset}
                    onChange={(e) => setWithdrawalAsset(e.target.value)}
                    className="bg-white/10 border border-white/20 rounded px-2 py-1 text-white text-sm"
                  >
                    <option value="USDT">USDT</option>
                    <option value="ETH">ETH</option>
                    <option value="BTC">BTC</option>
                  </select>
                )}
              </div>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="text-left text-xs text-gray-400 border-b border-white/10">
                    <th className="p-3">Rank</th>
                    <th className="p-3">Exchange</th>
                    <th className="p-3">Base Fee</th>
                    <th className="p-3">Trading Fee</th>
                    <th className="p-3">Withdrawal</th>
                    <th className="p-3">Total Cost</th>
                    <th className="p-3">Your Tier Fee</th>
                    <th className="p-3">Potential Savings</th>
                  </tr>
                </thead>
                <tbody>
                  {exchangeComparison.map((exchange, idx) => (
                    <tr key={exchange.id} className="border-b border-white/5 hover:bg-white/5">
                      <td className="p-3">
                        <span className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold ${
                          idx === 0 ? 'bg-yellow-500 text-black' :
                          idx === 1 ? 'bg-gray-400 text-black' :
                          idx === 2 ? 'bg-orange-600 text-white' :
                          'bg-white/10 text-gray-400'
                        }`}>
                          {idx + 1}
                        </span>
                      </td>
                      <td className="p-3">
                        <span className="text-white font-medium">{exchange.name}</span>
                        {exchange.tiers && (
                          <span className="ml-2 text-xs bg-blue-500/20 text-blue-400 px-1.5 py-0.5 rounded">VIP</span>
                        )}
                      </td>
                      <td className="p-3 text-gray-300">{exchange.feeRate.toFixed(2)}%</td>
                      <td className="p-3 text-white">${exchange.tradingFee.toFixed(2)}</td>
                      <td className="p-3 text-gray-300">
                        {includeWithdrawal ? `$${exchange.withdrawalFee.toFixed(2)}` : '-'}
                      </td>
                      <td className="p-3">
                        <span className={`font-semibold ${idx === 0 ? 'text-green-400' : 'text-white'}`}>
                          ${exchange.totalFee.toFixed(2)}
                        </span>
                      </td>
                      <td className="p-3">
                        {exchange.savings > 0 ? (
                          <span className="text-yellow-400">${exchange.effectiveTradingFee.toFixed(2)}</span>
                        ) : (
                          <span className="text-gray-400">${exchange.tradingFee.toFixed(2)}</span>
                        )}
                      </td>
                      <td className="p-3">
                        {exchange.savings > 0 ? (
                          <span className="text-green-400">-${exchange.savings.toFixed(2)}</span>
                        ) : (
                          <span className="text-gray-500">-</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* DEX Comparison */}
          <div className="bg-white/5 rounded-xl border border-white/10 overflow-hidden">
            <div className="p-4 border-b border-white/10 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Layers className="w-5 h-5 text-purple-400" />
                <h2 className="font-semibold text-white">DEX Fee Comparison</h2>
              </div>
              <select
                value={chain}
                onChange={(e) => setChain(e.target.value)}
                className="bg-white/10 border border-white/20 rounded px-3 py-1.5 text-white text-sm"
              >
                <option value="ethereum">Ethereum</option>
                <option value="bsc">BSC</option>
                <option value="polygon">Polygon</option>
                <option value="arbitrum">Arbitrum</option>
                <option value="optimism">Optimism</option>
                <option value="solana">Solana</option>
              </select>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="text-left text-xs text-gray-400 border-b border-white/10">
                    <th className="p-3">Rank</th>
                    <th className="p-3">DEX</th>
                    <th className="p-3">Chain</th>
                    <th className="p-3">Pool Fees</th>
                    <th className="p-3">Swap Fee</th>
                    <th className="p-3">Gas Cost</th>
                    <th className="p-3">Total Cost</th>
                  </tr>
                </thead>
                <tbody>
                  {dexComparison.map((dex, idx) => (
                    <tr key={dex.id} className="border-b border-white/5 hover:bg-white/5">
                      <td className="p-3">
                        <span className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold ${
                          idx === 0 ? 'bg-purple-500 text-white' :
                          idx === 1 ? 'bg-gray-400 text-black' :
                          'bg-white/10 text-gray-400'
                        }`}>
                          {idx + 1}
                        </span>
                      </td>
                      <td className="p-3 text-white font-medium">{dex.name}</td>
                      <td className="p-3 text-gray-300">{dex.chain}</td>
                      <td className="p-3 text-gray-300">{dex.pools}</td>
                      <td className="p-3 text-white">${dex.swapFee.toFixed(2)}</td>
                      <td className="p-3 text-orange-400">${dex.gasCost.toFixed(2)}</td>
                      <td className="p-3">
                        <span className={`font-semibold ${idx === 0 ? 'text-green-400' : 'text-white'}`}>
                          ${dex.totalCost.toFixed(2)}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* CEX vs DEX Summary */}
          <div className="grid grid-cols-2 gap-4">
            <div className="bg-blue-500/10 rounded-xl p-4 border border-blue-500/30">
              <div className="flex items-center gap-2 mb-3">
                <Building2 className="w-5 h-5 text-blue-400" />
                <span className="font-semibold text-white">Best CEX</span>
              </div>
              <div className="text-2xl font-bold text-blue-400 mb-1">
                {exchangeComparison[0]?.name}
              </div>
              <div className="text-gray-400">
                ${exchangeComparison[0]?.totalFee.toFixed(2)} total fee
              </div>
            </div>
            <div className="bg-purple-500/10 rounded-xl p-4 border border-purple-500/30">
              <div className="flex items-center gap-2 mb-3">
                <Layers className="w-5 h-5 text-purple-400" />
                <span className="font-semibold text-white">Best DEX</span>
              </div>
              <div className="text-2xl font-bold text-purple-400 mb-1">
                {dexComparison[0]?.name}
              </div>
              <div className="text-gray-400">
                ${dexComparison[0]?.totalCost.toFixed(2)} total cost
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Calculator Mode */}
      {mode === 'calculator' && (
        <div className="space-y-6">
          {/* Monthly Cost Projection */}
          <div className="bg-white/5 rounded-xl border border-white/10 p-6">
            <div className="flex items-center gap-2 mb-4">
              <Calculator className="w-5 h-5 text-green-400" />
              <h2 className="font-semibold text-white">Monthly Cost Projection</h2>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
              <div className="bg-white/5 rounded-lg p-4">
                <div className="text-sm text-gray-400 mb-1">Monthly Trades</div>
                <div className="text-2xl font-bold text-white">{tradesPerMonth}</div>
              </div>
              <div className="bg-white/5 rounded-lg p-4">
                <div className="text-sm text-gray-400 mb-1">Avg Trade Size</div>
                <div className="text-2xl font-bold text-white">${tradeSize.toLocaleString()}</div>
              </div>
              <div className="bg-white/5 rounded-lg p-4">
                <div className="text-sm text-gray-400 mb-1">Monthly Volume</div>
                <div className="text-2xl font-bold text-white">${(tradeSize * tradesPerMonth).toLocaleString()}</div>
              </div>
            </div>

            <div className="space-y-3">
              {monthlyCosts.map((cost, idx) => (
                <div key={cost.exchange} className="flex items-center justify-between p-3 bg-white/5 rounded-lg">
                  <div className="flex items-center gap-3">
                    <span className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold ${
                      idx === 0 ? 'bg-green-500 text-black' : 'bg-white/10 text-gray-400'
                    }`}>
                      {idx + 1}
                    </span>
                    <span className="text-white font-medium">{cost.exchange}</span>
                  </div>
                  <div className="flex items-center gap-6 text-sm">
                    <div className="text-right">
                      <div className="text-gray-400">Trading</div>
                      <div className="text-white">${cost.tradingCosts.toFixed(2)}</div>
                    </div>
                    <div className="text-right">
                      <div className="text-gray-400">Withdrawals</div>
                      <div className="text-white">${cost.withdrawalCosts.toFixed(2)}</div>
                    </div>
                    <div className="text-right">
                      <div className="text-gray-400">Monthly</div>
                      <div className="text-yellow-400 font-semibold">${cost.totalMonthly.toFixed(2)}</div>
                    </div>
                    <div className="text-right">
                      <div className="text-gray-400">Annual</div>
                      <div className="text-green-400 font-semibold">${cost.annualCost.toFixed(2)}</div>
                    </div>
                  </div>
                </div>
              ))}
            </div>

            {monthlyCosts.length >= 2 && (
              <div className="mt-4 p-4 bg-green-500/10 rounded-lg border border-green-500/30">
                <div className="flex items-center gap-2 text-green-400">
                  <CheckCircle className="w-5 h-5" />
                  <span className="font-medium">
                    Switching to {monthlyCosts[0].exchange} saves ${(monthlyCosts[1].annualCost - monthlyCosts[0].annualCost).toFixed(2)}/year
                  </span>
                </div>
              </div>
            )}
          </div>

          {/* Fee Tiers */}
          <div className="bg-white/5 rounded-xl border border-white/10 p-6">
            <div className="flex items-center gap-2 mb-4">
              <TrendingUp className="w-5 h-5 text-blue-400" />
              <h2 className="font-semibold text-white">Volume-Based Fee Tiers</h2>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {Object.entries(FEE_TIERS).slice(0, 3).map(([exchange, tiers]) => (
                <div key={exchange} className="bg-white/5 rounded-lg p-4">
                  <h3 className="font-medium text-white mb-3 capitalize">{exchange}</h3>
                  <div className="space-y-2">
                    {tiers.map((tier, idx) => {
                      const isCurrentTier = monthlyVolume >= tier.volume &&
                        (idx === tiers.length - 1 || monthlyVolume < tiers[idx + 1].volume)
                      return (
                        <div
                          key={tier.level}
                          className={`flex justify-between p-2 rounded ${
                            isCurrentTier ? 'bg-blue-500/20 border border-blue-500/30' : ''
                          }`}
                        >
                          <span className={isCurrentTier ? 'text-blue-400 font-medium' : 'text-gray-400'}>
                            {tier.level}
                          </span>
                          <span className="text-white">
                            {tier.maker}/{tier.taker}%
                          </span>
                        </div>
                      )
                    })}
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Trade History */}
          <div className="bg-white/5 rounded-xl border border-white/10 p-6">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <Clock className="w-5 h-5 text-gray-400" />
                <h2 className="font-semibold text-white">Recent Fee History</h2>
              </div>
              <div className="text-sm text-gray-400">
                Total Fees: <span className="text-yellow-400 font-semibold">${totalHistoricalFees.toFixed(2)}</span>
              </div>
            </div>
            <div className="space-y-2">
              {tradeHistory.slice(0, 5).map(trade => (
                <div key={trade.id} className="flex items-center justify-between p-3 bg-white/5 rounded-lg">
                  <div className="flex items-center gap-3">
                    <span className={`px-2 py-0.5 rounded text-xs ${
                      trade.type === 'DEX' ? 'bg-purple-500/20 text-purple-400' : 'bg-blue-500/20 text-blue-400'
                    }`}>
                      {trade.type}
                    </span>
                    <span className="text-white">{trade.exchange}</span>
                    <span className="text-gray-400">{trade.date}</span>
                  </div>
                  <div className="flex items-center gap-4">
                    <span className="text-gray-300">${trade.size.toLocaleString()}</span>
                    <span className="text-yellow-400">${trade.fee.toFixed(2)} fee</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Optimizer Mode */}
      {mode === 'optimizer' && (
        <div className="space-y-6">
          {/* Recommendations */}
          <div className="bg-white/5 rounded-xl border border-white/10 p-6">
            <div className="flex items-center gap-2 mb-4">
              <Zap className="w-5 h-5 text-yellow-400" />
              <h2 className="font-semibold text-white">Fee Optimization Recommendations</h2>
            </div>
            <div className="space-y-3">
              {recommendations.map((rec, idx) => (
                <div
                  key={idx}
                  className={`p-4 rounded-lg border ${
                    rec.type === 'cex' ? 'bg-blue-500/10 border-blue-500/30' :
                    rec.type === 'dex' ? 'bg-purple-500/10 border-purple-500/30' :
                    rec.type === 'tip' ? 'bg-green-500/10 border-green-500/30' :
                    rec.type === 'tier' ? 'bg-yellow-500/10 border-yellow-500/30' :
                    'bg-orange-500/10 border-orange-500/30'
                  }`}
                >
                  <div className="flex items-start justify-between">
                    <div className="flex items-start gap-3">
                      {rec.type === 'cex' && <Building2 className="w-5 h-5 text-blue-400 mt-0.5" />}
                      {rec.type === 'dex' && <Layers className="w-5 h-5 text-purple-400 mt-0.5" />}
                      {rec.type === 'tip' && <Info className="w-5 h-5 text-green-400 mt-0.5" />}
                      {rec.type === 'tier' && <TrendingUp className="w-5 h-5 text-yellow-400 mt-0.5" />}
                      {rec.type === 'timing' && <Clock className="w-5 h-5 text-orange-400 mt-0.5" />}
                      <span className="text-white">{rec.message}</span>
                    </div>
                    <span className="text-green-400 font-semibold whitespace-nowrap ml-4">
                      Save ${rec.savings.toFixed(2)}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Savings Calculator */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="bg-gradient-to-br from-green-500/20 to-green-600/10 rounded-xl p-6 border border-green-500/30">
              <div className="flex items-center gap-2 mb-2">
                <DollarSign className="w-5 h-5 text-green-400" />
                <span className="text-green-400 text-sm">Potential Monthly Savings</span>
              </div>
              <div className="text-3xl font-bold text-white">
                ${recommendations.reduce((sum, r) => sum + r.savings, 0).toFixed(2)}
              </div>
              <div className="text-sm text-green-400 mt-1">
                By implementing all recommendations
              </div>
            </div>
            <div className="bg-gradient-to-br from-blue-500/20 to-blue-600/10 rounded-xl p-6 border border-blue-500/30">
              <div className="flex items-center gap-2 mb-2">
                <Percent className="w-5 h-5 text-blue-400" />
                <span className="text-blue-400 text-sm">Fee Reduction</span>
              </div>
              <div className="text-3xl font-bold text-white">
                {exchangeComparison[0] && monthlyCosts[0] ?
                  ((1 - monthlyCosts[0].totalMonthly / monthlyCosts[monthlyCosts.length - 1]?.totalMonthly) * 100).toFixed(0) :
                  '0'
                }%
              </div>
              <div className="text-sm text-blue-400 mt-1">
                vs highest fee exchange
              </div>
            </div>
            <div className="bg-gradient-to-br from-purple-500/20 to-purple-600/10 rounded-xl p-6 border border-purple-500/30">
              <div className="flex items-center gap-2 mb-2">
                <BarChart3 className="w-5 h-5 text-purple-400" />
                <span className="text-purple-400 text-sm">Annual Impact</span>
              </div>
              <div className="text-3xl font-bold text-white">
                ${(recommendations.reduce((sum, r) => sum + r.savings, 0) * 12).toFixed(0)}
              </div>
              <div className="text-sm text-purple-400 mt-1">
                Yearly fee savings
              </div>
            </div>
          </div>

          {/* Action Items */}
          <div className="bg-white/5 rounded-xl border border-white/10 p-6">
            <div className="flex items-center gap-2 mb-4">
              <CheckCircle className="w-5 h-5 text-green-400" />
              <h2 className="font-semibold text-white">Action Items</h2>
            </div>
            <div className="space-y-2">
              <div className="flex items-center gap-3 p-3 bg-white/5 rounded-lg">
                <input type="checkbox" className="rounded bg-white/10" />
                <span className="text-white">Switch primary trading to {exchangeComparison[0]?.name}</span>
              </div>
              <div className="flex items-center gap-3 p-3 bg-white/5 rounded-lg">
                <input type="checkbox" className="rounded bg-white/10" />
                <span className="text-white">Use limit orders instead of market orders when possible</span>
              </div>
              <div className="flex items-center gap-3 p-3 bg-white/5 rounded-lg">
                <input type="checkbox" className="rounded bg-white/10" />
                <span className="text-white">Consolidate withdrawals to reduce withdrawal fees</span>
              </div>
              <div className="flex items-center gap-3 p-3 bg-white/5 rounded-lg">
                <input type="checkbox" className="rounded bg-white/10" />
                <span className="text-white">Time DEX trades during low gas periods</span>
              </div>
              <div className="flex items-center gap-3 p-3 bg-white/5 rounded-lg">
                <input type="checkbox" className="rounded bg-white/10" />
                <span className="text-white">Reach next volume tier for fee discounts</span>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default FeeAnalyzer
