# Jarvis/LifeOS - PR Plan

## Overview

This document outlines small, mergeable PRs to fix the critical issues and make Jarvis work reliably. PRs are ordered by dependency - earlier PRs must land before later ones.

---

## Phase 1: Foundation (Get Basic Chat Working)

### PR-1: Provider Health & Doctor Command
**Scope**: Add diagnostic tooling to understand why chat fails

**Files**:
- `core/cli.py` - Add `lifeos doctor` command
- `core/providers.py` - Add `check_provider_health()` function
- `core/secrets.py` - Add `list_configured_keys()` helper

**Changes**:
```python
# cli.py - new command
def cmd_doctor(args):
    """Check system health and provider availability."""
    # Check Groq key
    # Check Ollama running
    # Check OpenAI key (optional)
    # Check microphone permissions
    # Check required dependencies
```

**Tests**:
- [ ] `lifeos doctor` runs without error
- [ ] Shows clear message if Groq key missing
- [ ] Shows Ollama connection status

**Acceptance Criteria**:
- User can run `lifeos doctor` and understand what's broken
- Clear instructions on how to fix each issue

---

### PR-2: Clear Provider Error Messages
**Scope**: Surface why LLM calls fail instead of silent fallback

**Files**:
- `core/providers.py` - Add error messages, logging
- `core/conversation.py` - Show provider status in fallback

**Changes**:
```python
# providers.py
def generate_text(...) -> Optional[str]:
    if not ranked:
        _log("ERROR: No providers available. Run 'lifeos doctor' for setup help.")
        return None
    # Add clear logging for each provider attempt
```

**Tests**:
- [ ] Missing Groq key shows: "Groq API key not set. Run: export GROQ_API_KEY=..."
- [ ] Ollama not running shows: "Ollama not reachable at localhost:11434"
- [ ] All providers exhausted shows actionable error

**Acceptance Criteria**:
- Every provider failure has a clear, actionable error message
- User knows exactly what to fix

---

### PR-3: Memory Echo Chamber Fix
**Scope**: Stop assistant outputs from feeding back as "memory"

**Files**:
- `core/memory.py` - Add source filtering
- `core/conversation.py` - Separate conversation history from factual memory

**Changes**:
```python
# memory.py - new function
def get_factual_entries() -> List[Dict[str, Any]]:
    """Get memory entries excluding assistant responses."""
    entries = _read_jsonl(RECENT_PATH)
    return [e for e in entries if e.get("source") not in ("voice_chat_assistant",)]

# conversation.py
memory_summary = memory.summarize_entries(memory.get_factual_entries()[-10:])
```

**Tests**:
- [ ] `get_factual_entries()` excludes assistant outputs
- [ ] Memory summary in prompt only contains user inputs + external data
- [ ] Conversation history still includes both sides (for coherence)

**Acceptance Criteria**:
- LLM no longer sees its own outputs as "What you remember"
- Conversation history preserved for coherence
- Factual grounding separate from chat history

---

### PR-4: Progress Contract for Conversations
**Scope**: Each turn must advance or explicitly block

**Files**:
- `core/conversation.py` - Add progress tracking
- `core/session_state.py` (new) - Session-level state

**Changes**:
```python
# session_state.py (new file)
@dataclass
class SessionState:
    turn_count: int = 0
    attempted_actions: List[str] = field(default_factory=list)
    last_goal: str = ""
    progress_markers: List[str] = field(default_factory=list)

# conversation.py - add to prompt
"PROGRESS CONTRACT: You must either:
1. Take an action toward the goal
2. Ask ONE clarifying question
3. Declare the goal complete/blocked with reason
Do not repeat yourself or give generic responses."
```

**Tests**:
- [ ] Repeated identical responses detected and flagged
- [ ] Actions tracked per session
- [ ] Turn count limits enforced

**Acceptance Criteria**:
- Conversations show visible progress
- Circular patterns break automatically

---

## Phase 2: Voice Reliability

### PR-5: Voice Doctor Command
**Scope**: Systematic voice pipeline diagnostics

**Files**:
- `core/cli.py` - Add `lifeos voice doctor` command
- `core/voice.py` - Add diagnostic functions

