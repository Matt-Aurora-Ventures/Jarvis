# Jarvis Distributed AI Swarm Implementation Plan

**Version**: 2.0
**Created**: 2026-01-23
**Author**: architect-agent
**Status**: Planning

---

## Executive Summary

This plan integrates immediate demo bot bug fixes (US-033) with the evolution to a distributed 9-agent AI swarm architecture. The path is incremental: fix bugs first, then add infrastructure, then migrate to the swarm model.

**Current State**: Monolithic supervisor.py managing 10 components with in-memory message bus
**Target State**: LangGraph-supervised distributed swarm with NATS, Ollama, and MCP servers

---

## Components Inventory

### EXISTS (Can Migrate)

| Component | Location | Status |
|-----------|----------|--------|
| Telegram Bot | tg_bot/ | Active, has bugs |
| Twitter/X Bot | bots/twitter/ | Active |
| Buy Bot | bots/buy_tracker/ | Active |
| Treasury Bot | bots/treasury/ | Active |
| Bags Intel | bots/bags_intel/ | Disabled (402 error) |
| Supervisor | bots/supervisor.py | Active |
| MessageBus | core/self_correcting/message_bus.py | In-memory |
| OllamaRouter | core/self_correcting/ollama_router.py | Working |
| AI Supervisor | core/ai_runtime/supervisor/ai_supervisor.py | Partial |
| Sentiment | core/sentiment_aggregator.py | Active |
| Redis Cache | core/cache/redis_cache.py | Exists |
| PostgreSQL | core/db/pool.py | Exists |

### NEEDS BUILDING

| Component | Purpose | Phase |
|-----------|---------|-------|
| NATS Client | Persistent messaging | 1 |
| LangGraph Supervisor | State machine orchestration | 2 |
| MCP Servers | Per-agent tool isolation | 3 |
| Qdrant Client | Vector search | 3 |
| Dexter Agent | DEX aggregation | 3 |
| Launchpad Governor | Token evaluation | 3 |
| Online Trading Agent | Signal execution | 3 |
| LiteLLM Proxy | Unified LLM API | 1 |

---

## 9 Target Agents

| # | Agent | Function | Current | Phase |
|---|-------|----------|---------|-------|
| 1 | Jarvis X | Twitter + Voice | bots/twitter/ | 2 |
| 2 | Telegram Jarvis | Chat + Trading UI | tg_bot/ | 0-1 |
| 3 | Buy Bot | Token tracking | bots/buy_tracker/ | 2 |
| 4 | Treasury Bot | Portfolio trading | bots/treasury/ | 2 |
| 5 | Monitor Bot | System health | core/monitoring/ | 2 |
| 6 | Dexter Agent | DEX aggregation | Not built | 3 |
| 7 | Launchpad Governor | Token evaluation | bags_intel partial | 3 |
| 8 | Online Trading | Signal execution | Not built | 3 |
| 9 | Sentiment Agent | Multi-source sentiment | sentiment_aggregator | 2 |

---

## Phase 0: Critical Bug Fixes (Week 1-2)

**Goal**: Get demo bot working without errors

### 0.1 Bug Fix: safe_symbol NameError

**Status**: DONE (verified in demo.py line 81-99)

The function exists at the top of the file:
- File: tg_bot/handlers/demo.py
- Lines: 81-99
- Sanitizes token symbols for Telegram display

Verification:
- [x] Function defined at module level
- [ ] Test /demo command without NameError

### 0.2 Bug Fix: amount KeyError

**File**: tg_bot/handlers/demo.py
**Issue**: Position dict uses inconsistent keys

Fix Pattern:
- Search for: pos["amount"]
- Replace with: pos.get("amount_sol", pos.get("amount", 0))

Tasks:
- [ ] Audit all position dict access
- [ ] Standardize to "amount_sol"
- [ ] Migrate existing .positions.json
- [ ] Test buy/sell flow

### 0.3 Bug Fix: Bot Instance Conflicts

**Status**: DONE (supervisor.py lines 34-136)

