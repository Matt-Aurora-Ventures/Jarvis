#!/usr/bin/env python3
"""
JARVIS Unified Daemon - Always-On Desktop Assistant

Unified entry point that starts all JARVIS components:
- System tray UI
- Web research agent
- Proactive suggestion engine
- Cross-system state sync
- LLM services

Usage:
    python jarvis_daemon.py                    # Start all services
    python jarvis_daemon.py --no-tray          # Headless mode
    python jarvis_daemon.py --components tray,research  # Specific components

Dependencies:
    pip install pystray pillow aiohttp
"""

import argparse
import asyncio
import logging
import os
import signal
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add project root to path
ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

# Configure logging
LOG_DIR = ROOT / "logs"
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / f"jarvis_{datetime.now().strftime('%Y%m%d')}.log"),
        logging.StreamHandler(),
    ]
)
logger = logging.getLogger("jarvis.daemon")


class JarvisDaemon:
    """
    Main JARVIS daemon orchestrator.

    Coordinates all subsystems:
    - System tray for desktop presence
    - Web research for autonomous learning
    - Proactive suggestions for anticipatory help
    - State sync for cross-component communication
    - LLM services for AI capabilities
    """

    def __init__(self, components: Optional[List[str]] = None):
        self.components = components or ["tray", "research", "suggestions", "sync"]
        self._running = False
        self._tasks: List[asyncio.Task] = []

        # Component instances
        self._tray = None
        self._state_sync = None
        self._research_agent = None
        self._suggestion_engine = None
        self._llm = None

        # Event loop for async operations
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    async def start(self):
        """Start the daemon and all components."""
        self._running = True
        self._loop = asyncio.get_event_loop()

        logger.info("=" * 60)
        logger.info("JARVIS Daemon Starting")
        logger.info(f"Components: {', '.join(self.components)}")
        logger.info("=" * 60)

        # Start components in order
        try:
            # 1. State sync (foundational)
            if "sync" in self.components:
                await self._start_state_sync()

            # 2. LLM services
            await self._start_llm()

            # 3. System tray (UI)
            if "tray" in self.components:
                await self._start_tray()

            # 4. Research agent
            if "research" in self.components:
                await self._start_research()

            # 5. Proactive suggestions
            if "suggestions" in self.components:
                await self._start_suggestions()

            # Register with state sync
            if self._state_sync:
                self._state_sync.register_component("daemon", "running")

            logger.info("All components started successfully")

            # Main loop - heartbeat and coordination
            await self._main_loop()

        except Exception as e:
            logger.error(f"Daemon startup failed: {e}")
            raise
        finally:
            await self.stop()

    async def _start_state_sync(self):
        """Initialize cross-system state synchronization."""
        logger.info("Starting state sync...")
        try:
            from core.system_tray import get_state_sync
            self._state_sync = get_state_sync()
            logger.info("[OK] State sync initialized")
        except Exception as e:
            logger.warning(f"State sync unavailable: {e}")

    async def _start_llm(self):
        """Initialize LLM services."""
        logger.info("Starting LLM services...")
        try:
            from core.llm import get_llm
            self._llm = await get_llm()

            # Health check
            health = await self._llm.health_check()
            available = [p.value for p, ok in health.items() if ok]
            logger.info(f"[OK] LLM providers available: {', '.join(available) or 'none'}")

        except Exception as e:
            logger.warning(f"LLM services partially available: {e}")

    async def _start_tray(self):
        """Start system tray UI."""
        logger.info("Starting system tray...")
        try:
            from core.system_tray import get_tray, start_tray_daemon

            # Wire up callbacks
            tray, sync = start_tray_daemon()
            self._tray = tray

            # Connect tray actions to daemon
            tray.on_command = self._handle_tray_command
            tray.on_research = self._handle_research_request

            logger.info("[OK] System tray started")

        except Exception as e:
            logger.warning(f"System tray unavailable: {e}")
            logger.info("Running in headless mode")

    async def _start_research(self):
        """Start autonomous research agent."""
        logger.info("Starting research agent...")
        try:
            from core.autonomous_web_agent import get_research_agent

            self._research_agent = get_research_agent()

            # Start background research loop
            task = asyncio.create_task(self._research_loop())
            self._tasks.append(task)

            logger.info("[OK] Research agent started")

        except Exception as e:
            logger.warning(f"Research agent unavailable: {e}")

    async def _start_suggestions(self):
        """Start proactive suggestion engine."""
        logger.info("Starting suggestion engine...")
        try:
            from core.proactive import get_suggestion_engine

            self._suggestion_engine = get_suggestion_engine()

            # Register callback for new suggestions
            self._suggestion_engine.on_suggestion(self._handle_suggestion)

            # Start suggestion loop
            task = asyncio.create_task(self._suggestion_engine.start(check_interval=60))
            self._tasks.append(task)

            logger.info("[OK] Suggestion engine started")

        except Exception as e:
            logger.warning(f"Suggestion engine unavailable: {e}")

    async def _main_loop(self):
        """Main daemon loop - heartbeat and coordination."""
        logger.info("Entering main loop...")

        while self._running:
            try:
                # Heartbeat
                if self._state_sync:
                    self._state_sync.heartbeat("daemon")

                # Update tray status
                if self._tray:
                    self._tray.update_status("active" if self._running else "idle")

                # Process any pending cross-component actions
                if self._state_sync:
                    actions = self._state_sync.get_pending_actions("daemon")
                    for action in actions:
                        await self._process_action(action)

                await asyncio.sleep(10)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Main loop error: {e}")
                await asyncio.sleep(5)

    async def _research_loop(self):
        """Background research loop."""
        if not self._research_agent:
            return

        while self._running:
            try:
                # Run periodic research
                await self._research_agent.run_research_cycle()
                await asyncio.sleep(300)  # Every 5 minutes
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Research loop error: {e}")
                await asyncio.sleep(60)

    def _handle_tray_command(self, command: str):
        """Handle command from system tray."""
        logger.info(f"Tray command: {command}")

        if self._state_sync:
            self._state_sync.queue_action({
                "type": "command",
                "command": command,
                "target": "telegram",  # Forward to telegram bot
            })

        if self._tray:
            self._tray.notify(f"Running: {command}")

    def _handle_research_request(self, topic: str):
        """Handle research request from tray."""
        if self._research_agent:
            # Queue research topic
            asyncio.create_task(self._do_research(topic))

    async def _do_research(self, topic: str):
        """Perform research on a topic."""
        if not self._research_agent:
            return

        try:
            from core.autonomous_web_agent import ResearchTopic, ResearchPriority

            research_topic = ResearchTopic(
                topic=topic or "crypto market trends",
                priority=ResearchPriority.HIGH,
            )

            results = await self._research_agent.research_topic(research_topic)

            if self._tray:
                self._tray.notify(f"Research complete: {len(results)} entries found")

        except Exception as e:
            logger.error(f"Research failed: {e}")

    def _handle_suggestion(self, suggestion):
        """Handle new proactive suggestion."""
        logger.info(f"New suggestion: {suggestion.title}")

        # Show in tray
        if self._tray:
            self._tray.notify(suggestion.content, suggestion.title)

        # Queue for telegram if high priority
        if suggestion.priority.value >= 3 and self._state_sync:
            self._state_sync.queue_action({
                "type": "suggestion",
                "title": suggestion.title,
                "content": suggestion.content,
                "target": "telegram",
            })

    async def _process_action(self, action: Dict[str, Any]):
        """Process a queued action."""
        action_type = action.get("type")
        logger.debug(f"Processing action: {action_type}")

        if action_type == "research":
            await self._do_research(action.get("topic", ""))

        elif action_type == "llm":
            if self._llm:
                result = await self._llm.generate(action.get("prompt", ""))
                if self._state_sync:
                    self._state_sync.set_context("last_llm_result", result.content)

    async def stop(self):
        """Stop the daemon and all components."""
        logger.info("Stopping JARVIS daemon...")
        self._running = False

        # Cancel tasks
        for task in self._tasks:
            task.cancel()

        # Wait for tasks to complete
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)

        # Stop components
        if self._suggestion_engine:
            self._suggestion_engine.stop()

        if self._tray:
            self._tray.stop()

        if self._llm:
            await self._llm.close()

        if self._state_sync:
            self._state_sync.unregister_component("daemon")

        logger.info("JARVIS daemon stopped")

    def handle_signal(self, signum, frame):
        """Handle OS signals."""
        logger.info(f"Received signal {signum}")
        self._running = False


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="JARVIS Daemon")
    parser.add_argument(
        "--components",
        type=str,
        default="tray,research,suggestions,sync",
        help="Comma-separated list of components to start"
    )
    parser.add_argument(
        "--no-tray",
        action="store_true",
        help="Run in headless mode (no system tray)"
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging"
    )

    args = parser.parse_args()

    # Configure logging level
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    # Parse components
    components = args.components.split(",")
    if args.no_tray and "tray" in components:
        components.remove("tray")

    # Create and run daemon
    daemon = JarvisDaemon(components=components)

    # Set up signal handlers
    signal.signal(signal.SIGINT, daemon.handle_signal)
    signal.signal(signal.SIGTERM, daemon.handle_signal)

    # Run
    try:
        asyncio.run(daemon.start())
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.error(f"Daemon error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
