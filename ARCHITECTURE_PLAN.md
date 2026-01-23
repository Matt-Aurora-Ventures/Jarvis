# Distributed Multi-Agent AI Swarm Architecture for Crypto Trading

A 32GB VPS running 9+ autonomous agents with Ollama cannot realistically serve 1 million concurrent users with real-time LLM inference—the math simply doesn't work. However, this architecture design provides a **production-viable path** through aggressive caching (80%+ hit rate), tiered service levels, intelligent failover to cloud APIs, and a clear scaling roadmap from single-VPS to multi-node cluster. The system handles **30-60 LLM requests/minute locally** with sub-second latency for critical trading signals, scaling through Redis queuing, NATS JetStream messaging, and cloud burst capacity.

---

## Complete system architecture

The architecture separates concerns into five layers: API gateway, agent orchestration (LangGraph supervisor), inference (Ollama + LiteLLM), messaging (NATS JetStream), and storage (Redis/PostgreSQL/Qdrant hybrid).

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              EXTERNAL INTERFACES                                 │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────────┐  │
│  │ Twitter  │  │ Telegram │  │   Web    │  │   DEX    │  │ Exchange APIs    │  │
│  │   API    │  │   Bot    │  │   App    │  │ (Dexter) │  │ (Binance, etc)   │  │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────────┬─────────┘  │
└───────┼──────────────┼──────────────┼──────────────┼───────────────┼────────────┘
        │              │              │              │               │
        └──────────────┴──────────────┼──────────────┴───────────────┘
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           NGINX REVERSE PROXY + RATE LIMITER                     │
│                    (SSL termination, request routing, throttling)                │
└─────────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         SUPERVISOR AGENT (LangGraph)                             │
│  ┌───────────────┐ ┌────────────────┐ ┌─────────────────┐ ┌─────────────────┐  │
│  │ Task Router   │ │ Human Approval │ │ Health Monitor  │ │ Error Handler   │  │
│  │ (capability-  │ │ Gateway        │ │ (heartbeat,     │ │ (retry, DLQ,    │  │
│  │  based)       │ │ (interrupt())  │ │  restart)       │ │  escalation)    │  │
│  └───────────────┘ └────────────────┘ └─────────────────┘ └─────────────────┘  │
└─────────────────────────────────────┬───────────────────────────────────────────┘
                                      │ Handoff Tools
        ┌─────────┬─────────┬─────────┼─────────┬─────────┬─────────┬─────────┐
        ▼         ▼         ▼         ▼         ▼         ▼         ▼         ▼
┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐
│Jarvis X │ │Telegram │ │ Buy Bot │ │Treasury │ │Monitor  │ │ Dexter  │ │Launchpad│
│Twitter  │ │ Jarvis  │ │         │ │   Bot   │ │   Bot   │ │  Agent  │ │Governor │
│(+Voice) │ │         │ │         │ │         │ │         │ │         │ │         │
└────┬────┘ └────┬────┘ └────┬────┘ └────┬────┘ └────┬────┘ └────┬────┘ └────┬────┘
     │          │          │          │          │          │          │
     └──────────┴──────────┴──────────┼──────────┴──────────┴──────────┘
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           MCP SERVER LAYER (per-agent tools)                     │
│  ┌───────────────────────────────────────────────────────────────────────────┐  │
│  │ Trading MCP     │ Social MCP      │ Monitor MCP    │ Treasury MCP         │  │
│  │ • execute_trade │ • post_tweet    │ • get_alerts   │ • get_balance        │  │
│  │ • get_positions │ • get_mentions  │ • check_health │ • transfer_funds     │  │
│  │ • cancel_order  │ • analyze_sent  │ • log_event    │ • generate_report    │  │
│  └───────────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              NATS JETSTREAM                                      │
│                    (Inter-agent messaging, event streaming)                      │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────────────────┐  │
│  │ TRADING_CRITICAL│  │ TRADING_HIGH    │  │ SYSTEM_LOW                      │  │
│  │ (memory, 5min)  │  │ (file, 1hr)     │  │ (file, 24hr)                    │  │
│  │ P8-P9 signals   │  │ P5-P7 analysis  │  │ P0-P4 monitoring, social        │  │
│  └─────────────────┘  └─────────────────┘  └─────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────────┘
                                      │
                    ┌─────────────────┼─────────────────┐
                    ▼                 ▼                 ▼
