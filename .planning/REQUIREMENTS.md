# Requirements: Jarvis V3 — Sovereign AI Operating System

**Defined:** 2026-02-16
**Core Value:** The boot document — a portable, encrypted representation of the user's entire context that initializes any model on any platform.

## v3 Requirements

### Infrastructure

- [ ] **INFRA-01**: Codebase refactored into clean monorepo with proper Python package structure (pyproject.toml, src layout)
- [ ] **INFRA-02**: CI/CD pipeline runs tests and linting on every push
- [ ] **INFRA-03**: Database migrations managed by Alembic with versioned schema changes
- [ ] **INFRA-04**: Docker Compose orchestrates all services (gateway, memory, orchestrator, interfaces)
- [ ] **INFRA-05**: Scattered memory files consolidated into single persistence layer (PostgreSQL + Qdrant)

### LLM Gateway

- [ ] **GATE-01**: LiteLLM proxy deployed as Docker container exposing unified OpenAI-compatible endpoint
- [ ] **GATE-02**: Task-based routing rules configured (sentiment→Grok, reasoning→Claude, code→Claude, private→local Ollama)
- [ ] **GATE-03**: Automatic failover chain (primary→secondary→tertiary→local) with health checks and cooldown
- [ ] **GATE-04**: Per-model spend tracking with configurable budget controls
- [ ] **GATE-05**: PII masking via Presidio before sending to cloud models

### Memory Engine

- [ ] **MEM-01**: Mem0 extraction pipeline processes every conversation to identify facts, entities, and preferences
- [ ] **MEM-02**: Mem0 conflict resolution (add/merge/invalidate/skip) keeps memory consistent
- [ ] **MEM-03**: Letta self-editing memory runtime — agent manages its own context via tool calls
- [ ] **MEM-04**: Context window guard monitors token count and triggers summarization before overflow
- [ ] **MEM-05**: Graphiti temporal knowledge graph tracks entity relationships and how they evolve over time
- [ ] **MEM-06**: Four-tier memory hierarchy (working→episodic→semantic→procedural) with automatic promotion/demotion
- [ ] **MEM-07**: Memory is transparent and user-editable (plain Markdown view of memory state)

### Boot Document

- [ ] **BOOT-01**: Boot document auto-generates from Mem0 persistent store after each session
- [ ] **BOOT-02**: Boot document contains user profile, active goals, current projects, key relationships, communication preferences
- [ ] **BOOT-03**: Boot document injected as system prompt at every new interaction
- [ ] **BOOT-04**: Boot document is portable — can initialize Claude, GPT, Grok, or local models identically
- [ ] **BOOT-05**: Boot document encrypted at rest and in transit

### Agent Orchestration

- [ ] **ORCH-01**: LangGraph orchestrator replaces Python supervisor process
- [ ] **ORCH-02**: Trading domain runs as stateful subgraph with explicit state management
- [ ] **ORCH-03**: Research domain subgraph provides web search and document analysis
- [ ] **ORCH-04**: State checkpoints to PostgreSQL for pause/resume and time-travel debugging
- [ ] **ORCH-05**: Orchestrator routes between domains based on user intent classification
- [ ] **ORCH-06**: MCP (Model Context Protocol) used for standardized tool and data access across agents

### Domain Plugins

- [ ] **PLUG-01**: Plugin registry allows adding new domains without modifying core orchestrator code
- [ ] **PLUG-02**: Trading engine wrapped as first domain plugin (all existing functionality preserved)
- [ ] **PLUG-03**: Research domain plugin provides web search, document analysis, and deep research mode
- [ ] **PLUG-04**: Communication domain plugin handles email drafts and social media scheduling

### Interface Layer

- [ ] **INTF-01**: Central WebSocket gateway (hub) handles message routing, session management, and access control
- [ ] **INTF-02**: WhatsApp channel adapter via Baileys library for consumer messaging
- [ ] **INTF-03**: Telegram channel adapter upgraded from current bot with normalized message parsing
- [ ] **INTF-04**: Web PWA dashboard with portfolio monitoring, memory graph visualization, agent status
- [ ] **INTF-05**: Voice interface via Whisper STT + Piper TTS for hands-free interaction
- [ ] **INTF-06**: All channels route through central gateway for unified state management

### Edge & Sovereignty

