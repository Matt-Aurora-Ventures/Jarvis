import React, { useEffect, useState, useRef } from 'react'
import {
    Wallet, TrendingUp, Activity, Send, Bot, Cpu, RefreshCw, Play, Pause,
    DollarSign, BarChart2, Clock, Zap, AlertTriangle, MessageSquare,
    Target, XCircle, Search, Shield, ExternalLink, Home, Settings,
    LineChart, Wrench, ChevronRight, ArrowUpRight, ArrowDownRight, Layers
} from 'lucide-react'
import TradingChart from '../components/TradingChart'
import OrderPanel from '../components/OrderPanel'

const API_BASE = ''

// Default token (SOL)
const DEFAULT_TOKEN = {
    mint: 'So11111111111111111111111111111111111111112',
    symbol: 'SOL',
    name: 'Solana'
}

// =============================================================================
// V2 Components - Ultra-Clean White Knight Aesthetic
// =============================================================================

// Top Navigation
function TopNav({ walletData }) {
    return (
        <div className="top-nav">
            <div className="nav-brand">
                <Bot size={24} />
                <span>Jarvis Trading</span>
            </div>

            <div className="nav-search">
                <input type="text" placeholder="Search tokens, addresses..." />
            </div>

            <div className="nav-actions">
                <div className="price-ticker">
                    <div className="ticker-item">
                        <span className="ticker-symbol">SOL</span>
                        <span className="ticker-price">${walletData?.sol_price?.toFixed(2) || '---'}</span>
                    </div>
                </div>
                <button className="btn btn-ghost">
                    <Wallet size={18} />
                    {walletData?.balance_sol?.toFixed(3) || '0.000'} SOL
                </button>
            </div>
        </div>
    )
}

// Sidebar Navigation
function Sidebar({ activeView, setActiveView }) {
    const navItems = [
        { id: 'overview', icon: Home, label: 'Overview' },
        { id: 'trading', icon: LineChart, label: 'Trading' },
        { id: 'tools', icon: Wrench, label: 'Tools' },
        { id: 'analytics', icon: BarChart2, label: 'Analytics' },
        { id: 'settings', icon: Settings, label: 'Settings' },
    ]

    return (
        <div className="sidebar">
            {navItems.map(item => (
                <div
                    key={item.id}
                    className={`sidebar-item ${activeView === item.id ? 'active' : ''}`}
                    onClick={() => setActiveView(item.id)}
                    title={item.label}
                >
                    <item.icon size={20} />
                </div>
            ))}
        </div>
    )
}

// Stats Grid
function StatsGrid({ walletData, sniperData }) {
    const stats = [
        {
            label: 'Portfolio Value',
            value: `$${walletData?.balance_usd?.toFixed(2) || '0.00'}`,
            change: '+0.00%',
            positive: true
        },
        {
            label: 'Win Rate',
            value: sniperData?.win_rate || '0%',
            change: sniperData?.win_rate || '0%',
            positive: parseFloat(sniperData?.win_rate) >= 50
        },
        {
            label: 'Total Trades',
            value: sniperData?.total_trades || 0,
            change: 'All time',
            positive: true
        },
        {
            label: 'Total P&L',
            value: `$${sniperData?.state?.total_pnl_usd?.toFixed(2) || '0.00'}`,
            change: sniperData?.state?.total_pnl_usd >= 0 ? '+' : '',
            positive: sniperData?.state?.total_pnl_usd >= 0
        },
    ]

    return (
        <div className="stats-grid">
            {stats.map((stat, i) => (
                <div key={i} className="stat-card fade-in">
                    <div className="stat-label">{stat.label}</div>
                    <div className="stat-value">{stat.value}</div>
                    <div className={`stat-change ${stat.positive ? 'positive' : 'negative'}`}>
                        {stat.positive ? <ArrowUpRight size={14} /> : <ArrowDownRight size={14} />}
                        {stat.change}
                    </div>
                </div>
            ))}
        </div>
    )
}

