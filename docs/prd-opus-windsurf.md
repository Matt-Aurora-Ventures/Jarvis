# Autonomous Cross-Chain AI Portfolio Manager — Implementation PRD

**Target Builder:** Claude Opus 4.6 in Windsurf IDE
**Build Timeline:** 2 days
**Seed Capital:** $200
**Chain:** Base (EVM) → Solana via Circle CCTP
**Codebase:** Jarvis v4.6.6 at `C:\Users\lucid\Desktop\Jarvis`

---

## Table of Contents

1. [System Architecture Overview](#1-system-architecture-overview)
2. [Multi-Agent Orchestration](#2-multi-agent-orchestration)
3. [Alvara ERC-7621 Integration on Base](#3-alvara-erc-7621-integration-on-base)
4. [Cross-Chain Bridge (Circle CCTP)](#4-cross-chain-bridge-circle-cctp)
5. [Solana Staking Pool (Anchor)](#5-solana-staking-pool-anchor)
6. [Dashboard UI](#6-dashboard-ui)
7. [API Endpoints](#7-api-endpoints)
8. [Circuit Breakers & Safety](#8-circuit-breakers--safety)
9. [Infrastructure & Deployment](#9-infrastructure--deployment)
10. [File Structure](#10-file-structure)
11. [Implementation Order](#11-implementation-order)
12. [Acceptance Criteria](#12-acceptance-criteria)

---

## 1. System Architecture Overview

### 1.1 Component Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                         KVM2 VPS (Docker)                           │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │              AGENT ORCHESTRATION LAYER                        │  │
│  │                                                               │  │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐           │  │
│  │  │  Grok   │ │ Claude  │ │ ChatGPT │ │ Dexter  │  Analysts │  │
│  │  │(Sentim.)│ │ (Risk)  │ │ (Macro) │ │(Fundam.)│           │  │
│  │  └────┬────┘ └────┬────┘ └────┬────┘ └────┬────┘           │  │
│  │       └──────┬─────┴──────────┴────────────┘                │  │
│  │              ▼                                               │  │
│  │  ┌──────────────────────┐                                   │  │
│  │  │  Bull/Bear Debate    │ max 3 rounds                      │  │
│  │  └──────────┬───────────┘                                   │  │
│  │             ▼                                                │  │
│  │  ┌──────────────────────┐                                   │  │
│  │  │  Risk Officer (Claude)│ CAN VETO                         │  │
│  │  └──────────┬───────────┘                                   │  │
│  │             ▼                                                │  │
│  │  ┌──────────────────────┐                                   │  │
│  │  │  Trader (Grok)       │ final allocation                  │  │
│  │  └──────────┬───────────┘                                   │  │
│  │             ▼                                                │  │
│  │  ┌──────────────────────┐                                   │  │
│  │  │  Reflection (24-72h) │ updates calibration               │  │
│  │  └──────────────────────┘                                   │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                           │                                         │
│                           ▼                                         │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │              BASE (EVM) LAYER                                 │  │
│  │                                                               │  │
│  │  Alvara ERC-7621 Basket ──rebalance()──► LEL/1inch swaps    │  │
│  │  Management Fee: 1% annualized                               │  │
│  │  Fee collection ──► USDC conversion                          │  │
│  └──────────────┬───────────────────────────────────────────────┘  │
│                 │                                                    │
│                 ▼                                                    │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │              CCTP BRIDGE LAYER                                │  │
│  │                                                               │  │
│  │  State Machine:                                               │  │
│  │  FEE_COLLECTED → USDC_READY → BURN_SUBMITTED →               │  │
│  │  BURN_CONFIRMED → ATTESTATION_RECEIVED →                      │  │
│  │  MINT_SUBMITTED → MINT_CONFIRMED → DEPOSITED_TO_POOL         │  │
│  └──────────────┬───────────────────────────────────────────────┘  │
│                 │                                                    │
│                 ▼                                                    │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │              SOLANA LAYER                                     │  │
│  │                                                               │  │
│  │  USDC arrives → cranker calls deposit_rewards()               │  │
│  │  $KR8TIV stakers → claim_rewards()                           │  │
│  │  3-tier lockup: 1x / 1.25x (30d) / 1.5x (90d)              │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  PostgreSQL + TimescaleDB + Redis                             │  │
│  │  FastAPI Backend + React/Vite/Tailwind Frontend               │  │
│  └──────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

### 1.2 Data Flow Summary

1. **Daily cycle + event triggers**: Agent pipeline analyzes market → produces REBALANCE/HOLD/EXIT decision
2. **Execution**: Rebalance ERC-7621 basket on Base via Alvara contracts
3. **Fee collection**: 1% annualized management fee accrued and collected
4. **Bridge**: Management fees converted to USDC, burned via CCTP on Base, minted on Solana
5. **Distribution**: Cranker deposits USDC into staking pool, stakers claim proportionally
6. **Dashboard**: All state visible in real-time via Jarvis UI tab

### 1.3 Shared Infrastructure (Already Exists in Jarvis)

- **PostgreSQL**: New tables prefixed `inv_`
- **TimescaleDB**: New hypertables for NAV time-series
- **Redis**: New key namespace `inv:` for real-time cache
- **FastAPI**: New route group `/api/investments/`
- **Telegram bot**: New command handlers
- **LLM providers**: xAI, Anthropic, OpenAI keys already configured
- **Price feeds**: BirdEye, DexScreener already integrated

---

## 2. Multi-Agent Orchestration

### 2.1 Agent Pipeline Architecture

The pipeline runs as a directed acyclic graph, NOT a flat voting system.

```
LAYER 1: ANALYSTS (parallel, independent)
├── Grok (xAI) → Sentiment report via x_search
├── Claude (Anthropic) → Risk/on-chain analysis report
├── ChatGPT (OpenAI) → Macro/technical analysis report
└── Dexter (local) → Fundamental data QA report

LAYER 2: ADVERSARIAL RESEARCHERS (sequential, max 3 rounds)
├── Bull Researcher (Claude instance) → Best case for rebalancing
└── Bear Researcher (ChatGPT instance) → Best case for holding

LAYER 3: RISK OFFICER (Claude, separate instance)
└── Can VETO any trade exceeding risk thresholds → forces HOLD

LAYER 4: TRADER (Grok)
└── Final allocation decision within allowed action space

LAYER 5: REFLECTION (runs 24-72h post-trade, async)
└── Updates calibration hints + decision log
```

### 2.2 Analyst Layer Specifications

#### 2.2.1 Grok Sentiment Analyst

**Model:** `grok-4-1-fast` (non-reasoning for filtering) + `grok-4-1-fast-reasoning` (for scoring)
**API:** `https://api.x.ai/v1/responses` with `x_search` tool enabled
**Cost:** ~$0.50-1.00/day for sentiment queries

```python
# services/investments/agents/grok_agent.py

from typing import TypedDict, List
import httpx

class SentimentReport(TypedDict):
    token: str
    sentiment_score: float  # -1.0 to 1.0
    volume_24h: int
    notable_mentions: List[str]
    trend: str  # "DECLINING" | "STABLE" | "RISING"
    confidence: float  # 0.0 to 1.0

class GrokSentimentAnalyst:
    """Produces sentiment reports for each basket token using Grok's x_search."""
    
    def __init__(self, api_key: str, base_url: str = "https://api.x.ai/v1"):
        self.api_key = api_key
        self.base_url = base_url
        self.client = httpx.AsyncClient(
            base_url=base_url,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=60.0,
        )
    
    async def analyze_token(self, token_symbol: str, token_name: str) -> SentimentReport:
        """Query Grok x_search for token sentiment over last 24h."""
        response = await self.client.post("/responses", json={
            "model": "grok-4-1-fast-reasoning",
            "tools": [{"type": "x_search", "x_search": {
                "from_date": self._24h_ago_iso(),
            }}],
            "input": (
                f"Analyze the current sentiment for {token_name} ({token_symbol}) "
                f"on X/Twitter over the last 24 hours. Focus on: "
                f"1) Overall sentiment direction and strength "
                f"2) Notable mentions from high-influence accounts "
                f"3) Volume of discussion "
                f"4) Any significant narrative shifts or events "
                f"Return your analysis as structured data."
            ),
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "sentiment_report",
                    "strict": True,
                    "schema": {
                        "type": "object",
                        "properties": {
                            "sentiment_score": {"type": "number"},
                            "volume_24h": {"type": "integer"},
                            "notable_mentions": {"type": "array", "items": {"type": "string"}},
                            "trend": {"type": "string", "enum": ["DECLINING", "STABLE", "RISING"]},
                            "confidence": {"type": "number"},
                        },
                        "required": ["sentiment_score", "volume_24h", "notable_mentions", "trend", "confidence"],
                        "additionalProperties": False,
                    }
                }
            }
        })
        data = response.json()
        parsed = self._extract_json(data)
        return SentimentReport(token=token_symbol, **parsed)
    
    async def analyze_basket(self, tokens: list[dict]) -> list[SentimentReport]:
        """Analyze sentiment for all basket tokens in parallel."""
        import asyncio
        tasks = [self.analyze_token(t["symbol"], t["name"]) for t in tokens]
        return await asyncio.gather(*tasks, return_exceptions=True)
    
    def _24h_ago_iso(self) -> str:
        from datetime import datetime, timedelta, timezone
        return (datetime.now(timezone.utc) - timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M:%SZ")
    
    def _extract_json(self, response_data: dict) -> dict:
        import json
        for item in response_data.get("output", []):
            if item.get("type") == "message":
                for content in item.get("content", []):
                    if content.get("type") == "output_text":
                        return json.loads(content["text"])
        raise ValueError("No structured output found in Grok response")
```

#### 2.2.2 Claude Risk Analyst

**Model:** `claude-sonnet-4-20250514`
**API:** Anthropic Messages API

```python
# services/investments/agents/claude_agent.py

from typing import TypedDict, List
import anthropic

class RiskReport(TypedDict):
    portfolio_risk_score: float  # 0.0 (safe) to 1.0 (dangerous)
    concentration_risk: str
    correlation_risk: str
    drawdown_risk: str
    liquidity_risk: str
    recommended_max_position_pct: float
    risk_flags: List[str]
    reasoning: str

class ClaudeRiskAnalyst:
    """Produces risk analysis reports for the current portfolio state."""
    
    def __init__(self, api_key: str):
        self.client = anthropic.AsyncAnthropic(api_key=api_key)
    
    async def analyze(
        self,
        basket_state: dict,
        market_data: dict,
        calibration_hints: str,
    ) -> RiskReport:
        """Generate risk analysis for current basket state."""
        prompt = f"""You are a risk analyst for an AI-managed crypto portfolio on Base.

CURRENT BASKET STATE:
{self._format_basket(basket_state)}

MARKET DATA (24h):
{self._format_market(market_data)}

CALIBRATION HINTS FROM PAST PERFORMANCE:
{calibration_hints}

Analyze the portfolio for:
1. Concentration risk (no single token should exceed 30% weight)
2. Correlation risk (tokens moving together reduce diversification)
3. Drawdown risk (probability of >10% portfolio loss in next 24h)
4. Liquidity risk (can we exit positions within 1% slippage on Base DEXs)

Output strict JSON matching the RiskReport schema."""

        response = await self.client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}],
        )
        import json
        return json.loads(response.content[0].text)
    
    def _format_basket(self, state: dict) -> str:
        lines = []
        for token in state.get("tokens", []):
            lines.append(f"  {token['symbol']}: {token['weight']*100:.1f}% | ${token['value_usd']:.2f} | 24h: {token['change_24h']:+.1f}%")
        return "\n".join(lines)
    
    def _format_market(self, data: dict) -> str:
        return f"  BTC: {data.get('btc_change_24h', 'N/A')}% | ETH: {data.get('eth_change_24h', 'N/A')}% | Fear/Greed: {data.get('fear_greed', 'N/A')}"
```

#### 2.2.3 ChatGPT Macro Analyst

**Model:** `gpt-4o`
**API:** OpenAI Chat Completions

```python
# services/investments/agents/chatgpt_agent.py

from typing import TypedDict, List
from openai import AsyncOpenAI

class MacroReport(TypedDict):
    market_regime: str  # "RISK_ON" | "RISK_OFF" | "TRANSITIONING" | "UNCERTAIN"
    key_macro_factors: List[str]
    technical_signals: dict  # per-token technical indicators
    recommended_sector_weights: dict  # e.g. {"defi": 0.3, "l1": 0.4, "meme": 0.1}
    reasoning: str
    confidence: float

class ChatGPTMacroAnalyst:
    """Produces macro/technical analysis reports."""
    
    def __init__(self, api_key: str):
        self.client = AsyncOpenAI(api_key=api_key)
    
    async def analyze(
        self,
        basket_state: dict,
        market_data: dict,
        calibration_hints: str,
    ) -> MacroReport:
        prompt = f"""You are a macro and technical analyst for an AI-managed crypto portfolio.

BASKET STATE:
{basket_state}

MARKET DATA:
{market_data}

CALIBRATION FROM PAST:
{calibration_hints}

Provide:
1. Current market regime assessment
2. Key macro factors affecting crypto (rates, regulatory, flows)
3. Technical signals for each basket token (RSI, MACD direction, support/resistance)
4. Recommended sector weight adjustments

Output strict JSON matching MacroReport schema."""

        response = await self.client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            max_tokens=2000,
        )
        import json
        return json.loads(response.choices[0].message.content)
```

#### 2.2.4 Dexter Fundamental Analyst

**Model:** Local pipeline (LangChain-based)

```python
# services/investments/agents/dexter_agent.py

from typing import TypedDict, List

class FundamentalReport(TypedDict):
    token_fundamentals: dict  # per-token: TVL, volume, holders, dev activity
    data_quality_score: float  # 0-1, self-validated
    anomalies_detected: List[str]
    validation_notes: str

class DexterFundamentalAnalyst:
    """Self-validating fundamental data QA pipeline.
    
    Uses Plan → Act → Validate → Answer loop:
    1. Plan: determine what data points to gather
    2. Act: fetch from BirdEye, DexScreener, on-chain
    3. Validate: cross-reference sources, flag discrepancies
    4. Answer: produce validated fundamental report
    """
    
    def __init__(self, birdeye_key: str, dexscreener_base: str = "https://api.dexscreener.com"):
        self.birdeye_key = birdeye_key
        self.dexscreener_base = dexscreener_base
    
    async def analyze(self, basket_tokens: list[dict]) -> FundamentalReport:
        import httpx
        fundamentals = {}
        anomalies = []
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            for token in basket_tokens:
                addr = token["address"]
                symbol = token["symbol"]
                
                # Fetch from multiple sources for cross-validation
                birdeye_data = await self._fetch_birdeye(client, addr)
                dexscreener_data = await self._fetch_dexscreener(client, addr)
                
                # Cross-validate: volume should be within 20% across sources
                be_vol = birdeye_data.get("volume_24h", 0)
                ds_vol = dexscreener_data.get("volume_24h", 0)
                if be_vol > 0 and ds_vol > 0:
                    vol_diff = abs(be_vol - ds_vol) / max(be_vol, ds_vol)
                    if vol_diff > 0.2:
                        anomalies.append(f"{symbol}: volume discrepancy {vol_diff:.0%} between BirdEye and DexScreener")
                
                fundamentals[symbol] = {
                    "volume_24h": (be_vol + ds_vol) / 2,
                    "liquidity_usd": birdeye_data.get("liquidity", 0),
                    "holders": birdeye_data.get("holders", 0),
                    "price_change_24h": dexscreener_data.get("priceChange_24h", 0),
                }
        
        quality = 1.0 - (len(anomalies) * 0.15)  # degrade quality per anomaly
        return FundamentalReport(
            token_fundamentals=fundamentals,
            data_quality_score=max(0.0, quality),
            anomalies_detected=anomalies,
            validation_notes=f"Cross-validated {len(basket_tokens)} tokens across 2 sources",
        )
    
    async def _fetch_birdeye(self, client, address: str) -> dict:
        try:
            resp = await client.get(
                f"https://public-api.birdeye.so/defi/token_overview",
                params={"address": address},
                headers={"X-API-KEY": self.birdeye_key},
            )
            return resp.json().get("data", {})
        except Exception:
            return {}
    
    async def _fetch_dexscreener(self, client, address: str) -> dict:
        try:
            resp = await client.get(f"{self.dexscreener_base}/latest/dex/tokens/{address}")
            pairs = resp.json().get("pairs", [])
            return pairs[0] if pairs else {}
        except Exception:
            return {}
```

### 2.3 Bull/Bear Adversarial Debate

```python
# services/investments/consensus/debate.py

from typing import TypedDict, List
import anthropic
from openai import AsyncOpenAI

class DebateThesis(TypedDict):
    position: str  # "BULL" or "BEAR"
    thesis: str
    evidence: List[str]
    proposed_action: str  # "REBALANCE" or "HOLD"
    proposed_weights: dict  # token -> weight (only for REBALANCE)
    confidence: float
    what_would_change_my_mind: str

class DebateRound(TypedDict):
    round_number: int
    bull_thesis: DebateThesis
    bear_thesis: DebateThesis
    positions_changed: bool

class AdversarialDebate:
    """Bull/Bear adversarial researchers with max 3 debate rounds.
    
    Rules:
    - Bull MUST argue for the strongest case to rebalance
    - Bear MUST argue for the strongest case to hold/stay conservative
    - Position changes require NEW evidence (anti-sycophancy)
    - After 3 rounds, output both final theses for the Trader
    """
    
    MAX_ROUNDS = 3
    
    def __init__(self, anthropic_key: str, openai_key: str):
        self.bull_client = anthropic.AsyncAnthropic(api_key=anthropic_key)  # Claude as Bull
        self.bear_client = AsyncOpenAI(api_key=openai_key)  # ChatGPT as Bear
    
    async def run_debate(
        self,
        analyst_reports: dict,
        current_basket: dict,
        calibration_hints: str,
    ) -> list[DebateRound]:
        """Run up to 3 rounds of structured bull/bear debate."""
        rounds: list[DebateRound] = []
        bull_history = ""
        bear_history = ""
        
        for round_num in range(1, self.MAX_ROUNDS + 1):
            bull = await self._get_bull_thesis(analyst_reports, current_basket, calibration_hints, bear_history, round_num)
            bear = await self._get_bear_thesis(analyst_reports, current_basket, calibration_hints, bull_history, round_num)
            
            round_result = DebateRound(
                round_number=round_num,
                bull_thesis=bull,
                bear_thesis=bear,
                positions_changed=False,  # track if either side changed position
            )
            rounds.append(round_result)
            
            # Update debate history for next round
            bull_history += f"\n--- Round {round_num} Bull ---\n{bull['thesis']}\nEvidence: {bull['evidence']}"
            bear_history += f"\n--- Round {round_num} Bear ---\n{bear['thesis']}\nEvidence: {bear['evidence']}"
            
            # Early exit if confidence spread is narrow (consensus reached)
            if abs(bull["confidence"] - bear["confidence"]) < 0.15:
                break
        
        return rounds
    
    async def _get_bull_thesis(self, reports, basket, hints, opponent_history, round_num) -> DebateThesis:
        prompt = f"""You are the BULL researcher. Your job: make the STRONGEST possible case for rebalancing the portfolio.

ANALYST REPORTS: {reports}
CURRENT BASKET: {basket}
PAST CALIBRATION: {hints}
BEAR'S ARGUMENTS SO FAR: {opponent_history}

Round {round_num} of {self.MAX_ROUNDS}.
{"You MUST cite NEW evidence not already presented to change your position." if round_num > 1 else ""}

Output JSON: {{"position":"BULL","thesis":"...","evidence":["..."],"proposed_action":"REBALANCE","proposed_weights":{{}},"confidence":0.0-1.0,"what_would_change_my_mind":"..."}}"""

        response = await self.bull_client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1500,
            messages=[{"role": "user", "content": prompt}],
        )
        import json
        return json.loads(response.content[0].text)
    
    async def _get_bear_thesis(self, reports, basket, hints, opponent_history, round_num) -> DebateThesis:
        prompt = f"""You are the BEAR researcher. Your job: make the STRONGEST possible case for holding/staying conservative.

ANALYST REPORTS: {reports}
CURRENT BASKET: {basket}
PAST CALIBRATION: {hints}
BULL'S ARGUMENTS SO FAR: {opponent_history}

Round {round_num} of {self.MAX_ROUNDS}.
{"You MUST cite NEW evidence not already presented to change your position." if round_num > 1 else ""}

Output JSON: {{"position":"BEAR","thesis":"...","evidence":["..."],"proposed_action":"HOLD","proposed_weights":{{}},"confidence":0.0-1.0,"what_would_change_my_mind":"..."}}"""

        response = await self.bear_client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            max_tokens=1500,
        )
        import json
        return json.loads(response.choices[0].message.content)
```

### 2.4 Risk Officer (Veto Power)

```python
# services/investments/consensus/risk_officer.py

from typing import TypedDict, List
import anthropic

class RiskVeto(TypedDict):
    approved: bool
    veto_reason: str  # empty if approved
    risk_violations: List[str]
    adjusted_weights: dict  # risk-adjusted weights if partially approved
    max_allowed_change_pct: float

class RiskOfficer:
    """Claude-based risk officer with VETO power.
    
    Can block ANY trade that violates:
    - Max single-token weight: 30%
    - Max single-rebalance change: 25% of basket value
    - Max daily cumulative change: 40% of basket value
    - Correlation threshold: no more than 60% of basket in correlated assets
    - Min liquidity: every token must have >$50k liquidity on Base DEXs
    """
    
    HARD_LIMITS = {
        "max_single_token_pct": 0.30,
        "max_rebalance_change_pct": 0.25,
        "max_daily_cumulative_pct": 0.40,
        "max_correlated_exposure_pct": 0.60,
        "min_token_liquidity_usd": 50_000,
    }
    
    def __init__(self, api_key: str):
        self.client = anthropic.AsyncAnthropic(api_key=api_key)
    
    async def evaluate(
        self,
        proposed_action: str,
        proposed_weights: dict,
        current_weights: dict,
        basket_nav_usd: float,
        token_liquidities: dict,
        risk_report: dict,
        daily_changes_so_far_pct: float,
    ) -> RiskVeto:
        """Evaluate proposed trade against hard limits + LLM risk reasoning."""
        violations = []
        
        # Hard limit checks (no LLM needed)
        for token, weight in proposed_weights.items():
            if weight > self.HARD_LIMITS["max_single_token_pct"]:
                violations.append(f"{token} weight {weight:.0%} exceeds {self.HARD_LIMITS['max_single_token_pct']:.0%} max")
        
        total_change = sum(
            abs(proposed_weights.get(t, 0) - current_weights.get(t, 0))
            for t in set(list(proposed_weights.keys()) + list(current_weights.keys()))
        ) / 2  # divide by 2 because changes sum to ~2x
        
        if total_change > self.HARD_LIMITS["max_rebalance_change_pct"]:
            violations.append(f"Total change {total_change:.0%} exceeds {self.HARD_LIMITS['max_rebalance_change_pct']:.0%} max per rebalance")
        
        if daily_changes_so_far_pct + total_change > self.HARD_LIMITS["max_daily_cumulative_pct"]:
            violations.append(f"Cumulative daily change would exceed {self.HARD_LIMITS['max_daily_cumulative_pct']:.0%}")
        
        for token, weight in proposed_weights.items():
            if weight > 0.01:  # only check tokens with meaningful weight
                liq = token_liquidities.get(token, 0)
                if liq < self.HARD_LIMITS["min_token_liquidity_usd"]:
                    violations.append(f"{token} liquidity ${liq:,.0f} below ${self.HARD_LIMITS['min_token_liquidity_usd']:,.0f} minimum")
        
        if violations:
            return RiskVeto(
                approved=False,
                veto_reason=f"Hard limit violations: {'; '.join(violations)}",
                risk_violations=violations,
                adjusted_weights={},
                max_allowed_change_pct=self.HARD_LIMITS["max_rebalance_change_pct"],
            )
        
        # If hard limits pass, use Claude for soft risk assessment
        if proposed_action == "HOLD":
            return RiskVeto(approved=True, veto_reason="", risk_violations=[], adjusted_weights=proposed_weights, max_allowed_change_pct=total_change)
        
        # LLM risk assessment for edge cases
        response = await self.client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1000,
            messages=[{"role": "user", "content": f"""As risk officer, evaluate this proposed rebalance:

PROPOSED: {proposed_weights}
CURRENT: {current_weights}
NAV: ${basket_nav_usd:.2f}
RISK REPORT: {risk_report}

Hard limits already passed. Evaluate for soft risks:
- Sector concentration
- Momentum chasing
- Rebalancing too frequently for the basket size

Output JSON: {{"approved": bool, "veto_reason": "...", "risk_violations": [], "adjusted_weights": {{}}, "max_allowed_change_pct": float}}"""}],
        )
        import json
        return json.loads(response.content[0].text)
```

### 2.5 Trader (Final Decision)

```python
# services/investments/consensus/trader.py

from typing import TypedDict, List

class TradeDecision(TypedDict):
    action: str  # "REBALANCE" | "HOLD" | "EMERGENCY_EXIT"
    final_weights: dict  # token -> weight
    reasoning: str
    confidence: float
    estimated_gas_cost_usd: float
    estimated_slippage_pct: float

class TraderAgent:
    """Grok-based trader that makes the FINAL allocation decision.
    
    Receives: bull thesis, bear thesis, risk assessment, analyst reports, memory.
    Outputs: final trade decision within allowed action space.
    """
    
    def __init__(self, api_key: str):
        import httpx
        self.client = httpx.AsyncClient(
            base_url="https://api.x.ai/v1",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=60.0,
        )
    
    async def decide(
        self,
        bull_thesis: dict,
        bear_thesis: dict,
        risk_assessment: dict,
        analyst_reports: dict,
        current_weights: dict,
        basket_nav_usd: float,
        calibration_hints: str,
        decision_history: list[dict],  # last 30 days
    ) -> TradeDecision:
        prompt = f"""You are the TRADER making the final portfolio allocation decision.

BULL CASE (confidence {bull_thesis.get('confidence', 0):.0%}):
{bull_thesis.get('thesis', '')}

BEAR CASE (confidence {bear_thesis.get('confidence', 0):.0%}):
{bear_thesis.get('thesis', '')}

RISK OFFICER ASSESSMENT:
Approved: {risk_assessment.get('approved', False)}
Violations: {risk_assessment.get('risk_violations', [])}
Max allowed change: {risk_assessment.get('max_allowed_change_pct', 0):.0%}

ANALYST REPORTS SUMMARY:
{self._summarize_reports(analyst_reports)}

CURRENT PORTFOLIO:
{current_weights}
NAV: ${basket_nav_usd:.2f}

CALIBRATION (from past decisions):
{calibration_hints}

RECENT DECISIONS (last 5):
{decision_history[-5:] if decision_history else 'No history yet'}

CONSTRAINTS:
- Risk officer has {"APPROVED" if risk_assessment.get('approved') else "VETOED"} this rebalance
- If vetoed, you MUST output HOLD
- Max single-rebalance change: 25% of basket value
- No single token > 30%
- Basket must include ALVA at >= 5% weight
- Consider gas costs (~$0.50-2 on Base) relative to basket size ${basket_nav_usd:.2f}

Make your decision. Output JSON: {{"action":"REBALANCE|HOLD|EMERGENCY_EXIT","final_weights":{{}},"reasoning":"...","confidence":0.0-1.0,"estimated_gas_cost_usd":float,"estimated_slippage_pct":float}}"""

        response = await self.client.post("/chat/completions", json={
            "model": "grok-4-1-fast-reasoning",
            "messages": [{"role": "user", "content": prompt}],
            "response_format": {"type": "json_object"},
            "max_tokens": 1500,
        })
        import json
        return json.loads(response.json()["choices"][0]["message"]["content"])
    
    def _summarize_reports(self, reports: dict) -> str:
        lines = []
        for agent, report in reports.items():
            if isinstance(report, dict):
                lines.append(f"  {agent}: confidence={report.get('confidence', 'N/A')}, key={report.get('reasoning', report.get('thesis', 'N/A'))[:100]}")
        return "\n".join(lines)
```

### 2.6 Reflection Layer

```python
# services/investments/consensus/reflection.py

from datetime import datetime, timedelta, timezone
from typing import Optional

class ReflectionEngine:
    """Runs 24-72h post-trade. Compares predictions to outcomes. Updates calibration."""
    
    def __init__(self, db_pool):
        self.db = db_pool
    
    async def run_reflection(self, decision_id: int) -> dict:
        """Reflect on a past decision by comparing prediction to outcome."""
        decision = await self._get_decision(decision_id)
        if not decision:
            return {"error": "Decision not found"}
        
        # Get market state at decision time and current
        decision_time = decision["created_at"]
        hours_elapsed = (datetime.now(timezone.utc) - decision_time).total_seconds() / 3600
        
        if hours_elapsed < 24:
            return {"status": "too_early", "hours_elapsed": hours_elapsed}
        
        # Compare predicted vs actual outcomes
        predicted_weights = decision["final_weights"]
        actual_nav_change = await self._get_nav_change_since(decision_time)
        token_performance = await self._get_token_performance_since(decision_time)
        
        # Calculate which agent was most accurate
        agent_scores = {}
        for agent_name in ["grok_sentiment", "claude_risk", "chatgpt_macro", "dexter_fundamental"]:
            report = decision.get(f"{agent_name}_report", {})
            agent_scores[agent_name] = self._score_prediction(report, token_performance)
        
        # Generate calibration hint
        calibration = self._generate_calibration(decision, actual_nav_change, agent_scores)
        
        # Store reflection
        await self._store_reflection(decision_id, {
            "hours_elapsed": hours_elapsed,
            "predicted_action": decision["action"],
            "nav_change_pct": actual_nav_change,
            "agent_accuracy_scores": agent_scores,
            "calibration_hint": calibration,
            "best_agent": max(agent_scores, key=agent_scores.get),
        })
        
        return {"status": "reflected", "calibration": calibration}
    
    def _score_prediction(self, report: dict, actual_performance: dict) -> float:
        """Score 0-1 how accurate an agent's predictions were."""
        if not report:
            return 0.5  # neutral if no report
        # Simple: did the agent's directional call match reality?
        predicted_trend = report.get("trend", report.get("market_regime", "UNCERTAIN"))
        actual_direction = "UP" if sum(actual_performance.values()) > 0 else "DOWN"
        
        bullish = predicted_trend in ["RISING", "RISK_ON", "BULL"]
        bearish = predicted_trend in ["DECLINING", "RISK_OFF", "BEAR"]
        
        if (bullish and actual_direction == "UP") or (bearish and actual_direction == "DOWN"):
            return 0.8 + report.get("confidence", 0.5) * 0.2
        elif not bullish and not bearish:
            return 0.5
        else:
            return 0.2
    
    def _generate_calibration(self, decision: dict, nav_change: float, scores: dict) -> str:
        best = max(scores, key=scores.get)
        worst = min(scores, key=scores.get)
        action = decision["action"]
        
        hint = f"Decision '{action}' resulted in {nav_change:+.1%} NAV change. "
        hint += f"Most accurate: {best} ({scores[best]:.0%}). "
        hint += f"Least accurate: {worst} ({scores[worst]:.0%}). "
        
        if action == "REBALANCE" and nav_change < -0.02:
            hint += "Rebalance was net negative — consider higher HOLD bias in similar conditions. "
        elif action == "HOLD" and nav_change > 0.05:
            hint += "Holding missed upside — consider lower HOLD bias in similar conditions. "
        
        return hint
    
    async def get_calibration_hints(self, limit: int = 10) -> str:
        """Get recent calibration hints to inject into agent prompts."""
        rows = await self.db.fetch(
            "SELECT calibration_hint FROM inv_reflections ORDER BY created_at DESC LIMIT $1",
            limit,
        )
        return "\n".join(r["calibration_hint"] for r in rows) if rows else "No calibration data yet."
    
    async def _get_decision(self, decision_id: int) -> Optional[dict]:
        return await self.db.fetchrow("SELECT * FROM inv_decisions WHERE id = $1", decision_id)
    
    async def _get_nav_change_since(self, since: datetime) -> float:
        row = await self.db.fetchrow(
            "SELECT nav_usd FROM inv_nav_snapshots WHERE ts >= $1 ORDER BY ts ASC LIMIT 1", since
        )
        current = await self.db.fetchrow(
            "SELECT nav_usd FROM inv_nav_snapshots ORDER BY ts DESC LIMIT 1"
        )
        if row and current:
            return (current["nav_usd"] - row["nav_usd"]) / row["nav_usd"]
        return 0.0
    
    async def _get_token_performance_since(self, since: datetime) -> dict:
        rows = await self.db.fetch("""
            SELECT symbol, 
                   (LAST(price_usd, ts) - FIRST(price_usd, ts)) / FIRST(price_usd, ts) as change_pct
            FROM inv_token_prices
            WHERE ts >= $1
            GROUP BY symbol
        """, since)
        return {r["symbol"]: r["change_pct"] for r in rows}
    
    async def _store_reflection(self, decision_id: int, data: dict):
        import json
        await self.db.execute("""
            INSERT INTO inv_reflections (decision_id, data, calibration_hint, created_at)
            VALUES ($1, $2, $3, NOW())
        """, decision_id, json.dumps(data), data["calibration_hint"])
```

### 2.7 Memory Module — Database Tables

```sql
-- services/investments/migrations/001_agent_tables.sql

-- Decision log: every agent pipeline run
CREATE TABLE inv_decisions (
    id SERIAL PRIMARY KEY,
    basket_id VARCHAR(64) NOT NULL DEFAULT 'alpha',
    trigger_type VARCHAR(32) NOT NULL,  -- 'scheduled', 'event_nav_drop', 'event_sentiment_shift'
    action VARCHAR(32) NOT NULL,  -- 'REBALANCE', 'HOLD', 'EMERGENCY_EXIT'
    final_weights JSONB NOT NULL,
    previous_weights JSONB NOT NULL,
    basket_nav_usd NUMERIC(18, 2) NOT NULL,
    
    -- Individual agent reports (stored for audit + reflection)
    grok_sentiment_report JSONB,
    claude_risk_report JSONB,
    chatgpt_macro_report JSONB,
    dexter_fundamental_report JSONB,
    
    -- Debate
    bull_thesis JSONB,
    bear_thesis JSONB,
    debate_rounds INTEGER DEFAULT 0,
    
    -- Risk officer
    risk_approved BOOLEAN NOT NULL,
    risk_veto_reason TEXT,
    
    -- Trader
    trader_confidence NUMERIC(4, 3),
    trader_reasoning TEXT,
    
    -- Execution
    tx_hash VARCHAR(128),
    gas_cost_usd NUMERIC(10, 4),
    execution_status VARCHAR(32) DEFAULT 'pending',  -- 'pending', 'submitted', 'confirmed', 'failed'
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_inv_decisions_basket ON inv_decisions(basket_id, created_at DESC);

-- Reflection outcomes
CREATE TABLE inv_reflections (
    id SERIAL PRIMARY KEY,
    decision_id INTEGER REFERENCES inv_decisions(id),
    data JSONB NOT NULL,
    calibration_hint TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Strategy library: patterns that worked/failed
CREATE TABLE inv_strategies (
    id SERIAL PRIMARY KEY,
    name VARCHAR(128) NOT NULL,
    conditions JSONB NOT NULL,  -- e.g. {"market_regime": "RISK_OFF", "sentiment_trend": "DECLINING"}
    recommended_action VARCHAR(32) NOT NULL,
    success_rate NUMERIC(4, 3),
    sample_size INTEGER DEFAULT 0,
    notes TEXT,
    active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Calibration hints cache (injected into prompts)
CREATE TABLE inv_calibration_hints (
    id SERIAL PRIMARY KEY,
    agent_name VARCHAR(64) NOT NULL,
    hint TEXT NOT NULL,
    hint_type VARCHAR(32) NOT NULL,  -- 'accuracy', 'bias', 'timing'
    weight NUMERIC(4, 3) DEFAULT 1.0,
    expires_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

### 2.8 Master Orchestrator

```python
# services/investments/orchestrator.py

import asyncio
import logging
from datetime import datetime, timezone

from .agents.grok_agent import GrokSentimentAnalyst
from .agents.claude_agent import ClaudeRiskAnalyst
from .agents.chatgpt_agent import ChatGPTMacroAnalyst
from .agents.dexter_agent import DexterFundamentalAnalyst
from .consensus.debate import AdversarialDebate
from .consensus.risk_officer import RiskOfficer
from .consensus.trader import TraderAgent
from .consensus.reflection import ReflectionEngine
from .alvara_manager import AlvaraManager
from .config import InvestmentConfig

logger = logging.getLogger("investments.orchestrator")

class InvestmentOrchestrator:
    """Master orchestrator: runs the full agent pipeline and executes decisions."""
    
    def __init__(self, config: InvestmentConfig, db_pool, redis):
        self.config = config
        self.db = db_pool
        self.redis = redis
        
        # Agents
        self.grok = GrokSentimentAnalyst(config.xai_api_key)
        self.claude_risk = ClaudeRiskAnalyst(config.anthropic_api_key)
        self.chatgpt = ChatGPTMacroAnalyst(config.openai_api_key)
        self.dexter = DexterFundamentalAnalyst(config.birdeye_api_key)
        
        # Consensus layers
        self.debate = AdversarialDebate(config.anthropic_api_key, config.openai_api_key)
        self.risk_officer = RiskOfficer(config.anthropic_api_key)
        self.trader = TraderAgent(config.xai_api_key)
        self.reflection = ReflectionEngine(db_pool)
        
        # Execution
        self.alvara = AlvaraManager(config)
    
    async def run_cycle(self, trigger: str = "scheduled") -> dict:
        """Run a complete agent pipeline cycle.
        
        Args:
            trigger: 'scheduled', 'event_nav_drop', 'event_sentiment_shift'
        
        Returns:
            Decision record dict
        """
        # Check kill switch
        kill = await self.redis.get("inv:kill_switch")
        if kill and kill.decode() == "true":
            logger.warning("Kill switch active — skipping cycle")
            return {"action": "SKIPPED", "reason": "kill_switch"}
        
        logger.info(f"Starting investment cycle — trigger: {trigger}")
        
        # 1. Get current basket state
        basket_state = await self.alvara.get_basket_state()
        market_data = await self._get_market_data()
        calibration = await self.reflection.get_calibration_hints(limit=10)
        decision_history = await self._get_recent_decisions(limit=30)
        
        # 2. ANALYST LAYER — run all 4 in parallel
        sentiment_task = self.grok.analyze_basket(basket_state["tokens"])
        risk_task = self.claude_risk.analyze(basket_state, market_data, calibration)
        macro_task = self.chatgpt.analyze(basket_state, market_data, calibration)
        fundamental_task = self.dexter.analyze(basket_state["tokens"])
        
        results = await asyncio.gather(
            sentiment_task, risk_task, macro_task, fundamental_task,
            return_exceptions=True,
        )
        
        # Handle partial failures — if any analyst fails, continue with reduced confidence
        analyst_reports = {}
        failed_agents = []
        for name, result in zip(["grok_sentiment", "claude_risk", "chatgpt_macro", "dexter_fundamental"], results):
            if isinstance(result, Exception):
                logger.error(f"Agent {name} failed: {result}")
                failed_agents.append(name)
                analyst_reports[name] = {"error": str(result), "confidence": 0.0}
            else:
                analyst_reports[name] = result
        
        # If 2+ agents failed, default to HOLD
        if len(failed_agents) >= 2:
            logger.warning(f"Multiple agents failed ({failed_agents}), defaulting to HOLD")
            return await self._record_decision(
                trigger=trigger, action="HOLD", basket_state=basket_state,
                analyst_reports=analyst_reports,
                reason=f"Degraded mode: {len(failed_agents)} agents failed",
            )
        
        # 3. ADVERSARIAL DEBATE — Bull vs Bear
        debate_rounds = await self.debate.run_debate(analyst_reports, basket_state, calibration)
        final_bull = debate_rounds[-1]["bull_thesis"]
        final_bear = debate_rounds[-1]["bear_thesis"]
        
        # 4. RISK OFFICER — can VETO
        token_liquidities = {t["symbol"]: t.get("liquidity_usd", 0) for t in basket_state["tokens"]}
        daily_changes = await self._get_daily_cumulative_changes()
        
        risk_assessment = await self.risk_officer.evaluate(
            proposed_action=final_bull["proposed_action"],
            proposed_weights=final_bull.get("proposed_weights", {}),
            current_weights={t["symbol"]: t["weight"] for t in basket_state["tokens"]},
            basket_nav_usd=basket_state["nav_usd"],
            token_liquidities=token_liquidities,
            risk_report=analyst_reports.get("claude_risk", {}),
            daily_changes_so_far_pct=daily_changes,
        )
        
        # 5. TRADER — final decision
        trade_decision = await self.trader.decide(
            bull_thesis=final_bull,
            bear_thesis=final_bear,
            risk_assessment=risk_assessment,
            analyst_reports=analyst_reports,
            current_weights={t["symbol"]: t["weight"] for t in basket_state["tokens"]},
            basket_nav_usd=basket_state["nav_usd"],
            calibration_hints=calibration,
            decision_history=decision_history,
        )
        
        # 6. EXECUTE
        if trade_decision["action"] == "REBALANCE" and risk_assessment["approved"]:
            tx_hash = await self.alvara.execute_rebalance(trade_decision["final_weights"])
            trade_decision["tx_hash"] = tx_hash
        
        # 7. RECORD
        decision_record = await self._record_decision(
            trigger=trigger,
            action=trade_decision["action"],
            basket_state=basket_state,
            analyst_reports=analyst_reports,
            debate_rounds=debate_rounds,
            risk_assessment=risk_assessment,
            trade_decision=trade_decision,
        )
        
        # 8. SCHEDULE REFLECTION (24h later)
        await self._schedule_reflection(decision_record["id"])
        
        # 9. Notify via WebSocket + Telegram
        await self._broadcast_decision(decision_record)
        
        return decision_record
    
    async def _record_decision(self, **kwargs) -> dict:
        import json
        row = await self.db.fetchrow("""
            INSERT INTO inv_decisions (
                basket_id, trigger_type, action, final_weights, previous_weights,
                basket_nav_usd, grok_sentiment_report, claude_risk_report,
                chatgpt_macro_report, dexter_fundamental_report,
                bull_thesis, bear_thesis, debate_rounds,
                risk_approved, risk_veto_reason,
                trader_confidence, trader_reasoning,
                tx_hash, execution_status
            ) VALUES (
                'alpha', $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12,
                $13, $14, $15, $16, $17, $18
            ) RETURNING id, created_at
        """,
            kwargs.get("trigger", "scheduled"),
            kwargs.get("action", "HOLD"),
            json.dumps(kwargs.get("trade_decision", {}).get("final_weights", {})),
            json.dumps({t["symbol"]: t["weight"] for t in kwargs.get("basket_state", {}).get("tokens", [])}),
            kwargs.get("basket_state", {}).get("nav_usd", 0),
            json.dumps(kwargs.get("analyst_reports", {}).get("grok_sentiment", {})),
            json.dumps(kwargs.get("analyst_reports", {}).get("claude_risk", {})),
            json.dumps(kwargs.get("analyst_reports", {}).get("chatgpt_macro", {})),
            json.dumps(kwargs.get("analyst_reports", {}).get("dexter_fundamental", {})),
            json.dumps(kwargs.get("debate_rounds", [{}])[-1].get("bull_thesis", {}) if kwargs.get("debate_rounds") else {}),
            json.dumps(kwargs.get("debate_rounds", [{}])[-1].get("bear_thesis", {}) if kwargs.get("debate_rounds") else {}),
            len(kwargs.get("debate_rounds", [])),
            kwargs.get("risk_assessment", {}).get("approved", False),
            kwargs.get("risk_assessment", {}).get("veto_reason", ""),
            kwargs.get("trade_decision", {}).get("confidence", 0),
            kwargs.get("trade_decision", {}).get("reasoning", kwargs.get("reason", "")),
            kwargs.get("trade_decision", {}).get("tx_hash", None),
            "confirmed" if kwargs.get("trade_decision", {}).get("tx_hash") else "hold",
        )
        return {"id": row["id"], "created_at": row["created_at"], **kwargs}
    
    async def _get_market_data(self) -> dict:
        """Fetch general market data from existing Jarvis price feeds."""
        # Uses existing BirdEye/DexScreener integrations
        cached = await self.redis.get("inv:market_data")
        if cached:
            import json
            return json.loads(cached)
        return {"btc_change_24h": 0, "eth_change_24h": 0, "fear_greed": 50}
    
    async def _get_recent_decisions(self, limit: int = 30) -> list:
        rows = await self.db.fetch(
            "SELECT action, final_weights, trader_confidence, trader_reasoning, created_at "
            "FROM inv_decisions WHERE basket_id = 'alpha' ORDER BY created_at DESC LIMIT $1",
            limit,
        )
        return [dict(r) for r in rows]
    
    async def _get_daily_cumulative_changes(self) -> float:
        row = await self.db.fetchrow("""
            SELECT COALESCE(SUM(
                (SELECT SUM(ABS(value::float)) FROM jsonb_each_text(final_weights))
            ), 0) as total
            FROM inv_decisions
            WHERE created_at > NOW() - INTERVAL '24 hours'
            AND action = 'REBALANCE'
        """)
        return float(row["total"]) if row else 0.0
    
    async def _schedule_reflection(self, decision_id: int):
        """Schedule reflection to run 24h later via Redis delayed task."""
        await self.redis.set(
            f"inv:reflect:{decision_id}",
            str(decision_id),
            ex=86400,  # 24 hours
        )
    
    async def _broadcast_decision(self, decision: dict):
        import json
        await self.redis.publish("inv:decisions", json.dumps({
            "id": decision.get("id"),
            "action": decision.get("action"),
            "confidence": decision.get("trade_decision", {}).get("confidence", 0),
        }))
```

### 2.9 Scheduler (Daily + Event-Triggered)

```python
# services/investments/scheduler.py

import asyncio
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger("investments.scheduler")

class InvestmentScheduler:
    """Manages scheduled and event-triggered investment cycles."""
    
    def __init__(self, orchestrator, db_pool, redis):
        self.orchestrator = orchestrator
        self.db = db_pool
        self.redis = redis
        self.scheduler = AsyncIOScheduler()
    
    def start(self):
        # Daily scheduled review at 00:00 UTC
        self.scheduler.add_job(
            self._run_scheduled,
            CronTrigger(hour=0, minute=0, timezone="UTC"),
            id="daily_review",
            name="Daily Investment Review",
        )
        
        # Reflection runner: check every hour for pending reflections
        self.scheduler.add_job(
            self._run_pending_reflections,
            CronTrigger(minute=0, timezone="UTC"),
            id="reflection_check",
            name="Reflection Check",
        )
        
        # NAV monitor: check every 15 minutes for major drops
        self.scheduler.add_job(
            self._check_nav_drop,
            CronTrigger(minute="*/15", timezone="UTC"),
            id="nav_monitor",
            name="NAV Drop Monitor",
        )
        
        # Start event listener for sentiment shifts
        asyncio.create_task(self._listen_sentiment_events())
        
        self.scheduler.start()
        logger.info("Investment scheduler started")
    
    async def _run_scheduled(self):
        try:
            await self.orchestrator.run_cycle(trigger="scheduled")
        except Exception as e:
            logger.error(f"Scheduled cycle failed: {e}")
            await self._alert_telegram(f"⚠️ Scheduled investment cycle failed: {e}")
    
    async def _check_nav_drop(self):
        """Event trigger: >10% NAV drop in last 4 hours."""
        row = await self.db.fetchrow("""
            SELECT 
                FIRST(nav_usd, ts) as nav_4h_ago,
                LAST(nav_usd, ts) as nav_now
            FROM inv_nav_snapshots
            WHERE ts > NOW() - INTERVAL '4 hours'
        """)
        if row and row["nav_4h_ago"] and row["nav_4h_ago"] > 0:
            change = (row["nav_now"] - row["nav_4h_ago"]) / row["nav_4h_ago"]
            if change < -0.10:
                logger.warning(f"NAV dropped {change:.1%} in 4h — triggering event review")
                await self._alert_telegram(f"🚨 NAV dropped {change:.1%} in 4 hours! Triggering emergency review.")
                await self.orchestrator.run_cycle(trigger="event_nav_drop")
    
    async def _listen_sentiment_events(self):
        """Listen for major sentiment shift events from the sentiment pipeline."""
        pubsub = self.redis.pubsub()
        await pubsub.subscribe("inv:sentiment_shift")
        async for message in pubsub.listen():
            if message["type"] == "message":
                logger.info(f"Sentiment shift detected — triggering event review")
                await self.orchestrator.run_cycle(trigger="event_sentiment_shift")
    
    async def _run_pending_reflections(self):
        """Check for decisions that need reflection (24-72h old, unreflected)."""
        rows = await self.db.fetch("""
            SELECT d.id FROM inv_decisions d
            LEFT JOIN inv_reflections r ON r.decision_id = d.id
            WHERE r.id IS NULL
            AND d.created_at < NOW() - INTERVAL '24 hours'
            AND d.created_at > NOW() - INTERVAL '72 hours'
            AND d.action != 'HOLD'
            LIMIT 5
        """)
        for row in rows:
            await self.orchestrator.reflection.run_reflection(row["id"])
    
    async def _alert_telegram(self, message: str):
        """Send alert via existing Jarvis Telegram bot."""
        await self.redis.publish("telegram:alerts", message)
```

---

## 3. Alvara ERC-7621 Integration on Base

### 3.1 Contract Interfaces

```python
# services/investments/alvara_manager.py

import logging
from web3 import AsyncWeb3
from web3.middleware import ExtraDataToPOAMiddleware
from eth_account import Account

logger = logging.getLogger("investments.alvara")

# ERC-7621 ABI (relevant functions only)
BASKET_ABI = [
    {
        "name": "rebalance",
        "type": "function",
        "stateMutability": "nonpayable",
        "inputs": [
            {"name": "_newTokens", "type": "address[]"},
            {"name": "_newWeights", "type": "uint256[]"}
        ],
        "outputs": []
    },
    {
        "name": "contribute",
        "type": "function",
        "stateMutability": "payable",
        "inputs": [],
        "outputs": []
    },
    {
        "name": "withdraw",
        "type": "function",
        "stateMutability": "nonpayable",
        "inputs": [{"name": "_liquidity", "type": "uint256"}],
        "outputs": []
    },
    {
        "name": "withdrawETH",
        "type": "function",
        "stateMutability": "nonpayable",
        "inputs": [{"name": "_liquidity", "type": "uint256"}],
        "outputs": []
    },
    {
        "name": "getTokenDetails",
        "type": "function",
        "stateMutability": "view",
        "inputs": [{"name": "index", "type": "uint256"}],
        "outputs": [
            {"name": "token", "type": "address"},
            {"name": "weight", "type": "uint256"}
        ]
    },
    {
        "name": "totalTokens",
        "type": "function",
        "stateMutability": "view",
        "inputs": [],
        "outputs": [{"name": "", "type": "uint256"}]
    },
    {
        "name": "totalSupply",
        "type": "function",
        "stateMutability": "view",
        "inputs": [],
        "outputs": [{"name": "", "type": "uint256"}]
    },
]

# Events to monitor
BASKET_EVENTS = [
    "ContributedToBTS",
    "WithdrawnFromBTS",
    "RebalanceBTS",
]

# Base chain token addresses (verified)
BASE_TOKENS = {
    "WETH": "0x4200000000000000000000000000000000000006",
    "USDC": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
    "USDbC": "0xd9aAEc86B65D86f6A7B5B1b0c42FFA531710b6CA",
    "DAI": "0x50c5725949A6F0c72E6C4a641F24049A917DB0Cb",
    "cbETH": "0x2Ae3F1Ec7F1F5012CFEab0185bfc7aa3cf0DEc22",
    "AERO": "0x940181a94A35A4569E4529A3CDfB74e38FD98631",
    # ALVA address TBD — required 5% minimum in basket
}

# Base USDC address for fee conversion
BASE_USDC = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"

class AlvaraManager:
    """Manages the ERC-7621 basket on Base chain."""
    
    def __init__(self, config):
        self.config = config
        self.w3 = AsyncWeb3(AsyncWeb3.AsyncHTTPProvider(config.base_rpc_url))
        self.w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
        self.account = Account.from_key(config.management_wallet_key)
        self.basket_contract = self.w3.eth.contract(
            address=config.basket_address,
            abi=BASKET_ABI,
        )
        
        # Token symbol → address mapping for this basket
        self.token_map: dict[str, str] = {}
    
    async def get_basket_state(self) -> dict:
        """Get current basket composition, weights, and NAV."""
        total = await self.basket_contract.functions.totalTokens().call()
        tokens = []
        total_value_usd = 0
        
        for i in range(total):
            token_addr, weight = await self.basket_contract.functions.getTokenDetails(i).call()
            symbol = await self._get_token_symbol(token_addr)
            price = await self._get_token_price(token_addr)
            balance = await self._get_token_balance(token_addr)
            value = balance * price
            total_value_usd += value
            
            tokens.append({
                "address": token_addr,
                "symbol": symbol,
                "weight": weight / 10000,  # ERC-7621 weights are basis points
                "price_usd": price,
                "balance": balance,
                "value_usd": value,
                "change_24h": await self._get_24h_change(token_addr),
            })
        
        return {
            "basket_address": self.config.basket_address,
            "chain": "base",
            "tokens": tokens,
            "nav_usd": total_value_usd,
            "total_supply": await self.basket_contract.functions.totalSupply().call(),
            "timestamp": self._now_iso(),
        }
    
    async def execute_rebalance(self, new_weights: dict) -> str:
        """Execute a rebalance transaction on the basket.
        
        Args:
            new_weights: {"TOKEN_SYMBOL": 0.25, ...} — must sum to 1.0
        
        Returns:
            Transaction hash
        """
        # Validate weights
        total = sum(new_weights.values())
        if abs(total - 1.0) > 0.001:
            raise ValueError(f"Weights must sum to 1.0, got {total}")
        
        # Check ALVA minimum
        alva_weight = new_weights.get("ALVA", 0)
        if alva_weight < 0.05:
            raise ValueError(f"ALVA weight {alva_weight} below 5% minimum")
        
        # Convert to contract format
        token_addresses = []
        weight_bps = []
        for symbol, weight in new_weights.items():
            addr = self.token_map.get(symbol)
            if not addr:
                addr = await self._resolve_token_address(symbol)
            token_addresses.append(addr)
            weight_bps.append(int(weight * 10000))
        
        # Build transaction
        nonce = await self.w3.eth.get_transaction_count(self.account.address)
        gas_price = await self.w3.eth.gas_price
        
        tx = await self.basket_contract.functions.rebalance(
            token_addresses, weight_bps
        ).build_transaction({
            "from": self.account.address,
            "nonce": nonce,
            "gasPrice": gas_price,
            "chainId": 8453,  # Base mainnet
        })
        
        # Estimate gas
        gas_estimate = await self.w3.eth.estimate_gas(tx)
        tx["gas"] = int(gas_estimate * 1.2)  # 20% buffer
        
        # Sign and send
        signed = self.account.sign_transaction(tx)
        tx_hash = await self.w3.eth.send_raw_transaction(signed.raw_transaction)
        
        logger.info(f"Rebalance tx submitted: {tx_hash.hex()}")
        
        # Wait for confirmation
        receipt = await self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
        
        if receipt["status"] == 1:
            logger.info(f"Rebalance confirmed in block {receipt['blockNumber']}")
        else:
            logger.error(f"Rebalance FAILED: {receipt}")
            raise RuntimeError(f"Rebalance transaction failed: {tx_hash.hex()}")
        
        return tx_hash.hex()
    
    async def collect_management_fees(self) -> float:
        """Collect accrued 1% annualized management fees.
        
        Returns USDC amount collected.
        """
        # Fee calculation: 1% annualized = ~0.00274% per day
        # Accrued in the basket contract, collected during rebalance or explicitly
        # Implementation depends on specific Alvara fee mechanism
        # For now, calculate off-chain and swap proportional basket tokens to USDC
        
        basket = await self.get_basket_state()
        daily_fee_rate = 0.01 / 365  # 1% annualized
        fee_usd = basket["nav_usd"] * daily_fee_rate
        
        logger.info(f"Management fee: ${fee_usd:.4f} (daily from ${basket['nav_usd']:.2f} NAV)")
        return fee_usd
    
    async def _get_token_symbol(self, address: str) -> str:
        erc20_abi = [{"name": "symbol", "type": "function", "stateMutability": "view", "inputs": [], "outputs": [{"type": "string"}]}]
        contract = self.w3.eth.contract(address=address, abi=erc20_abi)
        return await contract.functions.symbol().call()
    
    async def _get_token_price(self, address: str) -> float:
        # Use existing Jarvis price feed (DexScreener/BirdEye)
        return 0.0  # Placeholder — connect to existing price feed
    
    async def _get_token_balance(self, address: str) -> float:
        erc20_abi = [{"name": "balanceOf", "type": "function", "stateMutability": "view", "inputs": [{"type": "address"}], "outputs": [{"type": "uint256"}]}]
        contract = self.w3.eth.contract(address=address, abi=erc20_abi)
        balance = await contract.functions.balanceOf(self.config.basket_address).call()
        return balance / 1e18  # Assumes 18 decimals — adjust per token
    
    async def _get_24h_change(self, address: str) -> float:
        return 0.0  # Placeholder — connect to existing price feed
    
    async def _resolve_token_address(self, symbol: str) -> str:
        addr = BASE_TOKENS.get(symbol)
        if not addr:
            raise ValueError(f"Unknown token symbol: {symbol}")
        self.token_map[symbol] = addr
        return addr
    
    def _now_iso(self) -> str:
        from datetime import datetime, timezone
        return datetime.now(timezone.utc).isoformat()
```

### 3.2 Event Monitor

```python
# services/investments/event_monitor.py

import asyncio
import logging
from web3 import AsyncWeb3

logger = logging.getLogger("investments.events")

class BasketEventMonitor:
    """Monitors ERC-7621 basket events on Base for dashboard updates."""
    
    def __init__(self, w3: AsyncWeb3, basket_address: str, db_pool, redis):
        self.w3 = w3
        self.basket_address = basket_address
        self.db = db_pool
        self.redis = redis
    
    async def start_monitoring(self):
        """Poll for new events every 12 seconds (Base block time)."""
        last_block = await self.w3.eth.block_number
        
        while True:
            try:
                current_block = await self.w3.eth.block_number
                if current_block > last_block:
                    logs = await self.w3.eth.get_logs({
                        "address": self.basket_address,
                        "fromBlock": last_block + 1,
                        "toBlock": current_block,
                    })
                    for log in logs:
                        await self._process_log(log)
                    last_block = current_block
            except Exception as e:
                logger.error(f"Event monitor error: {e}")
            
            await asyncio.sleep(12)
    
    async def _process_log(self, log):
        import json
        event_data = {
            "block": log["blockNumber"],
            "tx_hash": log["transactionHash"].hex(),
            "topics": [t.hex() for t in log["topics"]],
            "data": log["data"].hex(),
        }
        
        await self.db.execute(
            "INSERT INTO inv_basket_events (basket_address, block_number, tx_hash, event_data, created_at) "
            "VALUES ($1, $2, $3, $4, NOW())",
            self.basket_address, log["blockNumber"], log["transactionHash"].hex(), json.dumps(event_data),
        )
        
        await self.redis.publish("inv:basket_events", json.dumps(event_data))
```

---

## 4. Cross-Chain Bridge (Circle CCTP)

### 4.1 Bridge State Machine

**CRITICAL: This is NOT atomic. Build a proper state machine.**

```
States:
  FEE_COLLECTED        → Management fee collected in USDC on Base
  USDC_READY           → USDC approved for CCTP burn
  BURN_SUBMITTED       → Burn tx submitted on Base
  BURN_CONFIRMED       → Burn tx confirmed on Base
  ATTESTATION_PENDING  → Waiting for Circle attestation
  ATTESTATION_RECEIVED → Circle attestation received
  MINT_SUBMITTED       → Mint tx submitted on Solana
  MINT_CONFIRMED       → USDC minted on Solana
  DEPOSITED_TO_POOL    → USDC deposited to staking reward vault
  FAILED               → Any step failed — needs retry or manual intervention
  CANCELLED            → Cancelled (e.g., fee too high)
```

### 4.2 Bridge Controller

```python
# services/investments/bridge_controller.py

import asyncio
import logging
import httpx
from enum import Enum
from dataclasses import dataclass
from datetime import datetime, timezone
from web3 import AsyncWeb3
from solders.keypair import Keypair
from solders.pubkey import Pubkey
from solana.rpc.async_api import AsyncClient as SolanaClient

logger = logging.getLogger("investments.bridge")

class BridgeState(str, Enum):
    FEE_COLLECTED = "FEE_COLLECTED"
    USDC_READY = "USDC_READY"
    BURN_SUBMITTED = "BURN_SUBMITTED"
    BURN_CONFIRMED = "BURN_CONFIRMED"
    ATTESTATION_PENDING = "ATTESTATION_PENDING"
    ATTESTATION_RECEIVED = "ATTESTATION_RECEIVED"
    MINT_SUBMITTED = "MINT_SUBMITTED"
    MINT_CONFIRMED = "MINT_CONFIRMED"
    DEPOSITED_TO_POOL = "DEPOSITED_TO_POOL"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"

# Circle CCTP contract addresses on Base
CCTP_BASE = {
    "token_messenger": "0x1682Ae6375C4E4A97e4B583BC394c861A46D8962",
    "message_transmitter": "0xAD09780d193884d503182aD4F75D113B9B6a7c79",
    "usdc": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
}

# Circle attestation API
CIRCLE_ATTESTATION_URL = "https://iris-api.circle.com/attestations"

# Solana CCTP domain
SOLANA_CCTP_DOMAIN = 5

# ERC-20 Approve ABI
ERC20_APPROVE_ABI = [
    {"name": "approve", "type": "function", "inputs": [{"name": "spender", "type": "address"}, {"name": "amount", "type": "uint256"}], "outputs": [{"type": "bool"}]},
    {"name": "balanceOf", "type": "function", "inputs": [{"name": "account", "type": "address"}], "outputs": [{"type": "uint256"}]},
]

# CCTP TokenMessenger ABI (burn function)
TOKEN_MESSENGER_ABI = [
    {
        "name": "depositForBurn",
        "type": "function",
        "inputs": [
            {"name": "amount", "type": "uint256"},
            {"name": "destinationDomain", "type": "uint32"},
            {"name": "mintRecipient", "type": "bytes32"},
            {"name": "burnToken", "type": "address"},
        ],
        "outputs": [{"name": "nonce", "type": "uint64"}],
    },
]

class BridgeController:
    """Manages CCTP bridge from Base USDC to Solana USDC.
    
    Only management fees bridge cross-chain. Not basket principal.
    
    State machine handles non-atomic execution:
    fee collected → USDC ready → burn → attestation → mint → deposit to pool
    """
    
    def __init__(self, config, db_pool, redis):
        self.config = config
        self.db = db_pool
        self.redis = redis
        
        # Base (EVM)
        self.w3 = AsyncWeb3(AsyncWeb3.AsyncHTTPProvider(config.base_rpc_url))
        self.account = __import__("eth_account").Account.from_key(config.management_wallet_key)
        self.usdc_contract = self.w3.eth.contract(address=CCTP_BASE["usdc"], abi=ERC20_APPROVE_ABI)
        self.messenger_contract = self.w3.eth.contract(address=CCTP_BASE["token_messenger"], abi=TOKEN_MESSENGER_ABI)
        
        # Solana
        self.solana_client = SolanaClient(config.solana_rpc_url)
        self.solana_keypair = Keypair.from_base58_string(config.solana_wallet_key)
        
        # HTTP client for Circle attestation API
        self.http = httpx.AsyncClient(timeout=30.0)
    
    async def initiate_bridge(self, amount_usdc: float) -> int:
        """Start a bridge transfer. Returns bridge_job_id.
        
        Args:
            amount_usdc: Amount of USDC to bridge (6 decimals on Base)
        """
        amount_raw = int(amount_usdc * 1e6)  # USDC has 6 decimals
        
        # Create bridge job record
        job_id = await self._create_job(amount_usdc, amount_raw)
        
        try:
            # Step 1: Approve USDC for CCTP TokenMessenger
            await self._transition(job_id, BridgeState.USDC_READY)
            approve_tx = await self._approve_usdc(amount_raw)
            logger.info(f"Bridge job {job_id}: USDC approved, tx={approve_tx}")
            
            # Step 2: Burn USDC via CCTP
            await self._transition(job_id, BridgeState.BURN_SUBMITTED)
            burn_tx, nonce = await self._burn_usdc(amount_raw)
            await self._update_job(job_id, burn_tx_hash=burn_tx, cctp_nonce=nonce)
            logger.info(f"Bridge job {job_id}: Burn submitted, tx={burn_tx}, nonce={nonce}")
            
            # Step 3: Wait for burn confirmation
            receipt = await self.w3.eth.wait_for_transaction_receipt(burn_tx, timeout=120)
            if receipt["status"] != 1:
                raise RuntimeError(f"Burn tx failed: {burn_tx}")
            await self._transition(job_id, BridgeState.BURN_CONFIRMED)
            
            # Step 4: Wait for Circle attestation (poll)
            await self._transition(job_id, BridgeState.ATTESTATION_PENDING)
            message_hash = self._extract_message_hash(receipt)
            attestation = await self._wait_for_attestation(message_hash)
            await self._transition(job_id, BridgeState.ATTESTATION_RECEIVED)
            await self._update_job(job_id, attestation=attestation)
            
            # Step 5: Mint on Solana
            await self._transition(job_id, BridgeState.MINT_SUBMITTED)
            mint_tx = await self._mint_on_solana(attestation, message_hash)
            await self._update_job(job_id, mint_tx_hash=mint_tx)
            await self._transition(job_id, BridgeState.MINT_CONFIRMED)
            
            # Step 6: Deposit to staking pool (separate tx — NOT atomic with mint)
            deposit_tx = await self._deposit_to_staking_pool(amount_raw)
            await self._update_job(job_id, deposit_tx_hash=deposit_tx)
            await self._transition(job_id, BridgeState.DEPOSITED_TO_POOL)
            
            logger.info(f"Bridge job {job_id}: Complete! ${amount_usdc} bridged and deposited.")
            return job_id
            
        except Exception as e:
            logger.error(f"Bridge job {job_id} failed: {e}")
            await self._transition(job_id, BridgeState.FAILED, error=str(e))
            await self._alert_telegram(f"🚨 Bridge job {job_id} FAILED: {e}")
            raise
    
    async def retry_failed_job(self, job_id: int):
        """Retry a failed bridge job from its last successful state."""
        job = await self._get_job(job_id)
        if not job or job["state"] != BridgeState.FAILED:
            return
        
        # Determine resume point based on what data we have
        if job.get("mint_tx_hash"):
            # Mint succeeded, just need deposit
            await self._deposit_to_staking_pool(job["amount_raw"])
            await self._transition(job_id, BridgeState.DEPOSITED_TO_POOL)
        elif job.get("attestation"):
            # Have attestation, retry mint
            mint_tx = await self._mint_on_solana(job["attestation"], job["message_hash"])
            await self._update_job(job_id, mint_tx_hash=mint_tx)
            await self._transition(job_id, BridgeState.MINT_CONFIRMED)
            # Then deposit
            deposit_tx = await self._deposit_to_staking_pool(job["amount_raw"])
            await self._update_job(job_id, deposit_tx_hash=deposit_tx)
            await self._transition(job_id, BridgeState.DEPOSITED_TO_POOL)
        elif job.get("burn_tx_hash"):
            # Burn confirmed, wait for attestation again
            receipt = await self.w3.eth.get_transaction_receipt(job["burn_tx_hash"])
            message_hash = self._extract_message_hash(receipt)
            attestation = await self._wait_for_attestation(message_hash)
            await self._transition(job_id, BridgeState.ATTESTATION_RECEIVED)
            # Continue from attestation...
        else:
            # Start over
            await self.initiate_bridge(job["amount_usdc"])
    
    async def _approve_usdc(self, amount: int) -> str:
        nonce = await self.w3.eth.get_transaction_count(self.account.address)
        tx = await self.usdc_contract.functions.approve(
            CCTP_BASE["token_messenger"], amount
        ).build_transaction({
            "from": self.account.address,
            "nonce": nonce,
            "chainId": 8453,
        })
        signed = self.account.sign_transaction(tx)
        tx_hash = await self.w3.eth.send_raw_transaction(signed.raw_transaction)
        await self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)
        return tx_hash.hex()
    
    async def _burn_usdc(self, amount: int) -> tuple[str, int]:
        """Burn USDC on Base via CCTP TokenMessenger.depositForBurn."""
        # Convert Solana address to bytes32 for CCTP
        recipient_bytes32 = bytes(self.solana_keypair.pubkey())
        recipient_bytes32 = b'\x00' * (32 - len(recipient_bytes32)) + recipient_bytes32
        
        nonce = await self.w3.eth.get_transaction_count(self.account.address)
        tx = await self.messenger_contract.functions.depositForBurn(
            amount,
            SOLANA_CCTP_DOMAIN,  # Solana destination domain = 5
            recipient_bytes32,
            CCTP_BASE["usdc"],
        ).build_transaction({
            "from": self.account.address,
            "nonce": nonce,
            "chainId": 8453,
        })
        
        gas = await self.w3.eth.estimate_gas(tx)
        tx["gas"] = int(gas * 1.2)
        
        signed = self.account.sign_transaction(tx)
        tx_hash = await self.w3.eth.send_raw_transaction(signed.raw_transaction)
        receipt = await self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
        
        # Extract nonce from MessageSent event
        cctp_nonce = self._extract_nonce(receipt)
        return tx_hash.hex(), cctp_nonce
    
    async def _wait_for_attestation(self, message_hash: str, max_wait: int = 300) -> str:
        """Poll Circle's attestation service until attestation is ready.
        
        CCTP Fast Transfer: ~8-20 seconds on Base.
        Standard: ~13 minutes.
        """
        for _ in range(max_wait // 5):
            response = await self.http.get(f"{CIRCLE_ATTESTATION_URL}/{message_hash}")
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "complete":
                    return data["attestation"]
            await asyncio.sleep(5)
        
        raise TimeoutError(f"Attestation not received after {max_wait}s for {message_hash}")
    
    async def _mint_on_solana(self, attestation: str, message_hash: str) -> str:
        """Submit receiveMessage on Solana to mint USDC."""
        # This uses the CCTP Solana program to receive and mint
        # Implementation requires CCTP Solana SDK / manual instruction building
        # Placeholder — use @noble-assets/cctp-solana or equivalent
        raise NotImplementedError("Implement Solana CCTP mint instruction")
    
    async def _deposit_to_staking_pool(self, amount_raw: int) -> str:
        """Deposit bridged USDC to the staking reward vault on Solana.
        
        This is a SEPARATE transaction from the mint — NOT atomic.
        """
        # Call deposit_rewards instruction on the staking pool
        # Implementation depends on Anchor IDL
        raise NotImplementedError("Implement staking pool deposit")
    
    def _extract_message_hash(self, receipt) -> str:
        """Extract CCTP message hash from burn transaction receipt."""
        # MessageSent event topic
        for log in receipt["logs"]:
            if log["address"].lower() == CCTP_BASE["message_transmitter"].lower():
                return self.w3.keccak(log["data"]).hex()
        raise ValueError("MessageSent event not found in receipt")
    
    def _extract_nonce(self, receipt) -> int:
        """Extract CCTP nonce from burn receipt."""
        # Parse from event data
        return 0  # Placeholder
    
    async def _create_job(self, amount_usdc: float, amount_raw: int) -> int:
        row = await self.db.fetchrow("""
            INSERT INTO inv_bridge_jobs (amount_usdc, amount_raw, state, created_at)
            VALUES ($1, $2, $3, NOW()) RETURNING id
        """, amount_usdc, amount_raw, BridgeState.FEE_COLLECTED)
        return row["id"]
    
    async def _transition(self, job_id: int, state: BridgeState, error: str = None):
        await self.db.execute(
            "UPDATE inv_bridge_jobs SET state = $1, error = $2, updated_at = NOW() WHERE id = $3",
            state, error, job_id,
        )
        import json
        await self.redis.publish("inv:bridge_events", json.dumps({"job_id": job_id, "state": state}))
    
    async def _update_job(self, job_id: int, **kwargs):
        sets = ", ".join(f"{k} = ${i+2}" for i, k in enumerate(kwargs.keys()))
        await self.db.execute(
            f"UPDATE inv_bridge_jobs SET {sets}, updated_at = NOW() WHERE id = $1",
            job_id, *kwargs.values(),
        )
    
    async def _get_job(self, job_id: int) -> dict:
        return await self.db.fetchrow("SELECT * FROM inv_bridge_jobs WHERE id = $1", job_id)
    
    async def _alert_telegram(self, message: str):
        await self.redis.publish("telegram:alerts", message)
```

### 4.3 Bridge Database Table

```sql
-- services/investments/migrations/002_bridge_tables.sql

CREATE TABLE inv_bridge_jobs (
    id SERIAL PRIMARY KEY,
    amount_usdc NUMERIC(18, 6) NOT NULL,
    amount_raw BIGINT NOT NULL,
    state VARCHAR(32) NOT NULL DEFAULT 'FEE_COLLECTED',
    
    -- Base (EVM) side
    approve_tx_hash VARCHAR(128),
    burn_tx_hash VARCHAR(128),
    cctp_nonce BIGINT,
    message_hash VARCHAR(128),
    
    -- Attestation
    attestation TEXT,
    
    -- Solana side
    mint_tx_hash VARCHAR(128),
    deposit_tx_hash VARCHAR(128),
    
    -- Fee accounting
    bridge_fee_usdc NUMERIC(18, 6) DEFAULT 0,
    gas_cost_usd NUMERIC(10, 4) DEFAULT 0,
    net_deposited_usdc NUMERIC(18, 6),
    
    -- Error handling
    error TEXT,
    retry_count INTEGER DEFAULT 0,
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_inv_bridge_state ON inv_bridge_jobs(state);
CREATE INDEX idx_inv_bridge_created ON inv_bridge_jobs(created_at DESC);

-- Fee accounting view
CREATE VIEW inv_bridge_fee_summary AS
SELECT
    DATE_TRUNC('day', created_at) as day,
    SUM(amount_usdc) as gross_bridged,
    SUM(bridge_fee_usdc) as bridge_fees,
    SUM(gas_cost_usd) as gas_costs,
    SUM(net_deposited_usdc) as net_deposited,
    COUNT(*) as bridge_count
FROM inv_bridge_jobs
WHERE state = 'DEPOSITED_TO_POOL'
GROUP BY DATE_TRUNC('day', created_at)
ORDER BY day DESC;
```

### 4.4 Bridge Fee Trigger Logic

```python
# services/investments/bridge_trigger.py

class BridgeTrigger:
    """Determines when to bridge accumulated fees to Solana.
    
    Rules:
    - Bridge when accumulated fees > $50 (Base gas is cheap)
    - Time fallback: bridge weekly if threshold not met
    - Never bridge when Base gas > 5 gwei
    - Max $50,000 per 24h period
    """
    
    THRESHOLD_USD = 50.0  # Low threshold because Base gas is ~$0.50
    MAX_DAILY_USD = 50_000.0
    MAX_GAS_GWEI = 5
    WEEKLY_FALLBACK_DAYS = 7
    
    def __init__(self, bridge_controller, alvara_manager, db_pool, w3):
        self.bridge = bridge_controller
        self.alvara = alvara_manager
        self.db = db_pool
        self.w3 = w3
    
    async def check_and_bridge(self):
        """Check if bridge conditions are met and initiate if so."""
        # Get accumulated unbridged fees
        accumulated = await self._get_accumulated_fees()
        
        if accumulated < 0.01:
            return  # Nothing to bridge
        
        # Check daily limit
        daily_total = await self._get_daily_bridged_total()
        if daily_total >= self.MAX_DAILY_USD:
            return
        
        # Check gas
        gas_price = await self.w3.eth.gas_price
        gas_gwei = gas_price / 1e9
        if gas_gwei > self.MAX_GAS_GWEI:
            return
        
        # Threshold check
        days_since_last = await self._days_since_last_bridge()
        
        should_bridge = (
            accumulated >= self.THRESHOLD_USD or
            (days_since_last >= self.WEEKLY_FALLBACK_DAYS and accumulated > 0)
        )
        
        if should_bridge:
            amount = min(accumulated, self.MAX_DAILY_USD - daily_total)
            await self.bridge.initiate_bridge(amount)
    
    async def _get_accumulated_fees(self) -> float:
        row = await self.db.fetchrow("""
            SELECT COALESCE(SUM(fee_amount_usdc), 0) as total
            FROM inv_fee_collections
            WHERE bridged = FALSE
        """)
        return float(row["total"])
    
    async def _get_daily_bridged_total(self) -> float:
        row = await self.db.fetchrow("""
            SELECT COALESCE(SUM(amount_usdc), 0) as total
            FROM inv_bridge_jobs
            WHERE created_at > NOW() - INTERVAL '24 hours'
            AND state != 'FAILED' AND state != 'CANCELLED'
        """)
        return float(row["total"])
    
    async def _days_since_last_bridge(self) -> float:
        row = await self.db.fetchrow("""
            SELECT created_at FROM inv_bridge_jobs
            WHERE state = 'DEPOSITED_TO_POOL'
            ORDER BY created_at DESC LIMIT 1
        """)
        if not row:
            return 999
        from datetime import datetime, timezone
        return (datetime.now(timezone.utc) - row["created_at"]).total_seconds() / 86400
```

---

## 5. Solana Staking Pool (Anchor)

### 5.1 Program Specification

```rust
// contracts/solana/kr8tiv-staking/programs/kr8tiv-staking/src/lib.rs

use anchor_lang::prelude::*;
use anchor_spl::token::{self, Mint, Token, TokenAccount, Transfer};

declare_id!("KR8TiVStake11111111111111111111111111111111"); // Replace with actual program ID

#[program]
pub mod kr8tiv_staking {
    use super::*;

    /// Initialize the staking pool. Called once by deployer.
    pub fn initialize_pool(
        ctx: Context<InitializePool>,
        pool_bump: u8,
        vault_bump: u8,
        reward_vault_bump: u8,
    ) -> Result<()> {
        let pool = &mut ctx.accounts.pool;
        pool.authority = ctx.accounts.authority.key();
        pool.kr8tiv_mint = ctx.accounts.kr8tiv_mint.key();
        pool.kr8tiv_vault = ctx.accounts.kr8tiv_vault.key();
        pool.reward_mint = ctx.accounts.reward_mint.key();
        pool.reward_vault = ctx.accounts.reward_vault.key();
        pool.total_staked = 0;
        pool.total_weighted_stake = 0;
        pool.rewards_per_weighted_stake = 0;
        pool.last_reward_timestamp = Clock::get()?.unix_timestamp;
        pool.pool_bump = pool_bump;
        pool.vault_bump = vault_bump;
        pool.reward_vault_bump = reward_vault_bump;
        pool.paused = false;
        Ok(())
    }

    /// Stake $KR8TIV tokens into the pool.
    pub fn stake(ctx: Context<Stake>, amount: u64) -> Result<()> {
        require!(!ctx.accounts.pool.paused, StakingError::PoolPaused);
        require!(amount > 0, StakingError::ZeroAmount);

        let pool = &mut ctx.accounts.pool;
        let entry = &mut ctx.accounts.stake_entry;
        let clock = Clock::get()?;

        // If user already has a stake, settle pending rewards first
        if entry.amount > 0 {
            let pending = calculate_pending_rewards(
                entry,
                pool.rewards_per_weighted_stake,
            )?;
            entry.pending_rewards = entry
                .pending_rewards
                .checked_add(pending)
                .ok_or(StakingError::Overflow)?;
        }

        // Transfer $KR8TIV from user to vault
        token::transfer(
            CpiContext::new(
                ctx.accounts.token_program.to_account_info(),
                Transfer {
                    from: ctx.accounts.user_kr8tiv.to_account_info(),
                    to: ctx.accounts.kr8tiv_vault.to_account_info(),
                    authority: ctx.accounts.owner.to_account_info(),
                },
            ),
            amount,
        )?;

        // Update stake entry
        let old_weighted = get_weighted_stake(entry.amount, entry.stake_timestamp, clock.unix_timestamp);
        entry.amount = entry.amount.checked_add(amount).ok_or(StakingError::Overflow)?;
        if entry.stake_timestamp == 0 {
            entry.stake_timestamp = clock.unix_timestamp;
        }
        entry.rewards_per_weighted_stake_snapshot = pool.rewards_per_weighted_stake;
        let new_weighted = get_weighted_stake(entry.amount, entry.stake_timestamp, clock.unix_timestamp);

        // Update pool totals
        pool.total_staked = pool.total_staked.checked_add(amount).ok_or(StakingError::Overflow)?;
        pool.total_weighted_stake = pool
            .total_weighted_stake
            .checked_sub(old_weighted)
            .ok_or(StakingError::Overflow)?
            .checked_add(new_weighted)
            .ok_or(StakingError::Overflow)?;

        emit!(StakeEvent {
            user: ctx.accounts.owner.key(),
            amount,
            total_staked: pool.total_staked,
            timestamp: clock.unix_timestamp,
        });

        Ok(())
    }

    /// Unstake $KR8TIV tokens. Automatically claims pending rewards.
    pub fn unstake(ctx: Context<Unstake>) -> Result<()> {
        let pool = &mut ctx.accounts.pool;
        let entry = &mut ctx.accounts.stake_entry;
        let clock = Clock::get()?;

        require!(entry.amount > 0, StakingError::NothingStaked);

        // Calculate and settle all pending rewards
        let pending = calculate_pending_rewards(entry, pool.rewards_per_weighted_stake)?;
        let total_rewards = entry
            .pending_rewards
            .checked_add(pending)
            .ok_or(StakingError::Overflow)?;

        // Transfer rewards (USDC) to user
        if total_rewards > 0 {
            let seeds = &[b"reward_vault", pool.reward_mint.as_ref(), &[pool.reward_vault_bump]];
            let signer = &[&seeds[..]];
            token::transfer(
                CpiContext::new_with_signer(
                    ctx.accounts.token_program.to_account_info(),
                    Transfer {
                        from: ctx.accounts.reward_vault.to_account_info(),
                        to: ctx.accounts.user_reward.to_account_info(),
                        authority: ctx.accounts.reward_vault.to_account_info(),
                    },
                    signer,
                ),
                total_rewards,
            )?;
        }

        // Transfer staked $KR8TIV back to user
        let vault_seeds = &[b"kr8tiv_vault", pool.kr8tiv_mint.as_ref(), &[pool.vault_bump]];
        let vault_signer = &[&vault_seeds[..]];
        token::transfer(
            CpiContext::new_with_signer(
                ctx.accounts.token_program.to_account_info(),
                Transfer {
                    from: ctx.accounts.kr8tiv_vault.to_account_info(),
                    to: ctx.accounts.user_kr8tiv.to_account_info(),
                    authority: ctx.accounts.kr8tiv_vault.to_account_info(),
                },
                vault_signer,
            ),
            entry.amount,
        )?;

        // Update pool
        let weighted = get_weighted_stake(entry.amount, entry.stake_timestamp, clock.unix_timestamp);
        pool.total_staked = pool.total_staked.checked_sub(entry.amount).ok_or(StakingError::Overflow)?;
        pool.total_weighted_stake = pool
            .total_weighted_stake
            .checked_sub(weighted)
            .ok_or(StakingError::Overflow)?;

        emit!(UnstakeEvent {
            user: ctx.accounts.owner.key(),
            amount: entry.amount,
            rewards_claimed: total_rewards,
            timestamp: clock.unix_timestamp,
        });

        // Reset entry
        entry.amount = 0;
        entry.pending_rewards = 0;
        entry.stake_timestamp = 0;
        entry.rewards_per_weighted_stake_snapshot = 0;

        Ok(())
    }

    /// Deposit bridged USDC rewards into the pool. Authority-only.
    pub fn deposit_rewards(ctx: Context<DepositRewards>, amount: u64) -> Result<()> {
        require!(amount > 0, StakingError::ZeroAmount);

        let pool = &mut ctx.accounts.pool;
        let clock = Clock::get()?;

        require!(pool.total_weighted_stake > 0, StakingError::NoStakers);

        // Transfer USDC from authority to reward vault
        token::transfer(
            CpiContext::new(
                ctx.accounts.token_program.to_account_info(),
                Transfer {
                    from: ctx.accounts.authority_reward.to_account_info(),
                    to: ctx.accounts.reward_vault.to_account_info(),
                    authority: ctx.accounts.authority.to_account_info(),
                },
            ),
            amount,
        )?;

        // Update accumulator: rewards_per_weighted_stake += (amount * PRECISION) / total_weighted_stake
        let reward_increment = (amount as u128)
            .checked_mul(PRECISION)
            .ok_or(StakingError::Overflow)?
            .checked_div(pool.total_weighted_stake as u128)
            .ok_or(StakingError::Overflow)?;

        pool.rewards_per_weighted_stake = pool
            .rewards_per_weighted_stake
            .checked_add(reward_increment)
            .ok_or(StakingError::Overflow)?;
        pool.last_reward_timestamp = clock.unix_timestamp;

        emit!(RewardDepositEvent {
            amount,
            new_rewards_per_weighted_stake: pool.rewards_per_weighted_stake,
            total_weighted_stake: pool.total_weighted_stake,
            timestamp: clock.unix_timestamp,
        });

        Ok(())
    }

    /// Claim pending USDC rewards without unstaking.
    pub fn claim_rewards(ctx: Context<ClaimRewards>) -> Result<()> {
        let pool = &mut ctx.accounts.pool;
        let entry = &mut ctx.accounts.stake_entry;
        let clock = Clock::get()?;

        // Recalculate weighted stake (multiplier may have changed)
        let old_weighted = get_weighted_stake(entry.amount, entry.stake_timestamp, clock.unix_timestamp);
        // Note: we don't update total_weighted_stake here since the stake amount hasn't changed
        // Multiplier changes are handled lazily

        let pending = calculate_pending_rewards(entry, pool.rewards_per_weighted_stake)?;
        let total = entry
            .pending_rewards
            .checked_add(pending)
            .ok_or(StakingError::Overflow)?;

        require!(total > 0, StakingError::NothingToClaim);

        // Transfer USDC rewards
        let seeds = &[b"reward_vault", pool.reward_mint.as_ref(), &[pool.reward_vault_bump]];
        let signer = &[&seeds[..]];
        token::transfer(
            CpiContext::new_with_signer(
                ctx.accounts.token_program.to_account_info(),
                Transfer {
                    from: ctx.accounts.reward_vault.to_account_info(),
                    to: ctx.accounts.user_reward.to_account_info(),
                    authority: ctx.accounts.reward_vault.to_account_info(),
                },
                signer,
            ),
            total,
        )?;

        // Update entry
        entry.pending_rewards = 0;
        entry.rewards_per_weighted_stake_snapshot = pool.rewards_per_weighted_stake;

        emit!(ClaimEvent {
            user: ctx.accounts.owner.key(),
            amount: total,
            timestamp: clock.unix_timestamp,
        });

        Ok(())
    }

    /// Emergency pause. Authority-only.
    pub fn set_paused(ctx: Context<AdminAction>, paused: bool) -> Result<()> {
        ctx.accounts.pool.paused = paused;
        Ok(())
    }
}

// ============ Constants ============

/// Precision factor for accumulator math (10^18)
const PRECISION: u128 = 1_000_000_000_000_000_000;

/// Lockup tier thresholds in seconds
const TIER_2_THRESHOLD: i64 = 30 * 24 * 60 * 60;  // 30 days
const TIER_3_THRESHOLD: i64 = 90 * 24 * 60 * 60;  // 90 days

/// Multipliers (basis points: 10000 = 1.0x)
const TIER_1_MULTIPLIER: u64 = 10000;  // 1.0x
const TIER_2_MULTIPLIER: u64 = 12500;  // 1.25x
const TIER_3_MULTIPLIER: u64 = 15000;  // 1.5x

// ============ Helper Functions ============

fn get_multiplier(stake_timestamp: i64, current_timestamp: i64) -> u64 {
    let duration = current_timestamp.saturating_sub(stake_timestamp);
    if duration >= TIER_3_THRESHOLD {
        TIER_3_MULTIPLIER
    } else if duration >= TIER_2_THRESHOLD {
        TIER_2_MULTIPLIER
    } else {
        TIER_1_MULTIPLIER
    }
}

fn get_weighted_stake(amount: u64, stake_timestamp: i64, current_timestamp: i64) -> u64 {
    let multiplier = get_multiplier(stake_timestamp, current_timestamp);
    // (amount * multiplier) / 10000
    (amount as u128)
        .checked_mul(multiplier as u128)
        .unwrap_or(0)
        .checked_div(10000)
        .unwrap_or(0) as u64
}

fn calculate_pending_rewards(
    entry: &StakeEntry,
    current_rewards_per_weighted_stake: u128,
) -> Result<u64> {
    let clock = Clock::get()?;
    let weighted_stake = get_weighted_stake(entry.amount, entry.stake_timestamp, clock.unix_timestamp);
    
    let diff = current_rewards_per_weighted_stake
        .checked_sub(entry.rewards_per_weighted_stake_snapshot)
        .ok_or(StakingError::Overflow)?;
    
    let rewards = (weighted_stake as u128)
        .checked_mul(diff)
        .ok_or(StakingError::Overflow)?
        .checked_div(PRECISION)
        .ok_or(StakingError::Overflow)?;
    
    Ok(rewards as u64)
}

// ============ Accounts ============

#[account]
pub struct StakePool {
    pub authority: Pubkey,              // 32
    pub kr8tiv_mint: Pubkey,            // 32
    pub kr8tiv_vault: Pubkey,           // 32
    pub reward_mint: Pubkey,            // 32
    pub reward_vault: Pubkey,           // 32
    pub total_staked: u64,              // 8
    pub total_weighted_stake: u64,      // 8
    pub rewards_per_weighted_stake: u128, // 16
    pub last_reward_timestamp: i64,     // 8
    pub pool_bump: u8,                  // 1
    pub vault_bump: u8,                 // 1
    pub reward_vault_bump: u8,          // 1
    pub paused: bool,                   // 1
    // Total: 8 (discriminator) + 204 = 212 bytes
}

#[account]
pub struct StakeEntry {
    pub owner: Pubkey,                              // 32
    pub amount: u64,                                // 8
    pub rewards_per_weighted_stake_snapshot: u128,   // 16
    pub pending_rewards: u64,                       // 8
    pub stake_timestamp: i64,                       // 8
    pub bump: u8,                                   // 1
    // Total: 8 (discriminator) + 73 = 81 bytes
}

// ============ Contexts ============

#[derive(Accounts)]
pub struct InitializePool<'info> {
    #[account(
        init,
        payer = authority,
        space = 8 + 212,
        seeds = [b"pool", kr8tiv_mint.key().as_ref()],
        bump,
    )]
    pub pool: Account<'info, StakePool>,
    
    pub kr8tiv_mint: Account<'info, Mint>,
    
    #[account(
        init,
        payer = authority,
        token::mint = kr8tiv_mint,
        token::authority = kr8tiv_vault,
        seeds = [b"kr8tiv_vault", kr8tiv_mint.key().as_ref()],
        bump,
    )]
    pub kr8tiv_vault: Account<'info, TokenAccount>,
    
    pub reward_mint: Account<'info, Mint>,
    
    #[account(
        init,
        payer = authority,
        token::mint = reward_mint,
        token::authority = reward_vault,
        seeds = [b"reward_vault", reward_mint.key().as_ref()],
        bump,
    )]
    pub reward_vault: Account<'info, TokenAccount>,
    
    #[account(mut)]
    pub authority: Signer<'info>,
    
    pub system_program: Program<'info, System>,
    pub token_program: Program<'info, Token>,
    pub rent: Sysvar<'info, Rent>,
}

#[derive(Accounts)]
pub struct Stake<'info> {
    #[account(
        mut,
        seeds = [b"pool", pool.kr8tiv_mint.as_ref()],
        bump = pool.pool_bump,
    )]
    pub pool: Account<'info, StakePool>,
    
    #[account(
        init_if_needed,
        payer = owner,
        space = 8 + 81,
        seeds = [b"stake", pool.key().as_ref(), owner.key().as_ref()],
        bump,
    )]
    pub stake_entry: Account<'info, StakeEntry>,
    
    #[account(
        mut,
        constraint = kr8tiv_vault.key() == pool.kr8tiv_vault,
    )]
    pub kr8tiv_vault: Account<'info, TokenAccount>,
    
    #[account(
        mut,
        constraint = user_kr8tiv.owner == owner.key(),
        constraint = user_kr8tiv.mint == pool.kr8tiv_mint,
    )]
    pub user_kr8tiv: Account<'info, TokenAccount>,
    
    #[account(mut)]
    pub owner: Signer<'info>,
    
    pub system_program: Program<'info, System>,
    pub token_program: Program<'info, Token>,
}

