import React, { useState, useRef, useEffect } from 'react'
import { Send, Mic, MicOff, Loader2 } from 'lucide-react'
import useJarvisStore from '../stores/jarvisStore'

function Chat() {
  const { messages, addMessage, isListening, setIsListening } = useJarvisStore()
  const [input, setInput] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const messagesEndRef = useRef(null)

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  const handleSend = async () => {
    if (!input.trim() || isLoading) return

    const userMessage = input.trim()
    setInput('')
    addMessage({ role: 'user', content: userMessage })
    setIsLoading(true)

    try {
      const response = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: userMessage }),
      })

      if (response.ok) {
        const data = await response.json()
        addMessage({ role: 'assistant', content: data.response })
      } else {
        addMessage({ role: 'assistant', content: 'Sorry, I encountered an error. Please try again.' })
      }
    } catch (error) {
      console.error('Chat error:', error)
      addMessage({ role: 'assistant', content: 'Connection error. Make sure Jarvis backend is running.' })
    }

    setIsLoading(false)
  }

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const toggleVoice = () => {
    setIsListening(!isListening)
  }

  return (
    <div className="flex-1 flex flex-col h-full">
      {/* Header */}
      <header className="p-6 border-b border-slate-700">
        <h1 className="text-2xl font-bold text-white">Chat with Jarvis</h1>
        <p className="text-slate-400">Type or speak to interact</p>
      </header>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-6 space-y-4">
        {messages.length === 0 && (
          <div className="text-center py-12">
            <div className="w-20 h-20 rounded-full bg-jarvis-primary/20 flex items-center justify-center mx-auto mb-4">
              <span className="text-4xl">🤖</span>
            </div>
            <h2 className="text-xl font-semibold text-white mb-2">Hello! I'm Jarvis</h2>
            <p className="text-slate-400 max-w-md mx-auto">
              Your personal AI assistant. I can help you with tasks, research, 
              control your computer, and offer proactive suggestions.
            </p>
            <div className="mt-6 flex flex-wrap gap-2 justify-center">
              {['What can you do?', 'Research crypto trends', 'Open Safari', 'Check my schedule'].map((suggestion) => (
                <button
                  key={suggestion}
                  onClick={() => setInput(suggestion)}
                  className="px-4 py-2 bg-jarvis-dark border border-slate-600 rounded-xl text-slate-300 hover:border-jarvis-primary hover:text-white transition-colors"
                >
                  {suggestion}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((message) => (
          <MessageBubble key={message.id} message={message} />
        ))}

        {isLoading && (
          <div className="flex items-center gap-2 text-slate-400">
            <Loader2 className="animate-spin" size={20} />
            <span>Jarvis is thinking...</span>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className="p-4 border-t border-slate-700">
        <div className="flex gap-3">
          <button
            onClick={toggleVoice}
            className={`p-3 rounded-xl transition-colors ${
              isListening
                ? 'bg-jarvis-primary text-white'
                : 'bg-jarvis-dark border border-slate-600 text-slate-400 hover:text-white'
            }`}
          >
            {isListening ? <Mic size={24} /> : <MicOff size={24} />}
          </button>

          <div className="flex-1 relative">
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyPress={handleKeyPress}
              placeholder="Type a message or click the mic to speak..."
              rows={1}
              className="w-full bg-jarvis-dark border border-slate-600 rounded-xl px-4 py-3 text-white placeholder-slate-500 focus:outline-none focus:border-jarvis-primary resize-none"
            />
          </div>

          <button
            onClick={handleSend}
            disabled={!input.trim() || isLoading}
            className="p-3 bg-jarvis-primary text-white rounded-xl hover:bg-blue-600 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <Send size={24} />
          </button>
        </div>
      </div>
    </div>
  )
}

function MessageBubble({ message }) {
  const isUser = message.role === 'user'

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
      <div
        className={`max-w-[80%] rounded-2xl px-4 py-3 ${
          isUser
            ? 'bg-jarvis-primary text-white'
            : 'bg-jarvis-dark border border-slate-700 text-slate-200'
        }`}
      >
        <p className="whitespace-pre-wrap">{message.content}</p>
        <span className={`text-xs mt-1 block ${isUser ? 'text-blue-200' : 'text-slate-500'}`}>
          {new Date(message.timestamp).toLocaleTimeString()}
        </span>
      </div>
    </div>
  )
}

export default Chat
