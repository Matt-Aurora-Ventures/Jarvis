import React, { useEffect, useState } from 'react'
import { Mic, MicOff, Volume2, VolumeX, Settings, BarChart3, DollarSign, Command, Keyboard } from 'lucide-react'
import { VoiceAssistant } from '../components/voice'
import { useNavigate } from 'react-router-dom'

function VoiceControl() {
    const navigate = useNavigate()
    const [voiceStatus, setVoiceStatus] = useState({
        enabled: true,
        listening: false,
        speaking: false,
        bargeInEnabled: true,
    })

    const [ttsConfig, setTtsConfig] = useState({
        engine: 'say',
        voice: 'Samantha',
        openaiVoice: 'nova',
        model: 'tts-1',
    })

    const [costs, setCosts] = useState({
        hour: 0,
        today: 0,
        projected: 0,
    })

    const [transcript, setTranscript] = useState([])

    useEffect(() => {
        fetchVoiceStatus()
        fetchCosts()
        const statusInterval = setInterval(fetchVoiceStatus, 2000)
        const costInterval = setInterval(fetchCosts, 10000)

        return () => {
            clearInterval(statusInterval)
            clearInterval(costInterval)
        }
    }, [])

    const fetchVoiceStatus = async () => {
        try {
            const response = await fetch('/api/voice/status')
            if (response.ok) {
                const data = await response.json()
                setVoiceStatus(data)
            }
        } catch (error) {
            console.error('Failed to fetch voice status:', error)
        }
    }

    const fetchCosts = async () => {
        try {
            const response = await fetch('/api/costs/tts')
            if (response.ok) {
                const data = await response.json()
                setCosts(data)
            }
        } catch (error) {
            console.error('Failed to fetch costs:', error)
        }
    }

    const toggleVoice = async () => {
        try {
            await fetch('/api/voice/toggle', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ enabled: !voiceStatus.enabled }),
            })
            fetchVoiceStatus()
        } catch (error) {
            console.error('Failed to toggle voice:', error)
        }
    }

    const updateTtsEngine = async (engine) => {
        try {
            await fetch('/api/voice/config', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ tts_engine: engine }),
            })
            setTtsConfig({ ...ttsConfig, engine })
        } catch (error) {
            console.error('Failed to update TTS engine:', error)
        }
    }

    const testVoice = async () => {
        try {
            await fetch('/api/voice/test', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ text: 'Hello, I am Jarvis. Voice system is operational.' }),
            })
        } catch (error) {
            console.error('Failed to test voice:', error)
        }
    }

    return (
        <div style={{ flex: 1, padding: 'var(--space-xl)', overflowY: 'auto' }}>
            <header style={{ marginBottom: 'var(--space-xl)' }}>
                <h1 style={{ fontSize: '1.875rem', fontWeight: 700, color: 'var(--text-primary)', marginBottom: 'var(--space-xs)' }}>Voice Control</h1>
                <p style={{ color: 'var(--text-secondary)' }}>Manage voice chat, TTS, and barge-in settings</p>
            </header>

            {/* Status Cards */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 'var(--space-lg)', marginBottom: 'var(--space-xl)' }}>
                <StatusCard
                    icon={voiceStatus.listening ? <Mic style={{ color: 'var(--success)' }} /> : <MicOff style={{ color: 'var(--text-tertiary)' }} />}
                    label="Listening"
                    status={voiceStatus.listening ? 'Active' : 'Idle'}
                    statusColor={voiceStatus.listening ? 'success' : 'muted'}
                />
                <StatusCard
                    icon={voiceStatus.speaking ? <Volume2 className="animate-pulse" style={{ color: 'var(--primary)' }} /> : <VolumeX style={{ color: 'var(--text-tertiary)' }} />}
                    label="Speaking"
                    status={voiceStatus.speaking ? 'Active' : 'Idle'}
                    statusColor={voiceStatus.speaking ? 'primary' : 'muted'}
                />
                <StatusCard
                    icon={<Settings style={{ color: 'var(--primary)' }} />}
                    label="Barge-in"
                    status={voiceStatus.bargeInEnabled ? 'Enabled' : 'Disabled'}
                    statusColor={voiceStatus.bargeInEnabled ? 'primary' : 'muted'}
                />
            </div>

            {/* Voice Assistant Section */}
            <div className="card" style={{ marginBottom: 'var(--space-xl)' }}>
                <h2 style={{ fontSize: '1.25rem', fontWeight: 600, color: 'var(--text-primary)', marginBottom: 'var(--space-md)', display: 'flex', alignItems: 'center', gap: 'var(--space-sm)' }}>
                    <Command size={20} style={{ color: 'var(--primary)' }} />
                    Voice Assistant
                </h2>
                <VoiceAssistant
                    onNavigate={navigate}
                    onCommand={(result) => console.log('Voice command result:', result)}
                />
            </div>

            {/* Voice Commands Reference */}
            <div className="card" style={{ marginBottom: 'var(--space-xl)' }}>
                <h2 style={{ fontSize: '1.25rem', fontWeight: 600, color: 'var(--text-primary)', marginBottom: 'var(--space-md)', display: 'flex', alignItems: 'center', gap: 'var(--space-sm)' }}>
                    <Keyboard size={20} style={{ color: 'var(--primary)' }} />
                    Voice Commands
                </h2>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 'var(--space-lg)' }}>
                    <CommandCategory title="Navigation" commands={[
                        '"Go to dashboard"', '"Open trading"', '"Show settings"', '"Open voice control"'
                    ]} />
                    <CommandCategory title="Trading" commands={[
                        '"What\'s the price of SOL?"', '"Show my portfolio"', '"Check my positions"', '"Set slippage to 1%"'
                    ]} />
                    <CommandCategory title="Market" commands={[
                        '"Show market sentiment"', '"What\'s trending?"', '"Show top gainers"', '"Run sentiment report"'
                    ]} />
                    <CommandCategory title="JARVIS" commands={[
                        '"Hey Jarvis, [question]"', '"Ask Jarvis about..."', '"Jarvis, help me with..."'
                    ]} />
                    <CommandCategory title="Control" commands={[
                        '"Stop listening"', '"Mute"', '"Unmute"', '"What commands?"'
                    ]} />
                    <CommandCategory title="System" commands={[
                        '"Restart backend"', '"Check status"', '"Minimize window"', '"Clear chat"'
                    ]} />
                </div>
            </div>

            {/* TTS Configuration */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(340px, 1fr))', gap: 'var(--space-lg)', marginBottom: 'var(--space-xl)' }}>
                <div className="card">
                    <h2 style={{ fontSize: '1.25rem', fontWeight: 600, color: 'var(--text-primary)', marginBottom: 'var(--space-md)', display: 'flex', alignItems: 'center', gap: 'var(--space-sm)' }}>
                        <Settings size={20} style={{ color: 'var(--primary)' }} />
                        TTS Configuration
                    </h2>

                    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-md)' }}>
                        <div>
                            <label style={{ display: 'block', fontSize: '0.875rem', fontWeight: 500, color: 'var(--text-secondary)', marginBottom: 'var(--space-xs)' }}>
                                TTS Engine
                            </label>
                            <select
                                value={ttsConfig.engine}
                                onChange={(e) => updateTtsEngine(e.target.value)}
                                className="input"
                                style={{ width: '100%' }}
                            >
                                <option value="say">macOS Say (Free)</option>
                                <option value="openai_tts">OpenAI TTS (Premium)</option>
                                <option value="piper">Piper (Local)</option>
                            </select>
                        </div>

                        {ttsConfig.engine === 'say' && (
                            <div>
                                <label style={{ display: 'block', fontSize: '0.875rem', fontWeight: 500, color: 'var(--text-secondary)', marginBottom: 'var(--space-xs)' }}>
                                    Voice
                                </label>
                                <select
                                    value={ttsConfig.voice}
                                    onChange={(e) => setTtsConfig({ ...ttsConfig, voice: e.target.value })}
                                    className="input"
                                    style={{ width: '100%' }}
                                >
                                    <option value="Samantha">Samantha</option>
                                    <option value="Alex">Alex</option>
                                    <option value="Victoria">Victoria</option>
                                    <option value="Allison">Allison</option>
                                </select>
                            </div>
                        )}

                        {ttsConfig.engine === 'openai_tts' && (
                            <>
                                <div>
                                    <label style={{ display: 'block', fontSize: '0.875rem', fontWeight: 500, color: 'var(--text-secondary)', marginBottom: 'var(--space-xs)' }}>
                                        OpenAI Voice
                                    </label>
                                    <select
                                        value={ttsConfig.openaiVoice}
                                        onChange={(e) => setTtsConfig({ ...ttsConfig, openaiVoice: e.target.value })}
                                        className="input"
                                        style={{ width: '100%' }}
                                    >
                                        <option value="nova">Nova (Energetic)</option>
                                        <option value="alloy">Alloy (Balanced)</option>
                                        <option value="echo">Echo (Male)</option>
                                        <option value="fable">Fable (British)</option>
                                        <option value="onyx">Onyx (Deep)</option>
                                        <option value="shimmer">Shimmer (Soft)</option>
                                    </select>
                                </div>
                                <div>
                                    <label style={{ display: 'block', fontSize: '0.875rem', fontWeight: 500, color: 'var(--text-secondary)', marginBottom: 'var(--space-xs)' }}>
                                        Model
                                    </label>
                                    <select
                                        value={ttsConfig.model}
                                        onChange={(e) => setTtsConfig({ ...ttsConfig, model: e.target.value })}
                                        className="input"
                                        style={{ width: '100%' }}
                                    >
                                        <option value="tts-1">TTS-1 (Fast, $0.015/1M chars)</option>
                                        <option value="tts-1-hd">TTS-1-HD (Quality, $0.030/1M chars)</option>
                                    </select>
                                </div>
                            </>
                        )}

                        <button
                            onClick={testVoice}
                            className="btn btn-primary"
                            style={{ width: '100%' }}
                        >
                            Test Voice
                        </button>
                    </div>
                </div>

                {/* Cost Monitor */}
                <div className="card">
                    <h2 style={{ fontSize: '1.25rem', fontWeight: 600, color: 'var(--text-primary)', marginBottom: 'var(--space-md)', display: 'flex', alignItems: 'center', gap: 'var(--space-sm)' }}>
                        <DollarSign size={20} style={{ color: 'var(--success)' }} />
                        Cost Monitor
                    </h2>

                    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-md)' }}>
                        <CostItem label="Last Hour" value={`$${costs.hour.toFixed(6)}`} />
                        <CostItem label="Today" value={`$${costs.today.toFixed(6)}`} />
                        <CostItem label="Projected Monthly" value={`$${costs.projected.toFixed(2)}`} highlight />

                        <div style={{ marginTop: 'var(--space-md)', padding: 'var(--space-md)', background: 'var(--bg-secondary)', borderRadius: 'var(--radius-md)' }}>
                            <p style={{ fontSize: '0.875rem', color: 'var(--text-secondary)', marginBottom: 'var(--space-xs)' }}>Current Settings Cost:</p>
                            <p style={{ fontSize: '1.125rem', fontWeight: 600, color: 'var(--text-primary)' }}>
                                {ttsConfig.engine === 'say' && '✨ Free (macOS Say)'}
                                {ttsConfig.engine === 'openai_tts' && `~$${(costs.projected * 1.5).toFixed(2)}/month`}
                                {ttsConfig.engine === 'piper' && '✨ Free (Local)'}
                            </p>
                        </div>
                    </div>
                </div>
            </div>

            {/* Recent Transcript */}
            <div className="card">
                <h2 style={{ fontSize: '1.25rem', fontWeight: 600, color: 'var(--text-primary)', marginBottom: 'var(--space-md)', display: 'flex', alignItems: 'center', gap: 'var(--space-sm)' }}>
                    <BarChart3 size={20} style={{ color: 'var(--success)' }} />
                    Recent Conversation
                </h2>

                <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-sm)', maxHeight: '24rem', overflowY: 'auto' }}>
                    {transcript.length > 0 ? (
                        transcript.map((item, index) => (
                            <div key={index} style={{ 
                                padding: 'var(--space-md)', 
                                borderRadius: 'var(--radius-md)',
                                background: item.role === 'user' ? 'rgba(59, 130, 246, 0.08)' : 'var(--bg-secondary)'
                            }}>
                                <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-xs)', marginBottom: 'var(--space-xs)' }}>
                                    <span style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--primary)' }}>
                                        {item.role === 'user' ? 'You' : 'Jarvis'}
                                    </span>
                                    <span style={{ fontSize: '0.75rem', color: 'var(--text-tertiary)' }}>{item.time}</span>
                                </div>
                                <p style={{ color: 'var(--text-primary)' }}>{item.text}</p>
                            </div>
                        ))
                    ) : (
                        <p style={{ color: 'var(--text-tertiary)', textAlign: 'center', padding: 'var(--space-xl)' }}>
                            No recent conversations. Say "jarvis" to start a chat.
                        </p>
                    )}
                </div>
            </div>
        </div>
    )
}