#[derive(Accounts)]
pub struct Unstake<'info> {
    #[account(
        mut,
        seeds = [b"pool", pool.kr8tiv_mint.as_ref()],
        bump = pool.pool_bump,
    )]
    pub pool: Account<'info, StakePool>,
    
    #[account(
        mut,
        seeds = [b"stake", pool.key().as_ref(), owner.key().as_ref()],
        bump = stake_entry.bump,
        constraint = stake_entry.owner == owner.key(),
    )]
    pub stake_entry: Account<'info, StakeEntry>,
    
    #[account(
        mut,
        constraint = kr8tiv_vault.key() == pool.kr8tiv_vault,
    )]
    pub kr8tiv_vault: Account<'info, TokenAccount>,
    
    #[account(
        mut,
        constraint = user_kr8tiv.owner == owner.key(),
    )]
    pub user_kr8tiv: Account<'info, TokenAccount>,
    
    #[account(
        mut,
        constraint = reward_vault.key() == pool.reward_vault,
    )]
    pub reward_vault: Account<'info, TokenAccount>,
    
    #[account(
        mut,
        constraint = user_reward.owner == owner.key(),
    )]
    pub user_reward: Account<'info, TokenAccount>,
    
    #[account(mut)]
    pub owner: Signer<'info>,
    
    pub token_program: Program<'info, Token>,
}

