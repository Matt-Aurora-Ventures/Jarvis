# Jarvis/LifeOS Architecture

## Overview

Jarvis is a macOS autonomous AI assistant with voice control, computer automation, and self-improvement capabilities. This document maps the complete system architecture.

---

## Component Map

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           USER INTERFACE LAYER                               │
├──────────────────┬──────────────────┬──────────────────┬────────────────────┤
│   CLI Entry      │   Voice Input    │   Hotkey        │   Web Dashboard    │
│   bin/lifeos     │   core/voice.py  │   core/hotkeys  │   web/task_web.py  │
│   core/cli.py    │   (wake word)    │   (Ctrl+Shift+Up)│   (Flask)          │
└────────┬─────────┴────────┬─────────┴────────┬─────────┴────────┬───────────┘
         │                  │                  │                  │
         ▼                  ▼                  ▼                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          DAEMON / ORCHESTRATION                              │
│                              core/daemon.py                                  │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │ Manages: VoiceManager, HotkeyManager, PassiveObserver, DeepObserver,  │ │
│  │          MissionScheduler, InterviewScheduler, ResourceMonitor,        │ │
│  │          ProactiveMonitor, MCPManager                                  │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────┬───────────────────────────────────┘
                                          │
                                          ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         REASONING / CONVERSATION                             │