┌──────────────────────┐ ┌─────────────────────┐ ┌─────────────────────────────┐
│    LITELLM PROXY     │ │   REDIS CLUSTER     │ │      QDRANT + POSTGRESQL    │
│   (Routing + Cache)  │ │   (Hot State)       │ │      (Persistent Memory)    │
│ ┌──────────────────┐ │ │ • Session context   │ │ ┌─────────────────────────┐ │
│ │ Tier 1: Ollama   │ │ │ • Agent registry    │ │ │ Qdrant: Semantic search │ │
│ │ Tier 2: Groq     │ │ │ • Priority queues   │ │ │ • 768d embeddings       │ │
│ │ Tier 3: OpenRouter│ │ │ • Blackboard state  │ │ │ • Multi-tenant (filter) │ │
│ │ Tier 4: Cached   │ │ │ • Rate limit counters│ │ ├─────────────────────────┤ │
│ └──────────────────┘ │ │                     │ │ │ PostgreSQL: Structured  │ │
└──────────┬───────────┘ └─────────────────────┘ │ │ • Conversation history  │ │
           │                                      │ │ • User preferences      │ │
           ▼                                      │ │ • Trade audit logs      │ │
┌─────────────────────────────────────────────┐  │ └─────────────────────────┘ │
│              OLLAMA (Local LLM)             │  └─────────────────────────────┘
│  Model: qwen3-8b-instruct-q4_k_m            │
│  Context: 4096 tokens                       │
│  Parallel: 2 requests                       │
│  CPU pinned: cores 0-1 (isolated)           │
│  Memory: 10GB allocated                     │
└─────────────────────────────────────────────┘
```

---

## Technology stack with justifications

| Layer | Technology | Justification |
|-------|------------|---------------|
| **LLM Inference** | Ollama + LiteLLM Proxy | Ollama excels at CPU inference via llama.cpp; LiteLLM provides unified routing, failover, and caching across Ollama→Groq→OpenRouter |
| **Model** | qwen3-8b Q4_K_M | Best quality/RAM balance for 32GB; 4-bit quantization fits with headroom for KV cache |
| **Agent Framework** | LangGraph | Native `interrupt()` for HITL approval, graph-based workflows, PostgreSQL checkpointing for crash recovery |
| **Inter-Agent Messaging** | NATS JetStream | Sub-millisecond latency (~0.4ms), exactly-once delivery, 10MB binary, built-in persistence |
| **State/Cache** | Redis Cluster | <1ms access for session context, agent registry, priority queues via sorted sets |
| **Vector Memory** | Qdrant (disk-optimized) | 135MB for 1M vectors with mmap, multi-tenant via payload filtering, production-ready |
| **Relational Storage** | PostgreSQL + Citus | RLS for tenant isolation, hash partitioning on user_id, pgvector for auxiliary embeddings |
| **Orchestration (Phase 1)** | Docker Compose + PM2 | Minimal overhead for 9-30 agents; PM2 provides clustering, zero-downtime reload |
| **Orchestration (Phase 2+)** | k3s | 1.6GB overhead acceptable at scale; enables multi-node, rolling updates |
| **Voice (Jarvis X)** | Whisper STT + ElevenLabs TTS | ~150ms STT + ~90ms TTS = <250ms audio latency; ElevenLabs for natural "Jarvis" voice |
| **MCP Integration** | Custom MCP servers per agent | JSON-RPC 2.0 over STDIO; tool isolation per agent type |

### Model configuration for 32GB RAM

```yaml
# Optimal Ollama configuration
Environment:
  OLLAMA_HOST: "0.0.0.0:11434"
  OLLAMA_NUM_PARALLEL: "2"        # Max concurrent requests
  OLLAMA_MAX_LOADED_MODELS: "1"   # Single model to save RAM
  OLLAMA_MAX_QUEUE: "256"         # Queue size before 503
  OLLAMA_KEEP_ALIVE: "10m"        # Unload after 10min idle
  OLLAMA_CONTEXT_LENGTH: "4096"   # Context window
  OLLAMA_KV_CACHE_TYPE: "q8_0"    # 50% KV cache reduction
  OLLAMA_FLASH_ATTENTION: "true"  # Memory optimization