#[derive(Accounts)]
pub struct DepositRewards<'info> {
    #[account(
        mut,
        seeds = [b"pool", pool.kr8tiv_mint.as_ref()],
        bump = pool.pool_bump,
        has_one = authority,
    )]
    pub pool: Account<'info, StakePool>,
    
    #[account(
        mut,
        constraint = reward_vault.key() == pool.reward_vault,
    )]
    pub reward_vault: Account<'info, TokenAccount>,
    
    #[account(
        mut,
        constraint = authority_reward.owner == authority.key(),
        constraint = authority_reward.mint == pool.reward_mint,
    )]
    pub authority_reward: Account<'info, TokenAccount>,
    
    pub authority: Signer<'info>,
    
    pub token_program: Program<'info, Token>,
}

#[derive(Accounts)]
pub struct ClaimRewards<'info> {
    #[account(
        mut,
        seeds = [b"pool", pool.kr8tiv_mint.as_ref()],
        bump = pool.pool_bump,
    )]
    pub pool: Account<'info, StakePool>,
    
    #[account(
        mut,
        seeds = [b"stake", pool.key().as_ref(), owner.key().as_ref()],
        bump = stake_entry.bump,
        constraint = stake_entry.owner == owner.key(),
    )]
    pub stake_entry: Account<'info, StakeEntry>,
    
    #[account(
        mut,
        constraint = reward_vault.key() == pool.reward_vault,
    )]
    pub reward_vault: Account<'info, TokenAccount>,
    
    #[account(
        mut,
        constraint = user_reward.owner == owner.key(),
    )]
    pub user_reward: Account<'info, TokenAccount>,
    
    #[account(mut)]
    pub owner: Signer<'info>,
    
    pub token_program: Program<'info, Token>,
}

