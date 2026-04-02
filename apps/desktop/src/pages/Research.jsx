import React, { useState } from 'react'
import { Search, FileText, Loader2, Download, ExternalLink } from 'lucide-react'

function Research() {
  const [topic, setTopic] = useState('')
  const [depth, setDepth] = useState('medium')
  const [isResearching, setIsResearching] = useState(false)
  const [results, setResults] = useState(null)
  const [history, setHistory] = useState([])

  const handleResearch = async () => {
    if (!topic.trim() || isResearching) return

    setIsResearching(true)
    setResults(null)

    try {
      const response = await fetch('/api/research', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ topic, depth }),
      })

      if (response.ok) {
        const data = await response.json()
        setResults(data)
        setHistory(prev => [{ topic, depth, timestamp: new Date(), ...data }, ...prev].slice(0, 10))
      } else {
        setResults({ error: 'Research failed. Please try again.' })
      }
    } catch (error) {
      console.error('Research error:', error)
      setResults({ error: 'Connection error. Make sure Jarvis backend is running.' })
    }

    setIsResearching(false)
  }

  return (
    <div className="flex-1 flex flex-col h-full overflow-hidden">
      {/* Header */}
      <header style={{ padding: 'var(--space-lg)', borderBottom: '1px solid var(--border-color)' }}>
        <h1 style={{ fontSize: '1.5rem', fontWeight: 700, color: 'var(--text-primary)', marginBottom: 'var(--space-xs)' }}>Research</h1>
        <p style={{ color: 'var(--text-secondary)' }}>Let Jarvis research any topic for you</p>
      </header>

      <div style={{ flex: 1, overflowY: 'auto', padding: 'var(--space-lg)' }}>
        {/* Search Form */}
        <div className="card" style={{ marginBottom: 'var(--space-lg)' }}>
          <div style={{ display: 'flex', gap: 'var(--space-md)', marginBottom: 'var(--space-md)' }}>
            <div style={{ flex: 1 }}>
              <input
                type="text"
                value={topic}
                onChange={(e) => setTopic(e.target.value)}
                placeholder="Enter a topic to research..."
                className="input"
                style={{ width: '100%' }}
                onKeyPress={(e) => e.key === 'Enter' && handleResearch()}
              />
            </div>
            <select
              value={depth}
              onChange={(e) => setDepth(e.target.value)}
              className="input"
              style={{ width: 'auto' }}
            >
              <option value="quick">Quick (1 search)</option>
              <option value="medium">Medium (3 searches)</option>
              <option value="deep">Deep (5+ searches)</option>
            </select>
            <button
              onClick={handleResearch}
              disabled={!topic.trim() || isResearching}
              className="btn btn-primary"
              style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-xs)' }}
            >
              {isResearching ? (
                <>
                  <Loader2 className="animate-spin" size={20} />
                  Researching...
                </>
              ) : (
                <>
                  <Search size={20} />
                  Research
                </>
              )}
            </button>
          </div>

          {/* Quick Topics */}
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 'var(--space-xs)' }}>
            {['AI trends 2025', 'Crypto trading strategies', 'Best free software', 'Productivity hacks'].map((t) => (
              <button
                key={t}
                onClick={() => setTopic(t)}
                className="btn btn-ghost"
                style={{ fontSize: '0.875rem', padding: 'var(--space-xs) var(--space-sm)' }}
              >
                {t}
              </button>
            ))}
          </div>
        </div>

        {/* Results - Loading State */}
        {isResearching && (
          <div className="card" style={{ textAlign: 'center', padding: 'var(--space-2xl)' }}>
            <Loader2 className="animate-spin" size={48} style={{ margin: '0 auto var(--space-md)', color: 'var(--primary)' }} />
            <p style={{ color: 'var(--text-primary)', fontWeight: 500 }}>Researching "{topic}"...</p>
            <p style={{ color: 'var(--text-secondary)', fontSize: '0.875rem' }}>This may take a moment</p>
          </div>
        )}

        {/* Results - Completed */}
        {results && !isResearching && (
          <div className="card">
            {results.error ? (
              <p style={{ color: 'var(--danger)' }}>{results.error}</p>
            ) : (
              <>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 'var(--space-md)' }}>
                  <div>
                    <h2 style={{ fontSize: '1.25rem', fontWeight: 600, color: 'var(--text-primary)' }}>{results.topic}</h2>
                    <p style={{ color: 'var(--text-secondary)', fontSize: '0.875rem' }}>
                      Researched at {new Date(results.timestamp).toLocaleString()}
                    </p>
                  </div>
                  {results.document_path && (
                    <button className="btn btn-primary" style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-xs)' }}>
                      <Download size={18} />
                      Download
                    </button>
                  )}
                </div>

                <div style={{ 
                  background: 'var(--bg-secondary)', 
                  borderRadius: 'var(--radius-md)', 
                  padding: 'var(--space-md)', 
                  whiteSpace: 'pre-wrap',
                  color: 'var(--text-primary)'
                }}>
                  {results.summary}
                </div>

                {results.searches && results.searches.length > 0 && (
                  <div style={{ marginTop: 'var(--space-lg)' }}>
                    <h3 style={{ fontSize: '1rem', fontWeight: 500, color: 'var(--text-primary)', marginBottom: 'var(--space-sm)' }}>Search Queries Used</h3>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-xs)' }}>
                      {results.searches.map((search, index) => (
                        <div key={index} style={{ 
                          padding: 'var(--space-sm)', 
                          background: 'var(--bg-secondary)', 
                          borderRadius: 'var(--radius-sm)'
                        }}>
                          <p style={{ color: 'var(--primary)', fontWeight: 500 }}>{search.query}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </>
            )}
          </div>
        )}

        {/* History */}
        {history.length > 0 && !results && !isResearching && (
          <div>
            <h2 style={{ fontSize: '1.125rem', fontWeight: 600, color: 'var(--text-primary)', marginBottom: 'var(--space-md)' }}>Recent Research</h2>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-sm)' }}>
              {history.map((item, index) => (
                <div
                  key={index}
                  className="card hover-lift"
                  style={{ 
                    display: 'flex', 
                    justifyContent: 'space-between', 
                    alignItems: 'center', 
                    cursor: 'pointer',
                    transition: 'border-color 0.2s ease'
                  }}
                  onClick={() => setResults(item)}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-sm)' }}>
                    <FileText size={20} style={{ color: 'var(--primary)' }} />
                    <div>
                      <p style={{ color: 'var(--text-primary)', fontWeight: 500 }}>{item.topic}</p>
                      <p style={{ color: 'var(--text-secondary)', fontSize: '0.875rem' }}>
                        {new Date(item.timestamp).toLocaleDateString()} • {item.depth}
                      </p>
                    </div>
                  </div>
                  <ExternalLink size={18} style={{ color: 'var(--text-tertiary)' }} />
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

export default Research
