import React, { useState, useMemo, useEffect, useCallback } from 'react'
import {
  Shield, AlertTriangle, CheckCircle, XCircle, Search, FileCode,
  Lock, Unlock, Eye, EyeOff, RefreshCw, Copy, ExternalLink,
  AlertOctagon, Bug, Zap, Users, Coins, ArrowRightLeft, Clock,
  ChevronDown, ChevronUp, Info, TrendingUp, Database
} from 'lucide-react'

// Security check types
const SECURITY_CHECKS = {
  OWNERSHIP: { name: 'Ownership', icon: Users, description: 'Contract ownership analysis' },
  HONEYPOT: { name: 'Honeypot', icon: Bug, description: 'Honeypot detection' },
  REENTRANCY: { name: 'Reentrancy', icon: RefreshCw, description: 'Reentrancy vulnerability' },
  PROXY: { name: 'Proxy', icon: ArrowRightLeft, description: 'Proxy pattern detection' },
  MINT: { name: 'Mint Function', icon: Coins, description: 'Unlimited mint capability' },
  PAUSE: { name: 'Pausable', icon: Clock, description: 'Contract pause functionality' },
  BLACKLIST: { name: 'Blacklist', icon: XCircle, description: 'Address blacklisting' },
  TAX: { name: 'Hidden Tax', icon: TrendingUp, description: 'Hidden transaction fees' },
  VERIFIED: { name: 'Verified', icon: CheckCircle, description: 'Source code verified' },
  LIQUIDITY: { name: 'Liquidity Lock', icon: Lock, description: 'Liquidity lock status' }
}

// Risk levels
const RISK_LEVELS = {
  SAFE: { label: 'Safe', color: 'text-green-400', bg: 'bg-green-500/20', score: '90-100' },
  LOW: { label: 'Low Risk', color: 'text-blue-400', bg: 'bg-blue-500/20', score: '70-89' },
  MEDIUM: { label: 'Medium Risk', color: 'text-yellow-400', bg: 'bg-yellow-500/20', score: '40-69' },
  HIGH: { label: 'High Risk', color: 'text-orange-400', bg: 'bg-orange-500/20', score: '20-39' },
  CRITICAL: { label: 'Critical', color: 'text-red-400', bg: 'bg-red-500/20', score: '0-19' }
}

// Supported chains
const CHAINS = {
  ETH: { name: 'Ethereum', explorer: 'etherscan.io' },
  BSC: { name: 'BNB Chain', explorer: 'bscscan.com' },
  ARB: { name: 'Arbitrum', explorer: 'arbiscan.io' },
  BASE: { name: 'Base', explorer: 'basescan.org' },
  POLYGON: { name: 'Polygon', explorer: 'polygonscan.com' },
  SOL: { name: 'Solana', explorer: 'solscan.io' }
}

