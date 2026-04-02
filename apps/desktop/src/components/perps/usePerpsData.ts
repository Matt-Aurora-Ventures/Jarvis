import { useState, useEffect, useRef, useCallback } from 'react'

const API_BASE = 'http://localhost:5001/api/perps'

export type PerpsMarket = 'SOL-USD' | 'BTC-USD' | 'ETH-USD'

export interface PerpsPrice {
  sol: number
  btc: number
  eth: number
  updated_at: number
}

export interface PerpsCandle {
  time: number
  open: number
  high: number
  low: number
  close: number
}

export interface PerpsArmState {
  stage: 'disarmed' | 'prepared' | 'armed'
  expires_at?: number
  armed_at?: number
  armed_by?: string
  last_reason?: string
}

export interface PerpsDailyStats {
  trades_today: number
  realized_pnl_today: number
  max_trades_per_day: number
  daily_loss_limit_usd: number
}

export interface PerpsStatus {
  runner_healthy: boolean
  runner_pid?: number
  heartbeat_age_s?: number
  arm: PerpsArmState
  daily: PerpsDailyStats
  mode: 'disabled' | 'alert' | 'live'
}

export interface PerpsPosition {
  pda: string
  market: string
  side: 'long' | 'short'
  collateral_usd: number
  leverage: number
  size_usd: number
  entry_price: number
  current_price: number
  unrealized_pnl_pct: number
  unrealized_pnl_usd: number
  peak_pnl_pct: number
  hold_hours: number
  opened_at: string
  exit_trigger?: string
  tp_price?: number
  sl_price?: number
  idempotency_key?: string
}

export interface PerpsSignal {
  direction: 'LONG' | 'SHORT' | 'FLAT'
  market: string
  confidence: number
  sources: {
    grok_weight: number
    momentum_weight: number
    ecosystem_weight: number
    grok_confidence?: number
    momentum_confidence?: number
    ecosystem_confidence?: number
  }
  cooldown_remaining_m?: number
  generated_at?: string
  reasoning?: string
}

export interface PerpsAuditEvent {
  ts: number
  type: string
  actor?: string
  detail?: string
  ok?: boolean
}

export interface PerpsPerformance {
  total_trades: number
  win_rate_pct: number
  avg_pnl_usd: number
  total_pnl_usd: number
  source_accuracy?: Record<string, number>
}

function parseNumber(value: unknown): number {
  const n = Number(value)
  return Number.isFinite(n) ? n : 0
}

function extractPrice(payload: Record<string, unknown>, marketKey: PerpsMarket, symbol: 'SOL' | 'BTC' | 'ETH'): number {
  const marketObj = payload[marketKey] as Record<string, unknown> | undefined
  if (marketObj && typeof marketObj === 'object') {
    const fromMarket = parseNumber(marketObj.price)
    if (fromMarket > 0) return fromMarket
  }

  const upper = parseNumber(payload[symbol])
  if (upper > 0) return upper
  const lower = parseNumber(payload[symbol.toLowerCase()])
  if (lower > 0) return lower

  return parseNumber(payload[marketKey])
}

function normalizeCandles(raw: unknown[]): PerpsCandle[] {
  return raw
    .map((c) => {
      const candle = (c && typeof c === 'object' ? c : {}) as Record<string, unknown>
      return {
        time: parseNumber(candle.time ?? candle.t),
        open: parseNumber(candle.open ?? candle.o),
        high: parseNumber(candle.high ?? candle.h),
        low: parseNumber(candle.low ?? candle.l),
        close: parseNumber(candle.close ?? candle.c),
      }
    })
    .filter((c) => c.time > 0 && c.high >= c.low)
}

