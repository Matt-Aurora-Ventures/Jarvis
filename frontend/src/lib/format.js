// Formatting utilities

/**
 * Format USD currency
 */
export function formatUSD(value, options = {}) {
  const { minimumFractionDigits = 2, maximumFractionDigits = 2, compact = false } = options
  
  if (value === null || value === undefined) return '$0.00'
  
  if (compact && Math.abs(value) >= 1000) {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      notation: 'compact',
      maximumFractionDigits: 1,
    }).format(value)
  }
  
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits,
    maximumFractionDigits,
  }).format(value)
}

/**
 * Format crypto price (8 decimals for small values)
 */
export function formatCryptoPrice(value) {
  if (value === null || value === undefined) return '$0.00'
  
  if (value < 0.0001) {
    return `$${value.toFixed(8)}`
  }
  if (value < 1) {
    return `$${value.toFixed(6)}`
  }
  return formatUSD(value)
}

/**
 * Format percentage
 */
export function formatPercent(value, options = {}) {
  const { showSign = true, decimals = 2 } = options
  
  if (value === null || value === undefined) return '0%'
  
  const sign = showSign && value > 0 ? '+' : ''
  return `${sign}${value.toFixed(decimals)}%`
}

/**
 * Format large numbers with K, M, B suffixes
 */
export function formatCompact(value) {
  if (value === null || value === undefined) return '0'
  
  return new Intl.NumberFormat('en-US', {
    notation: 'compact',
    maximumFractionDigits: 1,
  }).format(value)
}

/**
 * Format SOL amount
 */
export function formatSOL(value, decimals = 4) {
  if (value === null || value === undefined) return '0 SOL'
  return `${value.toFixed(decimals)} SOL`
}

/**
 * Format token amount
 */
export function formatTokenAmount(value, symbol = '', decimals = 4) {
  if (value === null || value === undefined) return '0'
  
  const formatted = new Intl.NumberFormat('en-US', {
    maximumFractionDigits: decimals,
  }).format(value)
  
  return symbol ? `${formatted} ${symbol}` : formatted
}

/**
 * Format time duration
 */
export function formatDuration(minutes) {
  if (!minutes) return '0m'
  
  if (minutes < 60) {
    return `${Math.round(minutes)}m`
  }
  
  const hours = Math.floor(minutes / 60)
  const mins = Math.round(minutes % 60)
  
  if (hours < 24) {
    return mins > 0 ? `${hours}h ${mins}m` : `${hours}h`
  }
  
  const days = Math.floor(hours / 24)
  const remainingHours = hours % 24
  return remainingHours > 0 ? `${days}d ${remainingHours}h` : `${days}d`
}

/**
 * Truncate address
 */
export function truncateAddress(address, chars = 4) {
  if (!address) return ''
  return `${address.slice(0, chars)}...${address.slice(-chars)}`
}

/**
 * Format relative time
 */
export function formatRelativeTime(date) {
  const now = new Date()
  const then = new Date(date)
  const diff = now - then
  
  const seconds = Math.floor(diff / 1000)
  const minutes = Math.floor(seconds / 60)
  const hours = Math.floor(minutes / 60)
  const days = Math.floor(hours / 24)
  
  if (seconds < 60) return 'just now'
  if (minutes < 60) return `${minutes}m ago`
  if (hours < 24) return `${hours}h ago`
  if (days < 7) return `${days}d ago`
  
  return then.toLocaleDateString()
}
