import React, { useState, useEffect } from 'react'
import { Activity, Wifi, WifiOff, RefreshCw, AlertCircle, CheckCircle } from 'lucide-react'

/**
 * StatusBar component for Electron app
 * Shows backend status, connection state, and platform info
 */
export default function StatusBar() {
  const [backendStatus, setBackendStatus] = useState({ running: false, pid: null })
  const [platform, setPlatform] = useState('')
  const [version, setVersion] = useState('')
  const [isRestarting, setIsRestarting] = useState(false)
  const [logs, setLogs] = useState([])

  useEffect(() => {
    // Only run in Electron environment
    if (!window.electronAPI) return

    // Get platform info
    setPlatform(window.electronAPI.getPlatform())
    window.electronAPI.getVersion().then(setVersion)

    // Get initial status
    window.electronAPI.getBackendStatus().then(setBackendStatus)

    // Listen for backend events
    window.electronAPI.onJarvisLog((data) => {
      setLogs(prev => [...prev.slice(-50), { type: 'log', message: data, time: new Date() }])
    })

    window.electronAPI.onJarvisError((data) => {
      setLogs(prev => [...prev.slice(-50), { type: 'error', message: data, time: new Date() }])
    })

    window.electronAPI.onJarvisExit((code) => {
      setBackendStatus({ running: false, pid: null })
      setLogs(prev => [...prev.slice(-50), { type: 'exit', message: `Backend exited with code ${code}`, time: new Date() }])
    })

    // Poll status periodically
    const interval = setInterval(async () => {
      const status = await window.electronAPI.getBackendStatus()
      setBackendStatus(status)
    }, 5000)

    return () => {
      clearInterval(interval)
      window.electronAPI.removeAllListeners('jarvis-log')
      window.electronAPI.removeAllListeners('jarvis-error')
      window.electronAPI.removeAllListeners('jarvis-exit')
    }
  }, [])

  const handleRestart = async () => {
    if (!window.electronAPI) return
    setIsRestarting(true)
    try {
      await window.electronAPI.restartBackend()
      setTimeout(() => {
        setIsRestarting(false)
        window.electronAPI.getBackendStatus().then(setBackendStatus)
      }, 2000)
    } catch (err) {
      setIsRestarting(false)
    }
  }

  const platformLabels = {
    win32: 'Windows',
    darwin: 'macOS',
    linux: 'Linux',
  }

  // Don't render in web-only mode
  if (!window.electronAPI) {
    return null
  }

  return (
    <div className="fixed bottom-0 left-0 right-0 bg-gray-900 border-t border-gray-800 px-4 py-2 flex items-center justify-between text-xs text-gray-400 z-50">
      {/* Left: Backend Status */}
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2">
          {backendStatus.running ? (
            <>
              <CheckCircle className="w-3 h-3 text-green-500" />
              <span className="text-green-400">Backend Running</span>
              {backendStatus.pid && (
                <span className="text-gray-500">(PID: {backendStatus.pid})</span>
              )}
            </>
          ) : (
            <>
              <AlertCircle className="w-3 h-3 text-red-500" />
              <span className="text-red-400">Backend Offline</span>
            </>
          )}
        </div>

        <button
          onClick={handleRestart}
          disabled={isRestarting}
          className="flex items-center gap-1 px-2 py-1 rounded bg-gray-800 hover:bg-gray-700 transition-colors disabled:opacity-50"
        >
          <RefreshCw className={`w-3 h-3 ${isRestarting ? 'animate-spin' : ''}`} />
          <span>{isRestarting ? 'Restarting...' : 'Restart'}</span>
        </button>
      </div>

      {/* Center: Activity */}
      <div className="flex items-center gap-2">
        <Activity className="w-3 h-3" />
        <span>JARVIS</span>
      </div>

      {/* Right: Platform & Version */}
      <div className="flex items-center gap-4">
        <span>{platformLabels[platform] || platform}</span>
        <span>v{version}</span>
      </div>
    </div>
  )
}
