"""
LifeOS CLI

Unified command-line interface for the LifeOS Jarvis system.

Provides commands for:
- Starting/stopping the system
- Chat and interaction
- Status and diagnostics
- Plugin management
- Configuration
- Doctor/health checks
- Trading operations
- Agent management
- Economics tracking

This is the single entry point for all LifeOS operations.
"""

import argparse
import asyncio
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from lifeos import Jarvis, Config, get_config

# Import core CLI for delegation to advanced commands
try:
    from core import cli as core_cli
    CORE_CLI_AVAILABLE = True
except ImportError:
    CORE_CLI_AVAILABLE = False


def create_parser() -> argparse.ArgumentParser:
    """Create the argument parser."""
    parser = argparse.ArgumentParser(
        prog="lifeos",
        description="LifeOS - Your AI Life Operating System",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Start command
    start_parser = subparsers.add_parser("start", help="Start LifeOS")
    start_parser.add_argument(
        "--foreground", "-f",
        action="store_true",
        help="Run in foreground (don't daemonize)",
    )
    start_parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Verbose output",
    )

    # Stop command
    stop_parser = subparsers.add_parser("stop", help="Stop LifeOS")

    # Status command
    status_parser = subparsers.add_parser("status", help="Show system status")
    status_parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show detailed status",
    )
    status_parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON",
    )

    # Chat command
    chat_parser = subparsers.add_parser("chat", help="Chat with Jarvis")
    chat_parser.add_argument(
        "message",
        nargs="?",
        help="Message to send (omit for interactive mode)",
    )
    chat_parser.add_argument(
        "--persona", "-p",
        help="Persona to use (default: jarvis)",
    )

    # Plugin commands
    plugin_parser = subparsers.add_parser("plugin", help="Plugin management")
    plugin_subparsers = plugin_parser.add_subparsers(dest="plugin_command")

    plugin_list = plugin_subparsers.add_parser("list", help="List plugins")
    plugin_enable = plugin_subparsers.add_parser("enable", help="Enable plugin")
    plugin_enable.add_argument("name", help="Plugin name")
    plugin_disable = plugin_subparsers.add_parser("disable", help="Disable plugin")
    plugin_disable.add_argument("name", help="Plugin name")
    plugin_info = plugin_subparsers.add_parser("info", help="Plugin info")
    plugin_info.add_argument("name", help="Plugin name")

    # Config command
    config_parser = subparsers.add_parser("config", help="Configuration management")
    config_parser.add_argument(
        "--get",
        metavar="KEY",
        help="Get a config value",
    )
    config_parser.add_argument(
        "--set",
        nargs=2,
        metavar=("KEY", "VALUE"),
        help="Set a config value",
    )
    config_parser.add_argument(
        "--list",
        action="store_true",
        help="List all config values",
    )

    # Memory commands
    memory_parser = subparsers.add_parser("memory", help="Memory operations")
    memory_subparsers = memory_parser.add_subparsers(dest="memory_command")

    memory_get = memory_subparsers.add_parser("get", help="Get memory value")
    memory_get.add_argument("key", help="Memory key")
    memory_set = memory_subparsers.add_parser("set", help="Set memory value")
    memory_set.add_argument("key", help="Memory key")
    memory_set.add_argument("value", help="Memory value")
    memory_forget = memory_subparsers.add_parser("forget", help="Forget memory key")
    memory_forget.add_argument("key", help="Memory key")

    # Persona command
    persona_parser = subparsers.add_parser("persona", help="Persona management")
    persona_parser.add_argument(
        "--list",
        action="store_true",
        help="List available personas",
    )
    persona_parser.add_argument(
        "--set",
        metavar="NAME",
        help="Set active persona",
    )
    persona_parser.add_argument(
        "--info",
        metavar="NAME",
        help="Show persona details",
    )

    # Events command
    events_parser = subparsers.add_parser("events", help="Event bus operations")
    events_parser.add_argument(
        "--history",
        action="store_true",
        help="Show event history",
    )
    events_parser.add_argument(
        "--stats",
        action="store_true",
        help="Show event statistics",
    )
    events_parser.add_argument(
        "--pattern",
        metavar="PATTERN",
        help="Filter by pattern",
    )

    # Version command
    version_parser = subparsers.add_parser("version", help="Show version")

    # ==========================================================================
    # Core CLI Commands (delegated to core/cli.py)
    # ==========================================================================

    # Doctor command - health diagnostics
    doctor_parser = subparsers.add_parser("doctor", help="Run health diagnostics")
    doctor_parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    doctor_parser.add_argument("--fix", action="store_true", help="Attempt to fix issues")

    # Diagnostics command
    diagnostics_parser = subparsers.add_parser("diagnostics", help="System diagnostics")
    diagnostics_parser.add_argument("--dry-run", action="store_true", help="Preview only")

    # Agents command
    agents_parser = subparsers.add_parser("agents", help="Multi-agent system management")
    agents_subparsers = agents_parser.add_subparsers(dest="agents_action")
    agents_subparsers.add_parser("status", help="Show agent system status")
    agents_run_parser = agents_subparsers.add_parser("run", help="Run specific agent")
    agents_run_parser.add_argument("agent_name", help="Agent to run")
    agents_run_parser.add_argument("--task", help="Task description")
    agents_subparsers.add_parser("providers", help="Show provider availability")

    # Economics command
    economics_parser = subparsers.add_parser("economics", help="Economic dashboard and P&L")
    economics_subparsers = economics_parser.add_subparsers(dest="economics_action")
    economics_subparsers.add_parser("status", help="Show economic status")
    economics_subparsers.add_parser("report", help="Generate P&L report")
    economics_subparsers.add_parser("costs", help="Show cost breakdown")
    economics_subparsers.add_parser("revenue", help="Show revenue breakdown")
    economics_subparsers.add_parser("alerts", help="Show economic alerts")

    # Trading positions command
    trading_parser = subparsers.add_parser("trading", help="Trading operations")
    trading_subparsers = trading_parser.add_subparsers(dest="trading_action")
    trading_subparsers.add_parser("positions", help="List open positions")
    trading_subparsers.add_parser("opportunities", help="Show trading opportunities")
    trading_subparsers.add_parser("scores", help="Strategy scores")

    # Task management command
    task_parser = subparsers.add_parser("task", help="Task management")
    task_subparsers = task_parser.add_subparsers(dest="task_action")
    task_add = task_subparsers.add_parser("add", help="Add a task")
    task_add.add_argument("description", help="Task description")
    task_add.add_argument("--priority", type=int, default=5, help="Priority 1-10")
    task_subparsers.add_parser("list", help="List tasks")
    task_complete = task_subparsers.add_parser("complete", help="Complete a task")
    task_complete.add_argument("task_id", help="Task ID")

    # Objective management command
    objective_parser = subparsers.add_parser("objective", help="Objective management")
    objective_subparsers = objective_parser.add_subparsers(dest="objective_action")
    obj_add = objective_subparsers.add_parser("add", help="Add an objective")
    obj_add.add_argument("description", help="Objective description")
    objective_subparsers.add_parser("list", help="List objectives")
    objective_subparsers.add_parser("history", help="Show objective history")

    # Secret management command
    secret_parser = subparsers.add_parser("secret", help="Secret/API key management")
    secret_parser.add_argument("--set", nargs=2, metavar=("KEY", "VALUE"), help="Set a secret")
    secret_parser.add_argument("--list", action="store_true", help="List configured keys")

    # Log command
    log_parser = subparsers.add_parser("log", help="View system logs")
    log_parser.add_argument("--tail", type=int, default=50, help="Number of lines")
    log_parser.add_argument("--follow", "-f", action="store_true", help="Follow log output")

    return parser


