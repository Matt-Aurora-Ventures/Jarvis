"""
Telegram Bot Command System - Aliases, validation, and help.
"""

import logging
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class CommandCategory(Enum):
    """Command categories for organization."""
    TRADING = "trading"
    ANALYSIS = "analysis"
    PORTFOLIO = "portfolio"
    ADMIN = "admin"
    UTILITY = "utility"


@dataclass
class Command:
    """A bot command definition."""
    name: str
    description: str
    handler: Optional[Callable] = None
    aliases: List[str] = field(default_factory=list)
    category: CommandCategory = CommandCategory.UTILITY
    admin_only: bool = False
    usage: str = ""
    examples: List[str] = field(default_factory=list)


class CommandRegistry:
    """
    Registry for bot commands with alias support.

    Usage:
        registry = CommandRegistry()

        @registry.command("trending", aliases=["t", "trend"])
        async def trending_handler(update, context):
            ...

        # Or register manually
        registry.register(Command(
            name="analyze",
            description="Analyze a token",
            aliases=["a", "check"],
            handler=analyze_handler
        ))
    """

    def __init__(self):
        self._commands: Dict[str, Command] = {}
        self._aliases: Dict[str, str] = {}  # alias -> command name

    def register(self, cmd: Command):
        """Register a command."""
        self._commands[cmd.name] = cmd

        # Register aliases
        for alias in cmd.aliases:
            self._aliases[alias] = cmd.name
            logger.debug(f"Registered alias '{alias}' -> '{cmd.name}'")

        logger.info(f"Registered command: /{cmd.name} (aliases: {cmd.aliases})")

    def command(self, name: str, description: str = "", aliases: List[str] = None,
                category: CommandCategory = CommandCategory.UTILITY, admin_only: bool = False,
                usage: str = "", examples: List[str] = None):
        """
        Decorator to register a command handler.

        Usage:
            @registry.command("trending", aliases=["t", "trend"])
            async def trending(update, context):
                ...
        """
        def decorator(func: Callable):
            cmd = Command(
                name=name,
                description=description or func.__doc__ or "",
                handler=func,
                aliases=aliases or [],
                category=category,
                admin_only=admin_only,
                usage=usage,
                examples=examples or []
            )
            self.register(cmd)
            return func
        return decorator

    def get_command(self, name: str) -> Optional[Command]:
        """Get command by name or alias."""
        # Direct match
        if name in self._commands:
            return self._commands[name]

        # Alias match
        if name in self._aliases:
            return self._commands[self._aliases[name]]

        return None

    def resolve_alias(self, name: str) -> str:
        """Resolve alias to command name."""
        return self._aliases.get(name, name)

    def get_all_commands(self) -> List[Command]:
        """Get all registered commands."""
        return list(self._commands.values())

    def get_by_category(self, category: CommandCategory) -> List[Command]:
        """Get commands by category."""
        return [c for c in self._commands.values() if c.category == category]

    def get_help_text(self, command_name: str = None) -> str:
        """Generate help text."""
        if command_name:
            cmd = self.get_command(command_name)
            if not cmd:
                return f"Unknown command: {command_name}"

            lines = [
                f"*/{cmd.name}* - {cmd.description}",
            ]

            if cmd.aliases:
                lines.append(f"Aliases: {', '.join('/' + a for a in cmd.aliases)}")

            if cmd.usage:
                lines.append(f"Usage: `{cmd.usage}`")

            if cmd.examples:
                lines.append("Examples:")
                for ex in cmd.examples:
                    lines.append(f"  `{ex}`")

            return "\n".join(lines)

        # Full help
        lines = ["*Available Commands:*\n"]

        for category in CommandCategory:
            cmds = self.get_by_category(category)
            if cmds:
                lines.append(f"*{category.value.title()}*")
                for cmd in cmds:
                    if cmd.admin_only:
                        lines.append(f"  /{cmd.name} - {cmd.description} (admin)")
                    else:
                        lines.append(f"  /{cmd.name} - {cmd.description}")
                lines.append("")

        return "\n".join(lines)


# === DEFAULT COMMANDS ===

