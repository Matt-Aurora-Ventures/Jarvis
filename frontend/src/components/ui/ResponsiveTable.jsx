import React from 'react'
import { useIsMobile } from '../../hooks/useMediaQuery'

/**
 * Responsive Table Component
 * Shows as cards on mobile, traditional table on desktop
 */
export default function ResponsiveTable({
  columns,
  data,
  keyField = 'id',
  emptyMessage = 'No data available',
  onRowClick,
  loading = false,
  className = '',
}) {
  const isMobile = useIsMobile()

  // Loading skeleton
  if (loading) {
    return (
      <div className={`animate-pulse space-y-3 ${className}`}>
        {[1, 2, 3].map((i) => (
          <div
            key={i}
            className="h-16 bg-gray-700/50 rounded-lg"
          />
        ))}
      </div>
    )
  }

  // Empty state
  if (!data || data.length === 0) {
    return (
      <div className={`text-center py-8 text-gray-400 ${className}`}>
        {emptyMessage}
      </div>
    )
  }

  // Mobile Card View
  if (isMobile) {
    return (
      <div className={`space-y-3 ${className}`}>
        {data.map((row, rowIndex) => (
          <div
            key={row[keyField] || rowIndex}
            onClick={() => onRowClick?.(row)}
            className={`
              bg-gray-800/50 rounded-lg border border-gray-700 p-3
              ${onRowClick ? 'cursor-pointer hover:bg-gray-700/50 active:scale-[0.98]' : ''}
              transition-all duration-200
            `}
          >
            {columns.map((column, colIndex) => {
              const value = column.accessor
                ? typeof column.accessor === 'function'
                  ? column.accessor(row)
                  : row[column.accessor]
                : null

              // Skip columns marked as hidden on mobile
              if (column.hideMobile) return null

              return (
                <div
                  key={column.key || colIndex}
                  className={`
                    flex items-center justify-between py-1.5
                    ${colIndex > 0 ? 'border-t border-gray-700/50' : ''}
                  `}
                >
                  <span className="text-xs text-gray-400 flex-shrink-0 mr-3">
                    {column.header}
                  </span>
                  <span className="text-sm text-white text-right min-w-0 truncate">
                    {column.cell ? column.cell(row, value) : value}
                  </span>
                </div>
              )
            })}
          </div>
        ))}
      </div>
    )
  }

  // Desktop Table View
  return (
    <div className={`overflow-x-auto ${className}`}>
      <table className="w-full">
        <thead>
          <tr className="border-b border-gray-700">
            {columns.map((column, index) => (
              <th
                key={column.key || index}
                className={`
                  px-4 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider
                  ${column.align === 'center' ? 'text-center' : ''}
                  ${column.align === 'right' ? 'text-right' : ''}
                  ${column.width || ''}
                `}
              >
                {column.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-700/50">
          {data.map((row, rowIndex) => (
            <tr
              key={row[keyField] || rowIndex}
              onClick={() => onRowClick?.(row)}
              className={`
                ${onRowClick ? 'cursor-pointer hover:bg-gray-700/30' : ''}
                transition-colors
              `}
            >
              {columns.map((column, colIndex) => {
                const value = column.accessor
                  ? typeof column.accessor === 'function'
                    ? column.accessor(row)
                    : row[column.accessor]
                  : null

                return (
                  <td
                    key={column.key || colIndex}
                    className={`
                      px-4 py-3 text-sm text-white whitespace-nowrap
                      ${column.align === 'center' ? 'text-center' : ''}
                      ${column.align === 'right' ? 'text-right' : ''}
                    `}
                  >
                    {column.cell ? column.cell(row, value) : value}
                  </td>
                )
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

/**
 * Table Column Helper
 * Creates standardized column definitions
 */
export function createColumn({
  key,
  header,
  accessor,
  cell,
  align = 'left',
  width,
  hideMobile = false,
}) {
  return { key, header, accessor, cell, align, width, hideMobile }
}

/**
 * Common Cell Renderers
 */
export const cellRenderers = {
  // Currency with color
  currency: (value, decimals = 2) => {
    const num = parseFloat(value) || 0
    const formatted = new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: decimals,
      maximumFractionDigits: decimals,
    }).format(Math.abs(num))

    return (
      <span className={num >= 0 ? 'text-green-400' : 'text-red-400'}>
        {num >= 0 ? '+' : '-'}{formatted}
      </span>
    )
  },

  // Percentage with color
  percentage: (value, decimals = 2) => {
    const num = parseFloat(value) || 0
    return (
      <span className={num >= 0 ? 'text-green-400' : 'text-red-400'}>
        {num >= 0 ? '+' : ''}{num.toFixed(decimals)}%
      </span>
    )
  },

  // Badge
  badge: (value, colorMap = {}) => {
    const color = colorMap[value] || 'gray'
    const colorClasses = {
      green: 'bg-green-500/20 text-green-400',
      red: 'bg-red-500/20 text-red-400',
      yellow: 'bg-yellow-500/20 text-yellow-400',
      blue: 'bg-blue-500/20 text-blue-400',
      purple: 'bg-purple-500/20 text-purple-400',
      gray: 'bg-gray-500/20 text-gray-400',
    }

    return (
      <span className={`px-2 py-0.5 rounded text-xs font-medium ${colorClasses[color]}`}>
        {value}
      </span>
    )
  },

  // Timestamp
  timestamp: (value, format = 'datetime') => {
    if (!value) return '-'
    const date = new Date(value)

    if (format === 'date') {
      return date.toLocaleDateString()
    }
    if (format === 'time') {
      return date.toLocaleTimeString()
    }
    if (format === 'relative') {
      const now = new Date()
      const diff = now - date
      const minutes = Math.floor(diff / 60000)
      const hours = Math.floor(diff / 3600000)
      const days = Math.floor(diff / 86400000)

      if (minutes < 1) return 'Just now'
      if (minutes < 60) return `${minutes}m ago`
      if (hours < 24) return `${hours}h ago`
      return `${days}d ago`
    }
    return date.toLocaleString()
  },

  // Truncated text
  truncate: (value, maxLength = 20) => {
    if (!value || value.length <= maxLength) return value
    return `${value.slice(0, maxLength)}...`
  },

  // Token/Address
  address: (value, chars = 4) => {
    if (!value || value.length <= chars * 2 + 3) return value
    return `${value.slice(0, chars)}...${value.slice(-chars)}`
  },
}
