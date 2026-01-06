// API Client - Centralized fetch wrapper with error handling
const API_BASE = ''

class ApiError extends Error {
  constructor(message, status, data) {
    super(message)
    this.status = status
    this.data = data
    this.name = 'ApiError'
  }
}

async function request(endpoint, options = {}) {
  const {
    method = 'GET',
    body,
    headers = {},
    timeout = 10000,
    ...rest
  } = options

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

    if (!response.ok) {
      const data = await response.json().catch(() => ({}))
      throw new ApiError(
        data.message || `HTTP ${response.status}`,
        response.status,
        data
      )
    }

    return response.json()
  } catch (error) {
    clearTimeout(timeoutId)
    
    if (error.name === 'AbortError') {
      throw new ApiError('Request timeout', 408, {})
    }
    
    throw error
  }
}

// Convenience methods
export const api = {
  get: (endpoint, options) => request(endpoint, { ...options, method: 'GET' }),
  post: (endpoint, body, options) => request(endpoint, { ...options, method: 'POST', body }),
  put: (endpoint, body, options) => request(endpoint, { ...options, method: 'PUT', body }),
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
  
  // Jarvis
  getJarvisStatus: () => api.get('/api/jarvis/status'),
  sendChat: (message) => api.post('/api/jarvis/chat', { message }),
  
  // Position
  getActivePosition: () => api.get('/api/position/active'),
  exitPosition: (reason) => api.post('/api/position/exit', { reason }),
  
  // Tools
  getTokenInfo: (mint) => api.get(`/api/tools/token/${mint}`),
  getRugCheck: (mint) => api.get(`/api/tools/rugcheck/${mint}`),
  
  // Stats
  getStats: () => api.get('/api/stats'),
  getHealth: () => api.get('/api/health'),
}

export default api
