# Feature Plan: Bags.fm Graduation Page

Created: 2026-02-10
Author: architect-agent (Opus 4.6)

---

## Overview

A dedicated `/bags` page within the Jarvis Sniper terminal that focuses exclusively on bags.fm graduated tokens. Unlike the main sniper page which scans all Solana tokens via DexScreener, this page provides a YC-style startup assessment framework for bags.fm launches -- combining quantitative on-chain metrics with qualitative founder/project evaluation. The page replaces the liquidity metric (meaningless for bags.fm locked liquidity) with creator reputation, project quality, and product-market fit scoring dimensions.

## Requirements

- [ ] Separate route at `/bags` with its own page component
- [ ] Navigation link in StatusBar to switch between Sniper and Bags pages
- [ ] Bags-only token feed (old and new graduated tokens from bags.fm API)
- [ ] YC-style 6-dimension scoring algorithm (no liquidity metric)
- [ ] Creator reputation scoring (Twitter, account age, launch history)
- [ ] Project quality scoring (description, website, socials, whitepaper)
- [ ] On-chain metrics scoring (holders, distribution, buy/sell ratio, volume)
- [ ] Market performance scoring (price stability post-graduation, survival time)
- [ ] Community engagement scoring (social sentiment, follower count)
- [ ] Product-market fit scoring (narrative quality, sector timing, uniqueness)
- [ ] Bags-specific Zustand store (separate from sniper store)
- [ ] Bags-specific API route that fetches from bags.fm API directly
- [ ] Bags-specific backtesting engine using historical graduation data
- [ ] Trading execution reuses existing bags-trading.ts swap infrastructure
- [ ] Same theme system (dark/light mode via CSS variables)

---

## Design

### Architecture

```
StatusBar (modified -- adds navigation links)
    |
    +-- / (SniperDashboard - existing, unchanged)
    +-- /bags (BagsPage - NEW)
            |
            +-- BagsTokenFeed (left column)
            |       |-- fetches /api/bags/graduations
            |       |-- BagsTokenCard (with YC-style score breakdown)
            |
            +-- BagsCenter (center column)
            |       |-- BagsPerformanceSummary
            |       |-- BagsBacktestPanel
            |       |-- TokenChart (reused from sniper)
            |       |-- BagsExecutionLog
            |
            +-- BagsRight (right column)
                    |-- BagsControls (strategy config)
                    |-- BagsCreatorProfile (expanded creator view)
                    |-- BagsPositionsPanel
```

### File Structure

```
jarvis-sniper/src/
  app/
    bags/
      page.tsx                    -- NEW: Bags graduation page
    api/bags/
      graduations/route.ts        -- NEW: Bags-specific graduation feed
      creator/route.ts            -- NEW: Creator profile lookup
      backtest/route.ts           -- NEW: Bags backtesting endpoint
      quote/route.ts              -- EXISTING: reuse
      swap/route.ts               -- EXISTING: reuse
  components/bags/
    BagsTokenFeed.tsx             -- NEW: Bags-only token scanner
    BagsTokenCard.tsx             -- NEW: YC-style token card
    BagsScoreRadar.tsx            -- NEW: Radar chart for 6 dimensions
    BagsControls.tsx              -- NEW: Strategy controls for bags
    BagsCreatorProfile.tsx        -- NEW: Expanded creator view
    BagsPositionsPanel.tsx        -- NEW: Bags positions list
    BagsPerformanceSummary.tsx    -- NEW: Bags-specific P&L summary
    BagsBacktestPanel.tsx         -- NEW: Bags backtest UI
    BagsExecutionLog.tsx          -- NEW: Bags execution log
  components/
    StatusBar.tsx                 -- MODIFIED: add /bags nav link
    TokenChart.tsx                -- REUSE: same chart component
  stores/
    useBagsStore.ts               -- NEW: Bags-specific Zustand store
  hooks/
    useBagsBacktest.ts            -- NEW: Bags backtesting hook
    useBagsRiskManagement.ts      -- NEW: Bags SL/TP management
    useBagsSnipeExecutor.ts       -- NEW: Bags trade executor
  lib/
    bags-api.ts                   -- EXISTING: reuse + extend
    bags-trading.ts               -- EXISTING: reuse as-is
    bags-scoring.ts               -- NEW: YC-style scoring algorithm
    bags-creator-lookup.ts        -- NEW: Creator profile resolution
    bags-historical.ts            -- NEW: Historical graduation data
```

