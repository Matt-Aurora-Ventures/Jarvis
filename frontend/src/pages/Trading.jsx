import React, { useEffect, useState } from 'react'
import { TrendingUp, DollarSign, Activity, Play, RefreshCw, BarChart2 } from 'lucide-react'

function Trading() {
    const [tradingStats, setTradingStats] = useState({
        activeStrategies: 0,
        backtestsRunning: 0,
        solanaTokens: 50,
        avgVolume: 0,
    })

    const [solanaTokens, setSolanaTokens] = useState([])
    const [backtestResults, setBacktestResults] = useState([])
    const [isScanning, setIsScanning] = useState(false)
    const [isBacktesting, setIsBacktesting] = useState(false)

    useEffect(() => {
        fetchTradingStats()
        fetchSolanaTokens()
        fetchBacktests()

        const interval = setInterval(() => {
            fetchTradingStats()
            if (isBacktesting) fetchBacktests()
        }, 5000)

        return () => clearInterval(interval)
    }, [isBacktesting])

    const fetchTradingStats = async () => {
        try {
            const response = await fetch('/api/trading/stats')
            if (response.ok) {
                const data = await response.json()
                setTradingStats(data)
            }
        } catch (error) {
            console.error('Failed to fetch trading stats:', error)
        }
    }

    const fetchSolanaTokens = async () => {
        try {
            const response = await fetch('/api/trading/solana/tokens')
            if (response.ok) {
                const data = await response.json()
                setSolanaTokens(data.tokens || [])
            }
        } catch (error) {
            console.error('Failed to fetch Solana tokens:', error)
        }
    }

    const fetchBacktests = async () => {
        try {
            const response = await fetch('/api/trading/backtests')
            if (response.ok) {
                const data = await response.json()
                setBacktestResults(data.results || [])
            }
        } catch (error) {
            console.error('Failed to fetch backtests:', error)
        }
    }

    const scanSolana = async () => {
        setIsScanning(true)
        try {
            const response = await fetch('/api/trading/solana/scan', {
                method: 'POST',
            })
            if (response.ok) {
                await fetchSolanaTokens()
            }
        } catch (error) {
            console.error('Failed to scan Solana:', error)
        } finally {
            setIsScanning(false)
        }
    }

    const runBacktests = async () => {
        setIsBacktesting(true)
        try {
            await fetch('/api/trading/backtests/run', {
                method: 'POST',
            })
        } catch (error) {
            console.error('Failed to run backtests:', error)
        }
    }

    return (
        <div className="flex-1 p-8 overflow-y-auto">
            <header className="mb-8">
                <h1 className="text-3xl font-bold text-white mb-2">Trading Dashboard</h1>
                <p className="text-slate-400">Monitor Solana tokens, backtests, and trading strategies</p>
            </header>

            {/* Stats Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
                <StatCard
                    icon={<TrendingUp className="text-jarvis-primary" />}
                    label="Active Strategies"
                    value={tradingStats.activeStrategies}
                />
                <StatCard
                    icon={<Activity className="text-blue-500" />}
                    label="Backtests Running"
                    value={tradingStats.backtestsRunning}
                    isActive={isBacktesting}
                />
                <StatCard
                    icon={<DollarSign className="text-green-500" />}
                    label="Solana Tokens"
                    value={tradingStats.solanaTokens}
                />
                <StatCard
                    icon={<BarChart2 className="text-jarvis-secondary" />}
                    label="Avg 24h Volume"
                    value={`$${(tradingStats.avgVolume / 1000).toFixed(1)}K`}
                />
            </div>

            {/* Actions */}
            <div className="flex gap-4 mb-8">
                <button
                    onClick={scanSolana}
                    disabled={isScanning}
                    className="flex items-center gap-2 bg-jarvis-primary hover:bg-jarvis-primary/80 disabled:bg-slate-700 text-white px-6 py-3 rounded-lg transition-colors"
                >
                    <RefreshCw className={`w-5 h-5 ${isScanning ? 'animate-spin' : ''}`} />
                    {isScanning ? 'Scanning...' : 'Scan Solana Tokens'}
                </button>

                <button
                    onClick={runBacktests}
                    disabled={isBacktesting}
                    className="flex items-center gap-2 bg-blue-600 hover:bg-blue-700 disabled:bg-slate-700 text-white px-6 py-3 rounded-lg transition-colors"
                >
                    <Play className="w-5 h-5" />
                    {isBacktesting ? 'Running Backtests...' : 'Run 90-Day Backtests'}
                </button>
            </div>

            {/* Solana Tokens Table */}
            <div className="bg-jarvis-dark rounded-2xl p-6 border border-slate-700 mb-8">
                <h2 className="text-xl font-semibold text-white mb-4">Top Solana Tokens (High Volume)</h2>

                <div className="overflow-x-auto">
                    <table className="w-full">
                        <thead>
                            <tr className="text-left text-slate-400 text-sm border-b border-slate-700">
                                <th className="pb-3 pr-4">Symbol</th>
                                <th className="pb-3 pr-4">Name</th>
                                <th className="pb-3 pr-4">24h Volume</th>
                                <th className="pb-3 pr-4">Price</th>
                                <th className="pb-3 pr-4">Liquidity</th>
                                <th className="pb-3">Status</th>
                            </tr>
                        </thead>
                        <tbody>
                            {solanaTokens.length > 0 ? (
                                solanaTokens.slice(0, 20).map((token, index) => (
                                    <tr key={index} className="border-b border-slate-800 hover:bg-slate-800/50">
                                        <td className="py-3 pr-4 text-white font-semibold">{token.symbol}</td>
                                        <td className="py-3 pr-4 text-slate-300">{token.name}</td>
                                        <td className="py-3 pr-4 text-green-400">${(token.volume24hUSD / 1000).toFixed(1)}K</td>
                                        <td className="py-3 pr-4 text-slate-300">${token.price?.toFixed(6) || '---'}</td>
                                        <td className="py-3 pr-4 text-blue-400">${(token.liquidity / 1000).toFixed(1)}K</td>
                                        <td className="py-3">
                                            <span className="px-2 py-1 bg-green-500/20 text-green-400 rounded text-xs">
                                                Active
                                            </span>
                                        </td>
                                    </tr>
                                ))
                            ) : (
                                <tr>
                                    <td colSpan="6" className="py-8 text-center text-slate-500">
                                        No tokens loaded. Click "Scan Solana Tokens" to fetch data.
                                    </td>
                                </tr>
                            )}
                        </tbody>
                    </table>
                </div>
            </div>

            {/* Backtest Results */}
            <div className="bg-jarvis-dark rounded-2xl p-6 border border-slate-700">
                <h2 className="text-xl font-semibold text-white mb-4">Recent Backtest Results</h2>

                <div className="space-y-3">
                    {backtestResults.length > 0 ? (
                        backtestResults.slice(0, 10).map((result, index) => (
                            <div key={index} className="p-4 bg-slate-800/50 rounded-xl flex items-center justify-between">
                                <div className="flex-1">
                                    <div className="flex items-center gap-3 mb-1">
                                        <span className="text-white font-semibold">{result.strategy_name}</span>
                                        <span className={`px-2 py-0.5 rounded text-xs ${result.passed ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'
                                            }`}>
                                            {result.passed ? 'Passed' : 'Failed'}
                                        </span>
                                    </div>
                                    <div className="flex gap-6 text-sm text-slate-400">
                                        <span>Period: {result.window_start} to {result.window_end}</span>
                                        <span>Trades: {result.total_trades}</span>
                                    </div>
                                </div>
                                <div className="text-right">
                                    <div className="text-white font-semibold mb-1">
                                        Sharpe: {result.sharpe_ratio?.toFixed(2) || '---'}
                                    </div>
                                    <div className="text-sm text-slate-400">
                                        Win Rate: {(result.win_rate * 100).toFixed(1)}%
                                    </div>
                                </div>
                            </div>
                        ))
                    ) : (
                        <p className="text-slate-500 text-center py-8">
                            No backtests completed. Click "Run 90-Day Backtests" to start.
                        </p>
                    )}
                </div>
            </div>
        </div>
    )
}

function StatCard({ icon, label, value, isActive }) {
    return (
        <div className="bg-jarvis-dark rounded-2xl p-6 border border-slate-700">
            <div className="flex items-center gap-3 mb-2">
                <div className={isActive ? 'animate-pulse' : ''}>
                    {icon}
                </div>
                <span className="text-slate-400 text-sm">{label}</span>
            </div>
            <p className="text-3xl font-bold text-white">{value}</p>
        </div>
    )
}

export default Trading
