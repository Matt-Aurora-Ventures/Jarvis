import React from 'react'
import { Outlet, NavLink } from 'react-router-dom'
import { Home, MessageCircle, Settings, Search, Mic, TrendingUp, Bot } from 'lucide-react'
import useJarvisStore from '../stores/jarvisStore'

function Layout() {
  const { isListening, status } = useJarvisStore()

  return (
    <div style={{ minHeight: '100vh', background: 'var(--bg-primary)' }}>
      {/* Top Navigation - V3 White Knight Style */}
      <div className="top-nav">
        <div className="nav-brand">
          <Bot size={24} />
          <span>Jarvis LifeOS</span>
        </div>

        <nav style={{ display: 'flex', gap: '8px', flex: 1, justifyContent: 'center' }}>
          <NavLink
            to="/"
            className={({ isActive }) =>
              `btn ${isActive ? 'btn-primary' : 'btn-ghost'}`
            }
          >
            <Home size={18} />
            Dashboard
          </NavLink>
          <NavLink
            to="/chat"
            className={({ isActive }) =>
              `btn ${isActive ? 'btn-primary' : 'btn-ghost'}`
            }
          >
            <MessageCircle size={18} />
            Chat
          </NavLink>
          <NavLink
            to="/voice"
            className={({ isActive }) =>
              `btn ${isActive ? 'btn-primary' : 'btn-ghost'}`
            }
          >
            <Mic size={18} />
            Voice
          </NavLink>
          <NavLink
            to="/trading"
            className={({ isActive }) =>
              `btn ${isActive ? 'btn-primary' : 'btn-ghost'}`
            }
          >
            <TrendingUp size={18} />
            Trading
          </NavLink>
          <NavLink
            to="/research"
            className={({ isActive }) =>
              `btn ${isActive ? 'btn-primary' : 'btn-ghost'}`
            }
          >
            <Search size={18} />
            Research
          </NavLink>
          <NavLink
            to="/settings"
            className={({ isActive }) =>
              `btn ${isActive ? 'btn-primary' : 'btn-ghost'}`
            }
          >
            <Settings size={18} />
            Settings
          </NavLink>
        </nav>

        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          {/* Status indicators */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.8125rem', color: 'var(--text-secondary)' }}>
            <div
              style={{
                width: '8px',
                height: '8px',
                borderRadius: '50%',
                background: status.daemon === 'running' ? 'var(--success)' : 'var(--danger)'
              }}
              title={`Daemon: ${status.daemon}`}
            />
            <span>System {status.daemon === 'running' ? 'Online' : 'Offline'}</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.8125rem', color: 'var(--text-secondary)' }}>
            <div
              style={{
                width: '8px',
                height: '8px',
                borderRadius: '50%',
                background: isListening ? 'var(--primary)' : 'var(--gray-300)',
                animation: isListening ? 'pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite' : 'none'
              }}
              title={isListening ? 'Listening' : 'Not listening'}
            />
            <span>{isListening ? 'Listening' : 'Idle'}</span>
          </div>
        </div>
      </div>

      {/* Main content */}
      <main style={{
        maxWidth: '1400px',
        margin: '0 auto',
        padding: 'var(--spacing-xl)',
        minHeight: 'calc(100vh - 64px)'
      }}>
        <Outlet />
      </main>
    </div>
  )
}

export default Layout
