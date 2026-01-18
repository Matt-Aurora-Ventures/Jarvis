#!/usr/bin/env python3
"""
Feature Flags Management CLI.

Commands:
    python scripts/manage_flags.py list              - Show all flags
    python scripts/manage_flags.py enable FLAG_NAME  - Enable flag
    python scripts/manage_flags.py disable FLAG_NAME - Disable flag
    python scripts/manage_flags.py set FLAG_NAME PERCENTAGE 50  - Set rollout %
    python scripts/manage_flags.py status            - Show current status
    python scripts/manage_flags.py get FLAG_NAME     - Get flag details

Examples:
    python scripts/manage_flags.py list
    python scripts/manage_flags.py enable DEXTER_REACT_ENABLED
    python scripts/manage_flags.py disable ADVANCED_STRATEGIES_ENABLED
    python scripts/manage_flags.py set ON_CHAIN_ANALYSIS_ENABLED PERCENTAGE 25
    python scripts/manage_flags.py status
"""

import argparse
import json
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.config.feature_flags import get_feature_flag_manager, _reset_manager


def cmd_list(args):
    """List all feature flags."""
    manager = get_feature_flag_manager()
    flags = manager.get_all_flags()

    if not flags:
        print("No feature flags configured.")
        return

    print(f"\n{'='*60}")
    print(f"{'FEATURE FLAGS':^60}")
    print(f"{'='*60}\n")

    for name, config in sorted(flags.items()):
        status = "ON" if config.get("enabled") else "OFF"
        percentage = config.get("rollout_percentage", 0)
        description = config.get("description", "")[:40]

        # Check time constraints
        start = config.get("start_date", "")
        end = config.get("end_date", "")
        time_info = ""
        if start or end:
            time_info = f" [{start or '...'} - {end or '...'}]"

        print(f"  {name}")
        print(f"    Status: {status}")
        if percentage > 0:
            print(f"    Rollout: {percentage}%")
        if time_info:
            print(f"    Active: {time_info}")
        print(f"    Desc: {description}")
        print()

    print(f"Total: {len(flags)} flags")


def cmd_enable(args):
    """Enable a feature flag."""
    manager = get_feature_flag_manager()
    flag = manager.get_flag(args.flag_name)

    if flag is None:
        print(f"Error: Flag '{args.flag_name}' not found.")
        print("Use 'list' command to see available flags.")
        sys.exit(1)

    manager.set_flag(args.flag_name, enabled=True)
    print(f"Enabled flag: {args.flag_name}")


def cmd_disable(args):
    """Disable a feature flag."""
    manager = get_feature_flag_manager()
    flag = manager.get_flag(args.flag_name)

    if flag is None:
        print(f"Error: Flag '{args.flag_name}' not found.")
        print("Use 'list' command to see available flags.")
        sys.exit(1)

    manager.set_flag(args.flag_name, enabled=False)
    print(f"Disabled flag: {args.flag_name}")


def cmd_set(args):
    """Set flag properties."""
    manager = get_feature_flag_manager()
    flag = manager.get_flag(args.flag_name)

    if flag is None:
        print(f"Error: Flag '{args.flag_name}' not found.")
        sys.exit(1)

    if args.property_name.upper() == "PERCENTAGE":
        try:
            percentage = int(args.value)
            if not 0 <= percentage <= 100:
                raise ValueError("Percentage must be 0-100")
        except ValueError as e:
            print(f"Error: Invalid percentage value: {e}")
            sys.exit(1)

        manager.set_flag(args.flag_name, enabled=True, percentage=percentage)
        print(f"Set {args.flag_name} rollout to {percentage}%")
    else:
        print(f"Error: Unknown property '{args.property_name}'")
        print("Supported properties: PERCENTAGE")
        sys.exit(1)


def cmd_status(args):
    """Show overall feature flags status."""
    manager = get_feature_flag_manager()
    flags = manager.get_all_flags()
    enabled = manager.get_enabled_flags()

    print(f"\n{'='*40}")
    print(f"{'FEATURE FLAGS STATUS':^40}")
    print(f"{'='*40}\n")

    print(f"Total flags: {len(flags)}")
    print(f"Enabled: {len(enabled)}")
    print(f"Disabled: {len(flags) - len(enabled)}")

    print("\nEnabled flags:")
    for name in sorted(enabled):
        print(f"  - {name}")

    print("\nDisabled flags:")
    for name in sorted(flags.keys()):
        if name not in enabled:
            print(f"  - {name}")


def cmd_get(args):
    """Get detailed information about a flag."""
    manager = get_feature_flag_manager()
    flag = manager.get_flag(args.flag_name)

    if flag is None:
        print(f"Error: Flag '{args.flag_name}' not found.")
        sys.exit(1)

    print(f"\n{'='*40}")
    print(f"Flag: {args.flag_name}")
    print(f"{'='*40}\n")

    config = flag.to_dict()
    for key, value in config.items():
        print(f"  {key}: {value}")

    # Show effective state
    print(f"\n  Effective state (is_enabled): {manager.is_enabled(args.flag_name)}")


def main():
    parser = argparse.ArgumentParser(
        description="Manage Jarvis feature flags",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # list command
    list_parser = subparsers.add_parser("list", help="List all feature flags")
    list_parser.set_defaults(func=cmd_list)

    # enable command
    enable_parser = subparsers.add_parser("enable", help="Enable a feature flag")
    enable_parser.add_argument("flag_name", help="Name of the flag to enable")
    enable_parser.set_defaults(func=cmd_enable)

    # disable command
    disable_parser = subparsers.add_parser("disable", help="Disable a feature flag")
    disable_parser.add_argument("flag_name", help="Name of the flag to disable")
    disable_parser.set_defaults(func=cmd_disable)

    # set command
    set_parser = subparsers.add_parser("set", help="Set flag properties")
    set_parser.add_argument("flag_name", help="Name of the flag")
    set_parser.add_argument("property_name", help="Property to set (e.g., PERCENTAGE)")
    set_parser.add_argument("value", help="Value to set")
    set_parser.set_defaults(func=cmd_set)

    # status command
    status_parser = subparsers.add_parser("status", help="Show feature flags status")
    status_parser.set_defaults(func=cmd_status)

    # get command
    get_parser = subparsers.add_parser("get", help="Get flag details")
    get_parser.add_argument("flag_name", help="Name of the flag")
    get_parser.set_defaults(func=cmd_get)

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(1)

    args.func(args)


if __name__ == "__main__":
    main()
