import React from 'react'
import { Activity, Brain, Clock, TrendingUp, Lightbulb, CheckCircle } from 'lucide-react'

// Hooks
import { useApi } from '@/hooks'

// Components
import { Card, Badge, Skeleton } from '@/components/ui'
import { StatsGrid } from '@/components/trading'
import { EmptyState, ErrorState } from '@/components/common'

// Store
import useJarvisStore from '@/stores/jarvisStore'

/**
 * Dashboard - Main system overview page
 * Refactored to use modular components and custom hooks
 */
function Dashboard() {
  const { suggestions, status, currentActivity } = useJarvisStore()
  
  // Use custom hooks for data fetching
  const { data: stats, loading: statsLoading, error: statsError, refresh: refreshStats } = useApi('/api/stats', {
    pollingInterval: 60000,
    initialData: {
      activeTime: '0h 0m',
      tasksCompleted: 0,
      suggestionsGiven: 0,
      focusScore: 0,
    }
  })

  const { data: health, loading: healthLoading } = useApi('/api/health', {
    pollingInterval: 30000,
    initialData: {
      profile: { cpu_load: 0, ram_total_gb: 0, ram_free_gb: 0, disk_free_gb: 0 },
      network: { rx_mbps: 0, tx_mbps: 0, packets_per_sec: 0 },
      llm: { last_provider: '', last_model: '', last_latency_ms: 0, last_errors: {} },
      voice: { enabled: false, mic_status: 'off', voice_error: '' },
    }
  })

  return (
    <div className="flex-1 p-8 overflow-y-auto" style={{ background: 'var(--bg-secondary)' }}>
      {/* Page Header */}
      <header className="mb-8">
        <h1 className="text-3xl font-bold mb-2" style={{ color: 'var(--text-primary)' }}>
          Dashboard
        </h1>
        <p style={{ color: 'var(--text-secondary)' }}>
          Welcome back. Here's what's happening.
        </p>
      </header>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
        {statsLoading ? (
          <>
            <StatCardSkeleton />
            <StatCardSkeleton />
            <StatCardSkeleton />
            <StatCardSkeleton />
          </>
        ) : (
          <>
            <StatCard
              icon={<Clock style={{ color: 'var(--primary)' }} />}
              label="Active Time Today"
              value={stats.activeTime}
            />
            <StatCard
              icon={<CheckCircle style={{ color: 'var(--success)' }} />}
              label="Tasks Completed"
              value={stats.tasksCompleted}
            />
            <StatCard
              icon={<Lightbulb style={{ color: 'var(--warning)' }} />}
              label="Suggestions Given"
              value={stats.suggestionsGiven}
            />
            <StatCard
              icon={<TrendingUp style={{ color: 'var(--info)' }} />}
              label="Focus Score"
              value={`${stats.focusScore}%`}
            />
          </>
        )}
      </div>

      {/* Current Activity + System Status Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
        {/* Current Activity */}
        <Card>
          <Card.Header>
            <Card.Title>
              <Activity size={20} style={{ color: 'var(--primary)' }} />
              Current Activity
            </Card.Title>
          </Card.Header>
          <Card.Body>
            <div className="space-y-3">
              <ActivityRow label="Active App" value={currentActivity?.app || 'Unknown'} />
              <ActivityRow 
                label="Window" 
                value={currentActivity?.window || 'Unknown'} 
                truncate 
              />
              <ActivityRow 
                label="Status" 
                value={
                  <Badge 
                    variant={currentActivity?.status === 'active' ? 'success' : 'default'}
                  >
                    {currentActivity?.status || 'Idle'}
                  </Badge>
                } 
              />
            </div>
          </Card.Body>
        </Card>

        {/* System Status */}
        <Card>
          <Card.Header>
            <Card.Title>
              <Brain size={20} style={{ color: 'var(--accent)' }} />
              System Status
            </Card.Title>
          </Card.Header>
          <Card.Body>
            <div className="space-y-3">
              <StatusItem label="Daemon" status={status.daemon} />
              <StatusItem label="Voice" status={status.voice} />
              <StatusItem label="Monitoring" status={status.monitoring} />
            </div>
          </Card.Body>
        </Card>
      </div>

      {/* Recent Suggestions */}
      <Card>
        <Card.Header>
          <Card.Title>
            <Lightbulb size={20} style={{ color: 'var(--warning)' }} />
            Recent Suggestions
          </Card.Title>
        </Card.Header>
        <Card.Body>
          {suggestions.length > 0 ? (
            <div className="space-y-3">
              {suggestions.slice(0, 5).map((suggestion) => (
                <SuggestionCard key={suggestion.id} suggestion={suggestion} />
              ))}
            </div>
          ) : (
            <EmptyState
              icon={Lightbulb}
              title="No suggestions yet"
              message="Jarvis is watching and will offer help when relevant."
            />
          )}
        </Card.Body>
      </Card>
    </div>
  )
}

/* =========== Sub-Components =========== */

function StatCard({ icon, label, value }) {
  return (
    <Card className="stat-card">
      <div className="flex items-center gap-3 mb-2">
        {icon}
        <span className="text-sm" style={{ color: 'var(--text-secondary)' }}>{label}</span>
      </div>
      <p className="text-3xl font-bold" style={{ color: 'var(--text-primary)' }}>{value}</p>
    </Card>
  )
}

function StatCardSkeleton() {
  return (
    <Card className="p-6">
      <div className="flex items-center gap-3 mb-2">
        <Skeleton className="w-6 h-6 rounded" />
        <Skeleton className="h-4 w-24" />
      </div>
      <Skeleton className="h-9 w-16 mt-2" />
    </Card>
  )
}

function ActivityRow({ label, value, truncate }) {
  return (
    <div className="flex justify-between items-center">
      <span style={{ color: 'var(--text-secondary)' }}>{label}</span>
      <span 
        className={`font-medium ${truncate ? 'truncate max-w-[200px]' : ''}`}
        style={{ color: 'var(--text-primary)' }}
      >
        {value}
      </span>
    </div>
  )
}

function StatusItem({ label, status }) {
  const getStatusColor = (s) => {
    switch (s) {
      case 'running':
      case 'on':
      case 'active':
        return 'var(--success)'
      case 'off':
      case 'stopped':
        return 'var(--danger)'
      default:
        return 'var(--warning)'
    }
  }

  return (
    <div className="flex justify-between items-center">
      <span style={{ color: 'var(--text-secondary)' }}>{label}</span>
      <div className="flex items-center gap-2">
        <div 
          className="w-2 h-2 rounded-full"
          style={{ background: getStatusColor(status) }}
        />
        <span className="capitalize" style={{ color: 'var(--text-primary)' }}>{status}</span>
      </div>
    </div>
  )
}

function SuggestionCard({ suggestion }) {
  return (
    <div 
      className="p-4 rounded-xl"
      style={{ background: 'var(--bg-tertiary)' }}
    >
      <p style={{ color: 'var(--text-primary)' }}>{suggestion.text}</p>
      <span className="text-xs" style={{ color: 'var(--text-tertiary)' }}>
        {new Date(suggestion.timestamp).toLocaleTimeString()}
      </span>
    </div>
  )
}

export default Dashboard