#[derive(Accounts)]
pub struct AdminAction<'info> {
    #[account(
        mut,
        seeds = [b"pool", pool.kr8tiv_mint.as_ref()],
        bump = pool.pool_bump,
        has_one = authority,
    )]
    pub pool: Account<'info, StakePool>,
    pub authority: Signer<'info>,
}

// ============ Events ============

#[event]
pub struct StakeEvent {
    pub user: Pubkey,
    pub amount: u64,
    pub total_staked: u64,
    pub timestamp: i64,
}

#[event]
pub struct UnstakeEvent {
    pub user: Pubkey,
    pub amount: u64,
    pub rewards_claimed: u64,
    pub timestamp: i64,
}

#[event]
pub struct RewardDepositEvent {
    pub amount: u64,
    pub new_rewards_per_weighted_stake: u128,
    pub total_weighted_stake: u64,
    pub timestamp: i64,
}

#[event]
pub struct ClaimEvent {
    pub user: Pubkey,
    pub amount: u64,
    pub timestamp: i64,
}

// ============ Errors ============

#[error_code]
pub enum StakingError {
    #[msg("Pool is paused")]
    PoolPaused,
    #[msg("Amount must be greater than zero")]
    ZeroAmount,
    #[msg("Nothing staked")]
    NothingStaked,
    #[msg("Nothing to claim")]
    NothingToClaim,
    #[msg("No stakers in pool")]
    NoStakers,
    #[msg("Arithmetic overflow")]
    Overflow,
}
```

### 5.2 Anchor.toml

```toml
# contracts/solana/kr8tiv-staking/Anchor.toml

