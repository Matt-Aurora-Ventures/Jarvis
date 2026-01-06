import React from 'react'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import Settings from '@/pages/Settings'
import Research from '@/pages/Research'
import VoiceControl from '@/pages/VoiceControl'
import Roadmap from '@/pages/Roadmap'

// Simple Dashboard until we fix the complex one
function Dashboard() {
  return (
    <div style={{ 
      padding: '2rem', 
      background: 'var(--bg-secondary, #fff)', 
      minHeight: '100vh',
      fontFamily: 'Inter, sans-serif'
    }}>
      <h1 style={{ 
        color: 'var(--text-primary, #111827)', 
        fontSize: '2.5rem', 
        fontWeight: 700,
        marginBottom: '0.5rem' 
      }}>
        Jarvis Dashboard
      </h1>
      <p style={{ 
        color: 'var(--text-secondary, #6B7280)',
        fontSize: '1rem',
        marginBottom: '2rem'
      }}>
        Welcome to your AI-powered trading and productivity assistant
      </p>
      
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))',
        gap: '1.5rem',
        marginTop: '2rem'
      }}>
        <div className="card" style={{
          padding: '1.5rem',
          background: 'var(--bg-card, #fff)',
          borderRadius: '12px',
          boxShadow: '0 1px 3px rgba(0,0,0,0.1)'
        }}>
          <h3 style={{ 
            fontSize: '1.125rem', 
            fontWeight: 600, 
            marginBottom: '0.5rem',
            color: 'var(--text-primary, #111827)'
          }}>
            Quick Stats
          </h3>
          <p style={{ color: 'var(--text-secondary, #6B7280)', fontSize: '0.875rem' }}>
            System is online and ready
          </p>
        </div>
        
        <div className="card" style={{
          padding: '1.5rem',
          background: 'var(--bg-card, #fff)',
          borderRadius: '12px',
          boxShadow: '0 1px 3px rgba(0,0,0,0.1)'
        }}>
          <h3 style={{ 
            fontSize: '1.125rem', 
            fontWeight: 600, 
            marginBottom: '0.5rem',
            color: 'var(--text-primary, #111827)'
          }}>
            Recent Activity
          </h3>
          <p style={{ color: 'var(--text-secondary, #6B7280)', fontSize: '0.875rem' }}>
            No recent activity
          </p>
        </div>
      </div>
    </div>
  )
}

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<Dashboard />} />
          <Route path="voice" element={<VoiceControl />} />
          <Route path="settings" element={<Settings />} />
          <Route path="research" element={<Research />} />
          <Route path="roadmap" element={<Roadmap />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}

export default App
