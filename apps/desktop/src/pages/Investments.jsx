import React, { useState } from 'react'
import InvestmentDashboard from '../components/investments/InvestmentDashboard'
import PerpsSniper from '../components/perps/PerpsSniper'

const TABS = [
  {
    id: 'basket',
    label: 'Alvara Basket',
    description: 'Grok-managed EVM portfolio + cross-chain yield',
    icon: (
      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M21 7.5l-9-5.25L3 7.5m18 0l-9 5.25m9-5.25v9l-9 5.25M3 7.5l9 5.25M3 7.5v9l9 5.25m0-9v9" />
      </svg>
    ),
  },
  {
    id: 'perps',
    label: 'Perps Sniper',
    description: 'Autonomous Jupiter Perps trading (SOL/BTC/ETH)',
    icon: (
      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 3v11.25A2.25 2.25 0 006 16.5h2.25M3.75 3h-1.5m1.5 0h16.5m0 0h1.5m-1.5 0v11.25A2.25 2.25 0 0118 16.5h-2.25m-7.5 0h7.5m-7.5 0l-1 3m8.5-3l1 3m0 0l.5 1.5m-.5-1.5h-9.5m0 0l-.5 1.5M9 11.25v1.5M12 9v3.75m3-6v6" />
      </svg>
    ),
  },
]

export default function Investments() {
  const [activeTab, setActiveTab] = useState('basket')

  return (
    <div className="min-h-screen bg-gray-950">
      {/* ===== TAB SELECTOR ===== */}
      <div className="bg-gray-900 border-b border-gray-800">
        <div className="max-w-7xl mx-auto px-6">
          <div className="flex gap-1 pt-4">
            {TABS.map(tab => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`flex items-center gap-2 px-5 py-2.5 text-sm font-medium rounded-t-lg border-t border-l border-r transition-all ${
                  activeTab === tab.id
                    ? 'bg-gray-950 border-gray-700 text-white'
                    : 'bg-transparent border-transparent text-gray-500 hover:text-gray-300 hover:bg-gray-800/50'
                }`}
              >
                {tab.icon}
                {tab.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* ===== TAB CONTENT ===== */}
      {activeTab === 'basket' && <InvestmentDashboard />}
      {activeTab === 'perps' && <PerpsSniper />}
    </div>
  )
}