SingleInstanceLock class implemented:
- Cross-platform (Windows msvcrt, Unix fcntl)
- ensure_single_instance() helper exists

Tasks:
- [x] Lock implementation exists
- [ ] Apply to demo bot entry
- [ ] Test concurrent launch prevention

### 0.4 Bug Fix: TP/SL UI Not Wired

**File**: tg_bot/handlers/demo.py

Required Callbacks:
- adj_tp: Adjust take-profit percentage
- adj_sl: Adjust stop-loss percentage
- adj_save: Persist changes to position
- adj_cancel: Restore original values

Tasks:
- [ ] Verify PositionButtons generates correct callback_data
- [ ] Implement adj_tp handler
- [ ] Implement adj_sl handler
- [ ] Implement adj_save handler
- [ ] Implement adj_cancel handler
- [ ] Test TP/SL adjustment flow

### Phase 0 Testing Checklist

- [ ] /demo command launches without errors
- [ ] Buy flow completes (no safe_symbol error)
- [ ] Sell flow completes (no amount KeyError)
- [ ] TP/SL buttons respond and persist
- [ ] Only one bot instance can run
- [ ] No unhandled exceptions in logs

### Phase 0 Rollback

1. Revert demo.py to last known good commit
2. Disable /demo command temporarily
3. Use treasury bot for trading (fallback)

---

## Phase 1: Infrastructure Foundation (Week 3-4)

**Goal**: Add core infrastructure for distributed operation

### 1.1 Redis Enhancement

**Current**: core/cache/redis_cache.py exists
**Enhancement**: Session store and distributed locks

New Files:
- core/redis/session_store.py
- core/redis/distributed_locks.py

Configuration (config.yaml):
```yaml
redis:
  url: redis://localhost:6379
  db: 0
  max_connections: 20
  session_ttl: 3600
```

Migration Tasks:
- [ ] Move tg_bot sessions from SQLite to Redis
- [ ] Replace file locks with Redis locks
- [ ] Add Redis health check

Resources: RAM 256MB, CPU minimal, Disk 100MB

### 1.2 NATS JetStream Setup

**Purpose**: Replace in-memory MessageBus

New Files:
- core/nats/client.py
- core/nats/streams.py
- core/nats/publishers.py
- core/nats/consumers.py

Streams:
- JARVIS_SIGNALS: Trading signals (7 day retention)
- JARVIS_EVENTS: System events (1 day retention)
- JARVIS_TASKS: Task queue (workqueue mode)

Migration Tasks:
- [ ] Install nats-py
- [ ] Create stream definitions
- [ ] Adapt MessageBus to NATS backend
- [ ] Keep in-memory fallback
- [ ] Update publish/subscribe calls

Resources: RAM 512MB, CPU 1 core, Disk 1GB

### 1.3 Ollama + LiteLLM Enhancement

**Current**: OllamaRouter exists
**Enhancement**: LiteLLM proxy for unified API

New Files:
- core/llm/litellm_proxy.py
- core/llm/model_registry.py
- core/llm/fallback_chain.py

Configuration:
```yaml
llm:
  default_provider: ollama
  ollama:
    base_url: http://localhost:11434
    models: [qwen3-coder, llama3.1, deepseek-coder]
  litellm:
    port: 4000
    fallback_to_cloud: true
    cloud_budget_daily: 10.00
```

Tasks:
- [ ] Install litellm
- [ ] Create proxy config
- [ ] Update OllamaRouter
- [ ] Add spend tracking
- [ ] Add quality metrics

Resources: RAM 8GB (models), CPU 4 cores, GPU optional

### 1.4 PostgreSQL Schema Extension

**Current**: Exists for OPC memory
**Enhancement**: Jarvis history tables

New Tables:
- trade_history: All trades with outcomes
- agent_states: Checkpoint snapshots
- conversations: Chat history with sentiment

Tasks:
- [ ] Create jarvis schema
- [ ] Migrate audit_log.json to PostgreSQL
- [ ] Add conversation logging
- [ ] Create indexes

### Phase 1 Testing Checklist