// Generate mock scan result
const generateScanResult = (address, chain) => {
  const isToken = Math.random() > 0.3
  const baseScore = Math.floor(Math.random() * 100)

  const checks = Object.keys(SECURITY_CHECKS).map(key => {
    const passed = Math.random() > 0.3
    const severity = passed ? 'safe' : ['low', 'medium', 'high', 'critical'][Math.floor(Math.random() * 4)]
    return {
      type: key,
      passed,
      severity,
      details: passed ? 'No issues found' : `Potential ${SECURITY_CHECKS[key].name.toLowerCase()} vulnerability detected`
    }
  })

  const passedChecks = checks.filter(c => c.passed).length
  const score = Math.floor((passedChecks / checks.length) * 100)

  let riskLevel = 'SAFE'
  if (score < 20) riskLevel = 'CRITICAL'
  else if (score < 40) riskLevel = 'HIGH'
  else if (score < 70) riskLevel = 'MEDIUM'
  else if (score < 90) riskLevel = 'LOW'

  return {
    address,
    chain,
    isToken,
    name: isToken ? ['SafeMoon', 'PepeCoin', 'ShibaX', 'DogeBonk', 'FlokiInu'][Math.floor(Math.random() * 5)] : 'Unknown Contract',
    symbol: isToken ? ['SAFM', 'PEPE', 'SHIBX', 'DOBO', 'FLOKI'][Math.floor(Math.random() * 5)] : null,
    score,
    riskLevel,
    checks,
    verified: Math.random() > 0.4,
    proxyType: Math.random() > 0.7 ? ['Transparent', 'UUPS', 'Beacon'][Math.floor(Math.random() * 3)] : null,
    compiler: `solc ${['0.8.19', '0.8.20', '0.8.21', '0.7.6'][Math.floor(Math.random() * 4)]}`,
    deployedAt: new Date(Date.now() - Math.random() * 365 * 24 * 60 * 60 * 1000),
    creator: `0x${Math.random().toString(16).slice(2, 42)}`,
    txCount: Math.floor(Math.random() * 100000),
    holders: isToken ? Math.floor(Math.random() * 50000) : null,
    totalSupply: isToken ? (Math.random() * 1000000000000).toFixed(0) : null,
    liquidity: isToken ? Math.floor(Math.random() * 5000000) : null,
    liquidityLocked: Math.random() > 0.5,
    lockDuration: Math.random() > 0.5 ? Math.floor(Math.random() * 365) : null,
    ownerBalance: (Math.random() * 30).toFixed(2),
    top10Holdings: (Math.random() * 80).toFixed(2),
    buyTax: (Math.random() * 15).toFixed(1),
    sellTax: (Math.random() * 20).toFixed(1),
    similarContracts: Math.floor(Math.random() * 100),
    scanTime: new Date()
  }
}

// Recent scans mock data
const generateRecentScans = () => {
  const chains = Object.keys(CHAINS)
  return Array.from({ length: 10 }, () => {
    const chain = chains[Math.floor(Math.random() * chains.length)]
    const address = `0x${Math.random().toString(16).slice(2, 42)}`
    return generateScanResult(address, chain)
  })
}

