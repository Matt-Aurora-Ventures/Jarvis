import React from 'react'
import { Home, LineChart, Wrench, BarChart2, Settings } from 'lucide-react'

const NAV_ITEMS = [
  { id: 'overview', icon: Home, label: 'Overview' },
  { id: 'trading', icon: LineChart, label: 'Trading' },
  { id: 'tools', icon: Wrench, label: 'Tools' },
  { id: 'analytics', icon: BarChart2, label: 'Analytics' },
  { id: 'settings', icon: Settings, label: 'Settings' },
]

/**
 * Sidebar - Vertical navigation sidebar
 */
function Sidebar({ activeView, onViewChange, items = NAV_ITEMS }) {
  return (
    <div className="sidebar">
      {items.map(item => (
        <div
          key={item.id}
          className={`sidebar-item ${activeView === item.id ? 'active' : ''}`}
          onClick={() => onViewChange(item.id)}
          title={item.label}
        >
          <item.icon size={20} />
        </div>
      ))}
    </div>
  )
}

export default Sidebar
