import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.jsx'
import './minimal.css'

function removeInitialLoader() {
  const root = document.getElementById('root')
  if (!root) return
  const loader = root.querySelector('.initial-loading')
  if (loader) loader.remove()
}

function renderFatalError(error) {
  const root = document.getElementById('root')
  if (!root) return

  const message = error instanceof Error ? error.message : String(error)
  root.innerHTML = `
    <div style="min-height:100vh;display:flex;align-items:center;justify-content:center;padding:24px;background:#fff;color:#111827;">
      <div style="max-width:720px;width:100%;border:1px solid #E5E7EB;border-radius:12px;padding:24px;">
        <h1 style="font-size:18px;margin:0 0 8px;font-weight:700;">Jarvis UI failed to start</h1>
        <p style="margin:0 0 12px;color:#6B7280;">The initial loader was removed, but React crashed during startup.</p>
        <pre style="white-space:pre-wrap;margin:0;padding:12px;background:#F9FAFB;border:1px solid #E5E7EB;border-radius:8px;">${message}</pre>
        <p style="margin:12px 0 0;color:#6B7280;font-size:12px;">Open DevTools Console for the full stack trace.</p>
      </div>
    </div>
  `
}

try {
  removeInitialLoader()
  const rootEl = document.getElementById('root')
  if (!rootEl) throw new Error('Missing #root element')

  ReactDOM.createRoot(rootEl).render(
    <React.StrictMode>
      <App />
    </React.StrictMode>,
  )
} catch (e) {
  // If React fails before it can render anything, don't leave the HTML loader forever.
  console.error('Fatal startup error:', e)
  removeInitialLoader()
  renderFatalError(e)
}
