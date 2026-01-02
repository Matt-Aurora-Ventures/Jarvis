import React from 'react'
import { Outlet, NavLink } from 'react-router-dom'
import { Home, MessageCircle, Settings, Search, Mic, TrendingUp } from 'lucide-react'
import useJarvisStore from '../stores/jarvisStore'
import VoiceOrb from './VoiceOrb'

function Layout() {
  const { isListening, status } = useJarvisStore()

  return (
    <div className="flex h-screen bg-jarvis-darker">
      {/* Sidebar */}
      <aside className="w-20 bg-jarvis-dark border-r border-slate-700 flex flex-col items-center py-6">
        <div className="mb-8">
          <div className="w-12 h-12 rounded-full bg-jarvis-primary flex items-center justify-center">
            <span className="text-white font-bold text-xl">J</span>
          </div>
        </div>

        <nav className="flex-1 flex flex-col gap-4">
          <NavLink
            to="/"
            className={({ isActive }) =>
              `p-3 rounded-xl transition-all ${isActive ? 'bg-jarvis-primary text-white' : 'text-slate-400 hover:bg-slate-700 hover:text-white'}`
            }
          >
            <Home size={24} />
          </NavLink>
          <NavLink
            to="/chat"
            className={({ isActive }) =>
              `p-3 rounded-xl transition-all ${isActive ? 'bg-jarvis-primary text-white' : 'text-slate-400 hover:bg-slate-700 hover:text-white'}`
            }
          >
            <MessageCircle size={24} />
          </NavLink>
          <NavLink
            to="/voice"
            className={({ isActive }) =>
              `p-3 rounded-xl transition-all ${isActive ? 'bg-jarvis-primary text-white' : 'text-slate-400 hover:bg-slate-700 hover:text-white'}`
            }
            title="Voice Control"
          >
            <Mic size={24} />
          </NavLink>
          <NavLink
            to="/trading"
            className={({ isActive }) =>
              `p-3 rounded-xl transition-all ${isActive ? 'bg-jarvis-primary text-white' : 'text-slate-400 hover:bg-slate-700 hover:text-white'}`
            }
            title="Trading"
          >
            <TrendingUp size={24} />
          </NavLink>
          <NavLink
            to="/research"
            className={({ isActive }) =>
              `p-3 rounded-xl transition-all ${isActive ? 'bg-jarvis-primary text-white' : 'text-slate-400 hover:bg-slate-700 hover:text-white'}`
            }
            title="Research"
          >
            <Search size={24} />
          </NavLink>
          <NavLink
            to="/settings"
            className={({ isActive }) =>
              `p-3 rounded-xl transition-all ${isActive ? 'bg-jarvis-primary text-white' : 'text-slate-400 hover:bg-slate-700 hover:text-white'}`
            }
            title="Settings"
          >
            <Settings size={24} />
          </NavLink>
        </nav>

        {/* Status indicators */}
        <div className="mt-auto flex flex-col gap-2 items-center">
          <div className={`w-3 h-3 rounded-full ${status.daemon === 'running' ? 'bg-green-500' : 'bg-red-500'}`}
            title={`Daemon: ${status.daemon}`} />
          <div className={`w-3 h-3 rounded-full ${isListening ? 'bg-jarvis-primary animate-pulse' : 'bg-slate-600'}`}
            title={isListening ? 'Listening' : 'Not listening'} />
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 flex flex-col overflow-hidden">
        <Outlet />
      </main>

      {/* Floating Voice Orb */}
      <VoiceOrb />
    </div>
  )
}

export default Layout