### Interfaces

```typescript
// --- src/lib/bags-scoring.ts ---
//
// YC-Style Assessment Dimensions for Bags.fm Tokens
// IMPORTANT: No liquidity dimension. Bags.fm locks liquidity at graduation,
// making it a constant -- not a differentiator.

/** Individual dimension score (0-100) with breakdown */
interface DimensionScore {
  score: number;             // 0-100
  weight: number;            // fraction of total (sums to 1.0)
  breakdown: ScoreFactor[];  // individual factors that built this score
  flags: {
    green: string[];
    red: string[];
    warnings: string[];
  };
}

interface ScoreFactor {
  name: string;
  value: number | string;
  contribution: number;  // points added/subtracted
  reasoning: string;
}

/** Complete YC-style assessment for a bags.fm token */
interface BagsAssessment {
  mint: string;
  symbol: string;
  name: string;
  overallScore: number;       // 0-100 weighted composite
  tier: 'exceptional' | 'strong' | 'average' | 'weak' | 'poor';
  riskLevel: 'low' | 'medium' | 'high' | 'extreme';

  dimensions: {
    creatorReputation: DimensionScore;   // 25% weight
    projectQuality: DimensionScore;       // 20% weight
    onChainMetrics: DimensionScore;       // 20% weight
    marketPerformance: DimensionScore;    // 15% weight
    communityEngagement: DimensionScore;  // 10% weight
    productMarketFit: DimensionScore;     // 10% weight
  };

  greenFlags: string[];
  redFlags: string[];
  warnings: string[];
  grokSummary?: string;
  assessedAt: number;
  graduatedAt: number;
}

// --- src/stores/useBagsStore.ts ---

interface BagsConfig {
  stopLossPct: number;
  takeProfitPct: number;
  trailingStopPct: number;
  maxPositionSol: number;
  maxConcurrentPositions: number;

  // Quality gates (bags-specific)
  minOverallScore: number;
  minCreatorScore: number;
  minProjectScore: number;
  requireTwitter: boolean;
  requireWebsite: boolean;
  maxGraduationAgeHours: number;
  minHolderCount: number;
  maxTop10HolderPct: number;

  autoSnipe: boolean;
  useJito: boolean;
  slippageBps: number;
  strategyMode: 'conservative' | 'balanced' | 'aggressive';

  circuitBreakerEnabled: boolean;
  maxConsecutiveLosses: number;
  maxDailyLossSol: number;
  minBalanceGuardSol: number;
}

/** Bags graduation data from the bags.fm API (extended) */
interface BagsGraduationExtended {
  mint: string;
  symbol: string;
  name: string;
  price_usd: number;
  market_cap: number;
  graduation_time: number;
  logo_uri?: string;

  // Bags-specific fields
  description?: string;
  website?: string;
  twitter?: string;
  telegram?: string;
  creator_wallet?: string;

  // On-chain metrics
  holder_count: number;
  top_10_holder_pct: number;
  volume_24h: number;
  buys_1h: number;
  sells_1h: number;
  buy_sell_ratio: number;
  price_change_1h: number;
  price_change_24h: number;

  // Bonding curve history
  bonding_duration_seconds: number;
  bonding_volume_sol: number;
  bonding_unique_buyers: number;

  // Computed
  assessment?: BagsAssessment;
  age_hours: number;
  is_alive: boolean;
}

interface BagsPosition {
  id: string;
  mint: string;
  symbol: string;
  name: string;
  walletAddress?: string;
  entryPrice: number;
  currentPrice: number;
  amount: number;
  amountLamports?: string;
  solInvested: number;
  pnlPercent: number;
  pnlSol: number;
  entryTime: number;
  txHash?: string;
  status: 'open' | 'tp_hit' | 'sl_hit' | 'trail_stop' | 'expired' | 'closed';
  isClosing?: boolean;
  assessment: BagsAssessment;
  highWaterMarkPct: number;
  exitSolReceived?: number;
  realPnlSol?: number;
  realPnlPercent?: number;
}
```

### Scoring Algorithm: YC-Style Assessment