class LifeOSCLI:
    """LifeOS command-line interface."""

    def __init__(self):
        self.jarvis: Optional[Jarvis] = None
        self.parser = create_parser()

    async def _ensure_jarvis(self) -> Jarvis:
        """Ensure Jarvis is initialized."""
        if self.jarvis is None:
            self.jarvis = Jarvis()
            await self.jarvis.start()
        return self.jarvis

    async def _shutdown_jarvis(self) -> None:
        """Shut down Jarvis if running."""
        if self.jarvis and self.jarvis.is_running:
            await self.jarvis.stop()

    async def cmd_start(self, args: argparse.Namespace) -> int:
        """Start LifeOS."""
        print("Starting LifeOS...")

        try:
            jarvis = await self._ensure_jarvis()

            if args.verbose:
                stats = jarvis.get_stats()
                print(f"  Memory: {stats['memory']['entry_count']} entries")
                print(f"  Events: {stats['events']['pattern_count']} patterns registered")
                print(f"  PAE: {stats['pae']['providers']} providers, {stats['pae']['actions']} actions")

            print(f"LifeOS started successfully at {datetime.now().strftime('%H:%M:%S')}")

            if args.foreground:
                print("Running in foreground. Press Ctrl+C to stop.")
                try:
                    # Keep running
                    while jarvis.is_running:
                        await asyncio.sleep(1)
                except KeyboardInterrupt:
                    print("\nStopping...")
                    await self._shutdown_jarvis()
                    print("LifeOS stopped.")

            return 0

        except Exception as e:
            print(f"Failed to start: {e}")
            return 1

    async def cmd_stop(self, args: argparse.Namespace) -> int:
        """Stop LifeOS."""
        print("Stopping LifeOS...")

        try:
            await self._shutdown_jarvis()
            print("LifeOS stopped.")
            return 0
        except Exception as e:
            print(f"Failed to stop: {e}")
            return 1

    async def cmd_status(self, args: argparse.Namespace) -> int:
        """Show system status."""
        try:
            jarvis = await self._ensure_jarvis()
            stats = jarvis.get_stats()

            if args.json:
                import json
                print(json.dumps(stats, indent=2, default=str))
            else:
                print("LifeOS Status")
                print("=" * 40)
                print(f"Running: {'Yes' if stats['running'] else 'No'}")
                print(f"Uptime: {stats['uptime_seconds']:.0f}s")
                print()

                print("Memory:")
                print(f"  Entries: {stats['memory']['entry_count']}")
                print(f"  Namespaces: {stats['memory']['namespace_count']}")
                print()

                print("Events:")
                print(f"  Emitted: {stats['events']['events_emitted']}")
                print(f"  Handled: {stats['events']['events_handled']}")
                print(f"  Patterns: {stats['events']['pattern_count']}")
                print()

                print("PAE Registry:")
                print(f"  Providers: {stats['pae']['providers']}")
                print(f"  Actions: {stats['pae']['actions']}")
                print(f"  Evaluators: {stats['pae']['evaluators']}")

                if args.verbose:
                    print()
                    print("Plugins:")
                    plugins = jarvis.list_plugins()
                    for name in plugins:
                        print(f"  - {name}")

            await self._shutdown_jarvis()
            return 0

        except Exception as e:
            print(f"Error: {e}")
            return 1

    async def cmd_chat(self, args: argparse.Namespace) -> int:
        """Chat with Jarvis."""
        try:
            jarvis = await self._ensure_jarvis()

            if args.persona:
                jarvis.set_persona(args.persona)

            if args.message:
                # Single message mode
                response = await jarvis.chat(args.message)
                print(response)
            else:
                # Interactive mode
                greeting = jarvis.get_greeting()
                print(greeting)
                print("(Type 'exit' or 'quit' to end)")
                print()

                while True:
                    try:
                        user_input = input("You: ").strip()
                        if not user_input:
                            continue
                        if user_input.lower() in ("exit", "quit", "bye"):
                            print("Goodbye!")
                            break

                        response = await jarvis.chat(user_input)
                        print(f"Jarvis: {response}")
                        print()
                    except EOFError:
                        break

            await self._shutdown_jarvis()
            return 0

        except Exception as e:
            print(f"Error: {e}")
            return 1

    async def cmd_plugin(self, args: argparse.Namespace) -> int:
        """Plugin management."""
        try:
            jarvis = await self._ensure_jarvis()

            if args.plugin_command == "list":
                plugins = jarvis.list_plugins()
                print("Plugins:")
                for name in plugins:
                    print(f"  - {name}")

            elif args.plugin_command == "enable":
                success = await jarvis.enable_plugin(args.name)
                if success:
                    print(f"Plugin '{args.name}' enabled.")
                else:
                    print(f"Failed to enable plugin '{args.name}'.")
                    return 1

            elif args.plugin_command == "disable":
                success = await jarvis.disable_plugin(args.name)
                if success:
                    print(f"Plugin '{args.name}' disabled.")
                else:
                    print(f"Failed to disable plugin '{args.name}'.")
                    return 1

            elif args.plugin_command == "info":
                plugins = jarvis.list_plugins()
                if args.name in plugins:
                    print(f"Plugin: {args.name}")
                    print("  Status: loaded")
                else:
                    print(f"Plugin '{args.name}' not found.")
                    return 1

            else:
                print("Usage: lifeos plugin [list|enable|disable|info]")

            await self._shutdown_jarvis()
            return 0

        except Exception as e:
            print(f"Error: {e}")
            return 1

    async def cmd_config(self, args: argparse.Namespace) -> int:
        """Configuration management."""
        config = get_config()

        if args.get:
            value = config.get(args.get)
            if value is not None:
                print(f"{args.get} = {value}")
            else:
                print(f"Key not found: {args.get}")
                return 1

        elif args.set:
            key, value = args.set
            config.set(key, value)
            print(f"Set {key} = {value}")

        elif args.list:
            data = config.to_dict()
            for section, values in data.items():
                print(f"[{section}]")
                if isinstance(values, dict):
                    for key, val in values.items():
                        print(f"  {key} = {val}")
                else:
                    print(f"  {values}")
                print()

        else:
            print("Usage: lifeos config [--get KEY | --set KEY VALUE | --list]")

        return 0

    async def cmd_memory(self, args: argparse.Namespace) -> int:
        """Memory operations."""
        try:
            jarvis = await self._ensure_jarvis()

            if args.memory_command == "get":
                value = await jarvis.recall(args.key)
                if value is not None:
                    print(f"{args.key} = {value}")
                else:
                    print(f"Key not found: {args.key}")

            elif args.memory_command == "set":
                await jarvis.remember(args.key, args.value)
                print(f"Set {args.key} = {args.value}")

            elif args.memory_command == "forget":
                deleted = await jarvis.forget(args.key)
                if deleted:
                    print(f"Forgot: {args.key}")
                else:
                    print(f"Key not found: {args.key}")

            else:
                print("Usage: lifeos memory [get|set|forget]")

            await self._shutdown_jarvis()
            return 0

        except Exception as e:
            print(f"Error: {e}")
            return 1

    async def cmd_persona(self, args: argparse.Namespace) -> int:
        """Persona management."""
        try:
            jarvis = await self._ensure_jarvis()

            if args.list:
                personas = jarvis.list_personas()
                active = jarvis.persona_manager.get_active_name()
                print("Available personas:")
                for name in personas:
                    marker = " (active)" if name == active else ""
                    print(f"  - {name}{marker}")

            elif args.set:
                success = jarvis.set_persona(args.set)
                if success:
                    print(f"Switched to persona: {args.set}")
                else:
                    print(f"Failed to switch to persona: {args.set}")
                    return 1

            elif args.info:
                persona = jarvis.persona_manager.get_persona(args.info)
                if persona:
                    print(f"Persona: {persona.name}")
                    print(f"Description: {persona.description}")
                    print(f"Voice: {persona.voice_description}")
                    print(f"Traits: {[t.value for t in persona.traits]}")
                else:
                    print(f"Persona not found: {args.info}")
                    return 1

            else:
                print("Usage: lifeos persona [--list | --set NAME | --info NAME]")

            await self._shutdown_jarvis()
            return 0

        except Exception as e:
            print(f"Error: {e}")
            return 1

    async def cmd_events(self, args: argparse.Namespace) -> int:
        """Event bus operations."""
        try:
            jarvis = await self._ensure_jarvis()
            event_bus = jarvis.event_bus

            if args.stats:
                stats = event_bus.get_stats()
                print("Event Bus Statistics:")
                print(f"  Events emitted: {stats['events_emitted']}")
                print(f"  Events handled: {stats['events_handled']}")
                print(f"  Handlers failed: {stats['handlers_failed']}")
                print(f"  Patterns: {stats['pattern_count']}")
                print(f"  History size: {stats['history_size']}")

            elif args.history:
                pattern = args.pattern if args.pattern else None
                history = event_bus.get_history(pattern=pattern, limit=20)
                print("Recent Events:")
                for event in history:
                    print(f"  [{event.timestamp.strftime('%H:%M:%S')}] {event.topic}")
                    if event.data:
                        print(f"    Data: {event.data}")

            else:
                print("Usage: lifeos events [--stats | --history]")

            await self._shutdown_jarvis()
            return 0

        except Exception as e:
            print(f"Error: {e}")
            return 1

    def cmd_version(self, args: argparse.Namespace) -> int:
        """Show version."""
        from lifeos import __version__
        print(f"LifeOS v{__version__}")
        print("Powered by Jarvis AI")
        return 0

    # ==========================================================================
    # Core CLI Command Handlers (delegated)
    # ==========================================================================

    def cmd_doctor(self, args: argparse.Namespace) -> int:
        """Run health diagnostics."""
        if CORE_CLI_AVAILABLE:
            return core_cli.cmd_doctor(args)
        else:
            print("Running basic health check...")
            # Fallback to basic checks
            from core import providers, secrets
            health = providers.check_provider_health()
            print("\nProvider Health:")
            for name, info in health.items():
                status = "✓" if info.get("available") else "✗"
                print(f"  {status} {name}: {info.get('message', 'Unknown')}")

            keys = secrets.list_configured_keys()
            print("\nConfigured Keys:")
            for name, configured in keys.items():
                status = "✓" if configured else "✗"
                print(f"  {status} {name}")

            return 0

    def cmd_diagnostics(self, args: argparse.Namespace) -> int:
        """Run system diagnostics."""
        if CORE_CLI_AVAILABLE:
            return core_cli.cmd_diagnostics(args)
        else:
            from core import diagnostics
            data = diagnostics.run_diagnostics()
            print("System Diagnostics")
            print("=" * 40)
            if "profile" in data and data["profile"]:
                p = data["profile"]
                print(f"OS: {p.os_version}")
                print(f"CPU Load: {p.cpu_load:.2f}")
                print(f"RAM: {p.ram_free_gb:.1f}/{p.ram_total_gb:.1f} GB free")
                print(f"Disk Free: {p.disk_free_gb:.1f} GB")
            return 0

    def cmd_agents(self, args: argparse.Namespace) -> int:
        """Manage multi-agent system."""
        if CORE_CLI_AVAILABLE:
            return core_cli.cmd_agents(args)
        else:
            print("Agent management requires core CLI")
            return 1

    def cmd_economics(self, args: argparse.Namespace) -> int:
        """Economics dashboard."""
        if CORE_CLI_AVAILABLE:
            return core_cli.cmd_economics(args)
        else:
            print("Economics dashboard requires core CLI")
            return 1

    def cmd_trading(self, args: argparse.Namespace) -> int:
        """Trading operations."""
        if not CORE_CLI_AVAILABLE:
            print("Trading operations require core CLI")
            return 1

        action = getattr(args, 'trading_action', None)
        if action == "positions":
            return core_cli.cmd_trading_positions(args)
        elif action == "opportunities":
            return core_cli.cmd_trading_opportunities(args)
        elif action == "scores":
            return core_cli.cmd_strategy_scores(args)
        else:
            print("Usage: lifeos trading [positions|opportunities|scores]")
            return 0

    def cmd_task(self, args: argparse.Namespace) -> int:
        """Task management."""
        if CORE_CLI_AVAILABLE:
            return core_cli.cmd_task(args)
        else:
            print("Task management requires core CLI")
            return 1

    def cmd_objective(self, args: argparse.Namespace) -> int:
        """Objective management."""
        if CORE_CLI_AVAILABLE:
            return core_cli.cmd_objective(args)
        else:
            print("Objective management requires core CLI")
            return 1

    def cmd_secret(self, args: argparse.Namespace) -> int:
        """Secret/API key management."""
        if CORE_CLI_AVAILABLE:
            return core_cli.cmd_secret(args)
        else:
            from core import secrets
            if args.list:
                keys = secrets.list_configured_keys()
                print("Configured Secrets:")
                for name, configured in keys.items():
                    status = "✓" if configured else "✗"
                    print(f"  {status} {name}")
            elif args.set:
                key, value = args.set
                secrets.set_key(key, value)
                print(f"Set secret: {key}")
            else:
                print("Usage: lifeos secret [--list | --set KEY VALUE]")
            return 0

    def cmd_log(self, args: argparse.Namespace) -> int:
        """View system logs."""
        if CORE_CLI_AVAILABLE:
            return core_cli.cmd_log(args)
        else:
            from pathlib import Path
            log_path = Path.home() / ".lifeos" / "logs" / "jarvis.log"
            if log_path.exists():
                lines = log_path.read_text().splitlines()
                for line in lines[-args.tail:]:
                    print(line)
            else:
                print("No log file found")
            return 0

    async def run(self, args: Optional[List[str]] = None) -> int:
        """Run the CLI."""
        parsed = self.parser.parse_args(args)

        if not parsed.command:
            self.parser.print_help()
            return 0

        handlers = {
            # LifeOS native commands
            "start": self.cmd_start,
            "stop": self.cmd_stop,
            "status": self.cmd_status,
            "chat": self.cmd_chat,
            "plugin": self.cmd_plugin,
            "config": self.cmd_config,
            "memory": self.cmd_memory,
            "persona": self.cmd_persona,
            "events": self.cmd_events,
            "version": lambda args: self.cmd_version(args),
            # Core CLI delegated commands
            "doctor": lambda args: self.cmd_doctor(args),
            "diagnostics": lambda args: self.cmd_diagnostics(args),
            "agents": lambda args: self.cmd_agents(args),
            "economics": lambda args: self.cmd_economics(args),
            "trading": lambda args: self.cmd_trading(args),
            "task": lambda args: self.cmd_task(args),
            "objective": lambda args: self.cmd_objective(args),
            "secret": lambda args: self.cmd_secret(args),
            "log": lambda args: self.cmd_log(args),
        }

        handler = handlers.get(parsed.command)
        if handler:
            if asyncio.iscoroutinefunction(handler):
                return await handler(parsed)
            else:
                return handler(parsed)
        else:
            print(f"Unknown command: {parsed.command}")
            return 1


def main() -> int:
    """Main entry point."""
    cli = LifeOSCLI()
    return asyncio.run(cli.run())


if __name__ == "__main__":
    sys.exit(main())