function StatusCard({ icon, label, status, statusColor }) {
    const colorMap = {
        success: 'var(--success)',
        primary: 'var(--primary)',
        muted: 'var(--text-tertiary)',
    }

    return (
        <div className="card">
            <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-sm)', marginBottom: 'var(--space-sm)' }}>
                {icon}
                <span style={{ color: 'var(--text-secondary)' }}>{label}</span>
            </div>
            <p style={{ fontSize: '1.5rem', fontWeight: 700, color: colorMap[statusColor] }}>{status}</p>
        </div>
    )
}

function CostItem({ label, value, highlight }) {
    return (
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ color: 'var(--text-secondary)' }}>{label}</span>
            <span style={{
                fontWeight: 600,
                fontSize: highlight ? '1.25rem' : '1rem',
                color: highlight ? 'var(--primary)' : 'var(--text-primary)'
            }}>
                {value}
            </span>
        </div>
    )
}

function CommandCategory({ title, commands }) {
    return (
        <div style={{ padding: 'var(--space-md)', background: 'var(--bg-secondary)', borderRadius: 'var(--radius-md)' }}>
            <h3 style={{ fontSize: '0.875rem', fontWeight: 600, color: 'var(--primary)', marginBottom: 'var(--space-sm)' }}>
                {title}
            </h3>
            <ul style={{ margin: 0, padding: 0, listStyle: 'none', display: 'flex', flexDirection: 'column', gap: 'var(--space-xs)' }}>
                {commands.map((cmd, i) => (
                    <li key={i} style={{
                        fontSize: '0.813rem',
                        color: 'var(--text-secondary)',
                        padding: '6px 10px',
                        background: 'var(--bg-tertiary)',
                        borderRadius: 'var(--radius-sm)',
                        fontFamily: 'monospace'
                    }}>
                        {cmd}
                    </li>
                ))}
            </ul>
        </div>
    )
}

export default VoiceControl
