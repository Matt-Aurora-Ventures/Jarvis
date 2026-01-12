/**
 * API Client - Centralized fetch wrapper with timeout, retry, and error handling
 */

const API_BASE = ''
const DEFAULT_TIMEOUT = 30000 // 30 seconds
const DEFAULT_RETRIES = 3
const RETRY_DELAY = 1000 // 1 second

/**
 * Custom API error class with error codes
 */
export class ApiError extends Error {
  constructor(message, status, data, code = null) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.data = data
    this.code = code || data?.error?.code || 'UNKNOWN'
  }

  get isTimeout() {
    return this.status === 408 || this.code === 'TIMEOUT'
  }

  get isNetworkError() {
    return this.status === 0 || this.code === 'NETWORK_ERROR'
  }

  get isRateLimited() {
    return this.status === 429 || this.code === 'PROV_002'
  }

  get isServerError() {
    return this.status >= 500
  }

  get isRetryable() {
    return this.isTimeout || this.isNetworkError || this.isRateLimited || this.isServerError
  }
}

/**
 * Sleep utility for retry delays
 */
function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms))
}

/**
 * Main request function with timeout and retry
 */
async function request(endpoint, options = {}) {
  const {
    method = 'GET',
    body,
    headers = {},
    timeout = DEFAULT_TIMEOUT,
    retries = DEFAULT_RETRIES,
    retryDelay = RETRY_DELAY,
    onRetry,
    ...rest
  } = options

  let lastError = null

  for (let attempt = 0; attempt <= retries; attempt++) {
    const controller = new AbortController()
    const timeoutId = setTimeout(() => controller.abort(), timeout)

    try {
      const response = await fetch(`${API_BASE}${endpoint}`, {
        method,
        headers: {
          'Content-Type': 'application/json',
          ...headers,
        },
        body: body ? JSON.stringify(body) : undefined,
        signal: controller.signal,
        ...rest,
      })

      clearTimeout(timeoutId)

      // Parse response
      const contentType = response.headers.get('content-type')
      let data = null

      if (contentType?.includes('application/json')) {
        data = await response.json()
      } else {
        data = await response.text()
      }

      // Handle error responses
      if (!response.ok) {
        const error = new ApiError(
          data?.error?.message || data?.message || `HTTP ${response.status}`,
          response.status,
          data,
          data?.error?.code
        )

        // Don't retry on client errors (4xx) except rate limiting
        if (response.status >= 400 && response.status < 500 && response.status !== 429) {
          throw error
        }

        // Retry on server errors and rate limiting
        lastError = error
        if (attempt < retries) {
          const delay = response.status === 429
            ? parseInt(response.headers.get('retry-after') || retryDelay) * 1000
            : retryDelay * Math.pow(2, attempt) // Exponential backoff

          onRetry?.(attempt + 1, delay, error)
          await sleep(delay)
          continue
        }
        throw error
      }

      return data
    } catch (error) {
      clearTimeout(timeoutId)

      // Handle abort (timeout)
      if (error.name === 'AbortError') {
        lastError = new ApiError('Request timed out', 408, {}, 'TIMEOUT')
        if (attempt < retries) {
          const delay = retryDelay * Math.pow(2, attempt)
          onRetry?.(attempt + 1, delay, lastError)
          await sleep(delay)
          continue
        }
        throw lastError
      }

      // Re-throw ApiErrors
      if (error instanceof ApiError) {
        throw error
      }

      // Handle network errors
      lastError = new ApiError('Network error', 0, { originalError: error.message }, 'NETWORK_ERROR')
      if (attempt < retries) {
        const delay = retryDelay * Math.pow(2, attempt)
        onRetry?.(attempt + 1, delay, lastError)
        await sleep(delay)
        continue
      }
      throw lastError
    }
  }

  throw lastError || new ApiError('Request failed', 0, {}, 'UNKNOWN')
}

// Convenience methods
export const api = {
  get: (endpoint, options) => request(endpoint, { ...options, method: 'GET' }),
  post: (endpoint, body, options) => request(endpoint, { ...options, method: 'POST', body }),
  put: (endpoint, body, options) => request(endpoint, { ...options, method: 'PUT', body }),
  patch: (endpoint, body, options) => request(endpoint, { ...options, method: 'PATCH', body }),
  delete: (endpoint, options) => request(endpoint, { ...options, method: 'DELETE' }),
}

// Specific API endpoints
export const jarvisApi = {
  // Wallet
  getWalletStatus: () => api.get('/api/wallet/status'),

  // Sniper
  getSniperStatus: () => api.get('/api/sniper/status'),
  startSniper: () => api.post('/api/sniper/start'),
  stopSniper: () => api.post('/api/sniper/stop'),

  // Jarvis Chat
  getJarvisStatus: () => api.get('/api/jarvis/status'),
  sendChat: (message) => api.post('/api/jarvis/chat', { message }),
  chat: (message) => api.post('/api/jarvis/chat', { message }),

  // Voice
  getVoiceStatus: () => api.get('/api/voice/status'),
  startVoice: () => api.post('/api/voice/start'),
  stopVoice: () => api.post('/api/voice/stop'),
  testVoice: (text) => api.post('/api/voice/test', { text }),

  // Position
  getActivePosition: () => api.get('/api/position/active'),
  exitPosition: (reason) => api.post('/api/position/exit', { reason }),

  // Trading
  getTradingStats: () => api.get('/api/trading/stats'),
  executeTrade: (trade) => api.post('/api/trading/execute', trade),
  getPositions: () => api.get('/api/trading/positions'),

  // Market
  getMarketIndicators: () => api.get('/api/market/indicators'),
  getSolanaTokens: () => api.get('/api/trading/solana/tokens'),

  // Tools
  getTokenInfo: (mint) => api.get(`/api/tools/token/${mint}`),
  getRugCheck: (mint) => api.get(`/api/tools/rugcheck/${mint}`),

  // System
  getStats: () => api.get('/api/stats'),
  getHealth: () => api.get('/api/health'),
  getHealthComponents: () => api.get('/api/health/components'),
}

/**
 * Format API error for display
 */
export function formatApiError(error) {
  if (!(error instanceof ApiError)) {
    return 'Something went wrong. Please try again.'
  }

  switch (error.code) {
    case 'TIMEOUT':
      return 'Request timed out. Please try again.'
    case 'NETWORK_ERROR':
      return 'Network error. Check your connection.'
    case 'AUTH_001':
      return 'Please sign in to continue.'
    case 'AUTH_002':
    case 'AUTH_003':
      return 'Session expired. Please sign in again.'
    case 'PROV_002':
      return 'Too many requests. Please wait a moment.'
    case 'PROV_001':
      return 'Service temporarily unavailable.'
    case 'VAL_001':
    case 'VAL_002':
      return error.message || 'Invalid request. Please check your input.'
    case 'TRADE_001':
      return 'Trade execution failed. Please try again.'
    case 'TRADE_002':
      return 'Insufficient balance for this trade.'
    case 'VOICE_001':
      return 'Voice system not available.'
    default:
      return error.message || 'An error occurred.'
  }
}

export default api
