import React, { useState, useRef, useEffect, useCallback } from 'react'
import { Send, Mic, MicOff, Loader2, MessageCircle, Sparkles } from 'lucide-react'

// Components
import { Card, Button, Input } from '@/components/ui'
import { EmptyState, LoadingSpinner } from '@/components/common'

// Store
import useJarvisStore from '@/stores/jarvisStore'

// Lib
import { jarvisApi } from '@/lib/api'

/**
 * Chat - Full page Jarvis chat interface
 * Refactored with modular components and improved UX
 */
function Chat() {
  const { messages, addMessage, isListening, setIsListening } = useJarvisStore()
  const [input, setInput] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const messagesEndRef = useRef(null)
  const inputRef = useRef(null)

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  // Focus input on mount
  useEffect(() => {
    inputRef.current?.focus()
  }, [])

  const handleSend = useCallback(async () => {
    if (!input.trim() || isLoading) return

    const userMessage = input.trim()
    setInput('')
    addMessage({ role: 'user', content: userMessage })
    setIsLoading(true)

    try {
      const data = await jarvisApi.chat(userMessage)
      addMessage({ role: 'assistant', content: data.response })
    } catch (error) {
      console.error('Chat error:', error)
      addMessage({ 
        role: 'assistant', 
        content: error.message || 'Connection error. Make sure Jarvis backend is running.' 
      })
    } finally {
      setIsLoading(false)
      inputRef.current?.focus()
    }
  }, [input, isLoading, addMessage])

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const handleSuggestionClick = (suggestion) => {
    setInput(suggestion)
    inputRef.current?.focus()
  }

  return (
    <div 
      className="flex-1 flex flex-col h-full"
      style={{ background: 'var(--bg-secondary)' }}
    >
      {/* Header */}
      <header 
        className="p-6"
        style={{ borderBottom: '1px solid var(--border-default)' }}
      >
        <h1 
          className="text-2xl font-bold mb-1"
          style={{ color: 'var(--text-primary)' }}
        >
          Chat with Jarvis
        </h1>
        <p style={{ color: 'var(--text-secondary)' }}>
          Type or speak to interact with your AI assistant
        </p>
      </header>

      {/* Messages Container */}
      <div className="flex-1 overflow-y-auto p-6 space-y-4">
        {messages.length === 0 ? (
          <WelcomeState onSuggestionClick={handleSuggestionClick} />
        ) : (
          <>
            {messages.map((message) => (
              <MessageBubble key={message.id} message={message} />
            ))}
          </>
        )}

        {/* Typing Indicator */}
        {isLoading && <TypingIndicator />}

        {/* Scroll anchor */}
        <div ref={messagesEndRef} />
      </div>

      {/* Input Area */}
      <ChatInput
        ref={inputRef}
        value={input}
        onChange={setInput}
        onSend={handleSend}
        onKeyPress={handleKeyPress}
        isLoading={isLoading}
        isListening={isListening}
        onToggleVoice={() => setIsListening(!isListening)}
      />
    </div>
  )
}

/* =========== Sub-Components =========== */

/**
 * WelcomeState - Empty chat welcome screen
 */
function WelcomeState({ onSuggestionClick }) {
  const suggestions = [
    'What can you do?',
    'Research crypto trends',
    'Analyze my portfolio',
    'Check market sentiment',
  ]

  return (
    <div className="text-center py-12">
      <div 
        className="w-20 h-20 rounded-full flex items-center justify-center mx-auto mb-4"
        style={{ background: 'var(--info-bg)' }}
      >
        <Sparkles size={40} style={{ color: 'var(--primary)' }} />
      </div>
      
      <h2 
        className="text-xl font-semibold mb-2"
        style={{ color: 'var(--text-primary)' }}
      >
        Hello! I'm Jarvis
      </h2>
      
      <p 
        className="max-w-md mx-auto mb-6"
        style={{ color: 'var(--text-secondary)' }}
      >
        Your personal AI trading assistant. I can help you with market research,
        portfolio analysis, and proactive trading suggestions.
      </p>
      
      <div className="flex flex-wrap gap-2 justify-center">
        {suggestions.map((suggestion) => (
          <button
            key={suggestion}
            onClick={() => onSuggestionClick(suggestion)}
            className="px-4 py-2 rounded-xl text-sm font-medium transition-all duration-200"
            style={{
              background: 'var(--bg-tertiary)',
              border: '1px solid var(--border-default)',
              color: 'var(--text-secondary)',
            }}
            onMouseEnter={(e) => {
              e.target.style.borderColor = 'var(--primary)'
              e.target.style.color = 'var(--text-primary)'
            }}
            onMouseLeave={(e) => {
              e.target.style.borderColor = 'var(--border-default)'
              e.target.style.color = 'var(--text-secondary)'
            }}
          >
            {suggestion}
          </button>
        ))}
      </div>
    </div>
  )
}

/**
 * MessageBubble - Chat message display
 */
function MessageBubble({ message }) {
  const isUser = message.role === 'user'

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
      <div
        className="max-w-[80%] rounded-2xl px-4 py-3"
        style={{
          background: isUser ? 'var(--primary)' : 'var(--bg-tertiary)',
          color: isUser ? 'var(--text-inverse)' : 'var(--text-primary)',
          borderBottomRightRadius: isUser ? '4px' : undefined,
          borderBottomLeftRadius: !isUser ? '4px' : undefined,
        }}
      >
        <p className="whitespace-pre-wrap">{message.content}</p>
        <span 
          className="text-xs mt-1 block opacity-60"
        >
          {new Date(message.timestamp).toLocaleTimeString()}
        </span>
      </div>
    </div>
  )
}

/**
 * TypingIndicator - Shows when Jarvis is thinking
 */
function TypingIndicator() {
  return (
    <div 
      className="flex items-center gap-2 px-4 py-3 rounded-2xl max-w-[120px]"
      style={{ background: 'var(--bg-tertiary)' }}
    >
      <div className="typing-indicator">
        <span />
        <span />
        <span />
      </div>
    </div>
  )
}

/**
 * ChatInput - Message input with voice toggle
 */
const ChatInput = React.forwardRef(({ 
  value, 
  onChange, 
  onSend, 
  onKeyPress, 
  isLoading,
  isListening,
  onToggleVoice,
}, ref) => {
  return (
    <div 
      className="p-4"
      style={{ borderTop: '1px solid var(--border-default)' }}
    >
      <div className="flex gap-3">
        {/* Voice Toggle */}
        <Button
          variant={isListening ? 'primary' : 'secondary'}
          onClick={onToggleVoice}
          className="flex-shrink-0"
        >
          {isListening ? <Mic size={20} /> : <MicOff size={20} />}
        </Button>

        {/* Text Input */}
        <div className="flex-1 relative">
          <textarea
            ref={ref}
            value={value}
            onChange={(e) => onChange(e.target.value)}
            onKeyPress={onKeyPress}
            placeholder="Type a message or click the mic to speak..."
            rows={1}
            className="input resize-none py-3"
            style={{ paddingRight: '48px' }}
          />
        </div>

        {/* Send Button */}
        <Button
          variant="primary"
          onClick={onSend}
          disabled={!value.trim() || isLoading}
          className="flex-shrink-0"
        >
          {isLoading ? (
            <LoadingSpinner size="sm" />
          ) : (
            <Send size={20} />
          )}
        </Button>
      </div>
    </div>
  )
})

ChatInput.displayName = 'ChatInput'

export default Chat
