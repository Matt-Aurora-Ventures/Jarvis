import React, { useState, useEffect } from 'react'
import { NavLink, useLocation } from 'react-router-dom'
import {
  Home,
  MessageCircle,
  Settings,
  Search,
  Mic,
  TrendingUp,
  Bot,
  Map,
  Bell,
  Menu,
  X,
  ChevronRight
} from 'lucide-react'
import useJarvisStore from '../stores/jarvisStore'

/**
 * Navigation Links Configuration
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
 * Mobile Navigation Component
 * Provides a hamburger menu for mobile devices
 */
export default function MobileNav() {
  const [isOpen, setIsOpen] = useState(false)
  const location = useLocation()
  const { isListening, status } = useJarvisStore()

  // Close menu on route change
  useEffect(() => {
    setIsOpen(false)
  }, [location.pathname])

  // Prevent body scroll when menu is open
  useEffect(() => {
    if (isOpen) {
      document.body.style.overflow = 'hidden'
    } else {
      document.body.style.overflow = ''
    }
    return () => {
      document.body.style.overflow = ''
    }
  }, [isOpen])

  return (
    <>
      {/* Mobile Header */}
      <header className="mobile-header md:hidden fixed top-0 left-0 right-0 z-50 bg-gray-900/95 backdrop-blur-sm border-b border-gray-800">
        <div className="flex items-center justify-between p-4">
          {/* Brand */}
          <div className="flex items-center gap-2">
            <Bot size={24} className="text-cyan-400" />
            <span className="font-semibold text-white">Jarvis</span>
          </div>

          {/* Status indicators */}
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-1.5">
              <div
                className={`w-2 h-2 rounded-full ${
                  status.daemon === 'running' ? 'bg-green-500' : 'bg-red-500'
                }`}
              />
              <span className="text-xs text-gray-400">
                {status.daemon === 'running' ? 'Online' : 'Offline'}
              </span>
            </div>

            {/* Hamburger button */}
            <button
              onClick={() => setIsOpen(!isOpen)}
              className="p-2 rounded-lg bg-gray-800 text-white hover:bg-gray-700 transition-colors"
              aria-label={isOpen ? 'Close menu' : 'Open menu'}
            >
              {isOpen ? <X size={24} /> : <Menu size={24} />}
            </button>
          </div>
        </div>
      </header>

      {/* Mobile Menu Overlay */}
      <div
        className={`md:hidden fixed inset-0 z-40 transition-opacity duration-300 ${
          isOpen ? 'opacity-100 pointer-events-auto' : 'opacity-0 pointer-events-none'
        }`}
        onClick={() => setIsOpen(false)}
      >
        <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" />
      </div>

      {/* Mobile Menu Panel */}
      <nav
        className={`md:hidden fixed top-0 right-0 bottom-0 w-72 z-50 bg-gray-900 border-l border-gray-800 transform transition-transform duration-300 ease-out ${
          isOpen ? 'translate-x-0' : 'translate-x-full'
        }`}
      >
        {/* Menu Header */}
        <div className="flex items-center justify-between p-4 border-b border-gray-800">
          <div className="flex items-center gap-2">
            <Bot size={24} className="text-cyan-400" />
            <span className="font-semibold text-white">Navigation</span>
          </div>
          <button
            onClick={() => setIsOpen(false)}
            className="p-2 rounded-lg hover:bg-gray-800 text-gray-400 hover:text-white transition-colors"
          >
            <X size={20} />
          </button>
        </div>

        {/* Navigation Links */}
        <div className="p-4 space-y-1 overflow-y-auto max-h-[calc(100vh-200px)]">
          {NAV_LINKS.map(({ path, label, icon: Icon }) => (
            <NavLink
              key={path}
              to={path}
              className={({ isActive }) =>
                `flex items-center gap-3 px-4 py-3 rounded-lg transition-all duration-200 ${
                  isActive
                    ? 'bg-cyan-500/20 text-cyan-400 border-l-2 border-cyan-400'
                    : 'text-gray-400 hover:bg-gray-800 hover:text-white'
                }`
              }
            >
              <Icon size={20} />
              <span className="flex-1">{label}</span>
              <ChevronRight size={16} className="text-gray-600" />
            </NavLink>
          ))}
        </div>

        {/* Status Section */}
        <div className="absolute bottom-0 left-0 right-0 p-4 border-t border-gray-800 bg-gray-900/95">
          <div className="space-y-3">
            {/* System Status */}
            <div className="flex items-center justify-between">
              <span className="text-sm text-gray-400">System Status</span>
              <div className="flex items-center gap-2">
                <div
                  className={`w-2 h-2 rounded-full ${
                    status.daemon === 'running' ? 'bg-green-500' : 'bg-red-500'
                  }`}
                />
                <span className={`text-sm ${
                  status.daemon === 'running' ? 'text-green-400' : 'text-red-400'
                }`}>
                  {status.daemon === 'running' ? 'Online' : 'Offline'}
                </span>
              </div>
            </div>

            {/* Voice Status */}
            <div className="flex items-center justify-between">
              <span className="text-sm text-gray-400">Voice Control</span>
              <div className="flex items-center gap-2">
                <div
                  className={`w-2 h-2 rounded-full ${
                    isListening ? 'bg-cyan-500 animate-pulse' : 'bg-gray-500'
                  }`}
                />
                <span className={`text-sm ${
                  isListening ? 'text-cyan-400' : 'text-gray-500'
                }`}>
                  {isListening ? 'Listening' : 'Idle'}
                </span>
              </div>
            </div>
          </div>
        </div>
      </nav>

      {/* Spacer for fixed header */}
      <div className="h-16 md:hidden" />
    </>
  )
}
