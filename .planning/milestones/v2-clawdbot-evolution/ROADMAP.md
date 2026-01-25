# Jarvis V2: Clawdbot Evolution Roadmap

**Created:** 2026-01-25
**Target:** Q2 2026
**Mode:** Ralph Wiggum Loop (Aggressive Parallel Execution)
**Quality Bar:** No shortcuts - production-grade from the start

---

## Executive Summary

Transform Jarvis from a trading-focused bot constellation into a **Clawdbot-equivalent intelligence system** with:
- Remote computer control from anywhere (not just LAN)
- GUI node system for device pairing and orchestration
- Dynamic skill installation and execution
- Advanced reasoning modes (thinking levels, streams)
- Voice capabilities (TTS/cloning via Qwen3-TTS)
- Web automation (Playwright-based browser control)
- Session management (compaction, context, persistence)
- Multi-model flexibility with intelligent routing

**Estimated Duration:** 8-12 weeks (aggressive parallel execution)
**Total Effort:** ~500-700 engineering hours
**Parallel Streams:** 4-6 concurrent work streams

---

## Current State Analysis

### Existing V1 Infrastructure (Leverage Points)

| Component | Status | V2 Integration |
|-----------|--------|----------------|
| **Supervisor** | Production | Extend for GUI node orchestration |
| **MCP Loader** | Production | Add new MCP servers (GUI, voice, web) |
| **Provider Manager** | Production | Add Claude/Gemini/GPT-4 reasoning modes |
| **Skill Manager** | Stub | Full dynamic skill system |
| **Browser Automation** | Basic | Replace with Playwright |
| **Qwen3-TTS** | Complete | Voice synthesis ready |
| **Memory System** | Phase 7 Complete | Session/context foundation |
| **PostgreSQL** | Production | Extend for skill/session storage |

### Critical Gaps (From Research)

| Gap | Severity | Phase |
|-----|----------|-------|
| Remote control infrastructure | CRITICAL | Phase 1 |
| GUI node pairing/execution | CRITICAL | Phase 2 |
| Dynamic skill system | HIGH | Phase 3 |
| Advanced reasoning modes | HIGH | Phase 4 |
| Voice cloning integration | MEDIUM | Phase 5 |
| Playwright web automation | MEDIUM | Phase 6 |
| Session compaction | MEDIUM | Phase 7 |
| Telegram bot intelligence parity | HIGH | Throughout |

---

## Phase Structure

### Phase 0: Foundation & Security Layer (Week 1)
**Priority:** CRITICAL
**Parallel:** No (blocks all other phases)
**Dependencies:** None

**Goal:** Establish secure remote access infrastructure that doesn't compromise V1.

**Deliverables:**
1. `core/remote/` - Remote control infrastructure
   - `auth.py` - JWT + API key + device pairing authentication
   - `tunnel.py` - Secure WebSocket tunnel (cloudflared/ngrok/custom)
   - `encryption.py` - E2E encryption for commands
   - `rate_limiter.py` - Per-device rate limiting
2. `api/remote/` - Remote control API endpoints
   - `/api/v2/remote/pair` - Device pairing initiation
   - `/api/v2/remote/execute` - Command execution
   - `/api/v2/remote/status` - System status
3. Security audit documentation
4. Integration tests for remote access

**Success Criteria:**
- [ ] Secure tunnel accessible from outside LAN
- [ ] Device pairing with QR code or manual code
- [ ] E2E encryption for all remote commands
- [ ] Rate limiting prevents abuse (100 req/min default)
- [ ] Audit log for all remote commands
- [ ] Zero V1 functionality regression

**Estimated Effort:** 40 hours
**Risk:** HIGH (security implications)
**Mitigation:** External security review before enabling

---

### Phase 1: Remote Execution Engine (Weeks 1-2)
**Priority:** CRITICAL
**Parallel:** After Phase 0 security layer
**Dependencies:** Phase 0

**Goal:** Build the core remote execution capability that all GUI nodes will use.

**Deliverables:**
1. `core/remote/executor.py` - Command execution engine
   - Safe subprocess execution with timeout
   - File system operations (read/write/list)
   - Process management (start/stop/status)
   - Resource limits (CPU, memory, disk)