[features]
seeds = false
skip-lint = false

[programs.localnet]
kr8tiv_staking = "KR8TiVStake11111111111111111111111111111111"

[programs.devnet]
kr8tiv_staking = "KR8TiVStake11111111111111111111111111111111"

[programs.mainnet]
kr8tiv_staking = "KR8TiVStake11111111111111111111111111111111"

[registry]
url = "https://api.apr.dev"

[provider]
cluster = "Localnet"
wallet = "~/.config/solana/id.json"

[scripts]
test = "yarn run ts-mocha -p ./tsconfig.json -t 1000000 tests/**/*.ts"
```

### 5.3 Staking Cranker (Solana-side automation)

```python
# services/investments/staking_cranker.py

import asyncio
import logging
from solana.rpc.async_api import AsyncClient
from solders.pubkey import Pubkey

logger = logging.getLogger("investments.cranker")

class StakingCranker:
    """Monitors Solana USDC arrivals and calls deposit_rewards on the staking pool.
    
    Uses Helius WebSocket (already in Jarvis) to detect USDC transfers
    to the authority's reward token account.
    """
    
    def __init__(self, config, db_pool, redis):
        self.config = config
        self.db = db_pool
        self.redis = redis
        self.solana = AsyncClient(config.solana_rpc_url)
        self.last_processed_signature = None
    
    async def start(self):
        """Main loop: poll for new USDC deposits and call deposit_rewards."""
        logger.info("Staking cranker started")
        
        while True:
            try:
                await self._check_for_deposits()
            except Exception as e:
                logger.error(f"Cranker error: {e}")
            await asyncio.sleep(10)  # Check every 10 seconds
    
    async def _check_for_deposits(self):
        """Check if new USDC has arrived in the authority's reward account."""
        # Get current balance of authority's USDC account
        balance = await self._get_reward_balance()
        
        # Get last deposited amount from DB
        last = await self.db.fetchrow(
            "SELECT amount_raw FROM inv_staking_deposits ORDER BY created_at DESC LIMIT 1"
        )
        
        # If balance exceeds what we've deposited, there's new USDC
        cached_balance = await self.redis.get("inv:cranker:last_balance")
        cached_balance = int(cached_balance) if cached_balance else 0
        
        if balance > cached_balance and balance > 0:
            new_amount = balance - cached_balance
            if new_amount > 1000:  # Min 0.001 USDC (1000 raw units)
                logger.info(f"New USDC detected: {new_amount / 1e6:.6f} USDC")
                await self._execute_deposit(new_amount)
                await self.redis.set("inv:cranker:last_balance", str(balance))
    
    async def _get_reward_balance(self) -> int:
        """Get USDC balance of authority's reward token account."""
        # Use Solana RPC to get token account balance
        result = await self.solana.get_token_account_balance(
            Pubkey.from_string(self.config.authority_reward_account)
        )
        return int(result.value.amount)
    
    async def _execute_deposit(self, amount: int):
        """Call deposit_rewards on the staking pool."""
        # Build and send the deposit_rewards transaction
        # Uses Anchor IDL client
        logger.info(f"Depositing {amount / 1e6:.6f} USDC to staking pool")
        
        # Record in DB
        await self.db.execute(
            "INSERT INTO inv_staking_deposits (amount_raw, amount_usdc, status, created_at) "
            "VALUES ($1, $2, 'confirmed', NOW())",
            amount, amount / 1e6,
        )
        
        await self.redis.publish("inv:staking_events", f'{{"type":"deposit","amount":{amount}}}')
