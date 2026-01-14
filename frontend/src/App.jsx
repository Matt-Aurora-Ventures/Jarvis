import React from 'react'
import { BrowserRouter, Routes, Route } from 'react-router-dom'

// Layout
import Layout from './components/Layout'

// Pages - Using the advanced refactored versions
import Dashboard from '@/pages/DashboardNew'
import Trading from '@/pages/TradingNew'
import Chat from '@/pages/ChatNew'
import Settings from '@/pages/Settings'
import Research from '@/pages/Research'
import VoiceControl from '@/pages/VoiceControl'
import Roadmap from '@/pages/Roadmap'
import Alerts from '@/pages/Alerts'

/**
 * JARVIS Dashboard - Main Application Router
 *
 * Routes:
 * - /           → Dashboard (system overview, stats, activity)
 * - /trading    → Trading Command Center (full-screen, own nav)
 * - /chat       → Full-page Jarvis conversation
 * - /voice      → Voice control interface
 * - /research   → Research tools
 * - /settings   → System configuration
 * - /roadmap    → Development roadmap
 */
function App() {
  return (
    <BrowserRouter>
      <Routes>
        {/* Trading - Full-screen with own navigation */}
        <Route path="/trading" element={<Trading />} />

        {/* Standard Layout Routes */}
        <Route path="/" element={<Layout />}>
          {/* Main Dashboard */}
          <Route index element={<Dashboard />} />

          {/* Chat Interface */}
          <Route path="chat" element={<Chat />} />

          {/* Voice Control */}
          <Route path="voice" element={<VoiceControl />} />

          {/* Research Tools */}
          <Route path="research" element={<Research />} />

          {/* Settings */}
          <Route path="settings" element={<Settings />} />

          {/* Roadmap */}
          <Route path="roadmap" element={<Roadmap />} />

          {/* Price Alerts */}
          <Route path="alerts" element={<Alerts />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}

export default App
