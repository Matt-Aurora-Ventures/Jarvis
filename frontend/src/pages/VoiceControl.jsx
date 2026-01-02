import React, { useEffect, useState } from 'react'
import { Mic, MicOff, Volume2, VolumeX, Settings, BarChart3, DollarSign } from 'lucide-react'

function VoiceControl() {
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
        <div className="flex-1 p-8 overflow-y-auto">
            <header className="mb-8">
                <h1 className="text-3xl font-bold text-white mb-2">Voice Control</h1>
                <p className="text-slate-400">Manage voice chat, TTS, and barge-in settings</p>
            </header>

            {/* Status Cards */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
                <StatusCard
                    icon={voiceStatus.listening ? <Mic className="text-green-500" /> : <MicOff className="text-slate-500" />}
                    label="Listening"
                    status={voiceStatus.listening ? 'Active' : 'Idle'}
                    statusColor={voiceStatus.listening ? 'green' : 'slate'}
                />
                <StatusCard
                    icon={voiceStatus.speaking ? <Volume2 className="text-blue-500 animate-pulse" /> : <VolumeX className="text-slate-500" />}
                    label="Speaking"
                    status={voiceStatus.speaking ? 'Active' : 'Idle'}
                    statusColor={voiceStatus.speaking ? 'blue' : 'slate'}
                />
                <StatusCard
                    icon={<Settings className="text-jarvis-primary" />}
                    label="Barge-in"
                    status={voiceStatus.bargeInEnabled ? 'Enabled' : 'Disabled'}
                    statusColor={voiceStatus.bargeInEnabled ? 'jarvis' : 'slate'}
                />
            </div>

            {/* TTS Configuration */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
                <div className="bg-jarvis-dark rounded-2xl p-6 border border-slate-700">
                    <h2 className="text-xl font-semibold text-white mb-4 flex items-center gap-2">
                        <Settings className="text-jarvis-accent" />
                        TTS Configuration
                    </h2>

                    <div className="space-y-4">
                        <div>
                            <label className="block text-sm font-medium text-slate-400 mb-2">
                                TTS Engine
                            </label>
                            <select
                                value={ttsConfig.engine}
                                onChange={(e) => updateTtsEngine(e.target.value)}
                                className="w-full bg-slate-800 border border-slate-600 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-jarvis-primary"
                            >
                                <option value="say">macOS Say (Free)</option>
                                <option value="openai_tts">OpenAI TTS (Premium)</option>
                                <option value="piper">Piper (Local)</option>
                            </select>
                        </div>

                        {ttsConfig.engine === 'say' && (
                            <div>
                                <label className="block text-sm font-medium text-slate-400 mb-2">
                                    Voice
                                </label>
                                <select
                                    value={ttsConfig.voice}
                                    onChange={(e) => setTtsConfig({ ...ttsConfig, voice: e.target.value })}
                                    className="w-full bg-slate-800 border border-slate-600 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-jarvis-primary"
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
                                    <label className="block text-sm font-medium text-slate-400 mb-2">
                                        OpenAI Voice
                                    </label>
                                    <select
                                        value={ttsConfig.openaiVoice}
                                        onChange={(e) => setTtsConfig({ ...ttsConfig, openaiVoice: e.target.value })}
                                        className="w-full bg-slate-800 border border-slate-600 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-jarvis-primary"
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
                                    <label className="block text-sm font-medium text-slate-400 mb-2">
                                        Model
                                    </label>
                                    <select
                                        value={ttsConfig.model}
                                        onChange={(e) => setTtsConfig({ ...ttsConfig, model: e.target.value })}
                                        className="w-full bg-slate-800 border border-slate-600 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-jarvis-primary"
                                    >
                                        <option value="tts-1">TTS-1 (Fast, $0.015/1M chars)</option>
                                        <option value="tts-1-hd">TTS-1-HD (Quality, $0.030/1M chars)</option>
                                    </select>
                                </div>
                            </>
                        )}

                        <button
                            onClick={testVoice}
                            className="w-full bg-jarvis-primary hover:bg-jarvis-primary/80 text-white py-2 px-4 rounded-lg transition-colors"
                        >
                            Test Voice
                        </button>
                    </div>
                </div>

                {/* Cost Monitor */}
                <div className="bg-jarvis-dark rounded-2xl p-6 border border-slate-700">
                    <h2 className="text-xl font-semibold text-white mb-4 flex items-center gap-2">
                        <DollarSign className="text-green-500" />
                        Cost Monitor
                    </h2>

                    <div className="space-y-4">
                        <CostItem label="Last Hour" value={`$${costs.hour.toFixed(6)}`} />
                        <CostItem label="Today" value={`$${costs.today.toFixed(6)}`} />
                        <CostItem label="Projected Monthly" value={`$${costs.projected.toFixed(2)}`} highlight />

                        <div className="mt-6 p-4 bg-slate-800/50 rounded-xl">
                            <p className="text-sm text-slate-400 mb-2">Current Settings Cost:</p>
                            <p className="text-lg font-semibold text-white">
                                {ttsConfig.engine === 'say' && '✨ Free (macOS Say)'}
                                {ttsConfig.engine === 'openai_tts' && `~$${(costs.projected * 1.5).toFixed(2)}/month`}
                                {ttsConfig.engine === 'piper' && '✨ Free (Local)'}
                            </p>
                        </div>
                    </div>
                </div>
            </div>

            {/* Recent Transcript */}
            <div className="bg-jarvis-dark rounded-2xl p-6 border border-slate-700">
                <h2 className="text-xl font-semibold text-white mb-4 flex items-center gap-2">
                    <BarChart3 className="text-jarvis-secondary" />
                    Recent Conversation
                </h2>

                <div className="space-y-3 max-h-96 overflow-y-auto">
                    {transcript.length > 0 ? (
                        transcript.map((item, index) => (
                            <div key={index} className={`p-4 rounded-xl ${item.role === 'user' ? 'bg-blue-900/20' : 'bg-slate-800/50'
                                }`}>
                                <div className="flex items-center gap-2 mb-1">
                                    <span className="text-xs font-semibold text-jarvis-primary">
                                        {item.role === 'user' ? 'You' : 'Jarvis'}
                                    </span>
                                    <span className="text-xs text-slate-500">{item.time}</span>
                                </div>
                                <p className="text-slate-200">{item.text}</p>
                            </div>
                        ))
                    ) : (
                        <p className="text-slate-500 text-center py-8">
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
        green: 'text-green-400',
        blue: 'text-blue-400',
        jarvis: 'text-jarvis-primary',
        slate: 'text-slate-400',
    }

    return (
        <div className="bg-jarvis-dark rounded-2xl p-6 border border-slate-700">
            <div className="flex items-center gap-3 mb-3">
                {icon}
                <span className="text-slate-400">{label}</span>
            </div>
            <p className={`text-2xl font-bold ${colorMap[statusColor]}`}>{status}</p>
        </div>
    )
}

function CostItem({ label, value, highlight }) {
    return (
        <div className="flex justify-between items-center">
            <span className="text-slate-400">{label}</span>
            <span className={`font-semibold ${highlight ? 'text-jarvis-primary text-xl' : 'text-white'}`}>
                {value}
            </span>
        </div>
    )
}

export default VoiceControl