The scoring replaces the sniper's liquidity-centric model with a startup investor framework. Each dimension is scored 0-100 and weighted to produce a composite.

#### Dimension 1: Creator Reputation (25%)

This is the highest-weighted dimension because in bags.fm, the creator IS the startup founder.

| Factor | Points | Logic |
|--------|--------|-------|
| Has Twitter linked | +15 | Identity verification signal |
| Twitter followers >= 1000 | +25 | Established influence |
| Twitter followers >= 100 | +10 | Minimum audience |
| Twitter account age >= 30d | +15 | Not a throwaway account |
| Twitter account age < 7d | -25 | Suspicious new account |
| No Twitter | -10 | Anonymous creator |
| Previous successful launches | +10 per (max 20) | Track record matters |
| Previous rugs/scams | -40 per | Instant red flag |
| Wallet age > 90 days | +10 | Established wallet |
| Wallet age < 7 days | -15 | Fresh wallet suspicious |
| Base score | 40 | Starting point |

#### Dimension 2: Project Quality (20%)

Evaluates the project's presentation and substance -- like a YC application review.

| Factor | Points | Logic |
|--------|--------|-------|
| Has description (>50 chars) | +10 | Effort into explanation |
| Has detailed description (>200 chars) | +10 | Even more effort |
| Has website | +15 | Professional presence |
| Has whitepaper/docs link | +10 | Technical depth |
| Has logo/branding | +5 | Visual identity |
| Multiple socials (>=3) | +15 | Ecosystem presence |
| Two socials | +8 | Minimum viable |
| No socials at all | -20 | Ghost project |
| Name is generic/spammy pattern | -15 | Low effort copycat |
| Base score | 40 | Starting point |

#### Dimension 3: On-Chain Metrics (20%)

Pure quantitative on-chain analysis -- the numbers don't lie.

| Factor | Points | Logic |
|--------|--------|-------|
| Holder count >= 500 | +20 | Well distributed |
| Holder count >= 100 | +10 | Growing community |
| Holder count < 50 | -15 | Concentrated |
| Top 10 holders <= 30% | +25 | Healthy distribution |
| Top 10 holders <= 50% | +10 | Acceptable |
| Top 10 holders > 50% | -25 | Whale risk |
| Volume 24h > $50K | +15 | Active trading |
| Volume 24h > $10K | +8 | Some activity |
| Buy/sell ratio 1.2-3.0 | +15 | Healthy demand |
| Buy/sell ratio > 5.0 | -10 | Manipulation signal |
| Buy/sell ratio < 0.5 | -15 | Sell pressure |
| Bonding curve duration 5-60 min | +15 | Organic graduation |
| Bonding curve < 1 min | -20 | Suspiciously fast |
| Unique bonding buyers >= 100 | +15 | Organic interest |
| Unique bonding buyers < 20 | -15 | Few participants |
| Base score | 40 | Starting point |

#### Dimension 4: Market Performance (15%)

How the token performs AFTER graduation -- survival is the real test.

| Factor | Points | Logic |
|--------|--------|-------|
| Still alive after 24h | +15 | Survived initial dump |
| Still alive after 7d | +25 | Real staying power |
| Still alive after 30d | +10 (bonus) | Veteran |
| Price stability (< 50% drawdown from ATH) | +15 | Not a pump-and-dump |
| Price > graduation price | +10 | Positive performance |
| 1h price change > +100% | -10 | Pump warning |
| 1h price change < -50% | -20 | Dump in progress |
| 24h volume > market cap * 0.1 | +10 | Active market |
| Base score | 40 | Starting point |

#### Dimension 5: Community Engagement (10%)

Social proof and organic community building.

| Factor | Points | Logic |
|--------|--------|-------|
| Telegram group exists | +15 | Community hub |
| Telegram group > 100 members | +10 | Active community |
| Twitter mentions in last 24h | +15 | Social buzz |
| Multiple independent Twitter mentions | +10 | Organic (not just creator) |
| No social activity | -20 | Dead community |
| Base score | 50 | Starting point |

#### Dimension 6: Product-Market Fit (10%)

Qualitative assessment of whether the project addresses a real need or trend.

