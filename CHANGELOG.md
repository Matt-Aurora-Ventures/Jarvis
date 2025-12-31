# Changelog

All notable changes to Jarvis (LifeOS) will be documented in this file.

---

# [0.9.1] - 2025-12-31

### 🔊 Voice + TTS
- Added barge-in support so Jarvis keeps listening while speaking and can be interrupted mid-response.
- Added self-echo suppression to stop the mic from re-feeding Jarvis's own TTS.
- Added local voice-clone engine (XTTS-v2) with optional Morgan Freeman reference support.
- Expanded Morgan Freeman voice handling with candidate selection and rate overrides.

### 🧠 Conversation Behavior
- Tightened execution bias and removed redundant follow-up prompts.
- Updated default conversation prompt guidance to avoid repeated questions.

### ⚙️ Providers + Config
- Removed deprecated Groq models and added `llama-3.3-70b-specdec` fallback.
- Updated local model ordering to match installed availability.
- Added barge-in and voice-clone settings to the main config.

### 📚 Docs
- Updated README with barge-in controls and local voice-cloning setup.

# [0.9.0] - 2025-12-30

### 🤖 Claude + GPT Hybrid Collaboration

This release represents a major milestone: **Claude Opus and GPT collaborated** to architect, implement, and refine Jarvis's trading research and autonomous capabilities. The hybrid approach combined Claude's deep reasoning with GPT's rapid iteration.

### 📊 Notion Deep Extraction System

- **New Module:** `core/notion_ingest.py` - API-based Notion page extraction with recursive block fetching
- **New Module:** `core/notion_scraper.py` - Playwright-based headless scraper for full content expansion
- **New Module:** `core/notion_tab_crawler.py` - Enhanced tab/toggle/database state-crawl for comprehensive extraction
- **New Module:** `core/notion_deep_extractor.py` - Deep recursive block fetcher using Notion's public API
- **Extracted 1,913 blocks** from Moon Dev's Algo Trading Roadmap
- **Parsed 81 trading strategies** into structured JSON catalog
- **Generated implementation plan** with architecture mapping and backtest checklist

### 📈 Trading Pipeline Enhancements

- **New Module:** `core/trading_pipeline.py` - End-to-end trading research pipeline
- **New Module:** `core/trading_youtube.py` - YouTube channel monitoring for trading content
- **New Module:** `core/trading_notion.py` - Notion-to-strategy extraction integration
- **New Module:** `core/liquidation_bot.py` - Liquidation-based trading signals (Hyperliquid/Moon Dev API)
- **New Module:** `core/solana_scanner.py` - Solana token scanner with Birdeye API integration
- **Strategy categories:** Trend following, carry trades, mean reversion, momentum, breakout, HMM regime detection

### 🧠 Agent Architecture

- **New Module:** `core/agent_graph.py` - Multi-agent graph orchestration
- **New Module:** `core/agent_router.py` - Intelligent routing between specialized agents
- **New Module:** `core/agents/` - Directory for specialized agent implementations
- **New Module:** `core/orchestrator.py` - High-level task orchestration
- **New Module:** `core/input_broker.py` - Unified input handling across voice/CLI/API
- **New Module:** `core/action_feedback.py` - Action result feedback loop

### 🔬 Self-Improvement Engine

- **New Module:** `core/self_improvement_engine.py` - Autonomous capability expansion
- **New Module:** `core/memory_driven_behavior.py` - Memory-first decision making
- **New Module:** `core/semantic_memory.py` - Semantic search over memory store
- **New Module:** `core/conversation_backtest.py` - Conversation replay for testing
- **New Module:** `core/enhanced_search_pipeline.py` - Multi-source research aggregation

### 🏥 Diagnostics & Reliability

- **New Module:** `core/mcp_doctor.py` - MCP server health diagnostics
- **New Module:** `core/mcp_doctor_simple.py` - Lightweight MCP health check
- **New Module:** `core/secret_hygiene.py` - Automated secrets scanning
- **New Module:** `core/objectives.py` - Goal tracking and progress measurement
- **New Module:** `core/vision_client.py` - Vision API integration for screen understanding
- **Added `lifeos doctor`** command for provider and MCP health checks

