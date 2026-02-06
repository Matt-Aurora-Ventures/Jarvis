# JARVIS Core Modules Index

**Last Updated:** 2026-02-02
**Purpose:** Complete reference for all core modules, their dependencies, and integration guidelines.

---

## Table of Contents

1. [Module Categories](#module-categories)
2. [Infrastructure](#infrastructure)
3. [Agent System](#agent-system)
4. [Automation](#automation)
5. [Security](#security)
6. [Skills](#skills)
7. [Trading & Finance](#trading--finance)
8. [Observability](#observability)
9. [Integrations](#integrations)
10. [Utilities](#utilities)
11. [Dependency Graph](#dependency-graph)
12. [Load Order](#load-order)
13. [Migration Guide](#migration-guide)
14. [Breaking Changes](#breaking-changes)

---

## Module Categories

### Overview

```
core/
├── Infrastructure/      # Foundation (config, state, events, orchestration)
├── Agent System/        # Multi-agent framework (4 specialized agents)
├── Automation/          # Browser, GUI, OAuth, computer control
├── Security/            # Audit, encryption, key management, RBAC
├── Skills/              # Dynamic skill system (Clawdbot-style)
├── Trading/             # Solana DEX, Jupiter, risk management
├── Observability/       # Health checks, metrics, audit trails
├── Integrations/        # External APIs (GitHub, Gmail, LinkedIn, X, Trello)
├── Utilities/           # Helpers, models, exceptions
└── Coordination/        # Multi-agent coordination (whiteboard, handoffs)
```

---

## Infrastructure

**Purpose:** Core system foundations - configuration, state management, orchestration.

### Core Infrastructure

| Module | Key Classes/Functions | Description |
|--------|----------------------|-------------|
| `config.py` | `load_config()`, `save_local_config()`, `update_local_config()` | JSON config loader with base/local override support |
| `safety.py` | `SafetyContext`, `resolve_mode()`, `confirm_apply()`, `allow_action()` | Dry-run mode, apply confirmations |
| `commands.py` | `not_implemented()` | Command stub system for phased rollout |
| `orchestrator.py` | `Orchestrator`, `LoopPhase`, `BrainState` | Main brain loop: OBSERVE → INTERPRET → PLAN → ACT → REVIEW → LEARN |
| `objectives.py` | `Objective`, `ObjectiveStatus`, `ObjectiveSource` | Task/objective management system |
| `state.py` | State persistence utilities | System state management |
| `memory.py` | Memory systems | Short/long-term memory |
| `output.py` | Output formatting | Structured output formatting |

### Event & Queue Systems

| Module | Description |
|--------|-------------|
| `event_catalyst.py` | Event-driven catalyst system |
| `input_broker.py` | Input routing and brokering |

### Context Management

| Module | Description |
|--------|-------------|
| `context_organizer.py` | Context organization for agents |
| `context_router.py` | Route context to appropriate handlers |
| `semantic_memory.py` | Semantic memory with vector embeddings |
| `memory_driven_behavior.py` | Memory-based decision making |

---

## Agent System

**Purpose:** Multi-agent delegation framework with specialized roles.

### Core Agent Framework

| Module | Key Classes | Description |
|--------|-------------|-------------|
| `agents/__init__.py` | `BaseAgent`, `AgentRole`, `AgentCapability` | Agent base classes and interfaces |
| `agents/registry.py` | `AgentRegistry`, `get_registry()` | Agent discovery and registration |
| `agents/researcher.py` | `ResearcherAgent` | Web research, summarization (Groq - fast) |
| `agents/operator.py` | `OperatorAgent` | Task execution, UI automation (Groq - fast) |
| `agents/trader.py` | `TraderAgent` | Crypto trading pipeline (Claude - quality) |
| `agents/architect.py` | `ArchitectAgent` | Self-improvement proposals (Claude - quality) |

### Agent Support Systems

| Module | Description |
|--------|-------------|
| `agent_router.py` | Route tasks to appropriate agents |
| `agent_graph.py` | Agent relationship and dependency graph |
| `autonomous_agent.py` | Autonomous agent base class |
| `logic_core.py` | Core reasoning logic for agents |

### Learning & Improvement

| Module | Description |
|--------|-------------|
| `autonomous_learner.py` | Self-learning capabilities |
| `autonomous_improver.py` | Self-improvement engine |
| `background_improver.py` | Background improvement tasks |
| `iterative_improver.py` | Iterative refinement loops |
| `learning_validator.py` | Validate learning outcomes |
| `self_evaluator.py` | Self-evaluation and metrics |
| `self_healing.py` | Self-healing and recovery |

---

## Automation

**Purpose:** Comprehensive computer automation - browser, GUI, OAuth, Windows control.

### Browser Automation

| Module | Key Classes | Description |
|--------|-------------|-------------|
| `automation/browser_cdp.py` | Chrome DevTools Protocol automation |
| `automation/browser_agent.py` | High-level browser automation agent |
| `browser_automation.py` | Legacy browser automation |

### Credential & OAuth Management

| Module | Key Classes | Description |
|--------|-------------|-------------|
| `automation/credential_manager.py` | `CredentialProvider` | 1Password/Bitwarden integration |
| `automation/google_oauth.py` | `OAuthManager` | Google OAuth multi-account management |
| `automation/x_multi_account.py` | X/Twitter multi-account automation |

### Platform Automation

| Module | Description |
|--------|-------------|
| `automation/linkedin_client.py` | LinkedIn automation |
| `automation/gui_automation.py` | Windows GUI automation (PyAutoGUI) |
| `automation/computer_control.py` | System-level computer control |
| `automation/remote_control_client.py` | Remote machine control client |
| `automation/remote_control_server.py` | Remote control server |
| `automation/wake_on_lan.py` | Wake-on-LAN for remote machines |

### Task Scheduling

| Module | Description |
|--------|-------------|
| `automation/scheduler.py` | Cron-style task scheduling |
| `automation/task_scheduler.py` | Windows Task Scheduler integration |
| `automation/chains.py` | Automation workflow chains |
| `automation/recorder.py` | Record and replay automation |
| `automation/orchestrator.py` | Automation orchestration layer |
| `automation/life_control.py` | Life automation workflows |

### Interfaces

| Module | Key Classes | Description |
|--------|-------------|-------------|
| `automation/interfaces.py` | `Credential`, `BrowserSession`, `OAuthToken` | Core automation interfaces |

---

## Security

**Purpose:** Comprehensive security framework - auditing, encryption, key management, RBAC.

### Core Security

| Module | Key Classes/Functions | Description |
|--------|----------------------|-------------|
| `security/audit.py` | `SecurityAuditor`, `run_security_audit()` | Security audit framework |
| `security/key_vault.py` | `KeyVault`, `get_key_vault()` | Secure key storage (encrypted SQLite) |
| `security/encryption.py` | `SecureEncryption`, `get_encryption()` | AES-256 encryption |
| `security/sanitizer.py` | `sanitize_string()`, `sanitize_filename()` | Input sanitization |

### Authentication & Authorization

| Module | Key Classes | Description |
|--------|-------------|-------------|
| `security/session_manager.py` | `SecureSessionManager` | Secure session management |
| `security/two_factor.py` | `TwoFactorAuth` | 2FA implementation |
| `security/rbac.py` | `rbac`, `Permission`, `Role`, `User` | Role-based access control |
| `security/request_signing.py` | `RequestSigner` | Request signing for APIs |

### Key Management

| Module | Description |
|--------|-------------|
| `security/key_manager.py` | Key lifecycle management |
| `security/key_rotation.py` | `KeyRotationManager`, auto-rotation for Anthropic/Telegram/Grok |
| `security/secret_manager.py` | Secret storage and retrieval |
| `security/secret_rotation.py` | Automated secret rotation |
| `security/enhanced_secrets_manager.py` | Enhanced secret management |

### Input Validation & Safety

| Module | Key Functions | Description |
|--------|--------------|-------------|
| `security/input_validator.py` | `validate_token()`, `validate_amount()`, `is_safe_string()` | Input validation |
| `security/sql_safety.py` | `SafeQueryBuilder`, `check_query_safety()` | SQL injection prevention |
| `security/safe_pickle.py` | Safe pickle deserialization |
| `security/scam_detector.py` | Detect scam tokens/addresses |

### Audit & Monitoring

| Module | Description |
|--------|-------------|
| `security/audit_trail.py` | `AuditTrail`, immutable event log |
| `security/audit_logger.py` | `AuditLogger`, structured audit logging |
| `security/audit_chain.py` | Blockchain-style audit chain |
| `security/audit_checklist.py` | Security checklist framework |
| `security/comprehensive_audit_logger.py` | Enhanced audit logging |

### Rate Limiting

| Module | Description |
|--------|-------------|
| `security/rate_limiter.py` | `RateLimiter`, token bucket |
| `security/enhanced_rate_limiter.py` | Enhanced rate limiting |

### Wallet & Transaction Security

| Module | Description |
|--------|-------------|
| `security/wallet_validation.py` | `validate_solana_address()`, validate Ethereum |
| `security/wallet_audit.py` | `WalletAuditor`, wallet security checks |
| `security/transaction_verifier.py` | Transaction verification |
| `security/tx_confirmation.py` | Transaction confirmation UI |
| `security/multisig_treasury.py` | Multisig wallet management |

### Data Protection

| Module | Description |
|--------|-------------|
| `security/sensitive_filter.py` | `SensitiveDataFilter` - scrub secrets from logs |
| `security/scrubber.py` | Data scrubbing utilities |
| `security/encrypted_storage.py` | Encrypted file storage |

### Credential Management

| Module | Description |
|--------|-------------|
| `security/credential_loader.py` | `CredentialLoader`, load X/Telegram credentials |
| `security/api_key_scopes.py` | API key scope management |

### Emergency Systems

| Module | Description |
|--------|-------------|
| `security/emergency_shutdown.py` | Emergency shutdown protocol |
| `security/incident_response.py` | Incident response playbooks |

---

## Skills

**Purpose:** Clawdbot-style dynamic skill system for extensibility.

| Module | Key Classes | Description |
|--------|-------------|-------------|
| `skills/__init__.py` | `SkillRegistry`, `SkillExecutor`, `SkillManager` | Main skill system exports |
| `skills/registry.py` | `SkillRegistry` | Discover and register skills |
| `skills/executor.py` | `SkillExecutor`, `SkillExecutionResult` | Execute skills with isolation |
| `skills/manager.py` | `SkillManager`, `SkillInstallResult` | Install/remove/update skills |
| `skills/self_healing.py` | `SelfHealingSkillRegistry`, `execute_with_healing()` | Auto-install missing skills |
| `skill_manager.py` | Legacy skill manager | (Deprecated - use `skills/`) |

**Skill Structure:**
```
skills/
  skill-name/
    SKILL.md         # Skill definition
    script.py        # Executable
    requirements.txt # Dependencies
    config.json      # Configuration
```

---

## Trading & Finance

**Purpose:** Solana DEX trading, Jupiter integration, risk management.

### Execution Engines

| Module | Description |
|--------|-------------|
| `solana_execution.py` | Core Solana transaction execution |
| `jupiter_orders.py` | Jupiter limit orders |
| `jupiter_perps.py` | Jupiter perpetuals trading |
| `jito_executor.py` | Jito MEV bundle execution |

### Trading Strategy

| Module | Description |
|--------|-------------|
| `micro_cap_sniper.py` | Micro-cap token sniping |
| `lute_momentum.py` | Momentum trading strategy |
| `liquidation_bot.py` | Liquidation hunting bot |
| `swap_simulator.py` | Simulate swaps before execution |

### Risk Management

| Module | Description |
|--------|-------------|
| `position_reconciler.py` | Reconcile on-chain vs tracked positions |
| `intent_trade_reconciler.py` | Reconcile trade intents |
| `strategy_scores.py` | Strategy scoring and selection |

### Market Data

| Module | Description |
|--------|-------------|
| `solana_scanner.py` | Scan Solana chain for opportunities |
| `solana_tokens.py` | Token metadata and discovery |
| `gmgn_metrics.py` | GMGN.ai metrics integration |
| `rugcheck.py` | Rug pull detection |
| `dextools.py` | DexTools API integration |

### Wallet & Network

| Module | Description |
|--------|-------------|
| `solana_wallet.py` | Wallet management |
| `solana_network_guard.py` | Network health monitoring |
| `rpc_diagnostics.py` | RPC endpoint diagnostics |

### Analytics

| Module | Description |
|--------|-------------|
| `sentiment_registry.py` | Token sentiment tracking |
| `opportunity_engine.py` | Opportunity detection and ranking |

### Economics

| Module | Description |
|--------|-------------|
| `economics/costs.py` | Cost tracking |
| `economics/revenue.py` | Revenue tracking |
| `economics/database.py` | Economics database |
| `economics/dashboard.py` | Economics dashboard |
| `fee_model.py` | Fee calculation models |

### Exotic Trading

| Module | Description |
|--------|-------------|
| `hyperliquid.py` | Hyperliquid DEX integration |
| `circular_logic.py` | Circular arbitrage detection |

---

## Observability

**Purpose:** Health checks, diagnostics, metrics, audit logging.

### Health & Diagnostics

| Module | Description |
|--------|-------------|
| `diagnostics.py` | System diagnostics |
| `rpc_diagnostics.py` | RPC health checks |

### Audit Systems

| Module | Description |
|--------|-------------|
| `audit/__init__.py` | Audit framework |
| `audit/runner.py` | Audit execution |
| `security/audit_trail.py` | Immutable audit log |
| `security/audit_logger.py` | Structured audit logging |

### Error Handling

| Module | Description |
|--------|-------------|
| `error_recovery.py` | Error recovery strategies |
| `command_watchdog.py` | Command timeout/watchdog |
| `emergency_kill.py` | Emergency kill switch |

---

## Integrations

**Purpose:** External API integrations (GitHub, Gmail, LinkedIn, X, Trello).

| Module | Description |
|--------|-------------|
| `integrations/github_integration.py` | GitHub API wrapper |
| `integrations/gmail_integration.py` | Gmail API wrapper |
| `integrations/linkedin_integration.py` | LinkedIn API wrapper |
| `integrations/x_integration.py` | X/Twitter API wrapper |
| `integrations/trello_integration.py` | Trello API wrapper |

### Research & Data

| Module | Description |
|--------|-------------|
| `research.py` | General research utilities |
| `research_engine.py` | Research workflow engine |
| `autonomous_researcher.py` | Autonomous research agent |
| `data_ingestion.py` | Data ingestion pipelines |
| `notion_ingest.py` | Notion data ingestion |
| `notion_deep_extractor.py` | Deep Notion extraction |

---

## Utilities

**Purpose:** Helper functions, models, exceptions, storage.

### Core Utilities

| Module | Description |
|--------|-------------|
| `storage_utils.py` | File storage utilities |
| `notes_manager.py` | Notes management |
| `prompt_library.py` | Prompt templates |
| `prompt_distiller.py` | Prompt optimization |
| `provider_manager.py` | LLM provider management |
| `dspy_classifier.py` | DSPy-based classification |

### Execution & Validation

| Module | Description |
|--------|-------------|
| `shell_executor.py` | Safe shell command execution |
| `command_validator.py` | Command validation |
| `observation_daemon.py` | Background observation daemon |
| `action_feedback.py` | Action feedback loop |

### Analysis & Optimization

| Module | Description |
|--------|-------------|
| `profile_analyzer.py` | Performance profiling |
| `conversation_backtest.py` | Backtest conversation flows |
| `google_cli.py` | Google CLI utilities |

### Browser & UI

| Module | Description |
|--------|-------------|
| `hotkeys.py` | Hotkey management |
| `interview.py` | Interactive interview system |

### Lifecycle

| Module | Description |
|--------|-------------|
| `overnight.py` | Overnight maintenance tasks |
| `ability_acquisition.py` | Acquire new capabilities dynamically |

### Economics & Ops

| Module | Description |
|--------|-------------|
| `life_os_router.py` | LifeOS routing |
| `git_ops.py` | Git operations |

### Evolution

| Module | Description |
|--------|-------------|
| `evolution/__init__.py` | Evolution framework |
| `evolution/gym/__init__.py` | Evolution gym/training |

---

## Coordination

**Purpose:** Multi-agent coordination and state sharing.

| Module | Key Classes | Description |
|--------|-------------|-------------|
| `coordination/whiteboard.py` | `Whiteboard` | Shared state board for agent coordination |
| `coordination/task_handoff.py` | `TaskHandoff` | Hand off tasks between agents |
| `coordination/token_coordinator.py` | `TokenCoordinator` | Coordinate token operations |

---

## Dependency Graph

### Core Dependencies

```
┌─────────────────┐
│ config.py       │  ← Foundation (no dependencies)
└────────┬────────┘
         │
    ┌────▼────┐
    │ safety  │  ← Depends on config
    └────┬────┘
         │
    ┌────▼────────┐
    │ state.py    │  ← Depends on config
    └────┬────────┘
         │
    ┌────▼──────────┐
    │ objectives.py │  ← Depends on state, config
    └────┬──────────┘
         │
    ┌────▼──────────────┐
    │ orchestrator.py   │  ← Depends on config, objectives, memory, safety, state
    └───────────────────┘
```

### Agent System Dependencies

```
┌──────────────────────┐
│ agents/base.py       │  ← Base agent interface
└──────────┬───────────┘
           │
    ┌──────▼──────────────────────────────┐
    │ agents/registry.py                  │  ← Agent registration
    └──────┬──────────────────────────────┘
           │
    ┌──────▼─────────────────────────────┐
    │ agents/researcher.py               │
    │ agents/operator.py                 │  ← Specialized agents
    │ agents/trader.py                   │
    │ agents/architect.py                │
    └────────────────────────────────────┘
```

### Security Dependencies

```
┌──────────────────┐
│ encryption.py    │  ← Foundation
└────────┬─────────┘
         │
    ┌────▼────────┐
    │ key_vault   │  ← Depends on encryption
    └────┬────────┘
         │
    ┌────▼────────────┐
    │ secret_manager  │  ← Depends on key_vault
    └────┬────────────┘
         │
    ┌────▼────────────────────┐
    │ credential_loader       │  ← Depends on secret_manager, key_vault
    └─────────────────────────┘
```

### Automation Dependencies

```
┌───────────────────┐
│ interfaces.py     │  ← Core interfaces
└─────────┬─────────┘
          │
    ┌─────▼──────────────────────────┐
    │ credential_manager.py          │  ← 1Password/Bitwarden
    │ google_oauth.py                │  ← OAuth
    │ browser_cdp.py                 │  ← Browser
    └─────────┬──────────────────────┘
              │
    ┌─────────▼────────────────────┐
    │ orchestrator.py              │  ← High-level automation
    └──────────────────────────────┘
```

### Trading Dependencies

```
┌──────────────────────┐
│ solana_wallet.py     │  ← Foundation
└──────────┬───────────┘
           │
    ┌──────▼────────────────┐
    │ solana_execution.py   │  ← Transaction execution
    └──────────┬────────────┘
               │
    ┌──────────▼────────────────┐
    │ jupiter_orders.py         │  ← DEX integration
    │ jupiter_perps.py          │
    │ jito_executor.py          │
    └──────────┬────────────────┘
               │
    ┌──────────▼─────────────────┐
    │ position_reconciler.py     │  ← Risk management
    └────────────────────────────┘
```

---

## Load Order

### Recommended Bootstrap Sequence

1. **Phase 1: Foundation**
   ```python
   from core import config
   from core import safety
   from core import state
   ```

2. **Phase 2: Security**
   ```python
   from core.security import encryption, key_vault
   from core.security import sanitizer, input_validator
   from core.security import audit_trail, audit_logger
   ```

3. **Phase 3: Infrastructure**
   ```python
   from core import objectives
   from core import memory
   from core.coordination import whiteboard
   ```

4. **Phase 4: Skills & Agents**
   ```python
   from core.skills import SkillRegistry, SkillExecutor
   from core.agents import AgentRegistry, get_registry
   ```

5. **Phase 5: Automation** (if needed)
   ```python
   from core.automation import credential_manager, browser_cdp
   from core.automation import orchestrator
   ```

6. **Phase 6: Trading** (if needed)
   ```python
   from core import solana_wallet, solana_execution
   from core import jupiter_orders
   ```

7. **Phase 7: Orchestration**
   ```python
   from core.orchestrator import Orchestrator
   ```

### Import Cycles to Avoid

**AVOID:**
- Importing `orchestrator.py` before `objectives.py` is initialized
- Importing agents before `agents/registry.py` is set up
- Importing trading modules before `solana_wallet.py` is configured
- Importing automation before `automation/interfaces.py` is loaded

**Safe Pattern:**
```python
# Good: Top-level imports
from core import config, safety, state

# Good: Lazy imports for heavy modules
def get_orchestrator():
    from core.orchestrator import Orchestrator
    return Orchestrator()

# Good: Conditional imports
if trading_enabled:
    from core import jupiter_orders
```

---

## Migration Guide

### From Legacy Modules to New Core

#### 1. Configuration

**Old:**
```python
import os
api_key = os.getenv("API_KEY")
```

**New:**
```python
from core.config import load_config
config = load_config()
api_key = config["api"]["key"]
```

#### 2. Security

**Old:**
```python
# Manual encryption
from cryptography.fernet import Fernet
cipher = Fernet(key)
```

**New:**
```python
from core.security import get_encryption
encryption = get_encryption()
encrypted = encryption.encrypt("secret")
```

#### 3. Skill System

**Old:**
```python
# Manual skill loading
import importlib
skill = importlib.import_module("skills.my_skill")
```

**New:**
```python
from core.skills import SkillRegistry, SkillExecutor
registry = SkillRegistry()
executor = SkillExecutor(registry)
result = executor.execute("my_skill", ["arg1"])
```

#### 4. Agent Delegation

**Old:**
```python
# Direct LLM calls
response = anthropic.messages.create(...)
```

**New:**
```python
from core.agents import get_registry
registry = get_registry()
researcher = registry.get_agent("researcher")
result = await researcher.execute(task)
```

#### 5. Automation

**Old:**
```python
# Manual Selenium setup
from selenium import webdriver
driver = webdriver.Chrome()
```

**New:**
```python
from core.automation import browser_cdp
session = browser_cdp.create_session()
await session.navigate("https://example.com")
```

#### 6. Trading

**Old:**
```python
# Direct Jupiter API calls
from jupiter import Jupiter
jupiter = Jupiter(...)
```

**New:**
```python
from core import jupiter_orders
order = jupiter_orders.create_limit_order(...)
```

### Integration Checklist

- [ ] Replace `os.getenv()` with `config.load_config()`
- [ ] Replace manual encryption with `core.security.encryption`
- [ ] Replace direct API calls with `core.integrations.*`
- [ ] Replace manual skill loading with `core.skills`
- [ ] Replace direct LLM calls with `core.agents`
- [ ] Replace Selenium with `core.automation.browser_cdp`
- [ ] Add audit logging via `core.security.audit_logger`
- [ ] Add input validation via `core.security.input_validator`
- [ ] Use `core.safety` for dry-run/apply modes
- [ ] Use `core.coordination.whiteboard` for multi-agent state

---

## Breaking Changes

### v2.0 (Current)

1. **Config System**
   - `lifeos.config.json` now required in `lifeos/config/`
   - Local overrides go to `lifeos.config.local.json`
   - Breaking: Environment variables no longer primary config source

2. **Security**
   - `KeyVault` now required for all API keys
   - Breaking: Plain-text `.env` files deprecated
   - Migration: Run `scripts/migrate_env_to_vault.py`

3. **Skills**
   - Skills must follow SKILL.md format
   - Breaking: Old skill format no longer supported
   - Migration: Use `core.skills.manager.migrate_legacy_skill()`

4. **Agents**
   - Agents must register with `AgentRegistry`
   - Breaking: Direct agent instantiation deprecated
   - Migration: Use `get_registry().get_agent(name)`

5. **Automation**
   - Browser automation now uses CDP, not Selenium
   - Breaking: Selenium-based code will fail
   - Migration: Rewrite using `core.automation.browser_cdp`

6. **Trading**
   - All trades must go through `position_reconciler`
   - Breaking: Direct Jupiter calls will not be tracked
   - Migration: Use `core.jupiter_orders` wrapper

### Deprecation Warnings

| Module | Status | Replacement | Removal |
|--------|--------|-------------|---------|
| `skill_manager.py` | Deprecated | `core.skills.manager` | v2.5 |
| `browser_automation.py` | Deprecated | `core.automation.browser_cdp` | v2.5 |
| Direct `os.getenv()` | Discouraged | `core.config.load_config()` | v3.0 |
| Plain `.env` files | Discouraged | `core.security.key_vault` | v3.0 |

---

## Quick Reference

### Most Common Imports

```python
# Configuration
from core.config import load_config

# Safety
from core.safety import SafetyContext, resolve_mode, allow_action

# Security
from core.security import get_key_vault, get_encryption, audit_logger
from core.security import validate_token, validate_address, sanitize_string

# Skills
from core.skills import SkillRegistry, SkillExecutor, execute_with_healing

# Agents
from core.agents import get_registry

# Automation
from core.automation import browser_cdp, credential_manager, google_oauth

# Trading
from core import jupiter_orders, solana_wallet, position_reconciler

# Coordination
from core.coordination import whiteboard, task_handoff

# Orchestration
from core.orchestrator import Orchestrator
```

### Environment Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Initialize KeyVault
python scripts/init_key_vault.py

# Migrate .env to KeyVault
python scripts/migrate_env_to_vault.py

# Verify setup
python -c "from core.config import load_config; print(load_config())"
```

---

## Support & Documentation

- **Full docs:** `docs/`
- **Security guide:** `docs/SECURITY.md`
- **Agent guide:** `docs/AGENTS.md`
- **Automation guide:** `docs/AUTOMATION_SETUP_GUIDE.md`
- **Trading guide:** `docs/TRADING.md`

---

**Maintained by:** Jarvis Core Team
**Last Audit:** 2026-02-02
**Next Review:** 2026-03-01
