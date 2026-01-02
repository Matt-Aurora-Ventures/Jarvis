# Observational Daemon: Architecture Integration Analysis

## Current State Audit

### What Exists Today
1. **PassiveObserver** (`core/passive.py`) - Logs activity every 60s
2. **DeepObserver** (`core/observer.py`) - Full keystroke/mouse logging
3. **Mirror Test** (`core/self_improvement_engine_v2.py`) - Nightly batch at 3am
4. **Proactive Monitor** - 15-minute suggestion cycle

### Key Insight: The Gap
**Current architecture is EVENT-BASED and BATCH-ORIENTED**

- PassiveObserver logs but doesn't analyze
- DeepObserver captures but doesn't learn
- Mirror Test reflects but only nightly
- Proactive Monitor suggests but doesn't self-improve

**What's Missing:** A continuous, lightweight loop that:
1. Observes patterns in real-time
2. Hypothesizes improvements immediately
3. Tests and deploys without interruption
4. Updates itself based on results

---

## Where the Observational Daemon Fits

### Architectural Position

```
┌─────────────────────────────────────────────────────────────────┐
│                         JARVIS v1.0                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌─────────────┐       ┌──────────────────┐                     │
│  │   Mirror    │       │   Observational  │  ← NEW              │
│  │    Test     │◄──────┤     Daemon       │                     │
│  │  (3am)      │       │   (Continuous)   │                     │
│  └─────────────┘       └──────────────────┘                     │
│        ▲                        │                                │
│        │                        ▼                                │
│  ┌─────────────────────────────────────────┐                    │
│  │    Background Improver (Silent Loop)    │                    │
│  │  Observe → Hypothesize → Test → Deploy  │                    │
│  └─────────────────────────────────────────┘                    │
│        │                        │                                │
│        ▼                        ▼                                │
│  ┌──────────┐            ┌──────────┐                           │
│  │  Passive │            │   Deep   │                            │
│  │ Observer │            │ Observer │                            │
│  └──────────┘            └──────────┘                           │
│                                                                   │
│  Information Session Trigger: Only when confidence < 0.7         │
└─────────────────────────────────────────────────────────────────┘
```

### Relationship to Existing Components

**AUGMENTS (not replaces):**
- **PassiveObserver:** Provides raw activity data → Daemon analyzes patterns
- **DeepObserver:** Provides keystroke data → Daemon detects coding patterns
- **Mirror Test:** Batch reflection at night → Daemon continuous micro-improvements
- **Proactive Monitor:** Suggestions every 15min → Daemon silent execution

**KEY DIFFERENCE:**
- Mirror Test = "What did I do wrong yesterday?"
- Observational Daemon = "What pattern am I seeing RIGHT NOW that I can improve?"

---

## Design Principles

### 1. Lightweight Resource Footprint
- **CPU:** <2% continuous (uses Groq FREE tier for analysis)
- **Memory:** <50MB rolling buffer
- **Network:** Batched API calls (max 1 per minute)
- **Model:** Groq Llama 3.3 70B (FREE, ultra-fast) for pattern detection

### 2. Silent Execution Philosophy
**The "No Interruption" Contract:**
```
IF improvement confidence > 0.7:
    → Execute silently
    → Log outcome
    → Update pattern database
ELSE IF confidence 0.5-0.7:
    → Queue for next Information Session
ELSE:
    → Discard hypothesis
```

### 3. Information Session Protocol
**Triggered by:**
- Scheduled daily check-in (configurable, default 9am)
- User idle for 10+ minutes (opportunistic)
- Manual trigger via `lifeos info-session`

**Questions asked:**
- "I noticed you struggle with X - should I auto-fix this?"
- "I see pattern Y happening frequently - what's your goal here?"
- "I've silently improved Z - want to review changes?"

**NOT asked during:**
- Active coding (keystroke activity in last 60s)
- Active communication (email/Slack/messaging apps)
- Meetings (calendar integration)

### 4. The Self-Improving Loop