### 📚 Documentation

- **New:** `docs/handoff_claude_opus.md` - Handoff brief for Claude Opus collaboration
- **New:** `docs/HANDOFF_GPT5.md` - Future handoff template for GPT-5
- **New:** `docs/notion_extraction_guide.md` - Notion extraction methodology
- **Generated:** `data/notion_deep/strategy_catalog.json` - 81 strategies in structured format
- **Generated:** `data/notion_deep/implementation_plan.md` - Architecture and backtest plan
- **Generated:** `data/notion_deep/knowledge_base.md` - Master knowledge base

### 🧪 Testing Infrastructure

- **New:** `tests/test_trading_pipeline.py` - Trading pipeline tests
- **New:** `tests/test_trading_youtube.py` - YouTube ingestion tests
- **New:** `tests/test_liquidation_bot.py` - Liquidation bot tests
- **New:** `tests/test_solana_scanner.py` - Solana scanner tests
- **New:** `tests/test_conversation_backtest.py` - Conversation replay tests
- **New:** `test_*.py` - Various integration and unit tests

### 🔧 Fixes & Improvements

- Improved UI actions to accept keyword arguments (voice chat compatibility)
- Added Groq throttling and backoff to avoid rate limit storms
- Ollama fallback now gated by health check
- Readability extractor fixed for HTML decoding
- Enhanced error recovery with circuit breaker pattern

---

# [0.8.1] - 2025-12-30

### 📄 Docs
- Clarified secrets handling in the README with local-only key storage and do-not-share guidance.

# [0.8.0] - 2025-12-27

### 🧠 Behavior + Context
- Tightened conversational focus to avoid circular logic, added clearer research summaries with sources, and improved cross-session memory capture.
- Added Jarvis superintelligence context directives and prompt pack support for agency + website workflows.

### 🔊 Voice
- New Jarvis voice is live (macOS `say` fallback configured).

### 📈 Trading + Research
- Added Hyperliquid data ingestion (30-day snapshots) plus lightweight MA backtests and research notes.
- Switched trading research to DEX-first, low-fee chains (Solana/Base/BNB/Monad/Abstract), with DEX API scouting missions.
- Expanded autonomous research topics for security, network monitoring, and lightweight AI tools.

### 🛡️ Resource + Security Monitoring
- Always-on resource monitor with memory/CPU/disk alerts and periodic security scans.
- Network throughput + packet rate monitoring with logs.
- Process guard to flag heavy/abusive processes and optionally auto-terminate (opt-in).

### 🧩 Missions + MCP
- Added new idle missions: AI/security news scan, business suggestions, directive digest, and Hyperliquid backtest.
- Added YouTube transcript MCP server and a local transcript API fallback for faster ingestion.

### 🌐 Control Deck
- Rebuilt the local web UI as a control deck with system status, resource telemetry, mission triggers, research runs, and config toggles.
- Added Flask to requirements and expanded server endpoints for status, security logs, and actions.

### 🔧 Fixes
- Fixed boot self-tests for memory pipeline and added lightweight guardrails to reduce UI automation spam.
- Added DuckDuckGo Lite fallback for research search and fixed API server chat invocation.

### ✅ Testing
- Preliminary testing on this build looks good so far.

# [0.7.0] - 2025-12-26

### 🧩 MCP Autonomy Stack
- Added a dedicated MCP configuration (`lifeos/config/mcp.config.json`) declared in priority order, covering filesystem, dual memory layers, Obsidian REST, SQLite, system monitor, shell, Puppeteer, sequential thinking, and git servers.
- Mirrored the same stack inside Windsurf’s `~/.codeium/windsurf/mcp_config.json` so the editor and LifeOS share the exact capabilities and storage paths.

### ⚙️ MCP Process Loader
- Introduced `core/mcp_loader.py`, a process supervisor that reads the MCP config, launches enabled servers with per-tool log files, and shuts them down cleanly.
- Wired the loader into `core/daemon.py` so MCP services start before the Jarvis boot sequence and are automatically stopped during shutdown.

