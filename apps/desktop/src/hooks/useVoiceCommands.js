import { useState, useEffect, useCallback, useRef } from 'react'

/**
 * Voice Command Patterns and Handlers
 * Recognizes natural language commands and maps to actions
 */
const COMMAND_PATTERNS = {
  // Navigation commands
  navigation: [
    { pattern: /^(go to|open|show) (dashboard|home)/i, action: 'navigate', params: { to: '/dashboard' } },
    { pattern: /^(go to|open|show) (trading|trade)/i, action: 'navigate', params: { to: '/trading' } },
    { pattern: /^(go to|open|show) (chat|messages?)/i, action: 'navigate', params: { to: '/chat' } },
    { pattern: /^(go to|open|show) (research|analyze)/i, action: 'navigate', params: { to: '/research' } },
    { pattern: /^(go to|open|show) settings/i, action: 'navigate', params: { to: '/settings' } },
    { pattern: /^(go to|open|show) voice (control|settings)/i, action: 'navigate', params: { to: '/voice' } },
  ],

  // Trading commands
  trading: [
    { pattern: /buy (\d+(?:\.\d+)?)\s*(sol|solana)/i, action: 'buy', extract: (m) => ({ amount: parseFloat(m[1]), asset: 'SOL' }) },
    { pattern: /sell (\d+(?:\.\d+)?)\s*(sol|solana)/i, action: 'sell', extract: (m) => ({ amount: parseFloat(m[1]), asset: 'SOL' }) },
    { pattern: /^what('?s| is) (the )?price (of )?(sol|solana|bitcoin|btc|ethereum|eth)/i, action: 'getPrice', extract: (m) => ({ asset: m[4] }) },
    { pattern: /^(check|show) (my )?portfolio/i, action: 'showPortfolio' },
    { pattern: /^(check|show) (my )?positions?/i, action: 'showPositions' },
    { pattern: /^(set|change) slippage (to )?(\d+(?:\.\d+)?)/i, action: 'setSlippage', extract: (m) => ({ slippage: parseFloat(m[3]) }) },
  ],

  // Market info commands
  market: [
    { pattern: /^(what('?s| is)|give me|show) (the )?market (sentiment|mood|vibe)/i, action: 'getSentiment' },
    { pattern: /^(show|what('?s| are)) (the )?trending (tokens?|coins?)/i, action: 'getTrending' },
    { pattern: /^(show|what('?s| are)) (the )?top (gainers?|movers?)/i, action: 'getGainers' },
    { pattern: /^(give me|run|generate) (a )?sentiment report/i, action: 'generateSentimentReport' },
  ],

  // Voice control commands
  voice: [
    { pattern: /^stop (listening|voice)/i, action: 'stopListening' },
    { pattern: /^(be )?quiet|shut up|mute/i, action: 'mute' },
    { pattern: /^unmute|resume voice/i, action: 'unmute' },
    { pattern: /^(what|list) commands?/i, action: 'listCommands' },
    { pattern: /^help|what can you do/i, action: 'help' },
  ],

  // System commands
  system: [
    { pattern: /^(restart|reboot) (the )?backend/i, action: 'restartBackend' },
    { pattern: /^(check|show) (backend )?(status|health)/i, action: 'checkHealth' },
    { pattern: /^clear (chat|history|messages?)/i, action: 'clearChat' },
    { pattern: /^(minimize|hide) (the )?window/i, action: 'minimize' },
    { pattern: /^(maximize|fullscreen) (the )?window/i, action: 'maximize' },
  ],

  // Query commands (for JARVIS)
  query: [
    { pattern: /^jarvis[,\s]+(.+)/i, action: 'askJarvis', extract: (m) => ({ query: m[1] }) },
    { pattern: /^(ask|tell) jarvis (.+)/i, action: 'askJarvis', extract: (m) => ({ query: m[2] }) },
    { pattern: /^hey jarvis[,\s]+(.+)/i, action: 'askJarvis', extract: (m) => ({ query: m[1] }) },
  ],
}

/**
 * useVoiceCommands - Parse and handle voice commands
 *
 * @param {object} handlers - Custom action handlers
 * @returns {object} Command recognition state and methods
 */
export function useVoiceCommands(handlers = {}) {
  const [lastCommand, setLastCommand] = useState(null)
  const [commandHistory, setCommandHistory] = useState([])
  const [isProcessing, setIsProcessing] = useState(false)
  const [feedback, setFeedback] = useState('')

  const handlersRef = useRef(handlers)
  handlersRef.current = handlers

  /**
   * Parse text and find matching command
   */
  const parseCommand = useCallback((text) => {
    const normalized = text.trim().toLowerCase()

    for (const [category, patterns] of Object.entries(COMMAND_PATTERNS)) {
      for (const { pattern, action, extract, params } of patterns) {
        const match = normalized.match(pattern) || text.match(pattern)
        if (match) {
          const extractedParams = extract ? extract(match) : {}
          return {
            category,
            action,
            params: { ...params, ...extractedParams },
            raw: text,
            match: match[0],
            confidence: match[0].length / text.length,
          }
        }
      }
    }

    return null
  }, [])

  /**
   * Execute a parsed command
   */
  const executeCommand = useCallback(async (command) => {
    if (!command) return { success: false, error: 'No command parsed' }

    setIsProcessing(true)
    setLastCommand(command)

    const entry = {
      ...command,
      timestamp: Date.now(),
      status: 'pending',
    }

    setCommandHistory(prev => [...prev.slice(-49), entry])

    try {
      // Check for custom handler first
      if (handlersRef.current[command.action]) {
        const result = await handlersRef.current[command.action](command.params)
        entry.status = 'success'
        entry.result = result
        setFeedback(result?.feedback || `Executed: ${command.action}`)
        return { success: true, result }
      }

      // Default handlers
      switch (command.action) {
        case 'navigate':
          if (typeof window !== 'undefined') {
            window.location.hash = command.params.to
          }
          entry.status = 'success'
          setFeedback(`Navigating to ${command.params.to}`)
          return { success: true }

        case 'listCommands':
          const commands = Object.entries(COMMAND_PATTERNS)
            .map(([cat, cmds]) => `${cat}: ${cmds.map(c => c.action).join(', ')}`)
            .join('\n')
          entry.status = 'success'
          entry.result = commands
          setFeedback('Available commands listed')
          return { success: true, result: commands }

        case 'help':
          entry.status = 'success'
          setFeedback('I can help with navigation, trading, market info, and more. Say "list commands" for details.')
          return { success: true }

        default:
          entry.status = 'unhandled'
          setFeedback(`Command "${command.action}" needs a handler`)
          return { success: false, error: 'No handler for command' }
      }
    } catch (err) {
      entry.status = 'error'
      entry.error = err.message
      setFeedback(`Error: ${err.message}`)
      return { success: false, error: err.message }
    } finally {
      setIsProcessing(false)
      setCommandHistory(prev => {
        const updated = [...prev]
        const idx = updated.findIndex(e => e.timestamp === entry.timestamp)
        if (idx >= 0) updated[idx] = entry
        return updated
      })
    }
  }, [])

  /**
   * Process raw text input - parse and execute
   */
  const processInput = useCallback(async (text) => {
    const command = parseCommand(text)

    if (command) {
      return await executeCommand(command)
    }

    // No command matched - treat as general query
    return await executeCommand({
      category: 'query',
      action: 'askJarvis',
      params: { query: text },
      raw: text,
      confidence: 1,
    })
  }, [parseCommand, executeCommand])

  /**
   * Clear feedback after delay
   */
  useEffect(() => {
    if (feedback) {
      const timer = setTimeout(() => setFeedback(''), 5000)
      return () => clearTimeout(timer)
    }
  }, [feedback])

  return {
    // State
    lastCommand,
    commandHistory,
    isProcessing,
    feedback,

    // Methods
    parseCommand,
    executeCommand,
    processInput,

    // Utils
    clearHistory: () => setCommandHistory([]),
    clearFeedback: () => setFeedback(''),

    // Patterns for reference
    patterns: COMMAND_PATTERNS,
  }
}

/**
 * useSpeechRecognition - Browser Speech Recognition API
 */
export function useSpeechRecognition(options = {}) {
  const {
    continuous = false,
    interimResults = true,
    lang = 'en-US',
    onResult,
    onError,
    onEnd,
  } = options

  const [isListening, setIsListening] = useState(false)
  const [transcript, setTranscript] = useState('')
  const [interimTranscript, setInterimTranscript] = useState('')
  const [supported, setSupported] = useState(false)
  const [error, setError] = useState(null)

  const recognitionRef = useRef(null)

  useEffect(() => {
    // Check for browser support
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition

    if (SpeechRecognition) {
      setSupported(true)
      recognitionRef.current = new SpeechRecognition()
      recognitionRef.current.continuous = continuous
      recognitionRef.current.interimResults = interimResults
      recognitionRef.current.lang = lang

      recognitionRef.current.onresult = (event) => {
        let interim = ''
        let final = ''

        for (let i = event.resultIndex; i < event.results.length; i++) {
          const result = event.results[i]
          if (result.isFinal) {
            final += result[0].transcript
          } else {
            interim += result[0].transcript
          }
        }

        setInterimTranscript(interim)
        if (final) {
          setTranscript(prev => prev + ' ' + final)
          onResult?.(final)
        }
      }

      recognitionRef.current.onerror = (event) => {
        console.error('Speech recognition error:', event.error)
        setError(event.error)
        onError?.(event.error)
      }

      recognitionRef.current.onend = () => {
        setIsListening(false)
        onEnd?.()
      }
    }

    return () => {
      if (recognitionRef.current) {
        recognitionRef.current.stop()
      }
    }
  }, [continuous, interimResults, lang, onResult, onError, onEnd])

  const start = useCallback(() => {
    if (recognitionRef.current && !isListening) {
      setTranscript('')
      setInterimTranscript('')
      setError(null)
      recognitionRef.current.start()
      setIsListening(true)
    }
  }, [isListening])

  const stop = useCallback(() => {
    if (recognitionRef.current && isListening) {
      recognitionRef.current.stop()
      setIsListening(false)
    }
  }, [isListening])

  const abort = useCallback(() => {
    if (recognitionRef.current) {
      recognitionRef.current.abort()
      setIsListening(false)
    }
  }, [])

  return {
    isListening,
    transcript,
    interimTranscript,
    supported,
    error,
    start,
    stop,
    abort,
    resetTranscript: () => setTranscript(''),
  }
}

export default useVoiceCommands
