# Jarvis Architecture

This directory contains comprehensive architecture documentation for the Jarvis/LifeOS system.

## Architecture Documents

| Document | Description |
|----------|-------------|
| **[ARCHITECTURE.md](ARCHITECTURE.md)** | Current system architecture - API layer, bot ecosystem, database schema, monitoring |
| **[DISTRIBUTED_MULTI_AGENT_ARCHITECTURE.md](DISTRIBUTED_MULTI_AGENT_ARCHITECTURE.md)** | Production scaling architecture - multi-agent swarm, distributed deployment, scaling roadmap from 32GB VPS to multi-cloud |
| **[BAGS_INTEGRATION_ARCHITECTURE.md](BAGS_INTEGRATION_ARCHITECTURE.md)** | bags.fm integration architecture |
| **[DASHBOARD_ARCHITECTURE.md](DASHBOARD_ARCHITECTURE.md)** | Web dashboard and data engine architecture |
| **[SYSTEM_AUDIT.md](SYSTEM_AUDIT.md)** | System audit and component analysis |
| **[STRATEGY_LEARNINGS.md](STRATEGY_LEARNINGS.md)** | Trading strategy learnings and patterns |

---

## System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        Frontend (React)                          │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────────┐ │
│  │Dashboard │  │ Trading  │  │   Chat   │  │ Voice Control    │ │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────────┬─────────┘ │
└───────┼─────────────┼─────────────┼──────────────────┼──────────┘
        │             │             │                  │
        └─────────────┴─────────────┴──────────────────┘
                              │
                    ┌─────────▼─────────┐
                    │   Nginx Proxy     │
                    └─────────┬─────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
┌───────▼───────┐   ┌─────────▼─────────┐  ┌───────▼───────┐
│  FastAPI App  │   │  WebSocket Hub    │  │  Legacy Flask │
│  (REST API)   │   │  (Real-time)      │  │  (Migration)  │
└───────┬───────┘   └─────────┬─────────┘  └───────────────┘
        │                     │
        └──────────┬──────────┘
                   │
    ┌──────────────┼──────────────┐
    │              │              │
┌───▼───┐    ┌─────▼─────┐   ┌────▼────┐
│ Redis │    │  SQLite   │   │  Vault  │
│ Cache │    │  Database │   │ Secrets │
└───────┘    └───────────┘   └─────────┘
```

## Core Components

### API Layer (`api/`)
- **fastapi_app.py** - Main FastAPI application
- **middleware/** - Request processing (rate limiting, auth, security headers)
- **auth/** - Authentication (JWT, API keys)
- **routes/** - API endpoints
- **schemas/** - Request/response validation

### Core Layer (`core/`)
- **providers.py** - AI provider integration (OpenAI, Gemini, etc.)
- **trading_pipeline.py** - Trading strategy execution
- **memory.py** - Conversation memory management
- **encryption.py** - Secure storage and encryption

### Security Layer (`core/security/`)
- **sanitizer.py** - Input sanitization
- **session_manager.py** - Session management
- **two_factor.py** - 2FA implementation
- **audit_trail.py** - Security event logging

### Resilience Layer (`core/resilience/`)
- **circuit_breaker.py** - Fault tolerance
- **retry.py** - Retry with backoff
- **fallback.py** - Graceful degradation

## Data Flow

### API Request Flow
```
Request → Middleware Chain → Route Handler → Service → Response
           │
           ├─ Rate Limiting
           ├─ Authentication
           ├─ Request Tracing
           └─ Body Validation
```

### Trading Flow
```
Signal → Validation → Risk Check → Order → Execution → Settlement
           │              │           │         │
           └──────────────┴───────────┴─────────┘
                          Audit Trail