// Live Position Card
function LivePositionCard({ position, onExit, onRefresh }) {
    if (!position?.has_position) {
        return (
            <div className="card">
                <div className="card-header">
                    <div className="card-title">
                        <Target className="card-title-icon" size={20} />
                        Active Position
                    </div>
                </div>
                <div className="card-body text-center">
                    <Zap size={32} style={{ color: 'var(--text-tertiary)', margin: '2rem auto' }} />
                    <p style={{ color: 'var(--text-secondary)' }}>No active position</p>
                    <p style={{ fontSize: '0.875rem', color: 'var(--text-tertiary)' }}>Waiting for entry signal...</p>
                </div>
            </div>
        )
    }

    const { symbol, entry_price, current_price, tp_price, sl_price, pnl_pct, pnl_usd, time_held_minutes, is_paper } = position
    const isProfit = pnl_pct >= 0
    const priceRange = tp_price - sl_price
    const currentProgress = ((current_price - sl_price) / priceRange) * 100

    return (
        <div className={`card position-card ${isProfit ? 'profit' : 'loss'}`}>
            <div className="card-header">
                <div className="card-title">
                    <Target className="card-title-icon" size={20} />
                    Active Position
                </div>
                <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                    {is_paper && <span className="badge badge-warning">PAPER</span>}
                    <button onClick={onRefresh} className="btn btn-ghost btn-sm">
                        <RefreshCw size={14} />
                    </button>
                </div>
            </div>

            <div className="card-body">
                <div className="position-header">
                    <span className="position-symbol">{symbol}</span>
                    <span className={`position-pnl ${isProfit ? 'positive' : 'negative'}`}>
                        {pnl_pct >= 0 ? '+' : ''}{pnl_pct?.toFixed(2)}%
                    </span>
                </div>

                <div className="position-metrics">
                    <div className="metric-item">
                        <div className="metric-label">Entry</div>
                        <div className="metric-value">${entry_price?.toFixed(8)}</div>
                    </div>
                    <div className="metric-item">
                        <div className="metric-label">Current</div>
                        <div className="metric-value">${current_price?.toFixed(8)}</div>
                    </div>
                    <div className="metric-item">
                        <div className="metric-label">P&L</div>
                        <div className={`metric-value ${isProfit ? 'positive' : 'negative'}`}>
                            {pnl_usd >= 0 ? '+' : ''}${pnl_usd?.toFixed(4)}
                        </div>
                    </div>
                </div>

                <div className="tpsl-progress">
                    <div className="tpsl-labels">
                        <span>SL: ${sl_price?.toFixed(6)}</span>
                        <span>TP: ${tp_price?.toFixed(6)}</span>
                    </div>
                    <div className="tpsl-bar">
                        <div className="tpsl-fill" style={{ width: `${Math.min(Math.max(currentProgress, 0), 100)}%` }} />
                        <div className="tpsl-marker" style={{ left: `${Math.min(Math.max(currentProgress, 0), 100)}%` }} />
                    </div>
                </div>

                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '1rem' }}>
                    <span style={{ fontSize: '0.875rem', color: 'var(--text-secondary)', display: 'flex', alignItems: 'center', gap: '4px' }}>
                        <Clock size={14} />
                        {time_held_minutes?.toFixed(0)}m held
                    </span>
                    <button className="btn btn-secondary btn-sm" onClick={() => onExit('MANUAL_EXIT')}>
                        <XCircle size={14} />
                        Exit Position
                    </button>
                </div>
            </div>
        </div>
    )
}

