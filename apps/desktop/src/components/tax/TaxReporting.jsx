import React, { useState, useMemo, useEffect, useCallback } from 'react'
import {
  FileText, Calculator, Download, Calendar, DollarSign, TrendingUp,
  TrendingDown, AlertTriangle, Check, X, Filter, Search, Upload,
  Wallet, ArrowUpRight, ArrowDownRight, RefreshCw, ChevronDown,
  ChevronUp, Settings, FileSpreadsheet, Clock, BarChart3, PieChart,
  Info, HelpCircle, Building, Globe, Coins
} from 'lucide-react'

// Transaction types for tax purposes
const TX_TYPES = {
  BUY: { label: 'Buy', icon: ArrowUpRight, color: 'text-green-400', taxable: false },
  SELL: { label: 'Sell', icon: ArrowDownRight, color: 'text-red-400', taxable: true },
  SWAP: { label: 'Swap', icon: RefreshCw, color: 'text-blue-400', taxable: true },
  TRANSFER: { label: 'Transfer', icon: Wallet, color: 'text-white/60', taxable: false },
  STAKING_REWARD: { label: 'Staking Reward', icon: Coins, color: 'text-yellow-400', taxable: true },
  AIRDROP: { label: 'Airdrop', icon: Download, color: 'text-purple-400', taxable: true },
  MINING: { label: 'Mining', icon: Building, color: 'text-orange-400', taxable: true },
  NFT_SALE: { label: 'NFT Sale', icon: PieChart, color: 'text-pink-400', taxable: true },
  INCOME: { label: 'Income', icon: DollarSign, color: 'text-green-400', taxable: true },
  GIFT: { label: 'Gift', icon: HelpCircle, color: 'text-cyan-400', taxable: false }
}

// Tax methods
const TAX_METHODS = {
  FIFO: { name: 'FIFO', description: 'First In, First Out' },
  LIFO: { name: 'LIFO', description: 'Last In, First Out' },
  HIFO: { name: 'HIFO', description: 'Highest Cost First' },
  ACB: { name: 'ACB', description: 'Average Cost Basis' },
  SPEC_ID: { name: 'Specific ID', description: 'Choose specific lots' }
}

// Jurisdictions
const JURISDICTIONS = {
  US: { name: 'United States', shortTerm: 365, shortTermRate: 37, longTermRate: 20 },
  UK: { name: 'United Kingdom', shortTerm: 0, shortTermRate: 20, longTermRate: 20 },
  DE: { name: 'Germany', shortTerm: 365, shortTermRate: 0, longTermRate: 26.375 },
  CA: { name: 'Canada', shortTerm: 0, shortTermRate: 50, longTermRate: 50 },
  AU: { name: 'Australia', shortTerm: 365, shortTermRate: 100, longTermRate: 50 }
}

// Generate mock transactions
const generateTransactions = () => {
  const assets = ['BTC', 'ETH', 'SOL', 'AVAX', 'MATIC', 'ARB', 'OP', 'LINK']
  const types = Object.keys(TX_TYPES)

  return Array.from({ length: 100 }, (_, idx) => {
    const type = types[Math.floor(Math.random() * types.length)]
    const asset = assets[Math.floor(Math.random() * assets.length)]
    const amount = (Math.random() * 10 + 0.01).toFixed(4)
    const price = asset === 'BTC' ? 50000 + Math.random() * 20000 :
                  asset === 'ETH' ? 2500 + Math.random() * 1500 :
                  Math.random() * 200 + 10
    const value = parseFloat(amount) * price
    const date = new Date(Date.now() - Math.random() * 365 * 24 * 60 * 60 * 1000)

    let costBasis = price * (0.7 + Math.random() * 0.6)
    let gain = value - (parseFloat(amount) * costBasis)

    const holdingDays = Math.floor(Math.random() * 500)

    return {
      id: `tx-${idx}`,
      date,
      type,
      asset,
      amount: parseFloat(amount),
      price,
      value,
      costBasis: parseFloat(amount) * costBasis,
      gain: TX_TYPES[type].taxable ? gain : 0,
      holdingDays,
      isLongTerm: holdingDays > 365,
      fee: Math.random() * 10,
      exchange: ['Binance', 'Coinbase', 'Kraken', 'Uniswap', 'dYdX'][Math.floor(Math.random() * 5)],
      wallet: `0x${Math.random().toString(16).slice(2, 10)}...`,
      txHash: `0x${Math.random().toString(16).slice(2, 66)}`,
      reviewed: Math.random() > 0.3
    }
  }).sort((a, b) => b.date - a.date)
}