### 🧠 System Instructions
- Authored `lifeos/config/system_instructions.md`, enforcing memory-first queries, structured decomposition, git safety rules, filesystem boundaries, and tool usage guidelines for Jarvis.

### ✅ Testing
- Verified the loader by launching every autostart server (filesystem, memory, obsidian-memory, mcp-obsidian, sqlite, system-monitor, shell, puppeteer, sequential-thinking, git) and confirmed clean shutdown.

## [0.6.0] - 2025-12-25

### 🚀 Major Features

#### Local Knowledge Base & Prompt Distillation
- All notes, research dumps, and scratchpads now save to `data/notes/` as `.md/.txt/.py`.
- Each capture auto-generates a distilled summary plus prompt-library snippet for reuse.
- CLI capture, voice `log`, and automation actions share the same pipeline for consistency.

#### Targeted Idle Missions
- Background scheduler now runs when the system is idle for 10+ minutes.
- Missions include:
  - **MoonDev Watcher** – curls the official MoonDevOnYT X feed.
  - **AlgoTradeCamp Digest** – snapshots algotradecamp.com for new strategies.
  - **MoonDev YouTube Harvester** – pulls transcripts via yt-dlp and summarizes key ideas.
  - **Self-Improvement Pulse** – inspects recent provider failures & memory to queue upgrades.
- Mission output lands in context docs *and* the local notes archive.

#### Offline Piper Voice
- Bundled Piper TTS support with automatic model download to `data/voices/`.
- `_speak` now prefers the local Piper engine, falling back to macOS `say` only if needed.
- Works without an internet connection while keeping the familiar voice preferences.

### 🔧 Improvements

- Added `core/youtube_ingest.py` helper for consistent transcript extraction.
- Guardian now whitelists key repo subdirectories so Jarvis can open/save local resources safely.
- Requirements updated with `yt-dlp` and `piper-tts` to support the new pipelines.

### 🐛 Fixes

- Stopped Jarvis from launching macOS Notes; local folder access no longer trips safety checks.
- Voice logging and CLI capture now report saved file locations for easy reference.

## [0.5.0] - 2024-12-24

### 🚀 Major Features

#### Proactive Monitoring System
- **15-minute suggestion cycle** - Jarvis now watches what you're doing and offers helpful suggestions every 15 minutes
- **Context-aware recommendations** - Suggestions based on current screen, recent activity, and your goals
- **macOS notifications** - Non-intrusive alerts when Jarvis has an idea for you
- **Suggestion logging** - All suggestions saved to `data/suggestions.jsonl` for review

#### Research & Document Creation
- **`research_topic(topic, depth)`** - Automated research with quick/medium/deep modes
- **`create_document(title, request)`** - AI-generated documents saved to `data/research/`
- **`search_free_software(category)`** - Find latest open-source tools in any category

#### Computer Control (Actions System)
- **Email composition** - `compose_email()`, `send_email()` via Mail.app or mailto:
- **Browser control** - `open_browser()`, `google()` for quick searches
- **App management** - `open_app()`, `switch_app()`, `close_window()`, `minimize()`
- **Keyboard shortcuts** - `copy()`, `paste()`, `cut()`, `undo()`, `select_all()`, `save()`
- **Notes & Reminders** - `create_note()`, `set_reminder()` integration
- **Calendar** - `create_calendar_event()` with date/time support
- **iMessage** - `send_imessage()` for quick messaging
- **Spotlight** - `spotlight_search()` for system-wide search

#### Conversational AI Upgrade
- **Natural conversation style** - No more robotic responses
- **Personality and warmth** - Jarvis now speaks like a brilliant friend
- **Proactive suggestions** - Points out opportunities without being asked
- **Action execution in chat** - Use `[ACTION: command()]` syntax to control Mac

### 🔧 Improvements

#### Provider System Overhaul
- **Smart provider ranking** - Free providers prioritized, ordered by intelligence
- **Groq integration** - Ultra-fast inference with Groq API (free tier)
- **Gemini CLI support** - Direct CLI integration for Gemini
- **Fixed Gemini 404 errors** - Updated all model names to valid 2.5 versions
- **Anthropic placeholder** - Ready for Claude API key

