import React, { useState, useEffect } from 'react'
import { Key, Save, Eye, EyeOff, Check, AlertCircle } from 'lucide-react'
import useJarvisStore from '../stores/jarvisStore'

const API_KEY_PROVIDERS = [
  { id: 'gemini', name: 'Google Gemini', env: 'GOOGLE_API_KEY', description: 'Primary AI provider' },
  { id: 'groq', name: 'Groq', env: 'GROQ_API_KEY', description: 'Ultra-fast free AI' },
  { id: 'anthropic', name: 'Anthropic Claude', env: 'ANTHROPIC_API_KEY', description: 'Coming soon' },
  { id: 'openai', name: 'OpenAI', env: 'OPENAI_API_KEY', description: 'GPT models' },
  { id: 'trello', name: 'Trello', env: 'TRELLO_API_KEY', description: 'Task management' },
  { id: 'github', name: 'GitHub PAT', env: 'GITHUB_TOKEN', description: 'Repository access' },
]

function Settings() {
  const { apiKeys, setApiKey } = useJarvisStore()
  const [localKeys, setLocalKeys] = useState({})
  const [showKeys, setShowKeys] = useState({})
  const [saveStatus, setSaveStatus] = useState({})
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    // Load existing keys from backend
    const loadKeys = async () => {
      try {
        const response = await fetch('/api/settings/keys')
        if (response.ok) {
          const data = await response.json()
          setLocalKeys(data)
        }
      } catch (error) {
        console.error('Failed to load keys:', error)
      }
      setLoading(false)
    }
    loadKeys()
  }, [])

  const handleKeyChange = (provider, value) => {
    setLocalKeys(prev => ({ ...prev, [provider]: value }))
    setSaveStatus(prev => ({ ...prev, [provider]: 'unsaved' }))
  }

  const saveKey = async (provider) => {
    setSaveStatus(prev => ({ ...prev, [provider]: 'saving' }))
    try {
      const response = await fetch('/api/settings/keys', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ provider, key: localKeys[provider] }),
      })
      if (response.ok) {
        setSaveStatus(prev => ({ ...prev, [provider]: 'saved' }))
        setApiKey(provider, localKeys[provider])
        setTimeout(() => setSaveStatus(prev => ({ ...prev, [provider]: null })), 2000)
      } else {
        setSaveStatus(prev => ({ ...prev, [provider]: 'error' }))
      }
    } catch (error) {
      setSaveStatus(prev => ({ ...prev, [provider]: 'error' }))
    }
  }

  const toggleShowKey = (provider) => {
    setShowKeys(prev => ({ ...prev, [provider]: !prev[provider] }))
  }

  const maskKey = (key) => {
    if (!key) return ''
    if (key.length <= 8) return '••••••••'
    return key.slice(0, 4) + '••••••••' + key.slice(-4)
  }

  return (
    <div style={{ flex: 1, padding: 'var(--space-xl)', overflowY: 'auto' }}>
      <header style={{ marginBottom: 'var(--space-xl)' }}>
        <h1 style={{ fontSize: '1.875rem', fontWeight: 700, color: 'var(--text-primary)', marginBottom: 'var(--space-xs)' }}>Settings</h1>
        <p style={{ color: 'var(--text-secondary)' }}>Manage your API keys and integrations</p>
      </header>

      {/* API Keys Section */}
      <section style={{ marginBottom: 'var(--space-xl)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-sm)', marginBottom: 'var(--space-lg)' }}>
          <Key size={20} style={{ color: 'var(--primary)' }} />
          <h2 style={{ fontSize: '1.25rem', fontWeight: 600, color: 'var(--text-primary)' }}>API Keys</h2>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-md)' }}>
          {API_KEY_PROVIDERS.map((provider) => (
            <div key={provider.id} className="card">
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 'var(--space-md)' }}>
                <div>
                  <h3 style={{ fontSize: '1rem', fontWeight: 500, color: 'var(--text-primary)' }}>{provider.name}</h3>
                  <p style={{ fontSize: '0.875rem', color: 'var(--text-secondary)' }}>{provider.description}</p>
                </div>
                <StatusBadge status={saveStatus[provider.id]} />
              </div>

              <div style={{ display: 'flex', gap: 'var(--space-sm)' }}>
                <div style={{ flex: 1, position: 'relative' }}>
                  <input
                    type={showKeys[provider.id] ? 'text' : 'password'}
                    value={localKeys[provider.id] || ''}
                    onChange={(e) => handleKeyChange(provider.id, e.target.value)}
                    placeholder={`Enter your ${provider.name} API key`}
                    className="input"
                    style={{ width: '100%', paddingRight: '2.5rem' }}
                  />
                  <button
                    onClick={() => toggleShowKey(provider.id)}
                    style={{ 
                      position: 'absolute', 
                      right: 'var(--space-sm)', 
                      top: '50%', 
                      transform: 'translateY(-50%)',
                      background: 'none',
                      border: 'none',
                      cursor: 'pointer',
                      color: 'var(--text-tertiary)',
                      padding: 'var(--space-xs)'
                    }}
                  >
                    {showKeys[provider.id] ? <EyeOff size={20} /> : <Eye size={20} />}
                  </button>
                </div>
                <button
                  onClick={() => saveKey(provider.id)}
                  disabled={!localKeys[provider.id] || saveStatus[provider.id] === 'saving'}
                  className="btn btn-primary"
                  style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-xs)' }}
                >
                  <Save size={18} />
                  Save
                </button>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* Voice Settings */}
      <section style={{ marginBottom: 'var(--space-xl)' }}>
        <h2 style={{ fontSize: '1.25rem', fontWeight: 600, color: 'var(--text-primary)', marginBottom: 'var(--space-lg)' }}>Voice Settings</h2>
        <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-md)' }}>
          <ToggleSetting
            label="Voice Responses"
            description="Jarvis speaks responses aloud"
            defaultChecked={true}
          />
          <ToggleSetting
            label="Wake Word Detection"
            description="Listen for 'Hey Jarvis'"
            defaultChecked={true}
          />
          <ToggleSetting
            label="Proactive Suggestions"
            description="Offer help every 15 minutes"
            defaultChecked={true}
          />
        </div>
      </section>

      {/* Integrations */}
      <section>
        <h2 style={{ fontSize: '1.25rem', fontWeight: 600, color: 'var(--text-primary)', marginBottom: 'var(--space-lg)' }}>Integrations</h2>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 'var(--space-md)' }}>
          <IntegrationCard name="Trello" connected={!!localKeys.trello} />
          <IntegrationCard name="Gmail" connected={false} />
          <IntegrationCard name="Google Calendar" connected={false} />
          <IntegrationCard name="GitHub" connected={!!localKeys.github} />
        </div>
      </section>
    </div>
  )
}