// Tools Hub
function ToolsHub({ onTokenSelect }) {
    const [searchMint, setSearchMint] = useState('')
    const [tokenData, setTokenData] = useState(null)
    const [rugData, setRugData] = useState(null)
    const [isSearching, setIsSearching] = useState(false)

    const handleLoadChart = () => {
        if (tokenData && searchMint) {
            onTokenSelect?.({
                mint: searchMint.trim(),
                symbol: tokenData.symbol || '???',
                name: tokenData.name || 'Unknown'
            })
        }
    }

    const searchToken = async () => {
        if (!searchMint.trim()) return
        setIsSearching(true)
        setTokenData(null)
        setRugData(null)

        try {
            const [tokenRes, rugRes] = await Promise.all([
                fetch(`${API_BASE}/api/tools/token/${searchMint.trim()}`),
                fetch(`${API_BASE}/api/tools/rugcheck/${searchMint.trim()}`)
            ])

            if (tokenRes.ok) setTokenData(await tokenRes.json())
            if (rugRes.ok) setRugData(await rugRes.json())
        } catch (e) {
            console.error('Tool search error:', e)
        } finally {
            setIsSearching(false)
        }
    }

    const getRiskColor = (level) => {
        if (level === 'low') return 'success'
        if (level === 'medium') return 'warning'
        return 'danger'
    }

    return (
        <div className="card">
            <div className="card-header">
                <div className="card-title">
                    <Shield className="card-title-icon" size={20} />
                    Token Scanner
                </div>
            </div>

            <div className="card-body">
                <div style={{ display: 'flex', gap: '8px', marginBottom: '1rem' }}>
                    <input
                        type="text"
                        className="input"
                        value={searchMint}
                        onChange={(e) => setSearchMint(e.target.value)}
                        onKeyPress={(e) => e.key === 'Enter' && searchToken()}
                        placeholder="Enter token mint address..."
                    />
                    <button onClick={searchToken} disabled={isSearching} className="btn btn-primary">
                        <Search size={16} />
                    </button>
                </div>

                {isSearching && (
                    <div style={{ textAlign: 'center', padding: '2rem', color: 'var(--text-secondary)' }}>
                        <RefreshCw size={20} className="pulse" />
                        <p style={{ marginTop: '0.5rem' }}>Analyzing token...</p>
                    </div>
                )}

                {tokenData && (
                    <div style={{ marginBottom: '1rem' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: '1rem', paddingBottom: '1rem', borderBottom: '1px solid var(--border-light)' }}>
                            <div>
                                <div style={{ fontSize: '1.25rem', fontWeight: 700 }}>{tokenData.symbol || '???'}</div>
                                <div style={{ fontSize: '0.875rem', color: 'var(--text-secondary)' }}>{tokenData.name}</div>
                            </div>
                            <div style={{ textAlign: 'right' }}>
                                <div style={{ fontSize: '1.125rem', fontWeight: 600 }}>${tokenData.price?.toFixed(8) || '---'}</div>
                                <div className={`stat-change ${(tokenData.price_change_24h || 0) >= 0 ? 'positive' : 'negative'}`}>
                                    {(tokenData.price_change_24h || 0) >= 0 ? '+' : ''}{tokenData.price_change_24h?.toFixed(1) || 0}%
                                </div>
                            </div>
                        </div>

                        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '12px' }}>
                            <div className="metric-item">
                                <div className="metric-label">Volume 24h</div>
                                <div className="metric-value">${(tokenData.volume_24h / 1000)?.toFixed(0) || 0}K</div>
                            </div>
                            <div className="metric-item">
                                <div className="metric-label">Liquidity</div>
                                <div className="metric-value">${(tokenData.liquidity / 1000)?.toFixed(0) || 0}K</div>
                            </div>
                            <div className="metric-item">
                                <div className="metric-label">MCap</div>
                                <div className="metric-value">{tokenData.market_cap ? '$' + (tokenData.market_cap / 1000000)?.toFixed(2) + 'M' : '---'}</div>
                            </div>
                        </div>

                        {tokenData.pair_address && (
                            <div style={{ display: 'flex', gap: '8px', marginTop: '1rem' }}>
                                <button
                                    onClick={handleLoadChart}
                                    className="btn btn-primary btn-sm"
                                    style={{ flex: 1 }}
                                >
                                    <LineChart size={14} />
                                    Load Chart
                                </button>
                                <a
                                    href={`https://dexscreener.com/solana/${tokenData.pair_address}`}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="btn btn-secondary btn-sm"
                                    style={{ flex: 1 }}
                                >
                                    <ExternalLink size={14} />
                                    DexScreener
                                </a>
                            </div>
                        )}
                    </div>
                )}

                {rugData && (
                    <div style={{ padding: '1rem', background: 'var(--bg-secondary)', borderRadius: 'var(--radius-lg)', borderLeft: `3px solid var(--${getRiskColor(rugData.risk_level)})` }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontWeight: 600 }}>
                                <Shield size={16} />
                                Risk Assessment
                            </div>
                            <span className={`badge badge-${getRiskColor(rugData.risk_level)}`}>
                                {rugData.risk_level?.toUpperCase()}
                            </span>
                        </div>

                        {rugData.warnings?.length > 0 && (
                            <ul style={{ listStyle: 'none', padding: 0, margin: '0.5rem 0' }}>
                                {rugData.warnings.map((w, i) => (
                                    <li key={i} style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '4px 0', fontSize: '0.8125rem', color: 'var(--warning)' }}>
                                        <AlertTriangle size={12} />
                                        {w}
                                    </li>
                                ))}
                            </ul>
                        )}

                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.875rem', marginTop: '0.75rem' }}>
                            <span>Risk Score:</span>
                            <div style={{ flex: 1, height: '6px', background: 'var(--gray-200)', borderRadius: '3px', overflow: 'hidden' }}>
                                <div style={{ height: '100%', width: `${rugData.risk_score || 0}%`, background: `var(--${getRiskColor(rugData.risk_level)})`, transition: 'width 0.3s' }} />
                            </div>
                            <span style={{ fontWeight: 600 }}>{rugData.risk_score || 0}/100</span>
                        </div>
                    </div>
                )}
            </div>
        </div>
    )
}

