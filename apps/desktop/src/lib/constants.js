// Application constants

// API endpoints
export const API_BASE = ''

// Default tokens
export const DEFAULT_TOKEN = {
  mint: 'So11111111111111111111111111111111111111112',
  symbol: 'SOL',
  name: 'Solana',
}

export const USDC_TOKEN = {
  mint: 'EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v',
  symbol: 'USDC',
  name: 'USD Coin',
}

// Timeframes for charts
export const TIMEFRAMES = [
  { label: '1m', value: '1m' },
  { label: '5m', value: '5m' },
  { label: '15m', value: '15m' },
  { label: '1H', value: '1H' },
  { label: '4H', value: '4H' },
  { label: '1D', value: '1D' },
]

// Trading status
export const TRADING_STATUS = {
  IDLE: 'idle',
  SCANNING: 'scanning',
  ENTERING: 'entering',
  MONITORING: 'monitoring',
  EXITING: 'exiting',
  PAUSED: 'paused',
}

// Position exit reasons
export const EXIT_REASONS = {
  TAKE_PROFIT: 'TAKE_PROFIT',
  STOP_LOSS: 'STOP_LOSS',
  MANUAL_EXIT: 'MANUAL_EXIT',
  TIMEOUT: 'TIMEOUT',
  TRAILING_STOP: 'TRAILING_STOP',
}

// Risk levels for tokens
export const RISK_LEVELS = {
  LOW: 'low',
  MEDIUM: 'medium',
  HIGH: 'high',
}

// Polling intervals (ms)
export const POLLING_INTERVALS = {
  WALLET: 30000,      // 30 seconds
  POSITION: 5000,     // 5 seconds
  SNIPER: 10000,      // 10 seconds
  PRICE: 2000,        // 2 seconds
  STATS: 60000,       // 1 minute
}

// Chart colors
export const CHART_COLORS = {
  UP: '#10B981',
  DOWN: '#EF4444',
  GRID: '#F3F4F6',
  CROSSHAIR: '#6366F1',
}

// Navigation items
export const NAV_ITEMS = [
  { id: 'overview', label: 'Overview', path: '/' },
  { id: 'trading', label: 'Trading', path: '/trading' },
  { id: 'chat', label: 'Chat', path: '/chat' },
  { id: 'research', label: 'Research', path: '/research' },
  { id: 'settings', label: 'Settings', path: '/settings' },
]

// External links
export const EXTERNAL_LINKS = {
  DEXSCREENER: (pair) => `https://dexscreener.com/solana/${pair}`,
  BIRDEYE: (mint) => `https://birdeye.so/token/${mint}`,
  SOLSCAN: (address) => `https://solscan.io/account/${address}`,
  JUPITER: (mint) => `https://jup.ag/swap/SOL-${mint}`,
}
