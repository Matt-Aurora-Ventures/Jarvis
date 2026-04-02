import React, { useState, useMemo } from 'react'
import {
  Calendar, Clock, Bell, Filter, ChevronLeft, ChevronRight,
  Unlock, Vote, Rocket, Coins, FileText, Globe, Users,
  AlertTriangle, Star, Eye, Plus, Download, RefreshCw
} from 'lucide-react'

const EVENT_TYPES = [
  { id: 'unlock', name: 'Token Unlock', icon: Unlock, color: 'bg-red-500/20 text-red-400 border-red-500/30' },
  { id: 'governance', name: 'Governance', icon: Vote, color: 'bg-purple-500/20 text-purple-400 border-purple-500/30' },
  { id: 'launch', name: 'Token Launch', icon: Rocket, color: 'bg-green-500/20 text-green-400 border-green-500/30' },
  { id: 'airdrop', name: 'Airdrop', icon: Coins, color: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30' },
  { id: 'upgrade', name: 'Upgrade/Fork', icon: FileText, color: 'bg-blue-500/20 text-blue-400 border-blue-500/30' },
  { id: 'conference', name: 'Conference', icon: Globe, color: 'bg-cyan-500/20 text-cyan-400 border-cyan-500/30' },
  { id: 'ama', name: 'AMA/Event', icon: Users, color: 'bg-pink-500/20 text-pink-400 border-pink-500/30' }
]

// Generate mock events
const generateEvents = () => {
  const events = []
  const today = new Date()

  const eventTemplates = [
    { token: 'ARB', type: 'unlock', title: 'ARB Token Unlock', value: '$120M', impact: 'high' },
    { token: 'OP', type: 'unlock', title: 'Optimism Unlock', value: '$85M', impact: 'medium' },
    { token: 'ETH', type: 'upgrade', title: 'Dencun Upgrade', value: 'EIP-4844', impact: 'high' },
    { token: 'SOL', type: 'conference', title: 'Solana Breakpoint', value: 'Conference', impact: 'medium' },
    { token: 'AAVE', type: 'governance', title: 'AAVE V4 Vote', value: 'Proposal', impact: 'medium' },
    { token: 'UNI', type: 'governance', title: 'Fee Switch Vote', value: 'Proposal', impact: 'high' },
    { token: 'JUP', type: 'airdrop', title: 'Jupiter Airdrop Round 2', value: 'TBA', impact: 'high' },
    { token: 'STRK', type: 'launch', title: 'Starknet Token Launch', value: 'Launch', impact: 'high' },
    { token: 'EIGEN', type: 'airdrop', title: 'EigenLayer Airdrop', value: 'TBA', impact: 'high' },
    { token: 'APT', type: 'unlock', title: 'Aptos Token Unlock', value: '$45M', impact: 'medium' },
    { token: 'AVAX', type: 'conference', title: 'Avalanche Summit', value: 'Conference', impact: 'low' },
    { token: 'DOT', type: 'governance', title: 'Polkadot OpenGov', value: 'Multiple', impact: 'low' },
    { token: 'BTC', type: 'conference', title: 'Bitcoin Conference', value: 'Nashville', impact: 'medium' },
    { token: 'LINK', type: 'upgrade', title: 'CCIP Expansion', value: 'Upgrade', impact: 'medium' },
    { token: 'MKR', type: 'ama', title: 'MakerDAO Town Hall', value: 'AMA', impact: 'low' }
  ]

  eventTemplates.forEach((template, idx) => {
    const daysOffset = Math.floor(Math.random() * 30) - 5
    const eventDate = new Date(today)
    eventDate.setDate(eventDate.getDate() + daysOffset)

    events.push({
      id: idx,
      ...template,
      date: eventDate,
      dateStr: eventDate.toISOString().split('T')[0],
      time: `${Math.floor(Math.random() * 12) + 1}:00 ${Math.random() > 0.5 ? 'AM' : 'PM'} UTC`,
      isWatching: Math.random() > 0.7
    })
  })

  return events.sort((a, b) => a.date - b.date)
}

export function MarketCalendar() {
  const [currentDate, setCurrentDate] = useState(new Date())
  const [viewMode, setViewMode] = useState('list') // list, calendar, timeline
  const [selectedTypes, setSelectedTypes] = useState(['all'])
  const [impactFilter, setImpactFilter] = useState('all')
  const [events] = useState(() => generateEvents())

  // Get current month's calendar data
  const calendarData = useMemo(() => {
    const year = currentDate.getFullYear()
    const month = currentDate.getMonth()

    const firstDay = new Date(year, month, 1)
    const lastDay = new Date(year, month + 1, 0)
    const startPadding = firstDay.getDay()
    const totalDays = lastDay.getDate()

    const days = []

    // Add padding for previous month
    for (let i = 0; i < startPadding; i++) {
      const prevDate = new Date(year, month, -startPadding + i + 1)
      days.push({ date: prevDate, isCurrentMonth: false, events: [] })
    }

    // Add current month days
    for (let i = 1; i <= totalDays; i++) {
      const date = new Date(year, month, i)
      const dateStr = date.toISOString().split('T')[0]
      const dayEvents = events.filter(e => e.dateStr === dateStr)
      days.push({ date, isCurrentMonth: true, events: dayEvents })
    }

    // Add padding for next month
    const remaining = 42 - days.length
    for (let i = 1; i <= remaining; i++) {
      const nextDate = new Date(year, month + 1, i)
      days.push({ date: nextDate, isCurrentMonth: false, events: [] })
    }

    return days
  }, [currentDate, events])

  // Filter events
  const filteredEvents = useMemo(() => {
    return events.filter(event => {
      if (!selectedTypes.includes('all') && !selectedTypes.includes(event.type)) return false
      if (impactFilter !== 'all' && event.impact !== impactFilter) return false
      return true
    })
  }, [events, selectedTypes, impactFilter])

  // Upcoming events
  const upcomingEvents = filteredEvents.filter(e => e.date >= new Date())
  const todayEvents = filteredEvents.filter(e => e.dateStr === new Date().toISOString().split('T')[0])

  const prevMonth = () => {
    setCurrentDate(new Date(currentDate.getFullYear(), currentDate.getMonth() - 1))
  }

  const nextMonth = () => {
    setCurrentDate(new Date(currentDate.getFullYear(), currentDate.getMonth() + 1))
  }

  const toggleType = (type) => {
    if (type === 'all') {
      setSelectedTypes(['all'])
    } else {
      let newTypes = selectedTypes.filter(t => t !== 'all')
      if (newTypes.includes(type)) {
        newTypes = newTypes.filter(t => t !== type)
      } else {
        newTypes.push(type)
      }
      setSelectedTypes(newTypes.length === 0 ? ['all'] : newTypes)
    }
  }

  const getEventTypeInfo = (type) => EVENT_TYPES.find(t => t.id === type) || EVENT_TYPES[0]

  const formatDate = (date) => {
    const today = new Date()
    const tomorrow = new Date(today)
    tomorrow.setDate(tomorrow.getDate() + 1)

    if (date.toDateString() === today.toDateString()) return 'Today'
    if (date.toDateString() === tomorrow.toDateString()) return 'Tomorrow'
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
  }

  return (
    <div className="p-6 bg-[#0a0e14] min-h-screen">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-blue-500/20 rounded-lg">
            <Calendar className="w-6 h-6 text-blue-400" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-white">Market Calendar</h1>
            <p className="text-sm text-gray-400">Track important crypto events</p>
          </div>
        </div>
        <div className="flex gap-2">
          {['list', 'calendar', 'timeline'].map(mode => (
            <button
              key={mode}
              onClick={() => setViewMode(mode)}
              className={`px-4 py-2 rounded-lg text-sm font-medium capitalize transition-colors ${
                viewMode === mode ? 'bg-blue-500 text-white' : 'bg-white/10 text-white hover:bg-white/20'
              }`}
            >
              {mode}
            </button>
          ))}
        </div>
      </div>

      {/* Quick Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <div className="bg-red-500/10 rounded-xl p-4 border border-red-500/30">
          <div className="text-sm text-gray-400">Today's Events</div>
          <div className="text-2xl font-bold text-red-400">{todayEvents.length}</div>
        </div>
        <div className="bg-yellow-500/10 rounded-xl p-4 border border-yellow-500/30">
          <div className="text-sm text-gray-400">This Week</div>
          <div className="text-2xl font-bold text-yellow-400">
            {upcomingEvents.filter(e => {
              const diff = (e.date - new Date()) / (1000 * 60 * 60 * 24)
              return diff >= 0 && diff < 7
            }).length}
          </div>
        </div>
        <div className="bg-green-500/10 rounded-xl p-4 border border-green-500/30">
          <div className="text-sm text-gray-400">High Impact</div>
          <div className="text-2xl font-bold text-green-400">
            {upcomingEvents.filter(e => e.impact === 'high').length}
          </div>
        </div>
        <div className="bg-blue-500/10 rounded-xl p-4 border border-blue-500/30">
          <div className="text-sm text-gray-400">Watching</div>
          <div className="text-2xl font-bold text-blue-400">
            {events.filter(e => e.isWatching).length}
          </div>
        </div>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-4 mb-6 flex-wrap">
        <div className="flex flex-wrap gap-2">
          <button
            onClick={() => toggleType('all')}
            className={`px-3 py-1.5 rounded-lg text-sm ${
              selectedTypes.includes('all') ? 'bg-white/20 text-white' : 'bg-white/10 text-gray-400'
            }`}
          >
            All
          </button>
          {EVENT_TYPES.map(type => {
            const Icon = type.icon
            return (
              <button
                key={type.id}
                onClick={() => toggleType(type.id)}
                className={`px-3 py-1.5 rounded-lg text-sm flex items-center gap-1.5 border ${
                  selectedTypes.includes(type.id) ? type.color : 'bg-white/10 text-gray-400 border-transparent'
                }`}
              >
                <Icon className="w-4 h-4" />
                {type.name}
              </button>
            )
          })}
        </div>

        <select
          value={impactFilter}
          onChange={(e) => setImpactFilter(e.target.value)}
          className="bg-white/10 border border-white/20 rounded-lg px-3 py-1.5 text-white text-sm"
        >
          <option value="all">All Impact</option>
          <option value="high">High Impact</option>
          <option value="medium">Medium Impact</option>
          <option value="low">Low Impact</option>
        </select>
      </div>

      {/* List View */}
      {viewMode === 'list' && (
        <div className="space-y-4">
          {filteredEvents.length === 0 ? (
            <div className="text-center py-12 text-gray-500">
              <Calendar className="w-12 h-12 mx-auto mb-3 opacity-50" />
              <p>No events found with current filters</p>
            </div>
          ) : (
            filteredEvents.map(event => {
              const typeInfo = getEventTypeInfo(event.type)
              const Icon = typeInfo.icon
              const isPast = event.date < new Date()

              return (
                <div
                  key={event.id}
                  className={`bg-white/5 rounded-xl border p-6 ${
                    isPast ? 'border-white/5 opacity-60' : 'border-white/10'
                  }`}
                >
                  <div className="flex items-start justify-between">
                    <div className="flex items-start gap-4">
                      <div className={`p-3 rounded-lg ${typeInfo.color} border`}>
                        <Icon className="w-6 h-6" />
                      </div>
                      <div>
                        <div className="flex items-center gap-2 mb-1">
                          <span className="font-bold text-white text-lg">{event.token}</span>
                          <span className={`px-2 py-0.5 rounded text-xs ${typeInfo.color} border`}>
                            {typeInfo.name}
                          </span>
                          {event.impact === 'high' && (
                            <span className="px-2 py-0.5 rounded text-xs bg-red-500/20 text-red-400 border border-red-500/30">
                              HIGH IMPACT
                            </span>
                          )}
                        </div>
                        <h3 className="text-white font-semibold mb-2">{event.title}</h3>
                        <div className="flex items-center gap-4 text-sm text-gray-400">
                          <span className="flex items-center gap-1">
                            <Calendar className="w-4 h-4" />
                            {formatDate(event.date)}
                          </span>
                          <span className="flex items-center gap-1">
                            <Clock className="w-4 h-4" />
                            {event.time}
                          </span>
                          {event.value && (
                            <span className="text-white font-medium">{event.value}</span>
                          )}
                        </div>
                      </div>
                    </div>
                    <div className="flex gap-2">
                      <button className={`p-2 rounded-lg ${
                        event.isWatching ? 'bg-yellow-500/20 text-yellow-400' : 'bg-white/10 text-gray-400 hover:bg-white/20'
                      }`}>
                        <Star className={`w-5 h-5 ${event.isWatching ? 'fill-current' : ''}`} />
                      </button>
                      <button className="p-2 bg-white/10 text-gray-400 rounded-lg hover:bg-white/20">
                        <Bell className="w-5 h-5" />
                      </button>
                    </div>
                  </div>
                </div>
              )
            })
          )}
        </div>
      )}

      {/* Calendar View */}
      {viewMode === 'calendar' && (
        <div className="bg-white/5 rounded-xl border border-white/10 p-6">
          {/* Month Navigation */}
          <div className="flex items-center justify-between mb-6">
            <button onClick={prevMonth} className="p-2 bg-white/10 rounded-lg hover:bg-white/20">
              <ChevronLeft className="w-5 h-5 text-gray-400" />
            </button>
            <h2 className="text-xl font-bold text-white">
              {currentDate.toLocaleDateString('en-US', { month: 'long', year: 'numeric' })}
            </h2>
            <button onClick={nextMonth} className="p-2 bg-white/10 rounded-lg hover:bg-white/20">
              <ChevronRight className="w-5 h-5 text-gray-400" />
            </button>
          </div>

          {/* Week Headers */}
          <div className="grid grid-cols-7 gap-1 mb-2">
            {['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'].map(day => (
              <div key={day} className="text-center text-sm text-gray-400 py-2">
                {day}
              </div>
            ))}
          </div>

          {/* Calendar Grid */}
          <div className="grid grid-cols-7 gap-1">
            {calendarData.map((day, idx) => {
              const isToday = day.date.toDateString() === new Date().toDateString()
              return (
                <div
                  key={idx}
                  className={`min-h-24 p-2 rounded-lg border ${
                    day.isCurrentMonth ? 'bg-white/5 border-white/10' : 'bg-white/[0.02] border-transparent'
                  } ${isToday ? 'ring-2 ring-blue-500' : ''}`}
                >
                  <div className={`text-sm mb-1 ${
                    day.isCurrentMonth ? 'text-white' : 'text-gray-600'
                  } ${isToday ? 'text-blue-400 font-bold' : ''}`}>
                    {day.date.getDate()}
                  </div>
                  <div className="space-y-1">
                    {day.events.slice(0, 2).map(event => {
                      const typeInfo = getEventTypeInfo(event.type)
                      return (
                        <div
                          key={event.id}
                          className={`text-xs px-1.5 py-0.5 rounded truncate ${typeInfo.color} border`}
                        >
                          {event.token}
                        </div>
                      )
                    })}
                    {day.events.length > 2 && (
                      <div className="text-xs text-gray-500">+{day.events.length - 2} more</div>
                    )}
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* Timeline View */}
      {viewMode === 'timeline' && (
        <div className="bg-white/5 rounded-xl border border-white/10 p-6">
          <div className="relative">
            {/* Timeline line */}
            <div className="absolute left-6 top-0 bottom-0 w-0.5 bg-white/10" />

            {/* Events */}
            <div className="space-y-6">
              {filteredEvents.map((event, idx) => {
                const typeInfo = getEventTypeInfo(event.type)
                const Icon = typeInfo.icon
                const isPast = event.date < new Date()

                return (
                  <div key={event.id} className="relative flex gap-6">
                    {/* Timeline dot */}
                    <div className={`w-12 h-12 rounded-full flex items-center justify-center z-10 border-2 ${
                      isPast ? 'bg-white/5 border-white/10' : `${typeInfo.color} border`
                    }`}>
                      <Icon className={`w-5 h-5 ${isPast ? 'text-gray-500' : ''}`} />
                    </div>

                    {/* Event content */}
                    <div className={`flex-1 pb-6 ${isPast ? 'opacity-60' : ''}`}>
                      <div className="text-sm text-gray-400 mb-1">
                        {formatDate(event.date)} - {event.time}
                      </div>
                      <div className="flex items-center gap-2 mb-1">
                        <span className="font-bold text-white">{event.token}</span>
                        <span className={`px-2 py-0.5 rounded text-xs ${typeInfo.color} border`}>
                          {typeInfo.name}
                        </span>
                        {event.impact === 'high' && (
                          <AlertTriangle className="w-4 h-4 text-red-400" />
                        )}
                      </div>
                      <p className="text-gray-300">{event.title}</p>
                      {event.value && (
                        <p className="text-sm text-gray-400 mt-1">Value: {event.value}</p>
                      )}
                    </div>
                  </div>
                )
              })}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default MarketCalendar
