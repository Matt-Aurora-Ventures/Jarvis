"""
JARVIS Bot Command Help System

Comprehensive help system for all JARVIS bots:
- Command registration and documentation
- Dynamic help generation
- Permission-aware help
- Multi-language support structure

Usage:
    from core.bot.help import HelpSystem, command

    help_system = HelpSystem("telegram")

    @command(help_system, "/start", "Start the bot", category="general")
    async def start_command(message):
        ...

    # Get help text
    help_text = help_system.get_help()
"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, Set

logger = logging.getLogger("jarvis.bot.help")


# =============================================================================
# MODELS
# =============================================================================

class CommandCategory(Enum):
    """Command categories for organization"""
    GENERAL = "general"
    TRADING = "trading"
    PORTFOLIO = "portfolio"
    ALERTS = "alerts"
    SETTINGS = "settings"
    ADMIN = "admin"
    INFO = "info"
    UTILITY = "utility"


class UserRole(Enum):
    """User permission roles"""
    PUBLIC = "public"           # Anyone can use
    SUBSCRIBER = "subscriber"   # Paid subscribers
    ADMIN = "admin"             # Administrators
    OWNER = "owner"             # Bot owner only


@dataclass
class CommandInfo:
    """Information about a command"""
    name: str
    description: str
    usage: str = ""
    examples: List[str] = field(default_factory=list)
    category: CommandCategory = CommandCategory.GENERAL
    aliases: List[str] = field(default_factory=list)
    min_role: UserRole = UserRole.PUBLIC
    hidden: bool = False
    parameters: Dict[str, str] = field(default_factory=dict)
    handler: Optional[Callable] = None

    def format_usage(self) -> str:
        """Format command usage"""
        if self.usage:
            return f"{self.name} {self.usage}"
        return self.name

    def format_full(self, include_examples: bool = True) -> str:
        """Format full command help"""
        lines = [
            f"**{self.name}**",
            f"_{self.description}_",
        ]

        if self.usage:
            lines.append(f"\n📝 Usage: `{self.format_usage()}`")

        if self.parameters:
            lines.append("\n📋 Parameters:")
            for param, desc in self.parameters.items():
                lines.append(f"  • `{param}` - {desc}")

        if include_examples and self.examples:
            lines.append("\n💡 Examples:")
            for example in self.examples:
                lines.append(f"  `{example}`")

        if self.aliases:
            lines.append(f"\n🔗 Aliases: {', '.join(self.aliases)}")

        return "\n".join(lines)


# =============================================================================
# HELP SYSTEM
# =============================================================================

class HelpSystem:
    """
    Centralized help system for bot commands.

    Features:
    - Command registration
    - Category organization
    - Role-based visibility
    - Dynamic help generation
    """

    # Category display order
    CATEGORY_ORDER = [
        CommandCategory.GENERAL,
        CommandCategory.TRADING,
        CommandCategory.PORTFOLIO,
        CommandCategory.ALERTS,
        CommandCategory.INFO,
        CommandCategory.UTILITY,
        CommandCategory.SETTINGS,
        CommandCategory.ADMIN,
    ]

    # Category icons
    CATEGORY_ICONS = {
        CommandCategory.GENERAL: "🏠",
        CommandCategory.TRADING: "📈",
        CommandCategory.PORTFOLIO: "💼",
        CommandCategory.ALERTS: "🔔",
        CommandCategory.SETTINGS: "⚙️",
        CommandCategory.ADMIN: "👑",
        CommandCategory.INFO: "ℹ️",
        CommandCategory.UTILITY: "🔧",
    }

    # Category names
    CATEGORY_NAMES = {
        CommandCategory.GENERAL: "General",
        CommandCategory.TRADING: "Trading",
        CommandCategory.PORTFOLIO: "Portfolio",
        CommandCategory.ALERTS: "Alerts",
        CommandCategory.SETTINGS: "Settings",
        CommandCategory.ADMIN: "Admin",
        CommandCategory.INFO: "Information",
        CommandCategory.UTILITY: "Utility",
    }

    def __init__(
        self,
        bot_name: str,
        bot_description: str = "",
        prefix: str = "/",
    ):
        """
        Initialize help system.

        Args:
            bot_name: Name of the bot
            bot_description: Description of the bot
            prefix: Command prefix (default: /)
        """
        self.bot_name = bot_name
        self.bot_description = bot_description
        self.prefix = prefix

        self._commands: Dict[str, CommandInfo] = {}
        self._aliases: Dict[str, str] = {}  # alias -> command name
        self._categories: Dict[CommandCategory, List[str]] = {
            cat: [] for cat in CommandCategory
        }

        logger.info(f"Initialized help system for {bot_name}")

    # =========================================================================
    # COMMAND REGISTRATION
    # =========================================================================

    def register(
        self,
        name: str,
        description: str,
        usage: str = "",
        examples: List[str] = None,
        category: CommandCategory = CommandCategory.GENERAL,
        aliases: List[str] = None,
        min_role: UserRole = UserRole.PUBLIC,
        hidden: bool = False,
        parameters: Dict[str, str] = None,
        handler: Callable = None,
    ) -> CommandInfo:
        """
        Register a command.

        Args:
            name: Command name (e.g., "/start")
            description: Short description
            usage: Usage pattern (e.g., "<token> [amount]")
            examples: Example usages
            category: Command category
            aliases: Alternative command names
            min_role: Minimum role required
            hidden: If True, not shown in help
            parameters: Parameter descriptions
            handler: Command handler function

        Returns:
            CommandInfo object
        """
        # Normalize name
        if not name.startswith(self.prefix):
            name = self.prefix + name

        cmd = CommandInfo(
            name=name,
            description=description,
            usage=usage,
            examples=examples or [],
            category=category,
            aliases=aliases or [],
            min_role=min_role,
            hidden=hidden,
            parameters=parameters or {},
            handler=handler,
        )

        self._commands[name] = cmd
        self._categories[category].append(name)

        # Register aliases
        for alias in cmd.aliases:
            if not alias.startswith(self.prefix):
                alias = self.prefix + alias
            self._aliases[alias] = name

        logger.debug(f"Registered command: {name}")
        return cmd

    def unregister(self, name: str):
        """Unregister a command"""
        if not name.startswith(self.prefix):
            name = self.prefix + name

        if name in self._commands:
            cmd = self._commands[name]

            # Remove from category
            if name in self._categories[cmd.category]:
                self._categories[cmd.category].remove(name)

            # Remove aliases
            for alias in cmd.aliases:
                if alias in self._aliases:
                    del self._aliases[alias]

            del self._commands[name]
            logger.debug(f"Unregistered command: {name}")

    def get_command(self, name: str) -> Optional[CommandInfo]:
        """Get command by name or alias"""
        if not name.startswith(self.prefix):
            name = self.prefix + name

        # Direct match
        if name in self._commands:
            return self._commands[name]

        # Alias match
        if name in self._aliases:
            return self._commands[self._aliases[name]]

        return None

    # =========================================================================
    # HELP GENERATION
    # =========================================================================

    def get_help(
        self,
        user_role: UserRole = UserRole.PUBLIC,
        category: CommandCategory = None,
        include_hidden: bool = False,
    ) -> str:
        """
        Generate help text.

        Args:
            user_role: User's role for filtering
            category: Specific category to show
            include_hidden: Whether to include hidden commands

        Returns:
            Formatted help text
        """
        lines = []

        # Header
        if self.bot_description:
            lines.append(f"**{self.bot_name}**")
            lines.append(f"_{self.bot_description}_\n")

        # Filter categories
        categories = [category] if category else self.CATEGORY_ORDER

        for cat in categories:
            commands = self._get_visible_commands(
                cat, user_role, include_hidden
            )

            if not commands:
                continue

            icon = self.CATEGORY_ICONS.get(cat, "📌")
            name = self.CATEGORY_NAMES.get(cat, cat.value.title())

            lines.append(f"\n{icon} **{name}**")

            for cmd in commands:
                desc = cmd.description[:50] + "..." if len(cmd.description) > 50 else cmd.description
                lines.append(f"  `{cmd.name}` - {desc}")

        # Footer
        lines.append(f"\n💬 Type `{self.prefix}help <command>` for details")

        return "\n".join(lines)

    def get_command_help(self, name: str) -> str:
        """Get detailed help for a specific command"""
        cmd = self.get_command(name)

        if cmd is None:
            return f"❌ Command not found: `{name}`"

        return cmd.format_full(include_examples=True)

    def get_category_help(
        self,
        category: CommandCategory,
        user_role: UserRole = UserRole.PUBLIC,
    ) -> str:
        """Get help for a specific category"""
        return self.get_help(user_role=user_role, category=category)

    def _get_visible_commands(
        self,
        category: CommandCategory,
        user_role: UserRole,
        include_hidden: bool,
    ) -> List[CommandInfo]:
        """Get commands visible to a user"""
        role_order = [UserRole.PUBLIC, UserRole.SUBSCRIBER, UserRole.ADMIN, UserRole.OWNER]
        user_level = role_order.index(user_role)

        commands = []
        for name in self._categories[category]:
            cmd = self._commands.get(name)
            if cmd is None:
                continue

            # Check visibility
            if cmd.hidden and not include_hidden:
                continue

            # Check role
            cmd_level = role_order.index(cmd.min_role)
            if cmd_level > user_level:
                continue

            commands.append(cmd)

        return sorted(commands, key=lambda c: c.name)

    # =========================================================================
    # SEARCH
    # =========================================================================

    def search(
        self,
        query: str,
        user_role: UserRole = UserRole.PUBLIC,
    ) -> List[CommandInfo]:
        """Search commands by name or description"""
        query = query.lower()
        results = []

        role_order = [UserRole.PUBLIC, UserRole.SUBSCRIBER, UserRole.ADMIN, UserRole.OWNER]
        user_level = role_order.index(user_role)

        for cmd in self._commands.values():
            # Check role
            cmd_level = role_order.index(cmd.min_role)
            if cmd_level > user_level:
                continue

            # Search in name and description
            if (query in cmd.name.lower() or
                query in cmd.description.lower() or
                any(query in alias.lower() for alias in cmd.aliases)):
                results.append(cmd)

        return results

    # =========================================================================
    # UTILITIES
    # =========================================================================

    def get_all_commands(self) -> List[CommandInfo]:
        """Get all registered commands"""
        return list(self._commands.values())

    def get_command_names(self) -> List[str]:
        """Get all command names"""
        return list(self._commands.keys())

    def get_categories(self) -> List[CommandCategory]:
        """Get categories that have commands"""
        return [cat for cat in self.CATEGORY_ORDER if self._categories[cat]]

    def to_dict(self) -> Dict[str, Any]:
        """Export help system to dictionary"""
        return {
            "bot_name": self.bot_name,
            "bot_description": self.bot_description,
            "prefix": self.prefix,
            "commands": {
                name: {
                    "description": cmd.description,
                    "usage": cmd.format_usage(),
                    "category": cmd.category.value,
                    "examples": cmd.examples,
                    "aliases": cmd.aliases,
                    "min_role": cmd.min_role.value,
                    "hidden": cmd.hidden,
                }
                for name, cmd in self._commands.items()
            }
        }


# =============================================================================
# DECORATORS
# =============================================================================

def command(
    help_system: HelpSystem,
    name: str,
    description: str,
    usage: str = "",
    examples: List[str] = None,
    category: str = "general",
    aliases: List[str] = None,
    min_role: str = "public",
    hidden: bool = False,
    parameters: Dict[str, str] = None,
):
    """
    Decorator to register a command with the help system.

    Usage:
        @command(help_system, "/start", "Start the bot")
        async def start_handler(update, context):
            ...
    """
    # Convert string category to enum
    cat_enum = CommandCategory(category.lower())
    role_enum = UserRole(min_role.lower())

    def decorator(func: Callable) -> Callable:
        # Register command
        help_system.register(
            name=name,
            description=description,
            usage=usage,
            examples=examples or [],
            category=cat_enum,
            aliases=aliases or [],
            min_role=role_enum,
            hidden=hidden,
            parameters=parameters or {},
            handler=func,
        )

        @wraps(func)
        async def wrapper(*args, **kwargs):
            return await func(*args, **kwargs)

        # Store reference
        wrapper._command_info = help_system.get_command(name)

        return wrapper

    return decorator


# =============================================================================
# HELP HANDLER GENERATOR
# =============================================================================

def create_help_handler(help_system: HelpSystem) -> Callable:
    """
    Create a help command handler for a bot.

    Usage:
        help_handler = create_help_handler(help_system)

        # In Telegram bot
        app.add_handler(CommandHandler("help", help_handler))
    """
    async def help_handler(update, context):
        """Dynamic help command handler"""
        # Get user role (can be customized)
        user_role = UserRole.PUBLIC

        # Check for admin
        if hasattr(update, "effective_user"):
            user_id = update.effective_user.id
            # You can add admin check logic here
            # if user_id in ADMIN_IDS:
            #     user_role = UserRole.ADMIN

        # Parse arguments
        args = context.args if hasattr(context, "args") else []

        if not args:
            # General help
            help_text = help_system.get_help(user_role=user_role)
        else:
            # Specific command or category help
            query = args[0].lower()

            # Check if it's a category
            try:
                cat = CommandCategory(query)
                help_text = help_system.get_category_help(cat, user_role)
            except ValueError:
                # Command help
                help_text = help_system.get_command_help(query)

        await update.message.reply_text(
            help_text,
            parse_mode="Markdown",
        )

    # Register help command itself
    help_system.register(
        name="/help",
        description="Show help information",
        usage="[command|category]",
        examples=["/help", "/help /buy", "/help trading"],
        category=CommandCategory.GENERAL,
        min_role=UserRole.PUBLIC,
    )

    return help_handler


# =============================================================================
# SINGLETON HELP SYSTEMS
# =============================================================================

_help_systems: Dict[str, HelpSystem] = {}


def get_help_system(
    bot_name: str,
    bot_description: str = "",
    prefix: str = "/",
) -> HelpSystem:
    """Get or create a help system for a bot"""
    if bot_name not in _help_systems:
        _help_systems[bot_name] = HelpSystem(bot_name, bot_description, prefix)
    return _help_systems[bot_name]


def get_all_help_systems() -> Dict[str, HelpSystem]:
    """Get all registered help systems"""
    return _help_systems.copy()
