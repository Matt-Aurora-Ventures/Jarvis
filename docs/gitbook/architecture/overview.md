# Architecture Overview

Jarvis is built as a **mesh of intelligent layers** working together. This page explains how the system is designed and how data flows through it.

---

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     User Interfaces                          │
│  Telegram │ Web Dashboard │ Voice │ API │ Mobile (future)   │
└────────────┬────────────────────────────────────────────────┘
             │
┌────────────▼────────────────────────────────────────────────┐
│                    Context Engine                            │
│  - Unified state management                                  │
│  - Cross-platform synchronization                            │
│  - User preferences & patterns                               │
└────────────┬────────────────────────────────────────────────┘
             │
┌────────────▼────────────────────────────────────────────────┐
│                  Intelligence Layer                          │
│  GPT-4 │ Claude │ Grok │ LLaMA (local) │ Model Router       │
└────────────┬────────────────────────────────────────────────┘
             │
┌────────────▼────────────────────────────────────────────────┐
│                    Action Domains                            │
│  Trading │ Social │ Productivity │ Devices (future)          │
└────────────┬────────────────────────────────────────────────┘
             │
┌────────────▼────────────────────────────────────────────────┐
│                   External Integrations                      │
│  Solana │ Jupiter │ Helius │ Grok │ APIs                    │
└──────────────────────────────────────────────────────────────┘
```

---

## Core Components

### 1. Supervisor System

**File**: `bots/supervisor.py`

The supervisor orchestrates all bot components with:

- **Auto-restart** with exponential backoff (5s → 300s)
- **Single instance enforcement** (cross-platform file locking)
- **Health monitoring** (60-second interval checks)
- **Graceful shutdown** handling (SIGTERM, SIGINT)

**Managed Components**:
1. Buy Bot (KR8TIV token tracking)
2. Sentiment Reporter (Grok AI, hourly)
3. Twitter Bot (@Jarvis_lifeos)
4. Telegram Bot (@Jarviskr8tivbot)
5. Bags Intel (bags.fm graduation monitoring)
6. Treasury Trading (autonomous execution)

### 2. Context Engine

**Files**: `core/context_loader.py`, `core/context_manager.py`

The context engine maintains a unified view of:
- User preferences and risk tolerance
- Active positions and portfolio state
- Recent market sentiment
- Pending tasks and alerts

**Cross-Session Persistence**:
- `context_manager.json` stores conversation context
- `master_context.json` holds user profile data
- Context preserved across bot restarts

### 3. Intelligence Layer

**File**: `core/providers.py`

Jarvis uses **multiple AI models** optimally routed based on task requirements.

#### Supported Models

| Model | Provider | Use Cases |
|-------|----------|-----------|
| **GPT-4 Turbo** | OpenAI | Complex reasoning, strategy generation |
| **Claude 3.5 Sonnet** | Anthropic | Code generation, long-context tasks |
| **Grok (xAI)** | xAI | Sentiment analysis, market commentary |
| **LLaMA 3.1 70B** | Meta (via Ollama) | Local inference, privacy-sensitive tasks |
| **qwen3-8b** | Qwen (via Ollama) | Fast responses, simple tasks |

#### Routing Logic

```python
if task_type == "trading_decision":
    model = "grok"  # Sentiment-aware
elif task_type == "code_generation":
    model = "claude-3.5-sonnet"  # Best for code
elif task_type == "user_conversation":
    model = "gpt-4-turbo"  # Best general intelligence
elif privacy_required:
    model = "llama-3.1-70b"  # Local, no data leaves device
else:
    model = "qwen3-8b"  # Fast, cheap fallback
```

### 4. Trading Engine

**Files**: `bots/treasury/trading.py`, `bots/treasury/position_manager.py`

The autonomous trading engine executes 81+ strategies:

**Architecture**:
```
Market Data → Sentiment Analysis → Signal Generation → Risk Check → Execution → Monitoring
```

**Risk Management**:
- Max 50 concurrent positions
- 4-tier risk classification (ESTABLISHED, MID, MICRO, SHITCOIN)
- Active stop-loss monitoring (60-second checks)
- Circuit breakers for safety

### 5. Memory System

**Files**: `core/memory/`, `core/memory/auto_import.py`

**Three-Tier Architecture**:

| Tier | Storage | Latency | Purpose |
|------|---------|---------|---------|
| **Hot** | Redis | <1ms | Active session context |
| **Warm** | Qdrant | ~20ms | Semantic retrieval (100+ learnings) |
| **Cold** | PostgreSQL | ~10ms | Persistent conversation history |

**Vector Embeddings**:
- Model: BGE-large-en-v1.5 (1024-dim)
- Indexed: Conversations, decisions, strategies, preferences
- Search: Hybrid RRF (text + vector combined)

---

## Data Flow: Trading Decision

This example shows how a trading decision flows through the system:

```
1. Market Data Ingestion
   ├─► DexScreener (price)
   ├─► Helius (on-chain data)
   └─► Grok (sentiment analysis)

2. Signal Generation
   ├─► 81+ strategies evaluate
   └─► Consensus scoring