function StatusBadge({ status }) {
  if (!status) return null
  
  const styles = {
    unsaved: { background: 'rgba(234, 179, 8, 0.1)', color: 'var(--warning)' },
    saving: { background: 'rgba(59, 130, 246, 0.1)', color: 'var(--primary)' },
    saved: { background: 'rgba(34, 197, 94, 0.1)', color: 'var(--success)' },
    error: { background: 'rgba(239, 68, 68, 0.1)', color: 'var(--danger)' },
  }

  const icons = {
    saved: <Check size={14} />,
    error: <AlertCircle size={14} />,
  }

  return (
    <span style={{ 
      ...styles[status],
      padding: 'var(--space-xs) var(--space-sm)', 
      borderRadius: 'var(--radius-full)', 
      fontSize: '0.75rem',
      display: 'flex',
      alignItems: 'center',
      gap: 'var(--space-xs)'
    }}>
      {icons[status]}
      {status.charAt(0).toUpperCase() + status.slice(1)}
    </span>
  )
}

function ToggleSetting({ label, description, defaultChecked }) {
  const [checked, setChecked] = useState(defaultChecked)

  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
      <div>
        <p style={{ color: 'var(--text-primary)', fontWeight: 500 }}>{label}</p>
        <p style={{ fontSize: '0.875rem', color: 'var(--text-secondary)' }}>{description}</p>
      </div>
      <button
        onClick={() => setChecked(!checked)}
        style={{
          width: '3rem',
          height: '1.5rem',
          borderRadius: 'var(--radius-full)',
          background: checked ? 'var(--primary)' : 'var(--gray-300)',
          border: 'none',
          cursor: 'pointer',
          position: 'relative',
          transition: 'background 0.2s ease'
        }}
      >
        <div style={{
          width: '1.25rem',
          height: '1.25rem',
          borderRadius: '50%',
          background: 'white',
          position: 'absolute',
          top: '50%',
          transform: `translateY(-50%) translateX(${checked ? '1.625rem' : '0.125rem'})`,
          transition: 'transform 0.2s ease',
          boxShadow: '0 1px 3px rgba(0,0,0,0.2)'
        }} />
      </button>
    </div>
  )
}

function IntegrationCard({ name, connected }) {
  return (
    <div className="card" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
      <span style={{ color: 'var(--text-primary)', fontWeight: 500 }}>{name}</span>
      <span style={{ 
        padding: 'var(--space-xs) var(--space-sm)', 
        borderRadius: 'var(--radius-full)', 
        fontSize: '0.875rem',
        background: connected ? 'rgba(34, 197, 94, 0.1)' : 'var(--bg-secondary)',
        color: connected ? 'var(--success)' : 'var(--text-tertiary)'
      }}>
        {connected ? 'Connected' : 'Not connected'}
      </span>
    </div>
  )
}

export default Settings