```

---

## 6. Dashboard UI

### 6.1 React Component Architecture

All components go in `frontend/src/components/investments/`. The dashboard integrates as a new tab in the existing Jarvis layout.

#### 6.1.1 Main Container

```typescript
// frontend/src/components/investments/InvestmentDashboard.tsx

import React, { useState } from 'react';
import { BasketOverview } from './BasketOverview';
import { PerformanceChart } from './PerformanceChart';
import { TokenTrajectories } from './TokenTrajectories';
import { AgentConsensusLog } from './AgentConsensusLog';
import { BridgeHistory } from './BridgeHistory';
import { StakingPanel } from './StakingPanel';
import { InvestmentInterface } from './InvestmentInterface';
import { useWebSocket } from '../../hooks/useWebSocket';

export const InvestmentDashboard: React.FC = () => {
  const [selectedTimeframe, setSelectedTimeframe] = useState<'1D' | '1W' | '1M' | '3M' | 'ALL'>('1M');
  const ws = useWebSocket('/ws/investments/live');

  return (
    <div className="grid grid-cols-12 gap-4 p-4 h-full">
      {/* Row 1: Basket Overview + Performance Chart */}
      <div className="col-span-5">
        <BasketOverview data={ws.basketState} />
      </div>
      <div className="col-span-7">
        <PerformanceChart 
          timeframe={selectedTimeframe} 
          onTimeframeChange={setSelectedTimeframe}
        />
      </div>

      {/* Row 2: Token Trajectories (full width) */}
      <div className="col-span-12">
        <TokenTrajectories tokens={ws.basketState?.tokens || []} />
      </div>

      {/* Row 3: Agent Log + Bridge History + Staking */}
      <div className="col-span-5">
        <AgentConsensusLog />
      </div>
      <div className="col-span-3">
        <BridgeHistory />
      </div>
      <div className="col-span-4">
        <StakingPanel />
      </div>

      {/* Investment Interface (modal overlay) */}
      <InvestmentInterface />
    </div>
  );
};
```

#### 6.1.2 Basket Overview Panel

```typescript
// frontend/src/components/investments/BasketOverview.tsx

import React from 'react';
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from 'recharts';

interface Token {
  symbol: string;
  weight: number;
  value_usd: number;
  change_24h: number;
  price_usd: number;
}

interface BasketState {
  nav_usd: number;
  tokens: Token[];
  chain: string;
}

const COLORS = ['#6366f1', '#8b5cf6', '#a78bfa', '#c4b5fd', '#e879f9', '#f472b6', '#fb7185', '#f97316', '#facc15', '#4ade80', '#22d3ee', '#38bdf8'];