| Factor | Points | Logic |
|--------|--------|-------|
| Trending narrative match (AI, RWA, DePIN, etc.) | +20 | Sector timing |
| Has utility beyond speculation | +15 | Real use case |
| Unique concept (not a clone) | +10 | Differentiation |
| Clone of existing token name | -15 | Low effort copycat |
| Fair launch or community-driven narrative | +10 | Popular meta |
| Base score | 45 | Starting point |

**NOTE on PMF scoring:** This dimension is harder to automate. Phase 1 implementation will use keyword matching on description + name + socials. Phase 2 can integrate Grok AI for qualitative assessment.

#### Composite Score

```
overallScore = (
    creatorReputation.score * 0.25 +
    projectQuality.score * 0.20 +
    onChainMetrics.score * 0.20 +
    marketPerformance.score * 0.15 +
    communityEngagement.score * 0.10 +
    productMarketFit.score * 0.10
)
```

#### Tier Classification

| Tier | Score Range | Action |
|------|-------------|--------|
| Exceptional | 80-100 | Strong buy signal, maximum conviction |
| Strong | 65-79 | Good entry, standard position |
| Average | 50-64 | Watch only unless other signals align |
| Weak | 35-49 | Avoid or very small position |
| Poor | 0-34 | Do not trade, likely scam |

### Data Flow

```
1. User navigates to /bags
2. BagsPage mounts, triggers BagsTokenFeed
3. BagsTokenFeed calls /api/bags/graduations (server route)
4. Server route:
   a. Fetches graduated tokens from bags.fm public API
   b. For each token, fetches DexScreener pair data for on-chain metrics
   c. Optionally fetches creator profiles from /api/bags/creator
   d. Runs scoring algorithm (bags-scoring.ts server-side)
   e. Returns sorted list with full BagsAssessment
5. Client receives scored list, renders BagsTokenCards
6. User clicks card -> radar chart + full breakdown
7. User clicks SNIPE -> reuses existing bags-trading.ts swap flow
8. Positions tracked in useBagsStore (separate from sniper store)
9. Risk management (SL/TP/trailing) runs via useBagsRiskManagement hook
```

### Navigation Changes (StatusBar.tsx)

The StatusBar will be modified to include navigation between the two pages. Uses Next.js `usePathname` to highlight the active page.

```typescript
// In the branding section, after the "JARVIS SNIPER" title:
import Link from 'next/link';
import { usePathname } from 'next/navigation';

const pathname = usePathname();

<nav className="flex items-center gap-1 ml-4">
  <Link href="/"
    className={`text-[10px] font-mono font-semibold uppercase tracking-wider
      px-3 py-1.5 rounded-full transition-colors ${
      pathname === '/'
        ? 'bg-accent-neon/15 text-accent-neon border border-accent-neon/30'
        : 'text-text-muted hover:text-text-secondary'
    }`}>
    SNIPER
  </Link>
  <Link href="/bags"
    className={`text-[10px] font-mono font-semibold uppercase tracking-wider
      px-3 py-1.5 rounded-full transition-colors ${
      pathname === '/bags'
        ? 'bg-purple-500/15 text-purple-400 border border-purple-500/30'
        : 'text-text-muted hover:text-text-secondary'
    }`}>
    BAGS.FM
  </Link>
</nav>
```

The Bags page gets a purple accent to visually differentiate it from the green sniper theme.

---

## Dependencies

| Dependency | Type | Reason | Status |
|------------|------|--------|--------|
| `bags-api.ts` | Internal | Bags.fm API client | EXISTING - extend |
| `bags-trading.ts` | Internal | Swap execution (buy/sell) | EXISTING - reuse as-is |
| `TokenChart.tsx` | Internal | Price chart component | EXISTING - reuse |
| `usePhantomWallet` hook | Internal | Wallet connection | EXISTING - reuse |
| `useSnipeExecutor` hook | Internal | Trade execution | EXISTING - reuse or adapt |
| DexScreener API | External | On-chain metrics, pair data | EXISTING - reuse |
| Bags.fm API v2 | External | Graduation feed, token metadata | EXISTING - extend usage |
| Helius RPC | External | Holder data, wallet age | OPTIONAL - Phase 2 |
| Grok AI (xAI) | External | Qualitative PMF analysis | OPTIONAL - Phase 2 |
| `next/navigation` | External | `usePathname` for nav state | Built into Next.js 15 |

---

## Reuse vs New Matrix

