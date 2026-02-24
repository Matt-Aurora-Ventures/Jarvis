import React, { useCallback, useEffect, useMemo, useState } from 'react'
import {
  CandlestickChart,
  Shield,
  Brain,
  Mic,
  Microscope,
  Sparkles,
  Check,
} from 'lucide-react'

const STATE_STYLE = {
  live: { label: 'Live', color: 'var(--success)', bg: 'rgba(34, 197, 94, 0.1)' },
  backend_only: { label: 'Backend-only', color: '#60a5fa', bg: 'rgba(96, 165, 250, 0.12)' },
  prototype: { label: 'Prototype', color: '#f59e0b', bg: 'rgba(245, 158, 11, 0.12)' },
  mock: { label: 'Mock', color: '#f97316', bg: 'rgba(249, 115, 22, 0.12)' },
  planned: { label: 'Planned', color: 'var(--text-tertiary)', bg: 'var(--bg-secondary)' },
}

const PHASES = [
  {
    id: 1,
    title: 'Trading Core',
    icon: CandlestickChart,
    status: 'in-progress',
    features: [
      { key: 'charts', name: 'Charts', description: 'TradingView with real-time candles', state: 'planned' },
      { key: 'order_panel', name: 'Order Panel', description: 'Buy/Sell with TP/SL, position sizing', state: 'planned' },
      { key: 'order_book', name: 'Order Book', description: 'Live depth, whale alerts, spread', state: 'planned' },
    ],
  },
  {
    id: 2,
    title: 'Sentinel Mode',
    icon: Shield,
    status: 'not-started',
    features: [
      { key: 'auto_trading', name: 'Auto-Trading', description: 'Master toggle, phase indicator (Trial -> Savage)', state: 'planned' },
      { key: 'coliseum', name: 'Coliseum', description: '81 strategies grid with live backtest results', state: 'planned' },
      { key: 'approval_gate', name: 'Approval Gate', description: 'Pending trades queue, one-click approve/reject', state: 'planned' },
      { key: 'kill_switch', name: 'Kill Switch', description: 'Emergency cancel all trades', state: 'planned' },
    ],
  },
  {
    id: 3,
    title: 'Intelligence Layer',
    icon: Brain,
    status: 'not-started',
    features: [
      {
        key: 'signal_aggregator',
        name: 'Signal Aggregator',
        description: 'Multi-source trending (Birdeye + Gecko + DexScreener)',
        state: 'planned',
      },
      { key: 'smart_money', name: 'Smart Money', description: 'GMGN insider tracking, whale patterns', state: 'planned' },
      { key: 'sentiment', name: 'Sentiment', description: 'Real-time X/Twitter via Grok', state: 'planned' },
      { key: 'ml_regime', name: 'ML Regime', description: 'Volatility prediction, strategy switching', state: 'planned' },
    ],
  },
  {
    id: 4,
    title: 'LifeOS Integration',
    icon: Mic,
    status: 'not-started',
    features: [
      { key: 'voice_trading', name: 'Voice Trading', description: '"Buy $50 of SOL" natural language', state: 'planned' },
      {
        key: 'mirror_test',
        name: 'Mirror Test',
        description: 'Self-correction dashboard, improvement history',
        state: 'planned',
      },
      { key: 'knowledge', name: 'Knowledge', description: 'Notes search, research viewer, trading journal', state: 'planned' },
    ],
  },
  {
    id: 5,
    title: 'Advanced Tools',
    icon: Microscope,
    status: 'not-started',
    features: [
      { key: 'mev_dashboard', name: 'MEV Dashboard', description: 'Jito bundles, sandwich scanner, SOR visualizer', state: 'planned' },
      { key: 'perps', name: 'Perps', description: 'Jupiter perps, 30x leverage, funding rates', state: 'planned' },
      { key: 'multi_dex', name: 'Multi-DEX', description: 'Quote comparison (Jupiter/Raydium/Orca)', state: 'planned' },
      { key: 'analytics', name: 'Analytics', description: 'Equity curve, trade heatmap, drawdown analysis', state: 'planned' },
    ],
  },
  {
    id: 6,
    title: 'Polish & Scale',
    icon: Sparkles,
    status: 'not-started',
    features: [
      { key: 'performance', name: 'Performance', description: 'WebSocket, code splitting, virtual scroll', state: 'planned' },
      { key: 'mobile', name: 'Mobile', description: 'PWA, push notifications, touch charts', state: 'planned' },
      { key: 'themes', name: 'Themes', description: 'Dark/light toggle, accent colors', state: 'planned' },
      { key: 'onboarding', name: 'Onboarding', description: 'Interactive tutorial, tooltips', state: 'planned' },
    ],
  },
]