// Floating Jarvis Chat
function FloatingChat({ jarvisStatus }) {
    const [isOpen, setIsOpen] = useState(false)
    const [messages, setMessages] = useState([
        { role: 'assistant', content: 'Hello! I\'m Jarvis. How can I assist with your trading today?' }
    ])
    const [input, setInput] = useState('')
    const [isLoading, setIsLoading] = useState(false)
    const messagesEndRef = useRef(null)

    const scrollToBottom = () => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
    }

    useEffect(scrollToBottom, [messages])

    const sendMessage = async () => {
        if (!input.trim() || isLoading) return

        const userMessage = input.trim()
        setInput('')
        setMessages(prev => [...prev, { role: 'user', content: userMessage }])
        setIsLoading(true)

        try {
            const response = await fetch(`${API_BASE}/api/jarvis/chat`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ message: userMessage })
            })

            if (response.ok) {
                const data = await response.json()
                setMessages(prev => [...prev, { role: 'assistant', content: data.response }])
            }
        } catch (e) {
            console.error('Chat error:', e)
        } finally {
            setIsLoading(false)
        }
    }

    return (
        <div className="chat-bubble">
            {isOpen && (
                <div className="chat-panel slide-in">
                    <div className="chat-header">
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                            <Bot size={20} />
                            <span style={{ fontWeight: 600 }}>Jarvis</span>
                        </div>
                        <button onClick={() => setIsOpen(false)} className="btn btn-ghost btn-sm" style={{ color: 'white' }}>
                            <XCircle size={16} />
                        </button>
                    </div>

                    <div className="chat-messages">
                        {messages.map((msg, i) => (
                            <div key={i} className={`chat-message ${msg.role}`}>
                                {msg.content}
                            </div>
                        ))}
                        {isLoading && (
                            <div className="chat-message assistant">
                                <span className="pulse">Thinking...</span>
                            </div>
                        )}
                        <div ref={messagesEndRef} />
                    </div>

                    <div className="chat-input-container">
                        <input
                            className="chat-input"
                            value={input}
                            onChange={(e) => setInput(e.target.value)}
                            onKeyPress={(e) => e.key === 'Enter' && sendMessage()}
                            placeholder="Ask Jarvis..."
                        />
                        <button onClick={sendMessage} className="btn btn-primary btn-sm">
                            <Send size={14} />
                        </button>
                    </div>
                </div>
            )}

            <div className="chat-trigger" onClick={() => setIsOpen(!isOpen)}>
                <MessageSquare size={24} />
            </div>
        </div>
    )
}

