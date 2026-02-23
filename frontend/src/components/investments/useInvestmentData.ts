import { useState, useEffect, useCallback, useRef } from 'react'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface BasketToken {
  symbol: string
  mint: string
  weight: number
  usd_value: number
  quantity: number
  price: number
  change_24h: number
}

export interface BasketData {
  tokens: BasketToken[]
  total_nav: number
  nav_per_share: number
  last_rebalance: string
  next_rebalance: string
}

export interface PerformancePoint {
  timestamp: string
  nav: number
}

export interface AgentReport {
  agent: string
  recommendation: string
  confidence: number
  reasoning: string
}

export interface DebateRound {
  round: number
  bull_argument: string
  bear_argument: string
  moderator_summary: string
}

export interface RiskAssessment {
  overall_risk: string
  max_drawdown_pct: number
  var_95: number
  concentration_risk: string
  liquidity_risk: string
}

export interface InvestmentDecision {
  id: string
  timestamp: string
  action: 'REBALANCE' | 'HOLD' | 'EMERGENCY_EXIT'
  confidence: number
  nav_at_decision: number
  summary: string
  agent_reports?: AgentReport[]
  debate_rounds?: DebateRound[]
  risk_assessment?: RiskAssessment
  new_weights?: Record<string, number>
}

export interface Reflection {
  id: string
  timestamp: string
  accuracy_pct: number
  lessons: string[]
  adjustments: string[]
}

export interface BridgeJob {
  id: string
  timestamp: string
  state: 'pending' | 'sending' | 'attesting' | 'claiming' | 'completed' | 'failed'
  amount_usd: number
  token: string
  source_chain: string
  dest_chain: string
  source_tx: string
  dest_tx: string
  error?: string
}

export interface StakingPool {
  tvl_usd: number
  apy_pct: number
  total_stakers: number
  tiers: StakingTier[]
}

export interface StakingTier {
  name: string
  multiplier: number
  min_days: number
  max_days: number
  stakers: number
}

