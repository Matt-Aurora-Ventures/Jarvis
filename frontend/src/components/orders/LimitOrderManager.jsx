import React, { useState, useMemo, useEffect, useCallback } from 'react'
import {
  ShoppingCart, Plus, Search, Filter, Trash2, Edit3, Clock, Check, X,
  TrendingUp, TrendingDown, AlertTriangle, RefreshCw, DollarSign,
  Target, Shield, ArrowUpDown, ChevronDown, MoreVertical, Eye,
  Activity, Zap, Ban, Copy, ExternalLink, Settings, BarChart2
} from 'lucide-react'

const ORDER_TYPES = [
  { value: 'limit', label: 'Limit', description: 'Buy/sell at a specific price' },
  { value: 'stop_loss', label: 'Stop Loss', description: 'Sell when price drops below threshold' },
  { value: 'take_profit', label: 'Take Profit', description: 'Sell when price rises above threshold' },
  { value: 'oco', label: 'OCO', description: 'One-Cancels-Other order pair' },
  { value: 'trailing_stop', label: 'Trailing Stop', description: 'Dynamic stop that follows price' }
]

const SUPPORTED_TOKENS = [
  { symbol: 'BTC', name: 'Bitcoin', price: 67500 },
  { symbol: 'ETH', name: 'Ethereum', price: 3450 },
  { symbol: 'SOL', name: 'Solana', price: 145 },
  { symbol: 'BNB', name: 'BNB Chain', price: 580 },
  { symbol: 'XRP', name: 'Ripple', price: 0.52 },
  { symbol: 'ADA', name: 'Cardano', price: 0.45 },
  { symbol: 'AVAX', name: 'Avalanche', price: 35 },
  { symbol: 'DOT', name: 'Polkadot', price: 7.2 },
  { symbol: 'MATIC', name: 'Polygon', price: 0.72 },
  { symbol: 'LINK', name: 'Chainlink', price: 14.5 },
  { symbol: 'UNI', name: 'Uniswap', price: 9.8 },
  { symbol: 'AAVE', name: 'Aave', price: 168 },
  { symbol: 'ARB', name: 'Arbitrum', price: 1.15 },
  { symbol: 'OP', name: 'Optimism', price: 2.45 }
]

const EXCHANGES = ['Binance', 'Coinbase', 'Kraken', 'KuCoin', 'Bybit', 'OKX']

const TIME_IN_FORCE = [
  { value: 'gtc', label: 'Good Till Cancelled' },
  { value: 'ioc', label: 'Immediate or Cancel' },
  { value: 'fok', label: 'Fill or Kill' },
  { value: 'day', label: 'Day Order' }
]

