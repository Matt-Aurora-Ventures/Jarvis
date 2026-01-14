import React, { useState, useCallback, useMemo } from 'react'
import {
  Plus, Trash2, Save, Play, Pause, Copy, ChevronDown, ChevronRight,
  TrendingUp, TrendingDown, Activity, Target, Shield, Zap, Settings,
  ArrowRight, AlertCircle, CheckCircle, X, Edit2, Eye, EyeOff, RefreshCw
} from 'lucide-react'

/**
 * StrategyBuilder - Visual trading strategy builder
 *
 * Features:
 * - Drag-and-drop condition builder
 * - Entry/Exit rule configuration
 * - Risk management settings
 * - Indicator configuration
 * - Strategy testing mode
 * - Save/Load strategies
 */

// Available condition types
const CONDITION_TYPES = {
  PRICE: {
    id: 'price',
    label: 'Price',
    icon: TrendingUp,
    color: 'cyan',
    operators: ['above', 'below', 'crosses_above', 'crosses_below'],
    valueType: 'number',
  },
  PERCENT_CHANGE: {
    id: 'percent_change',
    label: 'Price Change %',
    icon: Activity,
    color: 'purple',
    operators: ['greater_than', 'less_than'],
    valueType: 'percentage',
  },
  VOLUME: {
    id: 'volume',
    label: 'Volume',
    icon: Activity,
    color: 'blue',
    operators: ['above_avg', 'below_avg', 'spike'],
    valueType: 'multiplier',
  },
  RSI: {
    id: 'rsi',
    label: 'RSI',
    icon: Activity,
    color: 'yellow',
    operators: ['above', 'below', 'crosses_above', 'crosses_below'],
    valueType: 'number',
    range: [0, 100],
  },
  MA_CROSS: {
    id: 'ma_cross',
    label: 'MA Crossover',
    icon: TrendingUp,
    color: 'green',
    operators: ['bullish', 'bearish'],
    valueType: 'periods',
  },
  LIQUIDITY: {
    id: 'liquidity',
    label: 'Liquidity',
    icon: Activity,
    color: 'indigo',
    operators: ['above', 'below'],
    valueType: 'currency',
  },
  TIME: {
    id: 'time',
    label: 'Time',
    icon: Activity,
    color: 'orange',
    operators: ['after', 'before', 'between'],
    valueType: 'time',
  },
}

// Available actions
const ACTION_TYPES = {
  BUY: { id: 'buy', label: 'Buy', color: 'green', icon: TrendingUp },
  SELL: { id: 'sell', label: 'Sell', color: 'red', icon: TrendingDown },
  ALERT: { id: 'alert', label: 'Send Alert', color: 'yellow', icon: AlertCircle },
  STOP_LOSS: { id: 'stop_loss', label: 'Set Stop Loss', color: 'red', icon: Shield },
  TAKE_PROFIT: { id: 'take_profit', label: 'Set Take Profit', color: 'green', icon: Target },
}

// Default strategy template
const DEFAULT_STRATEGY = {
  id: '',
  name: 'New Strategy',
  description: '',
  enabled: false,
  entryRules: [],
  exitRules: [],
  riskManagement: {
    maxPositionSize: 10, // percent of portfolio
    stopLoss: 5, // percent
    takeProfit: 15, // percent
    trailingStop: false,
    trailingStopPercent: 3,
    maxDailyLoss: 20, // percent
    maxOpenPositions: 3,
  },
  notifications: {
    onEntry: true,
    onExit: true,
    onStopLoss: true,
    onTakeProfit: true,
  },
  createdAt: null,
  updatedAt: null,
}

/**
 * ConditionBuilder - Build a single condition
 */
