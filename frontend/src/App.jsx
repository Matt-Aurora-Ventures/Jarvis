import React from 'react'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import { ErrorBoundary } from './components/common'
import Dashboard from './pages/DashboardNew'
import Settings from './pages/Settings'
import Chat from './pages/ChatNew'
import Research from './pages/Research'
import VoiceControl from './pages/VoiceControl'
import Trading from './pages/TradingNew'
import Roadmap from './pages/Roadmap'

function App() {
  return (
    <ErrorBoundary>
      <div className="app-loading">
        <BrowserRouter>
          <Routes>
            {/* Trading Dashboard - Standalone (V2 White Knight Design) */}
            <Route path="/trading" element={<Trading />} />

            {/* Other pages with Layout */}
            <Route path="/" element={<Layout />}>
              <Route index element={<Dashboard />} />
              <Route path="chat" element={<Chat />} />
              <Route path="voice" element={<VoiceControl />} />
              <Route path="settings" element={<Settings />} />
              <Route path="research" element={<Research />} />
              <Route path="roadmap" element={<Roadmap />} />
            </Route>
          </Routes>
        </BrowserRouter>
      </div>
    </ErrorBoundary>
  )
}

export default App
