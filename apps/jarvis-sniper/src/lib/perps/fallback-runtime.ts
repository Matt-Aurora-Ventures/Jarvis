import { randomUUID } from 'crypto';

type PerpsMode = 'disabled' | 'alert' | 'live';
type ArmStage = 'disarmed' | 'prepared' | 'armed';

type FallbackPosition = {
  pda: string;
  market: 'SOL-USD' | 'BTC-USD' | 'ETH-USD';
  side: 'long' | 'short';
  size_usd: number;
  entry_price: number;
  current_price: number;
  unrealized_pnl_pct: number;
};

type FallbackAuditEvent = {
  timestamp: number;
  event: string;
  detail?: string;
};

type FallbackRuntimeState = {
  runnerHealthy: boolean;
  mode: PerpsMode;
  armStage: ArmStage;
  armChallenge: string | null;
  armLastReason: string;
  maxTradesPerDay: number;
  dailyLossLimitUsd: number;
  tradesToday: number;
  realizedPnlToday: number;
  positions: FallbackPosition[];
  audit: FallbackAuditEvent[];
};

type FallbackResult = {
  ok: boolean;
  status?: number;
  error?: string;
  [key: string]: unknown;
};

declare global {
  // eslint-disable-next-line no-var
  var __jarvisPerpsFallbackRuntime: FallbackRuntimeState | undefined;
}

const FALLBACK_MARKETS = new Set(['SOL-USD', 'BTC-USD', 'ETH-USD']);
const FALLBACK_PRICES: Record<'SOL-USD' | 'BTC-USD' | 'ETH-USD', number> = {
  'SOL-USD': 0,
  'BTC-USD': 0,
  'ETH-USD': 0,
};

function runtimeState(): FallbackRuntimeState {
  if (!globalThis.__jarvisPerpsFallbackRuntime) {
    globalThis.__jarvisPerpsFallbackRuntime = {
      runnerHealthy: false,
      mode: 'disabled',
      armStage: 'disarmed',
      armChallenge: null,
      armLastReason: 'perps_upstream_unavailable',
      maxTradesPerDay: 40,
      dailyLossLimitUsd: 500,
      tradesToday: 0,
      realizedPnlToday: 0,
      positions: [],
      audit: [],
    };
  }
  return globalThis.__jarvisPerpsFallbackRuntime;
}

function audit(event: string, detail?: string): void {
  const state = runtimeState();
  state.audit.unshift({
    timestamp: Math.floor(Date.now() / 1000),
    event,
    ...(detail ? { detail } : {}),
  });
  if (state.audit.length > 50) state.audit = state.audit.slice(0, 50);
}

function clampPositiveInt(value: unknown, fallback: number): number {
  const parsed = Number(value);
  if (!Number.isFinite(parsed) || parsed <= 0) return fallback;
  return Math.floor(parsed);
}

export function fallbackStatusPayload() {
  const state = runtimeState();
  return {
    runner_healthy: state.runnerHealthy,
    mode: state.mode,
    arm: {
      stage: state.armStage,
      last_reason: state.armLastReason,
    },
    daily: {
      trades_today: state.tradesToday,
      realized_pnl_today: state.realizedPnlToday,
      max_trades_per_day: state.maxTradesPerDay,
      daily_loss_limit_usd: state.dailyLossLimitUsd,
    },
    _fallback: true,
    _fallbackReason: 'perps_upstream_unavailable',
  };
}

export function fallbackPricesPayload() {
  return {
    'SOL-USD': { price: FALLBACK_PRICES['SOL-USD'] },
    'BTC-USD': { price: FALLBACK_PRICES['BTC-USD'] },
    'ETH-USD': { price: FALLBACK_PRICES['ETH-USD'] },
    _fallback: true,
    _fallbackReason: 'perps_upstream_unavailable',
  };
}

export function fallbackPositionsPayload() {
  return {
    positions: runtimeState().positions,
    _fallback: true,
    _fallbackReason: 'perps_upstream_unavailable',
  };
}

export function fallbackAuditPayload() {
  return {
    events: runtimeState().audit,
    _fallback: true,
    _fallbackReason: 'perps_upstream_unavailable',
  };
}

export function fallbackStartRunner(): FallbackResult {
  const state = runtimeState();
  state.runnerHealthy = true;
  if (state.mode === 'disabled') state.mode = 'alert';
  audit('fallback_runner_started');
  return { ok: true, message: 'Runner started (fallback mode).', _fallback: true };
}

export function fallbackStopRunner(): FallbackResult {
  const state = runtimeState();
  state.runnerHealthy = false;
  state.mode = 'disabled';
  state.armStage = 'disarmed';
  state.armChallenge = null;
  state.armLastReason = 'runner_stopped';
  audit('fallback_runner_stopped');
  return { ok: true, message: 'Runner stopped (fallback mode).', _fallback: true };
}

