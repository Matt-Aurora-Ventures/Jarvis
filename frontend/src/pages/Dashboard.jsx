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
    fetchStats()
    const interval = setInterval(fetchStats, 60000) // Refresh every minute
    return () => clearInterval(interval)
  }, [])

  return (
    <div className="flex-1 p-8 overflow-y-auto">
      <header className="mb-8">
        <h1 className="text-3xl font-bold text-white mb-2">Dashboard</h1>
        <p className="text-slate-400">Welcome back. Here's what's happening.</p>
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
        <div className="bg-jarvis-dark rounded-2xl p-6 border border-slate-700">
          <div className="flex items-center gap-3 mb-4">
            <Activity className="text-jarvis-primary" />
            <h2 className="text-xl font-semibold text-white">Current Activity</h2>
          </div>
          <div className="space-y-3">
            <div className="flex justify-between items-center">
              <span className="text-slate-400">Active App</span>
              <span className="text-white font-medium">{currentActivity?.app || 'Unknown'}</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-slate-400">Window</span>
              <span className="text-white font-medium truncate max-w-[200px]">
                {currentActivity?.window || 'Unknown'}
              </span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-slate-400">Status</span>
              <span className={`px-2 py-1 rounded-full text-xs ${
                currentActivity?.status === 'active' ? 'bg-green-500/20 text-green-400' : 'bg-slate-600 text-slate-300'
              }`}>
                {currentActivity?.status || 'Idle'}
              </span>
            </div>
          </div>
        </div>

        {/* System Status */}
        <div className="bg-jarvis-dark rounded-2xl p-6 border border-slate-700">
          <div className="flex items-center gap-3 mb-4">
            <Brain className="text-jarvis-accent" />
            <h2 className="text-xl font-semibold text-white">System Status</h2>
          </div>
          <div className="space-y-3">
            <StatusItem label="Daemon" status={status.daemon} />
            <StatusItem label="Voice" status={status.voice} />
            <StatusItem label="Monitoring" status={status.monitoring} />
          </div>
        </div>
      </div>

      {/* Recent Suggestions */}
      <div className="bg-jarvis-dark rounded-2xl p-6 border border-slate-700">
        <div className="flex items-center gap-3 mb-4">
          <Lightbulb className="text-yellow-500" />
          <h2 className="text-xl font-semibold text-white">Recent Suggestions</h2>
        </div>
        {suggestions.length > 0 ? (
          <div className="space-y-3">
            {suggestions.slice(0, 5).map((suggestion) => (
              <div key={suggestion.id} className="p-4 bg-slate-800/50 rounded-xl">
                <p className="text-slate-200">{suggestion.text}</p>
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
    <div className="bg-jarvis-dark rounded-2xl p-6 border border-slate-700">
      <div className="flex items-center gap-3 mb-2">
        {icon}
        <span className="text-slate-400 text-sm">{label}</span>
      </div>
      <p className="text-3xl font-bold text-white">{value}</p>
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
      <span className="text-slate-400">{label}</span>
      <div className="flex items-center gap-2">
        <div className={`w-2 h-2 rounded-full ${getStatusColor(status)}`} />
        <span className="text-white capitalize">{status}</span>
      </div>
    </div>
  )
}

export default Dashboard