**Changes**:
```python
# cli.py
def cmd_voice_doctor(args):
    """Diagnose voice pipeline issues."""
    # 1. Check microphone permissions
    # 2. List audio devices
    # 3. Test wake-word model loaded
    # 4. Test STT engine (Google/Groq/Whisper)
    # 5. Test TTS playback
    # 6. Show current voice_error state
```

**Tests**:
- [ ] `lifeos voice doctor` completes without crash
- [ ] Microphone permission status shown
- [ ] STT test transcribes "hello world" correctly
- [ ] TTS test plays audio

**Acceptance Criteria**:
- User can diagnose any voice issue with one command
- Each step shows pass/fail with fix instructions

---

### PR-6: Voice Error Surfacing
**Scope**: Make voice failures visible and actionable

**Files**:
- `core/voice.py` - Improve error handling
- `core/state.py` - Add voice_error_detail field

**Changes**:
```python
# voice.py - explicit error states
VOICE_ERRORS = {
    "mic_permission_denied": "Microphone access denied. Go to System Preferences > Security & Privacy > Microphone",
    "wake_word_model_missing": "Wake word model not found. Run: pip install openwakeword",
    "stt_all_failed": "All speech-to-text engines failed. Check internet or install pocketsphinx",
    "tts_piper_missing": "Piper TTS not installed. Run: pip install piper-tts",
}
```

**Tests**:
- [ ] Each error state has actionable message
- [ ] Errors shown in `lifeos status`
- [ ] Voice continues working with degraded mode when possible

**Acceptance Criteria**:
- No silent voice failures
- User always knows what broke and how to fix it

---

## Phase 3: Error Recovery & Stability

### PR-7: Retry Circuit Breaker
**Scope**: Add max retries to prevent infinite loops

**Files**:
- `core/error_recovery.py` - Add max_attempts

**Changes**:
```python
class RetryWithBackoffStrategy(RecoveryStrategy):
    max_attempts: int = 5  # NEW

    def attempt_recovery(self, error_record: ErrorRecord) -> bool:
        attempt = int(error_record.context.get("_retry_attempts", 0)) + 1
        if attempt > self.max_attempts:
            return False  # Stop retrying
        # ... rest of logic
```

**Tests**:
- [ ] After 5 failed attempts, stops retrying
- [ ] Exponential backoff still works
- [ ] Circuit breaker resets after success

**Acceptance Criteria**:
- System never hangs on persistent failures
- Graceful degradation after max retries

---

### PR-8: Daemon Health Reporting
**Scope**: Know when daemon components fail

**Files**:
- `core/daemon.py` - Track component health
- `core/state.py` - Add component_health field
- `core/cli.py` - Add `lifeos status --verbose`

**Changes**:
```python
# daemon.py
component_health = {
    "voice": "ok" | "failed: reason",
    "hotkeys": "ok" | "failed: reason",
    "mcp": "ok" | "partial: 3/11 servers" | "failed: reason",
    # etc
}
state.update_state(component_health=component_health)
```

**Tests**:
- [ ] `lifeos status --verbose` shows all component states
- [ ] Failed components show reason
- [ ] macOS notification on critical failure

**Acceptance Criteria**:
- User knows if daemon started successfully
- Failed components clearly identified

---

## Phase 4: Self-Improvement Safety

### PR-9: Disable Meta-Circular Improvement
**Scope**: Iterative improver shouldn't improve itself circularly

**Files**:
- `core/iterative_improver.py` - Block circular patterns

**Changes**:
```python
def generate_improvement_plan(self, gaps: List[Dict]) -> List[ImprovementProposal]:
    proposals = []
    for gap in gaps:
        gap_type = gap.get("type", "")

        # Skip meta-circular improvements
        if gap_type in ("circular_improvement", "meta_circular"):
            continue

        # ... generate proposals for other gaps
```

**Tests**:
- [ ] `circular_improvement` gap doesn't generate proposal
- [ ] Other gap types still work
- [ ] Hard limit on proposals per session

**Acceptance Criteria**:
- Self-improvement doesn't create infinite loops
- Manual review required for self-modification

---