export function fallbackArm(payload: Record<string, unknown>): FallbackResult {
  const state = runtimeState();
  const step = String(payload.step || 'prepare').toLowerCase();

  if (step === 'prepare') {
    const challenge = randomUUID();
    state.armChallenge = challenge;
    state.armStage = 'prepared';
    if (!state.runnerHealthy) {
      state.runnerHealthy = true;
      state.mode = 'alert';
    }
    state.armLastReason = 'prepared';
    audit('fallback_arm_prepare');
    return { ok: true, challenge, _fallback: true };
  }

  if (step === 'confirm') {
    const challenge = String(payload.challenge || '').trim();
    if (!challenge || challenge !== state.armChallenge) {
      audit('fallback_arm_confirm_failed', 'challenge_mismatch');
      return { ok: false, status: 400, error: 'Invalid arm challenge.', _fallback: true };
    }
    state.runnerHealthy = true;
    state.mode = 'live';
    state.armStage = 'armed';
    state.armChallenge = null;
    state.armLastReason = 'armed';
    audit('fallback_arm_confirm');
    return { ok: true, mode: state.mode, stage: state.armStage, _fallback: true };
  }

  return { ok: false, status: 400, error: "step must be 'prepare' or 'confirm'", _fallback: true };
}

export function fallbackDisarm(): FallbackResult {
  const state = runtimeState();
  state.armStage = 'disarmed';
  state.armChallenge = null;
  state.armLastReason = 'manual_disarm';
  state.mode = state.runnerHealthy ? 'alert' : 'disabled';
  audit('fallback_disarm');
  return { ok: true, mode: state.mode, stage: state.armStage, _fallback: true };
}

export function fallbackUpdateLimits(payload: Record<string, unknown>): FallbackResult {
  const state = runtimeState();
  state.maxTradesPerDay = clampPositiveInt(payload.max_trades_per_day, state.maxTradesPerDay);
  state.dailyLossLimitUsd = clampPositiveInt(payload.daily_loss_limit_usd, state.dailyLossLimitUsd);
  audit(
    'fallback_limits_updated',
    `max_trades_per_day=${state.maxTradesPerDay},daily_loss_limit_usd=${state.dailyLossLimitUsd}`,
  );
  return {
    ok: true,
    max_trades_per_day: state.maxTradesPerDay,
    daily_loss_limit_usd: state.dailyLossLimitUsd,
    _fallback: true,
  };
}

export function fallbackOpenPosition(payload: Record<string, unknown>): FallbackResult {
  const state = runtimeState();
  if (!state.runnerHealthy || state.mode !== 'live' || state.armStage !== 'armed') {
    return {
      ok: false,
      status: 409,
      error: 'Live order entry requires mode=LIVE and arm stage=ARMED.',
      _fallback: true,
    };
  }

  const market = String(payload.market || '').toUpperCase();
  if (!FALLBACK_MARKETS.has(market)) {
    return { ok: false, status: 400, error: 'market must be SOL-USD, BTC-USD, or ETH-USD', _fallback: true };
  }

  const sideRaw = String(payload.side || '').toLowerCase();
  if (sideRaw !== 'long' && sideRaw !== 'short') {
    return { ok: false, status: 400, error: 'side must be long or short', _fallback: true };
  }

  const collateral = Number(payload.collateral_amount_usd ?? payload.collateral_usd ?? 0);
  const leverage = Number(payload.leverage ?? 1);
  const sizeUsd = Number(payload.size_usd ?? collateral * leverage);
  if (!Number.isFinite(sizeUsd) || sizeUsd <= 0) {
    return { ok: false, status: 400, error: 'size_usd must be > 0', _fallback: true };
  }

  const typedMarket = market as 'SOL-USD' | 'BTC-USD' | 'ETH-USD';
  const entryPrice = Number(FALLBACK_PRICES[typedMarket] || 0);
  const position: FallbackPosition = {
    pda: `fallback-${randomUUID()}`,
    market: typedMarket,
    side: sideRaw,
    size_usd: sizeUsd,
    entry_price: entryPrice,
    current_price: entryPrice,
    unrealized_pnl_pct: 0,
  };

  state.positions.unshift(position);
  state.tradesToday += 1;
  audit('fallback_open_position', `${position.side} ${position.market} size=${sizeUsd.toFixed(2)}`);
  return { ok: true, position, _fallback: true };
}

export function fallbackClosePosition(payload: Record<string, unknown>): FallbackResult {
  const state = runtimeState();
  const target = String(payload.position_pda || '').trim();
  if (!target) {
    return { ok: false, status: 400, error: 'position_pda required', _fallback: true };
  }

  const index = state.positions.findIndex((position) => position.pda === target);
  if (index < 0) {
    return { ok: false, status: 404, error: 'position not found', _fallback: true };
  }

  const [closed] = state.positions.splice(index, 1);
  audit('fallback_close_position', `${closed.side} ${closed.market} ${closed.pda}`);
  return { ok: true, closed_position: closed, _fallback: true };
}