2. `core/remote/capabilities.py` - Capability registry
   - System info (OS, CPU, RAM, disk)
   - Installed applications discovery
   - Available MCP tools enumeration
   - Network interfaces and connectivity
3. `core/remote/protocol.py` - Remote protocol specification
   - JSON-RPC over WebSocket
   - Binary data streaming (screenshots, files)
   - Heartbeat/keepalive mechanism
4. Database schema for device registry
5. Integration with existing supervisor

**Success Criteria:**
- [ ] Execute shell commands remotely with proper sandboxing
- [ ] Stream large files bidirectionally
- [ ] Real-time capability discovery
- [ ] Automatic reconnection on disconnect
- [ ] Works across Windows/Linux/Mac

**Estimated Effort:** 60 hours
**Risk:** MEDIUM (cross-platform complexity)
**Mitigation:** Start with Windows (primary platform), abstract early

---

### Phase 2: GUI Node System (Weeks 2-4)
**Priority:** HIGH
**Parallel:** After Phase 1 core
**Dependencies:** Phase 1

**Goal:** Create the visual interface for managing remote devices and executing actions.

**Deliverables:**
1. `core/gui/` - GUI node infrastructure
   - `node.py` - Node abstraction (local or remote)
   - `registry.py` - Node discovery and registration
   - `orchestrator.py` - Multi-node workflow execution
   - `canvas.py` - Visual workflow builder data model
2. `api/gui/` - GUI API endpoints
   - `/api/v2/gui/nodes` - Node CRUD operations
   - `/api/v2/gui/workflows` - Workflow management
   - `/api/v2/gui/execute` - Workflow execution
3. `frontend/v2/` - React-based GUI (Electron optional)
   - Node connection panel
   - Workflow canvas (drag-drop)
   - Real-time execution monitoring
   - Output visualization
4. Telegram `/nodes` command for basic node management
5. Documentation and tutorials

**Success Criteria:**
- [ ] Pair devices via QR code or manual code
- [ ] Visual workflow builder with 10+ node types
- [ ] Execute workflows across multiple devices
- [ ] Real-time progress and output streaming
- [ ] Persist workflows for reuse
- [ ] Telegram integration for quick node control

**Estimated Effort:** 100 hours
**Risk:** MEDIUM (frontend complexity)
**Mitigation:** Start with API-first, frontend can be incremental

---

### Phase 3: Dynamic Skill System (Weeks 3-5)
**Priority:** HIGH
**Parallel:** Can run alongside Phase 2
**Dependencies:** Phase 0 (security)

**Goal:** Transform the stub skill manager into a full dynamic skill system.

**Deliverables:**
1. `core/skills/` - Full skill system
   - `registry.py` - Skill discovery and registration
   - `loader.py` - Dynamic skill loading (local + remote)
   - `executor.py` - Safe skill execution sandbox
   - `marketplace.py` - Skill catalog and installation
   - `validator.py` - Skill code security validation
2. `skills/` - Skill directory structure
   - `builtin/` - Core skills (trading, research, coding)
   - `community/` - User-contributed skills
   - `custom/` - User-created skills
3. Skill manifest format (skill.yaml)
4. Skill dependencies and versioning
5. Telegram `/skill` command family
   - `/skill list` - List installed skills
   - `/skill install <url>` - Install from URL
   - `/skill run <name> [args]` - Execute skill
   - `/skill create <name>` - AI-assisted skill creation

**Success Criteria:**
- [ ] Install skills from URL or marketplace
- [ ] Execute skills with proper isolation
- [ ] AI-assisted skill creation (existing capability enhanced)
- [ ] Skill versioning and updates
- [ ] Security validation before execution
- [ ] 10+ builtin skills covering trading, research, coding

**Estimated Effort:** 80 hours
**Risk:** HIGH (security sandbox)
**Mitigation:** Use subprocess isolation, restrict file system access

---

### Phase 4: Advanced Reasoning Modes (Weeks 4-6)
**Priority:** HIGH
**Parallel:** Can run alongside Phases 2-3
**Dependencies:** Provider Manager (existing)