function ConditionBuilder({ condition, onChange, onRemove, index }) {
  const conditionType = CONDITION_TYPES[condition.type?.toUpperCase()] || CONDITION_TYPES.PRICE

  return (
    <div className="flex items-center gap-2 p-3 bg-gray-800/50 rounded-lg border border-gray-700 group">
      {/* Index indicator */}
      <div className="w-6 h-6 rounded-full bg-gray-700 flex items-center justify-center text-xs text-gray-400">
        {index + 1}
      </div>

      {/* Condition type selector */}
      <select
        value={condition.type}
        onChange={(e) => onChange({ ...condition, type: e.target.value })}
        className="bg-gray-900 border border-gray-700 rounded px-2 py-1.5 text-sm text-white"
      >
        {Object.values(CONDITION_TYPES).map(type => (
          <option key={type.id} value={type.id}>{type.label}</option>
        ))}
      </select>

      {/* Operator selector */}
      <select
        value={condition.operator}
        onChange={(e) => onChange({ ...condition, operator: e.target.value })}
        className="bg-gray-900 border border-gray-700 rounded px-2 py-1.5 text-sm text-white"
      >
        {conditionType.operators.map(op => (
          <option key={op} value={op}>
            {op.replace(/_/g, ' ')}
          </option>
        ))}
      </select>

      {/* Value input */}
      <div className="flex items-center gap-1">
        <input
          type="number"
          value={condition.value}
          onChange={(e) => onChange({ ...condition, value: parseFloat(e.target.value) || 0 })}
          className="w-24 bg-gray-900 border border-gray-700 rounded px-2 py-1.5 text-sm text-white"
          placeholder="Value"
        />
        {conditionType.valueType === 'percentage' && (
          <span className="text-gray-400 text-sm">%</span>
        )}
        {conditionType.valueType === 'currency' && (
          <span className="text-gray-400 text-sm">$</span>
        )}
        {conditionType.valueType === 'multiplier' && (
          <span className="text-gray-400 text-sm">x</span>
        )}
      </div>

      {/* Timeframe (for price conditions) */}
      {['price', 'percent_change', 'volume'].includes(condition.type) && (
        <select
          value={condition.timeframe || '1m'}
          onChange={(e) => onChange({ ...condition, timeframe: e.target.value })}
          className="bg-gray-900 border border-gray-700 rounded px-2 py-1.5 text-sm text-white"
        >
          <option value="1m">1 min</option>
          <option value="5m">5 min</option>
          <option value="15m">15 min</option>
          <option value="1h">1 hour</option>
          <option value="4h">4 hour</option>
          <option value="1d">1 day</option>
        </select>
      )}

      {/* Remove button */}
      <button
        onClick={onRemove}
        className="p-1.5 rounded hover:bg-red-500/20 text-gray-400 hover:text-red-400 opacity-0 group-hover:opacity-100 transition-all"
      >
        <Trash2 className="w-4 h-4" />
      </button>
    </div>
  )
}

/**
 * RuleGroup - Group of conditions with AND/OR logic
 */