// Generate tax summary
const generateTaxSummary = (transactions, jurisdiction, year) => {
  const yearTxs = transactions.filter(tx =>
    tx.date.getFullYear() === year && TX_TYPES[tx.type].taxable
  )

  const shortTermGains = yearTxs.filter(tx => !tx.isLongTerm && tx.gain > 0).reduce((sum, tx) => sum + tx.gain, 0)
  const shortTermLosses = yearTxs.filter(tx => !tx.isLongTerm && tx.gain < 0).reduce((sum, tx) => sum + Math.abs(tx.gain), 0)
  const longTermGains = yearTxs.filter(tx => tx.isLongTerm && tx.gain > 0).reduce((sum, tx) => sum + tx.gain, 0)
  const longTermLosses = yearTxs.filter(tx => tx.isLongTerm && tx.gain < 0).reduce((sum, tx) => sum + Math.abs(tx.gain), 0)

  const netShortTerm = shortTermGains - shortTermLosses
  const netLongTerm = longTermGains - longTermLosses
  const totalGains = shortTermGains + longTermGains
  const totalLosses = shortTermLosses + longTermLosses
  const netGain = netShortTerm + netLongTerm

  const shortTermTax = Math.max(0, netShortTerm * JURISDICTIONS[jurisdiction].shortTermRate / 100)
  const longTermTax = Math.max(0, netLongTerm * JURISDICTIONS[jurisdiction].longTermRate / 100)
  const totalTax = shortTermTax + longTermTax

  const income = yearTxs.filter(tx => ['STAKING_REWARD', 'AIRDROP', 'MINING', 'INCOME'].includes(tx.type))
    .reduce((sum, tx) => sum + tx.value, 0)

  return {
    shortTermGains,
    shortTermLosses,
    longTermGains,
    longTermLosses,
    netShortTerm,
    netLongTerm,
    totalGains,
    totalLosses,
    netGain,
    shortTermTax,
    longTermTax,
    totalTax,
    income,
    transactionCount: yearTxs.length,
    unreviewedCount: yearTxs.filter(tx => !tx.reviewed).length
  }
}