// =============================================================================
// Main Trading Dashboard V2
// =============================================================================
function Trading() {
    const [activeView, setActiveView] = useState('trading')
    const [walletData, setWalletData] = useState(null)
    const [sniperData, setSniperData] = useState(null)
    const [jarvisStatus, setJarvisStatus] = useState(null)
    const [activePosition, setActivePosition] = useState(null)
    const [selectedToken, setSelectedToken] = useState(DEFAULT_TOKEN)
    const [currentPrice, setCurrentPrice] = useState(0)

    // Fetch functions
    const fetchWallet = async () => {
        try {
            const res = await fetch(`${API_BASE}/api/wallet/status`)
            if (res.ok) setWalletData(await res.json())
        } catch (e) { console.error('Wallet fetch error:', e) }
    }

    const fetchSniper = async () => {
        try {
            const res = await fetch(`${API_BASE}/api/sniper/status`)
            if (res.ok) setSniperData(await res.json())
        } catch (e) { console.error('Sniper fetch error:', e) }
    }

    const fetchJarvis = async () => {
        try {
            const res = await fetch(`${API_BASE}/api/jarvis/status`)
            if (res.ok) setJarvisStatus(await res.json())
        } catch (e) { console.error('Jarvis fetch error:', e) }
    }

    const fetchPosition = async () => {
        try {
            const res = await fetch(`${API_BASE}/api/position/active`)
            if (res.ok) setActivePosition(await res.json())
        } catch (e) { console.error('Position fetch error:', e) }
    }

    const exitPosition = async (reason) => {
        try {
            const res = await fetch(`${API_BASE}/api/position/exit`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ reason })
            })
            if (res.ok) {
                setActivePosition({ has_position: false })
                fetchPosition()
            }
        } catch (e) { console.error('Position exit error:', e) }
    }

    useEffect(() => {
        fetchWallet()
        fetchSniper()
        fetchJarvis()
        fetchPosition()

        const interval = setInterval(() => {
            fetchWallet()
            fetchSniper()
            fetchPosition()
        }, 5000)

        return () => clearInterval(interval)
    }, [])

    return (
        <div className="trading-dashboard">
            <TopNav walletData={walletData} />

            <div className="dashboard-container">
                <Sidebar activeView={activeView} setActiveView={setActiveView} />

                <div className="main-content">
                    <div className="page-header">
                        <h1 className="page-title">Trading Command Center</h1>
                        <p className="page-subtitle">Real-time Solana trading with Jarvis AI</p>
                    </div>

                    <StatsGrid walletData={walletData} sniperData={sniperData} />

                    {/* Chart + Order Panel Row */}
                    <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: '24px', marginBottom: '24px' }}>
                        <TradingChart
                            mint={selectedToken.mint}
                            symbol={selectedToken.symbol}
                            onPriceUpdate={setCurrentPrice}
                        />
                        <OrderPanel
                            mint={selectedToken.mint}
                            symbol={selectedToken.symbol}
                            currentPrice={currentPrice}
                            walletBalance={walletData?.balance_sol || 0}
                        />
                    </div>

                    {/* Position + Tools Row */}
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '24px', marginBottom: '24px' }}>
                        <LivePositionCard
                            position={activePosition}
                            onExit={exitPosition}
                            onRefresh={fetchPosition}
                        />
                        <ToolsHub onTokenSelect={(token) => setSelectedToken(token)} />
                    </div>
                </div>
            </div>

            <FloatingChat jarvisStatus={jarvisStatus} />
        </div>
    )
}

export default Trading
