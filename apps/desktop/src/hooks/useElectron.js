import { useState, useEffect, useCallback } from 'react'

/**
 * Hook for interacting with Electron APIs
 * Returns null for all values when running in browser
 */
export default function useElectron() {
  const [isElectron, setIsElectron] = useState(false)
  const [platform, setPlatform] = useState(null)
  const [version, setVersion] = useState(null)
  const [backendStatus, setBackendStatus] = useState({ running: false, pid: null })

  useEffect(() => {
    const hasElectron = !!window.electronAPI
    setIsElectron(hasElectron)

    if (hasElectron) {
      setPlatform(window.electronAPI.getPlatform())
      window.electronAPI.getVersion().then(setVersion)
      window.electronAPI.getBackendStatus().then(setBackendStatus)

      // Poll backend status
      const interval = setInterval(async () => {
        const status = await window.electronAPI.getBackendStatus()
        setBackendStatus(status)
      }, 5000)

      return () => clearInterval(interval)
    }
  }, [])

  const startBackend = useCallback(async () => {
    if (!window.electronAPI) return { success: false, error: 'Not in Electron' }
    return await window.electronAPI.startBackend()
  }, [])

  const stopBackend = useCallback(async () => {
    if (!window.electronAPI) return { success: false, error: 'Not in Electron' }
    return await window.electronAPI.stopBackend()
  }, [])

  const restartBackend = useCallback(async () => {
    if (!window.electronAPI) return { success: false, error: 'Not in Electron' }
    return await window.electronAPI.restartBackend()
  }, [])

  const openExternal = useCallback(async (url) => {
    if (!window.electronAPI) {
      window.open(url, '_blank')
      return
    }
    return await window.electronAPI.openExternal(url)
  }, [])

  const showNotification = useCallback(async (title, body) => {
    if (!window.electronAPI) {
      // Fallback to browser notification
      if (Notification.permission === 'granted') {
        new Notification(title, { body })
      }
      return
    }
    return await window.electronAPI.showNotification(title, body)
  }, [])

  const sendToTelegram = useCallback(async (message) => {
    if (!window.electronAPI) return { success: false, error: 'Not in Electron' }
    return await window.electronAPI.sendTelegramMessage(message)
  }, [])

  const getSetting = useCallback(async (key, defaultValue = null) => {
    if (!window.electronAPI) {
      return localStorage.getItem(`jarvis_${key}`) || defaultValue
    }
    const value = await window.electronAPI.getSetting(key)
    return value ?? defaultValue
  }, [])

  const setSetting = useCallback(async (key, value) => {
    if (!window.electronAPI) {
      localStorage.setItem(`jarvis_${key}`, value)
      return true
    }
    return await window.electronAPI.setSetting(key, value)
  }, [])

  const minimize = useCallback(async () => {
    if (!window.electronAPI) return
    return await window.electronAPI.minimize()
  }, [])

  const maximize = useCallback(async () => {
    if (!window.electronAPI) return
    return await window.electronAPI.maximize()
  }, [])

  const close = useCallback(async () => {
    if (!window.electronAPI) return
    return await window.electronAPI.close()
  }, [])

  return {
    isElectron,
    platform,
    version,
    backendStatus,
    startBackend,
    stopBackend,
    restartBackend,
    openExternal,
    showNotification,
    sendToTelegram,
    getSetting,
    setSetting,
    minimize,
    maximize,
    close,
  }
}

// Platform display names
export const platformNames = {
  win32: 'Windows',
  darwin: 'macOS',
  linux: 'Linux',
}