- [ ] **EDGE-01**: Quantized models (Gemma 3 1B, Phi-3 Mini, Llama 3.2 3B) available for on-device inference
- [ ] **EDGE-02**: Hybrid routing — private/simple tasks run locally, complex reasoning goes to cloud
- [ ] **EDGE-03**: Boot document syncs encrypted across devices via user-controlled infrastructure
- [ ] **EDGE-04**: All personal data stored on user infrastructure — zero third-party data storage

## Future Requirements (v4+)

### Monetization
- **TOKEN-01**: $KR8TIV token integration for access, staking, governance
- **PAY-01**: Stripe payments for premium features
- **FEE-01**: Success fee system for profitable trades

### Extended Domains
- **HEALTH-01**: Wearable data integration and habit tracking
- **EDU-01**: Learning paths and flashcard generation
- **SCHED-01**: Calendar optimization and time blocking
- **FIN-01**: Tax reporting and budget automation

### Mobile
- **MOB-01**: Native iOS app
- **MOB-02**: Native Android app

### Advanced AI
- **AI-01**: DSPy-based procedural memory optimization
- **AI-02**: Sleep-time agents for async memory consolidation (Letta pattern)
- **AI-03**: xRouter RL-based sequential routing decisions
- **AI-04**: CrewAI role-based agent teams within domains

## Out of Scope

| Feature | Reason |
|---------|--------|
| $KR8TIV token | Infrastructure first — monetization in v4 |
| Native mobile apps | PWA covers mobile; native adds maintenance burden |
| Multi-user isolation | Single-user personal AI OS — not a SaaS platform |
| Full strategy migration | 81 strategies stay in existing engine, wrapped as plugin |
| Real-time chat | Not a social platform |
| iMessage adapter | Apple ecosystem lock-in, WhatsApp covers messaging |
| Signal adapter | Niche user base, defer to community contribution |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| INFRA-01 | Phase 1 | Pending |
| INFRA-02 | Phase 1 | Pending |
| INFRA-03 | Phase 1 | Pending |
| INFRA-04 | Phase 1 | Pending |
| INFRA-05 | Phase 1 | Pending |
| GATE-01 | Phase 2 | Pending |
| GATE-02 | Phase 2 | Pending |
| GATE-03 | Phase 2 | Pending |
| GATE-04 | Phase 2 | Pending |
| GATE-05 | Phase 2 | Pending |
| MEM-01 | Phase 3 | Pending |
| MEM-02 | Phase 3 | Pending |
| MEM-03 | Phase 6 | Pending |
| MEM-04 | Phase 6 | Pending |
| MEM-05 | Phase 6 | Pending |
| MEM-06 | Phase 6 | Pending |
| MEM-07 | Phase 3 | Pending |
| BOOT-01 | Phase 3 | Pending |
| BOOT-02 | Phase 3 | Pending |
| BOOT-03 | Phase 3 | Pending |
| BOOT-04 | Phase 3 | Pending |
| BOOT-05 | Phase 3 | Pending |
| ORCH-01 | Phase 4 | Pending |
| ORCH-02 | Phase 4 | Pending |
| ORCH-03 | Phase 4 | Pending |
| ORCH-04 | Phase 4 | Pending |
| ORCH-05 | Phase 4 | Pending |
| ORCH-06 | Phase 4 | Pending |
| PLUG-01 | Phase 5 | Pending |
| PLUG-02 | Phase 5 | Pending |
| PLUG-03 | Phase 5 | Pending |
| PLUG-04 | Phase 8 | Pending |
| INTF-01 | Phase 5 | Pending |
| INTF-02 | Phase 5 | Pending |
| INTF-03 | Phase 5 | Pending |
| INTF-04 | Phase 7 | Pending |
| INTF-05 | Phase 7 | Pending |
| INTF-06 | Phase 5 | Pending |
| EDGE-01 | Phase 8 | Pending |
| EDGE-02 | Phase 8 | Pending |
| EDGE-03 | Phase 8 | Pending |
| EDGE-04 | Phase 8 | Pending |

**Coverage:**
- v3 requirements: 42 total
- Mapped to phases: 42
- Unmapped: 0 ✓

---
*Requirements defined: 2026-02-16*
*Last updated: 2026-02-16 after V3 milestone initialization*