export interface KillSwitchStatus {
  active: boolean
  activated_at?: string
  reason?: string
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const API_BASE = 'http://localhost:8770'
const WS_URL = 'ws://localhost:8770/ws/investments'
const REFRESH_INTERVAL_MS = 30_000

// ---------------------------------------------------------------------------
// Fetch helper
// ---------------------------------------------------------------------------

async function apiFetch<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`)
  if (!res.ok) {
    throw new Error(`API ${path} returned ${res.status}: ${res.statusText}`)
  }
  return res.json() as Promise<T>
}

async function apiPost<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: body ? JSON.stringify(body) : undefined,
  })
  if (!res.ok) {
    throw new Error(`API POST ${path} returned ${res.status}: ${res.statusText}`)
  }
  return res.json() as Promise<T>
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export interface InvestmentDataState {
  basket: BasketData | null
  performance: PerformancePoint[]
  decisions: InvestmentDecision[]
  reflections: Reflection[]
  bridgeJobs: BridgeJob[]
  stakingPool: StakingPool | null
  killSwitch: KillSwitchStatus | null
  loading: boolean
  error: string | null
  wsConnected: boolean
}

export interface InvestmentDataActions {
  refresh: () => Promise<void>
  fetchDecisionDetail: (id: string) => Promise<InvestmentDecision>
  fetchPerformance: (hours: number) => Promise<void>
  triggerCycle: () => Promise<void>
  activateKillSwitch: () => Promise<void>
  deactivateKillSwitch: () => Promise<void>
}

export type UseInvestmentDataReturn = InvestmentDataState & InvestmentDataActions

export function useInvestmentData(): UseInvestmentDataReturn {
  const [basket, setBasket] = useState<BasketData | null>(null)
  const [performance, setPerformance] = useState<PerformancePoint[]>([])
  const [decisions, setDecisions] = useState<InvestmentDecision[]>([])
  const [reflections, setReflections] = useState<Reflection[]>([])
  const [bridgeJobs, setBridgeJobs] = useState<BridgeJob[]>([])
  const [stakingPool, setStakingPool] = useState<StakingPool | null>(null)
  const [killSwitch, setKillSwitch] = useState<KillSwitchStatus | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [wsConnected, setWsConnected] = useState(false)

  const wsRef = useRef<WebSocket | null>(null)
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)

  // ---- Core data fetch ----
  const fetchAll = useCallback(async () => {
    try {
      const [basketRes, perfRes, decisionsRes, reflectionsRes, bridgeRes, poolRes, ksRes] =
        await Promise.allSettled([
          apiFetch<BasketData>('/api/investments/basket'),
          apiFetch<PerformancePoint[]>('/api/investments/performance?hours=168'),
          apiFetch<InvestmentDecision[]>('/api/investments/decisions?limit=20'),
          apiFetch<Reflection[]>('/api/investments/reflections?limit=10'),
          apiFetch<BridgeJob[]>('/api/investments/bridge/jobs?limit=20'),
          apiFetch<StakingPool>('/api/investments/staking/pool'),
          apiFetch<KillSwitchStatus>('/api/investments/kill-switch'),
        ])

      if (basketRes.status === 'fulfilled') setBasket(basketRes.value)
      if (perfRes.status === 'fulfilled') setPerformance(perfRes.value)
      if (decisionsRes.status === 'fulfilled') setDecisions(decisionsRes.value)
      if (reflectionsRes.status === 'fulfilled') setReflections(reflectionsRes.value)
      if (bridgeRes.status === 'fulfilled') setBridgeJobs(bridgeRes.value)
      if (poolRes.status === 'fulfilled') setStakingPool(poolRes.value)
      if (ksRes.status === 'fulfilled') setKillSwitch(ksRes.value)

      // If every request failed, set a general error
      const allFailed = [basketRes, perfRes, decisionsRes, reflectionsRes, bridgeRes, poolRes, ksRes]
        .every(r => r.status === 'rejected')
      if (allFailed) {
        setError('Unable to reach the investment service at ' + API_BASE)
      } else {
        setError(null)
      }
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Unknown fetch error')
    } finally {
      setLoading(false)
    }
  }, [])

  const refresh = useCallback(async () => {
    setLoading(true)
    await fetchAll()
  }, [fetchAll])

  // ---- Fetch a single decision's full detail ----
  const fetchDecisionDetail = useCallback(async (id: string): Promise<InvestmentDecision> => {
    return apiFetch<InvestmentDecision>(`/api/investments/decisions/${id}`)
  }, [])

  // ---- Fetch performance for specific timeframe ----
  const fetchPerformance = useCallback(async (hours: number) => {
    try {
      const data = await apiFetch<PerformancePoint[]>(`/api/investments/performance?hours=${hours}`)
      setPerformance(data)
    } catch (e: unknown) {
      console.error('Failed to fetch performance:', e)
    }
  }, [])

  // ---- Actions ----
  const triggerCycle = useCallback(async () => {
    await apiPost('/api/investments/trigger-cycle')
    // Refresh after trigger to pick up new data
    setTimeout(() => fetchAll(), 2000)
  }, [fetchAll])

  const activateKillSwitch = useCallback(async () => {
    const result = await apiPost<KillSwitchStatus>('/api/investments/kill-switch/activate')
    setKillSwitch(result)
  }, [])

  const deactivateKillSwitch = useCallback(async () => {
    const result = await apiPost<KillSwitchStatus>('/api/investments/kill-switch/deactivate')
    setKillSwitch(result)
  }, [])

  // ---- WebSocket ----
  useEffect(() => {
    let ws: WebSocket | null = null
    let reconnectTimeout: ReturnType<typeof setTimeout> | null = null

    function connect() {
      try {
        ws = new WebSocket(WS_URL)
        wsRef.current = ws

        ws.onopen = () => {
          setWsConnected(true)
        }

        ws.onmessage = (event) => {
          try {
            const msg = JSON.parse(event.data)
            switch (msg.type) {
              case 'basket_update':
                setBasket(msg.data)
                break
              case 'nav_update':
                setPerformance(prev => [...prev, msg.data])
                break
              case 'decision':
                setDecisions(prev => [msg.data, ...prev].slice(0, 20))
                break
              case 'bridge_update':
                setBridgeJobs(prev => {
                  const idx = prev.findIndex(j => j.id === msg.data.id)
                  if (idx >= 0) {
                    const next = [...prev]
                    next[idx] = msg.data
                    return next
                  }
                  return [msg.data, ...prev].slice(0, 20)
                })
                break
              case 'kill_switch':
                setKillSwitch(msg.data)
                break
              default:
                break
            }
          } catch {
            // Ignore malformed messages
          }
        }

        ws.onclose = () => {
          setWsConnected(false)
          wsRef.current = null
          // Attempt reconnect after 5 seconds
          reconnectTimeout = setTimeout(connect, 5000)
        }

        ws.onerror = () => {
          ws?.close()
        }
      } catch {
        // WebSocket construction failed (e.g. bad URL) -- retry later
        reconnectTimeout = setTimeout(connect, 5000)
      }
    }

    connect()

    return () => {
      if (reconnectTimeout) clearTimeout(reconnectTimeout)
      if (ws) {
        ws.onclose = null // prevent reconnect on intentional close
        ws.close()
      }
    }
  }, [])

  // ---- Polling interval ----
  useEffect(() => {
    fetchAll()
    intervalRef.current = setInterval(fetchAll, REFRESH_INTERVAL_MS)
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current)
    }
  }, [fetchAll])

  return {
    basket,
    performance,
    decisions,
    reflections,
    bridgeJobs,
    stakingPool,
    killSwitch,
    loading,
    error,
    wsConnected,
    refresh,
    fetchDecisionDetail,
    fetchPerformance,
    triggerCycle,
    activateKillSwitch,
    deactivateKillSwitch,
  }
}

export default useInvestmentData