export function TaxReporting() {
  const [transactions, setTransactions] = useState([])
  const [selectedYear, setSelectedYear] = useState(2024)
  const [selectedJurisdiction, setSelectedJurisdiction] = useState('US')
  const [taxMethod, setTaxMethod] = useState('FIFO')
  const [searchQuery, setSearchQuery] = useState('')
  const [filterType, setFilterType] = useState('ALL')
  const [showOnlyTaxable, setShowOnlyTaxable] = useState(false)
  const [expandedTx, setExpandedTx] = useState(null)
  const [activeTab, setActiveTab] = useState('summary')
  const [isGenerating, setIsGenerating] = useState(false)

  useEffect(() => {
    setTransactions(generateTransactions())
  }, [])

  const taxSummary = useMemo(() =>
    generateTaxSummary(transactions, selectedJurisdiction, selectedYear),
    [transactions, selectedJurisdiction, selectedYear]
  )

  const filteredTransactions = useMemo(() => {
    return transactions.filter(tx => {
      if (tx.date.getFullYear() !== selectedYear) return false
      if (searchQuery && !tx.asset.toLowerCase().includes(searchQuery.toLowerCase())) return false
      if (filterType !== 'ALL' && tx.type !== filterType) return false
      if (showOnlyTaxable && !TX_TYPES[tx.type].taxable) return false
      return true
    })
  }, [transactions, selectedYear, searchQuery, filterType, showOnlyTaxable])

  const handleExportCSV = () => {
    setIsGenerating(true)
    setTimeout(() => {
      setIsGenerating(false)
      // In real implementation, this would trigger a download
      alert('Tax report exported as CSV')
    }, 1500)
  }

  const handleExportPDF = () => {
    setIsGenerating(true)
    setTimeout(() => {
      setIsGenerating(false)
      alert('Tax report exported as PDF')
    }, 1500)
  }

  const formatCurrency = (value) => {
    const absValue = Math.abs(value)
    if (absValue >= 1e6) return (value >= 0 ? '' : '-') + '$' + (absValue / 1e6).toFixed(2) + 'M'
    if (absValue >= 1e3) return (value >= 0 ? '' : '-') + '$' + (absValue / 1e3).toFixed(2) + 'K'
    return '$' + value.toFixed(2)
  }

  const years = [2024, 2023, 2022, 2021, 2020]

  return (
    <div className="min-h-screen bg-[#0a0e14] text-white p-6">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold mb-2 flex items-center gap-3">
          <FileText className="w-8 h-8 text-cyan-400" />
          Crypto Tax Reporting
        </h1>
        <p className="text-white/60">Calculate capital gains, generate tax reports, and optimize your tax liability</p>
      </div>

      {/* Settings Bar */}
      <div className="bg-white/5 rounded-xl border border-white/10 p-4 mb-6">
        <div className="flex flex-wrap items-center gap-4">
          <div>
            <label className="block text-xs text-white/60 mb-1">Tax Year</label>
            <select
              value={selectedYear}
              onChange={(e) => setSelectedYear(parseInt(e.target.value))}
              className="bg-white/5 border border-white/10 rounded-lg px-4 py-2 focus:outline-none"
            >
              {years.map(year => (
                <option key={year} value={year} className="bg-[#0a0e14]">{year}</option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-xs text-white/60 mb-1">Jurisdiction</label>
            <select
              value={selectedJurisdiction}
              onChange={(e) => setSelectedJurisdiction(e.target.value)}
              className="bg-white/5 border border-white/10 rounded-lg px-4 py-2 focus:outline-none"
            >
              {Object.entries(JURISDICTIONS).map(([key, j]) => (
                <option key={key} value={key} className="bg-[#0a0e14]">{j.name}</option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-xs text-white/60 mb-1">Cost Basis Method</label>
            <select
              value={taxMethod}
              onChange={(e) => setTaxMethod(e.target.value)}
              className="bg-white/5 border border-white/10 rounded-lg px-4 py-2 focus:outline-none"
            >
              {Object.entries(TAX_METHODS).map(([key, method]) => (
                <option key={key} value={key} className="bg-[#0a0e14]">{method.name}</option>
              ))}
            </select>
          </div>

          <div className="flex-1"></div>

          <button
            onClick={handleExportCSV}
            disabled={isGenerating}
            className="px-4 py-2 bg-white/10 hover:bg-white/20 rounded-lg font-medium flex items-center gap-2"
          >
            <FileSpreadsheet className="w-4 h-4" />
            Export CSV
          </button>

          <button
            onClick={handleExportPDF}
            disabled={isGenerating}
            className="px-4 py-2 bg-cyan-500 hover:bg-cyan-600 rounded-lg font-medium flex items-center gap-2"
          >
            {isGenerating ? (
              <RefreshCw className="w-4 h-4 animate-spin" />
            ) : (
              <Download className="w-4 h-4" />
            )}
            Generate Report
          </button>
        </div>
      </div>

      {/* Tax Summary */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <div className="bg-white/5 rounded-xl border border-white/10 p-4">
          <div className="flex items-center justify-between mb-2">
            <span className="text-white/60 text-sm">Net Capital Gains</span>
            <TrendingUp className="w-4 h-4 text-white/40" />
          </div>
          <div className={`text-2xl font-bold ${taxSummary.netGain >= 0 ? 'text-green-400' : 'text-red-400'}`}>
            {formatCurrency(taxSummary.netGain)}
          </div>
          <div className="text-xs text-white/60 mt-1">
            {taxSummary.transactionCount} taxable transactions
          </div>
        </div>

        <div className="bg-white/5 rounded-xl border border-white/10 p-4">
          <div className="flex items-center justify-between mb-2">
            <span className="text-white/60 text-sm">Estimated Tax</span>
            <Calculator className="w-4 h-4 text-white/40" />
          </div>
          <div className="text-2xl font-bold text-orange-400">
            {formatCurrency(taxSummary.totalTax)}
          </div>
          <div className="text-xs text-white/60 mt-1">
            Based on {JURISDICTIONS[selectedJurisdiction].name} rates
          </div>
        </div>

        <div className="bg-white/5 rounded-xl border border-white/10 p-4">
          <div className="flex items-center justify-between mb-2">
            <span className="text-white/60 text-sm">Short Term</span>
            <Clock className="w-4 h-4 text-white/40" />
          </div>
          <div className={`text-2xl font-bold ${taxSummary.netShortTerm >= 0 ? 'text-green-400' : 'text-red-400'}`}>
            {formatCurrency(taxSummary.netShortTerm)}
          </div>
          <div className="text-xs text-white/60 mt-1">
            Taxed at {JURISDICTIONS[selectedJurisdiction].shortTermRate}%
          </div>
        </div>

        <div className="bg-white/5 rounded-xl border border-white/10 p-4">
          <div className="flex items-center justify-between mb-2">
            <span className="text-white/60 text-sm">Long Term</span>
            <Calendar className="w-4 h-4 text-white/40" />
          </div>
          <div className={`text-2xl font-bold ${taxSummary.netLongTerm >= 0 ? 'text-green-400' : 'text-red-400'}`}>
            {formatCurrency(taxSummary.netLongTerm)}
          </div>
          <div className="text-xs text-white/60 mt-1">
            Taxed at {JURISDICTIONS[selectedJurisdiction].longTermRate}%
          </div>
        </div>
      </div>

      {/* Detailed Summary */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-6">
        <div className="lg:col-span-2 bg-white/5 rounded-xl border border-white/10 p-4">
          <h3 className="font-medium mb-4 flex items-center gap-2">
            <BarChart3 className="w-5 h-5 text-cyan-400" />
            Gains & Losses Breakdown
          </h3>

          <div className="grid grid-cols-2 gap-4">
            <div className="bg-white/5 rounded-lg p-4">
              <h4 className="text-sm text-white/60 mb-3">Short Term ({`<`}1 year)</h4>
              <div className="space-y-2">
                <div className="flex justify-between">
                  <span className="text-white/60">Gains</span>
                  <span className="text-green-400">{formatCurrency(taxSummary.shortTermGains)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-white/60">Losses</span>
                  <span className="text-red-400">-{formatCurrency(taxSummary.shortTermLosses)}</span>
                </div>
                <div className="border-t border-white/10 pt-2 flex justify-between font-medium">
                  <span>Net</span>
                  <span className={taxSummary.netShortTerm >= 0 ? 'text-green-400' : 'text-red-400'}>
                    {formatCurrency(taxSummary.netShortTerm)}
                  </span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-white/60">Tax ({JURISDICTIONS[selectedJurisdiction].shortTermRate}%)</span>
                  <span className="text-orange-400">{formatCurrency(taxSummary.shortTermTax)}</span>
                </div>
              </div>
            </div>

            <div className="bg-white/5 rounded-lg p-4">
              <h4 className="text-sm text-white/60 mb-3">Long Term ({`>`}1 year)</h4>
              <div className="space-y-2">
                <div className="flex justify-between">
                  <span className="text-white/60">Gains</span>
                  <span className="text-green-400">{formatCurrency(taxSummary.longTermGains)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-white/60">Losses</span>
                  <span className="text-red-400">-{formatCurrency(taxSummary.longTermLosses)}</span>
                </div>
                <div className="border-t border-white/10 pt-2 flex justify-between font-medium">
                  <span>Net</span>
                  <span className={taxSummary.netLongTerm >= 0 ? 'text-green-400' : 'text-red-400'}>
                    {formatCurrency(taxSummary.netLongTerm)}
                  </span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-white/60">Tax ({JURISDICTIONS[selectedJurisdiction].longTermRate}%)</span>
                  <span className="text-orange-400">{formatCurrency(taxSummary.longTermTax)}</span>
                </div>
              </div>
            </div>
          </div>

          <div className="mt-4 bg-white/5 rounded-lg p-4">
            <div className="flex justify-between items-center">
              <span className="font-medium">Crypto Income (Staking, Airdrops, Mining)</span>
              <span className="text-cyan-400 font-bold">{formatCurrency(taxSummary.income)}</span>
            </div>
            <p className="text-sm text-white/60 mt-1">Taxed as ordinary income at your marginal rate</p>
          </div>
        </div>

        <div className="space-y-4">
          {/* Tax Optimization Tips */}
          <div className="bg-white/5 rounded-xl border border-white/10 p-4">
            <h3 className="font-medium mb-4 flex items-center gap-2">
              <Info className="w-5 h-5 text-cyan-400" />
              Tax Optimization
            </h3>
            <div className="space-y-3">
              {taxSummary.shortTermLosses > 0 && (
                <div className="flex items-start gap-2 text-sm">
                  <Check className="w-4 h-4 text-green-400 flex-shrink-0 mt-0.5" />
                  <span>You have {formatCurrency(taxSummary.shortTermLosses)} in losses to offset gains</span>
                </div>
              )}
              {taxSummary.netShortTerm > 0 && (
                <div className="flex items-start gap-2 text-sm">
                  <AlertTriangle className="w-4 h-4 text-yellow-400 flex-shrink-0 mt-0.5" />
                  <span>Consider holding assets longer for lower long-term rates</span>
                </div>
              )}
              <div className="flex items-start gap-2 text-sm">
                <Info className="w-4 h-4 text-cyan-400 flex-shrink-0 mt-0.5" />
                <span>Review {taxSummary.unreviewedCount} unreviewed transactions</span>
              </div>
            </div>
          </div>

          {/* Quick Stats */}
          <div className="bg-white/5 rounded-xl border border-white/10 p-4">
            <h3 className="font-medium mb-4">Quick Stats</h3>
            <div className="space-y-3">
              <div className="flex justify-between">
                <span className="text-white/60">Total Volume</span>
                <span>{formatCurrency(taxSummary.totalGains + taxSummary.totalLosses)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-white/60">Avg Gain/Trade</span>
                <span>{formatCurrency(taxSummary.netGain / (taxSummary.transactionCount || 1))}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-white/60">Loss Carryover</span>
                <span className="text-orange-400">{formatCurrency(Math.min(0, taxSummary.netGain))}</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Transactions List */}
      <div className="bg-white/5 rounded-xl border border-white/10 overflow-hidden">
        <div className="p-4 border-b border-white/10">
          <div className="flex flex-col md:flex-row gap-4">
            <div className="flex-1 relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-white/40" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search by asset..."
                className="w-full bg-white/5 border border-white/10 rounded-lg pl-10 pr-4 py-2 focus:outline-none focus:border-cyan-500/50"
              />
            </div>

            <select
              value={filterType}
              onChange={(e) => setFilterType(e.target.value)}
              className="bg-white/5 border border-white/10 rounded-lg px-4 py-2 focus:outline-none"
            >
              <option value="ALL" className="bg-[#0a0e14]">All Types</option>
              {Object.entries(TX_TYPES).map(([key, type]) => (
                <option key={key} value={key} className="bg-[#0a0e14]">{type.label}</option>
              ))}
            </select>

            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={showOnlyTaxable}
                onChange={(e) => setShowOnlyTaxable(e.target.checked)}
                className="rounded"
              />
              <span className="text-sm">Taxable only</span>
            </label>
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-white/10">
                <th className="text-left p-4 text-white/60 font-medium">Date</th>
                <th className="text-left p-4 text-white/60 font-medium">Type</th>
                <th className="text-left p-4 text-white/60 font-medium">Asset</th>
                <th className="text-left p-4 text-white/60 font-medium">Amount</th>
                <th className="text-left p-4 text-white/60 font-medium">Value</th>
                <th className="text-left p-4 text-white/60 font-medium">Cost Basis</th>
                <th className="text-left p-4 text-white/60 font-medium">Gain/Loss</th>
                <th className="text-left p-4 text-white/60 font-medium">Term</th>
                <th className="text-left p-4 text-white/60 font-medium">Status</th>
              </tr>
            </thead>
            <tbody>
              {filteredTransactions.slice(0, 50).map((tx, idx) => {
                const TypeIcon = TX_TYPES[tx.type].icon

                return (
                  <tr
                    key={tx.id}
                    className="border-b border-white/5 hover:bg-white/5 cursor-pointer"
                    onClick={() => setExpandedTx(expandedTx === tx.id ? null : tx.id)}
                  >
                    <td className="p-4">
                      <div className="font-medium">{tx.date.toLocaleDateString()}</div>
                      <div className="text-xs text-white/60">{tx.date.toLocaleTimeString()}</div>
                    </td>
                    <td className="p-4">
                      <div className={`flex items-center gap-2 ${TX_TYPES[tx.type].color}`}>
                        <TypeIcon className="w-4 h-4" />
                        {TX_TYPES[tx.type].label}
                      </div>
                    </td>
                    <td className="p-4 font-medium">{tx.asset}</td>
                    <td className="p-4">{tx.amount.toFixed(4)}</td>
                    <td className="p-4">{formatCurrency(tx.value)}</td>
                    <td className="p-4">{formatCurrency(tx.costBasis)}</td>
                    <td className="p-4">
                      {TX_TYPES[tx.type].taxable ? (
                        <span className={tx.gain >= 0 ? 'text-green-400' : 'text-red-400'}>
                          {tx.gain >= 0 ? '+' : ''}{formatCurrency(tx.gain)}
                        </span>
                      ) : (
                        <span className="text-white/40">N/A</span>
                      )}
                    </td>
                    <td className="p-4">
                      <span className={`px-2 py-1 rounded text-xs ${
                        tx.isLongTerm
                          ? 'bg-green-500/20 text-green-400'
                          : 'bg-yellow-500/20 text-yellow-400'
                      }`}>
                        {tx.isLongTerm ? 'Long' : 'Short'}
                      </span>
                    </td>
                    <td className="p-4">
                      {tx.reviewed ? (
                        <Check className="w-5 h-5 text-green-400" />
                      ) : (
                        <AlertTriangle className="w-5 h-5 text-yellow-400" />
                      )}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>

        <div className="p-4 border-t border-white/10 text-center text-white/60">
          Showing {Math.min(50, filteredTransactions.length)} of {filteredTransactions.length} transactions
        </div>
      </div>

      {/* Disclaimer */}
      <div className="mt-6 p-4 bg-yellow-500/10 border border-yellow-500/20 rounded-xl">
        <div className="flex items-start gap-3">
          <AlertTriangle className="w-5 h-5 text-yellow-400 flex-shrink-0 mt-0.5" />
          <div className="text-sm text-white/70">
            <div className="font-medium text-yellow-400 mb-1">Disclaimer</div>
            <p>
              This tool provides estimates for informational purposes only and is not tax advice.
              Tax laws vary by jurisdiction and individual circumstances. Always consult with a
              qualified tax professional before making tax-related decisions.
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}

export default TaxReporting
