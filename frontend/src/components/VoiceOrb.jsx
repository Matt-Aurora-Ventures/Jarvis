import React, { useState, useEffect } from 'react'
import { Mic, MicOff, Volume2 } from 'lucide-react'
import useJarvisStore from '../stores/jarvisStore'

function VoiceOrb() {
  const { isListening, setIsListening, voiceEnabled, addMessage } = useJarvisStore()
  const [isProcessing, setIsProcessing] = useState(false)
  const [transcript, setTranscript] = useState('')

  const toggleListening = async () => {
    if (isListening) {
      setIsListening(false)
      // Stop listening logic
    } else {
      setIsListening(true)
      // Start listening logic - will connect to backend
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

  return (
    <div className="fixed bottom-8 right-8 flex flex-col items-center gap-4">
      {/* Transcript bubble */}
      {transcript && (
        <div className="bg-jarvis-dark border border-slate-600 rounded-2xl px-4 py-2 max-w-xs">
          <p className="text-sm text-slate-300">{transcript}</p>
        </div>
      )}

      {/* Main orb */}
      <button
        onClick={toggleListening}
        className={`
          w-20 h-20 rounded-full flex items-center justify-center
          transition-all duration-300 transform hover:scale-105
          ${isListening 
            ? 'bg-jarvis-primary jarvis-glow listening-active' 
            : 'bg-jarvis-dark border-2 border-slate-600 hover:border-jarvis-primary'
          }
          ${isProcessing ? 'animate-pulse' : ''}
        `}
      >
        {isListening ? (
          <Mic size={32} className="text-white" />
        ) : (
          <MicOff size={32} className="text-slate-400" />
        )}
      </button>

      {/* Status text */}
      <span className={`text-sm ${isListening ? 'text-jarvis-primary' : 'text-slate-500'}`}>
        {isListening ? 'Listening...' : 'Click to talk'}
      </span>
    </div>
  )
}

export default VoiceOrb