**Goal:** Add structured reasoning capabilities with multiple thinking levels.

**Deliverables:**
1. `core/reasoning/` - Reasoning system
   - `modes.py` - Reasoning mode definitions
     - `quick` - Fast response, no explicit reasoning
     - `standard` - Balanced reasoning
     - `deep` - Extended chain-of-thought
     - `research` - Multi-source verification
   - `chain.py` - Chain-of-thought orchestrator
   - `stream.py` - Streaming reasoning output
   - `verify.py` - Self-verification loop
2. `core/reasoning/prompts/` - Reasoning prompt templates
3. Integration with all Telegram bots
   - Auto-detect when deep reasoning needed
   - User can force mode with `/think deep <query>`
4. Reasoning output in responses
   - Collapsible thinking sections
   - Source citations
   - Confidence indicators

**Success Criteria:**
- [ ] 4 reasoning modes operational
- [ ] Auto-mode selection based on query complexity
- [ ] Streaming reasoning output to Telegram
- [ ] Confidence scores on factual claims
- [ ] Verification loop catches obvious errors
- [ ] Works with Claude, Grok, GPT-4, Gemini

**Estimated Effort:** 60 hours
**Risk:** MEDIUM (prompt engineering)
**Mitigation:** Extensive testing, user feedback loop

---

### Phase 5: Voice Capabilities (Weeks 5-7)
**Priority:** MEDIUM
**Parallel:** Can run alongside Phase 4
**Dependencies:** Qwen3-TTS (existing)

**Goal:** Complete voice ecosystem with input, output, and cloning.

**Deliverables:**
1. `core/voice/` - Voice system
   - `synthesis.py` - Unified TTS interface (wraps Qwen3-TTS)
   - `recognition.py` - Speech-to-text (Whisper integration)
   - `cloning.py` - Voice cloning management
   - `profiles.py` - Voice profile storage
2. Telegram voice integration
   - Voice message input (STT -> process -> TTS response)
   - Voice note output for long responses
   - Per-user voice preference
3. Voice profile management
   - Create profiles from audio samples
   - Switch between profiles
   - Profile sharing (opt-in)
4. API endpoints for voice operations

**Success Criteria:**
- [ ] Voice messages transcribed accurately (>90% WER)
- [ ] TTS responses sound natural
- [ ] Voice cloning from <30s audio sample
- [ ] Real-time streaming voice synthesis
- [ ] Works with Telegram voice notes
- [ ] GPU acceleration when available

**Estimated Effort:** 50 hours
**Risk:** MEDIUM (GPU requirements, audio quality)
**Mitigation:** CPU fallback, quality presets

---

### Phase 6: Web Automation (Weeks 6-8)
**Priority:** MEDIUM
**Parallel:** Can run alongside Phase 5
**Dependencies:** Phase 0 (security)

**Goal:** Replace basic browser automation with full Playwright integration.

**Deliverables:**
1. `core/web/` - Web automation system
   - `playwright_manager.py` - Browser lifecycle management
   - `automation.py` - High-level automation actions
   - `scraper.py` - Intelligent scraping with LLM
   - `forms.py` - Form interaction and filling
   - `persistence.py` - Session/cookie management
2. Playwright configuration
   - Firefox Developer Edition profile support
   - Anti-detection measures
   - Proxy support
3. Web automation skills
   - Gmail automation (compose, read, search)
   - Google Drive automation (upload, download, organize)
   - Generic website automation
4. Telegram `/web` command family
   - `/web open <url>` - Open URL
   - `/web screenshot` - Capture screenshot
   - `/web fill <form> <data>` - Fill forms
   - `/web extract <selectors>` - Extract data

**Success Criteria:**
- [ ] Playwright browser management (launch, close, multiple contexts)
- [ ] Persistent sessions survive restarts
- [ ] Form filling with LLM-assisted field matching
- [ ] Screenshot and visual analysis
- [ ] Anti-detection for major sites
- [ ] Works headless or with visible browser

**Estimated Effort:** 70 hours
**Risk:** MEDIUM (anti-bot detection)
**Mitigation:** Profile rotation, human-like delays, Firefox preference

---

