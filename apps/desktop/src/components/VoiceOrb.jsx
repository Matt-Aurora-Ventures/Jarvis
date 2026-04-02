import React, { useState, useEffect, useRef } from 'react'
import { Mic, MicOff, Volume2, Loader2 } from 'lucide-react'
import useJarvisStore from '../stores/jarvisStore'

/**
 * VoiceOrb - Animated voice control orb with waveform visualization
 */
function VoiceOrb() {
  const { isListening, setIsListening, voiceEnabled, addMessage } = useJarvisStore()
  const [isProcessing, setIsProcessing] = useState(false)
  const [isSpeaking, setIsSpeaking] = useState(false)
  const [transcript, setTranscript] = useState('')
  const [audioLevel, setAudioLevel] = useState(0)
  const audioContextRef = useRef(null)
  const analyserRef = useRef(null)
  const animationRef = useRef(null)

  // Audio visualization
  useEffect(() => {
    if (isListening && !audioContextRef.current) {
      initAudioVisualization()
    } else if (!isListening && audioContextRef.current) {
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
        setAudioLevel(average / 128) // Normalize to 0-2
        animationRef.current = requestAnimationFrame(updateLevel)
      }
      updateLevel()
    } catch (error) {
      console.error('Audio visualization error:', error)
    }
  }

  const cleanupAudio = () => {
    if (animationRef.current) {
      cancelAnimationFrame(animationRef.current)
    }
    if (audioContextRef.current) {
      audioContextRef.current.close()
      audioContextRef.current = null
    }
    setAudioLevel(0)
  }

  const toggleListening = async () => {
    if (isListening) {
      setIsListening(false)
      cleanupAudio()
    } else {
      setIsListening(true)
      try {
        const response = await fetch('/api/voice/start', { method: 'POST' })
        if (!response.ok) {
          console.error('Failed to start voice')
          setIsListening(false)
        }
      } catch (error) {
        console.error('Voice error:', error)
        setIsListening(false)
      }
    }
  }

  // Calculate ring animations based on audio level
  const ringScale = 1 + (audioLevel * 0.3)
  const pulseOpacity = 0.3 + (audioLevel * 0.4)

  return (
    <div className="voice-orb-container">
      {/* Transcript bubble */}
      {transcript && (
        <div className="voice-transcript">
          <p>{transcript}</p>
        </div>
      )}

      {/* Animated rings */}
      <div className="voice-rings">
        <div
          className={`voice-ring ring-1 ${isListening ? 'active' : ''}`}
          style={{
            transform: isListening ? `scale(${ringScale})` : 'scale(1)',
            opacity: isListening ? pulseOpacity : 0
          }}
        />
        <div
          className={`voice-ring ring-2 ${isListening ? 'active' : ''}`}
          style={{
            transform: isListening ? `scale(${ringScale * 1.2})` : 'scale(1)',
            opacity: isListening ? pulseOpacity * 0.6 : 0
          }}
        />
        <div
          className={`voice-ring ring-3 ${isListening ? 'active' : ''}`}
          style={{
            transform: isListening ? `scale(${ringScale * 1.4})` : 'scale(1)',
            opacity: isListening ? pulseOpacity * 0.3 : 0
          }}
        />
      </div>

      {/* Main orb */}
      <button
        onClick={toggleListening}
        className={`voice-orb ${isListening ? 'listening' : ''} ${isProcessing ? 'processing' : ''} ${isSpeaking ? 'speaking' : ''}`}
        aria-label={isListening ? 'Stop listening' : 'Start listening'}
      >
        {isProcessing ? (
          <Loader2 size={32} className="animate-spin" />
        ) : isSpeaking ? (
          <Volume2 size={32} />
        ) : isListening ? (
          <Mic size={32} />
        ) : (
          <MicOff size={32} />
        )}

        {/* Audio level bars */}
        {isListening && (
          <div className="audio-bars">
            {[...Array(5)].map((_, i) => (
              <div
                key={i}
                className="audio-bar"
                style={{
                  height: `${Math.min(100, (audioLevel * 50) + (Math.random() * 20))}%`,
                  animationDelay: `${i * 0.1}s`
                }}
              />
            ))}
          </div>
        )}
      </button>

      {/* Status text */}
      <span className={`voice-status ${isListening ? 'active' : ''}`}>
        {isProcessing ? 'Processing...' : isSpeaking ? 'Speaking...' : isListening ? 'Listening...' : 'Click to talk'}
      </span>

      <style jsx>{`
        .voice-orb-container {
          position: fixed;
          bottom: 32px;
          right: 32px;
          display: flex;
          flex-direction: column;
          align-items: center;
          gap: 16px;
          z-index: 100;
        }

        .voice-transcript {
          background: var(--bg-secondary);
          border: 1px solid var(--border-primary);
          border-radius: 16px;
          padding: 12px 16px;
          max-width: 280px;
          animation: slideUp 0.3s ease-out;
        }

        .voice-transcript p {
          margin: 0;
          font-size: 14px;
          color: var(--text-secondary);
        }

        .voice-rings {
          position: absolute;
          width: 80px;
          height: 80px;
          pointer-events: none;
        }

        .voice-ring {
          position: absolute;
          inset: 0;
          border-radius: 50%;
          border: 2px solid var(--accent-primary);
          transition: all 0.1s ease-out;
        }

        .ring-1 { animation: pulse 2s ease-in-out infinite; }
        .ring-2 { animation: pulse 2s ease-in-out infinite 0.3s; }
        .ring-3 { animation: pulse 2s ease-in-out infinite 0.6s; }

        .voice-orb {
          position: relative;
          width: 80px;
          height: 80px;
          border-radius: 50%;
          display: flex;
          align-items: center;
          justify-content: center;
          cursor: pointer;
          transition: all 0.3s ease;
          background: var(--bg-tertiary);
          border: 2px solid var(--border-secondary);
          color: var(--text-secondary);
        }

        .voice-orb:hover {
          transform: scale(1.05);
          border-color: var(--accent-primary);
        }

        .voice-orb.listening {
          background: var(--accent-primary);
          border-color: var(--accent-primary);
          color: white;
          box-shadow: 0 0 30px rgba(var(--accent-primary-rgb), 0.5);
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
          bottom: 8px;
          left: 50%;
          transform: translateX(-50%);
          display: flex;
          gap: 3px;
          height: 20px;
          align-items: flex-end;
        }

        .audio-bar {
          width: 4px;
          background: rgba(255, 255, 255, 0.8);
          border-radius: 2px;
          transition: height 0.1s ease-out;
        }

        .voice-status {
          font-size: 13px;
          color: var(--text-tertiary);
          transition: color 0.3s ease;
        }

        .voice-status.active {
          color: var(--accent-primary);
        }

        @keyframes slideUp {
          from {
            opacity: 0;
            transform: translateY(10px);
          }
          to {
            opacity: 1;
            transform: translateY(0);
          }
        }

        @keyframes pulse {
          0%, 100% {
            transform: scale(1);
            opacity: 0;
          }
          50% {
            transform: scale(1.5);
            opacity: 0.3;
          }
        }
      `}</style>
    </div>
  )
}

export default VoiceOrb
