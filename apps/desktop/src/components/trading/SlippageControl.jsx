import React, { useState } from 'react'
import { Settings, AlertTriangle, Info } from 'lucide-react'

/**
 * SlippageControl - Component for setting and displaying slippage tolerance
 */
export function SlippageControl({
  value = 1,
  onChange,
  presets = [0.1, 0.5, 1, 3],
  max = 50,
  className = '',
}) {
  const [isCustom, setIsCustom] = useState(!presets.includes(value))
  const [customValue, setCustomValue] = useState(value.toString())

  const handlePresetClick = (preset) => {
    setIsCustom(false)
    setCustomValue(preset.toString())
    onChange?.(preset)
  }

  const handleCustomChange = (e) => {
    const val = e.target.value
    setCustomValue(val)

    const numVal = parseFloat(val)
    if (!isNaN(numVal) && numVal >= 0 && numVal <= max) {
      onChange?.(numVal)
    }
  }

  const handleCustomFocus = () => {
    setIsCustom(true)
  }

  const isHighSlippage = value > 5
  const isVeryHighSlippage = value > 15

  return (
    <div className={`slippage-control ${className}`}>
      <div className="slippage-header">
        <label className="slippage-label">
          <Settings size={14} />
          Slippage Tolerance
        </label>
        <span className="slippage-value">{value}%</span>
      </div>

      <div className="slippage-presets">
        {presets.map((preset) => (
          <button
            key={preset}
            className={`slippage-preset ${!isCustom && value === preset ? 'active' : ''}`}
            onClick={() => handlePresetClick(preset)}
          >
            {preset}%
          </button>
        ))}
        <div className={`slippage-custom ${isCustom ? 'active' : ''}`}>
          <input
            type="number"
            value={customValue}
            onChange={handleCustomChange}
            onFocus={handleCustomFocus}
            placeholder="Custom"
            min="0"
            max={max}
            step="0.1"
          />
          <span className="custom-suffix">%</span>
        </div>
      </div>

      {isHighSlippage && (
        <div className={`slippage-warning ${isVeryHighSlippage ? 'severe' : ''}`}>
          <AlertTriangle size={14} />
          <span>
            {isVeryHighSlippage
              ? 'Very high slippage! Your trade may be frontrun.'
              : 'High slippage may result in unfavorable execution.'}
          </span>
        </div>
      )}

      <style jsx>{`
        .slippage-control {
          display: flex;
          flex-direction: column;
          gap: 10px;
        }

        .slippage-header {
          display: flex;
          align-items: center;
          justify-content: space-between;
        }

        .slippage-label {
          display: flex;
          align-items: center;
          gap: 6px;
          font-size: 13px;
          font-weight: 500;
          color: var(--text-secondary);
        }

        .slippage-value {
          font-size: 14px;
          font-weight: 600;
          color: var(--text-primary);
        }

        .slippage-presets {
          display: flex;
          gap: 8px;
        }

        .slippage-preset {
          flex: 1;
          padding: 8px 12px;
          background: var(--bg-secondary);
          border: 1px solid var(--border-primary);
          border-radius: 8px;
          font-size: 13px;
          font-weight: 500;
          color: var(--text-secondary);
          cursor: pointer;
          transition: all 0.15s ease;
        }

        .slippage-preset:hover {
          border-color: var(--accent-primary);
          color: var(--text-primary);
        }

        .slippage-preset.active {
          background: var(--accent-primary);
          border-color: var(--accent-primary);
          color: white;
        }

        .slippage-custom {
          position: relative;
          flex: 1.5;
        }

        .slippage-custom input {
          width: 100%;
          padding: 8px 28px 8px 12px;
          background: var(--bg-secondary);
          border: 1px solid var(--border-primary);
          border-radius: 8px;
          font-size: 13px;
          font-weight: 500;
          color: var(--text-primary);
          transition: all 0.15s ease;
        }

        .slippage-custom input:focus {
          outline: none;
          border-color: var(--accent-primary);
        }

        .slippage-custom.active input {
          border-color: var(--accent-primary);
        }

        .custom-suffix {
          position: absolute;
          right: 10px;
          top: 50%;
          transform: translateY(-50%);
          font-size: 13px;
          color: var(--text-tertiary);
          pointer-events: none;
        }

        .slippage-warning {
          display: flex;
          align-items: center;
          gap: 8px;
          padding: 10px 12px;
          background: rgba(var(--warning-rgb), 0.1);
          border: 1px solid var(--warning);
          border-radius: 8px;
          font-size: 12px;
          color: var(--warning);
        }

        .slippage-warning.severe {
          background: rgba(var(--danger-rgb), 0.1);
          border-color: var(--danger);
          color: var(--danger);
        }

        /* Hide number input spinners */
        input[type='number']::-webkit-outer-spin-button,
        input[type='number']::-webkit-inner-spin-button {
          -webkit-appearance: none;
          margin: 0;
        }

        input[type='number'] {
          -moz-appearance: textfield;
        }
      `}</style>
    </div>
  )
}

