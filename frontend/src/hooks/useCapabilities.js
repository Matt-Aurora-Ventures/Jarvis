import { useState, useEffect, useCallback } from 'react'

/**
 * Hook to probe API endpoints and detect available capabilities.
 * Caches results in sessionStorage to avoid repeated probing.
 */

const ENDPOINTS = [
  { key: 'chat', path: '/api/chat', method: 'GET' },
  { key: 'research', path: '/api/research', method: 'OPTIONS' },
  { key: 'voice', path: '/api/voice/status', method: 'GET' },
  { key: 'trading', path: '/api/trading/positions', method: 'GET' },
  { key: 'wallet', path: '/api/wallet/balance', method: 'GET' },
  { key: 'status', path: '/api/status', method: 'GET' },
  { key: 'settings', path: '/api/settings/keys', method: 'GET' },
  { key: 'sniper', path: '/api/sniper/config', method: 'GET' },
  { key: 'costs', path: '/api/costs/tts', method: 'GET' },
]

const CACHE_KEY = 'lifeos_capabilities'
const CACHE_TTL = 5 * 60 * 1000 // 5 minutes

function useCapabilities() {
  const [capabilities, setCapabilities] = useState(() => {
    // Try to load from cache
    const cached = sessionStorage.getItem(CACHE_KEY)
    if (cached) {
      try {
        const { data, timestamp } = JSON.parse(cached)
        if (Date.now() - timestamp < CACHE_TTL) {
          return data
        }
      } catch (e) {
        // Invalid cache, ignore
      }
    }
    // Default: all unknown
    return ENDPOINTS.reduce((acc, ep) => ({ ...acc, [ep.key]: 'unknown' }), {})
  })

  const [isProbing, setIsProbing] = useState(false)
  const [lastProbed, setLastProbed] = useState(null)

  const probe = useCallback(async () => {
    setIsProbing(true)
    
    const results = {}
    
    await Promise.all(
      ENDPOINTS.map(async ({ key, path, method }) => {
        try {
          const controller = new AbortController()
          const timeout = setTimeout(() => controller.abort(), 3000)
          
          const response = await fetch(path, {
            method,
            signal: controller.signal,
          })
          
          clearTimeout(timeout)
          
          if (response.ok || response.status === 401 || response.status === 403) {
            // Endpoint exists (even if auth required)
            results[key] = 'available'
          } else if (response.status === 404) {
            results[key] = 'unavailable'
          } else {
            results[key] = 'error'
          }
        } catch (error) {
          if (error.name === 'AbortError') {
            results[key] = 'timeout'
          } else {
            results[key] = 'unavailable'
          }
        }
      })
    )

    // Cache the results
    const now = Date.now()
    sessionStorage.setItem(CACHE_KEY, JSON.stringify({
      data: results,
      timestamp: now,
    }))

    setCapabilities(results)
    setLastProbed(now)
    setIsProbing(false)
    
    return results
  }, [])

  // Probe on mount if no valid cache
  useEffect(() => {
    const cached = sessionStorage.getItem(CACHE_KEY)
    if (cached) {
      try {
        const { timestamp } = JSON.parse(cached)
        if (Date.now() - timestamp < CACHE_TTL) {
          return // Valid cache exists
        }
      } catch (e) {
        // Invalid cache, probe
      }
    }
    probe()
  }, [probe])

  const isAvailable = useCallback((key) => {
    return capabilities[key] === 'available'
  }, [capabilities])

  const availableCount = Object.values(capabilities).filter(v => v === 'available').length
  const totalCount = ENDPOINTS.length

  return {
    capabilities,
    isProbing,
    lastProbed,
    probe,
    isAvailable,
    availableCount,
    totalCount,
    healthPercent: Math.round((availableCount / totalCount) * 100),
  }
}

export default useCapabilities