```

## Security Architecture

### Authentication Methods
1. **JWT Tokens** - Short-lived access tokens
2. **API Keys** - Service-to-service auth
3. **2FA** - TOTP-based second factor

### Security Layers
1. **Network** - TLS, rate limiting, IP allowlist
2. **Application** - Input validation, CSRF, XSS prevention
3. **Data** - Encryption at rest, secure vault

## Deployment

### Docker Compose Services
- `jarvis-api` - FastAPI backend
- `jarvis-frontend` - React development server
- `redis` - Caching layer
- `nginx` - Reverse proxy
- `prometheus` - Metrics collection
- `grafana` - Dashboards

### Kubernetes
- Deployment with HPA
- ConfigMaps and Secrets
- PersistentVolumeClaims

## Monitoring

### Metrics
- HTTP request rate and latency
- Provider API calls
- Trade executions
- Cache hit/miss rates

### Alerting
- High error rate
- Provider failures
- High latency
- Memory leaks

---

## LLM Provider Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    UnifiedLLM Interface                     │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌───────────────────────────────────────────────────────┐  │
│  │                    LLM Router                         │  │
│  │                                                       │  │
│  │  TaskType.TRADING ───────► Groq (llama-3.3-70b)      │  │
│  │  TaskType.CHAT    ───────► Ollama (local)            │  │
│  │  TaskType.ANALYSIS ──────► OpenRouter (claude)       │  │
│  │  TaskType.CODING  ───────► xAI (grok)                │  │
│  │                                                       │  │
│  └───────────────────────────────────────────────────────┘  │
│                          │                                  │
│           ┌──────────────┼──────────────┐                  │
│           ▼              ▼              ▼                   │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐           │
│  │   Groq      │ │   Ollama    │ │ OpenRouter  │           │
│  │  Provider   │ │  Provider   │ │  Provider   │           │
│  └─────────────┘ └─────────────┘ └─────────────┘           │
│                          │                                  │
│                          ▼                                  │
│  ┌───────────────────────────────────────────────────────┐  │
│  │                 Cost Tracker                          │  │
│  │  • Token counting • Cost calculation • Budget alerts │  │
│  └───────────────────────────────────────────────────────┘  │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## Bot Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         Bot Ecosystem                                   │
└─────────────────────────────────────────────────────────────────────────┘

  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
  │  Telegram Bot   │  │   Twitter Bot   │  │  Treasury Bot   │
  ├─────────────────┤  ├─────────────────┤  ├─────────────────┤
  │ • Chat commands │  │ • Mentions      │  │ • Auto-trading  │
  │ • Trade alerts  │  │ • Sentiment     │  │ • Rebalancing   │
  │ • Price queries │  │ • Engagement    │  │ • Risk mgmt     │
  └────────┬────────┘  └────────┬────────┘  └────────┬────────┘
           │                    │                    │
           └────────────────────┼────────────────────┘
                                │
                    ┌───────────▼───────────┐
                    │    Bot Health         │
                    │    Monitoring         │
                    ├───────────────────────┤
                    │ • Uptime tracking     │
                    │ • Error logging       │
                    │ • Metrics collection  │
                    └───────────────────────┘
```

## Database Schema Overview

```
┌─────────────┐       ┌─────────────┐       ┌─────────────┐
│    users    │───────│ conversations│───────│  messages   │
└─────────────┘       └─────────────┘       └─────────────┘
      │
      ├───────────────┬───────────────┬───────────────┐
      ▼               ▼               ▼               ▼
┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐
│   trades    │ │   alerts    │ │  api_keys   │ │  webhooks   │
└─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘

Standalone Tables:
┌─────────────┐ ┌─────────────┐ ┌─────────────┐
│  llm_usage  │ │  audit_log  │ │ bot_metrics │
└─────────────┘ └─────────────┘ └─────────────┘
```

## Monitoring Stack

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   Application   │────►│   Prometheus    │────►│    Grafana      │
│    Metrics      │     │    Scraper      │     │   Dashboards    │
└─────────────────┘     └─────────────────┘     └─────────────────┘
        │                                               │
        ▼                                               ▼
┌─────────────────┐                             ┌───────────────┐
│  Log Aggregator │                             │  • Bot Health │
├─────────────────┤                             │  • LLM Costs  │
│ • Error rates   │                             │  • Trading    │
│ • Latency p99   │─────────────────────────────│  • API Perf   │
│ • Request logs  │        Alerting             └───────────────┘
└─────────────────┘

┌─────────────────┐
│  Uptime Monitor │
├─────────────────┤
│ • Health checks │
│ • Incidents     │
│ • Status page   │
└─────────────────┘
```

## Technology Stack

| Layer | Technology |
|-------|------------|
| API Framework | FastAPI |
| Async Runtime | asyncio, uvicorn |
| Database | PostgreSQL / SQLite |
| Cache | Redis / In-memory |
| LLM Providers | Groq, Ollama, OpenRouter, xAI |
| Blockchain | Solana (web3.py) |
| DEX | Jupiter Aggregator |
| Monitoring | Prometheus, Grafana |
| Testing | pytest, locust |
| Bots | python-telegram-bot, tweepy |
