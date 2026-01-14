import React from 'react'
import { PriceAlerts } from '../components/alerts'

/**
 * Alerts Page - Price Alerts Management
 * Allows users to create and manage price alerts for tokens
 */
export default function Alerts() {
  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-900 via-gray-800 to-gray-900 p-6">
      <div className="max-w-7xl mx-auto">
        <PriceAlerts />
      </div>
    </div>
  )
}