#### Self-Evolution System
- **Auto-evolve on boot** - Automatically applies pending safe improvements
- **Continuous improvement** - Analyzes errors and proposes fixes
- **Skill auto-installation** - New skills added without manual intervention
- **Safety validation** - Guardian checks all code before execution

#### Voice Chat
- **60-second silence timeout** - Chat no longer ends prematurely (was 10s)
- **Better command parsing** - More natural voice command recognition
- **Shutdown commands** - "Jarvis shut down", "goodbye Jarvis" etc.

#### Safety & Guardian System
- **Self-preservation rules** - Cannot delete own code or critical files
- **Code validation** - All generated code checked for dangerous patterns
- **Safety prompts** - Injected into all AI interactions
- **Protected paths** - Core system files locked from modification

### 🐛 Bug Fixes
- Fixed Gemini model 404 errors (gemini-1.5-flash → gemini-2.5-flash)
- Fixed chat ending due to silence after 10 seconds
- Fixed provider fallback not trying all available options
- Fixed evolution module import errors
- Fixed Ollama timeout issues (now 180s for model loading)

### 📁 New Files
- `core/actions.py` - Computer control action registry
- `core/proactive.py` - 15-minute monitoring and research system
- `core/guardian.py` - Safety constraints and code validation
- `core/jarvis.py` - Boot sequence, user profile, mission context
- `core/observer.py` - Deep activity observation
- `core/computer.py` - AppleScript computer control
- `lifeos/context/user_profile.md` - User goals and preferences

---

## [0.4.0] - 2024-12-23

### Added
- **Intelligent provider ranking** - Automatic selection of best available AI
- **Groq provider** - Fast, free inference option
- **Gemini CLI** - Alternative Gemini access method
- **Deep observer** - Full keyboard/mouse/screen logging (optional)
- **Guardian module** - Safety constraints for AI operations
- **Jarvis boot sequence** - System discovery and initialization

### Changed
- Provider order now prioritizes free options
- Ollama timeout increased for large model loading
- Config updated for better defaults

---

## [0.3.0] - 2024-12-22

### Added
- **Self-evolution system** - AI can propose and apply improvements
- **Skill system** - Modular capabilities in `skills/` directory
- **Memory routing** - Automatic categorization of notes
- **Activity summaries** - Injected into conversations

### Changed
- Conversation prompt includes more context
- Better error handling in providers

---

## [0.2.0] - 2024-12-20

### Added
- **Voice control** - Wake word detection with openwakeword
- **Chat mode** - Continuous conversation with context
- **Hotkey activation** - Ctrl+Shift+Up for quick access
- **Check-in system** - Scheduled prompts and interviews
- **Report generation** - Morning/afternoon summaries

### Changed
- Improved TTS with multiple voice options
- Better activity tracking resolution

---

## [0.1.0] - 2024-12-15

### Added
- Initial release
- **Passive observation** - Keyboard/mouse activity tracking
- **App tracking** - Monitor which apps are used
- **Context system** - Memory buffer and storage
- **CLI interface** - Basic commands (on, off, status, log)
- **Gemini integration** - Primary AI provider
- **Ollama support** - Local LLM option

---

## Roadmap

### Planned Features
- [ ] Web search integration (real-time internet access)
- [ ] Calendar sync and smart scheduling
- [ ] Email inbox monitoring and auto-responses
- [ ] Trading research automation
- [ ] Multi-device sync
- [ ] iOS companion app
- [ ] Automated backup system
- [ ] Plugin marketplace

### In Progress
- [x] Proactive monitoring (every 15 min)
- [x] Research and document creation
- [x] Computer control via actions
- [ ] Anthropic Claude integration
- [ ] Advanced web scraping

---

## Contributing

Contributions welcome! Please read the safety guidelines in `core/guardian.py` before submitting code that modifies system behavior.

## License

MIT License - See LICENSE file for details.