- [ ] Redis < 100ms operation latency
- [ ] NATS streams persist across restart
- [ ] Ollama responds via LiteLLM
- [ ] PostgreSQL queries indexed
- [ ] All health checks passing

### Phase 1 Rollback

Feature flags:
- JARVIS_USE_NATS=false -> in-memory MessageBus
- JARVIS_USE_REDIS=false -> file locks

---

## Phase 2: LangGraph Supervisor + Core Agents (Week 5-8)

**Goal**: Central task orchestration with 3 migrated agents

### 2.1 LangGraph Supervisor

**Purpose**: Replace supervisor.py process management

New Directory:
```
core/langgraph/
  __init__.py
  supervisor.py      # Main graph
  router.py          # Task routing
  checkpoints.py     # State persistence
  tools/
    agent_tools.py
    system_tools.py
```

Supervisor State:
- messages: Conversation history
- current_task: Active task
- agent_assignments: Task-to-agent mapping
- pending_approvals: Human approval queue

Graph Nodes:
- router: Route incoming tasks
- agent_selector: Match task to agent capability
- human_approval: Check if approval needed
- execute: Dispatch to agent
- aggregate: Collect results

Tasks:
- [ ] Install langgraph, langchain
- [ ] Define SupervisorState schema
- [ ] Implement routing logic
- [ ] Add human-in-the-loop
- [ ] Connect to NATS
- [ ] Persist checkpoints to PostgreSQL

### 2.2 Telegram Agent Migration

**Current**: tg_bot/ as subprocess
**Target**: LangGraph-managed agent

New Directory:
```
agents/telegram/
  __init__.py
  agent.py           # LangGraph agent
  tools.py           # Telegram tools
  mcp_server.py      # MCP server
  prompts.py         # System prompts
```

Agent Definition:
- Name: telegram_jarvis
- Capabilities: user_interaction, trading_ui, portfolio_display, alert_delivery
- Tools: send_message, edit_message, send_photo, get_user_context, execute_trade

Tasks:
- [ ] Extract demo.py handlers to tools
- [ ] Create MCP server
- [ ] Wire to supervisor
- [ ] Maintain backward compatibility
- [ ] Test with Telegram

### 2.3 Sentiment Agent Migration

**Current**: Scattered (sentiment_aggregator, grok_client)
**Target**: Dedicated agent

New Directory:
```
agents/sentiment/
  __init__.py
  agent.py
  sources.py         # Data connectors
  scoring.py         # Calculation
  mcp_server.py
```

Agent Definition:
- Name: sentiment_agent
- Capabilities: twitter_sentiment, market_sentiment, token_scoring, trend_detection
- Tools: fetch_twitter_mentions, fetch_market_data, calculate_score, detect_momentum

### 2.4 Monitor Agent Creation

**Current**: Fragmented in core/monitoring/
**Target**: Unified health agent

New Directory:
```
agents/monitor/
  __init__.py
  agent.py
  health_checks.py
  alerting.py
  mcp_server.py
```

Agent Definition:
- Name: monitor_bot
- Capabilities: health_monitoring, error_detection, performance_tracking, alerting
- Tools: check_agent_health, check_infra_health, get_error_rates, send_alert, trigger_restart

### Phase 2 Testing Checklist

- [ ] Supervisor routes 95%+ tasks correctly
- [ ] Telegram agent responds to commands
- [ ] Sentiment agent scores accurately
- [ ] Monitor agent detects failures
- [ ] Human approval < 30 seconds
- [ ] Agents communicate via NATS
- [ ] State persists across restarts

### Phase 2 Rollback

1. Keep supervisor.py running parallel
2. JARVIS_USE_LANGGRAPH=false
3. Agent failures fall back to old implementations

---

## Phase 3: Full Swarm + MCP Servers (Week 9-12)

**Goal**: Complete 9-agent swarm with tool isolation

### 3.1 Remaining Agent Migrations

**Jarvis X Agent** (Twitter + Voice):
```
agents/jarvis_x/
  agent.py
  twitter_tools.py
  voice_tools.py     # Future
  mcp_server.py
```