### Phase 7: Session Management (Weeks 7-9)
**Priority:** MEDIUM
**Parallel:** Can run alongside Phase 6
**Dependencies:** Memory System (Phase 7 complete)

**Goal:** Add conversation context management with compaction and persistence.

**Deliverables:**
1. `core/session/` - Session system
   - `manager.py` - Session lifecycle
   - `context.py` - Context window management
   - `compaction.py` - Context summarization
   - `persistence.py` - Session save/restore
2. Session compaction strategies
   - Token-based compaction (keep last N tokens)
   - Importance-weighted compaction
   - Semantic deduplication
3. Cross-platform session linking
   - Same user on Telegram + X + API = one context
   - Session handoff between platforms
4. Telegram session commands
   - `/session status` - Current context size
   - `/session compact` - Force compaction
   - `/session export` - Export context
   - `/session clear` - Clear context

**Success Criteria:**
- [ ] Context persists across restarts
- [ ] Automatic compaction at 80% context limit
- [ ] Important information preserved during compaction
- [ ] Cross-platform session linking works
- [ ] Session export/import functional

**Estimated Effort:** 50 hours
**Risk:** LOW (builds on existing memory)
**Mitigation:** Leverage PostgreSQL from Phase 7

---

### Phase 8: Intelligence Parity (Weeks 8-10)
**Priority:** HIGH
**Parallel:** Final integration phase
**Dependencies:** Phases 3-7

**Goal:** Ensure ALL Telegram bots have equal access to V2 capabilities.

**Deliverables:**
1. Unified intelligence layer
   - Every bot can use skills
   - Every bot can use reasoning modes
   - Every bot can use voice
   - Every bot can use web automation
   - Every bot has session management
2. Bot-specific optimizations
   - Treasury bot: Trading-focused skills, quick reasoning default
   - Telegram bot: General skills, voice enabled
   - X bot: Research skills, deep reasoning for content
   - Bags Intel: Market analysis skills
   - Buy Tracker: Alert-focused skills
3. Shared context across bots
   - User preference learned in one bot available in others
   - Cross-bot workflow execution
4. Documentation for each bot's capabilities

**Success Criteria:**
- [ ] All 5 bots have full V2 capability access
- [ ] Consistent command syntax across bots
- [ ] Shared user context works
- [ ] No bot is "second class"
- [ ] Documentation complete for all bots

**Estimated Effort:** 60 hours
**Risk:** MEDIUM (integration complexity)
**Mitigation:** Feature flags for gradual rollout

---

### Phase 9: Testing & Hardening (Weeks 9-11)
**Priority:** HIGH
**Parallel:** Runs alongside Phase 8
**Dependencies:** All implementation phases

**Goal:** Production-grade quality for all V2 features.

**Deliverables:**
1. Test suites
   - Unit tests (80%+ coverage on new code)
   - Integration tests for all major flows
   - E2E tests for critical paths
   - Security tests for remote access
2. Performance optimization
   - Response time benchmarks
   - Memory usage optimization
   - Connection handling under load
3. Error handling
   - Graceful degradation when features unavailable
   - Clear error messages
   - Automatic retry with backoff
4. Monitoring integration
   - V2 feature usage metrics
   - Error rate tracking
   - Performance dashboards

**Success Criteria:**
- [ ] 80%+ test coverage on V2 code
- [ ] All security tests pass
- [ ] P95 latency <500ms for local operations
- [ ] Graceful degradation tested
- [ ] Monitoring dashboards live

**Estimated Effort:** 80 hours
**Risk:** LOW (standard practice)
**Mitigation:** CI/CD integration from Phase 0

---

### Phase 10: Documentation & Launch (Weeks 10-12)
**Priority:** MEDIUM
**Parallel:** Final phase
**Dependencies:** All previous phases

**Goal:** Production launch with complete documentation.

**Deliverables:**
1. User documentation
   - Getting started guide
   - Feature reference
   - Troubleshooting guide
   - Video tutorials
2. Developer documentation
   - Architecture overview
   - API reference
   - Skill development guide
   - Contributing guide
3. Migration guide (V1 -> V2)
4. Launch checklist
5. Post-launch monitoring plan

