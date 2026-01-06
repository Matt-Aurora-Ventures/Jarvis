import React, { useState } from 'react'
import { 
  ChartCandlestick, 
  Shield, 
  Brain, 
  Mic, 
  Microscope, 
  Sparkles,
  Check,
  Circle,
  Clock
} from 'lucide-react'

const PHASES = [
  {
    id: 1,
    title: 'Trading Core',
    icon: ChartCandlestick,
    status: 'in-progress',
    features: [
      { name: 'Charts', description: 'TradingView with real-time candles', done: true },
      { name: 'Order Panel', description: 'Buy/Sell with TP/SL, position sizing', done: false },
      { name: 'Order Book', description: 'Live depth, whale alerts, spread', done: false },
    ]
  },
  {
    id: 2,
    title: 'Sentinel Mode',
    icon: Shield,
    status: 'not-started',
    features: [
      { name: 'Auto-Trading', description: 'Master toggle, phase indicator (Trial→Savage)', done: false },
      { name: 'Coliseum', description: '81 strategies grid with live backtest results', done: false },
      { name: 'Approval Gate', description: 'Pending trades queue, one-click approve/reject', done: false },
      { name: 'Kill Switch', description: 'Emergency cancel all trades', done: false },
    ]
  },
  {
    id: 3,
    title: 'Intelligence Layer',
    icon: Brain,
    status: 'not-started',
    features: [
      { name: 'Signal Aggregator', description: 'Multi-source trending (Birdeye + Gecko + DexScreener)', done: false },
      { name: 'Smart Money', description: 'GMGN insider tracking, whale patterns', done: false },
      { name: 'Sentiment', description: 'Real-time X/Twitter via Grok', done: false },
      { name: 'ML Regime', description: 'Volatility prediction, strategy switching', done: false },
    ]
  },
  {
    id: 4,
    title: 'LifeOS Integration',
    icon: Mic,
    status: 'not-started',
    features: [
      { name: 'Voice Trading', description: '"Buy $50 of SOL" natural language', done: false },
      { name: 'Mirror Test', description: 'Self-correction dashboard, improvement history', done: false },
      { name: 'Knowledge', description: 'Notes search, research viewer, trading journal', done: false },
    ]
  },
  {
    id: 5,
    title: 'Advanced Tools',
    icon: Microscope,
    status: 'not-started',
    features: [
      { name: 'MEV Dashboard', description: 'Jito bundles, sandwich scanner, SOR visualizer', done: false },
      { name: 'Perps', description: 'Jupiter perps, 30x leverage, funding rates', done: false },
      { name: 'Multi-DEX', description: 'Quote comparison (Jupiter/Raydium/Orca)', done: false },
      { name: 'Analytics', description: 'Equity curve, trade heatmap, drawdown analysis', done: false },
    ]
  },
  {
    id: 6,
    title: 'Polish & Scale',
    icon: Sparkles,
    status: 'not-started',
    features: [
      { name: 'Performance', description: 'WebSocket, code splitting, virtual scroll', done: false },
      { name: 'Mobile', description: 'PWA, push notifications, touch charts', done: false },
      { name: 'Themes', description: 'Dark/light toggle, accent colors', done: false },
      { name: 'Onboarding', description: 'Interactive tutorial, tooltips', done: false },
    ]
  },
]