/**
 * SlippageDisplay - Compact read-only slippage display
 */
export function SlippageDisplay({ value, estimated, className = '' }) {
  const isHigh = value > 3

  return (
    <div className={`slippage-display ${isHigh ? 'high' : ''} ${className}`}>
      <span className="slippage-display-label">Slippage</span>
      <span className="slippage-display-value">
        {value}%
        {estimated && (
          <span className="estimated">≈ ${estimated.toFixed(2)}</span>
        )}
      </span>

      <style jsx>{`
        .slippage-display {
          display: flex;
          align-items: center;
          justify-content: space-between;
          padding: 8px 12px;
          background: var(--bg-secondary);
          border-radius: 6px;
          font-size: 13px;
        }

        .slippage-display-label {
          color: var(--text-secondary);
        }

        .slippage-display-value {
          display: flex;
          align-items: center;
          gap: 8px;
          font-weight: 500;
          color: var(--text-primary);
        }

        .slippage-display.high .slippage-display-value {
          color: var(--warning);
        }

        .estimated {
          color: var(--text-tertiary);
          font-weight: 400;
        }
      `}</style>
    </div>
  )
}

/**
 * SlippageTooltip - Info tooltip explaining slippage
 */
export function SlippageTooltip() {
  const [isOpen, setIsOpen] = useState(false)

  return (
    <div className="slippage-tooltip-container">
      <button
        className="tooltip-trigger"
        onMouseEnter={() => setIsOpen(true)}
        onMouseLeave={() => setIsOpen(false)}
        onClick={() => setIsOpen(!isOpen)}
      >
        <Info size={14} />
      </button>

      {isOpen && (
        <div className="tooltip-content">
          <h4>What is Slippage?</h4>
          <p>
            Slippage is the difference between the expected price of a trade
            and the actual execution price. It occurs due to market volatility
            and liquidity conditions.
          </p>
          <ul>
            <li><strong>0.1% - 0.5%:</strong> Best for stable markets</li>
            <li><strong>1% - 3%:</strong> Standard for most trades</li>
            <li><strong>&gt;5%:</strong> High risk, may lose value</li>
          </ul>
        </div>
      )}

      <style jsx>{`
        .slippage-tooltip-container {
          position: relative;
          display: inline-flex;
        }

        .tooltip-trigger {
          display: flex;
          align-items: center;
          justify-content: center;
          width: 20px;
          height: 20px;
          background: transparent;
          border: none;
          color: var(--text-tertiary);
          cursor: pointer;
          transition: color 0.15s ease;
        }

        .tooltip-trigger:hover {
          color: var(--text-primary);
        }

        .tooltip-content {
          position: absolute;
          bottom: 100%;
          left: 50%;
          transform: translateX(-50%);
          width: 280px;
          padding: 16px;
          margin-bottom: 8px;
          background: var(--bg-primary);
          border: 1px solid var(--border-primary);
          border-radius: 12px;
          box-shadow: 0 10px 25px rgba(0, 0, 0, 0.2);
          z-index: 100;
        }

        .tooltip-content h4 {
          margin: 0 0 8px 0;
          font-size: 14px;
          font-weight: 600;
        }

        .tooltip-content p {
          margin: 0 0 12px 0;
          font-size: 13px;
          color: var(--text-secondary);
          line-height: 1.5;
        }

        .tooltip-content ul {
          margin: 0;
          padding: 0;
          list-style: none;
        }

        .tooltip-content li {
          font-size: 12px;
          color: var(--text-secondary);
          padding: 4px 0;
        }

        .tooltip-content li strong {
          color: var(--text-primary);
        }
      `}</style>
    </div>
  )
}

export default SlippageControl
