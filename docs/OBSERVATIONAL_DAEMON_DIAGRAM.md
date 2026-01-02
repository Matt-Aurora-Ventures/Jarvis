# Observational Daemon System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          JARVIS v1.0 + OBSERVATIONAL DAEMON                  │
└─────────────────────────────────────────────────────────────────────────────┘

┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃                         DATA COLLECTION LAYER                                ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

┌──────────────────────┐      ┌──────────────────────┐      ┌────────────────┐
│   DeepObserver       │      │  PassiveObserver     │      │  Screen        │
│   (core/observer.py) │      │  (core/passive.py)   │      │  Context       │
├──────────────────────┤      ├──────────────────────┤      ├────────────────┤
│ • All keystrokes     │      │ • App switches       │      │ • Frontmost app│
│ • Mouse clicks       │      │ • Activity summaries │      │ • Window title │
│ • Typed text         │      │ • Idle detection     │      │ • Visible apps │
│ • Compressed logs    │      │ • Focus sessions     │      │                │
└──────────────────────┘      └──────────────────────┘      └────────────────┘
         │                              │                            │
         │                              │                            │
         └───────────────┬──────────────┴────────────────────────────┘
                         │
                         ▼
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃                        CONTINUOUS ANALYSIS LAYER                             ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

┌─────────────────────────────────────────────────────────────────────────┐
│          Observational Daemon (core/observation_daemon.py)              │
│                     [Runs 24/7 - Analyzes every 60s]                    │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│ 1. PATTERN DETECTION                                                     │
│    ├─ Command Patterns: "git status && git pull" (5x) → alias gsp       │
│    ├─ Error Patterns: ModuleNotFoundError → auto pip install            │
│    └─ Workflow Patterns: Terminal→Browser→VSCode (10x) → workspace      │
│                                                                           │
│ 2. HYPOTHESIS GENERATION (Groq LLM - FREE)                              │
│    ├─ Prompt: Pattern + Context → Improvement suggestion                │
│    ├─ Output: JSON with confidence, impact, risk, code                  │
│    └─ Threshold check: >= 0.5 to proceed                                │
│                                                                           │
│ 3. CONFIDENCE SCORING                                                    │
│    ├─ High (0.7-1.0): Auto-execute → BackgroundImprover                 │
│    ├─ Med  (0.5-0.7): Queue → InformationSession                         │
│    └─ Low  (<0.5):    Discard → Learn for future                        │
│                                                                           │
└─────────────────────────────────────────────────────────────────────────┘
                         │
          ┌──────────────┴──────────────┐
          │                             │
          ▼                             ▼
┌───────────────────────┐   ┌───────────────────────────────────────┐
│   HIGH CONFIDENCE     │   │      MEDIUM CONFIDENCE                │
│    (>= 0.7)           │   │       (0.5 - 0.7)                     │
└───────────────────────┘   └───────────────────────────────────────┘
          │                             │
          ▼                             ▼
┏━━━━━━━━━━━━━━━━━━━━━┓   ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃   BACKGROUND         ┃   ┃   INFORMATION SESSION                ┃
┃   IMPROVER           ┃   ┃   (User Alignment)                   ┃
┗━━━━━━━━━━━━━━━━━━━━━┛   ┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

┌─────────────────────────────────────────────────────────────────────────┐
│     Background Improver (core/background_improver.py)                   │
│                     [Silent Execution - No Interruption]                │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│ 1. VALIDATE SAFETY (Guardian Integration)                               │
│    ├─ Code safety: No rm -rf, sudo, etc.                                │
│    ├─ Path whitelist: Only ~/.zshrc, ~/.config, LifeOS/                 │
│    └─ Risk threshold: Max 0.3 allowed                                   │
│                                                                           │
│ 2. CREATE ROLLBACK                                                       │
│    ├─ Snapshot original file → data/observation/rollbacks/              │
│    └─ Metadata: proposal_id, target, action (restore/delete)            │
│                                                                           │
│ 3. EXECUTE ACTION                                                        │
│    ├─ shell_alias: Append to ~/.zshrc                                   │
│    ├─ vscode_snippet: Update VS Code snippets JSON                      │
│    ├─ auto_install: pip install package                                 │
│    └─ workflow_template: Create project template file                   │
│                                                                           │
│ 4. MONITOR SUCCESS                                                       │
│    ├─ Log result → improvements.jsonl                                   │
│    ├─ IF success: Keep change                                           │
│    └─ IF failure: Auto-rollback from snapshot                           │
│                                                                           │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│     Information Session (core/information_session.py)                   │
│                  [Smart Scheduling - Non-Intrusive]                     │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│ TRIGGER CONDITIONS:                                                      │
│ ✓ Scheduled time: 9am daily (configurable)                              │
│ ✓ Opportunistic: User idle 10+ minutes                                  │
│ ✓ Cooldown: 4+ hours since last session                                 │
│                                                                           │
│ NEVER TRIGGER WHEN:                                                      │
│ ✗ Active keystrokes in last 60s                                         │
│ ✗ In Mail/Slack/Zoom/Discord/Teams/Messages                             │
│ ✗ Met cooldown period not elapsed                                       │
│                                                                           │
│ SESSION FLOW:                                                            │
│ 1. Send macOS notification: "I have 3 suggestions!"                     │
│ 2. Show dialog for each queued improvement (max 3)                      │
│ 3. User clicks [Reject] or [Approve] (30s timeout)                      │
│ 4. Execute approved improvements via BackgroundImprover                 │
│ 5. Learn from user's choices → Adjust future thresholds                 │
│                                                                           │
│ ADAPTIVE LEARNING:                                                       │
│ • If 90% approval rate for "command_alias" → Lower threshold to 0.6     │
│ • If 40% approval rate for "workflow" → Raise threshold to 0.9          │
│ • Saves to user_preferences.json                                        │
│                                                                           │
└─────────────────────────────────────────────────────────────────────────┘

┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃                          FEEDBACK & LEARNING LAYER                           ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

┌─────────────────────────────────────────────────────────────────────────┐
│                      Success Tracking & Self-Improvement                │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│ Did user use the improvement?                                            │
│ ├─ Monitor via DeepObserver: Track "gsp" alias usage                    │
│ ├─ If used 3+ times: Increase pattern confidence 0.85 → 0.9             │
│ └─ If never used: Decrease confidence for similar patterns              │
│                                                                           │
│ Self-update thresholds:                                                  │
│ ├─ After 30 days of data collection                                     │
│ ├─ If 90% success rate at 0.7 threshold → Lower to 0.65                 │
│ └─ If 50% success rate at 0.7 threshold → Raise to 0.75                 │
│                                                                           │
│ Feed to Mirror Test (nightly):                                          │
│ ├─ Patterns detected today → Validate against historical logs           │
│ ├─ Improvements executed → Score impact on productivity                 │
│ └─ Generate meta-improvements → Improve Daemon's own code               │
│                                                                           │
└─────────────────────────────────────────────────────────────────────────┘
                         │
                         ▼
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃                       NIGHTLY REFLECTION (3AM)                               ┃
┃                   Mirror Test (self_improvement_engine_v2.py)                ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
         ▲
         │
         └─ Validates Daemon's improvements against historical data
         │  Proposes refinements to Daemon's pattern detection
         └─ Creates pull request to improve observation_daemon.py itself


┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃                            DATA PERSISTENCE                                  ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

data/observation/
├── patterns.json              ← Pattern database (loaded on startup)
├── hypotheses.jsonl           ← All generated hypotheses (append-only log)
├── improvements.jsonl         ← All executed improvements (append-only log)
├── info_sessions.jsonl        ← Information session history (append-only log)
├── user_preferences.json      ← Learned user preferences (updated live)
└── rollbacks/
    ├── prop_*.json            ← Rollback metadata
    └── prop_*.backup          ← Original file snapshots


┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃                         RESOURCE FOOTPRINT                                   ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

Component                 CPU      Memory    Network       When
───────────────────────────────────────────────────────────────────────────
Observational Daemon      1.5%     40MB      1 call/60s    24/7
Background Improver       0.5%     15MB      None          On-demand
Information Session       0%       0MB       None          Triggered
───────────────────────────────────────────────────────────────────────────
TOTAL OVERHEAD:           ~2%      ~55MB     Negligible    Continuous


┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃                           SAFETY MECHANISMS                                  ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

1. Guardian Integration
   ├─ Validates all code before execution
   ├─ Blocks: rm -rf, sudo, curl | bash, eval, etc.
   └─ Whitelisted paths only

2. Confidence Thresholds
   ├─ 0.9+: Extremely safe (known error fixes)
   ├─ 0.7-0.9: High confidence → Auto-execute
   ├─ 0.5-0.7: Medium → Ask user
   └─ <0.5: Discard

3. Rollback System
   ├─ Snapshot before every change
   ├─ Auto-rollback on failure
   └─ Manual rollback: lifeos improver rollback <id>

4. File Path Whitelist
   ✓ ~/.zshrc, ~/.bashrc, ~/.bash_profile
   ✓ ~/.config/*
   ✓ LifeOS/lifeos/config/*
   ✓ LifeOS/data/*
   ✗ Everything else blocked


┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃                           KEY FEATURES                                       ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

✓ Lightweight: <2% CPU, <50MB RAM
✓ Silent: Only asks during scheduled Information Sessions
✓ Safe: Guardian validation + Rollback capability
✓ Smart: Learns from user preferences (adaptive thresholds)
✓ Continuous: Real-time pattern detection (not batch)
✓ Self-improving: Updates own detection algorithms
✓ Free: Uses Groq (FREE tier) for all LLM calls


┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃                         SUCCESS CRITERIA                                     ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

Week 1:
 [x] 5+ patterns detected
 [x] 2+ auto-executed improvements
 [x] 1 information session
 [x] 0 rollbacks needed

Month 1:
 [ ] 50+ patterns detected
 [ ] 20+ auto-executed improvements
 [ ] 90%+ success rate

Month 3:
 [ ] "I didn't even notice Jarvis set that up" - User
 [ ] 5+ hours saved per week
 [ ] Daemon self-improved 3+ times
```