**Success Criteria:**
- [ ] All features documented
- [ ] Video tutorials for key features
- [ ] Migration guide tested
- [ ] Launch checklist 100% complete
- [ ] Monitoring in place

**Estimated Effort:** 40 hours
**Risk:** LOW
**Mitigation:** Documentation alongside development

---

## Parallel Execution Map

```
Week 1  |--Phase 0 (Security)--|
Week 2  |-----Phase 1 (Remote Exec)-----|
Week 3     |-----Phase 2 (GUI Nodes)--------|--Phase 3 (Skills)--|
Week 4        |-----Phase 2 (cont)-----|-----Phase 3 (cont)-----|--Phase 4 (Reasoning)--|
Week 5           |--Phase 2 (cont)--|--Phase 3 (cont)--|-----Phase 4 (cont)-----|
Week 6                                    |--Phase 5 (Voice)--|--Phase 6 (Web)--|
Week 7                                       |--Phase 5--|--Phase 6 (cont)--|--Phase 7 (Sessions)--|
Week 8                                          |--Phase 6 (cont)--|--Phase 7 (cont)--|
Week 9  |---------------------------Phase 8 (Intelligence Parity)---------------------------|
Week 10 |---------------------------Phase 9 (Testing)----------------------------------------|
Week 11    |--Phase 9 (cont)--|--Phase 10 (Docs)--|
Week 12       |--Phase 10 (cont/Launch)--|
```

**Maximum Parallel Streams:** 4
**Critical Path:** Phase 0 -> Phase 1 -> Phase 2 -> Phase 8 -> Phase 9 -> Phase 10

---

## Risk Register

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|------------|
| Security vulnerability in remote access | MEDIUM | CRITICAL | External audit, staged rollout, kill switch |
| Skill sandbox escape | MEDIUM | HIGH | Subprocess isolation, restricted fs, code review |
| Anti-bot detection breaks web automation | HIGH | MEDIUM | Profile rotation, human delays, Firefox |
| Voice quality insufficient | MEDIUM | MEDIUM | Quality presets, user feedback |
| Integration complexity causes V1 regression | MEDIUM | HIGH | Feature flags, extensive testing, rollback plan |
| Performance degradation under load | MEDIUM | MEDIUM | Load testing, caching, optimization |
| Cross-platform compatibility issues | HIGH | MEDIUM | Early testing on all platforms, abstraction |

---

## Resource Requirements

### Infrastructure
- Existing PostgreSQL (extend schema)
- Existing supervisor (extend)
- New: Cloudflared/ngrok for tunneling
- New: Playwright browser binaries (~500MB)
- Optional: GPU for voice synthesis

### Development
- 1-2 senior engineers (parallel execution)
- 1 security reviewer (Phase 0, ongoing)
- 1 QA engineer (Phase 9+)

### External Dependencies
- Anthropic Claude API (existing)
- X.AI Grok API (existing)
- Google Gemini API (optional)
- OpenAI API (optional)
- Playwright (MIT license)
- Qwen3-TTS (existing integration)

---

## Success Metrics

### Capability Metrics
- [ ] Remote access from 3+ device types
- [ ] 10+ skills in marketplace
- [ ] 4 reasoning modes operational
- [ ] Voice response rate >90% accuracy
- [ ] Web automation success rate >80%

### Quality Metrics
- [ ] Zero critical security vulnerabilities
- [ ] 80%+ test coverage on V2 code
- [ ] P95 latency <500ms local, <2s remote
- [ ] Zero V1 regressions

### User Metrics
- [ ] 5+ users complete device pairing
- [ ] 10+ workflows created
- [ ] Positive feedback on reasoning modes

---

## Next Steps (Immediate)

1. **Today:** Create Phase 0 detailed plan
2. **Day 2:** Security architecture review
3. **Day 3:** Begin Phase 0 implementation
4. **Week 1:** Complete Phase 0, start Phase 1
5. **Week 2:** Phase 1 + Phase 2 parallel

---

**Document Version:** 1.0
**Last Updated:** 2026-01-25
**Author:** Plan Agent (Claude Opus 4.5)
**Review:** Pending user approval