| Component | Action | Notes |
|-----------|--------|-------|
| `bags-api.ts` | EXTEND | Add creator lookup, graduation history endpoints |
| `bags-trading.ts` | REUSE | Swap flow identical for bags tokens |
| `TokenChart.tsx` | REUSE | Same chart, just pass bags token mint |
| `StatusBar.tsx` | MODIFY | Add SNIPER / BAGS.FM nav tabs |
| `usePhantomWallet` | REUSE | Same wallet connection |
| `useSnipeExecutor` | REUSE/ADAPT | May need bags-specific variant |
| `useSniperStore.ts` | REFERENCE | Pattern reference, but bags gets own store |
| `globals.css` | REUSE | Same theme system, add purple accent vars |
| `layout.tsx` | REUSE | Shared layout with WalletProvider |
| `GraduationFeed.tsx` | REFERENCE | Pattern reference for BagsTokenFeed |
| `SniperControls.tsx` | REFERENCE | Pattern reference for BagsControls |
| `/api/graduations/route.ts` | REFERENCE | Pattern for new bags graduations route |
| `/api/backtest/route.ts` | REFERENCE | Pattern for bags backtest route |
| `bots/bags_intel/scorer.py` | REFERENCE | Scoring logic to port to TypeScript |
| `bots/bags_intel/models.py` | REFERENCE | Data model shapes to port |

---

## Implementation Phases

### Phase 1: Foundation (Types, Interfaces, Store)

**Files to create:**
- `src/lib/bags-scoring.ts` -- Scoring algorithm (port from Python scorer.py + new YC dimensions)
- `src/stores/useBagsStore.ts` -- Zustand store with persist (modeled after useSniperStore)

**Files to modify:**
- `src/app/globals.css` -- Add purple accent CSS variables for bags theme

**Acceptance:**
- [ ] TypeScript interfaces compile without errors
- [ ] BagsAssessment type covers all 6 dimensions
- [ ] useBagsStore has config, positions, graduations, execution log, circuit breaker
- [ ] Scoring function produces correct scores for test inputs
- [ ] Purple accent variables render in both dark and light themes

**Estimated effort:** Medium (1-2 sessions)

### Phase 2: API Routes (Server-Side Data)

**Files to create:**
- `src/app/api/bags/graduations/route.ts` -- Fetch bags.fm graduations + enrich with DexScreener + score
- `src/app/api/bags/creator/route.ts` -- Creator wallet profile lookup (Twitter, history)

**Dependencies:** Phase 1 (scoring types)

**Key design decisions:**
- Server-side scoring avoids exposing scoring logic to client
- 10-second cache TTL (bags graduations change slower than DexScreener boosts)
- Rate limiting: reuse existing `apiRateLimiter` from sniper
- Creator lookup: check bags.fm API for linked socials, then DexScreener profiles

**Data sources for the API route:**

```
bags.fm /api/graduations        -> mint, symbol, name, graduation_time, description, socials
bags.fm /api/tokens/{mint}      -> detailed token info
DexScreener /tokens/v1/solana/  -> pair data, volume, buys/sells, holder metrics
DexScreener /token-profiles/    -> social links, website
```

**Acceptance:**
- [ ] GET /api/bags/graduations returns scored BagsGraduationExtended[]
- [ ] GET /api/bags/creator?wallet=... returns creator profile
- [ ] Caching works (X-Cache: HIT on second request within TTL)
- [ ] Rate limiting works (429 on excessive requests)

**Estimated effort:** Medium (1-2 sessions)

### Phase 3: Core Components (UI)

**Files to create:**
- `src/components/bags/BagsTokenFeed.tsx` -- Token scanner (left column)
- `src/components/bags/BagsTokenCard.tsx` -- Individual token card with YC score
- `src/components/bags/BagsScoreRadar.tsx` -- 6-axis radar chart visualization
- `src/components/bags/BagsControls.tsx` -- Strategy configuration panel
- `src/components/bags/BagsCreatorProfile.tsx` -- Expanded creator/project view
- `src/components/bags/BagsPositionsPanel.tsx` -- Open/closed positions list
- `src/components/bags/BagsPerformanceSummary.tsx` -- P&L summary bar
- `src/components/bags/BagsExecutionLog.tsx` -- Trade execution log
- `src/app/bags/page.tsx` -- Page component (3-column layout)

