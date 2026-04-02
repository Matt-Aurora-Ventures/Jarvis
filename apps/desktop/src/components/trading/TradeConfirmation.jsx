import React, { useState, useEffect, useCallback } from 'react'
import { X, AlertTriangle, CheckCircle, Clock, TrendingUp, TrendingDown } from 'lucide-react'

/**
 * TradeConfirmation - Modal for confirming trades before execution
 * Shows trade details, fees, slippage, and countdown timer
 */
export function TradeConfirmation({
  isOpen,
  onClose,
  onConfirm,
  trade,
  autoConfirmSeconds = 0, // 0 = no auto-confirm
}) {
  const [countdown, setCountdown] = useState(autoConfirmSeconds)
  const [isConfirming, setIsConfirming] = useState(false)

  // Reset countdown when modal opens
  useEffect(() => {
    if (isOpen && autoConfirmSeconds > 0) {
      setCountdown(autoConfirmSeconds)
    }
  }, [isOpen, autoConfirmSeconds])

  // Countdown timer
  useEffect(() => {
    if (!isOpen || countdown <= 0 || autoConfirmSeconds === 0) return

    const timer = setInterval(() => {
      setCountdown(prev => {
        if (prev <= 1) {
          clearInterval(timer)
          handleConfirm()
          return 0
        }
        return prev - 1
      })
    }, 1000)

    return () => clearInterval(timer)
  }, [isOpen, countdown, autoConfirmSeconds])

  const handleConfirm = useCallback(async () => {
    setIsConfirming(true)
    try {
      await onConfirm(trade)
    } finally {
      setIsConfirming(false)
      onClose()
    }
  }, [trade, onConfirm, onClose])

  const handleCancel = useCallback(() => {
    setCountdown(0)
    onClose()
  }, [onClose])

  if (!isOpen || !trade) return null

  const isBuy = trade.side?.toLowerCase() === 'buy'
  const SideIcon = isBuy ? TrendingUp : TrendingDown

  // Calculate estimates
  const estimatedTotal = (trade.amount || 0) * (trade.price || 0)
  const estimatedFee = estimatedTotal * (trade.feePercent || 0.003) // 0.3% default
  const estimatedSlippage = estimatedTotal * (trade.slippagePercent || 0.01) // 1% default
  const worstCaseTotal = isBuy
    ? estimatedTotal + estimatedFee + estimatedSlippage
    : estimatedTotal - estimatedFee - estimatedSlippage

  return (
    <div className="trade-confirm-overlay" onClick={handleCancel}>
      <div className="trade-confirm-modal" onClick={e => e.stopPropagation()}>
        {/* Header */}
        <div className="trade-confirm-header">
          <div className="trade-confirm-title">
            <SideIcon
              size={24}
              className={isBuy ? 'text-success' : 'text-danger'}
            />
            <h2>Confirm {trade.side} Order</h2>
          </div>
          <button className="btn btn-ghost btn-icon" onClick={handleCancel}>
            <X size={20} />
          </button>
        </div>

        {/* Trade Details */}
        <div className="trade-confirm-body">
          {/* Main trade info */}
          <div className="trade-detail-card">
            <div className="trade-detail-row main">
              <span className="label">Action</span>
              <span className={`value ${isBuy ? 'text-success' : 'text-danger'}`}>
                {trade.side} {trade.symbol}
              </span>
            </div>
            <div className="trade-detail-row">
              <span className="label">Amount</span>
              <span className="value">{trade.amount?.toLocaleString()} {trade.baseToken || 'tokens'}</span>
            </div>
            <div className="trade-detail-row">
              <span className="label">Price</span>
              <span className="value">${trade.price?.toFixed(6)}</span>
            </div>
          </div>

          {/* Cost breakdown */}
          <div className="trade-detail-card">
            <div className="trade-detail-row">
              <span className="label">Subtotal</span>
              <span className="value">${estimatedTotal.toFixed(2)}</span>
            </div>
            <div className="trade-detail-row">
              <span className="label">Est. Fee ({((trade.feePercent || 0.003) * 100).toFixed(1)}%)</span>
              <span className="value text-warning">-${estimatedFee.toFixed(2)}</span>
            </div>
            <div className="trade-detail-row">
              <span className="label">Max Slippage ({((trade.slippagePercent || 0.01) * 100).toFixed(1)}%)</span>
              <span className="value text-warning">±${estimatedSlippage.toFixed(2)}</span>
            </div>
            <div className="trade-detail-row total">
              <span className="label">{isBuy ? 'Max Cost' : 'Min Receive'}</span>
              <span className="value">${worstCaseTotal.toFixed(2)}</span>
            </div>
          </div>

          {/* Risk warning for large trades */}
          {estimatedTotal > 1000 && (
            <div className="trade-warning">
              <AlertTriangle size={18} />
              <span>Large trade detected. Please review carefully.</span>
            </div>
          )}

          {/* TP/SL info if set */}
          {(trade.takeProfit || trade.stopLoss) && (
            <div className="trade-detail-card">
              {trade.takeProfit && (
                <div className="trade-detail-row">
                  <span className="label">Take Profit</span>
                  <span className="value text-success">${trade.takeProfit.toFixed(6)}</span>
                </div>
              )}
              {trade.stopLoss && (
                <div className="trade-detail-row">
                  <span className="label">Stop Loss</span>
                  <span className="value text-danger">${trade.stopLoss.toFixed(6)}</span>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Footer with actions */}
        <div className="trade-confirm-footer">
          <button
            className="btn btn-ghost"
            onClick={handleCancel}
            disabled={isConfirming}
          >
            Cancel
          </button>

          <button
            className={`btn ${isBuy ? 'btn-success' : 'btn-danger'}`}
            onClick={handleConfirm}
            disabled={isConfirming}
          >
            {isConfirming ? (
              <>Processing...</>
            ) : countdown > 0 ? (
              <>
                <Clock size={16} />
                Confirm ({countdown}s)
              </>
            ) : (
              <>
                <CheckCircle size={16} />
                Confirm {trade.side}
              </>
            )}
          </button>
        </div>

        <style jsx>{`
          .trade-confirm-overlay {
            position: fixed;
            inset: 0;
            background: rgba(0, 0, 0, 0.7);
            display: flex;
            align-items: center;
            justify-content: center;
            z-index: 1000;
            backdrop-filter: blur(4px);
          }

          .trade-confirm-modal {
            background: var(--bg-primary);
            border-radius: 16px;
            border: 1px solid var(--border-primary);
            width: 90%;
            max-width: 420px;
            box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5);
            animation: slideUp 0.2s ease-out;
          }

          .trade-confirm-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 20px 24px;
            border-bottom: 1px solid var(--border-primary);
          }

          .trade-confirm-title {
            display: flex;
            align-items: center;
            gap: 12px;
          }

          .trade-confirm-title h2 {
            margin: 0;
            font-size: 18px;
            font-weight: 600;
          }

          .trade-confirm-body {
            padding: 20px 24px;
            display: flex;
            flex-direction: column;
            gap: 16px;
          }

          .trade-detail-card {
            background: var(--bg-secondary);
            border-radius: 12px;
            padding: 16px;
          }

          .trade-detail-row {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 8px 0;
          }

          .trade-detail-row:not(:last-child) {
            border-bottom: 1px solid var(--border-primary);
          }

          .trade-detail-row.main {
            padding-bottom: 12px;
            margin-bottom: 4px;
          }

          .trade-detail-row.main .value {
            font-size: 18px;
            font-weight: 600;
          }

          .trade-detail-row.total {
            padding-top: 12px;
            margin-top: 4px;
            border-top: 2px solid var(--border-secondary);
            border-bottom: none;
          }

          .trade-detail-row.total .value {
            font-size: 18px;
            font-weight: 700;
          }

          .trade-detail-row .label {
            color: var(--text-secondary);
            font-size: 14px;
          }

          .trade-detail-row .value {
            font-weight: 500;
          }

          .trade-warning {
            display: flex;
            align-items: center;
            gap: 10px;
            padding: 12px 16px;
            background: rgba(var(--warning-rgb), 0.1);
            border: 1px solid var(--warning);
            border-radius: 8px;
            color: var(--warning);
            font-size: 14px;
          }

          .trade-confirm-footer {
            display: flex;
            gap: 12px;
            padding: 20px 24px;
            border-top: 1px solid var(--border-primary);
          }

          .trade-confirm-footer .btn {
            flex: 1;
            padding: 12px 20px;
            font-weight: 600;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 8px;
          }

          .text-success { color: var(--success); }
          .text-danger { color: var(--danger); }
          .text-warning { color: var(--warning); }

          .btn-success {
            background: var(--success);
            color: white;
          }

          .btn-danger {
            background: var(--danger);
            color: white;
          }

          @keyframes slideUp {
            from {
              opacity: 0;
              transform: translateY(20px);
            }
            to {
              opacity: 1;
              transform: translateY(0);
            }
          }
        `}</style>
      </div>
    </div>
  )
}

/**
 * useTradeConfirmation - Hook for managing trade confirmation state
 */
export function useTradeConfirmation() {
  const [isOpen, setIsOpen] = useState(false)
  const [pendingTrade, setPendingTrade] = useState(null)
  const [onConfirmCallback, setOnConfirmCallback] = useState(null)

  const requestConfirmation = useCallback((trade, onConfirm) => {
    setPendingTrade(trade)
    setOnConfirmCallback(() => onConfirm)
    setIsOpen(true)
  }, [])

  const handleClose = useCallback(() => {
    setIsOpen(false)
    setPendingTrade(null)
    setOnConfirmCallback(null)
  }, [])

  const handleConfirm = useCallback(async (trade) => {
    if (onConfirmCallback) {
      await onConfirmCallback(trade)
    }
  }, [onConfirmCallback])

  return {
    isOpen,
    pendingTrade,
    requestConfirmation,
    handleClose,
    handleConfirm,
    TradeConfirmationModal: () => (
      <TradeConfirmation
        isOpen={isOpen}
        trade={pendingTrade}
        onClose={handleClose}
        onConfirm={handleConfirm}
      />
    ),
  }
}

export default TradeConfirmation