**Buy Bot Agent**:
```
agents/buy_bot/
  agent.py
  tracking_tools.py
  notification_tools.py
  mcp_server.py
```

**Treasury Bot Agent**:
```
agents/treasury/
  agent.py
  trading_tools.py
  portfolio_tools.py
  mcp_server.py
```

### 3.2 New Agent Development

**Dexter Agent** (DEX Aggregation):
```
agents/dexter/
  agent.py
  aggregation.py     # Multi-DEX prices
  routing.py         # Optimal swaps
  mcp_server.py
```

Capabilities:
- Price comparison across DEXs
- Optimal route calculation
- Slippage estimation
- MEV protection

**Launchpad Governor** (Token Evaluation):
```
agents/launchpad/
  agent.py
  evaluation.py      # Token scoring
  monitoring.py      # Graduation tracking
  mcp_server.py
```

Capabilities:
- bags.fm monitoring
- Token risk scoring
- Graduation detection
- Early entry signals

**Online Trading Agent** (Signal Execution):
```
agents/online_trading/
  agent.py
  signal_parser.py   # External signals
  execution.py       # Trade execution
  mcp_server.py
```

Capabilities:
- Parse trading signals from external sources
- Validate signal quality
- Execute with confirmation
- Track signal performance

### 3.3 MCP Server Architecture

Each agent gets isolated MCP server:

Pattern:
```python
from mcp.server import Server
from mcp.types import Tool, Resource

app = Server("agent-name-tools")

@app.tool()
async def tool_name(param: str) -> dict:
    """Tool description."""
    pass

@app.resource("protocol://resource/{id}")
async def get_resource(id: str) -> Resource:
    """Resource description."""
    pass
```

MCP Config (config.yaml):
```yaml
mcp:
  servers:
    telegram:
      transport: stdio
      command: python -m agents.telegram.mcp_server
    sentiment:
      transport: stdio
      command: python -m agents.sentiment.mcp_server
    treasury:
      transport: stdio
      command: python -m agents.treasury.mcp_server
    # ... one per agent
```

### 3.4 Qdrant Vector Store

**Purpose**: Semantic search for agent memory

New Files:
- core/vectors/qdrant_client.py
- core/vectors/embeddings.py
- core/vectors/collections.py

Collections:
- trade_learnings: Trade outcome patterns
- conversation_context: User interaction history
- market_patterns: Market behavior patterns

Resources: RAM 1GB, CPU 1 core, Disk 10GB

### Phase 3 Testing Checklist

- [ ] All 9 agents registered
- [ ] Each agent has MCP server
- [ ] Inter-agent communication works
- [ ] Qdrant search < 100ms
- [ ] Complex workflows complete
- [ ] Agent failures handled gracefully

### Phase 3 Rollback

1. Individual agents can be disabled
2. Fallback to Phase 2 core agents
3. MCP servers bypassed (direct calls)
4. Qdrant failures -> PostgreSQL

---

## Phase 4: Production Hardening (Month 4+)

**Goal**: Production-ready distributed system

### 4.1 Observability

Stack:
- Prometheus: Metrics collection
- Grafana: Dashboards
- Loki: Log aggregation

Key Metrics:
- agent_task_duration_seconds
- agent_task_success_total
- agent_task_failure_total
- llm_request_duration_seconds
- llm_tokens_used_total
- llm_cost_dollars_total
- trades_executed_total
- trade_pnl_percent
- portfolio_value_sol
- nats_messages_published_total
- redis_connections_active
- postgres_query_duration_seconds

### 4.2 Scaling

Horizontal Scaling:
- Multiple agent instances (stateless)
- NATS consumer groups for load distribution
- Redis cluster for sessions

Resource Scaling Guide:
| Component | Base | +50% Load | +100% Load |
|-----------|------|-----------|------------|
| Redis | 256MB | 512MB | 1GB |
| NATS | 512MB | 1GB | 2GB |
| PostgreSQL | 1GB | 2GB | 4GB |
| Ollama | 8GB | 16GB | 24GB |
| Agents (each) | 256MB | 512MB | 1GB |

