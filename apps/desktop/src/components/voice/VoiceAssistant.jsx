import React, { useState, useEffect, useCallback, useRef } from 'react'
import {
  Mic,
  MicOff,
  Volume2,
  VolumeX,
  Settings,
  Loader2,
  AudioLines,
  Command,
  AlertCircle,
  CheckCircle2
} from 'lucide-react'
import { useVoiceCommands, useSpeechRecognition } from '../../hooks/useVoiceCommands'

/**
 * VoiceAssistant - Full voice control interface with speech recognition
 *
 * Features:
 * - Wake word detection ("jarvis", "hey jarvis")
 * - Natural language command parsing
 * - Text-to-speech responses
 * - Command feedback display
 * - Waveform visualization
 */
export default function VoiceAssistant({ onCommand, onNavigate, compact = false }) {
  // Voice command handling
  const {
    lastCommand,
    commandHistory,
    isProcessing: isCommandProcessing,
    feedback,
    processInput,
    clearFeedback,
  } = useVoiceCommands({
    // Custom handlers
    navigate: ({ to }) => {
      onNavigate?.(to)
      return { feedback: `Navigating to ${to}` }
    },
    askJarvis: async ({ query }) => {
      // Forward to JARVIS API
      try {
        const response = await fetch('/api/chat', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ message: query }),
        })
        if (response.ok) {
          const data = await response.json()
          speak(data.response)
          return { feedback: data.response, response: data.response }
        }
      } catch (err) {
        console.error('JARVIS query error:', err)
      }
      return { feedback: 'Failed to get response' }
    },
    getSentiment: async () => {
      try {
        const response = await fetch('/api/sentiment')
        if (response.ok) {
          const data = await response.json()
          const msg = `Market sentiment is ${data.overall}. ${data.summary}`
          speak(msg)
          return { feedback: msg }
        }
      } catch (err) {
        console.error('Sentiment fetch error:', err)
      }
      return { feedback: 'Could not fetch sentiment' }
    },
    getPrice: async ({ asset }) => {
      try {
        const response = await fetch(`/api/price/${asset}`)
        if (response.ok) {
          const data = await response.json()
          const msg = `${asset.toUpperCase()} is at $${data.price.toFixed(2)}, ${data.change > 0 ? 'up' : 'down'} ${Math.abs(data.change).toFixed(1)} percent`
          speak(msg)
          return { feedback: msg }
        }
      } catch (err) {
        console.error('Price fetch error:', err)
      }
      return { feedback: `Could not get ${asset} price` }
    },
    stopListening: () => {
      stopRecognition()
      return { feedback: 'Voice control stopped' }
    },
    mute: () => {
      setMuted(true)
      return { feedback: 'Muted' }
    },
    unmute: () => {
      setMuted(false)
      return { feedback: 'Unmuted' }
    },
    minimize: () => {
      window.jarvis?.minimize?.()
      return { feedback: 'Window minimized' }
    },
    maximize: () => {
      window.jarvis?.maximize?.()
      return { feedback: 'Window maximized' }
    },
    restartBackend: async () => {
      await window.jarvis?.restartBackend?.()
      return { feedback: 'Backend restarting' }
    },
  })

  // Speech recognition
  const {
    isListening,
    transcript,
    interimTranscript,
    supported: recognitionSupported,
    error: recognitionError,
    start: startRecognition,
    stop: stopRecognition,
    resetTranscript,
  } = useSpeechRecognition({
    continuous: true,
    interimResults: true,
    onResult: handleSpeechResult,
  })

  // Component state
  const [muted, setMuted] = useState(false)
  const [wakeWordActive, setWakeWordActive] = useState(false)
  const [pendingInput, setPendingInput] = useState('')
  const [audioLevel, setAudioLevel] = useState(0)
  const [isSpeaking, setIsSpeaking] = useState(false)

  // Audio context for visualization
  const audioContextRef = useRef(null)
  const analyserRef = useRef(null)
  const animationRef = useRef(null)
  const synthRef = useRef(null)

  // Initialize speech synthesis
  useEffect(() => {
    synthRef.current = window.speechSynthesis
  }, [])

  // Audio visualization
  useEffect(() => {
    if (isListening) {
      initAudioVisualization()
    } else {
      cleanupAudio()
    }
    return () => cleanupAudio()
  }, [isListening])

  const initAudioVisualization = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      audioContextRef.current = new (window.AudioContext || window.webkitAudioContext)()
      analyserRef.current = audioContextRef.current.createAnalyser()
      const source = audioContextRef.current.createMediaStreamSource(stream)
      source.connect(analyserRef.current)
      analyserRef.current.fftSize = 256

      const updateLevel = () => {
        if (!analyserRef.current) return
        const dataArray = new Uint8Array(analyserRef.current.frequencyBinCount)
        analyserRef.current.getByteFrequencyData(dataArray)
        const average = dataArray.reduce((a, b) => a + b) / dataArray.length
        setAudioLevel(average / 128)
        animationRef.current = requestAnimationFrame(updateLevel)
      }
      updateLevel()
    } catch (err) {
      console.error('Audio visualization error:', err)
    }
  }

  const cleanupAudio = () => {
    if (animationRef.current) cancelAnimationFrame(animationRef.current)
    if (audioContextRef.current) {
      audioContextRef.current.close()
      audioContextRef.current = null
    }
    setAudioLevel(0)
  }

  // Handle speech recognition results
  function handleSpeechResult(text) {
    if (!text) return

    const normalized = text.toLowerCase().trim()

    // Wake word detection
    if (normalized.includes('jarvis') || normalized.includes('hey jarvis')) {
      setWakeWordActive(true)
      // Extract command after wake word
      const afterWake = normalized.replace(/^(hey\s+)?jarvis[,\s]*/i, '').trim()
      if (afterWake) {
        processPendingInput(afterWake)
      }
      return
    }

    // If wake word is active, process any input
    if (wakeWordActive) {
      processPendingInput(normalized)
    }
  }

  async function processPendingInput(text) {
    setPendingInput(text)
    const result = await processInput(text)
    onCommand?.(result)

    // Reset after processing
    setTimeout(() => {
      setPendingInput('')
      setWakeWordActive(false)
      resetTranscript()
    }, 2000)
  }

  // Text-to-speech
  const speak = useCallback((text) => {
    if (muted || !synthRef.current || !text) return

    // Cancel any ongoing speech
    synthRef.current.cancel()

    const utterance = new SpeechSynthesisUtterance(text)
    utterance.rate = 1.0
    utterance.pitch = 1.0
    utterance.volume = 0.8

    // Try to use a good voice
    const voices = synthRef.current.getVoices()
    const preferredVoice = voices.find(v =>
      v.name.includes('Samantha') ||
      v.name.includes('Alex') ||
      v.name.includes('Google UK English Male') ||
      v.lang.startsWith('en')
    )
    if (preferredVoice) utterance.voice = preferredVoice

    utterance.onstart = () => setIsSpeaking(true)
    utterance.onend = () => setIsSpeaking(false)
    utterance.onerror = () => setIsSpeaking(false)

    synthRef.current.speak(utterance)
  }, [muted])

  // Stop speaking
  const stopSpeaking = useCallback(() => {
    if (synthRef.current) {
      synthRef.current.cancel()
      setIsSpeaking(false)
    }
  }, [])

  // Toggle listening
  const toggleListening = () => {
    if (isListening) {
      stopRecognition()
    } else {
      startRecognition()
    }
  }

  // Render compact version
  if (compact) {
    return (
      <div className="voice-assistant-compact">
        <button
          onClick={toggleListening}
          className={`voice-btn ${isListening ? 'listening' : ''} ${wakeWordActive ? 'active' : ''}`}
          title={isListening ? 'Stop listening' : 'Start listening'}
        >
          {isListening ? <Mic size={20} /> : <MicOff size={20} />}
          {isListening && (
            <span className="pulse-ring" style={{ transform: `scale(${1 + audioLevel * 0.5})` }} />
          )}
        </button>

        <button
          onClick={() => setMuted(!muted)}
          className={`voice-btn ${muted ? 'muted' : ''}`}
          title={muted ? 'Unmute' : 'Mute'}
        >
          {muted ? <VolumeX size={20} /> : <Volume2 size={20} />}
        </button>

        {(feedback || wakeWordActive) && (
          <div className="voice-feedback">
            {wakeWordActive && !feedback && <span className="wake-indicator">Listening...</span>}
            {feedback && <span className="feedback-text">{feedback}</span>}
          </div>
        )}

        <style jsx>{`
          .voice-assistant-compact {
            display: flex;
            align-items: center;
            gap: 8px;
            position: relative;
          }

          .voice-btn {
            position: relative;
            width: 36px;
            height: 36px;
            border-radius: 50%;
            border: 1px solid var(--border-secondary);
            background: var(--bg-secondary);
            color: var(--text-secondary);
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            transition: all 0.2s ease;
          }

          .voice-btn:hover {
            border-color: var(--primary);
            color: var(--primary);
          }

          .voice-btn.listening {
            background: var(--primary);
            border-color: var(--primary);
            color: white;
          }

          .voice-btn.active {
            box-shadow: 0 0 0 3px rgba(var(--primary-rgb), 0.3);
          }

          .voice-btn.muted {
            opacity: 0.6;
          }

          .pulse-ring {
            position: absolute;
            inset: -4px;
            border: 2px solid var(--primary);
            border-radius: 50%;
            opacity: 0.5;
            transition: transform 0.1s ease-out;
          }

          .voice-feedback {
            position: absolute;
            top: 100%;
            left: 0;
            margin-top: 8px;
            padding: 8px 12px;
            background: var(--bg-secondary);
            border: 1px solid var(--border-primary);
            border-radius: 8px;
            font-size: 13px;
            white-space: nowrap;
            z-index: 100;
            animation: fadeIn 0.2s ease;
          }

          .wake-indicator {
            color: var(--primary);
            font-weight: 500;
          }

          .feedback-text {
            color: var(--text-primary);
          }

          @keyframes fadeIn {
            from { opacity: 0; transform: translateY(-4px); }
            to { opacity: 1; transform: translateY(0); }
          }
        `}</style>
      </div>
    )
  }

  // Full version
  return (
    <div className="voice-assistant">
      {/* Status bar */}
      <div className="voice-status-bar">
        <div className="status-item">
          {recognitionSupported ? (
            <CheckCircle2 size={16} style={{ color: 'var(--success)' }} />
          ) : (
            <AlertCircle size={16} style={{ color: 'var(--error)' }} />
          )}
          <span>Speech Recognition</span>
        </div>
        <div className="status-item">
          {wakeWordActive ? (
            <span className="badge active">Active</span>
          ) : (
            <span className="badge">Say "Jarvis"</span>
          )}
        </div>
        {recognitionError && (
          <div className="status-item error">
            <AlertCircle size={16} />
            <span>{recognitionError}</span>
          </div>
        )}
      </div>

      {/* Main voice orb */}
      <div className="voice-orb-section">
        {/* Animated rings */}
        <div className="voice-rings">
          {[1, 2, 3].map(i => (
            <div
              key={i}
              className={`voice-ring ring-${i} ${isListening ? 'active' : ''}`}
              style={{
                transform: isListening ? `scale(${1 + audioLevel * 0.2 * i})` : 'scale(1)',
                opacity: isListening ? 0.3 - (i * 0.08) : 0,
              }}
            />
          ))}
        </div>

        {/* Main button */}
        <button
          onClick={toggleListening}
          className={`voice-orb ${isListening ? 'listening' : ''} ${wakeWordActive ? 'wake-active' : ''} ${isCommandProcessing ? 'processing' : ''} ${isSpeaking ? 'speaking' : ''}`}
        >
          {isCommandProcessing ? (
            <Loader2 size={40} className="animate-spin" />
          ) : isSpeaking ? (
            <Volume2 size={40} />
          ) : isListening ? (
            <Mic size={40} />
          ) : (
            <MicOff size={40} />
          )}

          {/* Audio level bars */}
          {isListening && (
            <div className="audio-bars">
              {[...Array(5)].map((_, i) => (
                <div
                  key={i}
                  className="audio-bar"
                  style={{
                    height: `${Math.min(100, audioLevel * 60 + Math.random() * 20)}%`,
                    animationDelay: `${i * 0.1}s`
                  }}
                />
              ))}
            </div>
          )}
        </button>

        {/* Status text */}
        <div className="voice-label">
          {isCommandProcessing ? 'Processing...' :
            isSpeaking ? 'Speaking...' :
              wakeWordActive ? 'Listening for command...' :
                isListening ? 'Say "Jarvis" to start' :
                  'Click to start voice control'}
        </div>
      </div>

      {/* Transcript display */}
      <div className="transcript-section">
        <div className="transcript-label">
          <AudioLines size={16} />
          <span>Transcript</span>
        </div>

        <div className="transcript-content">
          {interimTranscript && (
            <span className="interim">{interimTranscript}</span>
          )}
          {pendingInput && (
            <span className="pending">{pendingInput}</span>
          )}
          {!interimTranscript && !pendingInput && (
            <span className="placeholder">
              {isListening ? 'Listening...' : 'Voice input will appear here'}
            </span>
          )}
        </div>
      </div>

      {/* Feedback display */}
      {feedback && (
        <div className="feedback-section">
          <div className="feedback-content">
            <Command size={16} />
            <span>{feedback}</span>
          </div>
        </div>
      )}

      {/* Quick controls */}
      <div className="voice-controls">
        <button
          onClick={() => setMuted(!muted)}
          className={`control-btn ${muted ? 'active' : ''}`}
          title={muted ? 'Unmute' : 'Mute'}
        >
          {muted ? <VolumeX size={20} /> : <Volume2 size={20} />}
          <span>{muted ? 'Unmute' : 'Mute'}</span>
        </button>

        <button
          onClick={stopSpeaking}
          className="control-btn"
          title="Stop speaking"
          disabled={!isSpeaking}
        >
          <VolumeX size={20} />
          <span>Stop</span>
        </button>

        <button
          onClick={() => speak('Hello, I am Jarvis. Voice control is operational.')}
          className="control-btn"
          title="Test voice"
        >
          <Volume2 size={20} />
          <span>Test</span>
        </button>
      </div>

      {/* Recent commands */}
      {commandHistory.length > 0 && (
        <div className="history-section">
          <div className="history-label">Recent Commands</div>
          <div className="history-list">
            {commandHistory.slice(-5).reverse().map((cmd, i) => (
              <div key={i} className={`history-item ${cmd.status}`}>
                <span className="history-action">{cmd.action}</span>
                <span className="history-raw">{cmd.raw?.slice(0, 40)}</span>
                <span className={`history-status ${cmd.status}`}>
                  {cmd.status === 'success' ? '✓' : cmd.status === 'error' ? '✗' : '...'}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      <style jsx>{`
        .voice-assistant {
          display: flex;
          flex-direction: column;
          gap: 24px;
          padding: 24px;
          max-width: 480px;
          margin: 0 auto;
        }

        .voice-status-bar {
          display: flex;
          align-items: center;
          gap: 16px;
          padding: 12px 16px;
          background: var(--bg-secondary);
          border-radius: 12px;
          flex-wrap: wrap;
        }

        .status-item {
          display: flex;
          align-items: center;
          gap: 6px;
          font-size: 13px;
          color: var(--text-secondary);
        }

        .status-item.error {
          color: var(--error);
        }

        .badge {
          padding: 4px 10px;
          background: var(--bg-tertiary);
          border-radius: 12px;
          font-size: 12px;
          font-weight: 500;
        }

        .badge.active {
          background: var(--primary);
          color: white;
        }

        .voice-orb-section {
          display: flex;
          flex-direction: column;
          align-items: center;
          gap: 16px;
          padding: 40px 0;
          position: relative;
        }

        .voice-rings {
          position: absolute;
          width: 120px;
          height: 120px;
          pointer-events: none;
        }

        .voice-ring {
          position: absolute;
          inset: 0;
          border-radius: 50%;
          border: 2px solid var(--primary);
          transition: all 0.15s ease-out;
        }

        .voice-ring.active {
          animation: pulse 2s ease-in-out infinite;
        }

        .ring-1 { animation-delay: 0s; }
        .ring-2 { animation-delay: 0.3s; }
        .ring-3 { animation-delay: 0.6s; }

        .voice-orb {
          position: relative;
          width: 120px;
          height: 120px;
          border-radius: 50%;
          border: 3px solid var(--border-secondary);
          background: var(--bg-tertiary);
          color: var(--text-secondary);
          cursor: pointer;
          display: flex;
          align-items: center;
          justify-content: center;
          transition: all 0.3s ease;
        }

        .voice-orb:hover {
          transform: scale(1.05);
          border-color: var(--primary);
        }

        .voice-orb.listening {
          background: linear-gradient(135deg, var(--primary), var(--primary-dark, var(--primary)));
          border-color: transparent;
          color: white;
          box-shadow: 0 8px 32px rgba(var(--primary-rgb), 0.4);
        }

        .voice-orb.wake-active {
          animation: glow 1.5s ease-in-out infinite;
        }

        .voice-orb.processing {
          background: var(--warning);
          border-color: var(--warning);
        }

        .voice-orb.speaking {
          background: var(--success);
          border-color: var(--success);
        }

        .audio-bars {
          position: absolute;
          bottom: 12px;
          display: flex;
          gap: 4px;
          align-items: flex-end;
          height: 24px;
        }

        .audio-bar {
          width: 5px;
          background: rgba(255, 255, 255, 0.8);
          border-radius: 2px;
          transition: height 0.1s ease-out;
        }

        .voice-label {
          font-size: 14px;
          color: var(--text-secondary);
          text-align: center;
        }

        .transcript-section {
          background: var(--bg-secondary);
          border-radius: 12px;
          padding: 16px;
        }

        .transcript-label {
          display: flex;
          align-items: center;
          gap: 8px;
          font-size: 13px;
          font-weight: 500;
          color: var(--text-secondary);
          margin-bottom: 12px;
        }

        .transcript-content {
          min-height: 48px;
          padding: 12px;
          background: var(--bg-tertiary);
          border-radius: 8px;
          font-size: 15px;
        }

        .transcript-content .placeholder {
          color: var(--text-tertiary);
        }

        .transcript-content .interim {
          color: var(--text-secondary);
          font-style: italic;
        }

        .transcript-content .pending {
          color: var(--primary);
          font-weight: 500;
        }

        .feedback-section {
          animation: slideIn 0.3s ease;
        }

        .feedback-content {
          display: flex;
          align-items: center;
          gap: 12px;
          padding: 16px;
          background: rgba(var(--primary-rgb), 0.1);
          border: 1px solid rgba(var(--primary-rgb), 0.2);
          border-radius: 12px;
          color: var(--text-primary);
        }

        .voice-controls {
          display: flex;
          gap: 12px;
          justify-content: center;
        }

        .control-btn {
          display: flex;
          align-items: center;
          gap: 8px;
          padding: 10px 16px;
          background: var(--bg-secondary);
          border: 1px solid var(--border-secondary);
          border-radius: 8px;
          color: var(--text-secondary);
          font-size: 13px;
          cursor: pointer;
          transition: all 0.2s ease;
        }

        .control-btn:hover:not(:disabled) {
          border-color: var(--primary);
          color: var(--primary);
        }

        .control-btn:disabled {
          opacity: 0.5;
          cursor: not-allowed;
        }

        .control-btn.active {
          background: var(--primary);
          border-color: var(--primary);
          color: white;
        }

        .history-section {
          background: var(--bg-secondary);
          border-radius: 12px;
          padding: 16px;
        }

        .history-label {
          font-size: 13px;
          font-weight: 500;
          color: var(--text-secondary);
          margin-bottom: 12px;
        }

        .history-list {
          display: flex;
          flex-direction: column;
          gap: 8px;
        }

        .history-item {
          display: flex;
          align-items: center;
          gap: 12px;
          padding: 10px 12px;
          background: var(--bg-tertiary);
          border-radius: 8px;
          font-size: 13px;
        }

        .history-action {
          font-weight: 500;
          color: var(--primary);
        }

        .history-raw {
          flex: 1;
          color: var(--text-secondary);
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
        }

        .history-status {
          font-weight: 600;
        }

        .history-status.success { color: var(--success); }
        .history-status.error { color: var(--error); }
        .history-status.pending { color: var(--warning); }

        @keyframes pulse {
          0%, 100% { transform: scale(1); opacity: 0; }
          50% { transform: scale(1.5); opacity: 0.2; }
        }

        @keyframes glow {
          0%, 100% { box-shadow: 0 8px 32px rgba(var(--primary-rgb), 0.4); }
          50% { box-shadow: 0 8px 48px rgba(var(--primary-rgb), 0.6); }
        }

        @keyframes slideIn {
          from { opacity: 0; transform: translateY(-8px); }
          to { opacity: 1; transform: translateY(0); }
        }
      `}</style>
    </div>
  )
}