export function ContractScanner() {
  const [searchAddress, setSearchAddress] = useState('')
  const [selectedChain, setSelectedChain] = useState('ETH')
  const [scanResult, setScanResult] = useState(null)
  const [isScanning, setIsScanning] = useState(false)
  const [recentScans, setRecentScans] = useState([])
  const [expandedChecks, setExpandedChecks] = useState({})
  const [activeTab, setActiveTab] = useState('overview')

  useEffect(() => {
    setRecentScans(generateRecentScans())
  }, [])

  const handleScan = useCallback(() => {
    if (!searchAddress) return

    setIsScanning(true)
    // Simulate API call
    setTimeout(() => {
      const result = generateScanResult(searchAddress, selectedChain)
      setScanResult(result)
      setRecentScans(prev => [result, ...prev.slice(0, 9)])
      setIsScanning(false)
    }, 2000)
  }, [searchAddress, selectedChain])

  const toggleCheck = (checkType) => {
    setExpandedChecks(prev => ({
      ...prev,
      [checkType]: !prev[checkType]
    }))
  }

  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text)
  }

  const formatAddress = (addr) => {
    if (!addr) return ''
    return `${addr.slice(0, 6)}...${addr.slice(-4)}`
  }

  const formatNumber = (num) => {
    if (num >= 1e9) return (num / 1e9).toFixed(2) + 'B'
    if (num >= 1e6) return (num / 1e6).toFixed(2) + 'M'
    if (num >= 1e3) return (num / 1e3).toFixed(2) + 'K'
    return num?.toString() || '0'
  }

  const getRiskColor = (level) => RISK_LEVELS[level]?.color || 'text-white/60'
  const getRiskBg = (level) => RISK_LEVELS[level]?.bg || 'bg-white/10'

  const getSeverityColor = (severity) => {
    switch (severity) {
      case 'safe': return 'text-green-400'
      case 'low': return 'text-blue-400'
      case 'medium': return 'text-yellow-400'
      case 'high': return 'text-orange-400'
      case 'critical': return 'text-red-400'
      default: return 'text-white/60'
    }
  }

  return (
    <div className="min-h-screen bg-[#0a0e14] text-white p-6">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold mb-2 flex items-center gap-3">
          <Shield className="w-8 h-8 text-cyan-400" />
          Smart Contract Scanner
        </h1>
        <p className="text-white/60">Security audit and vulnerability detection for smart contracts</p>
      </div>

      {/* Search Section */}
      <div className="bg-white/5 rounded-xl border border-white/10 p-6 mb-6">
        <div className="flex flex-col md:flex-row gap-4">
          <div className="flex-1">
            <label className="block text-sm text-white/60 mb-2">Contract Address</label>
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-white/40" />
              <input
                type="text"
                value={searchAddress}
                onChange={(e) => setSearchAddress(e.target.value)}
                placeholder="0x... or token name"
                className="w-full bg-white/5 border border-white/10 rounded-lg pl-10 pr-4 py-3 focus:outline-none focus:border-cyan-500/50"
              />
            </div>
          </div>

          <div className="w-full md:w-48">
            <label className="block text-sm text-white/60 mb-2">Chain</label>
            <select
              value={selectedChain}
              onChange={(e) => setSelectedChain(e.target.value)}
              className="w-full bg-white/5 border border-white/10 rounded-lg px-4 py-3 focus:outline-none focus:border-cyan-500/50"
            >
              {Object.entries(CHAINS).map(([key, chain]) => (
                <option key={key} value={key} className="bg-[#0a0e14]">
                  {chain.name}
                </option>
              ))}
            </select>
          </div>

          <div className="flex items-end">
            <button
              onClick={handleScan}
              disabled={isScanning || !searchAddress}
              className="w-full md:w-auto px-6 py-3 bg-cyan-500 hover:bg-cyan-600 disabled:bg-white/10 disabled:cursor-not-allowed rounded-lg font-medium flex items-center justify-center gap-2 transition-colors"
            >
              {isScanning ? (
                <>
                  <RefreshCw className="w-5 h-5 animate-spin" />
                  Scanning...
                </>
              ) : (
                <>
                  <Shield className="w-5 h-5" />
                  Scan Contract
                </>
              )}
            </button>
          </div>
        </div>
      </div>

      {/* Scan Result */}
      {scanResult && (
        <div className="bg-white/5 rounded-xl border border-white/10 overflow-hidden mb-6">
          {/* Result Header */}
          <div className="p-6 border-b border-white/10">
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
              <div className="flex items-center gap-4">
                <div className={`w-16 h-16 rounded-xl ${getRiskBg(scanResult.riskLevel)} flex items-center justify-center`}>
                  <span className={`text-2xl font-bold ${getRiskColor(scanResult.riskLevel)}`}>
                    {scanResult.score}
                  </span>
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <h2 className="text-xl font-bold">
                      {scanResult.isToken ? scanResult.name : 'Contract'}
                    </h2>
                    {scanResult.symbol && (
                      <span className="px-2 py-0.5 bg-white/10 rounded text-sm">
                        ${scanResult.symbol}
                      </span>
                    )}
                    {scanResult.verified && (
                      <CheckCircle className="w-5 h-5 text-green-400" />
                    )}
                  </div>
                  <div className="flex items-center gap-2 mt-1">
                    <span className="text-white/60 font-mono text-sm">
                      {formatAddress(scanResult.address)}
                    </span>
                    <button onClick={() => copyToClipboard(scanResult.address)} className="text-white/40 hover:text-white">
                      <Copy className="w-4 h-4" />
                    </button>
                    <a href={`https://${CHAINS[scanResult.chain].explorer}/address/${scanResult.address}`} target="_blank" rel="noopener noreferrer" className="text-white/40 hover:text-cyan-400">
                      <ExternalLink className="w-4 h-4" />
                    </a>
                  </div>
                </div>
              </div>

              <div className={`px-4 py-2 rounded-lg ${getRiskBg(scanResult.riskLevel)}`}>
                <span className={`font-medium ${getRiskColor(scanResult.riskLevel)}`}>
                  {RISK_LEVELS[scanResult.riskLevel].label}
                </span>
              </div>
            </div>
          </div>

          {/* Tabs */}
          <div className="flex border-b border-white/10">
            {['overview', 'security', 'tokenomics', 'code'].map(tab => (
              <button
                key={tab}
                onClick={() => setActiveTab(tab)}
                className={`px-6 py-3 font-medium capitalize transition-colors ${
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
          <div className="p-6">
            {activeTab === 'overview' && (
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div className="bg-white/5 rounded-lg p-4">
                  <div className="text-white/60 text-sm mb-1">Chain</div>
                  <div className="font-medium">{CHAINS[scanResult.chain].name}</div>
                </div>
                <div className="bg-white/5 rounded-lg p-4">
                  <div className="text-white/60 text-sm mb-1">Deployed</div>
                  <div className="font-medium">{scanResult.deployedAt.toLocaleDateString()}</div>
                </div>
                <div className="bg-white/5 rounded-lg p-4">
                  <div className="text-white/60 text-sm mb-1">Transactions</div>
                  <div className="font-medium">{formatNumber(scanResult.txCount)}</div>
                </div>
                <div className="bg-white/5 rounded-lg p-4">
                  <div className="text-white/60 text-sm mb-1">Compiler</div>
                  <div className="font-medium">{scanResult.compiler}</div>
                </div>
                {scanResult.isToken && (
                  <>
                    <div className="bg-white/5 rounded-lg p-4">
                      <div className="text-white/60 text-sm mb-1">Holders</div>
                      <div className="font-medium">{formatNumber(scanResult.holders)}</div>
                    </div>
                    <div className="bg-white/5 rounded-lg p-4">
                      <div className="text-white/60 text-sm mb-1">Liquidity</div>
                      <div className="font-medium">${formatNumber(scanResult.liquidity)}</div>
                    </div>
                    <div className="bg-white/5 rounded-lg p-4">
                      <div className="text-white/60 text-sm mb-1">Buy Tax</div>
                      <div className="font-medium">{scanResult.buyTax}%</div>
                    </div>
                    <div className="bg-white/5 rounded-lg p-4">
                      <div className="text-white/60 text-sm mb-1">Sell Tax</div>
                      <div className="font-medium">{scanResult.sellTax}%</div>
                    </div>
                  </>
                )}
                {scanResult.proxyType && (
                  <div className="bg-white/5 rounded-lg p-4">
                    <div className="text-white/60 text-sm mb-1">Proxy Type</div>
                    <div className="font-medium">{scanResult.proxyType}</div>
                  </div>
                )}
              </div>
            )}

            {activeTab === 'security' && (
              <div className="space-y-3">
                {scanResult.checks.map((check, idx) => {
                  const CheckIcon = SECURITY_CHECKS[check.type].icon
                  return (
                    <div key={idx} className="bg-white/5 rounded-lg overflow-hidden">
                      <button
                        onClick={() => toggleCheck(check.type)}
                        className="w-full p-4 flex items-center justify-between hover:bg-white/5 transition-colors"
                      >
                        <div className="flex items-center gap-3">
                          <div className={`w-10 h-10 rounded-lg ${check.passed ? 'bg-green-500/20' : 'bg-red-500/20'} flex items-center justify-center`}>
                            <CheckIcon className={`w-5 h-5 ${check.passed ? 'text-green-400' : 'text-red-400'}`} />
                          </div>
                          <div className="text-left">
                            <div className="font-medium">{SECURITY_CHECKS[check.type].name}</div>
                            <div className="text-sm text-white/60">{SECURITY_CHECKS[check.type].description}</div>
                          </div>
                        </div>
                        <div className="flex items-center gap-3">
                          <span className={`px-2 py-1 rounded text-sm ${check.passed ? 'bg-green-500/20 text-green-400' : `bg-${check.severity === 'critical' ? 'red' : check.severity === 'high' ? 'orange' : check.severity === 'medium' ? 'yellow' : 'blue'}-500/20 ${getSeverityColor(check.severity)}`}`}>
                            {check.passed ? 'Passed' : check.severity.toUpperCase()}
                          </span>
                          {expandedChecks[check.type] ? <ChevronUp className="w-5 h-5 text-white/40" /> : <ChevronDown className="w-5 h-5 text-white/40" />}
                        </div>
                      </button>
                      {expandedChecks[check.type] && (
                        <div className="px-4 pb-4 pt-0 border-t border-white/5">
                          <div className="bg-white/5 rounded p-3 text-sm text-white/80">
                            {check.details}
                          </div>
                        </div>
                      )}
                    </div>
                  )
                })}
              </div>
            )}

            {activeTab === 'tokenomics' && scanResult.isToken && (
              <div className="space-y-6">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  <div className="bg-white/5 rounded-lg p-4">
                    <h3 className="font-medium mb-4 flex items-center gap-2">
                      <Coins className="w-5 h-5 text-cyan-400" />
                      Supply Distribution
                    </h3>
                    <div className="space-y-3">
                      <div className="flex justify-between">
                        <span className="text-white/60">Total Supply</span>
                        <span>{formatNumber(scanResult.totalSupply)}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-white/60">Owner Balance</span>
                        <span className={parseFloat(scanResult.ownerBalance) > 10 ? 'text-yellow-400' : ''}>{scanResult.ownerBalance}%</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-white/60">Top 10 Holdings</span>
                        <span className={parseFloat(scanResult.top10Holdings) > 50 ? 'text-orange-400' : ''}>{scanResult.top10Holdings}%</span>
                      </div>
                    </div>
                  </div>

                  <div className="bg-white/5 rounded-lg p-4">
                    <h3 className="font-medium mb-4 flex items-center gap-2">
                      <Lock className="w-5 h-5 text-cyan-400" />
                      Liquidity Info
                    </h3>
                    <div className="space-y-3">
                      <div className="flex justify-between">
                        <span className="text-white/60">Liquidity</span>
                        <span>${formatNumber(scanResult.liquidity)}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-white/60">Lock Status</span>
                        <span className={scanResult.liquidityLocked ? 'text-green-400' : 'text-red-400'}>
                          {scanResult.liquidityLocked ? 'Locked' : 'Unlocked'}
                        </span>
                      </div>
                      {scanResult.lockDuration && (
                        <div className="flex justify-between">
                          <span className="text-white/60">Lock Duration</span>
                          <span>{scanResult.lockDuration} days</span>
                        </div>
                      )}
                    </div>
                  </div>
                </div>

                <div className="bg-white/5 rounded-lg p-4">
                  <h3 className="font-medium mb-4 flex items-center gap-2">
                    <TrendingUp className="w-5 h-5 text-cyan-400" />
                    Tax Configuration
                  </h3>
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <div className="text-white/60 text-sm mb-1">Buy Tax</div>
                      <div className={`text-xl font-bold ${parseFloat(scanResult.buyTax) > 10 ? 'text-orange-400' : 'text-green-400'}`}>
                        {scanResult.buyTax}%
                      </div>
                    </div>
                    <div>
                      <div className="text-white/60 text-sm mb-1">Sell Tax</div>
                      <div className={`text-xl font-bold ${parseFloat(scanResult.sellTax) > 10 ? 'text-orange-400' : 'text-green-400'}`}>
                        {scanResult.sellTax}%
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {activeTab === 'code' && (
              <div className="space-y-4">
                <div className="bg-white/5 rounded-lg p-4">
                  <div className="flex items-center justify-between mb-4">
                    <h3 className="font-medium flex items-center gap-2">
                      <FileCode className="w-5 h-5 text-cyan-400" />
                      Contract Info
                    </h3>
                    <div className={`px-3 py-1 rounded-full text-sm ${scanResult.verified ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'}`}>
                      {scanResult.verified ? 'Verified' : 'Unverified'}
                    </div>
                  </div>
                  <div className="space-y-3 text-sm">
                    <div className="flex justify-between">
                      <span className="text-white/60">Compiler Version</span>
                      <span className="font-mono">{scanResult.compiler}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-white/60">Creator</span>
                      <div className="flex items-center gap-2">
                        <span className="font-mono">{formatAddress(scanResult.creator)}</span>
                        <button onClick={() => copyToClipboard(scanResult.creator)} className="text-white/40 hover:text-white">
                          <Copy className="w-3 h-3" />
                        </button>
                      </div>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-white/60">Similar Contracts</span>
                      <span>{scanResult.similarContracts}</span>
                    </div>
                    {scanResult.proxyType && (
                      <div className="flex justify-between">
                        <span className="text-white/60">Proxy Pattern</span>
                        <span className="text-yellow-400">{scanResult.proxyType}</span>
                      </div>
                    )}
                  </div>
                </div>

                <div className="bg-yellow-500/10 border border-yellow-500/20 rounded-lg p-4">
                  <div className="flex items-start gap-3">
                    <AlertTriangle className="w-5 h-5 text-yellow-400 flex-shrink-0 mt-0.5" />
                    <div className="text-sm">
                      <div className="font-medium text-yellow-400 mb-1">Security Notice</div>
                      <div className="text-white/70">
                        This scan provides automated analysis. Always do your own research and verify contract code before interacting.
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Recent Scans */}
      <div className="bg-white/5 rounded-xl border border-white/10 overflow-hidden">
        <div className="p-4 border-b border-white/10">
          <h2 className="font-semibold flex items-center gap-2">
            <Database className="w-5 h-5 text-cyan-400" />
            Recent Scans
          </h2>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-white/10">
                <th className="text-left p-4 text-white/60 font-medium">Contract</th>
                <th className="text-left p-4 text-white/60 font-medium">Chain</th>
                <th className="text-left p-4 text-white/60 font-medium">Score</th>
                <th className="text-left p-4 text-white/60 font-medium">Risk</th>
                <th className="text-left p-4 text-white/60 font-medium">Verified</th>
                <th className="text-left p-4 text-white/60 font-medium">Scanned</th>
                <th className="text-left p-4 text-white/60 font-medium">Actions</th>
              </tr>
            </thead>
            <tbody>
              {recentScans.map((scan, idx) => (
                <tr key={idx} className="border-b border-white/5 hover:bg-white/5">
                  <td className="p-4">
                    <div className="font-medium">{scan.isToken ? scan.name : 'Contract'}</div>
                    <div className="text-sm text-white/60 font-mono">{formatAddress(scan.address)}</div>
                  </td>
                  <td className="p-4">{CHAINS[scan.chain].name}</td>
                  <td className="p-4">
                    <span className={`font-bold ${getRiskColor(scan.riskLevel)}`}>{scan.score}</span>
                  </td>
                  <td className="p-4">
                    <span className={`px-2 py-1 rounded text-sm ${getRiskBg(scan.riskLevel)} ${getRiskColor(scan.riskLevel)}`}>
                      {RISK_LEVELS[scan.riskLevel].label}
                    </span>
                  </td>
                  <td className="p-4">
                    {scan.verified ? (
                      <CheckCircle className="w-5 h-5 text-green-400" />
                    ) : (
                      <XCircle className="w-5 h-5 text-red-400" />
                    )}
                  </td>
                  <td className="p-4 text-white/60">
                    {scan.scanTime.toLocaleTimeString()}
                  </td>
                  <td className="p-4">
                    <button
                      onClick={() => {
                        setSearchAddress(scan.address)
                        setSelectedChain(scan.chain)
                        setScanResult(scan)
                      }}
                      className="text-cyan-400 hover:text-cyan-300"
                    >
                      <Eye className="w-5 h-5" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Risk Legend */}
      <div className="mt-6 p-4 bg-white/5 rounded-xl border border-white/10">
        <h3 className="font-medium mb-3 flex items-center gap-2">
          <Info className="w-5 h-5 text-cyan-400" />
          Risk Score Guide
        </h3>
        <div className="flex flex-wrap gap-4">
          {Object.entries(RISK_LEVELS).map(([key, level]) => (
            <div key={key} className="flex items-center gap-2">
              <div className={`w-3 h-3 rounded-full ${level.bg}`}></div>
              <span className={level.color}>{level.label}</span>
              <span className="text-white/40 text-sm">({level.score})</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

export default ContractScanner
