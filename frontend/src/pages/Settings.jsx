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
    <div className="flex-1 p-8 overflow-y-auto">
      <header className="mb-8">
        <h1 className="text-3xl font-bold text-white mb-2">Settings</h1>
        <p className="text-slate-400">Manage your API keys and integrations</p>
      </header>

      {/* API Keys Section */}
      <section className="mb-8">
        <div className="flex items-center gap-3 mb-6">
          <Key className="text-jarvis-primary" />
          <h2 className="text-xl font-semibold text-white">API Keys</h2>
        </div>

        <div className="space-y-4">
          {API_KEY_PROVIDERS.map((provider) => (
            <div
              key={provider.id}
              className="bg-jarvis-dark rounded-2xl p-6 border border-slate-700"
            >
              <div className="flex justify-between items-start mb-4">
                <div>
                  <h3 className="text-lg font-medium text-white">{provider.name}</h3>
                  <p className="text-sm text-slate-400">{provider.description}</p>
                </div>
                <StatusBadge status={saveStatus[provider.id]} />
              </div>

              <div className="flex gap-3">
                <div className="flex-1 relative">
                  <input
                    type={showKeys[provider.id] ? 'text' : 'password'}
                    value={localKeys[provider.id] || ''}
                    onChange={(e) => handleKeyChange(provider.id, e.target.value)}
                    placeholder={`Enter your ${provider.name} API key`}
                    className="w-full bg-slate-800 border border-slate-600 rounded-xl px-4 py-3 text-white placeholder-slate-500 focus:outline-none focus:border-jarvis-primary"
                  />
                  <button
                    onClick={() => toggleShowKey(provider.id)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-white"
                  >
                    {showKeys[provider.id] ? <EyeOff size={20} /> : <Eye size={20} />}
                  </button>
                </div>
                <button
                  onClick={() => saveKey(provider.id)}
                  disabled={!localKeys[provider.id] || saveStatus[provider.id] === 'saving'}
                  className="px-6 py-3 bg-jarvis-primary text-white rounded-xl hover:bg-blue-600 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
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
      <section className="mb-8">
        <h2 className="text-xl font-semibold text-white mb-6">Voice Settings</h2>
        <div className="bg-jarvis-dark rounded-2xl p-6 border border-slate-700 space-y-4">
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
        <h2 className="text-xl font-semibold text-white mb-6">Integrations</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
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
    unsaved: 'bg-yellow-500/20 text-yellow-400',
    saving: 'bg-blue-500/20 text-blue-400',
    saved: 'bg-green-500/20 text-green-400',
    error: 'bg-red-500/20 text-red-400',
  }

  const icons = {
    saved: <Check size={14} />,
    error: <AlertCircle size={14} />,
  }

  return (
    <span className={`px-2 py-1 rounded-full text-xs flex items-center gap-1 ${styles[status]}`}>
      {icons[status]}
      {status.charAt(0).toUpperCase() + status.slice(1)}
    </span>
  )
}

function ToggleSetting({ label, description, defaultChecked }) {
  const [checked, setChecked] = useState(defaultChecked)

  return (
    <div className="flex justify-between items-center">
      <div>
        <p className="text-white font-medium">{label}</p>
        <p className="text-sm text-slate-400">{description}</p>
      </div>
      <button
        onClick={() => setChecked(!checked)}
        className={`w-12 h-6 rounded-full transition-colors ${checked ? 'bg-jarvis-primary' : 'bg-slate-600'}`}
      >
        <div className={`w-5 h-5 rounded-full bg-white transform transition-transform ${checked ? 'translate-x-6' : 'translate-x-0.5'}`} />
      </button>
    </div>
  )
}

function IntegrationCard({ name, connected }) {
  return (
    <div className="bg-jarvis-dark rounded-2xl p-4 border border-slate-700 flex justify-between items-center">
      <span className="text-white">{name}</span>
      <span className={`px-3 py-1 rounded-full text-sm ${connected ? 'bg-green-500/20 text-green-400' : 'bg-slate-600 text-slate-300'}`}>
        {connected ? 'Connected' : 'Not connected'}
      </span>
    </div>
  )
}

export default Settings