function stateWeight(state) {
  if (state === 'live') return 1.0
  if (state === 'backend_only') return 0.75
  if (state === 'prototype') return 0.5
  if (state === 'mock') return 0.25
  return 0
}

function mergePhases(basePhases, apiPhases) {
  if (!Array.isArray(apiPhases) || apiPhases.length === 0) {
    return basePhases
  }

  const phaseById = new Map(apiPhases.map((phase) => [phase.id, phase]))
  return basePhases.map((phase) => {
    const apiPhase = phaseById.get(phase.id)
    if (!apiPhase || !Array.isArray(apiPhase.features)) {
      return phase
    }

    const featureByKey = new Map(apiPhase.features.map((feature) => [feature.key, feature]))
    const mergedFeatures = phase.features.map((feature) => {
      const apiFeature = featureByKey.get(feature.key)
      if (!apiFeature) {
        return feature
      }

      return {
        ...feature,
        state: apiFeature.state || feature.state,
        stateLabel: apiFeature.state_label,
        note: apiFeature.note,
      }
    })

    return {
      ...phase,
      status: apiPhase.status || phase.status,
      progressPercent:
        typeof apiPhase.progress_percent === 'number'
          ? apiPhase.progress_percent
          : phase.progressPercent,
      features: mergedFeatures,
    }
  })
}

