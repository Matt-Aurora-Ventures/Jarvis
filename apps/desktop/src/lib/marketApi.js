/**
 * Market API client for Jarvis frontend
 * Handles all market data fetching with caching and error handling
 */

const API_BASE = process.env.VITE_API_URL || 'http://localhost:8000'
const CACHE_TTL = 30000 // 30 seconds

// Simple in-memory cache
const cache = new Map()

function getCached(key) {
  const entry = cache.get(key)
  if (!entry) return null
  if (Date.now() - entry.timestamp > CACHE_TTL) {
    cache.delete(key)
    return null
  }
  return entry.data
}

function setCache(key, data) {
  cache.set(key, { data, timestamp: Date.now() })
}

async function fetchWithRetry(url, options = {}, retries = 3) {
  for (let i = 0; i < retries; i++) {
    try {
      const response = await fetch(url, {
        ...options,
        headers: {
          'Content-Type': 'application/json',
          ...options.headers,
        },
      })

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`)
      }

      return await response.json()
    } catch (error) {
      if (i === retries - 1) throw error
      await new Promise(r => setTimeout(r, 1000 * (i + 1)))
    }
  }
}

export const marketApi = {
  /**
   * Get SOL price
   */
  async getSolPrice() {
    const cached = getCached('sol_price')
    if (cached) return cached

    try {
      const data = await fetchWithRetry(`${API_BASE}/api/price/sol`)
      setCache('sol_price', data.price)
      return data.price
    } catch (error) {
      console.error('Failed to fetch SOL price:', error)
      return null
    }
  },

  /**
   * Get token price by address
   */
  async getTokenPrice(address) {
    if (!address) return null

    const cached = getCached(`price_${address}`)
    if (cached) return cached

    try {
      const data = await fetchWithRetry(`${API_BASE}/api/price/${address}`)
      setCache(`price_${address}`, data)
      return data
    } catch (error) {
      console.error(`Failed to fetch price for ${address}:`, error)
      return null
    }
  },

  /**
   * Get trending tokens
   */
  async getTrending(limit = 10) {
    const cached = getCached('trending')
    if (cached) return cached

    try {
      const data = await fetchWithRetry(`${API_BASE}/api/trending?limit=${limit}`)
      const tokens = data.tokens || data
      setCache('trending', tokens)
      return tokens
    } catch (error) {
      console.error('Failed to fetch trending:', error)
      return []
    }
  },

  /**
   * Get top gainers
   */
  async getGainers(limit = 10) {
    const cached = getCached('gainers')
    if (cached) return cached

    try {
      const data = await fetchWithRetry(`${API_BASE}/api/gainers?limit=${limit}`)
      const tokens = data.tokens || data
      setCache('gainers', tokens)
      return tokens
    } catch (error) {
      console.error('Failed to fetch gainers:', error)
      return []
    }
  },

  /**
   * Get market overview
   */
  async getMarketOverview() {
    const cached = getCached('overview')
    if (cached) return cached

    try {
      const data = await fetchWithRetry(`${API_BASE}/api/market/overview`)
      setCache('overview', data)
      return data
    } catch (error) {
      console.error('Failed to fetch market overview:', error)
      return null
    }
  },

  /**
   * Get wallet balance
   */
  async getWallet() {
    try {
      const data = await fetchWithRetry(`${API_BASE}/api/wallet`)
      return data
    } catch (error) {
      console.error('Failed to fetch wallet:', error)
      return null
    }
  },

  /**
   * Get positions
   */
  async getPositions() {
    try {
      const data = await fetchWithRetry(`${API_BASE}/api/positions`)
      return data.positions || data
    } catch (error) {
      console.error('Failed to fetch positions:', error)
      return []
    }
  },

  /**
   * Execute trade
   */
  async executeTrade(params) {
    const { action, token, amount, slippage = 1 } = params

    try {
      const data = await fetchWithRetry(`${API_BASE}/api/trade`, {
        method: 'POST',
        body: JSON.stringify({
          action,
          token,
          amount,
          slippage,
        }),
      })

      return { success: true, data }
    } catch (error) {
      console.error('Trade execution failed:', error)
      return { success: false, error: error.message }
    }
  },

  /**
   * Get sniper status
   */
  async getSniperStatus() {
    try {
      const data = await fetchWithRetry(`${API_BASE}/api/sniper/status`)
      return data
    } catch (error) {
      console.error('Failed to fetch sniper status:', error)
      return null
    }
  },

  /**
   * Search tokens
   */
  async searchTokens(query) {
    if (!query || query.length < 2) return []

    try {
      const data = await fetchWithRetry(`${API_BASE}/api/search?q=${encodeURIComponent(query)}`)
      return data.tokens || data
    } catch (error) {
      console.error('Token search failed:', error)
      return []
    }
  },

  /**
   * Clear all cache
   */
  clearCache() {
    cache.clear()
  },
}

export default marketApi