export const BasketOverview: React.FC<{ data?: BasketState }> = ({ data }) => {
  if (!data) return <div className="bg-gray-900 rounded-lg p-4 animate-pulse h-80" />;

  const chartData = data.tokens.map(t => ({
    name: t.symbol,
    value: t.weight * 100,
    usdValue: t.value_usd,
  }));

  return (
    <div className="bg-gray-900 rounded-lg p-4 border border-gray-800">
      <div className="flex justify-between items-center mb-4">
        <h2 className="text-lg font-bold text-white">Basket Overview</h2>
        <span className="text-xs text-gray-400 uppercase">{data.chain}</span>
      </div>
      
      <div className="text-3xl font-bold text-green-400 mb-2">
        ${data.nav_usd.toLocaleString(undefined, { minimumFractionDigits: 2 })}
      </div>
      <div className="text-sm text-gray-400 mb-4">Total NAV</div>

      <div className="flex">
        <div className="w-1/2">
          <ResponsiveContainer width="100%" height={200}>
            <PieChart>
              <Pie data={chartData} dataKey="value" cx="50%" cy="50%" innerRadius={50} outerRadius={80}>
                {chartData.map((_, i) => (
                  <Cell key={i} fill={COLORS[i % COLORS.length]} />
                ))}
              </Pie>
              <Tooltip formatter={(v: number) => `${v.toFixed(1)}%`} />
            </PieChart>
          </ResponsiveContainer>
        </div>
        <div className="w-1/2 space-y-1 overflow-y-auto max-h-52">
          {data.tokens.map((t, i) => (
            <div key={t.symbol} className="flex items-center justify-between text-sm">
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 rounded-full" style={{ backgroundColor: COLORS[i % COLORS.length] }} />
                <span className="text-white font-medium">{t.symbol}</span>
              </div>
              <div className="text-right">
                <span className="text-gray-300">{(t.weight * 100).toFixed(1)}%</span>
                <span className={`ml-2 ${t.change_24h >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                  {t.change_24h >= 0 ? '+' : ''}{t.change_24h.toFixed(1)}%
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
```

#### 6.1.3 Performance Chart

```typescript
// frontend/src/components/investments/PerformanceChart.tsx

import React, { useEffect, useState } from 'react';
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, Legend } from 'recharts';

type Timeframe = '1D' | '1W' | '1M' | '3M' | 'ALL';

interface Props {
  timeframe: Timeframe;
  onTimeframeChange: (tf: Timeframe) => void;
}

export const PerformanceChart: React.FC<Props> = ({ timeframe, onTimeframeChange }) => {
  const [data, setData] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      const res = await fetch(`/api/investments/performance?timeframe=${timeframe}`);
      const json = await res.json();
      setData(json.data);
      setLoading(false);
    };
    fetchData();
  }, [timeframe]);

  const timeframes: Timeframe[] = ['1D', '1W', '1M', '3M', 'ALL'];

  return (
    <div className="bg-gray-900 rounded-lg p-4 border border-gray-800">
      <div className="flex justify-between items-center mb-4">
        <h2 className="text-lg font-bold text-white">Performance</h2>
        <div className="flex gap-1">
          {timeframes.map(tf => (
            <button
              key={tf}
              onClick={() => onTimeframeChange(tf)}
              className={`px-2 py-1 text-xs rounded ${
                timeframe === tf ? 'bg-indigo-600 text-white' : 'bg-gray-800 text-gray-400 hover:bg-gray-700'
              }`}
            >
              {tf}
            </button>
          ))}
        </div>
      </div>

      {loading ? (
        <div className="h-48 animate-pulse bg-gray-800 rounded" />
      ) : (
        <ResponsiveContainer width="100%" height={200}>
          <LineChart data={data}>
            <XAxis dataKey="timestamp" tick={{ fontSize: 10 }} stroke="#4b5563" />
            <YAxis tick={{ fontSize: 10 }} stroke="#4b5563" tickFormatter={v => `$${v}`} />
            <Tooltip
              contentStyle={{ backgroundColor: '#1f2937', border: '1px solid #374151' }}
              labelStyle={{ color: '#9ca3af' }}
            />
            <Legend />
            <Line type="monotone" dataKey="nav_usd" name="Basket NAV" stroke="#6366f1" dot={false} strokeWidth={2} />
            <Line type="monotone" dataKey="btc_benchmark" name="BTC" stroke="#f97316" dot={false} strokeWidth={1} opacity={0.5} />
            <Line type="monotone" dataKey="eth_benchmark" name="ETH" stroke="#8b5cf6" dot={false} strokeWidth={1} opacity={0.5} />
          </LineChart>
        </ResponsiveContainer>
      )}

      {data.length > 0 && (
        <div className="grid grid-cols-4 gap-4 mt-4 text-sm">
          <Stat label="Total Invested" value={`$${data[0]?.nav_usd?.toFixed(2) || '0'}`} />
          <Stat label="Current Value" value={`$${data[data.length - 1]?.nav_usd?.toFixed(2) || '0'}`} />
          <Stat
            label="P&L"
            value={`${((data[data.length - 1]?.nav_usd / data[0]?.nav_usd - 1) * 100).toFixed(1)}%`}
            positive={(data[data.length - 1]?.nav_usd || 0) >= (data[0]?.nav_usd || 0)}
          />
          <Stat label="Fees Collected" value="$0.00" />
        </div>
      )}
    </div>
  );
};

const Stat: React.FC<{ label: string; value: string; positive?: boolean }> = ({ label, value, positive }) => (
  <div>
    <div className="text-gray-400">{label}</div>
    <div className={`font-bold ${positive === false ? 'text-red-400' : positive ? 'text-green-400' : 'text-white'}`}>
      {value}
    </div>
  </div>
);
```

#### 6.1.4 Token Trajectories

```typescript
// frontend/src/components/investments/TokenTrajectories.tsx

import React, { useState } from 'react';
import { Sparklines, SparklinesLine } from 'react-sparklines';

interface Token {
  symbol: string;
  weight: number;
  price_usd: number;
  change_24h: number;
  value_usd: number;
}

export const TokenTrajectories: React.FC<{ tokens: Token[] }> = ({ tokens }) => {
  const [sortBy, setSortBy] = useState<'weight' | 'change_24h'>('weight');
  
  const sorted = [...tokens].sort((a, b) => 
    sortBy === 'weight' ? b.weight - a.weight : b.change_24h - a.change_24h
  );

  return (
    <div className="bg-gray-900 rounded-lg p-4 border border-gray-800">
      <div className="flex justify-between items-center mb-3">
        <h2 className="text-lg font-bold text-white">Token Trajectories</h2>
        <div className="flex gap-2 text-xs">
          <button onClick={() => setSortBy('weight')} className={sortBy === 'weight' ? 'text-indigo-400' : 'text-gray-400'}>By Weight</button>
          <button onClick={() => setSortBy('change_24h')} className={sortBy === 'change_24h' ? 'text-indigo-400' : 'text-gray-400'}>By 24h Change</button>
        </div>
      </div>
      <div className="grid grid-cols-4 gap-3">
        {sorted.map(token => (
          <div key={token.symbol} className="bg-gray-800 rounded-lg p-3">
            <div className="flex justify-between items-center mb-1">
              <span className="text-white font-medium text-sm">{token.symbol}</span>
              <span className={`text-xs ${token.change_24h >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                {token.change_24h >= 0 ? '+' : ''}{token.change_24h.toFixed(1)}%
              </span>
            </div>
            <div className="text-gray-400 text-xs mb-2">${token.price_usd.toFixed(4)} · {(token.weight * 100).toFixed(1)}%</div>
            <Sparklines data={[1, 1.02, 0.98, 1.01, 1.03, 1 + token.change_24h / 100]} height={30}>
              <SparklinesLine color={token.change_24h >= 0 ? '#4ade80' : '#f87171'} />
            </Sparklines>
          </div>
        ))}
      </div>
    </div>
  );
};
```

#### 6.1.5 Agent Consensus Log

```typescript
// frontend/src/components/investments/AgentConsensusLog.tsx

import React, { useEffect, useState } from 'react';

interface Decision {
  id: number;
  action: string;
  trader_confidence: number;
  trader_reasoning: string;
  risk_approved: boolean;
  debate_rounds: number;
  bull_thesis: { confidence: number; thesis: string };
  bear_thesis: { confidence: number; thesis: string };
  created_at: string;
}

const ACTION_COLORS: Record<string, string> = {
  REBALANCE: 'text-yellow-400 bg-yellow-400/10',
  HOLD: 'text-green-400 bg-green-400/10',
  EMERGENCY_EXIT: 'text-red-400 bg-red-400/10',
};

export const AgentConsensusLog: React.FC = () => {
  const [decisions, setDecisions] = useState<Decision[]>([]);
  const [expanded, setExpanded] = useState<number | null>(null);

  useEffect(() => {
    fetch('/api/investments/agents/logs?limit=20')
      .then(r => r.json())
      .then(d => setDecisions(d.data));
  }, []);

  return (
    <div className="bg-gray-900 rounded-lg p-4 border border-gray-800 max-h-96 overflow-y-auto">
      <h2 className="text-lg font-bold text-white mb-3">Agent Consensus Log</h2>
      <div className="space-y-2">
        {decisions.map(d => (
          <div key={d.id} className="bg-gray-800 rounded-lg p-3 cursor-pointer" onClick={() => setExpanded(expanded === d.id ? null : d.id)}>
            <div className="flex justify-between items-center">
              <div className="flex items-center gap-2">
                <span className={`px-2 py-0.5 rounded text-xs font-medium ${ACTION_COLORS[d.action] || 'text-gray-400'}`}>
                  {d.action}
                </span>
                <span className="text-gray-400 text-xs">
                  {new Date(d.created_at).toLocaleString()}
                </span>
              </div>
              <span className="text-xs text-gray-400">
                {(d.trader_confidence * 100).toFixed(0)}% conf · {d.debate_rounds} rounds
              </span>
            </div>
            
            {expanded === d.id && (
              <div className="mt-3 space-y-2 text-sm">
                <div className="text-gray-300">{d.trader_reasoning}</div>
                <div className="grid grid-cols-2 gap-2 mt-2">
                  <div className="bg-green-900/20 rounded p-2">
                    <div className="text-green-400 text-xs font-medium mb-1">🐂 Bull ({(d.bull_thesis?.confidence * 100 || 0).toFixed(0)}%)</div>
                    <div className="text-gray-300 text-xs">{d.bull_thesis?.thesis || 'N/A'}</div>
                  </div>
                  <div className="bg-red-900/20 rounded p-2">
                    <div className="text-red-400 text-xs font-medium mb-1">🐻 Bear ({(d.bear_thesis?.confidence * 100 || 0).toFixed(0)}%)</div>
                    <div className="text-gray-300 text-xs">{d.bear_thesis?.thesis || 'N/A'}</div>
                  </div>
                </div>
                <div className="text-xs">
                  Risk Officer: <span className={d.risk_approved ? 'text-green-400' : 'text-red-400'}>
                    {d.risk_approved ? '✅ Approved' : '❌ Vetoed'}
                  </span>
                </div>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
};
```

#### 6.1.6 Bridge History

```typescript
// frontend/src/components/investments/BridgeHistory.tsx

import React, { useEffect, useState } from 'react';

interface BridgeJob {
  id: number;
  amount_usdc: number;
  state: string;
  burn_tx_hash?: string;
  mint_tx_hash?: string;
  deposit_tx_hash?: string;
  bridge_fee_usdc: number;
  net_deposited_usdc?: number;
  created_at: string;
}

const STATE_COLORS: Record<string, string> = {
  DEPOSITED_TO_POOL: 'text-green-400',
  MINT_CONFIRMED: 'text-blue-400',
  ATTESTATION_PENDING: 'text-yellow-400',
  BURN_CONFIRMED: 'text-yellow-400',
  FAILED: 'text-red-400',
};

export const BridgeHistory: React.FC = () => {
  const [jobs, setJobs] = useState<BridgeJob[]>([]);

  useEffect(() => {
    fetch('/api/investments/bridge/history?limit=20')
      .then(r => r.json())
      .then(d => setJobs(d.data));
  }, []);

  const totalBridged = jobs
    .filter(j => j.state === 'DEPOSITED_TO_POOL')
    .reduce((sum, j) => sum + (j.net_deposited_usdc || 0), 0);

  return (
    <div className="bg-gray-900 rounded-lg p-4 border border-gray-800 max-h-96 overflow-y-auto">
      <h2 className="text-lg font-bold text-white mb-1">Bridge History</h2>
      <div className="text-sm text-gray-400 mb-3">
        Base → Solana · Total bridged: <span className="text-green-400">${totalBridged.toFixed(2)}</span>
      </div>
      <div className="space-y-2">
        {jobs.map(j => (
          <div key={j.id} className="bg-gray-800 rounded p-2 text-xs">
            <div className="flex justify-between">
              <span className="text-white">${j.amount_usdc.toFixed(2)} USDC</span>
              <span className={STATE_COLORS[j.state] || 'text-gray-400'}>
                {j.state.replace(/_/g, ' ')}
              </span>
            </div>
            <div className="text-gray-500 mt-1">
              {new Date(j.created_at).toLocaleString()}
              {j.burn_tx_hash && (
                <a href={`https://basescan.org/tx/${j.burn_tx_hash}`} target="_blank" className="ml-2 text-indigo-400 hover:underline">
                  Base TX ↗
                </a>
              )}
              {j.mint_tx_hash && (
                <a href={`https://solscan.io/tx/${j.mint_tx_hash}`} target="_blank" className="ml-2 text-indigo-400 hover:underline">
                  Solana TX ↗
                </a>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
```

#### 6.1.7 Staking Panel

```typescript
// frontend/src/components/investments/StakingPanel.tsx

import React, { useEffect, useState } from 'react';

interface StakingStatus {
  total_staked: number;
  total_stakers: number;
  reward_vault_balance: number;
  estimated_apy: number;
  user_staked?: number;
  user_claimable?: number;
  user_tier?: string;
  user_multiplier?: number;
}

export const StakingPanel: React.FC = () => {
  const [status, setStatus] = useState<StakingStatus | null>(null);

  useEffect(() => {
    fetch('/api/investments/staking/status')
      .then(r => r.json())
      .then(d => setStatus(d.data));
  }, []);

  if (!status) return <div className="bg-gray-900 rounded-lg p-4 animate-pulse h-80" />;

  return (
    <div className="bg-gray-900 rounded-lg p-4 border border-gray-800">
      <h2 className="text-lg font-bold text-white mb-3">$KR8TIV Staking</h2>
      
      <div className="grid grid-cols-2 gap-3 mb-4">
        <div className="bg-gray-800 rounded p-2">
          <div className="text-gray-400 text-xs">Total Staked</div>
          <div className="text-white font-bold">{status.total_staked.toLocaleString()} KR8TIV</div>
        </div>
        <div className="bg-gray-800 rounded p-2">
          <div className="text-gray-400 text-xs">Stakers</div>
          <div className="text-white font-bold">{status.total_stakers}</div>
        </div>
        <div className="bg-gray-800 rounded p-2">
          <div className="text-gray-400 text-xs">Reward Vault</div>
          <div className="text-green-400 font-bold">${status.reward_vault_balance.toFixed(2)}</div>
        </div>
        <div className="bg-gray-800 rounded p-2">
          <div className="text-gray-400 text-xs">Est. APY</div>
          <div className="text-indigo-400 font-bold">{status.estimated_apy.toFixed(1)}%</div>
        </div>
      </div>

      {/* Tier info */}
      <div className="bg-gray-800 rounded p-3 mb-4">
        <div className="text-xs text-gray-400 mb-2">Lockup Tiers</div>
        <div className="space-y-1 text-xs">
          <div className="flex justify-between"><span className="text-gray-300">Base (0-29d)</span><span className="text-white">1.0x</span></div>
          <div className="flex justify-between"><span className="text-gray-300">Silver (30-89d)</span><span className="text-yellow-400">1.25x</span></div>
          <div className="flex justify-between"><span className="text-gray-300">Gold (90d+)</span><span className="text-yellow-300">1.5x</span></div>
        </div>
      </div>

      {/* User position (if connected) */}
      {status.user_staked !== undefined && (
        <div className="bg-indigo-900/20 border border-indigo-800 rounded p-3 mb-3">
          <div className="text-xs text-gray-400 mb-1">Your Position</div>
          <div className="text-white font-bold">{status.user_staked.toLocaleString()} KR8TIV</div>
          <div className="text-xs text-gray-400">
            Tier: {status.user_tier} · Multiplier: {status.user_multiplier}x
          </div>
          <div className="text-green-400 font-bold mt-1">
            Claimable: ${status.user_claimable?.toFixed(4)} USDC
          </div>
          <button className="mt-2 w-full bg-green-600 hover:bg-green-700 text-white rounded py-1.5 text-sm font-medium">
            Claim Rewards
          </button>
        </div>
      )}
    </div>
  );
};
```

#### 6.1.8 Investment Interface

```typescript
// frontend/src/components/investments/InvestmentInterface.tsx

import React, { useState } from 'react';

export const InvestmentInterface: React.FC = () => {
  const [isOpen, setIsOpen] = useState(false);
  const [amount, setAmount] = useState('');
  const [mode, setMode] = useState<'invest' | 'withdraw'>('invest');

  if (!isOpen) {
    return (
      <button
        onClick={() => setIsOpen(true)}
        className="fixed bottom-6 right-6 bg-indigo-600 hover:bg-indigo-700 text-white rounded-full px-6 py-3 font-medium shadow-lg"
      >
        💰 Invest / Withdraw
      </button>
    );
  }

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-gray-900 rounded-xl p-6 w-96 border border-gray-700">
        <div className="flex justify-between items-center mb-4">
          <h2 className="text-lg font-bold text-white">
            {mode === 'invest' ? 'Invest in Basket' : 'Withdraw from Basket'}
          </h2>
          <button onClick={() => setIsOpen(false)} className="text-gray-400 hover:text-white">✕</button>
        </div>

        <div className="flex gap-2 mb-4">
          <button
            onClick={() => setMode('invest')}
            className={`flex-1 py-2 rounded text-sm ${mode === 'invest' ? 'bg-green-600 text-white' : 'bg-gray-800 text-gray-400'}`}
          >
            Invest
          </button>
          <button
            onClick={() => setMode('withdraw')}
            className={`flex-1 py-2 rounded text-sm ${mode === 'withdraw' ? 'bg-red-600 text-white' : 'bg-gray-800 text-gray-400'}`}
          >
            Withdraw
          </button>
        </div>

        <div className="mb-4">
          <label className="text-sm text-gray-400 mb-1 block">
            Amount ({mode === 'invest' ? 'ETH' : 'LP Tokens'})
          </label>
          <input
            type="number"
            value={amount}
            onChange={e => setAmount(e.target.value)}
            placeholder="0.0"
            className="w-full bg-gray-800 text-white rounded-lg px-4 py-3 border border-gray-700 focus:border-indigo-500 outline-none"
          />
        </div>

        <button
          className={`w-full py-3 rounded-lg font-medium ${
            mode === 'invest' ? 'bg-green-600 hover:bg-green-700' : 'bg-red-600 hover:bg-red-700'
          } text-white`}
        >
          {mode === 'invest' ? 'Invest ETH' : 'Withdraw'}
        </button>

        <div className="text-xs text-gray-500 mt-3 text-center">
          {mode === 'invest'
            ? 'Calls contribute() on the ERC-7621 basket on Base'
            : 'Burns LP tokens via withdrawETH() for ETH equivalent'}
        </div>
      </div>
    </div>
  );
};
```

#### 6.1.9 WebSocket Hook

```typescript
// frontend/src/hooks/useInvestmentWebSocket.ts

import { useEffect, useRef, useState, useCallback } from 'react';

interface InvestmentWSData {
  basketState: any;
  latestDecision: any;
  bridgeUpdates: any[];
  stakingStatus: any;
}

export function useInvestmentWebSocket(): InvestmentWSData & { connected: boolean } {
  const ws = useRef<WebSocket | null>(null);
  const [connected, setConnected] = useState(false);
  const [data, setData] = useState<InvestmentWSData>({
    basketState: null,
    latestDecision: null,
    bridgeUpdates: [],
    stakingStatus: null,
  });

  useEffect(() => {
    const connect = () => {
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      ws.current = new WebSocket(`${protocol}//${window.location.host}/ws/investments/live`);

      ws.current.onopen = () => setConnected(true);
      ws.current.onclose = () => {
        setConnected(false);
        setTimeout(connect, 3000); // Auto-reconnect
      };

      ws.current.onmessage = (event) => {
        const msg = JSON.parse(event.data);
        setData(prev => {
          switch (msg.type) {
            case 'basket_state':
              return { ...prev, basketState: msg.data };
            case 'decision':
              return { ...prev, latestDecision: msg.data };
            case 'bridge_update':
              return { ...prev, bridgeUpdates: [msg.data, ...prev.bridgeUpdates].slice(0, 50) };
            case 'staking_status':
              return { ...prev, stakingStatus: msg.data };
            default:
              return prev;
          }
        });
      };
    };

    connect();
    return () => ws.current?.close();
  }, []);

  return { ...data, connected };
}
```

---

## 7. API Endpoints

### 7.1 REST Endpoints

```python
# api/routes/investments.py

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket
from typing import Optional
import json

router = APIRouter(prefix="/api/investments", tags=["investments"])

# ---- Basket ----

@router.get("/basket")
async def get_basket(db=Depends(get_db)):
    """Current basket composition, NAV, weights."""
    row = await db.fetchrow("""
        SELECT data FROM inv_basket_snapshots ORDER BY created_at DESC LIMIT 1
    """)
    return {"data": json.loads(row["data"]) if row else None}

# ---- Performance ----

@router.get("/performance")
async def get_performance(
    timeframe: str = Query("1M", regex="^(1D|1W|1M|3M|ALL)$"),
    db=Depends(get_db),
):
    """Historical performance data from TimescaleDB."""
    interval_map = {"1D": "1 day", "1W": "7 days", "1M": "30 days", "3M": "90 days", "ALL": "1000 days"}
    bucket_map = {"1D": "1 hour", "1W": "4 hours", "1M": "1 day", "3M": "1 day", "ALL": "1 week"}
    
    rows = await db.fetch(f"""
        SELECT 
            time_bucket('{bucket_map[timeframe]}', ts) as timestamp,
            AVG(nav_usd) as nav_usd,
            AVG(btc_benchmark) as btc_benchmark,
            AVG(eth_benchmark) as eth_benchmark
        FROM inv_nav_snapshots
        WHERE ts > NOW() - INTERVAL '{interval_map[timeframe]}'
        GROUP BY timestamp
        ORDER BY timestamp ASC
    """)
    return {"data": [dict(r) for r in rows]}

# ---- Token Details ----

@router.get("/tokens/{symbol}")
async def get_token_detail(symbol: str, db=Depends(get_db)):
    """Individual token trajectory data."""
    rows = await db.fetch("""
        SELECT ts, price_usd, volume_24h
        FROM inv_token_prices
        WHERE symbol = $1 AND ts > NOW() - INTERVAL '7 days'
        ORDER BY ts ASC
    """, symbol)
    return {"data": [dict(r) for r in rows]}

# ---- Agent Logs ----

@router.get("/agents/logs")
async def get_agent_logs(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db=Depends(get_db),
):
    """Agent consensus logs with full decision details."""
    rows = await db.fetch("""
        SELECT id, basket_id, trigger_type, action, final_weights, previous_weights,
               basket_nav_usd, bull_thesis, bear_thesis, debate_rounds,
               risk_approved, risk_veto_reason, trader_confidence, trader_reasoning,
               tx_hash, execution_status, created_at
        FROM inv_decisions
        ORDER BY created_at DESC
        LIMIT $1 OFFSET $2
    """, limit, offset)
    return {"data": [dict(r) for r in rows]}

# ---- Bridge History ----

@router.get("/bridge/history")
async def get_bridge_history(
    limit: int = Query(20, ge=1, le=100),
    db=Depends(get_db),
):
    """Bridge transaction history + status."""
    rows = await db.fetch("""
        SELECT id, amount_usdc, state, burn_tx_hash, mint_tx_hash, deposit_tx_hash,
               bridge_fee_usdc, gas_cost_usd, net_deposited_usdc, error, retry_count,
               created_at, updated_at
        FROM inv_bridge_jobs
        ORDER BY created_at DESC
        LIMIT $1
    """, limit)
    return {"data": [dict(r) for r in rows]}

@router.post("/bridge/trigger")
async def trigger_bridge(
    amount_usdc: float,
    admin_key: str = Depends(verify_admin),
    bridge=Depends(get_bridge_controller),
):
    """Manual bridge trigger (admin only)."""
    job_id = await bridge.initiate_bridge(amount_usdc)
    return {"job_id": job_id, "status": "initiated"}

# ---- Staking ----

@router.get("/staking/status")
async def get_staking_status(
    user_address: Optional[str] = None,
    db=Depends(get_db),
):
    """Pool TVL, APY, user rewards."""
    pool = await db.fetchrow("SELECT * FROM inv_staking_pool_snapshots ORDER BY created_at DESC LIMIT 1")
    
    result = {
        "total_staked": pool["total_staked"] if pool else 0,
        "total_stakers": pool["total_stakers"] if pool else 0,
        "reward_vault_balance": pool["reward_vault_balance"] if pool else 0,
        "estimated_apy": pool["estimated_apy"] if pool else 0,
    }
    
    if user_address:
        user = await db.fetchrow(
            "SELECT * FROM inv_staking_entries WHERE owner = $1", user_address
        )
        if user:
            result.update({
                "user_staked": user["amount"],
                "user_claimable": user["pending_rewards"],
                "user_tier": user["tier"],
                "user_multiplier": user["multiplier"],
            })
    
    return {"data": result}

# ---- Kill Switch ----

@router.post("/kill-switch")
async def toggle_kill_switch(
    enabled: bool,
    admin_key: str = Depends(verify_admin),
    redis=Depends(get_redis),
):
    """Toggle the kill switch."""
    await redis.set("inv:kill_switch", "true" if enabled else "false")
    return {"kill_switch": enabled}
```

### 7.2 WebSocket Endpoint

```python
# api/routes/investments_ws.py

from fastapi import WebSocket, WebSocketDisconnect
import asyncio
import json

class InvestmentWSManager:
    """Manages WebSocket connections for real-time investment updates."""
    
    def __init__(self):
        self.connections: list[WebSocket] = []
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.connections.append(websocket)
    
    def disconnect(self, websocket: WebSocket):
        self.connections.remove(websocket)
    
    async def broadcast(self, message_type: str, data: dict):
        msg = json.dumps({"type": message_type, "data": data})
        dead = []
        for conn in self.connections:
            try:
                await conn.send_text(msg)
            except:
                dead.append(conn)
        for d in dead:
            self.connections.remove(d)

ws_manager = InvestmentWSManager()

async def investment_ws_endpoint(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        while True:
            # Keep connection alive, handle client messages if needed
            data = await websocket.receive_text()
            # Client can request specific data
            msg = json.loads(data)
            if msg.get("type") == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
```

### 7.3 Register Routes

```python
# Add to api/server.py

from api.routes.investments import router as investments_router
from api.routes.investments_ws import investment_ws_endpoint

app.include_router(investments_router)
app.add_api_websocket_route("/ws/investments/live", investment_ws_endpoint)
```

---

## 8. Circuit Breakers & Safety

### 8.1 Five-Layer Safety System

```python
# services/investments/safety.py

import logging
from datetime import datetime, timezone

logger = logging.getLogger("investments.safety")

class SafetySystem:
    """Five-layer safety system for autonomous investment operations.
    
    Layer 1: Portfolio Guard — position limits
    Layer 2: Loss Limiter — drawdown protection
    Layer 3: Bridge Limiter — transfer caps
    Layer 4: Kill Switch — immediate halt
    Layer 5: Idempotency Guard — prevent double-execution
    """
    
    def __init__(self, db_pool, redis):
        self.db = db_pool
        self.redis = redis
    
    # ---- Layer 1: Portfolio Guard ----
    
    async def check_portfolio_limits(self, proposed_weights: dict, current_weights: dict, nav_usd: float) -> tuple[bool, str]:
        """Check position limits before any rebalance.
        
        Rules:
        - No single token > 30% weight
        - Single rebalance max 25% of basket value
        - No more than 4 tokens removed or added per rebalance
        - ALVA must remain >= 5%
        """
        for token, weight in proposed_weights.items():
            if weight > 0.30:
                return False, f"{token} weight {weight:.0%} exceeds 30% limit"
        
        if proposed_weights.get("ALVA", 0) < 0.05:
            return False, "ALVA weight below 5% minimum"
        
        total_change = sum(
            abs(proposed_weights.get(t, 0) - current_weights.get(t, 0))
            for t in set(list(proposed_weights) + list(current_weights))
        ) / 2
        if total_change > 0.25:
            return False, f"Total change {total_change:.0%} exceeds 25% per-rebalance limit"
        
        added = set(proposed_weights) - set(current_weights)
        removed = set(current_weights) - set(proposed_weights)
        if len(added) + len(removed) > 4:
            return False, f"Too many token changes: {len(added)} added + {len(removed)} removed > 4 max"
        
        return True, ""
    
    # ---- Layer 2: Loss Limiter ----
    
    async def check_loss_limits(self) -> tuple[bool, str]:
        """Check if basket has breached loss thresholds.
        
        Rules:
        - If NAV drops >15% in 24h → enter HOLD-only mode
        - If NAV drops >10% in 4h → trigger event review (handled by scheduler)
        - Requires manual re-enable after 15% halt
        """
        halted = await self.redis.get("inv:loss_halt")
        if halted and halted.decode() == "true":
            return False, "Loss limiter active: NAV dropped >15% in 24h. Manual re-enable required."
        
        row = await self.db.fetchrow("""
            SELECT 
                FIRST(nav_usd, ts) as nav_24h_ago,
                LAST(nav_usd, ts) as nav_now
            FROM inv_nav_snapshots
            WHERE ts > NOW() - INTERVAL '24 hours'
        """)
        
        if row and row["nav_24h_ago"] and row["nav_24h_ago"] > 0:
            change = (row["nav_now"] - row["nav_24h_ago"]) / row["nav_24h_ago"]
            if change < -0.15:
                await self.redis.set("inv:loss_halt", "true")
                await self._alert(f"🚨 LOSS HALT: NAV dropped {change:.1%} in 24h. All operations halted.")
                return False, f"NAV dropped {change:.1%} in 24h — operations halted"
        
        return True, ""
    
    # ---- Layer 3: Bridge Limiter ----
    
    async def check_bridge_limits(self, amount_usdc: float) -> tuple[bool, str]:
        """Check bridge transfer limits.
        
        Rules:
        - Max $50,000 per 24h
        - Single transfer max $10,000
        """
        if amount_usdc > 10_000:
            return False, f"Single bridge ${amount_usdc} exceeds $10,000 limit"
        
        row = await self.db.fetchrow("""
            SELECT COALESCE(SUM(amount_usdc), 0) as total
            FROM inv_bridge_jobs
            WHERE created_at > NOW() - INTERVAL '24 hours'
            AND state NOT IN ('FAILED', 'CANCELLED')
        """)
        
        daily_total = float(row["total"])
        if daily_total + amount_usdc > 50_000:
            return False, f"Daily bridge total ${daily_total + amount_usdc:.2f} would exceed $50,000 limit"
        
        return True, ""
    
    # ---- Layer 4: Kill Switch ----
    
    async def is_killed(self) -> bool:
        """Check if kill switch is active."""
        val = await self.redis.get("inv:kill_switch")
        return val and val.decode() == "true"
    
    async def activate_kill_switch(self, reason: str):
        """Activate kill switch — halts ALL operations."""
        await self.redis.set("inv:kill_switch", "true")
        await self._alert(f"🛑 KILL SWITCH ACTIVATED: {reason}")
        logger.critical(f"Kill switch activated: {reason}")
    
    async def deactivate_kill_switch(self):
        """Deactivate kill switch — resume operations."""
        await self.redis.set("inv:kill_switch", "false")
        await self._alert("✅ Kill switch deactivated. Operations resumed.")
    
    # ---- Layer 5: Idempotency Guard ----
    
    async def check_idempotency(self, operation_key: str) -> bool:
        """Prevent double-execution of the same operation.
        
        Uses Redis SET NX with 1-hour TTL.
        Returns True if operation is safe to proceed (not already running).
        """
        result = await self.redis.set(
            f"inv:idempotency:{operation_key}",
            "running",
            nx=True,
            ex=3600,
        )
        return result is not None
    
    async def clear_idempotency(self, operation_key: str):
        """Clear idempotency lock after operation completes."""
        await self.redis.delete(f"inv:idempotency:{operation_key}")
    
    # ---- Telegram Alerts ----
    
    async def _alert(self, message: str):
        """Send alert via Telegram."""
        await self.redis.publish("telegram:alerts", message)
        logger.warning(f"Safety alert: {message}")
```

### 8.2 Telegram Bot Commands

```python
# tg_bot/handlers/investments.py

async def handle_kill_investments(update, context):
    """/kill_investments — Activate kill switch."""
    await redis.set("inv:kill_switch", "true")
    await update.message.reply_text("🛑 Investment kill switch ACTIVATED. All operations halted.")

async def handle_resume_investments(update, context):
    """/resume_investments — Deactivate kill switch."""
    await redis.set("inv:kill_switch", "false")
    await redis.delete("inv:loss_halt")
    await update.message.reply_text("✅ Investment operations resumed.")

async def handle_invest_status(update, context):
    """/invest_status — Quick status summary."""
    # Fetch latest data
    basket = await db.fetchrow("SELECT data FROM inv_basket_snapshots ORDER BY created_at DESC LIMIT 1")
    decision = await db.fetchrow("SELECT action, trader_confidence, created_at FROM inv_decisions ORDER BY created_at DESC LIMIT 1")
    bridge = await db.fetchrow("SELECT COUNT(*), SUM(amount_usdc) FROM inv_bridge_jobs WHERE state = 'DEPOSITED_TO_POOL'")
    
    kill = await redis.get("inv:kill_switch")
    loss_halt = await redis.get("inv:loss_halt")
    
    status = "🟢 Active"
    if kill and kill.decode() == "true":
        status = "🔴 KILLED"
    elif loss_halt and loss_halt.decode() == "true":
        status = "🟡 LOSS HALT"
    
    msg = f"""📊 Investment Status: {status}

NAV: ${basket['data']['nav_usd'] if basket else 'N/A'}
Last Decision: {decision['action'] if decision else 'N/A'} ({decision['trader_confidence']*100:.0f}% conf)
Bridges Completed: {bridge[0] if bridge else 0} (${bridge[1] or 0:.2f} total)
"""
    await update.message.reply_text(msg)

async def handle_bridge_trigger(update, context):
    """/bridge_trigger <amount> — Manual bridge trigger."""
    # Parse amount from command
    args = context.args
    if not args:
        await update.message.reply_text("Usage: /bridge_trigger <amount_usdc>")
        return
    amount = float(args[0])
    # Trigger bridge
    await update.message.reply_text(f"🌉 Bridge initiated: ${amount:.2f} USDC Base→Solana")
```

---

## 9. Infrastructure & Deployment

### 9.1 Docker Compose

```yaml
# docker-compose.investments.yml
# Extends existing Jarvis docker-compose

version: '3.8'

services:
  investment-orchestrator:
    build:
      context: .
      dockerfile: services/investments/Dockerfile
    container_name: jarvis-investments
    environment:
      - DATABASE_URL=postgresql://jarvis:${DB_PASSWORD}@postgres:5432/jarvis
      - REDIS_URL=redis://redis:6379
      - XAI_API_KEY=${XAI_API_KEY}
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - BASE_RPC_URL=${BASE_RPC_URL}
      - SOLANA_RPC_URL=${SOLANA_RPC_URL}
      - MANAGEMENT_WALLET_KEY=${MANAGEMENT_WALLET_KEY}
      - SOLANA_WALLET_KEY=${SOLANA_WALLET_KEY}
      - BASKET_ADDRESS=${BASKET_ADDRESS}
      - BIRDEYE_API_KEY=${BIRDEYE_API_KEY}
      - STAKING_POOL_ADDRESS=${STAKING_POOL_ADDRESS}
      - TELEGRAM_BOT_TOKEN=${TELEGRAM_BOT_TOKEN}
      - TELEGRAM_ADMIN_CHAT_ID=${TELEGRAM_ADMIN_CHAT_ID}
    depends_on:
      - postgres
      - redis
    restart: unless-stopped
    mem_limit: 2g
    networks:
      - jarvis-net

  investment-cranker:
    build:
      context: .
      dockerfile: services/investments/Dockerfile.cranker
    container_name: jarvis-cranker
    environment:
      - DATABASE_URL=postgresql://jarvis:${DB_PASSWORD}@postgres:5432/jarvis
      - REDIS_URL=redis://redis:6379
      - SOLANA_RPC_URL=${SOLANA_RPC_URL}
      - SOLANA_WALLET_KEY=${SOLANA_WALLET_KEY}
      - STAKING_POOL_ADDRESS=${STAKING_POOL_ADDRESS}
    depends_on:
      - postgres
      - redis
    restart: unless-stopped
    mem_limit: 512m
    networks:
      - jarvis-net

networks:
  jarvis-net:
    external: true
```

### 9.2 Dockerfile

```dockerfile
# services/investments/Dockerfile

FROM python:3.12-slim

WORKDIR /app

COPY requirements-investments.txt .
RUN pip install --no-cache-dir -r requirements-investments.txt

COPY services/investments/ ./services/investments/
COPY api/ ./api/
COPY core/ ./core/

CMD ["python", "-m", "services.investments.main"]
```

### 9.3 Requirements

```txt
# requirements-investments.txt

# Web framework (already in Jarvis)
fastapi>=0.115.0
uvicorn>=0.30.0

# Database
asyncpg>=0.30.0
aioredis>=2.0.0

# LLM clients
anthropic>=0.40.0
openai>=1.50.0
httpx>=0.27.0

# EVM
web3>=7.0.0
eth-account>=0.13.0

# Solana
solders>=0.21.0
solana>=0.35.0

# Scheduling
apscheduler>=3.10.0

# Utils
pydantic>=2.0.0
python-dotenv>=1.0.0
```

### 9.4 Environment Variables

```bash
# .env additions for investments

# Investment System
INVESTMENT_ENABLED=true

# Base (EVM) — use Alchemy, Infura, or public RPC
BASE_RPC_URL=https://mainnet.base.org
# Or: https://base-mainnet.g.alchemy.com/v2/YOUR_KEY

# Management wallet (Base) — holds ERC-721 management NFT
MANAGEMENT_WALLET_KEY=  # Private key, hex encoded

# Alvara basket address on Base
BASKET_ADDRESS=0x...

# Solana
SOLANA_RPC_URL=https://mainnet.helius-rpc.com/?api-key=YOUR_KEY
SOLANA_WALLET_KEY=  # Base58 encoded keypair

# Staking pool
STAKING_POOL_ADDRESS=  # Solana program ID
AUTHORITY_REWARD_ACCOUNT=  # Authority's USDC token account on Solana

# LLM Keys (likely already set)
XAI_API_KEY=
ANTHROPIC_API_KEY=
OPENAI_API_KEY=

# Price feeds (likely already set)
BIRDEYE_API_KEY=

# Telegram (likely already set)
TELEGRAM_BOT_TOKEN=
TELEGRAM_ADMIN_CHAT_ID=
```

### 9.5 Database Migrations (Complete)

```sql
-- services/investments/migrations/000_setup.sql

-- NAV time-series (TimescaleDB hypertable)
CREATE TABLE inv_nav_snapshots (
    ts TIMESTAMPTZ NOT NULL,
    basket_id VARCHAR(64) NOT NULL DEFAULT 'alpha',
    nav_usd NUMERIC(18, 2) NOT NULL,
    btc_benchmark NUMERIC(18, 2),
    eth_benchmark NUMERIC(18, 2)
);
SELECT create_hypertable('inv_nav_snapshots', 'ts');
CREATE INDEX idx_inv_nav_basket ON inv_nav_snapshots(basket_id, ts DESC);

-- Token prices (TimescaleDB hypertable)
CREATE TABLE inv_token_prices (
    ts TIMESTAMPTZ NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    address VARCHAR(64),
    price_usd NUMERIC(24, 8) NOT NULL,
    volume_24h NUMERIC(24, 2)
);
SELECT create_hypertable('inv_token_prices', 'ts');
CREATE INDEX idx_inv_token_symbol ON inv_token_prices(symbol, ts DESC);

-- Basket snapshots (full state cache)
CREATE TABLE inv_basket_snapshots (
    id SERIAL PRIMARY KEY,
    basket_id VARCHAR(64) NOT NULL DEFAULT 'alpha',
    data JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Basket events from on-chain
CREATE TABLE inv_basket_events (
    id SERIAL PRIMARY KEY,
    basket_address VARCHAR(64) NOT NULL,
    block_number BIGINT NOT NULL,
    tx_hash VARCHAR(128) NOT NULL,
    event_data JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Fee collections
CREATE TABLE inv_fee_collections (
    id SERIAL PRIMARY KEY,
    basket_id VARCHAR(64) NOT NULL DEFAULT 'alpha',
    fee_amount_usdc NUMERIC(18, 6) NOT NULL,
    nav_at_collection NUMERIC(18, 2),
    bridged BOOLEAN DEFAULT FALSE,
    bridge_job_id INTEGER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Staking deposits (from cranker)
CREATE TABLE inv_staking_deposits (
    id SERIAL PRIMARY KEY,
    amount_raw BIGINT NOT NULL,
    amount_usdc NUMERIC(18, 6) NOT NULL,
    tx_hash VARCHAR(128),
    status VARCHAR(32) NOT NULL DEFAULT 'pending',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Staking pool snapshots (for dashboard)
CREATE TABLE inv_staking_pool_snapshots (
    id SERIAL PRIMARY KEY,
    total_staked BIGINT DEFAULT 0,
    total_stakers INTEGER DEFAULT 0,
    reward_vault_balance NUMERIC(18, 6) DEFAULT 0,
    estimated_apy NUMERIC(8, 2) DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Staking entries (mirror of on-chain for fast queries)
CREATE TABLE inv_staking_entries (
    owner VARCHAR(64) PRIMARY KEY,
    amount BIGINT DEFAULT 0,
    pending_rewards BIGINT DEFAULT 0,
    stake_timestamp BIGINT,
    tier VARCHAR(16),
    multiplier NUMERIC(4, 2),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

---

## 10. File Structure

```
C:\Users\lucid\Desktop\Jarvis\
├── services/
│   └── investments/
│       ├── __init__.py
│       ├── main.py                          # Entry point — starts orchestrator + scheduler
│       ├── config.py                        # InvestmentConfig dataclass
│       ├── orchestrator.py                  # Master orchestrator (Section 2.8)
│       ├── scheduler.py                     # APScheduler + event triggers (Section 2.9)
│       ├── alvara_manager.py                # ERC-7621 basket management (Section 3.1)
│       ├── event_monitor.py                 # On-chain event monitoring (Section 3.2)
│       ├── bridge_controller.py             # CCTP bridge state machine (Section 4.2)
│       ├── bridge_trigger.py                # Bridge threshold logic (Section 4.4)
│       ├── staking_cranker.py               # Solana reward deposit automation (Section 5.3)
│       ├── safety.py                        # 5-layer safety system (Section 8.1)
│       ├── agents/
│       │   ├── __init__.py
│       │   ├── grok_agent.py                # Grok sentiment analyst (Section 2.2.1)
│       │   ├── claude_agent.py              # Claude risk analyst (Section 2.2.2)
│       │   ├── chatgpt_agent.py             # ChatGPT macro analyst (Section 2.2.3)
│       │   └── dexter_agent.py              # Dexter fundamental analyst (Section 2.2.4)
│       ├── consensus/
│       │   ├── __init__.py
│       │   ├── debate.py                    # Bull/bear adversarial debate (Section 2.3)
│       │   ├── risk_officer.py              # Risk veto system (Section 2.4)
│       │   ├── trader.py                    # Final trade decision (Section 2.5)
│       │   └── reflection.py                # Post-trade reflection (Section 2.6)
│       ├── migrations/
│       │   ├── 000_setup.sql                # Core tables + hypertables (Section 9.5)
│       │   ├── 001_agent_tables.sql         # Decision + reflection tables (Section 2.7)
│       │   └── 002_bridge_tables.sql        # Bridge job tables (Section 4.3)
│       ├── Dockerfile
│       ├── Dockerfile.cranker
│       └── requirements-investments.txt
│
├── contracts/
│   └── solana/
│       └── kr8tiv-staking/
│           ├── Anchor.toml                  # Anchor config (Section 5.2)
│           ├── Cargo.toml
│           ├── programs/
│           │   └── kr8tiv-staking/
│           │       ├── Cargo.toml
│           │       └── src/
│           │           └── lib.rs           # Full staking program (Section 5.1)
│           └── tests/
│               └── kr8tiv-staking.ts        # Anchor tests
│
├── frontend/
│   └── src/
│       ├── components/
│       │   └── investments/
│       │       ├── InvestmentDashboard.tsx   # Main container (Section 6.1.1)
│       │       ├── BasketOverview.tsx        # Allocation pie chart (Section 6.1.2)
│       │       ├── PerformanceChart.tsx      # NAV + P&L chart (Section 6.1.3)
│       │       ├── TokenTrajectories.tsx     # Token sparklines (Section 6.1.4)
│       │       ├── AgentConsensusLog.tsx     # Decision history (Section 6.1.5)
│       │       ├── BridgeHistory.tsx         # Bridge timeline (Section 6.1.6)
│       │       ├── StakingPanel.tsx          # Staking status (Section 6.1.7)
│       │       └── InvestmentInterface.tsx   # Invest/withdraw modal (Section 6.1.8)
│       └── hooks/
│           └── useInvestmentWebSocket.ts     # WebSocket hook (Section 6.1.9)
│
├── api/
│   └── routes/
│       ├── investments.py                   # REST endpoints (Section 7.1)
│       └── investments_ws.py                # WebSocket endpoint (Section 7.2)
│
├── tg_bot/
│   └── handlers/
│       └── investments.py                   # Telegram commands (Section 8.2)
│
├── docker-compose.investments.yml           # Docker services (Section 9.1)
└── .env                                     # Environment variables (Section 9.4)
```

---

## 11. Implementation Order

### Day 1 (Hours 1-12): Foundation

| Hour | Task | Files |
|------|------|-------|
| 1-2 | Database migrations — create all tables | `migrations/000_setup.sql`, `001_agent_tables.sql`, `002_bridge_tables.sql` |
| 2-3 | Config + safety system | `config.py`, `safety.py` |
| 3-5 | Agent implementations (all 4 analysts) | `agents/grok_agent.py`, `agents/claude_agent.py`, `agents/chatgpt_agent.py`, `agents/dexter_agent.py` |
| 5-6 | Adversarial debate + risk officer + trader | `consensus/debate.py`, `consensus/risk_officer.py`, `consensus/trader.py` |
| 6-7 | Reflection engine | `consensus/reflection.py` |
| 7-9 | Master orchestrator + scheduler | `orchestrator.py`, `scheduler.py` |
| 9-10 | Alvara manager (ERC-7621 interaction) | `alvara_manager.py`, `event_monitor.py` |
| 10-12 | REST API endpoints | `api/routes/investments.py`, `api/routes/investments_ws.py` |

### Day 1 (Hours 12-16): Bridge + Staking

| Hour | Task | Files |
|------|------|-------|
| 12-14 | Bridge controller (CCTP state machine) | `bridge_controller.py`, `bridge_trigger.py` |
| 14-16 | Solana staking program (Anchor) | `contracts/solana/kr8tiv-staking/programs/kr8tiv-staking/src/lib.rs` |

### Day 2 (Hours 1-8): Frontend

| Hour | Task | Files |
|------|------|-------|
| 1-2 | Dashboard container + WebSocket hook | `InvestmentDashboard.tsx`, `useInvestmentWebSocket.ts` |
| 2-3 | Basket overview + performance chart | `BasketOverview.tsx`, `PerformanceChart.tsx` |
| 3-4 | Token trajectories + agent consensus log | `TokenTrajectories.tsx`, `AgentConsensusLog.tsx` |
| 4-5 | Bridge history + staking panel | `BridgeHistory.tsx`, `StakingPanel.tsx` |
| 5-6 | Investment interface (modal) | `InvestmentInterface.tsx` |
| 6-7 | Telegram handlers | `tg_bot/handlers/investments.py` |
| 7-8 | Staking cranker | `staking_cranker.py` |

### Day 2 (Hours 8-12): Integration + Deploy

| Hour | Task | Files |
|------|------|-------|
| 8-9 | Docker compose + Dockerfiles | `docker-compose.investments.yml`, `Dockerfile`, `Dockerfile.cranker` |
| 9-10 | Main entry point + wiring | `main.py` |
| 10-11 | Integration testing — end-to-end flow | Test scripts |
| 11-12 | Deploy to KVM2, seed with $200, verify | Production deployment |

---

## 12. Acceptance Criteria

### 12.1 Multi-Agent Orchestration

- [ ] All 4 analysts (Grok, Claude, ChatGPT, Dexter) return structured reports without error
- [ ] Bull/bear debate runs 1-3 rounds and produces opposing theses
- [ ] Risk officer VETOES trades exceeding hard limits (30% single token, 25% total change)
- [ ] Risk officer veto forces HOLD regardless of trader decision
- [ ] Trader produces valid action (REBALANCE/HOLD/EMERGENCY_EXIT) with weights summing to 1.0
- [ ] If 2+ agents fail, system defaults to HOLD and logs degradation
- [ ] Full pipeline completes in < 5 minutes
- [ ] All decisions logged to `inv_decisions` with complete audit trail

### 12.2 Reflection & Memory

- [ ] Reflection runs 24-72h after each REBALANCE decision
- [ ] Calibration hints are generated and stored
- [ ] Calibration hints are injected into agent prompts on next cycle
- [ ] Decision log retains last 30 days of entries

### 12.3 Alvara ERC-7621 on Base

- [ ] `get_basket_state()` returns accurate token list, weights, and NAV
- [ ] `execute_rebalance()` submits valid transaction on Base and waits for confirmation
- [ ] ALVA 5% minimum weight enforced at code level
- [ ] Event monitor detects ContributedToBTS, WithdrawnFromBTS, RebalanceBTS events

### 12.4 Cross-Chain Bridge (CCTP)

- [ ] Bridge state machine transitions through all states correctly
- [ ] USDC approved → burned on Base → attestation received → minted on Solana
- [ ] Failed jobs are retryable from last successful state
- [ ] Bridge fee accounting: gross, bridge fees, gas, net deposited — all recorded
- [ ] $50 minimum threshold enforced (Base gas is cheap)
- [ ] $50,000 daily limit enforced
- [ ] Telegram alert on any bridge failure

### 12.5 Solana Staking Pool

- [ ] `initialize_pool` creates pool with correct PDAs
- [ ] `stake` transfers $KR8TIV to vault and creates StakeEntry
- [ ] `deposit_rewards` updates accumulator: `rewards_per_weighted_stake += (amount * 10^18) / total_weighted_stake`
- [ ] `claim_rewards` calculates correct proportional share using accumulator math
- [ ] `unstake` returns tokens + claims all pending rewards
- [ ] Time-weighted multipliers: 1x (0-29d), 1.25x (30-89d), 1.5x (90d+)
- [ ] All arithmetic uses u128 with checked operations (no overflow)
- [ ] Pool can be paused by authority

### 12.6 Dashboard UI

- [ ] Investment tab renders in existing Jarvis layout
- [ ] All 7 panels render with data (or loading states)
- [ ] WebSocket connection auto-reconnects on disconnect
- [ ] Basket pie chart updates in real-time via WebSocket
- [ ] Performance chart supports 5 timeframes (1D/1W/1M/3M/ALL)
- [ ] Agent consensus log shows expandable decision details with bull/bear theses
- [ ] Bridge history links to block explorers (BaseScan, SolScan)
- [ ] Staking panel shows tier multipliers and user position

### 12.7 API

- [ ] All REST endpoints return valid JSON with correct data
- [ ] WebSocket broadcasts basket_state, decision, bridge_update, staking_status events
- [ ] Admin endpoints require authentication
- [ ] Performance endpoint uses TimescaleDB `time_bucket` for efficient aggregation

### 12.8 Safety & Circuit Breakers

- [ ] Kill switch (`/kill_investments`) halts ALL operations within 1 second
- [ ] Loss limiter activates on >15% NAV drop in 24h
- [ ] Portfolio guard blocks single-token weights > 30%
- [ ] Bridge limiter enforces $50,000/day cap
- [ ] Idempotency guard prevents double-execution of same operation
- [ ] All safety events trigger Telegram alerts

### 12.9 Infrastructure

- [ ] Docker containers start and connect to existing PostgreSQL/Redis
- [ ] Total memory usage < 3GB (fits within KVM2 4GB container limit with headroom)
- [ ] Services auto-restart on failure
- [ ] All environment variables documented and required

---

## Appendix A: Key Technical Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Chain for basket | **Base** (not Ethereum mainnet) | Gas ~$0.50 vs $20-50; min profitable TVL ~$5k vs $50k |
| Bridge | **Circle CCTP** (primary) | Zero exploits, native USDC burn/mint, institutional backing |
| Bridge hooks | **NOT atomic** on Solana | CCTP V2 does not auto-execute Solana programs; cranker handles deposit separately |
| Agent structure | **Pipeline** (not flat voting) | Adversarial tension + risk separation produces better decisions |
| Staking math | **Accumulator pattern** | O(1) per deposit regardless of staker count |
| Memory | **Lightweight MVP** | 30-day decision log + calibration hints; not full FinMem architecture |
| Key management | **Environment variables** (MVP) | HashiCorp Vault or MPC wallet as post-MVP upgrade |
| Multi-basket | **Architecture supports N, launch with 1** | `basket_id` field everywhere; add baskets without schema changes |

## Appendix B: Cost Estimates (Daily)

| Item | Est. Cost |
|------|-----------|
| Grok x_search + reasoning | ~$1-2 |
| Claude risk analysis | ~$0.50 |
| ChatGPT macro analysis | ~$0.50 |
| Bull/bear debate (3 rounds) | ~$1-2 |
| Risk officer evaluation | ~$0.25 |
| Trader decision | ~$0.50 |
| Reflection | ~$0.25 |
| Base gas (rebalance + bridge) | ~$1-3 |
| Solana tx fees | ~$0.01 |
| **Total daily** | **~$5-10** |

## Appendix C: Risk Matrix

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| Smart contract bug (staking) | Critical | Medium | Anchor framework, u128 checked math, audit before mainnet |
| Bridge failure | High | Low | State machine with retry, fallback to manual deposit |
| AI makes bad trade | High | Medium | 5-layer safety system, 25% max change per cycle, kill switch |
| Management wallet key compromise | Critical | Low | MVP: env vars. Post-MVP: MPC/multisig |
| API provider outage (xAI/Anthropic/OpenAI) | Medium | Medium | Graceful degradation to HOLD when 2+ agents fail |
| Gas spike on Base | Low | Low | 5 gwei ceiling for bridge operations |
| $200 seed capital lost | Medium | Medium | Circuit breakers limit max loss to 15% per day |