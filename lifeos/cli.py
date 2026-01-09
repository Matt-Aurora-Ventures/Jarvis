"""
LifeOS CLI

Command-line interface for the LifeOS Jarvis system.

Provides commands for:
- Starting/stopping the system
- Chat and interaction
- Status and diagnostics
- Plugin management
- Configuration
"""

import argparse
import asyncio
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from lifeos import Jarvis, Config, get_config


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
        print("LifeOS v1.0.0")
        print("Powered by Jarvis AI")
        return 0

    async def run(self, args: Optional[List[str]] = None) -> int:
        """Run the CLI."""
        parsed = self.parser.parse_args(args)

        if not parsed.command:
            self.parser.print_help()
            return 0

        handlers = {
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