```
┌─────────────────────────────────────────────────────────────┐
│                   Continuous Improvement Cycle               │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  1. OBSERVE (Real-time)                                      │
│     ├─ Keyboard patterns (regex struggles, repeated edits)   │
│     ├─ App context (terminal commands, error messages)       │
│     ├─ Time patterns (when are you most productive?)         │
│     └─ Error patterns (stack traces, build failures)         │
│                                                               │
│  2. HYPOTHESIZE (LLM-powered, every 60s)                     │
│     ├─ "User repeatedly types 'git status && git pull'"      │
│     ├─ Hypothesis: Create alias 'gsp'                        │
│     ├─ Confidence: 0.85 (high - safe to auto-apply)          │
│     └─ Impact: Low risk, high convenience                    │
│                                                               │
│  3. TEST (Background sandbox)                                │
│     ├─ Create temp shell file with alias                     │
│     ├─ Validate syntax: `bash -n temp.sh`                    │
│     ├─ Check Guardian safety: guardian.is_safe()             │
│     └─ Rollback plan: Save original config                   │
│                                                               │
│  4. DEPLOY (Silent or Queued)                                │
│     ├─ IF confidence > 0.7: Execute immediately              │
│     ├─ Append to ~/.zshrc: alias gsp='git status && git pull'│
│     ├─ Log action: improvement_log.jsonl                     │
│     └─ Monitor success in next session                       │
│                                                               │
│  5. UPDATE SELF (Meta-learning)                              │
│     ├─ Did user use the new alias? (track via DeepObserver)  │
│     ├─ IF used 3+ times: Increase pattern confidence         │
│     ├─ IF never used: Lower confidence for similar patterns  │
│     ├─ Update observation_daemon.py thresholds               │
│     └─ Feed learnings to Mirror Test for nightly refinement  │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

---

## Pattern Categories

### High-Confidence Patterns (Auto-Execute)

**1. Command Aliases (0.8-0.9 confidence)**
```
Observed: "docker ps && docker logs app_1" (5x in 30min)
Hypothesis: alias dlog='docker ps && docker logs'
Action: Add to ~/.zshrc
Validation: Track usage via DeepObserver
```

**2. Code Snippets (0.75-0.85 confidence)**
```
Observed: User types same try/except block 3x
Hypothesis: Create VSCode snippet or utils function
Action: Inject into workspace settings
Validation: Monitor file edits
```

**3. Error Resolution (0.8-0.95 confidence)**
```
Observed: "ModuleNotFoundError: No module named 'requests'"
Seen: User runs `pip install requests` after
Hypothesis: Auto-install on import error detection
Action: Add to auto-fix rules
Validation: Check if error recurs
```

### Medium-Confidence Patterns (Queue for Info Session)

**4. Workflow Optimization (0.5-0.7 confidence)**
```
Observed: User switches Terminal → Browser → VS Code 10x/hour
Hypothesis: Create multi-pane workspace layout
Action: ASK during Information Session
Validation: User decides
```

**5. Project Structure (0.5-0.7 confidence)**
```
Observed: User creates similar directory structure 3x
Hypothesis: Create project template generator
Action: ASK for confirmation
Validation: Track usage
```

### Low-Confidence Patterns (Discard or Learn)

**6. Ambiguous Behaviors (< 0.5 confidence)**
```
Observed: User deletes code, rewrites differently
Hypothesis: Unclear - learning preference? debugging?
Action: LOG for future pattern matching
Validation: Wait for more data
```

---

## Resource Footprint Comparison

| Component | CPU | Memory | Network | When |
|-----------|-----|--------|---------|------|
| **Passive Observer** | 0.5% | 20MB | None | 24/7 |
| **Deep Observer** | 1% | 30MB | None | 24/7 |
| **Mirror Test** | 15% | 200MB | Heavy | 3am only |
| **Observational Daemon** | 1.5% | 40MB | Light | 24/7 |
| **Background Improver** | 0.5% | 15MB | Batched | On-demand |

**Total overhead: <5% CPU, <100MB RAM**

---

## Safety Mechanisms

### Guardian Integration
```python
class BackgroundImprover:
    def validate_improvement(self, proposal):
        # 1. Guardian safety check
        if not guardian.is_safe(proposal.code):
            return False
        
        # 2. File path whitelist
        if not self._is_safe_path(proposal.target_file):
            return False
        
        # 3. Rollback capability
        if not self._can_rollback(proposal):
            return False
        
        # 4. Impact assessment
        if proposal.risk_level > 0.3:
            return False  # Too risky
        
        return True
```

### Confidence Calibration
```
Initial confidence thresholds:
- Auto-execute: >= 0.7
- Queue for review: 0.5 - 0.7
- Discard: < 0.5

After 30 days of learning:
- Thresholds auto-adjust based on success rate
- If 90% of 0.7 confidence improves work: lower to 0.65
- If 50% of 0.7 confidence unused: raise to 0.75
```

---

## Data Flow

```
DeepObserver (keystrokes) ─┐
                           ├──> Observational Daemon
PassiveObserver (apps)  ───┤         │
                           │         ▼
Screen Context ────────────┘    Pattern Detector
                                     │
                                     ▼
                               Hypothesis Generator
                                  (Groq LLM)
                                     │
                                     ▼
                               Confidence Scorer
                                     │
                      ┌──────────────┴──────────────┐
                      │                             │
                 confidence                    confidence
                   >= 0.7                      < 0.7
                      │                             │
                      ▼                             ▼
              Background Improver          Information Session Queue
                      │                             │
                      ▼                             ▼
              Guardian Validation              User Input Required
                      │                             │
                      ▼                             ▼
                 Auto-Deploy                   Manual Approval
                      │                             │
                      └─────────────┬───────────────┘
                                    ▼
                             Improvement Log
                                    │
                                    ▼
                              Mirror Test
                          (Nightly validation)
```

---

## Next Steps: Implementation

See the companion files:
1. `core/observation_daemon.py` - Main observational loop
2. `core/background_improver.py` - Silent improvement executor
3. `core/information_session.py` - User alignment protocol

---

**Design Philosophy:**
> "The best assistant is one you never notice, until you realize how much easier your work has become."

**Key Metric:**
> Weeks until user thinks: "Wait, I didn't set that up... when did Jarvis add this?"
