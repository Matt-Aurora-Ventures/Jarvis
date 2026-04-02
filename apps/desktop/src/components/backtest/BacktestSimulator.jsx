import React, { useState, useMemo, useEffect } from 'react'
import {
  PlayCircle,
  PauseCircle,
  SkipForward,
  SkipBack,
  Settings,
  TrendingUp,
  TrendingDown,
  DollarSign,
  BarChart3,
  Calendar,
  Target,
  Shield,
  Zap,
  ChevronDown,
  ChevronUp,
  Download,
  RefreshCw,
  Clock,
  Activity,
  AlertTriangle,
  CheckCircle,
  XCircle,
  LineChart,
  PieChart
} from 'lucide-react'

export function BacktestSimulator() {
  const [mode, setMode] = useState('setup') // setup, running, results
  const [strategy, setStrategy] = useState('sma_cross')
  const [timeframe, setTimeframe] = useState('1d')
  const [startDate, setStartDate] = useState('2024-01-01')
  const [endDate, setEndDate] = useState('2024-12-31')
  const [initialCapital, setInitialCapital] = useState(10000)
  const [selectedToken, setSelectedToken] = useState('SOL')
  const [isRunning, setIsRunning] = useState(false)
  const [progress, setProgress] = useState(0)
  const [speed, setSpeed] = useState(1)

  const strategies = [
    { id: 'sma_cross', name: 'SMA Crossover', description: 'Buy when short SMA crosses above long SMA' },
    { id: 'rsi_oversold', name: 'RSI Oversold', description: 'Buy when RSI drops below 30, sell above 70' },
    { id: 'macd_signal', name: 'MACD Signal', description: 'Trade on MACD signal line crossovers' },
    { id: 'bollinger_bounce', name: 'Bollinger Bounce', description: 'Buy at lower band, sell at upper band' },
    { id: 'momentum', name: 'Momentum', description: 'Follow price momentum with trailing stops' },
    { id: 'mean_reversion', name: 'Mean Reversion', description: 'Trade reversions to moving average' },
    { id: 'breakout', name: 'Breakout', description: 'Trade breakouts from consolidation' },
    { id: 'dca', name: 'DCA', description: 'Dollar cost averaging at regular intervals' }
  ]

  const tokens = ['SOL', 'ETH', 'BTC', 'BONK', 'WIF', 'JUP', 'RNDR', 'PYTH', 'JTO', 'RAY']

  const timeframes = [
    { id: '1m', name: '1 Minute' },
    { id: '5m', name: '5 Minutes' },
    { id: '15m', name: '15 Minutes' },
    { id: '1h', name: '1 Hour' },
    { id: '4h', name: '4 Hours' },
    { id: '1d', name: '1 Day' }
  ]

  // Strategy Parameters
  const [strategyParams, setStrategyParams] = useState({
    sma_short: 10,
    sma_long: 50,
    rsi_period: 14,
    rsi_oversold: 30,
    rsi_overbought: 70,
    stop_loss: 5,
    take_profit: 15,
    position_size: 100
  })

  // Generate mock backtest results
  const backtestResults = useMemo(() => {
    const totalTrades = Math.floor(Math.random() * 100) + 50
    const winRate = 40 + Math.random() * 30
    const avgWin = Math.random() * 10 + 5
    const avgLoss = Math.random() * 5 + 2
    const profitFactor = (winRate / 100 * avgWin) / ((100 - winRate) / 100 * avgLoss)
    const totalReturn = (Math.random() - 0.3) * 200
    const maxDrawdown = Math.random() * 30 + 10
    const sharpeRatio = (Math.random() * 2 - 0.5).toFixed(2)

    return {
      totalTrades,
      winningTrades: Math.floor(totalTrades * winRate / 100),
      losingTrades: Math.floor(totalTrades * (100 - winRate) / 100),
      winRate: winRate.toFixed(2),
      avgWin: avgWin.toFixed(2),
      avgLoss: avgLoss.toFixed(2),
      profitFactor: profitFactor.toFixed(2),
      totalReturn: totalReturn.toFixed(2),
      finalCapital: initialCapital * (1 + totalReturn / 100),
      maxDrawdown: maxDrawdown.toFixed(2),
      sharpeRatio,
      sortinoRatio: (parseFloat(sharpeRatio) * 1.2).toFixed(2),
      avgHoldTime: Math.floor(Math.random() * 72) + 1,
      bestTrade: (Math.random() * 30 + 10).toFixed(2),
      worstTrade: -(Math.random() * 15 + 5).toFixed(2),
      consecutiveWins: Math.floor(Math.random() * 8) + 2,
      consecutiveLosses: Math.floor(Math.random() * 5) + 1,
      calmarRatio: (totalReturn / maxDrawdown).toFixed(2)
    }
  }, [initialCapital, strategy, selectedToken, mode])

  // Generate mock trade history
  const tradeHistory = useMemo(() => {
    return Array.from({ length: 30 }, (_, i) => {
      const isWin = Math.random() > 0.45
      const entryPrice = Math.random() * 100 + 50
      const exitPrice = isWin
        ? entryPrice * (1 + Math.random() * 0.15)
        : entryPrice * (1 - Math.random() * 0.08)
      const pnl = ((exitPrice - entryPrice) / entryPrice * 100)

      return {
        id: i + 1,
        type: Math.random() > 0.5 ? 'long' : 'short',
        entryDate: `2024-${String(Math.floor(i / 3) + 1).padStart(2, '0')}-${String(Math.floor(Math.random() * 28) + 1).padStart(2, '0')}`,
        exitDate: `2024-${String(Math.floor(i / 3) + 1).padStart(2, '0')}-${String(Math.floor(Math.random() * 28) + 1).padStart(2, '0')}`,
        entryPrice: entryPrice.toFixed(2),
        exitPrice: exitPrice.toFixed(2),
        size: Math.floor(Math.random() * 1000) + 100,
        pnl: pnl.toFixed(2),
        pnlUsd: (pnl * initialCapital / 100).toFixed(2),
        isWin,
        signal: strategies.find(s => s.id === strategy)?.name || 'Custom',
        duration: `${Math.floor(Math.random() * 48) + 1}h`
      }
    })
  }, [strategy, initialCapital])

  // Generate equity curve data
  const equityCurve = useMemo(() => {
    let equity = initialCapital
    return Array.from({ length: 100 }, (_, i) => {
      equity = equity * (1 + (Math.random() - 0.48) * 0.05)
      return {
        day: i + 1,
        equity: equity,
        drawdown: Math.max(0, initialCapital - equity) / initialCapital * 100
      }
    })
  }, [initialCapital, strategy])

  // Monthly returns
  const monthlyReturns = useMemo(() => {
    return Array.from({ length: 12 }, (_, i) => ({
      month: ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'][i],
      return: (Math.random() - 0.4) * 30
    }))
  }, [strategy])

  useEffect(() => {
    if (isRunning && progress < 100) {
      const interval = setInterval(() => {
        setProgress(prev => {
          if (prev >= 100) {
            setIsRunning(false)
            setMode('results')
            return 100
          }
          return prev + speed
        })
      }, 50)
      return () => clearInterval(interval)
    }
  }, [isRunning, progress, speed])

  const handleStartBacktest = () => {
    setProgress(0)
    setIsRunning(true)
    setMode('running')
  }

  const handleStopBacktest = () => {
    setIsRunning(false)
  }

  const formatCurrency = (value) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 0,
      maximumFractionDigits: 0
    }).format(value)
  }

  return (
    <div className="bg-[#0a0e14] rounded-xl border border-white/10 p-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <PlayCircle className="w-6 h-6 text-green-400" />
          <h2 className="text-xl font-bold text-white">Backtest Simulator</h2>
        </div>
        <div className="flex items-center gap-2">
          {mode !== 'setup' && (
            <button
              onClick={() => { setMode('setup'); setProgress(0); setIsRunning(false); }}
              className="px-4 py-2 bg-white/5 border border-white/10 rounded-lg text-gray-400 hover:bg-white/10 text-sm"
            >
              Reset
            </button>
          )}
        </div>
      </div>

      {/* Setup Mode */}
      {mode === 'setup' && (
        <div className="space-y-6">
          {/* Strategy Selection */}
          <div className="bg-white/5 rounded-lg p-4 border border-white/10">
            <h3 className="text-white font-medium mb-4 flex items-center gap-2">
              <Target className="w-4 h-4 text-purple-400" />
              Select Strategy
            </h3>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              {strategies.map(strat => (
                <button
                  key={strat.id}
                  onClick={() => setStrategy(strat.id)}
                  className={`p-3 rounded-lg text-left transition-colors ${
                    strategy === strat.id
                      ? 'bg-green-500/20 border border-green-500/30'
                      : 'bg-white/5 border border-white/10 hover:bg-white/10'
                  }`}
                >
                  <div className={`font-medium text-sm ${strategy === strat.id ? 'text-green-400' : 'text-white'}`}>
                    {strat.name}
                  </div>
                  <div className="text-xs text-gray-500 mt-1">{strat.description}</div>
                </button>
              ))}
            </div>
          </div>

          {/* Configuration */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Token & Timeframe */}
            <div className="bg-white/5 rounded-lg p-4 border border-white/10">
              <h3 className="text-white font-medium mb-4 flex items-center gap-2">
                <Settings className="w-4 h-4 text-blue-400" />
                Configuration
              </h3>
              <div className="space-y-4">
                <div>
                  <label className="text-gray-400 text-sm block mb-2">Token</label>
                  <select
                    value={selectedToken}
                    onChange={(e) => setSelectedToken(e.target.value)}
                    className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white"
                  >
                    {tokens.map(token => (
                      <option key={token} value={token}>{token}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="text-gray-400 text-sm block mb-2">Timeframe</label>
                  <select
                    value={timeframe}
                    onChange={(e) => setTimeframe(e.target.value)}
                    className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white"
                  >
                    {timeframes.map(tf => (
                      <option key={tf.id} value={tf.id}>{tf.name}</option>
                    ))}
                  </select>
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="text-gray-400 text-sm block mb-2">Start Date</label>
                    <input
                      type="date"
                      value={startDate}
                      onChange={(e) => setStartDate(e.target.value)}
                      className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white"
                    />
                  </div>
                  <div>
                    <label className="text-gray-400 text-sm block mb-2">End Date</label>
                    <input
                      type="date"
                      value={endDate}
                      onChange={(e) => setEndDate(e.target.value)}
                      className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white"
                    />
                  </div>
                </div>
                <div>
                  <label className="text-gray-400 text-sm block mb-2">Initial Capital ($)</label>
                  <input
                    type="number"
                    value={initialCapital}
                    onChange={(e) => setInitialCapital(Number(e.target.value))}
                    className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white"
                  />
                </div>
              </div>
            </div>

            {/* Strategy Parameters */}
            <div className="bg-white/5 rounded-lg p-4 border border-white/10">
              <h3 className="text-white font-medium mb-4 flex items-center gap-2">
                <Zap className="w-4 h-4 text-yellow-400" />
                Strategy Parameters
              </h3>
              <div className="space-y-4">
                {strategy === 'sma_cross' && (
                  <>
                    <div>
                      <label className="text-gray-400 text-sm block mb-2">Short SMA Period</label>
                      <input
                        type="number"
                        value={strategyParams.sma_short}
                        onChange={(e) => setStrategyParams({...strategyParams, sma_short: Number(e.target.value)})}
                        className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white"
                      />
                    </div>
                    <div>
                      <label className="text-gray-400 text-sm block mb-2">Long SMA Period</label>
                      <input
                        type="number"
                        value={strategyParams.sma_long}
                        onChange={(e) => setStrategyParams({...strategyParams, sma_long: Number(e.target.value)})}
                        className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white"
                      />
                    </div>
                  </>
                )}
                {strategy === 'rsi_oversold' && (
                  <>
                    <div>
                      <label className="text-gray-400 text-sm block mb-2">RSI Period</label>
                      <input
                        type="number"
                        value={strategyParams.rsi_period}
                        onChange={(e) => setStrategyParams({...strategyParams, rsi_period: Number(e.target.value)})}
                        className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white"
                      />
                    </div>
                    <div>
                      <label className="text-gray-400 text-sm block mb-2">Oversold Level</label>
                      <input
                        type="number"
                        value={strategyParams.rsi_oversold}
                        onChange={(e) => setStrategyParams({...strategyParams, rsi_oversold: Number(e.target.value)})}
                        className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white"
                      />
                    </div>
                    <div>
                      <label className="text-gray-400 text-sm block mb-2">Overbought Level</label>
                      <input
                        type="number"
                        value={strategyParams.rsi_overbought}
                        onChange={(e) => setStrategyParams({...strategyParams, rsi_overbought: Number(e.target.value)})}
                        className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white"
                      />
                    </div>
                  </>
                )}
                <div>
                  <label className="text-gray-400 text-sm block mb-2">Stop Loss (%)</label>
                  <input
                    type="number"
                    value={strategyParams.stop_loss}
                    onChange={(e) => setStrategyParams({...strategyParams, stop_loss: Number(e.target.value)})}
                    className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white"
                  />
                </div>
                <div>
                  <label className="text-gray-400 text-sm block mb-2">Take Profit (%)</label>
                  <input
                    type="number"
                    value={strategyParams.take_profit}
                    onChange={(e) => setStrategyParams({...strategyParams, take_profit: Number(e.target.value)})}
                    className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white"
                  />
                </div>
                <div>
                  <label className="text-gray-400 text-sm block mb-2">Position Size (%)</label>
                  <input
                    type="number"
                    value={strategyParams.position_size}
                    onChange={(e) => setStrategyParams({...strategyParams, position_size: Number(e.target.value)})}
                    className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white"
                  />
                </div>
              </div>
            </div>
          </div>

          {/* Start Button */}
          <button
            onClick={handleStartBacktest}
            className="w-full py-3 bg-green-500 hover:bg-green-600 text-white rounded-lg font-medium flex items-center justify-center gap-2 transition-colors"
          >
            <PlayCircle className="w-5 h-5" />
            Start Backtest
          </button>
        </div>
      )}

      {/* Running Mode */}
      {mode === 'running' && (
        <div className="space-y-6">
          <div className="bg-white/5 rounded-lg p-6 border border-white/10">
            <div className="flex items-center justify-between mb-4">
              <div className="text-white font-medium">Running Backtest...</div>
              <div className="text-green-400">{progress.toFixed(0)}%</div>
            </div>
            <div className="h-3 bg-white/10 rounded-full overflow-hidden">
              <div
                className="h-full bg-gradient-to-r from-green-500 to-emerald-400 transition-all duration-100"
                style={{ width: `${progress}%` }}
              />
            </div>
            <div className="flex items-center justify-between mt-4">
              <div className="text-gray-400 text-sm">
                {strategies.find(s => s.id === strategy)?.name} on {selectedToken}
              </div>
              <div className="flex items-center gap-2">
                <span className="text-gray-400 text-sm">Speed:</span>
                {[1, 2, 5, 10].map(s => (
                  <button
                    key={s}
                    onClick={() => setSpeed(s)}
                    className={`px-2 py-1 rounded text-xs ${
                      speed === s ? 'bg-green-500/20 text-green-400' : 'bg-white/5 text-gray-400'
                    }`}
                  >
                    {s}x
                  </button>
                ))}
              </div>
            </div>
            <div className="flex justify-center gap-4 mt-6">
              <button
                onClick={handleStopBacktest}
                className="px-6 py-2 bg-red-500/20 text-red-400 rounded-lg flex items-center gap-2 hover:bg-red-500/30"
              >
                <PauseCircle className="w-4 h-4" />
                Stop
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Results Mode */}
      {mode === 'results' && (
        <div className="space-y-6">
          {/* Key Metrics */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className={`rounded-lg p-4 border ${parseFloat(backtestResults.totalReturn) >= 0 ? 'bg-green-500/10 border-green-500/20' : 'bg-red-500/10 border-red-500/20'}`}>
              <div className="text-gray-400 text-sm mb-1">Total Return</div>
              <div className={`text-2xl font-bold ${parseFloat(backtestResults.totalReturn) >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                {parseFloat(backtestResults.totalReturn) >= 0 ? '+' : ''}{backtestResults.totalReturn}%
              </div>
              <div className="text-sm text-gray-500">{formatCurrency(backtestResults.finalCapital)}</div>
            </div>
            <div className="bg-white/5 rounded-lg p-4 border border-white/10">
              <div className="text-gray-400 text-sm mb-1">Win Rate</div>
              <div className="text-2xl font-bold text-white">{backtestResults.winRate}%</div>
              <div className="text-sm text-gray-500">{backtestResults.winningTrades}W / {backtestResults.losingTrades}L</div>
            </div>
            <div className="bg-white/5 rounded-lg p-4 border border-white/10">
              <div className="text-gray-400 text-sm mb-1">Profit Factor</div>
              <div className={`text-2xl font-bold ${parseFloat(backtestResults.profitFactor) >= 1.5 ? 'text-green-400' : parseFloat(backtestResults.profitFactor) >= 1 ? 'text-yellow-400' : 'text-red-400'}`}>
                {backtestResults.profitFactor}
              </div>
              <div className="text-sm text-gray-500">Gross profit / loss</div>
            </div>
            <div className="bg-red-500/10 rounded-lg p-4 border border-red-500/20">
              <div className="text-gray-400 text-sm mb-1">Max Drawdown</div>
              <div className="text-2xl font-bold text-red-400">-{backtestResults.maxDrawdown}%</div>
              <div className="text-sm text-gray-500">Peak to trough</div>
            </div>
          </div>

          {/* Secondary Metrics */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="bg-white/5 rounded-lg p-4 border border-white/10">
              <div className="text-gray-400 text-sm mb-1">Sharpe Ratio</div>
              <div className="text-xl font-bold text-white">{backtestResults.sharpeRatio}</div>
            </div>
            <div className="bg-white/5 rounded-lg p-4 border border-white/10">
              <div className="text-gray-400 text-sm mb-1">Sortino Ratio</div>
              <div className="text-xl font-bold text-white">{backtestResults.sortinoRatio}</div>
            </div>
            <div className="bg-white/5 rounded-lg p-4 border border-white/10">
              <div className="text-gray-400 text-sm mb-1">Calmar Ratio</div>
              <div className="text-xl font-bold text-white">{backtestResults.calmarRatio}</div>
            </div>
            <div className="bg-white/5 rounded-lg p-4 border border-white/10">
              <div className="text-gray-400 text-sm mb-1">Total Trades</div>
              <div className="text-xl font-bold text-white">{backtestResults.totalTrades}</div>
            </div>
          </div>

          {/* Trade Statistics */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="bg-white/5 rounded-lg p-4 border border-white/10">
              <h3 className="text-white font-medium mb-4">Trade Statistics</h3>
              <div className="space-y-3">
                <div className="flex justify-between">
                  <span className="text-gray-400">Avg Winning Trade</span>
                  <span className="text-green-400">+{backtestResults.avgWin}%</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-400">Avg Losing Trade</span>
                  <span className="text-red-400">-{backtestResults.avgLoss}%</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-400">Best Trade</span>
                  <span className="text-green-400">+{backtestResults.bestTrade}%</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-400">Worst Trade</span>
                  <span className="text-red-400">{backtestResults.worstTrade}%</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-400">Avg Hold Time</span>
                  <span className="text-white">{backtestResults.avgHoldTime}h</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-400">Max Consecutive Wins</span>
                  <span className="text-green-400">{backtestResults.consecutiveWins}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-400">Max Consecutive Losses</span>
                  <span className="text-red-400">{backtestResults.consecutiveLosses}</span>
                </div>
              </div>
            </div>

            {/* Monthly Returns */}
            <div className="bg-white/5 rounded-lg p-4 border border-white/10">
              <h3 className="text-white font-medium mb-4">Monthly Returns</h3>
              <div className="grid grid-cols-6 gap-2">
                {monthlyReturns.map((month, i) => (
                  <div key={i} className="text-center">
                    <div className="text-xs text-gray-500 mb-1">{month.month}</div>
                    <div className={`text-xs font-medium ${month.return >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                      {month.return >= 0 ? '+' : ''}{month.return.toFixed(1)}%
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Equity Curve Visualization */}
          <div className="bg-white/5 rounded-lg p-4 border border-white/10">
            <h3 className="text-white font-medium mb-4">Equity Curve</h3>
            <div className="h-48 flex items-end gap-0.5">
              {equityCurve.map((point, i) => {
                const height = ((point.equity - initialCapital * 0.5) / (initialCapital * 1.5)) * 100
                return (
                  <div
                    key={i}
                    className={`flex-1 rounded-t ${point.equity >= initialCapital ? 'bg-green-500/60' : 'bg-red-500/60'}`}
                    style={{ height: `${Math.max(5, Math.min(100, height))}%` }}
                  />
                )
              })}
            </div>
            <div className="flex justify-between mt-2 text-xs text-gray-500">
              <span>Start</span>
              <span>End</span>
            </div>
          </div>

          {/* Trade History */}
          <div className="bg-white/5 rounded-lg p-4 border border-white/10">
            <h3 className="text-white font-medium mb-4">Recent Trades</h3>
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="text-left text-gray-400 text-sm border-b border-white/10">
                    <th className="pb-3 pr-4">#</th>
                    <th className="pb-3 pr-4">Type</th>
                    <th className="pb-3 pr-4">Entry</th>
                    <th className="pb-3 pr-4">Exit</th>
                    <th className="pb-3 pr-4 text-right">P&L</th>
                    <th className="pb-3 text-right">Duration</th>
                  </tr>
                </thead>
                <tbody>
                  {tradeHistory.slice(0, 10).map(trade => (
                    <tr key={trade.id} className="border-b border-white/5">
                      <td className="py-2 pr-4 text-gray-400">{trade.id}</td>
                      <td className="py-2 pr-4">
                        <span className={`px-2 py-0.5 rounded text-xs ${trade.type === 'long' ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'}`}>
                          {trade.type.toUpperCase()}
                        </span>
                      </td>
                      <td className="py-2 pr-4 text-white">${trade.entryPrice}</td>
                      <td className="py-2 pr-4 text-white">${trade.exitPrice}</td>
                      <td className={`py-2 pr-4 text-right ${trade.isWin ? 'text-green-400' : 'text-red-400'}`}>
                        {trade.isWin ? '+' : ''}{trade.pnl}%
                      </td>
                      <td className="py-2 text-right text-gray-400">{trade.duration}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Export Button */}
          <div className="flex justify-end">
            <button className="px-4 py-2 bg-white/5 border border-white/10 rounded-lg text-gray-400 hover:bg-white/10 flex items-center gap-2 text-sm">
              <Download className="w-4 h-4" />
              Export Results
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

export default BacktestSimulator