function RuleGroup({
  title,
  rules,
  onRulesChange,
  logic,
  onLogicChange,
  actionType,
  onActionChange,
  color = 'cyan',
}) {
  const [isExpanded, setIsExpanded] = useState(true)

  const addCondition = useCallback(() => {
    onRulesChange([
      ...rules,
      {
        type: 'price',
        operator: 'above',
        value: 0,
        timeframe: '1m',
      }
    ])
  }, [rules, onRulesChange])

  const updateCondition = useCallback((index, updatedCondition) => {
    const newRules = [...rules]
    newRules[index] = updatedCondition
    onRulesChange(newRules)
  }, [rules, onRulesChange])

  const removeCondition = useCallback((index) => {
    onRulesChange(rules.filter((_, i) => i !== index))
  }, [rules, onRulesChange])

  const colorClasses = {
    green: 'border-green-500/30 bg-green-500/5',
    red: 'border-red-500/30 bg-red-500/5',
    cyan: 'border-cyan-500/30 bg-cyan-500/5',
    yellow: 'border-yellow-500/30 bg-yellow-500/5',
  }

  return (
    <div className={`rounded-lg border ${colorClasses[color]} p-4`}>
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <button
          onClick={() => setIsExpanded(!isExpanded)}
          className="flex items-center gap-2"
        >
          {isExpanded ? (
            <ChevronDown className="w-4 h-4 text-gray-400" />
          ) : (
            <ChevronRight className="w-4 h-4 text-gray-400" />
          )}
          <span className={`font-medium text-${color}-400`}>{title}</span>
          <span className="text-xs text-gray-500">({rules.length} conditions)</span>
        </button>

        <div className="flex items-center gap-2">
          {/* Logic selector */}
          <div className="flex items-center gap-1 bg-gray-800 rounded-lg p-0.5">
            <button
              onClick={() => onLogicChange('AND')}
              className={`px-2 py-1 text-xs rounded ${
                logic === 'AND' ? 'bg-gray-700 text-white' : 'text-gray-400'
              }`}
            >
              AND
            </button>
            <button
              onClick={() => onLogicChange('OR')}
              className={`px-2 py-1 text-xs rounded ${
                logic === 'OR' ? 'bg-gray-700 text-white' : 'text-gray-400'
              }`}
            >
              OR
            </button>
          </div>

          {/* Action selector */}
          <ArrowRight className="w-4 h-4 text-gray-500" />
          <select
            value={actionType}
            onChange={(e) => onActionChange(e.target.value)}
            className={`bg-gray-900 border border-gray-700 rounded px-2 py-1 text-sm text-${ACTION_TYPES[actionType.toUpperCase()]?.color || 'white'}-400`}
          >
            {Object.values(ACTION_TYPES).map(action => (
              <option key={action.id} value={action.id}>{action.label}</option>
            ))}
          </select>
        </div>
      </div>

      {/* Conditions */}
      {isExpanded && (
        <div className="space-y-2">
          {rules.map((condition, index) => (
            <div key={index} className="flex items-center gap-2">
              {index > 0 && (
                <span className="w-12 text-center text-xs text-gray-500">{logic}</span>
              )}
              <div className={index > 0 ? 'flex-1' : 'flex-1 ml-14'}>
                <ConditionBuilder
                  condition={condition}
                  onChange={(updated) => updateCondition(index, updated)}
                  onRemove={() => removeCondition(index)}
                  index={index}
                />
              </div>
            </div>
          ))}

          {/* Add condition button */}
          <button
            onClick={addCondition}
            className="flex items-center gap-2 w-full p-2 border border-dashed border-gray-700 rounded-lg text-gray-400 hover:text-white hover:border-gray-600 transition-colors"
          >
            <Plus className="w-4 h-4" />
            <span className="text-sm">Add Condition</span>
          </button>
        </div>
      )}
    </div>
  )
}

/**
 * RiskManagementPanel - Configure risk settings
 */
