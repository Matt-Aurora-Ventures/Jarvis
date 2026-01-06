import React, { useState } from 'react'
import { Shield, Search, RefreshCw, AlertTriangle, ExternalLink, LineChart } from 'lucide-react'
import { jarvisApi } from '../../lib/api'
import { formatUSD, formatCompact, formatPercent } from '../../lib/format'

/**
 * TokenScanner - Search and analyze tokens
 */
function TokenScanner({ onTokenSelect }) {
  const [searchMint, setSearchMint] = useState('')
  const [tokenData, setTokenData] = useState(null)
  const [rugData, setRugData] = useState(null)
  const [isSearching, setIsSearching] = useState(false)

  const handleLoadChart = () => {
    if (tokenData && searchMint) {
      onTokenSelect?.({
        mint: searchMint.trim(),
        symbol: tokenData.symbol || '???',
        name: tokenData.name || 'Unknown',
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
        jarvisApi.getTokenInfo(searchMint.trim()).catch(() => null),
        jarvisApi.getRugCheck(searchMint.trim()).catch(() => null),
      ])

      if (tokenRes) setTokenData(tokenRes)
      if (rugRes) setRugData(rugRes)
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

        {tokenData && <TokenDetails token={tokenData} onLoadChart={handleLoadChart} />}
        {rugData && <RiskAssessment data={rugData} getRiskColor={getRiskColor} />}
      </div>
    </div>
  )
}

function TokenDetails({ token, onLoadChart }) {
  return (
    <div style={{ marginBottom: '1rem' }}>
      <div style={{ 
        display: 'flex', 
        justifyContent: 'space-between', 
        alignItems: 'baseline', 
        marginBottom: '1rem', 
        paddingBottom: '1rem', 
        borderBottom: '1px solid var(--border-light)' 
      }}>
        <div>
          <div style={{ fontSize: '1.25rem', fontWeight: 700 }}>
            {token.symbol || '???'}
          </div>
          <div style={{ fontSize: '0.875rem', color: 'var(--text-secondary)' }}>
            {token.name}
          </div>
        </div>
        <div style={{ textAlign: 'right' }}>
          <div style={{ fontSize: '1.125rem', fontWeight: 600 }}>
            {formatUSD(token.price, { maximumFractionDigits: 8 })}
          </div>
          <div className={`stat-change ${(token.price_change_24h || 0) >= 0 ? 'positive' : 'negative'}`}>
            {formatPercent(token.price_change_24h)}
          </div>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '12px' }}>
        <div className="metric-item">
          <div className="metric-label">Volume 24h</div>
          <div className="metric-value">${formatCompact(token.volume_24h)}</div>
        </div>
        <div className="metric-item">
          <div className="metric-label">Liquidity</div>
          <div className="metric-value">${formatCompact(token.liquidity)}</div>
        </div>
        <div className="metric-item">
          <div className="metric-label">MCap</div>
          <div className="metric-value">
            {token.market_cap ? '$' + formatCompact(token.market_cap) : '---'}
          </div>
        </div>
      </div>

      {token.pair_address && (
        <div style={{ display: 'flex', gap: '8px', marginTop: '1rem' }}>
          <button onClick={onLoadChart} className="btn btn-primary btn-sm" style={{ flex: 1 }}>
            <LineChart size={14} />
            Load Chart
          </button>
          <a
            href={`https://dexscreener.com/solana/${token.pair_address}`}
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
  )
}

function RiskAssessment({ data, getRiskColor }) {
  return (
    <div style={{ 
      padding: '1rem', 
      background: 'var(--bg-secondary)', 
      borderRadius: 'var(--radius-lg)', 
      borderLeft: `3px solid var(--${getRiskColor(data.risk_level)})` 
    }}>
      <div style={{ 
        display: 'flex', 
        justifyContent: 'space-between', 
        alignItems: 'center', 
        marginBottom: '0.75rem' 
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontWeight: 600 }}>
          <Shield size={16} />
          Risk Assessment
        </div>
        <span className={`badge badge-${getRiskColor(data.risk_level)}`}>
          {data.risk_level?.toUpperCase()}
        </span>
      </div>

      {data.warnings?.length > 0 && (
        <ul style={{ listStyle: 'none', padding: 0, margin: '0.5rem 0' }}>
          {data.warnings.map((w, i) => (
            <li key={i} style={{ 
              display: 'flex', 
              alignItems: 'center', 
              gap: '8px', 
              padding: '4px 0', 
              fontSize: '0.8125rem', 
              color: 'var(--warning)' 
            }}>
              <AlertTriangle size={12} />
              {w}
            </li>
          ))}
        </ul>
      )}

      <div style={{ 
        display: 'flex', 
        alignItems: 'center', 
        gap: '8px', 
        fontSize: '0.875rem', 
        marginTop: '0.75rem' 
      }}>
        <span>Risk Score:</span>
        <div style={{ 
          flex: 1, 
          height: '6px', 
          background: 'var(--gray-200)', 
          borderRadius: '3px', 
          overflow: 'hidden' 
        }}>
          <div style={{ 
            height: '100%', 
            width: `${data.risk_score || 0}%`, 
            background: `var(--${getRiskColor(data.risk_level)})`, 
            transition: 'width 0.3s' 
          }} />
        </div>
        <span style={{ fontWeight: 600 }}>{data.risk_score || 0}/100</span>
      </div>
    </div>
  )
}

export default TokenScanner