### 4.3 Security Hardening

Authentication:
- mTLS between agents
- JWT for external API
- API key rotation

Authorization:
- Role-based tool access
- Approval workflows for sensitive ops
- Audit logging

### 4.4 Disaster Recovery

Backup Strategy:
- PostgreSQL: Daily snapshots + WAL
- Redis: RDB + AOF
- NATS: Stream replication
- Qdrant: Collection backups

Recovery Procedures:
1. Agent failure: Auto-restart
2. Infra failure: Failover to backup
3. Data corruption: Restore from backup
4. Total failure: Full rebuild

---

## Resource Requirements

### Development Environment

| Component | RAM | CPU | Disk |
|-----------|-----|-----|------|
| Redis | 256MB | 0.5 | 100MB |
| NATS | 512MB | 1 | 1GB |
| PostgreSQL | 1GB | 1 | 5GB |
| Ollama | 8GB | 4 | 20GB |
| Supervisor | 512MB | 1 | - |
| 9 Agents | 2GB | 2 | - |
| **Total** | **12GB** | **9.5** | **26GB** |

### Production Environment

| Component | RAM | CPU | Disk |
|-----------|-----|-----|------|
| Redis | 1GB | 2 | 500MB |
| NATS | 2GB | 2 | 5GB |
| PostgreSQL | 4GB | 4 | 50GB |
| Ollama | 24GB | 8 | 50GB |
| Supervisor | 1GB | 2 | - |
| 9 Agents | 4GB | 4 | - |
| Monitoring | 2GB | 2 | 20GB |
| **Total** | **38GB** | **24** | **125GB** |

---

## Dependencies

### Python Packages (New)

Phase 1:
- redis>=5.0.0
- nats-py>=2.6.0
- litellm>=1.30.0

Phase 2:
- langgraph>=0.0.50
- langchain>=0.1.0
- langchain-anthropic>=0.1.0

Phase 3:
- mcp>=0.1.0
- qdrant-client>=1.7.0

Phase 4:
- prometheus-client>=0.19.0

### Infrastructure (Docker)

```yaml
services:
  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]
    
  nats:
    image: nats:2.10-alpine
    ports: ["4222:4222"]
    command: ["-js", "-sd", "/data"]
    
  postgres:
    image: postgres:16-alpine
    ports: ["5432:5432"]
    
  qdrant:
    image: qdrant/qdrant:v1.7.0
    ports: ["6333:6333"]
```

---

## Success Criteria

### Phase 0 (Bug Fixes)
- [ ] Zero crashes in 24 hours
- [ ] All TP/SL buttons functional
- [ ] Single instance enforcement

### Phase 1 (Infrastructure)
- [ ] Redis < 100ms latency
- [ ] NATS < 50ms delivery
- [ ] Ollama < 5 second response
- [ ] All health checks pass

### Phase 2 (Core Agents)
- [ ] 95%+ task routing accuracy
- [ ] Human approval < 30 seconds
- [ ] Recovery < 10 seconds
- [ ] State persistence verified

### Phase 3 (Full Swarm)
- [ ] 9 agents operational
- [ ] MCP isolation verified
- [ ] Vector search < 100ms
- [ ] Complex workflows succeed

### Phase 4 (Production)
- [ ] 99.9% uptime
- [ ] Recovery < 5 seconds
- [ ] Complete audit trail
- [ ] DR tested

---

## Open Questions

- [ ] Voice interface: WebRTC vs phone?
- [ ] Ollama model: qwen3-coder vs deepseek-coder?
- [ ] NATS vs Redis Streams?
- [ ] LangGraph vs custom state machine?

---

## Changelog

| Version | Date | Changes |
|---------|------|---------|
| 2.0 | 2026-01-23 | Full swarm architecture |
| 1.0 | 2026-01-22 | Initial bug fixes |

---

**Next Action**: Complete Phase 0 bug fixes, verify demo bot stability