function Roadmap() {
  const [expandedPhase, setExpandedPhase] = useState(1)

  const completedFeatures = PHASES.reduce((acc, phase) => 
    acc + phase.features.filter(f => f.done).length, 0
  )
  const totalFeatures = PHASES.reduce((acc, phase) => 
    acc + phase.features.length, 0
  )
  const progressPercent = Math.round((completedFeatures / totalFeatures) * 100)

  return (
    <div style={{ flex: 1, padding: 'var(--space-xl)', overflowY: 'auto' }}>
      <header style={{ marginBottom: 'var(--space-xl)' }}>
        <h1 style={{ fontSize: '1.875rem', fontWeight: 700, color: 'var(--text-primary)', marginBottom: 'var(--space-xs)' }}>
          Roadmap
        </h1>
        <p style={{ color: 'var(--text-secondary)', maxWidth: '600px' }}>
          "An edge for the little guy" — Democratizing institutional-grade trading tools.
        </p>
      </header>

      {/* Progress Overview */}
      <div className="card" style={{ marginBottom: 'var(--space-xl)' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 'var(--space-md)' }}>
          <div>
            <h2 style={{ fontSize: '1.25rem', fontWeight: 600, color: 'var(--text-primary)' }}>Overall Progress</h2>
            <p style={{ color: 'var(--text-secondary)', fontSize: '0.875rem' }}>
              {completedFeatures} of {totalFeatures} features completed
            </p>
          </div>
          <span style={{ 
            fontSize: '2rem', 
            fontWeight: 700, 
            color: 'var(--primary)'
          }}>
            {progressPercent}%
          </span>
        </div>
        <div style={{ 
          height: '8px', 
          background: 'var(--bg-secondary)', 
          borderRadius: 'var(--radius-full)',
          overflow: 'hidden'
        }}>
          <div style={{
            height: '100%',
            width: `${progressPercent}%`,
            background: 'var(--primary)',
            borderRadius: 'var(--radius-full)',
            transition: 'width 0.5s ease'
          }} />
        </div>
        <div style={{ 
          display: 'flex', 
          justifyContent: 'space-between', 
          marginTop: 'var(--space-md)',
          fontSize: '0.75rem',
          color: 'var(--text-tertiary)'
        }}>
          <span>Timeline: ~19 days</span>
          <span>45 API endpoints planned</span>
        </div>
      </div>

      {/* Phase Cards */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-md)' }}>
        {PHASES.map((phase) => {
          const Icon = phase.icon
          const phaseProgress = Math.round(
            (phase.features.filter(f => f.done).length / phase.features.length) * 100
          )
          const isExpanded = expandedPhase === phase.id

          return (
            <div 
              key={phase.id} 
              className="card hover-lift"
              style={{ cursor: 'pointer' }}
              onClick={() => setExpandedPhase(isExpanded ? null : phase.id)}
            >
              <div style={{ 
                display: 'flex', 
                justifyContent: 'space-between', 
                alignItems: 'center'
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-md)' }}>
                  <div style={{
                    width: '48px',
                    height: '48px',
                    borderRadius: 'var(--radius-md)',
                    background: phase.status === 'completed' ? 'rgba(34, 197, 94, 0.1)' :
                              phase.status === 'in-progress' ? 'rgba(59, 130, 246, 0.1)' :
                              'var(--bg-secondary)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center'
                  }}>
                    <Icon size={24} style={{ 
                      color: phase.status === 'completed' ? 'var(--success)' :
                             phase.status === 'in-progress' ? 'var(--primary)' :
                             'var(--text-tertiary)'
                    }} />
                  </div>
                  <div>
                    <h3 style={{ 
                      fontSize: '1.125rem', 
                      fontWeight: 600, 
                      color: 'var(--text-primary)',
                      display: 'flex',
                      alignItems: 'center',
                      gap: 'var(--space-xs)'
                    }}>
                      Phase {phase.id}: {phase.title}
                      <StatusBadge status={phase.status} />
                    </h3>
                    <p style={{ color: 'var(--text-secondary)', fontSize: '0.875rem' }}>
                      {phase.features.length} features
                    </p>
                  </div>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-lg)' }}>
                  <div style={{ width: '120px' }}>
                    <div style={{ 
                      height: '4px', 
                      background: 'var(--bg-secondary)', 
                      borderRadius: 'var(--radius-full)',
                      overflow: 'hidden'
                    }}>
                      <div style={{
                        height: '100%',
                        width: `${phaseProgress}%`,
                        background: phase.status === 'completed' ? 'var(--success)' :
                                   phase.status === 'in-progress' ? 'var(--primary)' :
                                   'var(--gray-400)',
                        transition: 'width 0.3s ease'
                      }} />
                    </div>
                  </div>
                  <span style={{ 
                    fontSize: '0.875rem', 
                    fontWeight: 600,
                    color: 'var(--text-secondary)',
                    width: '36px',
                    textAlign: 'right'
                  }}>
                    {phaseProgress}%
                  </span>
                </div>
              </div>

              {/* Expanded Features */}
              {isExpanded && (
                <div style={{ 
                  marginTop: 'var(--space-lg)', 
                  paddingTop: 'var(--space-lg)',
                  borderTop: '1px solid var(--border-color)'
                }}>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-sm)' }}>
                    {phase.features.map((feature, index) => (
                      <div 
                        key={index}
                        style={{
                          display: 'flex',
                          alignItems: 'flex-start',
                          gap: 'var(--space-sm)',
                          padding: 'var(--space-sm)',
                          borderRadius: 'var(--radius-sm)',
                          background: feature.done ? 'rgba(34, 197, 94, 0.05)' : 'transparent'
                        }}
                      >
                        <div style={{
                          width: '20px',
                          height: '20px',
                          borderRadius: '50%',
                          border: feature.done ? 'none' : '2px solid var(--border-color)',
                          background: feature.done ? 'var(--success)' : 'transparent',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          flexShrink: 0,
                          marginTop: '2px'
                        }}>
                          {feature.done && <Check size={12} color="white" />}
                        </div>
                        <div>
                          <p style={{ 
                            fontWeight: 500, 
                            color: feature.done ? 'var(--success)' : 'var(--text-primary)',
                            textDecoration: feature.done ? 'line-through' : 'none'
                          }}>
                            {feature.name}
                          </p>
                          <p style={{ 
                            fontSize: '0.875rem', 
                            color: 'var(--text-secondary)' 
                          }}>
                            {feature.description}
                          </p>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}

function StatusBadge({ status }) {
  const config = {
    'completed': { label: 'Completed', color: 'var(--success)', bg: 'rgba(34, 197, 94, 0.1)' },
    'in-progress': { label: 'In Progress', color: 'var(--primary)', bg: 'rgba(59, 130, 246, 0.1)' },
    'not-started': { label: 'Planned', color: 'var(--text-tertiary)', bg: 'var(--bg-secondary)' },
  }
  const { label, color, bg } = config[status] || config['not-started']

  return (
    <span style={{
      fontSize: '0.625rem',
      fontWeight: 600,
      textTransform: 'uppercase',
      letterSpacing: '0.05em',
      padding: '2px 8px',
      borderRadius: 'var(--radius-full)',
      background: bg,
      color: color
    }}>
      {label}
    </span>
  )
}

export default Roadmap