### PR-10: Circular Logic Enforcement
**Scope**: Make circular detection actually stop cycles

**Files**:
- `core/circular_logic.py` - Add enforcement
- `core/autonomous_controller.py` - Respect circular limits

**Changes**:
```python
# circular_logic.py
class CycleGovernor:
    def enforce(self, cycle_type: str) -> bool:
        """Returns True if cycle should be blocked."""
        detection = self.detector.detect_circular_logic()
        if detection and detection["type"] == cycle_type:
            self._record_block(cycle_type)
            return True  # BLOCK
        return False
```

**Tests**:
- [ ] Circular detection triggers block
- [ ] Blocked cycles logged
- [ ] Cooldown before retry allowed

**Acceptance Criteria**:
- Detected circular patterns are stopped, not just observed
- System recovers gracefully after blocking

---

## Phase 5: Testing & CI

### PR-11: Basic Smoke Tests
**Scope**: Ensure core functionality works

**Files**:
- `tests/test_smoke.py` (new)
- `tests/test_providers.py` (new)
- `tests/test_memory.py` (new)
- `pytest.ini` (new)

**Changes**:
```python
# tests/test_smoke.py
def test_config_loads():
    cfg = config.load_config()
    assert "voice" in cfg

def test_status_command():
    # Run lifeos status and check output

def test_memory_round_trip():
    # Write entry, read it back
```

**Tests**:
- [ ] All tests pass on clean install
- [ ] Tests run in < 30 seconds
- [ ] No external dependencies required

**Acceptance Criteria**:
- Basic confidence that system works
- Can run `pytest` to verify

---

### PR-12: CI Workflow with Secret Scanning
**Scope**: Automated checks on every push

**Files**:
- `.github/workflows/ci.yml` (new)
- `.pre-commit-config.yaml` (new)

**Changes**:
```yaml
# .github/workflows/ci.yml
name: CI
on: [push, pull_request]
jobs:
  test:
    runs-on: macos-latest
    steps:
      - uses: actions/checkout@v4
      - name: Set up Python
        uses: actions/setup-python@v5
      - name: Install dependencies
        run: pip install -r requirements.txt
      - name: Run tests
        run: pytest
      - name: Secret scan
        uses: gitleaks/gitleaks-action@v2
```

**Tests**:
- [ ] CI passes on clean push
- [ ] Gitleaks catches test secrets
- [ ] Pre-commit hooks work locally

**Acceptance Criteria**:
- Every PR is tested
- Secrets can't be committed accidentally

---

## Summary: PR Landing Order

```
PR-1: Provider Health & Doctor  ──┐
PR-2: Clear Provider Errors     ──┼── Basic Chat Works
PR-3: Memory Echo Chamber Fix   ──┤
PR-4: Progress Contract         ──┘

PR-5: Voice Doctor Command      ──┐
PR-6: Voice Error Surfacing     ──┴── Voice Reliable

PR-7: Retry Circuit Breaker     ──┐
PR-8: Daemon Health Reporting   ──┴── System Stability

PR-9: Disable Meta-Circular     ──┐
PR-10: Circular Logic Enforce   ──┴── Safe Self-Improvement

PR-11: Basic Smoke Tests        ──┐
PR-12: CI Workflow              ──┴── Quality Gates
```

---

## Estimated Effort

| PR | Complexity | Files | Est. Hours |
|----|------------|-------|------------|
| PR-1 | Low | 3 | 2-3 |
| PR-2 | Low | 2 | 1-2 |
| PR-3 | Medium | 2 | 3-4 |
| PR-4 | Medium | 2 (1 new) | 4-5 |
| PR-5 | Medium | 2 | 3-4 |
| PR-6 | Low | 2 | 2-3 |
| PR-7 | Low | 1 | 1-2 |
| PR-8 | Medium | 3 | 3-4 |
| PR-9 | Low | 1 | 1-2 |
| PR-10 | Medium | 2 | 2-3 |
| PR-11 | Medium | 4 (new) | 4-5 |
| PR-12 | Low | 2 (new) | 2-3 |

**Total: ~30-40 hours of implementation**

First 4 PRs (basic chat working): ~10-14 hours
