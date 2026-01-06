import React from 'react'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import Settings from './pages/Settings'
import Chat from './pages/Chat'
import Research from './pages/Research'
import VoiceControl from './pages/VoiceControl'
import Trading from './pages/Trading'

function App() {
  return (
    <BrowserRouter>
      <Routes>
        {/* Trading Dashboard - Standalone (V3 White Knight Design) */}
        <Route path="/trading" element={<Trading />} />

        {/* Other pages with Layout (Dark Design) */}
        <Route path="/" element={<Layout />}>
          <Route index element={<Dashboard />} />
          <Route path="chat" element={<Chat />} />
          <Route path="voice" element={<VoiceControl />} />
          <Route path="settings" element={<Settings />} />
          <Route path="research" element={<Research />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}

export default App
