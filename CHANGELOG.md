# Changelog

All notable changes to Jarvis (LifeOS) will be documented in this file.

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
