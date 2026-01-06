import React, { useState, useEffect, useRef } from 'react'
import { Bot, XCircle, Send, MessageSquare } from 'lucide-react'
import { jarvisApi } from '@/lib/api'

/**
 * FloatingChat - Floating Jarvis chat bubble
 */
function FloatingChat({ jarvisStatus }) {
  const [isOpen, setIsOpen] = useState(false)
  const [messages, setMessages] = useState([
    { role: 'assistant', content: "Hello! I'm Jarvis. How can I assist with your trading today?" }
  ])
  const [input, setInput] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const messagesEndRef = useRef(null)

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(scrollToBottom, [messages])

  const sendMessage = async () => {
    if (!input.trim() || isLoading) return

    const userMessage = input.trim()
    setInput('')
    setMessages(prev => [...prev, { role: 'user', content: userMessage }])
    setIsLoading(true)

    try {
      const data = await jarvisApi.sendChat(userMessage)
      setMessages(prev => [...prev, { role: 'assistant', content: data.response }])
    } catch (e) {
      console.error('Chat error:', e)
      setMessages(prev => [...prev, { 
        role: 'assistant', 
        content: 'Sorry, I encountered an error. Please try again.' 
      }])
    } finally {
      setIsLoading(false)
    }
  }

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage()
    }
  }

  return (
    <div className="chat-bubble">
      {isOpen && (
        <div className="chat-panel slide-in">
          <div className="chat-header">
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Bot size={20} />
              <span style={{ fontWeight: 600 }}>Jarvis</span>
              {jarvisStatus?.is_running && (
                <span className="status-dot status-online" />
              )}
            </div>
            <button 
              onClick={() => setIsOpen(false)} 
              className="btn btn-ghost btn-sm" 
              style={{ color: 'white' }}
            >
              <XCircle size={16} />
            </button>
          </div>

          <div className="chat-messages">
            {messages.map((msg, i) => (
              <div key={i} className={`chat-message ${msg.role}`}>
                {msg.content}
              </div>
            ))}
            {isLoading && (
              <div className="chat-message assistant">
                <span className="typing-indicator">
                  <span></span>
                  <span></span>
                  <span></span>
                </span>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          <div className="chat-input-container">
            <input
              className="chat-input"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyPress={handleKeyPress}
              placeholder="Ask Jarvis..."
            />
            <button 
              onClick={sendMessage} 
              disabled={!input.trim() || isLoading}
              className="btn btn-primary btn-sm"
            >
              <Send size={14} />
            </button>
          </div>
        </div>
      )}

      <div 
        className="chat-trigger" 
        onClick={() => setIsOpen(!isOpen)}
        title="Chat with Jarvis"
      >
        <MessageSquare size={24} />
        {messages.length > 1 && (
          <span className="chat-badge">{messages.length - 1}</span>
        )}
      </div>
    </div>
  )
}

export default FloatingChat