def setup_default_commands(registry: CommandRegistry):
    """Register default Jarvis commands with aliases."""

    # Trading commands
    registry.register(Command(
        name="trending",
        description="Show trending Solana tokens",
        aliases=["t", "trend", "hot"],
        category=CommandCategory.TRADING,
        usage="/trending [count]",
        examples=["/trending", "/t 20"]
    ))

    registry.register(Command(
        name="analyze",
        description="Analyze a specific token",
        aliases=["a", "check", "lookup"],
        category=CommandCategory.ANALYSIS,
        usage="/analyze <token_address>",
        examples=["/analyze So11...", "/a BONK"]
    ))

    registry.register(Command(
        name="sentiment",
        description="Get market sentiment report",
        aliases=["s", "sent", "report"],
        category=CommandCategory.ANALYSIS,
        usage="/sentiment",
        examples=["/sentiment", "/s"]
    ))

    registry.register(Command(
        name="signals",
        description="Show trading signals",
        aliases=["sig", "signal"],
        category=CommandCategory.TRADING,
        usage="/signals [count]",
        examples=["/signals", "/sig 10"]
    ))

    registry.register(Command(
        name="portfolio",
        description="View treasury portfolio",
        aliases=["p", "port", "holdings"],
        category=CommandCategory.PORTFOLIO,
        usage="/portfolio",
        examples=["/portfolio", "/p"]
    ))

    registry.register(Command(
        name="balance",
        description="Check treasury balance",
        aliases=["b", "bal"],
        category=CommandCategory.PORTFOLIO,
        usage="/balance",
        examples=["/balance", "/b"]
    ))

    registry.register(Command(
        name="pnl",
        description="Show P&L summary",
        aliases=["profit", "gains"],
        category=CommandCategory.PORTFOLIO,
        usage="/pnl [period]",
        examples=["/pnl", "/pnl 7d"]
    ))

    registry.register(Command(
        name="digest",
        description="Get market digest",
        aliases=["d", "summary", "tldr"],
        category=CommandCategory.ANALYSIS,
        usage="/digest",
        examples=["/digest", "/d"]
    ))

    registry.register(Command(
        name="macro",
        description="Get macro market outlook",
        aliases=["m", "dxy", "markets"],
        category=CommandCategory.ANALYSIS,
        usage="/macro",
        examples=["/macro", "/m"]
    ))

    registry.register(Command(
        name="stocks",
        description="Get stock picks",
        aliases=["st", "equities"],
        category=CommandCategory.ANALYSIS,
        usage="/stocks",
        examples=["/stocks", "/st"]
    ))

    registry.register(Command(
        name="commodities",
        description="Get commodities outlook",
        aliases=["comm", "gold", "oil"],
        category=CommandCategory.ANALYSIS,
        usage="/commodities",
        examples=["/commodities", "/comm"]
    ))

    # Admin commands
    registry.register(Command(
        name="admin",
        description="Admin panel",
        aliases=["adm"],
        category=CommandCategory.ADMIN,
        admin_only=True,
        usage="/admin <action>",
        examples=["/admin stats", "/admin reload"]
    ))

    registry.register(Command(
        name="broadcast",
        description="Broadcast message to all users",
        aliases=["bc"],
        category=CommandCategory.ADMIN,
        admin_only=True,
        usage="/broadcast <message>",
        examples=["/broadcast System maintenance in 1 hour"]
    ))

    registry.register(Command(
        name="freeze",
        description="Freeze/unfreeze chat",
        aliases=["lock", "unlock"],
        category=CommandCategory.ADMIN,
        admin_only=True,
        usage="/freeze [on/off]",
        examples=["/freeze on", "/freeze off"]
    ))

    # Utility commands
    registry.register(Command(
        name="help",
        description="Show help",
        aliases=["h", "?", "commands"],
        category=CommandCategory.UTILITY,
        usage="/help [command]",
        examples=["/help", "/help trending"]
    ))

    registry.register(Command(
        name="start",
        description="Start the bot",
        aliases=[],
        category=CommandCategory.UTILITY,
        usage="/start"
    ))

    registry.register(Command(
        name="status",
        description="Check bot status",
        aliases=["ping", "health"],
        category=CommandCategory.UTILITY,
        usage="/status",
        examples=["/status", "/ping"]
    ))

    registry.register(Command(
        name="stats",
        description="Show CLI execution stats (admin only)",
        aliases=["metrics", "perf"],
        category=CommandCategory.ADMIN,
        admin_only=True,
        usage="/stats",
        examples=["/stats", "/metrics"]
    ))

    registry.register(Command(
        name="queue",
        description="Show CLI command queue status (admin only)",
        aliases=["q", "pending"],
        category=CommandCategory.ADMIN,
        admin_only=True,
        usage="/queue",
        examples=["/queue", "/q"]
    ))

    logger.info(f"Registered {len(registry.get_all_commands())} default commands")


# === SINGLETON ===

_registry: Optional[CommandRegistry] = None

def get_command_registry() -> CommandRegistry:
    """Get singleton command registry."""
    global _registry
    if _registry is None:
        _registry = CommandRegistry()
        setup_default_commands(_registry)
    return _registry


# === INPUT SANITIZATION ===

import re
import html

# Patterns to strip from input
DANGEROUS_PATTERNS = [
    re.compile(r'<script[^>]*>.*?</script>', re.IGNORECASE | re.DOTALL),
    re.compile(r'javascript:', re.IGNORECASE),
    re.compile(r'on\w+\s*=', re.IGNORECASE),
    re.compile(r'data:', re.IGNORECASE),
]

def sanitize_input(text: str, max_length: int = 4096) -> str:
    """
    Sanitize user input for safety.

    - Remove dangerous patterns
    - Escape HTML
    - Truncate to max length
    - Remove null bytes
    """
    if not text:
        return ""

    # Remove null bytes
    text = text.replace('\x00', '')

    # Remove dangerous patterns
    for pattern in DANGEROUS_PATTERNS:
        text = pattern.sub('', text)

    # Escape HTML entities
    text = html.escape(text)

    # Truncate
    if len(text) > max_length:
        text = text[:max_length - 3] + "..."

    return text.strip()


def sanitize_token_address(address: str) -> Optional[str]:
    """
    Validate and sanitize a Solana token address.

    Returns sanitized address or None if invalid.
    """
    if not address:
        return None

    # Remove whitespace
    address = address.strip()

    # Basic validation - base58, 32-44 chars
    if not re.match(r'^[1-9A-HJ-NP-Za-km-z]{32,44}$', address):
        return None

    return address


def parse_command_args(text: str) -> tuple[str, List[str]]:
    """
    Parse command and arguments from message text.

    Returns (command_name, [args])
    """
    if not text:
        return "", []

    # Remove leading slash
    if text.startswith('/'):
        text = text[1:]

    # Split on whitespace
    parts = text.split()

    if not parts:
        return "", []

    # Command is first part (might have @botname suffix)
    command = parts[0].split('@')[0].lower()

    # Rest are arguments
    args = parts[1:] if len(parts) > 1 else []

    return command, args