function Roadmap() {
  const [expandedPhase, setExpandedPhase] = useState(1)
  const [apiPayload, setApiPayload] = useState(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState(null)

  const fetchRoadmap = useCallback(async () => {
    try {
      setError(null)
      const response = await fetch('/api/roadmap/capabilities', { method: 'GET' })
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`)
      }
      const payload = await response.json()
      setApiPayload(payload)
    } catch (err) {
      setError(err?.message || 'Failed to fetch roadmap capability matrix')
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchRoadmap()
    const intervalId = setInterval(fetchRoadmap, 30000)
    return () => clearInterval(intervalId)
  }, [fetchRoadmap])

  const phases = useMemo(() => mergePhases(PHASES, apiPayload?.phases), [apiPayload])

  const summary = useMemo(() => {
    if (apiPayload?.summary) {
      return apiPayload.summary
    }

    const allFeatures = phases.flatMap((phase) => phase.features)
    const totalFeatures = allFeatures.length
    const completedFeatures = allFeatures.filter((feature) => feature.state === 'live').length
    const weightedProgress = totalFeatures
      ? Math.round(
          (allFeatures.reduce((acc, feature) => acc + stateWeight(feature.state), 0) / totalFeatures) * 100
        )
      : 0
    return {
      total_features: totalFeatures,
      completed_features: completedFeatures,
      overall_progress_percent: weightedProgress,
      state_counts: {},
    }
  }, [apiPayload, phases])

  const completedFeatures = summary.completed_features || 0
  const totalFeatures = summary.total_features || 0
  const progressPercent = summary.overall_progress_percent || 0

  return (
    <div style={{ flex: 1, padding: 'var(--space-xl)', overflowY: 'auto' }}>
      <header style={{ marginBottom: 'var(--space-xl)' }}>
        <h1 style={{ fontSize: '1.875rem', fontWeight: 700, color: 'var(--text-primary)', marginBottom: 'var(--space-xs)' }}>
          Roadmap
        </h1>
        <p style={{ color: 'var(--text-secondary)', maxWidth: '780px' }}>
          Capability-truth view for delivery status: each item is tagged as Live, Backend-only, Prototype, Mock, or Planned.
        </p>
      </header>

      {error ? (
        <div
          className="card"
          style={{ marginBottom: 'var(--space-lg)', borderColor: 'rgba(249, 115, 22, 0.35)' }}
        >
          <p style={{ color: '#f97316', margin: 0 }}>
            Roadmap API unavailable ({error}). Showing local fallback map.
          </p>
        </div>
      ) : null}

      <div className="card" style={{ marginBottom: 'var(--space-xl)' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 'var(--space-md)' }}>
          <div>
            <h2 style={{ fontSize: '1.25rem', fontWeight: 600, color: 'var(--text-primary)' }}>Overall Progress</h2>
            <p style={{ color: 'var(--text-secondary)', fontSize: '0.875rem' }}>
              {completedFeatures} of {totalFeatures} features live
            </p>
          </div>
          <span
            style={{
              fontSize: '2rem',
              fontWeight: 700,
              color: 'var(--primary)',
            }}
          >
            {progressPercent}%
          </span>
        </div>
        <div
          style={{
            height: '8px',
            background: 'var(--bg-secondary)',
            borderRadius: 'var(--radius-full)',
            overflow: 'hidden',
          }}
        >
          <div
            style={{
              height: '100%',
              width: `${progressPercent}%`,
              background: 'var(--primary)',
              borderRadius: 'var(--radius-full)',
              transition: 'width 0.5s ease',
            }}
          />
        </div>
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            marginTop: 'var(--space-md)',
            fontSize: '0.75rem',
            color: 'var(--text-tertiary)',
          }}
        >
          <span>Source: {apiPayload?.source || 'fallback'}</span>
          <span>{isLoading ? 'Refreshing...' : `Last update: ${new Date().toLocaleTimeString()}`}</span>
        </div>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-md)' }}>
        {phases.map((phase) => {
          const Icon = phase.icon
          const phaseProgress =
            typeof phase.progressPercent === 'number'
              ? phase.progressPercent
              : Math.round(
                  (phase.features.reduce((acc, feature) => acc + stateWeight(feature.state), 0) /
                    Math.max(1, phase.features.length)) *
                    100
                )
          const isExpanded = expandedPhase === phase.id

          return (
            <div
              key={phase.id}
              className="card hover-lift"
              style={{ cursor: 'pointer' }}
              onClick={() => setExpandedPhase(isExpanded ? null : phase.id)}
            >
              <div
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-md)' }}>
                  <div
                    style={{
                      width: '48px',
                      height: '48px',
                      borderRadius: 'var(--radius-md)',
                      background:
                        phase.status === 'completed'
                          ? 'rgba(34, 197, 94, 0.1)'
                          : phase.status === 'in-progress'
                            ? 'rgba(59, 130, 246, 0.1)'
                            : 'var(--bg-secondary)',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                    }}
                  >
                    <Icon
                      size={24}
                      style={{
                        color:
                          phase.status === 'completed'
                            ? 'var(--success)'
                            : phase.status === 'in-progress'
                              ? 'var(--primary)'
                              : 'var(--text-tertiary)',
                      }}
                    />
                  </div>
                  <div>
                    <h3
                      style={{
                        fontSize: '1.125rem',
                        fontWeight: 600,
                        color: 'var(--text-primary)',
                        display: 'flex',
                        alignItems: 'center',
                        gap: 'var(--space-xs)',
                      }}
                    >
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
                    <div
                      style={{
                        height: '4px',
                        background: 'var(--bg-secondary)',
                        borderRadius: 'var(--radius-full)',
                        overflow: 'hidden',
                      }}
                    >
                      <div
                        style={{
                          height: '100%',
                          width: `${phaseProgress}%`,
                          background:
                            phase.status === 'completed'
                              ? 'var(--success)'
                              : phase.status === 'in-progress'
                                ? 'var(--primary)'
                                : 'var(--gray-400)',
                          transition: 'width 0.3s ease',
                        }}
                      />
                    </div>
                  </div>
                  <span
                    style={{
                      fontSize: '0.875rem',
                      fontWeight: 600,
                      color: 'var(--text-secondary)',
                      width: '36px',
                      textAlign: 'right',
                    }}
                  >
                    {phaseProgress}%
                  </span>
                </div>
              </div>

              {isExpanded ? (
                <div
                  style={{
                    marginTop: 'var(--space-lg)',
                    paddingTop: 'var(--space-lg)',
                    borderTop: '1px solid var(--border-color)',
                  }}
                >
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-sm)' }}>
                    {phase.features.map((feature) => {
                      const state = feature.state || 'planned'
                      const stateMeta = STATE_STYLE[state] || STATE_STYLE.planned
                      const isLive = state === 'live'
                      return (
                        <div
                          key={feature.key}
                          style={{
                            display: 'flex',
                            alignItems: 'flex-start',
                            gap: 'var(--space-sm)',
                            padding: 'var(--space-sm)',
                            borderRadius: 'var(--radius-sm)',
                            background: isLive ? 'rgba(34, 197, 94, 0.05)' : 'transparent',
                          }}
                        >
                          <div
                            style={{
                              width: '20px',
                              height: '20px',
                              borderRadius: '50%',
                              border: isLive ? 'none' : `2px solid ${stateMeta.color}`,
                              background: isLive ? 'var(--success)' : 'transparent',
                              display: 'flex',
                              alignItems: 'center',
                              justifyContent: 'center',
                              flexShrink: 0,
                              marginTop: '2px',
                            }}
                          >
                            {isLive ? <Check size={12} color="white" /> : null}
                          </div>
                          <div style={{ flex: 1 }}>
                            <div
                              style={{
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'space-between',
                                gap: 'var(--space-sm)',
                              }}
                            >
                              <p
                                style={{
                                  fontWeight: 500,
                                  color: isLive ? 'var(--success)' : 'var(--text-primary)',
                                }}
                              >
                                {feature.name}
                              </p>
                              <FeatureStateBadge state={state} />
                            </div>
                            <p
                              style={{
                                fontSize: '0.875rem',
                                color: 'var(--text-secondary)',
                              }}
                            >
                              {feature.description}
                            </p>
                            {feature.note ? (
                              <p
                                style={{
                                  marginTop: '4px',
                                  fontSize: '0.75rem',
                                  color: 'var(--text-tertiary)',
                                }}
                              >
                                {feature.note}
                              </p>
                            ) : null}
                          </div>
                        </div>
                      )
                    })}
                  </div>
                </div>
              ) : null}
            </div>
          )
        })}
      </div>
    </div>
  )
}

function FeatureStateBadge({ state }) {
  const config = STATE_STYLE[state] || STATE_STYLE.planned
  return (
    <span
      style={{
        fontSize: '0.625rem',
        fontWeight: 600,
        textTransform: 'uppercase',
        letterSpacing: '0.05em',
        padding: '2px 8px',
        borderRadius: 'var(--radius-full)',
        background: config.bg,
        color: config.color,
      }}
    >
      {config.label}
    </span>
  )
}

function StatusBadge({ status }) {
  const config = {
    completed: { label: 'Completed', color: 'var(--success)', bg: 'rgba(34, 197, 94, 0.1)' },
    'in-progress': { label: 'In Progress', color: 'var(--primary)', bg: 'rgba(59, 130, 246, 0.1)' },
    'not-started': { label: 'Planned', color: 'var(--text-tertiary)', bg: 'var(--bg-secondary)' },
  }
  const { label, color, bg } = config[status] || config['not-started']

  return (
    <span
      style={{
        fontSize: '0.625rem',
        fontWeight: 600,
        textTransform: 'uppercase',
        letterSpacing: '0.05em',
        padding: '2px 8px',
        borderRadius: 'var(--radius-full)',
        background: bg,
        color,
      }}
    >
      {label}
    </span>
  )
}

export default Roadmap