**Files to modify:**
- `src/components/StatusBar.tsx` -- Add SNIPER / BAGS.FM navigation tabs

**Dependencies:** Phase 1, Phase 2

**Component Details:**

**BagsTokenCard** -- The key differentiator from the sniper TokenCard:
- Shows 6-dimension mini radar chart instead of filter dots
- Displays creator Twitter handle + follower count
- Shows green/red flag count badge
- Age label shows "alive X days" instead of just graduation time
- No liquidity metric shown (it is locked and meaningless)
- Conviction sizing based on YC composite score (not vol/liq)

**BagsControls** -- Bags-specific strategy panel:
- Quality gates: min overall score, min creator score, require Twitter toggle
- Exit strategy: SL/TP/trail (reuses sniper pattern but different defaults)
  - Default bags SL: 30% (bags tokens more volatile post-graduation)
  - Default bags TP: 150% (bags survivors often 5-10x)
  - Default bags trail: 15% (wider trail for bags volatility)
- Budget authorization (same as sniper)
- Auto-snipe toggle
- Circuit breaker settings

**BagsScoreRadar** -- SVG radar chart:
- 6 axes: Creator, Project, On-Chain, Market, Community, PMF
- Fill color based on tier (green for strong, yellow for average, red for weak)
- Hover to see individual dimension scores
- No external charting library -- pure SVG for zero bundle bloat

**Acceptance:**
- [ ] /bags page renders with 3-column layout
- [ ] BagsTokenFeed fetches and displays bags graduations
- [ ] BagsTokenCard shows YC score + radar chart
- [ ] StatusBar shows navigation between Sniper and Bags
- [ ] BagsControls can configure bags-specific settings
- [ ] Manual snipe (click SNIPE on card) works via bags-trading.ts
- [ ] Positions tracked in useBagsStore

**Estimated effort:** Large (2-3 sessions)

### Phase 4: Risk Management and Trading Integration

**Files to create:**
- `src/hooks/useBagsRiskManagement.ts` -- SL/TP/trailing stop monitoring
- `src/hooks/useBagsSnipeExecutor.ts` -- Bags-specific trade executor (or adapt existing)

**Dependencies:** Phase 3

**Key adaptations from sniper risk management:**
- Same SL/TP/trailing stop logic
- Different defaults (wider stops for bags volatility)
- Conviction sizing based on YC score instead of vol/liq ratio
- No trading hours gate (bags tokens trade 24/7, no OHLCV-proven hour pattern yet)
- No min-age-minutes gate (bags graduations are the event, not DexScreener boosts)
- Circuit breaker identical to sniper pattern

**Conviction Multiplier for Bags:**

```typescript
function getBagsConvictionMultiplier(
  assessment: BagsAssessment
): { multiplier: number; factors: string[] } {
  let score = 0;
  const factors: string[] = [];

  // Factor 1: Overall YC score (highest weight)
  if (assessment.overallScore >= 80) {
    score += 0.5; factors.push('Elite YC score');
  } else if (assessment.overallScore >= 65) {
    score += 0.3; factors.push('Strong YC score');
  } else if (assessment.overallScore >= 50) {
    score += 0.1; factors.push('Average YC score');
  }

  // Factor 2: Creator reputation
  const creatorScore = assessment.dimensions.creatorReputation.score;
  if (creatorScore >= 80) {
    score += 0.3; factors.push('Trusted creator');
  } else if (creatorScore >= 60) {
    score += 0.1;
  }

  // Factor 3: No red flags
  if (assessment.redFlags.length === 0) {
    score += 0.2; factors.push('Clean');
  } else if (assessment.redFlags.length >= 3) {
    score -= 0.3; factors.push(String(assessment.redFlags.length) + ' red flags');
  }

  // Factor 4: Survival (market performance)
  if (assessment.dimensions.marketPerformance.score >= 70) {
    score += 0.2; factors.push('Survivor');
  }

  // Negative: high risk
  if (assessment.riskLevel === 'extreme') {
    score -= 0.5; factors.push('EXTREME risk');
  } else if (assessment.riskLevel === 'high') {
    score -= 0.2; factors.push('High risk');
  }

  const multiplier = Math.max(0.3, Math.min(2.0, 0.5 + score));
  return { multiplier, factors };
}
```