# Memory breakdown
Model weights (7B Q4_K_M): ~5GB
KV cache (4K × 2 parallel): ~3GB
Ollama overhead: ~2GB
Total Ollama allocation: 10GB
```

---

## Memory and storage schema

The hybrid architecture uses **three tiers**: Redis for hot session data (<1ms), Qdrant for semantic retrieval (~20ms), and PostgreSQL for persistent history (~10ms).

### Per-user storage requirements

| Data Type | Per User | 1M Users | Storage Location |
|-----------|----------|----------|------------------|
| Vector embeddings (768d × 500 chunks) | 2.25MB | 2.25TB | Qdrant |
| Conversation history | 2MB | 2TB (500GB compressed) | PostgreSQL |
| Session context (active) | 50KB | 5GB (100K concurrent) | Redis |
| User metadata | 10KB | 10GB | PostgreSQL |
| **Total** | ~4.3MB | ~2.8TB | Hybrid |

### PostgreSQL schema (Citus distributed)

```sql
-- Users table (reference, replicated to all nodes)
CREATE TABLE users (
    user_id UUID PRIMARY KEY,
    preferences JSONB,
    trading_constraints JSONB,
    risk_profile VARCHAR(20),
    created_at TIMESTAMP DEFAULT NOW()
);

-- Conversations (distributed by user_id for horizontal scaling)
CREATE TABLE conversations (
    id UUID DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    session_id UUID NOT NULL,
    agent_id VARCHAR(50),
    role VARCHAR(20), -- 'user', 'assistant', 'system', 'tool'
    content TEXT,
    metadata JSONB,
    embedding_generated BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (user_id, id)
) PARTITION BY HASH (user_id);

-- Create 64 partitions for million-user scale
SELECT create_distributed_table('conversations', 'user_id');

-- Row-Level Security for tenant isolation
ALTER TABLE conversations ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON conversations
    USING (user_id = current_setting('app.current_tenant')::uuid);

