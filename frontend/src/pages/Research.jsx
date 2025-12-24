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
      <header className="p-6 border-b border-slate-700">
        <h1 className="text-2xl font-bold text-white">Research</h1>
        <p className="text-slate-400">Let Jarvis research any topic for you</p>
      </header>

      <div className="flex-1 overflow-y-auto p-6">
        {/* Search Form */}
        <div className="bg-jarvis-dark rounded-2xl p-6 border border-slate-700 mb-6">
          <div className="flex gap-4 mb-4">
            <div className="flex-1">
              <input
                type="text"
                value={topic}
                onChange={(e) => setTopic(e.target.value)}
                placeholder="Enter a topic to research..."
                className="w-full bg-slate-800 border border-slate-600 rounded-xl px-4 py-3 text-white placeholder-slate-500 focus:outline-none focus:border-jarvis-primary"
                onKeyPress={(e) => e.key === 'Enter' && handleResearch()}
              />
            </div>
            <select
              value={depth}
              onChange={(e) => setDepth(e.target.value)}
              className="bg-slate-800 border border-slate-600 rounded-xl px-4 py-3 text-white focus:outline-none focus:border-jarvis-primary"
            >
              <option value="quick">Quick (1 search)</option>
              <option value="medium">Medium (3 searches)</option>
              <option value="deep">Deep (5+ searches)</option>
            </select>
            <button
              onClick={handleResearch}
              disabled={!topic.trim() || isResearching}
              className="px-6 py-3 bg-jarvis-primary text-white rounded-xl hover:bg-blue-600 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
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
          <div className="flex flex-wrap gap-2">
            {['AI trends 2025', 'Crypto trading strategies', 'Best free software', 'Productivity hacks'].map((t) => (
              <button
                key={t}
                onClick={() => setTopic(t)}
                className="px-3 py-1 bg-slate-700 rounded-full text-sm text-slate-300 hover:bg-slate-600"
              >
                {t}
              </button>
            ))}
          </div>
        </div>

        {/* Results */}
        {isResearching && (
          <div className="bg-jarvis-dark rounded-2xl p-8 border border-slate-700 text-center">
            <Loader2 className="animate-spin mx-auto mb-4 text-jarvis-primary" size={48} />
            <p className="text-white font-medium">Researching "{topic}"...</p>
            <p className="text-slate-400 text-sm">This may take a moment</p>
          </div>
        )}

        {results && !isResearching && (
          <div className="bg-jarvis-dark rounded-2xl p-6 border border-slate-700">
            {results.error ? (
              <p className="text-red-400">{results.error}</p>
            ) : (
              <>
                <div className="flex justify-between items-start mb-4">
                  <div>
                    <h2 className="text-xl font-semibold text-white">{results.topic}</h2>
                    <p className="text-slate-400 text-sm">
                      Researched at {new Date(results.timestamp).toLocaleString()}
                    </p>
                  </div>
                  {results.document_path && (
                    <button className="px-4 py-2 bg-jarvis-secondary text-white rounded-xl flex items-center gap-2 hover:bg-green-600">
                      <Download size={18} />
                      Download
                    </button>
                  )}
                </div>

                <div className="prose prose-invert max-w-none">
                  <div className="bg-slate-800/50 rounded-xl p-4 whitespace-pre-wrap text-slate-200">
                    {results.summary}
                  </div>
                </div>

                {results.searches && results.searches.length > 0 && (
                  <div className="mt-6">
                    <h3 className="text-lg font-medium text-white mb-3">Search Queries Used</h3>
                    <div className="space-y-2">
                      {results.searches.map((search, index) => (
                        <div key={index} className="p-3 bg-slate-800/30 rounded-lg">
                          <p className="text-jarvis-primary font-medium">{search.query}</p>
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
            <h2 className="text-lg font-semibold text-white mb-4">Recent Research</h2>
            <div className="space-y-3">
              {history.map((item, index) => (
                <div
                  key={index}
                  className="bg-jarvis-dark rounded-xl p-4 border border-slate-700 flex justify-between items-center cursor-pointer hover:border-jarvis-primary"
                  onClick={() => setResults(item)}
                >
                  <div className="flex items-center gap-3">
                    <FileText className="text-jarvis-primary" />
                    <div>
                      <p className="text-white font-medium">{item.topic}</p>
                      <p className="text-slate-400 text-sm">
                        {new Date(item.timestamp).toLocaleDateString()} • {item.depth}
                      </p>
                    </div>
                  </div>
                  <ExternalLink className="text-slate-400" size={18} />
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