**Acceptance:**
- [ ] Auto-snipe triggers on qualifying bags tokens
- [ ] SL/TP/trailing stop executes sells correctly
- [ ] Circuit breaker trips after cascading losses
- [ ] Conviction sizing scales position by YC score

**Estimated effort:** Medium (1-2 sessions)

### Phase 5: Backtesting

**Files to create:**
- `src/lib/bags-historical.ts` -- Fetch historical bags.fm graduation data
- `src/lib/bags-backtest-engine.ts` -- Bags-specific backtest engine
- `src/app/api/bags/backtest/route.ts` -- Server-side backtest endpoint
- `src/hooks/useBagsBacktest.ts` -- Client-side backtest hook

**Dependencies:** Phase 1, Phase 2

**Backtesting Approach:**

The bags backtesting problem is different from memecoin sniping:

1. **Data source:** All historical bags.fm graduations (fetch from bags.fm API or build database)
2. **Key question:** "If I had bought at graduation, what would have happened?"
3. **Metrics to track per graduation:**
   - Price at graduation
   - Peak price post-graduation (and time to peak)
   - Current price (or price at death)
   - Maximum drawdown
   - Time alive
   - Whether it is still alive today
4. **Backtest simulation:**
   - For each historical graduation, compute the YC assessment score
   - Simulate entry at graduation + configurable delay (0, 5, 15, 30 min)
   - Apply SL/TP/trailing stop rules against actual price history
   - Track win rate, average P&L, Sharpe ratio, max drawdown

**Strategy presets for bags:**

```typescript
const BAGS_STRATEGY_PRESETS = [
  {
    id: 'bags_conservative',
    name: 'BAGS CONSERVATIVE',
    description: 'High YC score only, tight exits',
    config: {
      minOverallScore: 70, minCreatorScore: 60,
      requireTwitter: true,
      stopLossPct: 25, takeProfitPct: 100, trailingStopPct: 12,
    },
  },
  {
    id: 'bags_balanced',
    name: 'BAGS BALANCED',
    description: 'Moderate filters, standard exits',
    config: {
      minOverallScore: 55, minCreatorScore: 40,
      requireTwitter: false,
      stopLossPct: 35, takeProfitPct: 200, trailingStopPct: 18,
    },
  },
  {
    id: 'bags_aggressive',
    name: 'BAGS DEGEN',
    description: 'Wide net, ride the 10x runners',
    config: {
      minOverallScore: 35, minCreatorScore: 0,
      requireTwitter: false,
      stopLossPct: 50, takeProfitPct: 500, trailingStopPct: 25,
    },
  },
  {
    id: 'bags_founder_bet',
    name: 'FOUNDER BET',
    description: 'Strong creator + project quality only',
    config: {
      minOverallScore: 50, minCreatorScore: 75,
      minProjectScore: 65,
      requireTwitter: true, requireWebsite: true,
      stopLossPct: 40, takeProfitPct: 300, trailingStopPct: 20,
    },
  },
];
```

**Historical Data Collection Strategy:**

```
Step 1: Fetch all graduations from bags.fm API (paginated)
Step 2: For each graduation, fetch DexScreener OHLCV candles post-graduation
Step 3: Compute YC assessment retroactively
Step 4: Simulate SL/TP/trail against candle data
Step 5: Aggregate statistics by score tier, strategy, time period
```

**Acceptance:**
- [ ] Historical graduation data fetchable (at least 100+ tokens)
- [ ] Backtest engine simulates entry/exit correctly
- [ ] Strategy presets produce win rate / P&L / Sharpe stats
- [ ] BagsBacktestPanel shows results in UI
- [ ] Results persist in localStorage across sessions

**Estimated effort:** Large (2-3 sessions)

### Phase 6: Polish and Documentation

**Files to create/modify:**
- `src/components/bags/BagsTokenCard.tsx` -- Tooltip/popover for full score breakdown
- README or docs -- Document the /bags page, scoring algorithm
- `src/app/bags/page.tsx` -- Loading states, empty states, error handling

**Acceptance:**
- [ ] Loading skeletons show while data fetches
- [ ] Error boundary catches component failures gracefully
- [ ] Empty state shows clear message when no graduations found
- [ ] Score breakdown is accessible via hover/click on any dimension
- [ ] Mobile responsive (stacks to single column on small screens)