export function usePerpsData() {
  const [prices, setPrices] = useState<PerpsPrice | null>(null)
  const [status, setStatus] = useState<PerpsStatus | null>(null)
  const [positions, setPositions] = useState<PerpsPosition[]>([])
  const [signal, setSignal] = useState<PerpsSignal | null>(null)
  const [audit, setAudit] = useState<PerpsAuditEvent[]>([])
  const [performance, setPerformance] = useState<PerpsPerformance | null>(null)
  const [error, setError] = useState<string | null>(null)

  const [historyMarket, setHistoryMarket] = useState<PerpsMarket>('SOL-USD')
  const [historyResolution, setHistoryResolution] = useState('5')
  const [historyCandles, setHistoryCandles] = useState<PerpsCandle[]>([])
  const [historyLoading, setHistoryLoading] = useState(true)
  const [historyError, setHistoryError] = useState<string | null>(null)

  const priceTimerRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const statusTimerRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const auditTimerRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const perfTimerRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const historyTimerRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const fetchPrices = useCallback(async () => {
    try {
      const r = await fetch(`${API_BASE}/prices`)
      if (!r.ok) return
      const d = await r.json() as Record<string, unknown>
      setPrices({
        sol: extractPrice(d, 'SOL-USD', 'SOL'),
        btc: extractPrice(d, 'BTC-USD', 'BTC'),
        eth: extractPrice(d, 'ETH-USD', 'ETH'),
        updated_at: Date.now(),
      })
    } catch {
      // server offline: fail silently
    }
  }, [])

  const fetchStatus = useCallback(async () => {
    try {
      const [statusRes, posRes, sigRes] = await Promise.all([
        fetch(`${API_BASE}/status`),
        fetch(`${API_BASE}/positions`),
        fetch(`${API_BASE}/signal`),
      ])

      if (statusRes.ok) {
        const d = await statusRes.json()
        setStatus({
          runner_healthy: d.runner_healthy ?? d.healthy ?? false,
          runner_pid: d.pid,
          heartbeat_age_s: d.heartbeat_age_s,
          arm: {
            stage: d.arm?.stage ?? 'disarmed',
            expires_at: d.arm?.expires_at,
            armed_at: d.arm?.armed_at,
            armed_by: d.arm?.armed_by,
            last_reason: d.arm?.last_reason,
          },
          daily: {
            trades_today: d.stats?.trades_today ?? 0,
            realized_pnl_today: d.stats?.realized_pnl_today ?? 0,
            max_trades_per_day: d.limits?.max_trades_per_day ?? 40,
            daily_loss_limit_usd: d.limits?.daily_loss_limit_usd ?? 500,
          },
          mode: d.mode ?? 'disabled',
        })
        setError(null)
      }

      if (posRes.ok) {
        const d = await posRes.json()
        setPositions(Array.isArray(d) ? d : d.positions ?? [])
      }

      if (sigRes.ok) {
        const d = await sigRes.json()
        setSignal(d.signal ?? d ?? null)
      }
    } catch {
      setError('Perps API offline')
    }
  }, [])

  const fetchHistory = useCallback(async () => {
    try {
      const r = await fetch(`${API_BASE}/history/${historyMarket}?resolution=${encodeURIComponent(historyResolution)}`)
      if (!r.ok) {
        throw new Error(`HTTP ${r.status}`)
      }
      const d = await r.json() as Record<string, unknown>
      const candles = normalizeCandles(Array.isArray(d.candles) ? d.candles : [])
      setHistoryCandles(candles)
      if (candles.length === 0) {
        const reason = String(d.reason ?? d.error ?? 'no_data')
        setHistoryError(`No candle data (${reason})`)
      } else {
        setHistoryError(null)
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err)
      setHistoryCandles([])
      setHistoryError(`History unavailable (${msg})`)
    } finally {
      setHistoryLoading(false)
    }
  }, [historyMarket, historyResolution])

  const fetchAudit = useCallback(async () => {
    try {
      const r = await fetch(`${API_BASE}/audit`)
      if (!r.ok) return
      const d = await r.json()
      setAudit(Array.isArray(d) ? d : d.events ?? [])
    } catch {
      // ignore
    }
  }, [])

  const fetchPerformance = useCallback(async () => {
    try {
      const r = await fetch(`${API_BASE}/performance`)
      if (!r.ok) return
      const d = await r.json()
      setPerformance(d)
    } catch {
      // ignore
    }
  }, [])

  useEffect(() => {
    fetchPrices()
    fetchStatus()
    fetchAudit()
    fetchPerformance()

    priceTimerRef.current = setInterval(fetchPrices, 2_000)
    statusTimerRef.current = setInterval(fetchStatus, 5_000)
    auditTimerRef.current = setInterval(fetchAudit, 10_000)
    perfTimerRef.current = setInterval(fetchPerformance, 30_000)

    return () => {
      if (priceTimerRef.current) clearInterval(priceTimerRef.current)
      if (statusTimerRef.current) clearInterval(statusTimerRef.current)
      if (auditTimerRef.current) clearInterval(auditTimerRef.current)
      if (perfTimerRef.current) clearInterval(perfTimerRef.current)
    }
  }, [fetchPrices, fetchStatus, fetchAudit, fetchPerformance])

  useEffect(() => {
    setHistoryLoading(true)
    fetchHistory()

    historyTimerRef.current = setInterval(fetchHistory, 15_000)
    return () => {
      if (historyTimerRef.current) clearInterval(historyTimerRef.current)
    }
  }, [fetchHistory])

  const openPosition = useCallback(async (params: {
    market: string
    side: 'long' | 'short'
    collateral_usd: number
    leverage: number
    tp_pct?: number
    sl_pct?: number
  }) => {
    const r = await fetch(`${API_BASE}/open`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(params),
    })
    if (!r.ok) {
      const d = await r.json().catch(() => ({}))
      throw new Error(d.error ?? `HTTP ${r.status}`)
    }
    await fetchStatus()
    await fetchAudit()
    return r.json()
  }, [fetchStatus, fetchAudit])

  const closePosition = useCallback(async (pda: string) => {
    const r = await fetch(`${API_BASE}/close`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ position_pda: pda }),
    })
    if (!r.ok) {
      const d = await r.json().catch(() => ({}))
      throw new Error(d.error ?? `HTTP ${r.status}`)
    }
    await fetchStatus()
    return r.json()
  }, [fetchStatus])

  const prepareArm = useCallback(async () => {
    const r = await fetch(`${API_BASE}/arm`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ step: 'prepare' }),
    })
    if (!r.ok) {
      const d = await r.json().catch(() => ({}))
      throw new Error(d.error ?? `HTTP ${r.status}`)
    }
    const d = await r.json()
    await fetchStatus()
    return d
  }, [fetchStatus])

  const confirmArm = useCallback(async (challenge: string, phrase: string) => {
    const r = await fetch(`${API_BASE}/arm`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ step: 'confirm', challenge, phrase }),
    })
    if (!r.ok) {
      const d = await r.json().catch(() => ({}))
      throw new Error(d.error ?? `HTTP ${r.status}`)
    }
    await fetchStatus()
    return r.json()
  }, [fetchStatus])

  const disarm = useCallback(async (reason = 'user_request') => {
    const r = await fetch(`${API_BASE}/disarm`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ reason }),
    })
    if (!r.ok) {
      const d = await r.json().catch(() => ({}))
      throw new Error(d.error ?? `HTTP ${r.status}`)
    }
    await fetchStatus()
    return r.json()
  }, [fetchStatus])

  return {
    prices,
    status,
    positions,
    signal,
    audit,
    performance,
    error,
    historyMarket,
    historyResolution,
    historyCandles,
    historyLoading,
    historyError,
    setHistoryMarket,
    setHistoryResolution,
    openPosition,
    closePosition,
    prepareArm,
    confirmArm,
    disarm,
    refresh: fetchStatus,
  }
}