function RiskManagementPanel({ settings, onChange }) {
  return (
    <div className="bg-gray-900/50 rounded-lg border border-gray-800 p-4">
      <div className="flex items-center gap-2 mb-4">
        <Shield className="w-4 h-4 text-yellow-400" />
        <span className="font-medium text-white">Risk Management</span>
      </div>

      <div className="grid grid-cols-2 gap-4">
        {/* Position Size */}
        <div>
          <label className="block text-xs text-gray-400 mb-1">Max Position Size</label>
          <div className="flex items-center gap-2">
            <input
              type="number"
              value={settings.maxPositionSize}
              onChange={(e) => onChange({ ...settings, maxPositionSize: parseFloat(e.target.value) || 0 })}
              className="flex-1 bg-gray-800 border border-gray-700 rounded px-3 py-2 text-sm text-white"
              min="1"
              max="100"
            />
            <span className="text-gray-400 text-sm">%</span>
          </div>
        </div>

        {/* Stop Loss */}
        <div>
          <label className="block text-xs text-gray-400 mb-1">Stop Loss</label>
          <div className="flex items-center gap-2">
            <input
              type="number"
              value={settings.stopLoss}
              onChange={(e) => onChange({ ...settings, stopLoss: parseFloat(e.target.value) || 0 })}
              className="flex-1 bg-gray-800 border border-gray-700 rounded px-3 py-2 text-sm text-white"
              min="0.1"
              max="100"
              step="0.1"
            />
            <span className="text-gray-400 text-sm">%</span>
          </div>
        </div>

        {/* Take Profit */}
        <div>
          <label className="block text-xs text-gray-400 mb-1">Take Profit</label>
          <div className="flex items-center gap-2">
            <input
              type="number"
              value={settings.takeProfit}
              onChange={(e) => onChange({ ...settings, takeProfit: parseFloat(e.target.value) || 0 })}
              className="flex-1 bg-gray-800 border border-gray-700 rounded px-3 py-2 text-sm text-white"
              min="0.1"
              max="1000"
              step="0.5"
            />
            <span className="text-gray-400 text-sm">%</span>
          </div>
        </div>

        {/* Max Daily Loss */}
        <div>
          <label className="block text-xs text-gray-400 mb-1">Max Daily Loss</label>
          <div className="flex items-center gap-2">
            <input
              type="number"
              value={settings.maxDailyLoss}
              onChange={(e) => onChange({ ...settings, maxDailyLoss: parseFloat(e.target.value) || 0 })}
              className="flex-1 bg-gray-800 border border-gray-700 rounded px-3 py-2 text-sm text-white"
              min="1"
              max="100"
            />
            <span className="text-gray-400 text-sm">%</span>
          </div>
        </div>

        {/* Max Open Positions */}
        <div>
          <label className="block text-xs text-gray-400 mb-1">Max Open Positions</label>
          <input
            type="number"
            value={settings.maxOpenPositions}
            onChange={(e) => onChange({ ...settings, maxOpenPositions: parseInt(e.target.value) || 1 })}
            className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-sm text-white"
            min="1"
            max="100"
          />
        </div>

        {/* Trailing Stop */}
        <div>
          <label className="block text-xs text-gray-400 mb-1">Trailing Stop</label>
          <div className="flex items-center gap-2">
            <button
              onClick={() => onChange({ ...settings, trailingStop: !settings.trailingStop })}
              className={`px-3 py-2 rounded text-sm ${
                settings.trailingStop ? 'bg-green-500/20 text-green-400' : 'bg-gray-800 text-gray-400'
              }`}
            >
              {settings.trailingStop ? 'Enabled' : 'Disabled'}
            </button>
            {settings.trailingStop && (
              <div className="flex items-center gap-1">
                <input
                  type="number"
                  value={settings.trailingStopPercent}
                  onChange={(e) => onChange({ ...settings, trailingStopPercent: parseFloat(e.target.value) || 0 })}
                  className="w-16 bg-gray-800 border border-gray-700 rounded px-2 py-2 text-sm text-white"
                  min="0.1"
                  max="50"
                  step="0.1"
                />
                <span className="text-gray-400 text-sm">%</span>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

/**
 * Main StrategyBuilder Component
 */
export function StrategyBuilder({
  initialStrategy = DEFAULT_STRATEGY,
  onSave,
  onTest,
  onClose,
  className = '',
}) {
  const [strategy, setStrategy] = useState({
    ...DEFAULT_STRATEGY,
    ...initialStrategy,
    id: initialStrategy.id || `strategy_${Date.now()}`,
    createdAt: initialStrategy.createdAt || new Date().toISOString(),
  })

  const [isTesting, setIsTesting] = useState(false)
  const [testResults, setTestResults] = useState(null)
  const [activeTab, setActiveTab] = useState('rules') // rules, risk, notifications

  // Update strategy fields
  const updateStrategy = useCallback((updates) => {
    setStrategy(prev => ({
      ...prev,
      ...updates,
      updatedAt: new Date().toISOString(),
    }))
  }, [])

  // Handle save
  const handleSave = useCallback(() => {
    if (onSave) {
      onSave(strategy)
    }
  }, [strategy, onSave])

  // Handle test
  const handleTest = useCallback(async () => {
    setIsTesting(true)
    setTestResults(null)

    try {
      if (onTest) {
        const results = await onTest(strategy)
        setTestResults(results)
      }
    } catch (err) {
      setTestResults({ error: err.message })
    } finally {
      setIsTesting(false)
    }
  }, [strategy, onTest])

  // Validate strategy
  const validation = useMemo(() => {
    const errors = []
    const warnings = []

    if (!strategy.name.trim()) {
      errors.push('Strategy name is required')
    }

    if (strategy.entryRules.length === 0) {
      errors.push('At least one entry condition is required')
    }

    if (strategy.exitRules.length === 0) {
      warnings.push('No exit conditions defined - trades may run indefinitely')
    }

    if (strategy.riskManagement.stopLoss === 0) {
      warnings.push('No stop loss configured - high risk')
    }

    return { errors, warnings, isValid: errors.length === 0 }
  }, [strategy])

  return (
    <div className={`bg-gray-900 rounded-xl border border-gray-800 flex flex-col max-h-[90vh] ${className}`}>
      {/* Header */}
      <div className="flex items-center justify-between px-6 py-4 border-b border-gray-800">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-purple-500/10 rounded-lg">
            <Zap className="w-5 h-5 text-purple-400" />
          </div>
          <div>
            <input
              type="text"
              value={strategy.name}
              onChange={(e) => updateStrategy({ name: e.target.value })}
              className="bg-transparent border-none text-lg font-semibold text-white focus:outline-none"
              placeholder="Strategy Name"
            />
            <input
              type="text"
              value={strategy.description}
              onChange={(e) => updateStrategy({ description: e.target.value })}
              className="block w-full bg-transparent border-none text-sm text-gray-400 focus:outline-none"
              placeholder="Add description..."
            />
          </div>
        </div>

        <div className="flex items-center gap-2">
          {/* Enable/Disable toggle */}
          <button
            onClick={() => updateStrategy({ enabled: !strategy.enabled })}
            className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm ${
              strategy.enabled
                ? 'bg-green-500/20 text-green-400'
                : 'bg-gray-800 text-gray-400'
            }`}
          >
            {strategy.enabled ? (
              <>
                <Eye className="w-4 h-4" />
                Active
              </>
            ) : (
              <>
                <EyeOff className="w-4 h-4" />
                Inactive
              </>
            )}
          </button>

          {/* Test button */}
          <button
            onClick={handleTest}
            disabled={isTesting || !validation.isValid}
            className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-cyan-500/20 text-cyan-400 hover:bg-cyan-500/30 disabled:opacity-50"
          >
            {isTesting ? (
              <RefreshCw className="w-4 h-4 animate-spin" />
            ) : (
              <Play className="w-4 h-4" />
            )}
            Test
          </button>

          {/* Save button */}
          <button
            onClick={handleSave}
            disabled={!validation.isValid}
            className="flex items-center gap-2 px-4 py-1.5 rounded-lg bg-purple-500 text-white hover:bg-purple-600 disabled:opacity-50"
          >
            <Save className="w-4 h-4" />
            Save
          </button>

          {/* Close button */}
          {onClose && (
            <button
              onClick={onClose}
              className="p-2 rounded-lg hover:bg-gray-800 text-gray-400"
            >
              <X className="w-4 h-4" />
            </button>
          )}
        </div>
      </div>

      {/* Validation messages */}
      {(validation.errors.length > 0 || validation.warnings.length > 0) && (
        <div className="px-6 py-2 border-b border-gray-800 space-y-1">
          {validation.errors.map((error, i) => (
            <div key={`error-${i}`} className="flex items-center gap-2 text-red-400 text-sm">
              <AlertCircle className="w-4 h-4" />
              {error}
            </div>
          ))}
          {validation.warnings.map((warning, i) => (
            <div key={`warning-${i}`} className="flex items-center gap-2 text-yellow-400 text-sm">
              <AlertCircle className="w-4 h-4" />
              {warning}
            </div>
          ))}
        </div>
      )}

      {/* Tabs */}
      <div className="flex gap-1 px-6 py-2 border-b border-gray-800">
        {[
          { id: 'rules', label: 'Trading Rules', icon: Activity },
          { id: 'risk', label: 'Risk Management', icon: Shield },
          { id: 'notifications', label: 'Notifications', icon: AlertCircle },
        ].map(tab => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm transition-colors ${
              activeTab === tab.id
                ? 'bg-gray-800 text-white'
                : 'text-gray-400 hover:text-white'
            }`}
          >
            <tab.icon className="w-4 h-4" />
            {tab.label}
          </button>
        ))}
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-6">
        {activeTab === 'rules' && (
          <div className="space-y-6">
            {/* Entry Rules */}
            <RuleGroup
              title="Entry Conditions"
              rules={strategy.entryRules}
              onRulesChange={(rules) => updateStrategy({ entryRules: rules })}
              logic={strategy.entryLogic || 'AND'}
              onLogicChange={(logic) => updateStrategy({ entryLogic: logic })}
              actionType={strategy.entryAction || 'buy'}
              onActionChange={(action) => updateStrategy({ entryAction: action })}
              color="green"
            />

            {/* Exit Rules */}
            <RuleGroup
              title="Exit Conditions"
              rules={strategy.exitRules}
              onRulesChange={(rules) => updateStrategy({ exitRules: rules })}
              logic={strategy.exitLogic || 'OR'}
              onLogicChange={(logic) => updateStrategy({ exitLogic: logic })}
              actionType={strategy.exitAction || 'sell'}
              onActionChange={(action) => updateStrategy({ exitAction: action })}
              color="red"
            />
          </div>
        )}

        {activeTab === 'risk' && (
          <RiskManagementPanel
            settings={strategy.riskManagement}
            onChange={(riskManagement) => updateStrategy({ riskManagement })}
          />
        )}

        {activeTab === 'notifications' && (
          <div className="bg-gray-900/50 rounded-lg border border-gray-800 p-4">
            <div className="flex items-center gap-2 mb-4">
              <AlertCircle className="w-4 h-4 text-yellow-400" />
              <span className="font-medium text-white">Notification Settings</span>
            </div>

            <div className="space-y-3">
              {[
                { key: 'onEntry', label: 'Entry Signal Triggered' },
                { key: 'onExit', label: 'Exit Signal Triggered' },
                { key: 'onStopLoss', label: 'Stop Loss Hit' },
                { key: 'onTakeProfit', label: 'Take Profit Hit' },
              ].map(item => (
                <label key={item.key} className="flex items-center justify-between">
                  <span className="text-sm text-gray-300">{item.label}</span>
                  <button
                    onClick={() => updateStrategy({
                      notifications: {
                        ...strategy.notifications,
                        [item.key]: !strategy.notifications[item.key],
                      }
                    })}
                    className={`relative w-10 h-6 rounded-full transition-colors ${
                      strategy.notifications[item.key] ? 'bg-green-500' : 'bg-gray-700'
                    }`}
                  >
                    <span
                      className={`absolute top-1 w-4 h-4 rounded-full bg-white transition-transform ${
                        strategy.notifications[item.key] ? 'left-5' : 'left-1'
                      }`}
                    />
                  </button>
                </label>
              ))}
            </div>
          </div>
        )}

        {/* Test Results */}
        {testResults && (
          <div className="mt-6 bg-gray-800/50 rounded-lg border border-gray-700 p-4">
            <div className="flex items-center gap-2 mb-3">
              {testResults.error ? (
                <AlertCircle className="w-4 h-4 text-red-400" />
              ) : (
                <CheckCircle className="w-4 h-4 text-green-400" />
              )}
              <span className="font-medium text-white">Test Results</span>
            </div>

            {testResults.error ? (
              <p className="text-red-400 text-sm">{testResults.error}</p>
            ) : (
              <div className="grid grid-cols-3 gap-4 text-sm">
                <div>
                  <div className="text-gray-400">Win Rate</div>
                  <div className="text-white font-medium">{testResults.winRate || '-'}%</div>
                </div>
                <div>
                  <div className="text-gray-400">Total Trades</div>
                  <div className="text-white font-medium">{testResults.totalTrades || '-'}</div>
                </div>
                <div>
                  <div className="text-gray-400">Profit Factor</div>
                  <div className="text-white font-medium">{testResults.profitFactor || '-'}</div>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

/**
 * StrategyCard - Compact strategy display card
 */
export function StrategyCard({
  strategy,
  onEdit,
  onToggle,
  onDelete,
  onDuplicate,
  className = '',
}) {
  return (
    <div className={`bg-gray-900/50 rounded-lg border border-gray-800 p-4 ${className}`}>
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-3">
          <div className={`p-2 rounded-lg ${strategy.enabled ? 'bg-green-500/10' : 'bg-gray-800'}`}>
            <Zap className={`w-5 h-5 ${strategy.enabled ? 'text-green-400' : 'text-gray-500'}`} />
          </div>
          <div>
            <h3 className="font-medium text-white">{strategy.name}</h3>
            <p className="text-sm text-gray-400">{strategy.description || 'No description'}</p>
          </div>
        </div>

        <div className="flex items-center gap-1">
          <button
            onClick={() => onToggle?.(strategy)}
            className={`p-1.5 rounded hover:bg-gray-800 ${
              strategy.enabled ? 'text-green-400' : 'text-gray-500'
            }`}
          >
            {strategy.enabled ? <Eye className="w-4 h-4" /> : <EyeOff className="w-4 h-4" />}
          </button>
          <button
            onClick={() => onEdit?.(strategy)}
            className="p-1.5 rounded hover:bg-gray-800 text-gray-400"
          >
            <Edit2 className="w-4 h-4" />
          </button>
          <button
            onClick={() => onDuplicate?.(strategy)}
            className="p-1.5 rounded hover:bg-gray-800 text-gray-400"
          >
            <Copy className="w-4 h-4" />
          </button>
          <button
            onClick={() => onDelete?.(strategy)}
            className="p-1.5 rounded hover:bg-red-500/20 text-gray-400 hover:text-red-400"
          >
            <Trash2 className="w-4 h-4" />
          </button>
        </div>
      </div>

      <div className="flex items-center gap-4 mt-4 pt-4 border-t border-gray-800 text-xs text-gray-400">
        <div className="flex items-center gap-1">
          <TrendingUp className="w-3 h-3 text-green-400" />
          <span>{strategy.entryRules?.length || 0} entry rules</span>
        </div>
        <div className="flex items-center gap-1">
          <TrendingDown className="w-3 h-3 text-red-400" />
          <span>{strategy.exitRules?.length || 0} exit rules</span>
        </div>
        <div className="flex items-center gap-1">
          <Shield className="w-3 h-3 text-yellow-400" />
          <span>{strategy.riskManagement?.stopLoss || 0}% SL</span>
        </div>
      </div>
    </div>
  )
}

/**
 * StrategyList - List of all strategies
 */
export function StrategyList({
  strategies = [],
  onEdit,
  onToggle,
  onDelete,
  onDuplicate,
  onCreate,
  className = '',
}) {
  return (
    <div className={className}>
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold text-white">Trading Strategies</h2>
        <button
          onClick={onCreate}
          className="flex items-center gap-2 px-3 py-1.5 bg-purple-500 text-white rounded-lg text-sm hover:bg-purple-600"
        >
          <Plus className="w-4 h-4" />
          New Strategy
        </button>
      </div>

      {strategies.length === 0 ? (
        <div className="text-center py-12">
          <Zap className="w-12 h-12 text-gray-600 mx-auto mb-4" />
          <h3 className="text-lg font-medium text-gray-400 mb-2">No Strategies Yet</h3>
          <p className="text-sm text-gray-500 mb-4">Create your first automated trading strategy</p>
          <button
            onClick={onCreate}
            className="inline-flex items-center gap-2 px-4 py-2 bg-purple-500 text-white rounded-lg hover:bg-purple-600"
          >
            <Plus className="w-4 h-4" />
            Create Strategy
          </button>
        </div>
      ) : (
        <div className="space-y-3">
          {strategies.map(strategy => (
            <StrategyCard
              key={strategy.id}
              strategy={strategy}
              onEdit={onEdit}
              onToggle={onToggle}
              onDelete={onDelete}
              onDuplicate={onDuplicate}
            />
          ))}
        </div>
      )}
    </div>
  )
}

export default StrategyBuilder