export function LimitOrderManager() {
  const [activeTab, setActiveTab] = useState('active')
  const [orders, setOrders] = useState([])
  const [orderHistory, setOrderHistory] = useState([])
  const [showCreateOrder, setShowCreateOrder] = useState(false)
  const [selectedOrder, setSelectedOrder] = useState(null)
  const [filterToken, setFilterToken] = useState('all')
  const [filterType, setFilterType] = useState('all')
  const [searchQuery, setSearchQuery] = useState('')
  const [currentPrices, setCurrentPrices] = useState({})

  // New order form
  const [newOrder, setNewOrder] = useState({
    type: 'limit',
    side: 'buy',
    token: 'BTC',
    amount: '',
    price: '',
    stopPrice: '',
    takeProfitPrice: '',
    trailingPercent: '',
    timeInForce: 'gtc',
    exchange: 'Binance'
  })

  // Generate mock orders
  useEffect(() => {
    const mockOrders = [
      { id: 1, type: 'limit', side: 'buy', token: 'BTC', amount: 0.5, price: 65000, status: 'active', exchange: 'Binance', created: new Date(Date.now() - 2 * 60 * 60 * 1000), timeInForce: 'gtc', filled: 0 },
      { id: 2, type: 'limit', side: 'sell', token: 'ETH', amount: 5, price: 3600, status: 'active', exchange: 'Coinbase', created: new Date(Date.now() - 5 * 60 * 60 * 1000), timeInForce: 'gtc', filled: 0 },
      { id: 3, type: 'stop_loss', side: 'sell', token: 'SOL', amount: 50, price: 130, stopPrice: 135, status: 'active', exchange: 'Binance', created: new Date(Date.now() - 1 * 60 * 60 * 1000), timeInForce: 'gtc', filled: 0 },
      { id: 4, type: 'take_profit', side: 'sell', token: 'BTC', amount: 0.25, price: 75000, status: 'active', exchange: 'Kraken', created: new Date(Date.now() - 12 * 60 * 60 * 1000), timeInForce: 'gtc', filled: 0 },
      { id: 5, type: 'oco', side: 'sell', token: 'ETH', amount: 2, price: 3800, stopPrice: 3200, status: 'active', exchange: 'Binance', created: new Date(Date.now() - 24 * 60 * 60 * 1000), timeInForce: 'gtc', filled: 0 },
      { id: 6, type: 'trailing_stop', side: 'sell', token: 'SOL', amount: 100, trailingPercent: 5, status: 'active', exchange: 'Bybit', created: new Date(Date.now() - 3 * 60 * 60 * 1000), timeInForce: 'gtc', filled: 0 },
      { id: 7, type: 'limit', side: 'buy', token: 'LINK', amount: 100, price: 13, status: 'active', exchange: 'KuCoin', created: new Date(Date.now() - 6 * 60 * 60 * 1000), timeInForce: 'day', filled: 0 }
    ]

    const mockHistory = [
      { id: 101, type: 'limit', side: 'buy', token: 'BTC', amount: 0.3, price: 64000, status: 'filled', exchange: 'Binance', created: new Date(Date.now() - 48 * 60 * 60 * 1000), filled: 0.3, filledAt: new Date(Date.now() - 46 * 60 * 60 * 1000) },
      { id: 102, type: 'limit', side: 'sell', token: 'ETH', amount: 10, price: 3500, status: 'filled', exchange: 'Coinbase', created: new Date(Date.now() - 72 * 60 * 60 * 1000), filled: 10, filledAt: new Date(Date.now() - 70 * 60 * 60 * 1000) },
      { id: 103, type: 'stop_loss', side: 'sell', token: 'SOL', amount: 25, price: 120, status: 'triggered', exchange: 'Binance', created: new Date(Date.now() - 96 * 60 * 60 * 1000), filled: 25, filledAt: new Date(Date.now() - 94 * 60 * 60 * 1000) },
      { id: 104, type: 'limit', side: 'buy', token: 'AVAX', amount: 50, price: 30, status: 'cancelled', exchange: 'Kraken', created: new Date(Date.now() - 120 * 60 * 60 * 1000), filled: 0, cancelledAt: new Date(Date.now() - 100 * 60 * 60 * 1000) },
      { id: 105, type: 'limit', side: 'buy', token: 'DOT', amount: 200, price: 6.5, status: 'partially_filled', exchange: 'KuCoin', created: new Date(Date.now() - 150 * 60 * 60 * 1000), filled: 150, expiredAt: new Date(Date.now() - 140 * 60 * 60 * 1000) }
    ]

    setOrders(mockOrders)
    setOrderHistory(mockHistory)
  }, [])

  // Update current prices
  useEffect(() => {
    const updatePrices = () => {
      const prices = {}
      SUPPORTED_TOKENS.forEach(token => {
        prices[token.symbol] = token.price * (1 + (Math.random() - 0.5) * 0.02)
      })
      setCurrentPrices(prices)
    }

    updatePrices()
    const interval = setInterval(updatePrices, 5000)
    return () => clearInterval(interval)
  }, [])

  const filteredOrders = useMemo(() => {
    let filtered = activeTab === 'active' ? orders : orderHistory

    if (filterToken !== 'all') {
      filtered = filtered.filter(o => o.token === filterToken)
    }

    if (filterType !== 'all') {
      filtered = filtered.filter(o => o.type === filterType)
    }

    if (searchQuery) {
      filtered = filtered.filter(o =>
        o.token.toLowerCase().includes(searchQuery.toLowerCase()) ||
        o.exchange.toLowerCase().includes(searchQuery.toLowerCase())
      )
    }

    return filtered
  }, [orders, orderHistory, activeTab, filterToken, filterType, searchQuery])

  const orderStats = useMemo(() => {
    const activeOrders = orders.length
    const totalValue = orders.reduce((sum, o) => {
      const price = o.price || currentPrices[o.token] || 0
      return sum + (o.amount * price)
    }, 0)
    const buyOrders = orders.filter(o => o.side === 'buy').length
    const sellOrders = orders.filter(o => o.side === 'sell').length

    return { activeOrders, totalValue, buyOrders, sellOrders }
  }, [orders, currentPrices])

  const formatPrice = (price) => {
    if (!price) return '-'
    if (price < 1) return `$${price.toFixed(4)}`
    if (price < 100) return `$${price.toFixed(2)}`
    return `$${price.toLocaleString(undefined, { maximumFractionDigits: 0 })}`
  }

  const formatDate = (date) => {
    if (!date) return '-'
    return new Date(date).toLocaleString(undefined, {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    })
  }

  const getOrderTypeIcon = (type) => {
    switch (type) {
      case 'limit': return <Target className="w-4 h-4" />
      case 'stop_loss': return <Shield className="w-4 h-4 text-red-400" />
      case 'take_profit': return <TrendingUp className="w-4 h-4 text-green-400" />
      case 'oco': return <ArrowUpDown className="w-4 h-4 text-purple-400" />
      case 'trailing_stop': return <Activity className="w-4 h-4 text-yellow-400" />
      default: return <Target className="w-4 h-4" />
    }
  }

  const getStatusBadge = (status) => {
    switch (status) {
      case 'active':
        return <span className="px-2 py-1 bg-blue-500/20 text-blue-400 rounded text-xs">Active</span>
      case 'filled':
        return <span className="px-2 py-1 bg-green-500/20 text-green-400 rounded text-xs">Filled</span>
      case 'partially_filled':
        return <span className="px-2 py-1 bg-yellow-500/20 text-yellow-400 rounded text-xs">Partial</span>
      case 'cancelled':
        return <span className="px-2 py-1 bg-red-500/20 text-red-400 rounded text-xs">Cancelled</span>
      case 'triggered':
        return <span className="px-2 py-1 bg-purple-500/20 text-purple-400 rounded text-xs">Triggered</span>
      case 'expired':
        return <span className="px-2 py-1 bg-white/20 text-white/60 rounded text-xs">Expired</span>
      default:
        return <span className="px-2 py-1 bg-white/20 rounded text-xs">{status}</span>
    }
  }

  const calculateDistance = (order) => {
    const currentPrice = currentPrices[order.token]
    if (!currentPrice || !order.price) return null

    const distance = ((order.price - currentPrice) / currentPrice) * 100
    return distance
  }

  const createOrder = () => {
    const order = {
      id: Date.now(),
      ...newOrder,
      amount: parseFloat(newOrder.amount),
      price: parseFloat(newOrder.price) || undefined,
      stopPrice: parseFloat(newOrder.stopPrice) || undefined,
      trailingPercent: parseFloat(newOrder.trailingPercent) || undefined,
      status: 'active',
      created: new Date(),
      filled: 0
    }

    setOrders(prev => [order, ...prev])
    setShowCreateOrder(false)
    setNewOrder({
      type: 'limit',
      side: 'buy',
      token: 'BTC',
      amount: '',
      price: '',
      stopPrice: '',
      takeProfitPrice: '',
      trailingPercent: '',
      timeInForce: 'gtc',
      exchange: 'Binance'
    })
  }

  const cancelOrder = (orderId) => {
    const order = orders.find(o => o.id === orderId)
    if (order) {
      setOrders(prev => prev.filter(o => o.id !== orderId))
      setOrderHistory(prev => [{ ...order, status: 'cancelled', cancelledAt: new Date() }, ...prev])
    }
  }

  const cancelAllOrders = () => {
    const cancelled = orders.map(o => ({ ...o, status: 'cancelled', cancelledAt: new Date() }))
    setOrderHistory(prev => [...cancelled, ...prev])
    setOrders([])
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <ShoppingCart className="w-6 h-6 text-blue-400" />
          <h2 className="text-xl font-bold">Limit Order Manager</h2>
        </div>
        <div className="flex items-center gap-2">
          {orders.length > 0 && (
            <button
              onClick={cancelAllOrders}
              className="px-3 py-2 bg-red-500/20 text-red-400 rounded-lg hover:bg-red-500/30 transition flex items-center gap-2"
            >
              <Ban className="w-4 h-4" />
              Cancel All
            </button>
          )}
          <button
            onClick={() => setShowCreateOrder(true)}
            className="px-4 py-2 bg-blue-500/20 text-blue-400 rounded-lg hover:bg-blue-500/30 transition flex items-center gap-2"
          >
            <Plus className="w-4 h-4" />
            New Order
          </button>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-white/5 border border-white/10 rounded-xl p-4">
          <div className="text-white/60 text-sm mb-1">Active Orders</div>
          <div className="text-2xl font-bold">{orderStats.activeOrders}</div>
        </div>
        <div className="bg-white/5 border border-white/10 rounded-xl p-4">
          <div className="text-white/60 text-sm mb-1">Total Value</div>
          <div className="text-2xl font-bold">${orderStats.totalValue.toLocaleString(undefined, { maximumFractionDigits: 0 })}</div>
        </div>
        <div className="bg-white/5 border border-white/10 rounded-xl p-4">
          <div className="text-white/60 text-sm mb-1">Buy Orders</div>
          <div className="text-2xl font-bold text-green-400">{orderStats.buyOrders}</div>
        </div>
        <div className="bg-white/5 border border-white/10 rounded-xl p-4">
          <div className="text-white/60 text-sm mb-1">Sell Orders</div>
          <div className="text-2xl font-bold text-red-400">{orderStats.sellOrders}</div>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex items-center gap-4 border-b border-white/10">
        <button
          onClick={() => setActiveTab('active')}
          className={`pb-3 px-4 transition ${
            activeTab === 'active'
              ? 'text-blue-400 border-b-2 border-blue-400'
              : 'text-white/60 hover:text-white'
          }`}
        >
          Active Orders ({orders.length})
        </button>
        <button
          onClick={() => setActiveTab('history')}
          className={`pb-3 px-4 transition ${
            activeTab === 'history'
              ? 'text-blue-400 border-b-2 border-blue-400'
              : 'text-white/60 hover:text-white'
          }`}
        >
          Order History ({orderHistory.length})
        </button>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-4">
        <div className="flex-1 min-w-[200px] relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-white/40" />
          <input
            type="text"
            placeholder="Search orders..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-10 pr-4 py-2 bg-white/5 border border-white/10 rounded-lg focus:outline-none focus:border-white/20"
          />
        </div>

        <select
          value={filterToken}
          onChange={(e) => setFilterToken(e.target.value)}
          className="px-4 py-2 bg-white/5 border border-white/10 rounded-lg focus:outline-none"
        >
          <option value="all" className="bg-[#0a0e14]">All Tokens</option>
          {SUPPORTED_TOKENS.map(token => (
            <option key={token.symbol} value={token.symbol} className="bg-[#0a0e14]">{token.symbol}</option>
          ))}
        </select>

        <select
          value={filterType}
          onChange={(e) => setFilterType(e.target.value)}
          className="px-4 py-2 bg-white/5 border border-white/10 rounded-lg focus:outline-none"
        >
          <option value="all" className="bg-[#0a0e14]">All Types</option>
          {ORDER_TYPES.map(type => (
            <option key={type.value} value={type.value} className="bg-[#0a0e14]">{type.label}</option>
          ))}
        </select>
      </div>

      {/* Orders Table */}
      <div className="bg-white/5 border border-white/10 rounded-xl overflow-hidden">
        <table className="w-full">
          <thead>
            <tr className="border-b border-white/10 text-left text-sm text-white/60">
              <th className="px-4 py-3">Type</th>
              <th className="px-4 py-3">Side</th>
              <th className="px-4 py-3">Token</th>
              <th className="px-4 py-3">Amount</th>
              <th className="px-4 py-3">Price</th>
              <th className="px-4 py-3">Current</th>
              <th className="px-4 py-3">Distance</th>
              <th className="px-4 py-3">Exchange</th>
              <th className="px-4 py-3">Status</th>
              <th className="px-4 py-3">Created</th>
              {activeTab === 'active' && <th className="px-4 py-3">Actions</th>}
            </tr>
          </thead>
          <tbody>
            {filteredOrders.map((order) => {
              const distance = calculateDistance(order)
              return (
                <tr key={order.id} className="border-b border-white/5 hover:bg-white/5">
                  <td className="px-4 py-4">
                    <div className="flex items-center gap-2">
                      {getOrderTypeIcon(order.type)}
                      <span className="text-sm">{ORDER_TYPES.find(t => t.value === order.type)?.label}</span>
                    </div>
                  </td>
                  <td className="px-4 py-4">
                    <span className={`font-medium ${order.side === 'buy' ? 'text-green-400' : 'text-red-400'}`}>
                      {order.side.toUpperCase()}
                    </span>
                  </td>
                  <td className="px-4 py-4">
                    <div className="flex items-center gap-2">
                      <div className="w-6 h-6 rounded-full bg-gradient-to-br from-blue-500 to-purple-500 flex items-center justify-center text-xs font-bold">
                        {order.token.slice(0, 2)}
                      </div>
                      <span>{order.token}</span>
                    </div>
                  </td>
                  <td className="px-4 py-4 font-mono">{order.amount}</td>
                  <td className="px-4 py-4">
                    <div>
                      <div className="font-mono">{formatPrice(order.price)}</div>
                      {order.stopPrice && (
                        <div className="text-xs text-white/40">Stop: {formatPrice(order.stopPrice)}</div>
                      )}
                      {order.trailingPercent && (
                        <div className="text-xs text-yellow-400">Trail: {order.trailingPercent}%</div>
                      )}
                    </div>
                  </td>
                  <td className="px-4 py-4 font-mono text-white/60">
                    {formatPrice(currentPrices[order.token])}
                  </td>
                  <td className="px-4 py-4">
                    {distance !== null && (
                      <span className={`text-sm ${distance > 0 ? 'text-green-400' : 'text-red-400'}`}>
                        {distance > 0 ? '+' : ''}{distance.toFixed(2)}%
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-4 text-white/60 text-sm">{order.exchange}</td>
                  <td className="px-4 py-4">{getStatusBadge(order.status)}</td>
                  <td className="px-4 py-4 text-white/40 text-sm">{formatDate(order.created)}</td>
                  {activeTab === 'active' && (
                    <td className="px-4 py-4">
                      <div className="flex items-center gap-2">
                        <button
                          onClick={() => setSelectedOrder(order)}
                          className="p-2 rounded-lg hover:bg-white/10 transition"
                          title="View details"
                        >
                          <Eye className="w-4 h-4 text-white/40" />
                        </button>
                        <button
                          onClick={() => cancelOrder(order.id)}
                          className="p-2 rounded-lg hover:bg-red-500/20 hover:text-red-400 transition"
                          title="Cancel order"
                        >
                          <X className="w-4 h-4 text-white/40" />
                        </button>
                      </div>
                    </td>
                  )}
                </tr>
              )
            })}
          </tbody>
        </table>

        {filteredOrders.length === 0 && (
          <div className="text-center py-12 text-white/40">
            <ShoppingCart className="w-12 h-12 mx-auto mb-4 opacity-50" />
            <p>{activeTab === 'active' ? 'No active orders' : 'No order history'}</p>
            {activeTab === 'active' && (
              <button
                onClick={() => setShowCreateOrder(true)}
                className="mt-4 px-4 py-2 bg-blue-500/20 text-blue-400 rounded-lg hover:bg-blue-500/30 transition"
              >
                Create Your First Order
              </button>
            )}
          </div>
        )}
      </div>

      {/* Create Order Modal */}
      {showCreateOrder && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-[#0a0e14] border border-white/10 rounded-xl p-6 w-full max-w-lg max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between mb-6">
              <h3 className="text-lg font-bold">Create New Order</h3>
              <button onClick={() => setShowCreateOrder(false)} className="p-2 hover:bg-white/10 rounded-lg">
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="space-y-4">
              {/* Order Type */}
              <div>
                <label className="block text-sm text-white/60 mb-2">Order Type</label>
                <div className="grid grid-cols-2 gap-2">
                  {ORDER_TYPES.map(type => (
                    <button
                      key={type.value}
                      onClick={() => setNewOrder(prev => ({ ...prev, type: type.value }))}
                      className={`p-3 rounded-lg text-left transition ${
                        newOrder.type === type.value
                          ? 'bg-blue-500/20 border border-blue-500/50'
                          : 'bg-white/5 border border-white/10 hover:bg-white/10'
                      }`}
                    >
                      <div className="flex items-center gap-2 mb-1">
                        {getOrderTypeIcon(type.value)}
                        <span className="font-medium">{type.label}</span>
                      </div>
                      <div className="text-xs text-white/40">{type.description}</div>
                    </button>
                  ))}
                </div>
              </div>

              {/* Side */}
              <div>
                <label className="block text-sm text-white/60 mb-2">Side</label>
                <div className="grid grid-cols-2 gap-2">
                  <button
                    onClick={() => setNewOrder(prev => ({ ...prev, side: 'buy' }))}
                    className={`py-3 rounded-lg font-medium transition ${
                      newOrder.side === 'buy'
                        ? 'bg-green-500/20 text-green-400 border border-green-500/50'
                        : 'bg-white/5 border border-white/10 hover:bg-white/10'
                    }`}
                  >
                    BUY
                  </button>
                  <button
                    onClick={() => setNewOrder(prev => ({ ...prev, side: 'sell' }))}
                    className={`py-3 rounded-lg font-medium transition ${
                      newOrder.side === 'sell'
                        ? 'bg-red-500/20 text-red-400 border border-red-500/50'
                        : 'bg-white/5 border border-white/10 hover:bg-white/10'
                    }`}
                  >
                    SELL
                  </button>
                </div>
              </div>

              {/* Token & Exchange */}
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm text-white/60 mb-2">Token</label>
                  <select
                    value={newOrder.token}
                    onChange={(e) => setNewOrder(prev => ({ ...prev, token: e.target.value }))}
                    className="w-full px-4 py-2 bg-white/5 border border-white/10 rounded-lg focus:outline-none"
                  >
                    {SUPPORTED_TOKENS.map(token => (
                      <option key={token.symbol} value={token.symbol} className="bg-[#0a0e14]">
                        {token.symbol} - {token.name}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-sm text-white/60 mb-2">Exchange</label>
                  <select
                    value={newOrder.exchange}
                    onChange={(e) => setNewOrder(prev => ({ ...prev, exchange: e.target.value }))}
                    className="w-full px-4 py-2 bg-white/5 border border-white/10 rounded-lg focus:outline-none"
                  >
                    {EXCHANGES.map(ex => (
                      <option key={ex} value={ex} className="bg-[#0a0e14]">{ex}</option>
                    ))}
                  </select>
                </div>
              </div>

              {/* Amount */}
              <div>
                <label className="block text-sm text-white/60 mb-2">Amount</label>
                <input
                  type="number"
                  value={newOrder.amount}
                  onChange={(e) => setNewOrder(prev => ({ ...prev, amount: e.target.value }))}
                  placeholder={`Amount in ${newOrder.token}`}
                  className="w-full px-4 py-2 bg-white/5 border border-white/10 rounded-lg focus:outline-none"
                />
              </div>

              {/* Price Fields */}
              {(newOrder.type === 'limit' || newOrder.type === 'take_profit') && (
                <div>
                  <label className="block text-sm text-white/60 mb-2">
                    {newOrder.type === 'take_profit' ? 'Take Profit Price' : 'Limit Price'}
                  </label>
                  <div className="relative">
                    <DollarSign className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-white/40" />
                    <input
                      type="number"
                      value={newOrder.price}
                      onChange={(e) => setNewOrder(prev => ({ ...prev, price: e.target.value }))}
                      placeholder="0.00"
                      className="w-full pl-10 pr-4 py-2 bg-white/5 border border-white/10 rounded-lg focus:outline-none"
                    />
                  </div>
                  <div className="text-xs text-white/40 mt-1">
                    Current: {formatPrice(currentPrices[newOrder.token])}
                  </div>
                </div>
              )}

              {(newOrder.type === 'stop_loss' || newOrder.type === 'oco') && (
                <div>
                  <label className="block text-sm text-white/60 mb-2">Stop Price</label>
                  <div className="relative">
                    <Shield className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-red-400" />
                    <input
                      type="number"
                      value={newOrder.stopPrice}
                      onChange={(e) => setNewOrder(prev => ({ ...prev, stopPrice: e.target.value }))}
                      placeholder="0.00"
                      className="w-full pl-10 pr-4 py-2 bg-white/5 border border-white/10 rounded-lg focus:outline-none"
                    />
                  </div>
                </div>
              )}

              {newOrder.type === 'oco' && (
                <div>
                  <label className="block text-sm text-white/60 mb-2">Take Profit Price</label>
                  <div className="relative">
                    <TrendingUp className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-green-400" />
                    <input
                      type="number"
                      value={newOrder.price}
                      onChange={(e) => setNewOrder(prev => ({ ...prev, price: e.target.value }))}
                      placeholder="0.00"
                      className="w-full pl-10 pr-4 py-2 bg-white/5 border border-white/10 rounded-lg focus:outline-none"
                    />
                  </div>
                </div>
              )}

              {newOrder.type === 'trailing_stop' && (
                <div>
                  <label className="block text-sm text-white/60 mb-2">Trailing Percentage</label>
                  <div className="relative">
                    <Activity className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-yellow-400" />
                    <input
                      type="number"
                      value={newOrder.trailingPercent}
                      onChange={(e) => setNewOrder(prev => ({ ...prev, trailingPercent: e.target.value }))}
                      placeholder="5"
                      className="w-full pl-10 pr-4 py-2 bg-white/5 border border-white/10 rounded-lg focus:outline-none"
                    />
                  </div>
                </div>
              )}

              {/* Time in Force */}
              <div>
                <label className="block text-sm text-white/60 mb-2">Time in Force</label>
                <select
                  value={newOrder.timeInForce}
                  onChange={(e) => setNewOrder(prev => ({ ...prev, timeInForce: e.target.value }))}
                  className="w-full px-4 py-2 bg-white/5 border border-white/10 rounded-lg focus:outline-none"
                >
                  {TIME_IN_FORCE.map(tif => (
                    <option key={tif.value} value={tif.value} className="bg-[#0a0e14]">{tif.label}</option>
                  ))}
                </select>
              </div>

              {/* Order Summary */}
              <div className="bg-white/5 border border-white/10 rounded-lg p-4">
                <div className="text-sm text-white/60 mb-2">Order Summary</div>
                <div className="space-y-1 text-sm">
                  <div className="flex justify-between">
                    <span className="text-white/40">Type:</span>
                    <span>{ORDER_TYPES.find(t => t.value === newOrder.type)?.label}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-white/40">Side:</span>
                    <span className={newOrder.side === 'buy' ? 'text-green-400' : 'text-red-400'}>
                      {newOrder.side.toUpperCase()}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-white/40">Amount:</span>
                    <span>{newOrder.amount || '0'} {newOrder.token}</span>
                  </div>
                  {newOrder.price && (
                    <div className="flex justify-between">
                      <span className="text-white/40">Price:</span>
                      <span>{formatPrice(parseFloat(newOrder.price))}</span>
                    </div>
                  )}
                  {newOrder.amount && newOrder.price && (
                    <div className="flex justify-between font-medium pt-2 border-t border-white/10">
                      <span className="text-white/40">Total:</span>
                      <span>{formatPrice(parseFloat(newOrder.amount) * parseFloat(newOrder.price))}</span>
                    </div>
                  )}
                </div>
              </div>

              <button
                onClick={createOrder}
                disabled={!newOrder.amount || (newOrder.type !== 'trailing_stop' && !newOrder.price && !newOrder.stopPrice)}
                className={`w-full py-3 rounded-lg font-medium transition ${
                  newOrder.side === 'buy'
                    ? 'bg-green-500 text-white hover:bg-green-600'
                    : 'bg-red-500 text-white hover:bg-red-600'
                } disabled:opacity-50 disabled:cursor-not-allowed`}
              >
                {newOrder.side === 'buy' ? 'Place Buy Order' : 'Place Sell Order'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Order Detail Modal */}
      {selectedOrder && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-[#0a0e14] border border-white/10 rounded-xl p-6 w-full max-w-md">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-bold">Order Details</h3>
              <button onClick={() => setSelectedOrder(null)} className="p-2 hover:bg-white/10 rounded-lg">
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="space-y-4">
              <div className="flex items-center gap-3">
                {getOrderTypeIcon(selectedOrder.type)}
                <div>
                  <div className="font-medium">{ORDER_TYPES.find(t => t.value === selectedOrder.type)?.label}</div>
                  <div className="text-sm text-white/40">{selectedOrder.exchange}</div>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="bg-white/5 rounded-lg p-3">
                  <div className="text-xs text-white/40">Side</div>
                  <div className={`font-medium ${selectedOrder.side === 'buy' ? 'text-green-400' : 'text-red-400'}`}>
                    {selectedOrder.side.toUpperCase()}
                  </div>
                </div>
                <div className="bg-white/5 rounded-lg p-3">
                  <div className="text-xs text-white/40">Token</div>
                  <div className="font-medium">{selectedOrder.token}</div>
                </div>
                <div className="bg-white/5 rounded-lg p-3">
                  <div className="text-xs text-white/40">Amount</div>
                  <div className="font-medium">{selectedOrder.amount}</div>
                </div>
                <div className="bg-white/5 rounded-lg p-3">
                  <div className="text-xs text-white/40">Price</div>
                  <div className="font-medium">{formatPrice(selectedOrder.price)}</div>
                </div>
              </div>

              <div className="bg-white/5 rounded-lg p-3">
                <div className="text-xs text-white/40 mb-1">Current Market Price</div>
                <div className="text-xl font-bold">{formatPrice(currentPrices[selectedOrder.token])}</div>
                {calculateDistance(selectedOrder) !== null && (
                  <div className={`text-sm ${calculateDistance(selectedOrder) > 0 ? 'text-green-400' : 'text-red-400'}`}>
                    {calculateDistance(selectedOrder) > 0 ? '+' : ''}{calculateDistance(selectedOrder).toFixed(2)}% from target
                  </div>
                )}
              </div>

              <div className="flex gap-2">
                <button
                  onClick={() => {
                    cancelOrder(selectedOrder.id)
                    setSelectedOrder(null)
                  }}
                  className="flex-1 py-2 bg-red-500/20 text-red-400 rounded-lg hover:bg-red-500/30 transition"
                >
                  Cancel Order
                </button>
                <button
                  onClick={() => setSelectedOrder(null)}
                  className="flex-1 py-2 bg-white/5 rounded-lg hover:bg-white/10 transition"
                >
                  Close
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default LimitOrderManager