**Estimated effort:** Small (1 session)

---

## Risks and Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Bags.fm API changes/breaks | High | Medium | Fallback to DexScreener-only scoring (lose creator/bonding data) |
| Creator profile data unavailable | Medium | Medium | Degrade gracefully -- score creator dimension as "unknown" (50/100) |
| Historical graduation data sparse | High | Low | Use DexScreener token-boosts as fallback for historical discovery |
| Scoring algorithm too aggressive/conservative | Medium | High | Calibrate against known good/bad tokens; expose weights as config |
| Bags.fm API rate limiting | Medium | Medium | Server-side caching (10s TTL), batch requests, respect rate headers |
| Radar chart SVG rendering perf | Low | Low | Keep to 6 axes, no animation on initial load, memo components |
| Two Zustand stores confusing | Low | Low | Clear naming (useSniperStore vs useBagsStore), separate localStorage keys |

---

## Open Questions

- [ ] **Historical data depth:** How far back does the bags.fm API serve graduation history? Need to test pagination.
- [ ] **Creator wallet lookup:** Does bags.fm expose creator wallet addresses? If not, we may need Helius/Solscan for wallet age.
- [ ] **Grok AI integration timing:** Should Phase 1 include Grok analysis on the server route, or defer to Phase 2? (Recommend: defer to Phase 2 to ship faster.)
- [ ] **Shared positions across pages:** If user has positions from both sniper and bags, should they see all positions on both pages, or only page-specific? (Recommend: page-specific, with a "View All" option.)
- [ ] **Purple vs green accent:** Confirm the purple (#8B5CF6) accent for bags page differentiates well from green sniper in both themes.

---

## Success Criteria

1. User can navigate to `/bags` and see a bags.fm-only token feed with YC-style scores
2. Each token card shows a 6-dimension radar chart with score breakdown
3. No liquidity metric is displayed (irrelevant for bags.fm locked liquidity)
4. Creator reputation is prominently shown (Twitter handle, followers, account age)
5. Manual and auto-snipe work correctly via existing bags-trading.ts infrastructure
6. Backtesting shows historical performance of bags strategies with real graduation data
7. The page feels like a separate product within the same terminal (purple accent, bags branding)
8. Risk management (SL/TP/trail/circuit breaker) protects capital independently from sniper page
9. StatusBar navigation allows seamless switching between Sniper and Bags pages
10. Assessment scoring matches or exceeds the Python bags_intel scorer in accuracy

---

## Strategy Default Comparison: Sniper vs Bags

| Parameter | Sniper Default | Bags Default | Rationale |
|-----------|---------------|--------------|-----------|
| Stop Loss % | 20% | 30% | Bags tokens more volatile post-graduation |
| Take Profit % | 80% | 150% | Bags survivors often 5-10x |
| Trailing Stop % | 8% | 15% | Wider trail for bags volatility |
| Max Position SOL | 0.1 | 0.05 | Smaller sizing due to higher risk |
| Max Concurrent | 10 | 5 | Fewer but more researched bets |
| Min Score | 0 | 55 | Quality gate is THE filter for bags |
| Max Age Hours | 200 | 168 (7d) | Focus on recent graduations |
| Auto Snipe | Off | Off | Always manual by default |
| Circuit Breaker | 3 losses | 2 losses | Tighter breaker for bags |

---

## CSS Additions (globals.css)

```css
/* Bags.fm purple accent (used on /bags page) */
:root {
  --accent-bags: #8B5CF6;
  --accent-bags-glow: rgba(139, 92, 246, 0.5);
}

[data-theme="light"] {
  --accent-bags: #7C3AED;
  --accent-bags-glow: rgba(124, 58, 237, 0.15);
}
```

---

## File Count Summary

| Category | New Files | Modified Files |
|----------|-----------|----------------|
| Pages | 1 | 0 |
| Components | 9 | 1 (StatusBar) |
| Stores | 1 | 0 |
| Hooks | 3 | 0 |
| Lib/Utils | 4 | 1 (bags-api extend) |
| API Routes | 3 | 0 |
| Styles | 0 | 1 (globals.css) |
| **Total** | **21** | **3** |
