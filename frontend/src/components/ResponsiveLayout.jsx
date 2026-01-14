import React from 'react'
import { Outlet, NavLink } from 'react-router-dom'
import { Home, MessageCircle, Settings, Search, Mic, TrendingUp, Bot, Map, Bell } from 'lucide-react'
import useJarvisStore from '../stores/jarvisStore'
import MobileNav from './MobileNav'

/**
 * Navigation Links - shared between desktop and mobile
 */
const NAV_LINKS = [
  { path: '/', label: 'Dashboard', icon: Home },
  { path: '/chat', label: 'Chat', icon: MessageCircle },
  { path: '/voice', label: 'Voice', icon: Mic },
  { path: '/trading', label: 'Trading', icon: TrendingUp },
  { path: '/alerts', label: 'Alerts', icon: Bell },
  { path: '/research', label: 'Research', icon: Search },
  { path: '/roadmap', label: 'Roadmap', icon: Map },
  { path: '/settings', label: 'Settings', icon: Settings },
]

/**
 * Desktop Navigation Component
 */
function DesktopNav() {
  const { isListening, status } = useJarvisStore()

  return (
    <div className="top-nav hidden md:flex">
      {/* Brand */}
      <div className="nav-brand">
        <Bot size={24} />
        <span>Jarvis LifeOS</span>
      </div>

      {/* Navigation Links */}
      <nav className="flex gap-2 flex-1 justify-center flex-wrap">
        {NAV_LINKS.map(({ path, label, icon: Icon }) => (
          <NavLink
            key={path}
            to={path}
            className={({ isActive }) =>
              `btn ${isActive ? 'btn-primary' : 'btn-ghost'}`
            }
          >
            <Icon size={18} />
            <span className="hidden lg:inline">{label}</span>
          </NavLink>
        ))}
      </nav>

      {/* Status Indicators */}
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2 text-sm text-gray-400">
          <div
            className={`w-2 h-2 rounded-full ${
              status.daemon === 'running' ? 'bg-green-500' : 'bg-red-500'
            }`}
          />
          <span className="hidden xl:inline">
            {status.daemon === 'running' ? 'Online' : 'Offline'}
          </span>
        </div>
        <div className="flex items-center gap-2 text-sm text-gray-400">
          <div
            className={`w-2 h-2 rounded-full ${
              isListening ? 'bg-cyan-500 animate-pulse' : 'bg-gray-500'
            }`}
          />
          <span className="hidden xl:inline">
            {isListening ? 'Listening' : 'Idle'}
          </span>
        </div>
      </div>
    </div>
  )
}

/**
 * Bottom Tab Bar for Mobile
 */
function BottomTabBar() {
  const quickLinks = [
    { path: '/', label: 'Home', icon: Home },
    { path: '/trading', label: 'Trade', icon: TrendingUp },
    { path: '/chat', label: 'Chat', icon: MessageCircle },
    { path: '/alerts', label: 'Alerts', icon: Bell },
    { path: '/settings', label: 'More', icon: Settings },
  ]

  return (
    <nav className="md:hidden fixed bottom-0 left-0 right-0 z-40 bg-gray-900/95 backdrop-blur-sm border-t border-gray-800 safe-area-bottom">
      <div className="flex justify-around items-center py-2">
        {quickLinks.map(({ path, label, icon: Icon }) => (
          <NavLink
            key={path}
            to={path}
            className={({ isActive }) =>
              `flex flex-col items-center gap-1 px-3 py-2 rounded-lg transition-colors ${
                isActive
                  ? 'text-cyan-400'
                  : 'text-gray-500 hover:text-gray-300'
              }`
            }
          >
            <Icon size={20} />
            <span className="text-xs">{label}</span>
          </NavLink>
        ))}
      </div>
    </nav>
  )
}

/**
 * Responsive Layout Component
 * Handles both desktop and mobile layouts
 */
export default function ResponsiveLayout() {
  return (
    <div className="min-h-screen bg-gray-900">
      {/* Mobile Navigation */}
      <MobileNav />

      {/* Desktop Navigation */}
      <DesktopNav />

      {/* Main Content */}
      <main className="responsive-main px-4 md:px-6 lg:px-8 pb-20 md:pb-8 pt-4">
        <div className="max-w-7xl mx-auto">
          <Outlet />
        </div>
      </main>

      {/* Bottom Tab Bar (Mobile) */}
      <BottomTabBar />
    </div>
  )
}
