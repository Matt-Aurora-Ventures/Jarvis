# Jarvis/LifeOS - Top Issues Analysis

## Priority Definitions

- **P0 (Critical)**: System is broken/unusable without fixing this
- **P1 (High)**: Major functionality impaired or significant risk
- **P2 (Medium)**: Quality/UX issues that should be addressed

---

## P0 - Critical Issues (Fix First)

### P0-1: Memory Echo Chamber Creates Circular/Shallow Behavior

**Symptom**: Conversations feel circular, shallow, don't progress toward goals.

**Root Cause**: In [conversation.py:45-55](core/conversation.py#L45-L55) and [conversation.py:140-141](core/conversation.py#L140-L141):
```python
# Assistant outputs are stored to memory
memory.append_entry(_truncate(assistant_text, 800), "voice_chat_assistant", ctx)

# Then immediately read back as "What you remember"
recent_entries = memory.get_recent_entries()
memory_summary = memory.summarize_entries(recent_entries[-10:])
```

The LLM sees its own previous responses as "memory," reinforcing whatever patterns (shallow or not) it already produced. There's no quality filtering.

**Evidence**: [memory.py:122-135](core/memory.py#L122-L135) has NO quality filtering:
```python
def summarize_entries(entries: List[Dict[str, Any]]) -> str:
    # Only deduplicates identical text, no quality check
    for item in entries:
        text = str(item.get("text", "")).strip()
        if text:
            key = text.lower()
            if key in seen:
                continue
            lines.append(f"- {text}")  # No filtering
```

**Fix Approach**:
1. Filter assistant outputs from memory summary (only include user inputs + external data)
2. Add a "progress marker" that must advance each turn
3. Separate "conversation history" (for coherence) from "factual memory" (for grounding)

**Files to Modify**: `core/memory.py`, `core/conversation.py`

---

### P0-2: Groq API Key Not Configured = Silent Failure

**Symptom**: Chat returns fallback "model unavailable" without clear error.

**Root Cause**: [providers.py:529-531](core/providers.py#L529-L531) silently skips Groq if no key:
```python
elif provider["provider"] == "groq":
    if _groq_client():  # Returns None if no key
        available.append(provider)
```

Groq is the PRIMARY provider (configured as first in PROVIDER_RANKINGS). Without it, system falls to Ollama which may not be running, causing cascade failure.

**Evidence**: No clear setup documentation for required GROQ_API_KEY.

**Fix Approach**:
1. Add clear error message when Groq key missing
2. Add `lifeos doctor` command that checks all required providers
3. Document Groq setup in README Quick Start

**Files to Modify**: `core/providers.py`, `core/cli.py`, `README.md`

---

### P0-3: Voice Pipeline Silently Fails

**Symptom**: Voice doesn't work, no error shown to user.

**Root Cause**: Multiple silent failures in [voice.py](core/voice.py):
1. Wake-word model download fails silently (line 577-580)
2. STT cascade catches all exceptions, returns empty string (line 245-291)
3. Microphone permissions not checked before use
4. No diagnostic output on voice state

**Evidence**: State only shows `mic_status: "not_initialized"` without actionable error.

**Fix Approach**:
1. Add `lifeos voice doctor` command with:
   - Microphone permission check
   - Audio device enumeration
   - Wake-word model status
   - STT engine availability test
   - TTS playback test
2. Surface errors to `voice_error` state field with actionable messages

**Files to Modify**: `core/voice.py`, `core/cli.py`

---

### P0-4: Daemon Startup Doesn't Report Failures

**Symptom**: `lifeos on --apply` says started, but things don't work.

**Root Cause**: [daemon.py:112-145](core/daemon.py#L112-L145) catches all exceptions and only logs warnings:
```python
except Exception as e:
    _log_message(log_path, f"MCP loader warning: {str(e)[:100]}")  # Silent!
```

User sees "daemon started" but MCP servers, voice, hotkeys may all have failed.

**Fix Approach**:
1. Track critical component startup success/failure
2. Add `lifeos status --verbose` that shows component health
3. Emit macOS notification on critical failures

**Files to Modify**: `core/daemon.py`, `core/cli.py`, `core/state.py`

---

### P0-5: No `.gitignore` Protection for New Sensitive Paths

**Symptom**: Risk of committing secrets.

**Root Cause**: Current `.gitignore` exists but missing some paths:
```
# Current coverage is good but missing:
# - .env.local
# - *.db (SQLite databases)
# - cookies/
# - browser-data/
# - transcripts/
```

**Evidence**: `mcp.config.json` has placeholder `OBSIDIAN_API_KEY: "SET_OBSIDIAN_API_KEY"` which is fine, but real keys could be committed.

**Fix Approach**:
1. Expand `.gitignore` with comprehensive coverage
2. Add pre-commit hook using gitleaks
3. Add CI secret scanning

**Files to Modify**: `.gitignore`, add `.pre-commit-config.yaml`

---

## P1 - High Priority Issues

### P1-1: Error Recovery Has No Retry Limit

**Root Cause**: [error_recovery.py:269-292](core/error_recovery.py#L269-L292) implements exponential backoff but NO max attempts:
```python
class RetryWithBackoffStrategy(RecoveryStrategy):
    def attempt_recovery(self, error_record: ErrorRecord) -> bool:
        attempt = int(error_record.context.get("_retry_attempts", 0)) + 1
        error_record.context["_retry_attempts"] = attempt
        # NO MAX CHECK - can retry forever!
        error_record.context["should_retry"] = True
```

**Impact**: System can hang indefinitely on persistent failures.

**Fix Approach**: Add `max_attempts=5` with circuit breaker pattern.

**Files to Modify**: `core/error_recovery.py`

---

### P1-2: Iterative Improver Creates Meta-Circular Loop

**Root Cause**: [iterative_improver.py](core/iterative_improver.py) detects "circular_improvement" as a gap, then generates an improvement proposal FOR that gap:
```python
if len(self.iterations.get("validation_failures", [])) > 5:
    gaps.append({"type": "circular_improvement", ...})

# Later:
elif gap_type == "circular_improvement":
    proposals.append(ImprovementProposal(
        title="Reduce circular improvement loops",
        ...
    ))  # This IS a circular loop!
```

**Impact**: Self-improvement becomes self-referential without progress.

**Fix Approach**:
1. Don't generate improvements for `circular_improvement` gap type
2. Add hard limit on improvement proposals per session
3. Require validation before applying any improvement

**Files to Modify**: `core/iterative_improver.py`

---

### P1-3: Circular Logic Detection Doesn't Enforce

**Root Cause**: [circular_logic.py](core/circular_logic.py) only DETECTS and SUGGESTS:
```python
def detect_circular_logic(self) -> Optional[Dict]:
    if self._detect_research_improvement_loop():
        return {
            "type": "research_improvement_loop",
            "suggestion": "Add cooldown period..."  # Just a suggestion!
        }
```

Detection is passive observation. No enforcement, no stopping.

**Fix Approach**:
1. Change from detection-only to enforcement
2. Add `CycleGovernor.enforce()` that actually blocks cycles
3. Integrate with autonomous_controller to respect limits

**Files to Modify**: `core/circular_logic.py`, `core/autonomous_controller.py`

---

### P1-4: Deep Observer Logs ALL Keystrokes (Privacy Risk)

**Root Cause**: [observer.py](core/observer.py) logs actual key content:
```python
# DeepObserver logs everything typed
# Stored in data/observer/*.json.gz
```

**Impact**: Passwords, sensitive data captured to disk. Even if gitignored, still a privacy concern.

**Fix Approach**:
1. Default `observer.mode` to `"lite"` (counts only, not content)
2. Add clear warning when enabling deep mode
3. Never store actual key values, only metadata

**Files to Modify**: `core/observer.py`, `lifeos/config/lifeos.config.json`

---

### P1-5: State Resets Each Conversation Turn

**Root Cause**: [conversation.py:135-145](core/conversation.py#L135-L145) reloads everything fresh:
```python
def generate_response(...) -> str:
    cfg = config.load_config()  # Reload
    context_text = context_loader.load_context()  # Reload
    recent_entries = memory.get_recent_entries()  # Reload
    # No "what I already tried" tracking
```

**Impact**: No learning across turns. Can't track "I already tried this action."

**Fix Approach**:
1. Add session-level state that persists across turns
2. Track "attempted actions this session" to avoid repetition
3. Implement progress checkpoints

**Files to Modify**: `core/conversation.py`, add `core/session_state.py`

---

### P1-6: Provider Fallback to Paid Without Consent

**Root Cause**: [providers.py:451](core/providers.py#L451):
```python
{"name": "gpt-4o-mini", "provider": "openai", "intelligence": 88, "free": False, "notes": "Paid fallback"},
```

If all free providers fail, OpenAI is used without user confirmation.

**Fix Approach**:
1. Add config option `providers.allow_paid_fallback: false` (default)
2. Require explicit opt-in for paid providers
3. Log/notify when paid provider is used

**Files to Modify**: `core/providers.py`, `lifeos/config/lifeos.config.json`

---

## P2 - Medium Priority Issues

### P2-1: Too Many Concurrent Background Threads

**Root Cause**: Daemon starts 8+ threads:
- VoiceManager
- HotkeyManager
- PassiveObserver
- DeepObserver (optional)
- ResourceMonitor
- ProactiveMonitor
- MissionScheduler
- InterviewScheduler
- MCP health monitor

**Impact**: Resource overhead, complexity, potential race conditions.

**Fix Approach**:
1. Consolidate into fewer event-driven loops
2. Make most components lazy-start (only when needed)
3. Add thread pool with limits

---

### P2-2: No Test Coverage

**Root Cause**: No test files exist (all `test_*.py` gitignored).

**Impact**: Can't verify fixes, can't prevent regressions.

**Fix Approach**:
1. Add basic smoke tests for CLI commands
2. Add unit tests for memory, providers, conversation
3. Add CI workflow to run tests

---

### P2-3: MCP Servers All Auto-Start

**Root Cause**: [mcp.config.json](lifeos/config/mcp.config.json) has all 11 servers with `autostart: true`.

**Impact**: Spawns 11 node/python processes on daemon start.

**Fix Approach**:
1. Default most to `autostart: false`
2. Only start on-demand when needed
3. Add connection pooling

---

### P2-4: Prompt Too Long

**Root Cause**: [conversation.py:168-208](core/conversation.py#L168-L208) assembles massive prompts:
- safety_rules
- mission_context
- personality (50+ words)
- available_actions
- conversation_history (6 turns × 400 chars)
- context_text (potentially large)
- memory_summary (10 entries)
- screen_context
- activity_summary (2 hours)
- cross_session_context
- prompt_inspirations (3)
- user_text

**Impact**: Token waste, potential context overflow, diluted signal.

**Fix Approach**:
1. Dynamic context budget based on model
2. Prioritize relevant context over comprehensive context
3. Summarize aggressively before including

---

### P2-5: Hardcoded Voice in Config Comments

**Root Cause**: Various "Samantha", "Ava" defaults scattered in code.

**Impact**: Not easily configurable.

**Fix Approach**: Centralize all voice settings in config with clear schema.

---

## Summary: Immediate P0 Fix Order

1. **P0-2**: Add Groq API key check with clear setup error → Makes chat work
2. **P0-4**: Add daemon startup failure reporting → Know what's broken
3. **P0-3**: Add voice doctor command → Debug voice issues
4. **P0-1**: Fix memory echo chamber → Stop circular conversations
5. **P0-5**: Expand .gitignore + add pre-commit → Prevent secret leaks

After P0s are fixed, system should be able to:
- Start daemon and know if it failed
- Chat via CLI with working Groq provider
- Debug voice issues systematically
- Have conversations that progress
- Safely commit without leaking secrets

---

## Verification Commands

After implementing fixes, verify with:

```bash
# P0-2: Check provider setup
lifeos doctor  # Should show Groq status

# P0-4: Daemon health
lifeos on --apply
lifeos status --verbose  # Should show component health

# P0-3: Voice diagnostics
lifeos voice doctor  # Should show mic/STT/TTS status

# P0-1: Test conversation depth
lifeos chat  # Multi-turn should show progress

# P0-5: Secret scanning
gitleaks detect --source . --verbose
```
