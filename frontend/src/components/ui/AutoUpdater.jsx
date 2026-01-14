import React, { useState, useEffect } from 'react'
import { Download, RefreshCw, CheckCircle, AlertTriangle, X } from 'lucide-react'

/**
 * AutoUpdater component for Electron app
 * Handles checking for updates and installing them
 */
export default function AutoUpdater() {
  const [updateInfo, setUpdateInfo] = useState(null)
  const [downloadProgress, setDownloadProgress] = useState(null)
  const [updateReady, setUpdateReady] = useState(false)
  const [checking, setChecking] = useState(false)
  const [dismissed, setDismissed] = useState(false)

  useEffect(() => {
    if (!window.electronAPI) return

    // Listen for update events
    window.electronAPI.onUpdateAvailable((info) => {
      setUpdateInfo(info)
      setDismissed(false)
    })

    window.electronAPI.onUpdateDownloaded((info) => {
      setUpdateReady(true)
      setDownloadProgress(null)
    })

    // Check for updates on mount (with delay)
    const timeout = setTimeout(() => {
      checkForUpdates()
    }, 5000)

    return () => {
      clearTimeout(timeout)
      window.electronAPI.removeAllListeners('update-available')
      window.electronAPI.removeAllListeners('update-downloaded')
    }
  }, [])

  const checkForUpdates = async () => {
    if (!window.electronAPI) return
    setChecking(true)
    try {
      await window.electronAPI.checkForUpdates()
    } catch (err) {
      console.error('Update check failed:', err)
    }
    setChecking(false)
  }

  const installUpdate = async () => {
    if (!window.electronAPI) return
    await window.electronAPI.installUpdate()
  }

  // Don't render in web-only mode or if dismissed
  if (!window.electronAPI || dismissed || (!updateInfo && !checking)) {
    return null
  }

  return (
    <div className="fixed top-4 right-4 z-50 bg-gray-900 border border-gray-700 rounded-lg shadow-xl p-4 max-w-sm">
      {/* Close button */}
      <button
        onClick={() => setDismissed(true)}
        className="absolute top-2 right-2 text-gray-500 hover:text-gray-300"
      >
        <X className="w-4 h-4" />
      </button>

      {/* Checking state */}
      {checking && !updateInfo && (
        <div className="flex items-center gap-3">
          <RefreshCw className="w-5 h-5 text-blue-400 animate-spin" />
          <span className="text-gray-300">Checking for updates...</span>
        </div>
      )}

      {/* Update available */}
      {updateInfo && !updateReady && (
        <div className="space-y-3">
          <div className="flex items-center gap-2">
            <Download className="w-5 h-5 text-blue-400" />
            <span className="text-white font-medium">Update Available</span>
          </div>
          <p className="text-sm text-gray-400">
            Version {updateInfo.version} is available.
            {updateInfo.releaseNotes && (
              <span className="block mt-1 text-gray-500">
                {updateInfo.releaseNotes.slice(0, 100)}...
              </span>
            )}
          </p>
          {downloadProgress !== null && (
            <div className="w-full bg-gray-700 rounded-full h-2">
              <div
                className="bg-blue-500 h-2 rounded-full transition-all"
                style={{ width: `${downloadProgress}%` }}
              />
            </div>
          )}
        </div>
      )}

      {/* Update ready to install */}
      {updateReady && (
        <div className="space-y-3">
          <div className="flex items-center gap-2">
            <CheckCircle className="w-5 h-5 text-green-400" />
            <span className="text-white font-medium">Update Ready</span>
          </div>
          <p className="text-sm text-gray-400">
            Restart to apply the update.
          </p>
          <button
            onClick={installUpdate}
            className="w-full px-4 py-2 bg-green-600 hover:bg-green-500 text-white rounded-lg font-medium transition-colors"
          >
            Restart & Update
          </button>
        </div>
      )}
    </div>
  )
}
