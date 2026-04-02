import React, { useEffect, useState } from 'react'
import { Activity, Brain, Clock, TrendingUp, Lightbulb, CheckCircle } from 'lucide-react'
import useJarvisStore from '../stores/jarvisStore'

function Dashboard() {
  const { suggestions, status, currentActivity } = useJarvisStore()
  const [stats, setStats] = useState({
    activeTime: '0h 0m',
    tasksCompleted: 0,
    suggestionsGiven: 0,
    focusScore: 0,
  })
  const [health, setHealth] = useState({
    profile: { cpu_load: 0, ram_total_gb: 0, ram_free_gb: 0, disk_free_gb: 0 },
    network: { rx_mbps: 0, tx_mbps: 0, packets_per_sec: 0 },
    llm: { last_provider: '', last_model: '', last_latency_ms: 0, last_errors: {} },
    voice: { enabled: false, mic_status: 'off', voice_error: '' },
  })

  useEffect(() => {
    // Fetch dashboard data
    const fetchStats = async () => {
      try {
        const response = await fetch('/api/stats')
        if (response.ok) {
          const data = await response.json()
          setStats(data)
        }
      } catch (error) {
        console.error('Failed to fetch stats:', error)
      }
    }
    const fetchHealth = async () => {
      try {
        const response = await fetch('/api/health')
        if (response.ok) {
          const data = await response.json()
          setHealth(data)
        }
      } catch (error) {
        console.error('Failed to fetch health:', error)
      }
    }
    fetchStats()
    fetchHealth()
    const interval = setInterval(fetchStats, 60000) // Refresh every minute
    const healthInterval = setInterval(fetchHealth, 30000)
    return () => clearInterval(interval)
  }, [])

  const providerErrors = Object.entries(health.llm?.last_errors || {}).filter(([, msg]) => msg)
  const providerErrorText = providerErrors.length > 0 ? `${providerErrors[0][0]}: ${providerErrors[0][1]}` : 'None'

  return (
    <div className="flex-1 p-8 overflow-y-auto">
      <header className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900 mb-2">Dashboard</h1>
        <p className="text-gray-500">Welcome back. Here's what's happening.</p>
      </header>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
        <StatCard
          icon={<Clock className="text-jarvis-primary" />}
          label="Active Time Today"
          value={stats.activeTime}
        />
        <StatCard
          icon={<CheckCircle className="text-green-500" />}
          label="Tasks Completed"
          value={stats.tasksCompleted}
        />
        <StatCard
          icon={<Lightbulb className="text-yellow-500" />}
          label="Suggestions Given"
          value={stats.suggestionsGiven}
        />
        <StatCard
          icon={<TrendingUp className="text-jarvis-secondary" />}
          label="Focus Score"
          value={`${stats.focusScore}%`}
        />
      </div>

      {/* Current Activity */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
        <div className="bg-white rounded-2xl p-6 border border-gray-200 shadow-sm">
          <div className="flex items-center gap-3 mb-4">
            <Activity className="text-jarvis-primary" />
            <h2 className="text-xl font-semibold text-gray-900">Current Activity</h2>
          </div>
          <div className="space-y-3">
            <div className="flex justify-between items-center">
              <span className="text-gray-500">Active App</span>
              <span className="text-gray-900 font-medium">{currentActivity?.app || 'Unknown'}</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-gray-500">Window</span>
              <span className="text-gray-900 font-medium truncate max-w-[200px]">
                {currentActivity?.window || 'Unknown'}
              </span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-gray-500">Status</span>
              <span className={`px-2 py-1 rounded-full text-xs ${currentActivity?.status === 'active' ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'
                }`}>
                {currentActivity?.status || 'Idle'}
              </span>
            </div>
          </div>
        </div>

        {/* System Status */}
        <div className="bg-white rounded-2xl p-6 border border-gray-200 shadow-sm">
          <div className="flex items-center gap-3 mb-4">
            <Brain className="text-jarvis-accent" />
            <h2 className="text-xl font-semibold text-gray-900">System Status</h2>
          </div>
          <div className="space-y-3">
            <StatusItem label="Daemon" status={status.daemon} />
            <StatusItem label="Voice" status={status.voice} />
            <StatusItem label="Monitoring" status={status.monitoring} />
          </div>
        </div>
      </div>

      {/* Recent Suggestions */}
      <div className="bg-white rounded-2xl p-6 border border-gray-200 shadow-sm">
        <div className="flex items-center gap-3 mb-4">
          <Lightbulb className="text-yellow-500" />
          <h2 className="text-xl font-semibold text-gray-900">Recent Suggestions</h2>
        </div>
        {suggestions.length > 0 ? (
          <div className="space-y-3">
            {suggestions.slice(0, 5).map((suggestion) => (
              <div key={suggestion.id} className="p-4 bg-gray-50 rounded-xl">
                <p className="text-gray-700">{suggestion.text}</p>
                <span className="text-xs text-slate-500">
                  {new Date(suggestion.timestamp).toLocaleTimeString()}
                </span>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-slate-500">No recent suggestions. Jarvis is watching and will offer help when relevant.</p>
        )}
      </div>
    </div>
  )
}

function StatCard({ icon, label, value }) {
  return (
    <div className="bg-white rounded-2xl p-6 border border-gray-200 shadow-sm">
      <div className="flex items-center gap-3 mb-2">
        {icon}
        <span className="text-gray-500 text-sm">{label}</span>
      </div>
      <p className="text-3xl font-bold text-gray-900">{value}</p>
    </div>
  )
}

function StatusItem({ label, status }) {
  const getStatusColor = (s) => {
    switch (s) {
      case 'running':
      case 'on':
      case 'active':
        return 'bg-green-500'
      case 'off':
      case 'stopped':
        return 'bg-red-500'
      default:
        return 'bg-yellow-500'
    }
  }

  return (
    <div className="flex justify-between items-center">
      <span className="text-gray-500">{label}</span>
      <div className="flex items-center gap-2">
        <div className={`w-2 h-2 rounded-full ${getStatusColor(status)}`} />
        <span className="text-gray-900 capitalize">{status}</span>
      </div>
    </div>
  )
}

export default Dashboard
