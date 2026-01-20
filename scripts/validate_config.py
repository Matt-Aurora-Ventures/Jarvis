#!/usr/bin/env python3
"""
Configuration Validation Script.

Run this before starting Jarvis to validate all environment variables
and configuration settings.

Usage:
    python scripts/validate_config.py              # Non-strict, show all issues
    python scripts/validate_config.py --strict     # Strict, exit on errors
    python scripts/validate_config.py --fix-hints  # Show how to fix issues
"""

import sys
import os
from pathlib import Path

# Fix Windows encoding for emoji support
if sys.platform == "win32":
    for stream in [sys.stdout, sys.stderr]:
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8', errors='replace')

# Add project root to path
project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))

from core.config.validator import (
    validate_config,
    print_validation_summary,
    ConfigValidationError,
    ValidationLevel,
    get_validator,
)


def print_fix_hints(validator):
    """Print hints on how to fix missing/invalid config."""
    print("\n" + "=" * 70)
    print("HOW TO FIX CONFIGURATION ISSUES")
    print("=" * 70 + "\n")

    print("1. Create/edit .env file in project root:")
    print("   cp .env.example .env")
    print("   nano .env  # or your preferred editor\n")

    print("2. Required environment variables:\n")

    required_vars = {
        "TELEGRAM_BOT_TOKEN": "Get from @BotFather on Telegram",
        "TELEGRAM_ADMIN_IDS": "Your Telegram user ID (comma-separated)",
    }

    for key, hint in required_vars.items():
        value = os.environ.get(key)
        if value:
            print(f"   ✓ {key:30s} [SET]")
        else:
            print(f"   ✗ {key:30s} [MISSING] - {hint}")

    print("\n3. Optional but recommended:\n")

    optional_vars = {
        "XAI_API_KEY": "For Grok sentiment analysis",
        "ANTHROPIC_API_KEY": "For Claude integration",
        "SOLANA_RPC_URL": "Solana RPC endpoint (default: public mainnet)",
        "TREASURY_WALLET_PATH": "Path to wallet keypair JSON",
        "JARVIS_WALLET_PASSWORD": "Wallet encryption password",
    }

    for key, hint in optional_vars.items():
        value = os.environ.get(key)
        if value:
            print(f"   ✓ {key:30s} [SET]")
        else:
            print(f"   - {key:30s} [NOT SET] - {hint}")

    print("\n4. Security recommendations:\n")
    print("   • Use TREASURY_WALLET_PATH (keypair file) instead of WALLET_PRIVATE_KEY")
    print("   • Set strong JARVIS_WALLET_PASSWORD (12+ chars, mixed case, digits)")
    print("   • Never commit .env file to git (already in .gitignore)")
    print("   • Test with TREASURY_LIVE_MODE=false before enabling live trading")

    print("\n5. Check configuration groups:\n")

    groups = validator.get_group_summary()
    for group, stats in sorted(groups.items()):
        configured_pct = (stats["configured"] / stats["total"] * 100) if stats["total"] > 0 else 0
        status = "✓" if configured_pct > 50 else "⚠" if configured_pct > 0 else "✗"
        print(f"   {status} {group:15s}: {stats['configured']}/{stats['total']} configured ({configured_pct:.0f}%)")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Validate Jarvis configuration")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit with error code if validation fails (for CI/CD)"
    )
    parser.add_argument(
        "--fix-hints",
        action="store_true",
        help="Show hints on how to fix configuration issues"
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Only print errors/warnings, not full summary"
    )

    args = parser.parse_args()

    print("=" * 70)
    print("JARVIS CONFIGURATION VALIDATOR")
    print("=" * 70 + "\n")

    validator = get_validator()

    try:
        is_valid, results = validate_config(strict=args.strict)

        if not args.quiet:
            print_validation_summary()
            print()

        # Print errors/warnings
        errors = [r for r in results if r.level == ValidationLevel.ERROR]
        warnings = [r for r in results if r.level == ValidationLevel.WARNING]

        if errors:
            print(f"\n❌ Found {len(errors)} critical error(s)")
            if args.strict:
                print("   Strict mode: Cannot start Jarvis with errors\n")

        if warnings:
            print(f"⚠️  Found {len(warnings)} warning(s)")
            print("   Jarvis may have limited functionality\n")

        if not errors and not warnings:
            print("✅ Configuration looks good!\n")

        # Show fix hints if requested or if there are errors
        if args.fix_hints or (errors and not args.quiet):
            print_fix_hints(validator)

        # Exit code
        if args.strict:
            sys.exit(0 if is_valid else 1)
        else:
            # In non-strict mode, exit 0 even with warnings
            sys.exit(0 if not errors else 1)

    except ConfigValidationError as e:
        print(f"\n❌ CONFIGURATION VALIDATION FAILED\n")
        print(str(e))
        print()

        if args.fix_hints:
            print_fix_hints(validator)

        sys.exit(1)

    except Exception as e:
        print(f"\n❌ UNEXPECTED ERROR: {e}\n")
        import traceback
        traceback.print_exc()
        sys.exit(2)


if __name__ == "__main__":
    main()