-- Trade audit log (compliance requirement)
CREATE TABLE trade_audit (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    agent_id VARCHAR(50) NOT NULL,
    action_type VARCHAR(50),
    trade_details JSONB,
    risk_assessment JSONB,
    ai_reasoning TEXT,
    human_approval JSONB, -- {approver_id, decision, timestamp, modifications}
    execution_result JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_trade_audit_user ON trade_audit(user_id, created_at DESC);
```

### Redis session structure

```python
# Key patterns for multi-tenant isolation
SESSION_KEY = "session:{user_id}:{session_id}"
AGENT_REGISTRY = "agents:registry"
AGENT_HEALTH = "agents:health"  # Sorted set, score = last heartbeat
PRIORITY_QUEUE = "queue:priority:{level}"  # 0-9, 9 = critical

# Session hash structure
{
    "messages": "[{\"role\": \"user\", \"content\": \"...\", \"ts\": 1706000000}, ...]",
    "user_context": "{\"preferences\": {...}, \"portfolio\": {...}}",
    "agent_state": "{\"current_agent\": \"trading\", \"pending_approval\": true}",
    "last_activity": "1706000000"
}

# TTL: 1 hour for active, extend on activity
# Eviction: LRU when memory pressure

# Agent registry hash
HSET agents:registry buy_bot {
    "name": "Buy Bot",
    "capabilities": ["token_purchase", "dex_interaction"],
    "status": "active",
    "queue": "trading.buy_bot",
    "current_load": 3,
    "max_concurrent": 10
}
```

### Qdrant collection configuration

```python
from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance, HnswConfigDiff

client.create_collection(
    collection_name="user_memories",
    vectors_config=VectorParams(
        size=768,  # text-embedding-3-small with MRL (50% storage savings)
        distance=Distance.COSINE
    ),
    hnsw_config=HnswConfigDiff(
        on_disk=True  # Critical for 32GB constraint
    ),
    optimizers_config=OptimizersConfigDiff(
        memmap_threshold=20000  # Use mmap for large segments
    )
)

# Multi-tenant via payload filtering
client.upsert(
    collection_name="user_memories",
    points=[
        PointStruct(
            id=uuid4(),
            vector=embedding,
            payload={
                "user_id": user_id,       # Tenant isolation
                "session_id": session_id,
                "content": message,
                "agent_type": "trading",
                "timestamp": timestamp
            }
        )
    ]
)

# Retrieval with tenant filter
results = client.search(
    collection_name="user_memories",
    query_vector=query_embedding,
    query_filter=Filter(
        must=[FieldCondition(key="user_id", match=MatchValue(value=user_id))]
    ),
    limit=5
)
```

---

## Inter-agent message protocol specification

NATS JetStream handles all agent-to-agent communication with Protobuf serialization for performance-critical paths.

### Message schema (Protobuf)

```protobuf
syntax = "proto3";
package trading.agents;

message AgentMessage {
  // Header
  string message_id = 1;           // UUID v7 (time-ordered)
  string correlation_id = 2;       // Request-reply tracking
  string source_agent = 3;
  string target_agent = 4;         // Empty for broadcast
  int64 timestamp_ns = 5;
  int32 priority = 6;              // 0-9, 9 = critical trading signal
  int32 ttl_ms = 7;
  
  // Routing
  string topic = 8;                // e.g., "trading.buy.urgent"
  
  // Payload (oneof for type safety)
  oneof payload {
    TradingSignal trading_signal = 10;
    ApprovalRequest approval_request = 11;
    ApprovalResponse approval_response = 12;
    HealthCheck health_check = 13;
    AgentCommand command = 14;
  }
  
  map<string, string> headers = 15;
  int32 retry_count = 16;
}

message TradingSignal {
  string action = 1;               // BUY, SELL, HOLD
  string token_address = 2;
  string amount = 3;               // String for precision
  string price_limit = 4;
  int64 expiry_timestamp = 5;
  double confidence = 6;           // 0.0-1.0
  string reasoning = 7;            // AI explanation for audit
}

message ApprovalRequest {
  string action_type = 1;
  string description = 2;
  map<string, string> parameters = 3;
  int64 timeout_ms = 4;
  string requester_agent = 5;
}

message ApprovalResponse {
  enum Decision { APPROVE = 0; REJECT = 1; MODIFY = 2; }
  Decision decision = 1;
  map<string, string> modified_params = 2;
  string reason = 3;
  string approver_id = 4;
  int64 approved_at = 5;
}
```

### Topic naming convention

```
{domain}.{agent_type}.{action}.{priority}

Examples:
trading.buy_bot.execute.critical     # P9 - immediate execution
trading.treasury.sentiment.high      # P7 - important but not urgent  
social.jarvis_x.alert.normal         # P5 - standard priority
system.supervisor.heartbeat.low      # P2 - background
system.*.health.low                  # Wildcard subscription
```

### NATS JetStream stream configuration

```javascript
// Stream definitions
const streams = {
  // Critical trading signals - memory storage for speed
  TRADING_CRITICAL: {
    name: "TRADING_CRITICAL",
    subjects: ["trading.*.urgent", "trading.*.critical"],
    retention: "limits",
    max_msgs: 100000,
    max_age: "5m",
    storage: "memory",
    replicas: 1,  // Single node
    duplicate_window: "30s"
  },
  
  // Standard trading - file storage for durability
  TRADING_HIGH: {
    name: "TRADING_HIGH", 
    subjects: ["trading.*.high", "trading.*.normal"],
    retention: "limits",
    max_msgs: 500000,
    max_age: "1h",
    storage: "file",
    replicas: 1
  },
  
  // System/monitoring - longer retention
  SYSTEM_LOW: {
    name: "SYSTEM_LOW",
    subjects: ["system.*", "social.*", "monitoring.*"],
    retention: "limits",
    max_msgs: 1000000,
    max_age: "24h",
    storage: "file",
    replicas: 1
  }
};
```

---

## Failover and fault tolerance design

The system implements a **four-tier failover chain** for LLM inference and comprehensive failure handling for agents.

### LLM failover chain

```yaml
# litellm-config.yaml
model_list:
  # Tier 1: Local Ollama (primary - zero cost)
  - model_name: trading-llm
    litellm_params:
      model: ollama/qwen3:8b
      api_base: http://localhost:11434
      timeout: 10
    model_info:
      id: ollama-local
    order: 1

  # Tier 2: Groq (fast cloud fallback - ~$0.10/1M tokens)
  - model_name: trading-llm
    litellm_params:
      model: groq/llama-3.1-8b-instant
      api_key: ${GROQ_API_KEY}
      timeout: 15
    model_info:
      id: groq-fallback
    order: 2

  # Tier 3: OpenRouter (broad model access - ~$0.50/1M tokens)
  - model_name: trading-llm
    litellm_params:
      model: openrouter/meta-llama/llama-3.1-8b-instruct
      api_key: ${OPENROUTER_API_KEY}
      timeout: 20
    model_info:
      id: openrouter-fallback
    order: 3

router_settings:
  enable_pre_call_checks: true
  fallbacks:
    - trading-llm: ["groq-fallback", "openrouter-fallback"]
  num_retries: 2
  retry_after: 1
  allowed_fails: 3
  cooldown_time: 60  # Cool down failed endpoint for 60s

# Tier 4: Redis cache for degraded mode
cache: true
cache_params:
  type: redis
  host: localhost
  port: 6379
  ttl: 3600
```

### Agent failure recovery

```python
class AgentRecoveryManager:
    """Handles graceful agent failure recovery"""
    
    RETRY_POLICY = {
        "trading_signal": {
            "max_retries": 3,
            "initial_delay_ms": 100,
            "max_delay_ms": 2000,
            "backoff_multiplier": 2.0
        },
        "monitoring": {
            "max_retries": 5,
            "initial_delay_ms": 1000,
            "max_delay_ms": 60000,
            "backoff_multiplier": 2.0
        }
    }
    
    async def handle_agent_failure(self, agent_id: str):
        # 1. Mark agent unhealthy
        await self.registry.set_status(agent_id, "unhealthy")
        
        # 2. Redistribute in-flight messages
        pending = await self.get_pending_messages(agent_id)
        for msg in pending:
            alt_agent = await self.find_alternative(msg.capabilities)
            if alt_agent:
                await self.nats.publish(f"agent.{alt_agent}.queue", msg)
            else:
                await self.escalate_to_supervisor(msg)
        
        # 3. Attempt restart via PM2/k8s
        if self.can_restart(agent_id):
            await self.restart_agent(agent_id)
        
        # 4. Alert
        await self.alert(f"Agent {agent_id} failed, {len(pending)} msgs redistributed")


class TradingSignalGuard:
    """Exactly-once guarantee for trading signals"""
    
    async def execute_with_guarantee(self, signal: TradingSignal):
        # 1. Journal to NATS JetStream (persistent)
        ack = await self.journal.publish("trading.signals.journal", signal)
        
        try:
            # 2. Execute
            result = await self.execute_trade(signal)
            
            # 3. Acknowledge completion
            await self.journal.ack(ack.seq)
            return result
            
        except Exception as e:
            # 4. NAK for redelivery after delay
            await self.journal.nak(ack.seq, delay=5000)
            raise
```

### Circuit breaker pattern

```python
class OllamaCircuitBreaker:
    def __init__(self):
        self.failure_count = 0
        self.failure_threshold = 5
        self.recovery_time = 30  # seconds
        self.last_failure = 0
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
    
    async def call(self, prompt: str, priority: int):
        if self.state == "OPEN":
            if time.time() - self.last_failure > self.recovery_time:
                self.state = "HALF_OPEN"
            else:
                return await self.fallback(prompt, priority)
        
        try:
            result = await self.ollama.generate(prompt)
            if self.state == "HALF_OPEN":
                self.state = "CLOSED"
                self.failure_count = 0
            return result
        except Exception as e:
            self.failure_count += 1
            self.last_failure = time.time()
            if self.failure_count >= self.failure_threshold:
                self.state = "OPEN"
            return await self.fallback(prompt, priority)
    
    async def fallback(self, prompt: str, priority: int):
        # High priority: use cloud API
        if priority >= 7:
            return await self.litellm.acompletion(model="groq/llama-3.1-8b-instant")
        # Low priority: return cached or template response
        return self.get_cached_response(prompt)
```

---

## Deployment strategy for Hostinger VPS

### Resource allocation (32GB total)

| Component | RAM | CPU | Notes |
|-----------|-----|-----|-------|
| OS/System | 2GB | - | Linux kernel, systemd |
| Ollama | 10GB | 2 cores (pinned) | Isolated via cgroups |
| Trading Agents (9-30) | 12GB | 4 cores (shared) | PM2 cluster mode |
| PostgreSQL | 2GB | shared | Trading data, audit |
| Redis | 1GB | shared | Session cache, queues |
| NATS JetStream | 1GB | shared | Message persistence |
| Monitoring | 500MB | shared | Prometheus + Grafana |
| Buffer | 3.5GB | - | Burst handling |

### Docker Compose deployment

```yaml
version: '3.8'

services:
  ollama:
    image: ollama/ollama:latest
    restart: unless-stopped
    ports:
      - "11434:11434"
    volumes:
      - ollama-data:/root/.ollama
    environment:
      - OLLAMA_NUM_PARALLEL=2
      - OLLAMA_MAX_LOADED_MODELS=1
      - OLLAMA_MAX_QUEUE=256
      - OLLAMA_KEEP_ALIVE=10m
    deploy:
      resources:
        limits:
          cpus: '2.0'
          memory: 10G
        reservations:
          cpus: '1.0'
          memory: 8G
    # CPU pinning via cgroups
    cpuset: "0,1"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:11434/api/tags"]
      interval: 30s
      timeout: 10s
      retries: 3

  litellm:
    image: ghcr.io/berriai/litellm:main-stable
    restart: unless-stopped
    ports:
      - "4000:4000"
    volumes:
      - ./litellm-config.yaml:/app/config.yaml
    environment:
      - GROQ_API_KEY=${GROQ_API_KEY}
      - OPENROUTER_API_KEY=${OPENROUTER_API_KEY}
    depends_on:
      - ollama
      - redis
    deploy:
      resources:
        limits:
          memory: 1G

  nats:
    image: nats:2.10-alpine
    restart: unless-stopped
    command: ["--jetstream", "--store_dir=/data"]
    ports:
      - "4222:4222"
      - "8222:8222"
    volumes:
      - nats-data:/data
    deploy:
      resources:
        limits:
          memory: 1G

  redis:
    image: redis:7-alpine
    restart: unless-stopped
    command: redis-server --maxmemory 1gb --maxmemory-policy allkeys-lru
    ports:
      - "6379:6379"
    volumes:
      - redis-data:/data

  postgres:
    image: postgres:16-alpine
    restart: unless-stopped
    environment:
      - POSTGRES_DB=trading
      - POSTGRES_USER=trading
      - POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
    volumes:
      - postgres-data:/var/lib/postgresql/data
    deploy:
      resources:
        limits:
          memory: 2G

  qdrant:
    image: qdrant/qdrant:v1.7.4
    restart: unless-stopped
    ports:
      - "6333:6333"
    volumes:
      - qdrant-data:/qdrant/storage
    environment:
      - QDRANT__STORAGE__ON_DISK_PAYLOAD=true
    deploy:
      resources:
        limits:
          memory: 2G

volumes:
  ollama-data:
  nats-data:
  redis-data:
  postgres-data:
  qdrant-data:
```

### PM2 agent configuration

```javascript
// ecosystem.config.js
module.exports = {
  apps: [
    {
      name: 'supervisor-agent',
      script: './agents/supervisor/index.js',
      instances: 1,
      exec_mode: 'fork',
      max_memory_restart: '1G',
      env: {
        NODE_ENV: 'production',
        OLLAMA_URL: 'http://localhost:11434',
        NATS_URL: 'nats://localhost:4222'
      }
    },
    {
      name: 'trading-agents',
      script: './agents/trading/index.js',
      instances: 4,  // Cluster across 4 cores
      exec_mode: 'cluster',
      max_memory_restart: '500M',
      cron_restart: '0 */6 * * *',  // Restart every 6h to prevent leaks
      env: {
        NODE_ENV: 'production',
        AGENT_TYPES: 'buy_bot,treasury,dexter,online_trading'
      }
    },
    {
      name: 'social-agents',
      script: './agents/social/index.js',
      instances: 2,
      exec_mode: 'cluster',
      max_memory_restart: '500M',
      env: {
        AGENT_TYPES: 'jarvis_x,telegram_jarvis'
      }
    },
    {
      name: 'monitoring-agent',
      script: './agents/monitoring/index.js',
      instances: 1,
      max_memory_restart: '256M'
    },
    {
      name: 'launchpad-governor',
      script: './agents/launchpad/index.js',
      instances: 1,
      max_memory_restart: '256M'
    }
  ]
};
```

### Hostinger CPU throttling mitigation

```bash
# Create systemd slice to limit agent CPU (stay under 60% sustained)
cat > /etc/systemd/system/trading-agents.slice << SLICE
[Slice]
CPUQuota=400%  # 4 cores max (50% of 8)
MemoryMax=12G
MemoryHigh=10G
SLICE

# Run PM2 under resource-limited slice
systemd-run --slice=trading-agents.slice pm2 start ecosystem.config.js

# Prometheus alert to warn before throttling
# Alert at 60% CPU sustained for 30 min (180 min triggers throttling)
- alert: HighCPUUsage
  expr: 100 - (avg(rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100) > 60
  for: 30m
  labels:
    severity: warning
  annotations:
    summary: "CPU approaching Hostinger throttle threshold"
```

---

## Scaling roadmap

### Phase 1: Single VPS (Now → 6 months)

**Configuration**: Hostinger KVM 8 (32GB/8vCPU)
**Agents**: 9-30 agents
**Users**: 1,000-10,000 (with heavy caching)
**Cost**: ~$40-55/month

**Triggers to advance**:
- Sustained CPU >70% for >1 week
- RAM usage >28GB consistently
- Latency SLAs missed (>2s for trading signals)

### Phase 2: Dual VPS (6-12 months)

**Configuration**:
- VPS 1: Ollama + LiteLLM + core services
- VPS 2: Agents + additional Redis

**Agents**: 30-50 agents
**Users**: 10,000-50,000
**Cost**: ~$85-130/month

**Changes**:
- Migrate to k3s for orchestration
- PostgreSQL streaming replication
- Redis Cluster (3 nodes)
- HAProxy load balancing

### Phase 3: Multi-VPS cluster (12-18 months)

**Configuration**: 3-5 VPS nodes with k3s HA
**Agents**: 50-100 agents
**Users**: 50,000-200,000
**Cost**: ~$150-300/month

**Changes**:
- Geographic distribution (EU + US for exchange proximity)
- Managed PostgreSQL (Supabase or Citus Cloud)
- Qdrant Cloud for vector search
- Dedicated inference node with GPU (optional)

### Phase 4: Cloud hybrid (18+ months)

**Configuration**:
- VPS for stable workloads
- Cloud (Hetzner/DigitalOcean) for burst capacity
- Serverless for overflow (AWS Lambda, Groq API)

**Agents**: 100+ agents
**Users**: 200,000-1,000,000+
**Cost**: $300-1,000/month

**Changes**:
- Kubernetes federation across providers
- Global CDN for static assets
- Event-driven scaling with KEDA
- Full observability stack (Grafana Cloud)

---

## Cost estimates

### Current deployment (Phase 1)

| Item | Monthly Cost |
|------|--------------|
| Hostinger VPS KVM 8 (32GB/8vCPU) | $45 |
| Domain + SSL | $0 (Let's Encrypt) |
| Backups | $5 |
| Cloud API budget (Groq/OpenRouter failover) | $20-50 |
| **Total** | **$70-100/month** |

### Scaled deployment (Phase 3)

| Item | Monthly Cost |
|------|--------------|
| 3× Hostinger VPS KVM 4 | $105 |
| Qdrant Cloud (2TB vectors) | $200-300 |
| Managed PostgreSQL | $50-100 |
| Redis Cloud (32GB) | $50-100 |
| Cloud API budget | $100-200 |
| Monitoring (Grafana Cloud) | $0-50 |
| **Total** | **$505-855/month** |

### Per-user cost at scale

| Scale | Infrastructure | Per User/Month |
|-------|---------------|----------------|
| 10,000 users | $100 | $0.01 |
| 100,000 users | $500 | $0.005 |
| 1,000,000 users | $1,500 | $0.0015 |

---

## Critical implementation priorities

The following sequence ensures a stable foundation before scaling:

1. **Week 1-2**: Deploy Ollama + LiteLLM + Redis on Docker Compose; implement basic failover chain
2. **Week 3-4**: Build supervisor agent with LangGraph; implement `interrupt()` for trade approvals
3. **Week 5-6**: Deploy 9 core agents with MCP tool servers; integrate NATS for messaging
4. **Week 7-8**: Implement memory architecture (PostgreSQL + Qdrant); context retrieval pipeline
5. **Week 9-10**: Add monitoring, alerting, and safety rails; stress test under load
6. **Week 11-12**: Voice integration for Jarvis X; self-improvement feedback loops

**Hard safety rails to implement immediately**:
- Max position size: $10,000 USD (code-enforced, not prompt-based)
- Daily loss limit: 5% of portfolio
- Human approval required above $1,000 trades
- Rate limit: 20 trades/hour per user
- Circuit breaker: Disable trading if 3 consecutive losses >2%

This architecture provides a clear path from a single $45/month VPS to a production-grade distributed system capable of handling millions of users, while maintaining the flexibility to adapt as requirements evolve and the crypto trading landscape changes.