├───────────────────────────────────────────────────────────────────────────────
│                                                                             │
│  ┌─────────────────┐    ┌──────────────────┐    ┌────────────────────────┐ │
│  │ Input Processing│───▶│ Context Assembly │───▶│ LLM Provider Chain     │ │
│  │                 │    │                  │    │                        │ │
│  │ conversation.py │    │ - context_loader │    │ providers.py           │ │
│  │ - truncate      │    │ - memory.py      │    │ - Groq (primary)       │ │
│  │ - recent_chat() │    │ - context_manager│    │ - Ollama (local)       │ │
│  │ - is_research() │    │ - passive.py     │    │ - Gemini (disabled)    │ │
│  └─────────────────┘    │ - prompt_library │    │ - OpenAI (paid fallback│ │
│                         └──────────────────┘    └────────────────────────┘ │
│                                                           │                │
│                                                           ▼                │
│                                           ┌──────────────────────────────┐ │
│                                           │ Response + Action Execution  │ │
│                                           │ - Parse [ACTION: ...]        │ │
│                                           │ - Execute via actions.py     │ │
│                                           │ - Record to memory           │ │
│                                           └──────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
                                          │
                                          ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                            MEMORY & STATE LAYER                              │
├───────────────────────────────────────────────────────────────────────────────
│  ┌─────────────────────┐  ┌─────────────────────┐  ┌─────────────────────┐ │
│  │ Recent Memory       │  │ Context Manager     │  │ State Store         │ │
│  │ (JSONL)             │  │ (JSON)              │  │                     │ │
│  │                     │  │                     │  │ state.py            │ │
│  │ memory/recent.jsonl │  │ master_context.json │  │ logs/state.json     │ │
│  │ memory/pending.jsonl│  │ activity_context    │  │ PID tracking        │ │
│  │                     │  │ conversation_context│  │ Voice/hotkey state  │ │
│  │ Cap: 50-300 entries │  │                     │  │                     │ │
│  └─────────────────────┘  └─────────────────────┘  └─────────────────────┘ │
│                                                                             │
│  ┌─────────────────────┐  ┌─────────────────────┐                          │
│  │ Context Documents   │  │ Secrets             │                          │
│  │ (Markdown)          │  │                     │                          │
│  │                     │  │ secrets/keys.json   │                          │
│  │ context/goals.md    │  │ - google_api_key    │                          │
│  │ context/principles  │  │ - openai_api_key    │                          │
│  │ context/projects/   │  │ - groq_api_key      │                          │
│  └─────────────────────┘  └─────────────────────┘                          │
└─────────────────────────────────────────────────────────────────────────────┘
                                          │
                                          ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           ACTIONS & INTEGRATIONS                             │
├───────────────────────────────────────────────────────────────────────────────
│  ┌─────────────────────┐  ┌─────────────────────┐  ┌─────────────────────┐ │
│  │ Computer Control    │  │ External APIs       │  │ MCP Servers         │ │
│  │                     │  │                     │  │                     │ │
│  │ actions.py          │  │ integrations/       │  │ mcp_loader.py       │ │
│  │ computer.py         │  │ - gmail             │  │ - filesystem        │ │
│  │ window_interaction  │  │ - google_calendar   │  │ - memory            │ │
│  │ browser_automation  │  │ - github            │  │ - shell (sandboxed) │ │
│  │                     │  │ - linkedin          │  │ - puppeteer         │ │
│  │ - open_mail         │  │ - trello            │  │ - sqlite            │ │
│  │ - compose_email     │  │ - x (twitter)       │  │ - git               │ │
│  │ - google_search     │  │                     │  │ - youtube-transcript│ │
│  │ - open_browser      │  │                     │  │ - sequential-think  │ │
│  │ - create_note       │  │                     │  │                     │ │
│  └─────────────────────┘  └─────────────────────┘  └─────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
                                          │
                                          ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         AUTONOMOUS / BACKGROUND SYSTEMS                      │
├───────────────────────────────────────────────────────────────────────────────
│  ┌─────────────────────┐  ┌─────────────────────┐  ┌─────────────────────┐ │
│  │ Observation         │  │ Autonomous Agents   │  │ Self-Improvement    │ │
│  │                     │  │                     │  │                     │ │
│  │ observer.py (deep)  │  │ autonomous_agent.py │  │ evolution.py        │ │
│  │ - ALL key/mouse     │  │ agent_graph.py      │  │ self_healing.py     │ │
│  │ passive.py (lite)   │  │ agent_router.py     │  │ self_evaluator.py   │ │
│  │ - app switches      │  │ autonomous_ctrl.py  │  │ iterative_improver  │ │
│  │ - idle detection    │  │ autonomous_learner  │  │ ability_acquisition │ │
│  │                     │  │                     │  │ error_recovery.py   │ │
│  └─────────────────────┘  └─────────────────────┘  └─────────────────────┘ │
│                                                                             │
│  ┌─────────────────────┐  ┌─────────────────────┐  ┌─────────────────────┐ │
│  │ Missions            │  │ Proactive           │  │ Monitoring          │ │
│  │                     │  │                     │  │                     │ │
│  │ missions.py         │  │ proactive.py        │  │ resource_monitor.py │ │
│  │ - idle research     │  │ - 15-min suggestions│  │ - CPU/RAM/disk      │ │
│  │ - crypto analysis   │  │ - macOS notifications│ │ - process guard     │ │
│  │ - web crawling      │  │                     │  │ - security scans    │ │
│  │                     │  │ interview.py        │  │                     │ │
│  │                     │  │ - periodic check-ins│  │ circular_logic.py   │ │
│  └─────────────────────┘  └─────────────────────┘  └─────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Request-to-Action Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ 1. INPUT CAPTURE                                                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  User speaks "Hey Jarvis"  ──▶  OpenWakeWord detects  ──▶  VoiceManager    │
│        OR                                                                   │
│  User presses Ctrl+Shift+Up ──▶  HotkeyManager  ──▶  start_chat_session()  │
│        OR                                                                   │
│  User runs `lifeos chat`   ──▶  cli.cmd_chat()  ──▶  voice.chat_session()  │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ Audio Capture: PyAudio → 16kHz mono → SpeechRecognition.listen()   │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 2. SPEECH-TO-TEXT                                                           │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  voice._transcribe_once() tries in order:                                  │
│    1. Gemini (if API key) ── audio upload + transcribe                     │
│    2. OpenAI Whisper (if API key) ── whisper-1 model                       │
│    3. Google Speech (free) ── recognize_google()                           │
│    4. PocketSphinx (offline) ── recognize_sphinx()                         │
│                                                                             │
│  Returns: "open my email and check for messages from John"                 │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 3. COMMAND PARSING                                                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  voice.parse_command(text) checks for built-in commands:                   │
│    - "stop listening" → listening_off                                      │
│    - "status" → status                                                     │
│    - "shutdown" → shutdown                                                 │
│    - etc.                                                                  │
│                                                                             │
│  If NO match → send to conversation engine                                 │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 4. CONTEXT ASSEMBLY                                                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  conversation.generate_response() builds prompt:                           │
│                                                                             │
│  ┌───────────────────────────────────────────────────────────────────────┐ │
│  │ safety_rules (guardian.py) ─────────────────────────────────────────▶ │ │
│  │ mission_context (jarvis.py) ────────────────────────────────────────▶ │ │
│  │ personality_prompt (hardcoded) ─────────────────────────────────────▶ │ │
│  │ available_actions (actions.py) ─────────────────────────────────────▶ │ │
│  │ conversation_history (memory recent.jsonl, last 6 turns) ───────────▶ │ │
│  │ context_text (context_loader → context/*.md) ───────────────────────▶ │ │
│  │ memory_summary (memory.summarize_entries, last 10) ─────────────────▶ │ │  ◀── PROBLEM: Includes
│  │ screen_context (observation.py) ────────────────────────────────────▶ │ │      assistant outputs!
│  │ activity_summary (passive.py, 2 hours) ─────────────────────────────▶ │ │
│  │ cross_session_context (context_manager.py) ─────────────────────────▶ │ │
│  │ prompt_inspirations (prompt_library.py, up to 3) ───────────────────▶ │ │
│  │ user_text ──────────────────────────────────────────────────────────▶ │ │
│  └───────────────────────────────────────────────────────────────────────┘ │
│                                                                             │
│  Total prompt can be 2000-5000 tokens depending on context                 │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 5. LLM GENERATION                                                           │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  providers.generate_text(prompt, max_output_tokens=500)                    │
│                                                                             │
│  Provider chain (get_ranked_providers):                                    │
│    1. Groq llama-3.3-70b-versatile (PRIMARY, free, ultra-fast)            │
│    2. Groq mixtral-8x7b-32768 (free, fast)                                │
│    3. Ollama qwen2.5:7b (local, private)                                  │
│    4. Ollama llama3.1:8b (local)                                          │
│    5. OpenAI gpt-4o-mini (paid fallback) ◀── only if all free fail       │
│                                                                             │
│  Note: Gemini is DISABLED in code (line 527: "if False and ...")          │
│                                                                             │
│  Returns: "Sure! Let me open your email app. [ACTION: open_mail()]"       │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 6. ACTION EXECUTION                                                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  conversation._execute_actions_in_response(response)                       │
│                                                                             │
│  Regex: \[ACTION:\s*(\w+)\(([^)]*)\)\]                                     │
│  Example: [ACTION: open_mail()]                                            │
│                                                                             │
│  actions.execute_action("open_mail", **{})                                 │
│    └── ACTION_REGISTRY["open_mail"] → open_mail_app()                      │
│        └── osascript: tell application "Mail" to activate                  │
│                                                                             │
│  Appends result: "[open_mail: ✓ Opened Mail app]"                          │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 7. MEMORY PERSISTENCE                                                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  conversation._record_conversation_turn(user_text, assistant_text)         │
│                                                                             │
│  Writes to:                                                                │
│    - memory/recent.jsonl ── both user AND assistant messages              │
│    - context_manager ── conversation_context.json                          │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ CIRCULAR RISK: Next turn reads memory_summary which includes this   │   │
│  │ assistant output → LLM sees its own words as "memory"               │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 8. TTS OUTPUT                                                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  voice._speak(response_text)                                               │
│                                                                             │
│  TTS cascade:                                                              │
│    1. Piper TTS (local ONNX) ── en_US-lessac-medium.onnx                  │
│    2. macOS `say` ── with voice Samantha (or fallbacks: Ava, Allison...)  │
│                                                                             │
│  Playback: afplay (macOS native)                                           │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Background Loops & Timers

| Component | File:Line | Interval | Trigger | Purpose |
|-----------|-----------|----------|---------|---------|
| **Main Daemon Loop** | daemon.py:174-205 | 5 seconds | `lifeos on --apply` | Orchestrates scheduled reports, interview check-ins |
| **VoiceManager** | voice.py:645-683 | 80ms (audio frames) | Daemon start | Wake-word detection + voice capture |
| **HotkeyManager** | hotkeys.py:29-87 | 250ms polling | Daemon start | Ctrl+Shift+Up detection |
| **PassiveObserver** | passive.py:394-475 | 1 second checks | Daemon start | App switches, idle detection, activity logs |
| **DeepObserver** | observer.py:253-295 | 30 second flush | Daemon start (if enabled) | ALL keyboard/mouse logging (privacy concern!) |
| **ResourceMonitor** | resource_monitor.py:305-335 | 20 seconds | Daemon start | CPU/RAM/disk monitoring, alerts |
| **MissionScheduler** | missions.py:1049-1060 | 120 seconds | Daemon start | Idle-time research, crypto analysis |
| **ProactiveMonitor** | proactive.py:41-47 | 15 minutes | Daemon start | Suggestions via macOS notifications |
| **InterviewScheduler** | interview.py:227-240 | 120 minutes | Daemon loop | Periodic user check-ins |
| **AutonomousController** | autonomous_controller.py:135-217 | 10 seconds base | Proactive monitor | 12 autonomous research/improvement cycles |
| **MCP Health Monitor** | mcp_loader.py:257-271 | 30/60 seconds | MCP server start | Auto-restart unhealthy MCP servers |

---

## State Files

| File | Format | Contents | Location |
|------|--------|----------|----------|
| `state.json` | JSON | Runtime state: PID, voice/hotkey status, last report | `lifeos/logs/state.json` |
| `recent.jsonl` | JSONL | Recent memory entries (cap: 50-300) | `lifeos/memory/recent.jsonl` |
| `pending.jsonl` | JSONL | Overflow memory awaiting routing | `lifeos/memory/pending.jsonl` |
| `lifeos.config.json` | JSON | Main configuration | `lifeos/config/lifeos.config.json` |
| `lifeos.config.local.json` | JSON | Local overrides (gitignored) | `lifeos/config/lifeos.config.local.json` |
| `keys.json` | JSON | API keys (gitignored) | `secrets/keys.json` |
| `mcp.config.json` | JSON | MCP server definitions | `lifeos/config/mcp.config.json` |
| Activity logs | JSONL | Per-hour activity snapshots | `data/activity_logs/*.jsonl` |
| Observer logs | JSONL.gz | Compressed key/mouse logs | `data/observer/*.json.gz` |

---

## Configuration Hierarchy

```
lifeos.config.json (base)
       │
       ▼
lifeos.config.local.json (overrides, gitignored)
       │
       ▼
Environment variables (GROQ_API_KEY, etc.)
       │
       ▼
secrets/keys.json (API keys)
```

---

## Critical Data Paths

```
User Input
    │
    ▼
┌─────────────────────────────────────────────┐
│           SHARED MEMORY                     │
│                                             │
│  recent.jsonl ←── ALL conversation turns   │
│       │                                     │
│       └──▶ Feeds back into next prompt     │
│            as "What you remember"           │
│                                             │
│  ⚠️ CIRCULAR: Assistant outputs included!  │
└─────────────────────────────────────────────┘
```

---

## Key Module Responsibilities

### Core Conversation
- `conversation.py` - Main response generation, prompt assembly
- `providers.py` - LLM provider abstraction, ranking, fallback chain
- `memory.py` - JSONL memory store, adaptive caps
- `context_loader.py` - Load markdown context documents
- `context_manager.py` - Cross-session context persistence

### Voice Pipeline
- `voice.py` - VoiceManager, STT/TTS, wake-word, chat sessions
- `hotkeys.py` - Global hotkey capture via pynput

### Actions & Control
- `actions.py` - Action registry and execution
- `computer.py` - Mac control via osascript/AppleScript
- `window_interaction.py` - Window manipulation

### Autonomous Systems
- `autonomous_agent.py` - Multi-step agent with tool use
- `autonomous_controller.py` - Orchestrates multiple autonomous cycles
- `iterative_improver.py` - Self-improvement cycle runner
- `error_recovery.py` - Retry strategies, self-healing
- `circular_logic.py` - Circular pattern detection (observation only)

### Observation
- `observer.py` - Deep activity logging (ALL keystrokes)
- `passive.py` - Lightweight activity tracking (counts only)
- `observation.py` - Screen context (frontmost app, visible apps)

### Infrastructure
- `daemon.py` - Main daemon process, thread orchestration
- `mcp_loader.py` - MCP server lifecycle management
- `state.py` - Runtime state persistence
- `config.py` - Configuration loading with deep merge
- `secrets.py` - API key management

---

## Version

Generated: 2024-12-30
Codebase: ~27,000 lines Python across 79 core modules
