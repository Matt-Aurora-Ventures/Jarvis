import React, { useState } from 'react'
import {
    DollarSign, TrendingUp, TrendingDown, Target, Shield,
    AlertTriangle, Check, Loader
} from 'lucide-react'

const API_BASE = ''

function OrderPanel({ mint, symbol = 'TOKEN', currentPrice = 0, walletBalance = 0 }) {
    const [side, setSide] = useState('buy')
    const [amountSol, setAmountSol] = useState('')
    const [tpPct, setTpPct] = useState(20)
    const [slPct, setSlPct] = useState(10)
    const [isSubmitting, setIsSubmitting] = useState(false)
    const [result, setResult] = useState(null)

    const tpPrice = currentPrice * (1 + tpPct / 100)
    const slPrice = currentPrice * (1 - slPct / 100)

    const handleSubmit = async () => {
        if (!mint || !amountSol || parseFloat(amountSol) <= 0) return

        setIsSubmitting(true)
        setResult(null)

        try {
            const response = await fetch(`${API_BASE}/api/trade`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    mint,
                    side,
                    amount_sol: parseFloat(amountSol),
                    tp_pct: tpPct,
                    sl_pct: slPct,
                })
            })

            const data = await response.json()
            setResult(data)

            if (data.success) {
                setAmountSol('')
            }
        } catch (err) {
            setResult({ success: false, error: err.message })
        } finally {
            setIsSubmitting(false)
        }
    }

    const presetAmounts = [0.01, 0.05, 0.1, 0.25]

    return (
        <div className="card">
            <div className="card-header">
                <div className="card-title">
                    <DollarSign className="card-title-icon" size={20} />
                    Trade {symbol}
                </div>
                <span className="badge badge-warning">PAPER</span>
            </div>

            <div className="card-body">
                {/* Buy/Sell Toggle */}
                <div style={{
                    display: 'flex',
                    gap: '8px',
                    marginBottom: '16px',
                    background: 'var(--bg-secondary)',
                    padding: '4px',
                    borderRadius: 'var(--radius-md)'
                }}>
                    <button
                        onClick={() => setSide('buy')}
                        className={`btn ${side === 'buy' ? 'btn-primary' : 'btn-ghost'}`}
                        style={{ flex: 1 }}
                    >
                        <TrendingUp size={16} />
                        Buy
                    </button>
                    <button
                        onClick={() => setSide('sell')}
                        className={`btn ${side === 'sell' ? '' : 'btn-ghost'}`}
                        style={{
                            flex: 1,
                            background: side === 'sell' ? 'var(--danger)' : 'transparent',
                            color: side === 'sell' ? 'white' : 'inherit'
                        }}
                    >
                        <TrendingDown size={16} />
                        Sell
                    </button>
                </div>

                {/* Current Price */}
                <div style={{
                    marginBottom: '16px',
                    padding: '12px',
                    background: 'var(--bg-secondary)',
                    borderRadius: 'var(--radius-md)',
                    textAlign: 'center'
                }}>
                    <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>Current Price</div>
                    <div style={{ fontSize: '1.25rem', fontWeight: 700, fontFamily: 'monospace' }}>
                        ${currentPrice.toFixed(8)}
                    </div>
                </div>

                {/* Amount */}
                <div style={{ marginBottom: '16px' }}>
                    <label style={{
                        display: 'block',
                        fontSize: '0.8125rem',
                        fontWeight: 500,
                        marginBottom: '8px',
                        color: 'var(--text-secondary)'
                    }}>
                        Amount (SOL)
                    </label>
                    <input
                        type="number"
                        className="input"
                        value={amountSol}
                        onChange={(e) => setAmountSol(e.target.value)}
                        placeholder="0.00"
                        step="0.01"
                        min="0"
                    />
                    <div style={{ display: 'flex', gap: '4px', marginTop: '8px' }}>
                        {presetAmounts.map(amt => (
                            <button
                                key={amt}
                                onClick={() => setAmountSol(amt.toString())}
                                className="btn btn-ghost btn-sm"
                                style={{ flex: 1 }}
                            >
                                {amt}
                            </button>
                        ))}
                    </div>
                    <div style={{
                        fontSize: '0.75rem',
                        color: 'var(--text-tertiary)',
                        marginTop: '4px'
                    }}>
                        Balance: {walletBalance.toFixed(4)} SOL
                    </div>
                </div>

                {/* TP/SL */}
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', marginBottom: '16px' }}>
                    <div>
                        <label style={{
                            display: 'flex',
                            alignItems: 'center',
                            gap: '4px',
                            fontSize: '0.75rem',
                            fontWeight: 500,
                            marginBottom: '8px',
                            color: 'var(--success)'
                        }}>
                            <Target size={12} />
                            Take Profit
                        </label>
                        <div style={{ display: 'flex', gap: '4px' }}>
                            {[10, 20, 50].map(pct => (
                                <button
                                    key={pct}
                                    onClick={() => setTpPct(pct)}
                                    className={`btn btn-sm ${tpPct === pct ? 'btn-primary' : 'btn-ghost'}`}
                                    style={{ flex: 1 }}
                                >
                                    +{pct}%
                                </button>
                            ))}
                        </div>
                        <div style={{
                            fontSize: '0.75rem',
                            color: 'var(--text-tertiary)',
                            marginTop: '4px',
                            fontFamily: 'monospace'
                        }}>
                            ${tpPrice.toFixed(8)}
                        </div>
                    </div>

                    <div>
                        <label style={{
                            display: 'flex',
                            alignItems: 'center',
                            gap: '4px',
                            fontSize: '0.75rem',
                            fontWeight: 500,
                            marginBottom: '8px',
                            color: 'var(--danger)'
                        }}>
                            <Shield size={12} />
                            Stop Loss
                        </label>
                        <div style={{ display: 'flex', gap: '4px' }}>
                            {[5, 10, 20].map(pct => (
                                <button
                                    key={pct}
                                    onClick={() => setSlPct(pct)}
                                    className={`btn btn-sm ${slPct === pct ? '' : 'btn-ghost'}`}
                                    style={{
                                        flex: 1,
                                        background: slPct === pct ? 'var(--danger)' : 'transparent',
                                        color: slPct === pct ? 'white' : 'inherit'
                                    }}
                                >
                                    -{pct}%
                                </button>
                            ))}
                        </div>
                        <div style={{
                            fontSize: '0.75rem',
                            color: 'var(--text-tertiary)',
                            marginTop: '4px',
                            fontFamily: 'monospace'
                        }}>
                            ${slPrice.toFixed(8)}
                        </div>
                    </div>
                </div>

                {/* Submit Button */}
                <button
                    onClick={handleSubmit}
                    disabled={isSubmitting || !amountSol || parseFloat(amountSol) <= 0}
                    className="btn btn-primary btn-lg"
                    style={{
                        width: '100%',
                        background: side === 'sell' ? 'var(--danger)' : 'var(--primary)'
                    }}
                >
                    {isSubmitting ? (
                        <>
                            <Loader size={16} className="pulse" />
                            Processing...
                        </>
                    ) : (
                        <>
                            {side === 'buy' ? <TrendingUp size={16} /> : <TrendingDown size={16} />}
                            {side === 'buy' ? 'Buy' : 'Sell'} {amountSol || '0'} SOL
                        </>
                    )}
                </button>

                {/* Result */}
                {result && (
                    <div style={{
                        marginTop: '16px',
                        padding: '12px',
                        borderRadius: 'var(--radius-md)',
                        background: result.success ? 'rgba(16, 185, 129, 0.1)' : 'rgba(239, 68, 68, 0.1)',
                        border: `1px solid ${result.success ? 'var(--success)' : 'var(--danger)'}`
                    }}>
                        <div style={{
                            display: 'flex',
                            alignItems: 'center',
                            gap: '8px',
                            color: result.success ? 'var(--success)' : 'var(--danger)',
                            fontWeight: 600
                        }}>
                            {result.success ? <Check size={16} /> : <AlertTriangle size={16} />}
                            {result.success ? 'Trade Submitted' : 'Trade Failed'}
                        </div>
                        <div style={{
                            fontSize: '0.8125rem',
                            color: 'var(--text-secondary)',
                            marginTop: '4px'
                        }}>
                            {result.message || result.error}
                        </div>
                        {result.trade_id && (
                            <div style={{
                                fontSize: '0.75rem',
                                color: 'var(--text-tertiary)',
                                fontFamily: 'monospace',
                                marginTop: '4px'
                            }}>
                                ID: {result.trade_id}
                            </div>
                        )}
                    </div>
                )}
            </div>
        </div>
    )
}

export default OrderPanel
