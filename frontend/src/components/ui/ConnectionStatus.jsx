import React, { useState, useEffect, useCallback } from 'react'
import { Wifi, WifiOff, RefreshCw, Server, Database, Mic, Activity } from 'lucide-react'

/**
 * ConnectionStatus - Display connection status to backend services
 *
 * Features:
 * - Real-time connection monitoring
 * - Multiple service status indicators
 * - Auto-reconnection handling
 * - Expandable details panel
 */
export function ConnectionStatus({ className = '', variant = 'compact' }) {
  const [status, setStatus] = useState({
    api: { connected: false, latency: null },
    websocket: { connected: false },
    voice: { available: false },
    database: { connected: false },
    lastCheck: null,
    checking: false,
  })
  const [expanded, setExpanded] = useState(false)

  const checkConnections = useCallback(async () => {
    setStatus(prev => ({ ...prev, checking: true }))

    const startTime = Date.now()

    try {
      const response = await fetch('/api/health', {
        method: 'GET',
        headers: { 'Content-Type': 'application/json' },
        signal: AbortSignal.timeout(5000),
      })

      const latency = Date.now() - startTime

      if (response.ok) {
        const data = await response.json()
        setStatus({
          api: { connected: true, latency },
          websocket: { connected: true }, // Assume WS is up if API is up
          voice: { available: data.voice?.available || false },
          database: { connected: data.services?.database || false },
          lastCheck: new Date(),
          checking: false,
        })
      } else {
        throw new Error('API returned error')
      }
    } catch (error) {
      setStatus(prev => ({
        ...prev,
        api: { connected: false, latency: null },
        websocket: { connected: false },
        lastCheck: new Date(),
        checking: false,
      }))
    }
  }, [])

  // Check on mount and periodically
  useEffect(() => {
    checkConnections()
    const interval = setInterval(checkConnections, 30000) // Every 30 seconds
    return () => clearInterval(interval)
  }, [checkConnections])

  const isConnected = status.api.connected
  const statusColor = isConnected ? 'var(--success)' : 'var(--danger)'
  const statusText = isConnected ? 'Connected' : 'Disconnected'

  // Compact variant - just an icon
  if (variant === 'minimal') {
    return (
      <div
        className={`connection-status-minimal ${className}`}
        title={`${statusText}${status.api.latency ? ` (${status.api.latency}ms)` : ''}`}
        onClick={checkConnections}
        style={{ cursor: 'pointer' }}
      >
        {isConnected ? (
          <Wifi size={16} style={{ color: statusColor }} />
        ) : (
          <WifiOff size={16} style={{ color: statusColor }} />
        )}
        <style jsx>{`
          .connection-status-minimal {
            display: inline-flex;
            align-items: center;
            padding: 4px;
          }
        `}</style>
      </div>
    )
  }

  // Compact variant - icon with text
  if (variant === 'compact') {
    return (
      <div
        className={`connection-status-compact ${className}`}
        onClick={() => setExpanded(!expanded)}
        style={{ cursor: 'pointer' }}
      >
        <div className="status-indicator">
          {status.checking ? (
            <RefreshCw size={14} className="spin" />
          ) : isConnected ? (
            <Wifi size={14} />
          ) : (
            <WifiOff size={14} />
          )}
          <span className="status-text">{statusText}</span>
          {status.api.latency && (
            <span className="latency">{status.api.latency}ms</span>
          )}
        </div>

        {expanded && (
          <div className="status-dropdown">
            <ServiceStatus
              icon={Server}
              name="API"
              connected={status.api.connected}
              detail={status.api.latency ? `${status.api.latency}ms` : null}
            />
            <ServiceStatus
              icon={Activity}
              name="WebSocket"
              connected={status.websocket.connected}
            />
            <ServiceStatus
              icon={Mic}
              name="Voice"
              connected={status.voice.available}
            />
            <ServiceStatus
              icon={Database}
              name="Database"
              connected={status.database.connected}
            />

            <div className="last-check">
              Last check: {status.lastCheck?.toLocaleTimeString() || 'Never'}
              <button onClick={(e) => { e.stopPropagation(); checkConnections(); }} className="btn btn-ghost btn-xs">
                <RefreshCw size={12} />
              </button>
            </div>
          </div>
        )}

        <style jsx>{`
          .connection-status-compact {
            position: relative;
          }

          .status-indicator {
            display: flex;
            align-items: center;
            gap: 6px;
            padding: 6px 10px;
            background: var(--bg-secondary);
            border-radius: 6px;
            font-size: 12px;
            color: ${statusColor};
            transition: background 0.2s;
          }

          .status-indicator:hover {
            background: var(--bg-tertiary);
          }

          .status-text {
            font-weight: 500;
          }

          .latency {
            color: var(--text-tertiary);
            font-size: 11px;
          }

          .status-dropdown {
            position: absolute;
            top: 100%;
            right: 0;
            margin-top: 4px;
            min-width: 200px;
            background: var(--bg-primary);
            border: 1px solid var(--border-primary);
            border-radius: 8px;
            padding: 12px;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
            z-index: 100;
          }

          .last-check {
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-top: 8px;
            padding-top: 8px;
            border-top: 1px solid var(--border-primary);
            font-size: 11px;
            color: var(--text-tertiary);
          }

          .spin {
            animation: spin 1s linear infinite;
          }

          @keyframes spin {
            from { transform: rotate(0deg); }
            to { transform: rotate(360deg); }
          }
        `}</style>
      </div>
    )
  }

  // Full variant - detailed panel
  return (
    <div className={`connection-status-full ${className}`}>
      <div className="status-header">
        <h4>Connection Status</h4>
        <button onClick={checkConnections} className="btn btn-ghost btn-sm" disabled={status.checking}>
          <RefreshCw size={14} className={status.checking ? 'spin' : ''} />
        </button>
      </div>

      <div className="services-grid">
        <ServiceStatus icon={Server} name="API Server" connected={status.api.connected} detail={status.api.latency ? `${status.api.latency}ms latency` : null} />
        <ServiceStatus icon={Activity} name="WebSocket" connected={status.websocket.connected} />
        <ServiceStatus icon={Mic} name="Voice System" connected={status.voice.available} />
        <ServiceStatus icon={Database} name="Database" connected={status.database.connected} />
      </div>

      {status.lastCheck && (
        <div className="last-updated">
          Last updated: {status.lastCheck.toLocaleTimeString()}
        </div>
      )}

      <style jsx>{`
        .connection-status-full {
          background: var(--bg-secondary);
          border-radius: 12px;
          padding: 16px;
        }

        .status-header {
          display: flex;
          align-items: center;
          justify-content: space-between;
          margin-bottom: 16px;
        }

        .status-header h4 {
          margin: 0;
          font-size: 14px;
          font-weight: 600;
        }

        .services-grid {
          display: grid;
          grid-template-columns: repeat(2, 1fr);
          gap: 12px;
        }

        .last-updated {
          margin-top: 12px;
          font-size: 11px;
          color: var(--text-tertiary);
          text-align: center;
        }

        .spin {
          animation: spin 1s linear infinite;
        }

        @keyframes spin {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  )
}

/**
 * ServiceStatus - Individual service status indicator
 */
function ServiceStatus({ icon: Icon, name, connected, detail }) {
  return (
    <div className="service-status">
      <div className="service-icon" style={{ color: connected ? 'var(--success)' : 'var(--text-tertiary)' }}>
        <Icon size={16} />
      </div>
      <div className="service-info">
        <span className="service-name">{name}</span>
        <span className="service-state" style={{ color: connected ? 'var(--success)' : 'var(--danger)' }}>
          {connected ? 'Online' : 'Offline'}
          {detail && <span className="service-detail"> - {detail}</span>}
        </span>
      </div>
      <style jsx>{`
        .service-status {
          display: flex;
          align-items: center;
          gap: 10px;
          padding: 10px;
          background: var(--bg-primary);
          border-radius: 8px;
        }

        .service-icon {
          display: flex;
          align-items: center;
          justify-content: center;
          width: 32px;
          height: 32px;
          background: var(--bg-secondary);
          border-radius: 6px;
        }

        .service-info {
          display: flex;
          flex-direction: column;
          gap: 2px;
        }

        .service-name {
          font-size: 12px;
          font-weight: 500;
          color: var(--text-primary);
        }

        .service-state {
          font-size: 11px;
        }

        .service-detail {
          color: var(--text-tertiary);
        }
      `}</style>
    </div>
  )
}

/**
 * useConnectionStatus - Hook for checking connection status
 */
export function useConnectionStatus() {
  const [connected, setConnected] = useState(true)
  const [checking, setChecking] = useState(false)

  const checkConnection = useCallback(async () => {
    setChecking(true)
    try {
      const response = await fetch('/api/health', {
        method: 'GET',
        signal: AbortSignal.timeout(5000),
      })
      setConnected(response.ok)
    } catch {
      setConnected(false)
    } finally {
      setChecking(false)
    }
  }, [])

  useEffect(() => {
    checkConnection()
    const interval = setInterval(checkConnection, 30000)
    return () => clearInterval(interval)
  }, [checkConnection])

  return { connected, checking, checkConnection }
}

export default ConnectionStatus