3. Risk Check
   ├─► Position limits (max 50)
   ├─► Liquidity check (min $1K volume)
   ├─► Risk tier classification
   └─► Circuit breaker state

4. Execution
   ├─► Jupiter quote request
   ├─► Transaction building
   ├─► Signing (encrypted local wallet)
   └─► Submission (Helius RPC)

5. Monitoring
   ├─► Position tracking in .positions.json
   ├─► Stop loss checks every 60 seconds
   └─► Performance logging to PostgreSQL

6. Learning
   ├─► Outcome recorded to memory
   ├─► Strategy performance updated
   └─► Learnings stored for future decisions
```

---

## Component Interaction

```
┌──────────────┐
│  Supervisor  │ ◄────── Health Checks ──────┐
└──────┬───────┘                              │
       │                                      │
       ├──► Buy Bot (KR8TIV tracking)        │
       ├──► Sentiment Reporter (Grok)        │
       ├──► Twitter Bot (autonomous)     ────┘
       ├──► Telegram Bot (UI)
       ├──► Bags Intel (graduations)
       └──► Trading Engine (treasury)
                  │
                  ├──► Position Manager
                  ├──► Risk Manager
                  ├──► Execution Engine (Jupiter)
                  └──► Performance Tracker
```

---

## State Files

| File | Format | Contents | Location |
|------|--------|----------|----------|
| `state.json` | JSON | Runtime state: PID, voice/hotkey status, last report | `logs/state.json` |
| `.positions.json` | JSON | Active treasury positions with entry/exit data | `bots/treasury/.positions.json` |
| `recent.jsonl` | JSONL | Recent memory entries (cap: 50-300) | `memory/recent.jsonl` |
| `sentiment_report_data.json` | JSON | Latest Grok sentiment analysis | `bots/twitter/sentiment_report_data.json` |
| `.recent_graduations.json` | JSON | Bags.fm token graduations | `bots/bags_intel/.recent_graduations.json` |
| `master_context.json` | JSON | User profile and preferences | `lifeos/context/master_context.json` |

---

## Background Loops & Timers

| Component | File | Interval | Purpose |
|-----------|------|----------|---------|
| **Supervisor Loop** | supervisor.py:174-205 | 5 seconds | Orchestrates scheduled reports, interview check-ins |
| **Sentiment Reporter** | sentiment_report.py | 15 minutes | Grok AI sentiment analysis |
| **TP/SL Monitoring** | bot.py | 5 minutes | Take-profit/stop-loss checks |
| **Health Monitor** | supervisor.py | 60 seconds | Component health checks |
| **Buy Bot** | buy_tracker/bot.py | Real-time | KR8TIV transaction monitoring |
| **Twitter Poster** | autonomous_engine.py | Variable | Autonomous posting based on sentiment |
| **Bags Intel** | bags_intel_bot.py | Real-time | WebSocket monitoring for graduations |

---

## Distributed Architecture (Future)

For production scaling beyond a single server, Jarvis includes a **distributed multi-agent architecture** designed to scale from a single 32GB VPS to multi-node clusters serving millions of users.

**Key Features**:
- **LangGraph supervisor** for agent orchestration with HITL approval
- **NATS JetStream** for sub-millisecond inter-agent messaging
- **Ollama + LiteLLM** for local inference with cloud failover
- **Hybrid storage**: Redis (hot), Qdrant (vector), PostgreSQL (persistent)
- **Horizontal scaling**: Phase 1 (1 VPS) → Phase 4 (Multi-cloud)

**Scaling Phases**:

| Phase | Infrastructure | Users | Cost/Month |
|-------|---------------|-------|------------|
| **1: Single VPS** | 32GB/8vCPU | 1K-10K | $70-100 |
| **2: Dual VPS** | 2× VPS + k3s | 10K-50K | $85-130 |
| **3: Multi-Node** | 3-5 VPS + Managed DB | 50K-200K | $150-300 |
| **4: Cloud Hybrid** | VPS + Cloud Burst | 200K-1M+ | $300-1K |

Full details: [Distributed Multi-Agent Architecture](../../architecture/DISTRIBUTED_MULTI_AGENT_ARCHITECTURE.md)

---

## MCP Integration

Jarvis uses **18 Model Context Protocols (MCPs)** for extended capabilities:

| MCP | Purpose |
|-----|---------|
| **ast-grep** | 20x faster code pattern search |
| **nia** | Instant SDK/API documentation |
| **firecrawl** | Website scraping for market data |
| **postgres** | Direct semantic memory queries |
| **perplexity** | Real-time web research |
| **filesystem** | File operations |
| **git** | Version control |
| **github** | Repository management |
| **sqlite** | Local database queries |
| **memory** | Knowledge graph storage |

---

## Next Steps

- **Explore Trading System** → [Trading Overview](../trading/overview.md)
- **Understand Bot Integrations** → [Bots Overview](../bots/overview.md)
- **API Documentation** → [API Reference](../api/endpoints.md)
- **Deep Technical Dive** → [Whitepaper](../../WHITEPAPER.md)
