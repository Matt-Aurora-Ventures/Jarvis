#!/usr/bin/env python3
"""
Cache Management CLI

Manage API response caches with commands:
- stats: Show cache hit rate, size, and breakdown
- clear: Clear all caches
- invalidate: Invalidate specific API cache
- ttl: Adjust TTL for specific API
- info: Detailed cache information

Usage:
    python scripts/cache_management.py stats
    python scripts/cache_management.py clear
    python scripts/cache_management.py invalidate jupiter
    python scripts/cache_management.py ttl jupiter 600
    python scripts/cache_management.py info
"""

import argparse
import json
import sys
from pathlib import Path
from datetime import datetime

# Add project root to path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.cache.api_cache import get_api_cache, DEFAULT_TTLS


def cmd_stats(args):
    """Show cache statistics."""
    cache = get_api_cache()
    stats = cache.get_stats()

    print("\n" + "=" * 60)
    print("                   CACHE STATISTICS")
    print("=" * 60)

    # Overall stats
    print(f"\n  Total Hits:     {stats['total_hits']:,}")
    print(f"  Total Misses:   {stats['total_misses']:,}")
    print(f"  Total Entries:  {stats['total_entries']:,}")
    print(f"  Hit Rate:       {stats['hit_rate']:.1%}")
    print(f"  Max Size:       {stats['max_size']:,}")

    # Per-API breakdown
    print("\n" + "-" * 60)
    print("  Per-API Breakdown")
    print("-" * 60)
    print(f"  {'API':<15} {'Hits':>8} {'Misses':>8} {'Entries':>8} {'Rate':>8} {'TTL':>8}")
    print(f"  {'-'*15} {'-'*8} {'-'*8} {'-'*8} {'-'*8} {'-'*8}")

    for api_name, api_stats in sorted(stats['by_api'].items()):
        if api_stats['hits'] > 0 or api_stats['misses'] > 0 or api_stats['entries'] > 0:
            rate_str = f"{api_stats['hit_rate']:.0%}"
            ttl_str = f"{api_stats['ttl_seconds']}s"
            print(f"  {api_name:<15} {api_stats['hits']:>8,} {api_stats['misses']:>8,} "
                  f"{api_stats['entries']:>8,} {rate_str:>8} {ttl_str:>8}")

    print("\n" + "=" * 60)

    if args.json:
        print("\nJSON Output:")
        print(cache.export_stats_json())


def cmd_clear(args):
    """Clear all caches."""
    cache = get_api_cache()

    if not args.yes:
        confirm = input("Are you sure you want to clear ALL caches? [y/N] ")
        if confirm.lower() != 'y':
            print("Aborted.")
            return

    count = cache.clear_all()
    print(f"\nCleared {count:,} cache entries.")


def cmd_invalidate(args):
    """Invalidate specific API cache."""
    cache = get_api_cache()
    api_name = args.api_name.lower()

    if api_name not in DEFAULT_TTLS:
        print(f"Warning: '{api_name}' is not a known API. Known APIs:")
        for name in sorted(DEFAULT_TTLS.keys()):
            print(f"  - {name}")

    count = cache.invalidate_api(api_name)
    print(f"\nInvalidated {count:,} entries for '{api_name}'.")


def cmd_ttl(args):
    """Adjust TTL for specific API."""
    cache = get_api_cache()
    api_name = args.api_name.lower()
    ttl_seconds = args.seconds

    old_ttl = cache.get_ttl(api_name)
    cache.set_ttl(api_name, ttl_seconds)

    print(f"\nTTL for '{api_name}' changed:")
    print(f"  Old: {old_ttl}s ({old_ttl // 60}m)")
    print(f"  New: {ttl_seconds}s ({ttl_seconds // 60}m)")
    print("\nNote: This affects new cache entries only.")


def cmd_info(args):
    """Show detailed cache information."""
    cache = get_api_cache()
    info = cache.get_info()

    print("\n" + "=" * 60)
    print("                   CACHE INFORMATION")
    print("=" * 60)

    print(f"\n  Total Entries:    {info['total_entries']:,}")
    print(f"  Memory Usage:     {info['memory_usage_bytes']:,} bytes ({info['memory_usage_bytes'] / 1024:.1f} KB)")
    print(f"  Max Size:         {info['max_size']:,}")

    print("\n" + "-" * 60)
    print("  API Details")
    print("-" * 60)

    for api_name, api_info in sorted(info['apis'].items()):
        if api_info['entries'] > 0:
            print(f"\n  {api_name.upper()}")
            print(f"    Entries:      {api_info['entries']:,}")
            print(f"    TTL:          {api_info['ttl_seconds']}s ({api_info['ttl_seconds'] // 60}m)")
            if api_info['oldest_entry_age'] is not None:
                print(f"    Oldest:       {api_info['oldest_entry_age']:.1f}s ago")
            if api_info['newest_entry_age'] is not None:
                print(f"    Newest:       {api_info['newest_entry_age']:.1f}s ago")

    # Default TTLs reference
    print("\n" + "-" * 60)
    print("  Default TTLs")
    print("-" * 60)
    for api_name, ttl in sorted(DEFAULT_TTLS.items()):
        if api_name != "default":
            print(f"    {api_name:<15} {ttl:>6}s  ({ttl // 60}m)")

    print("\n" + "=" * 60)

    if args.json:
        print("\nJSON Output:")
        print(json.dumps(info, indent=2))


def cmd_export(args):
    """Export cache statistics to file."""
    cache = get_api_cache()
    stats = cache.get_stats()

    output = {
        "timestamp": datetime.now().isoformat(),
        "stats": stats,
        "info": cache.get_info()
    }

    output_path = Path(args.output)
    with open(output_path, 'w') as f:
        json.dump(output, f, indent=2)

    print(f"\nExported cache data to: {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Manage API response caches",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s stats             Show cache statistics
  %(prog)s stats --json      Show stats with JSON output
  %(prog)s clear             Clear all caches (with confirmation)
  %(prog)s clear -y          Clear all caches (no confirmation)
  %(prog)s invalidate jupiter    Clear Jupiter cache
  %(prog)s ttl jupiter 600       Set Jupiter TTL to 10 minutes
  %(prog)s info              Show detailed cache information
  %(prog)s export cache.json Export stats to file
        """
    )

    subparsers = parser.add_subparsers(dest='command', help='Available commands')

    # stats command
    stats_parser = subparsers.add_parser('stats', help='Show cache statistics')
    stats_parser.add_argument('--json', action='store_true', help='Include JSON output')
    stats_parser.set_defaults(func=cmd_stats)

    # clear command
    clear_parser = subparsers.add_parser('clear', help='Clear all caches')
    clear_parser.add_argument('-y', '--yes', action='store_true', help='Skip confirmation')
    clear_parser.set_defaults(func=cmd_clear)

    # invalidate command
    inv_parser = subparsers.add_parser('invalidate', help='Invalidate specific API cache')
    inv_parser.add_argument('api_name', help='API name (jupiter, solscan, coingecko, grok, etc.)')
    inv_parser.set_defaults(func=cmd_invalidate)

    # ttl command
    ttl_parser = subparsers.add_parser('ttl', help='Adjust TTL for specific API')
    ttl_parser.add_argument('api_name', help='API name')
    ttl_parser.add_argument('seconds', type=int, help='TTL in seconds')
    ttl_parser.set_defaults(func=cmd_ttl)

    # info command
    info_parser = subparsers.add_parser('info', help='Show detailed cache information')
    info_parser.add_argument('--json', action='store_true', help='Include JSON output')
    info_parser.set_defaults(func=cmd_info)

    # export command
    export_parser = subparsers.add_parser('export', help='Export cache data to file')
    export_parser.add_argument('output', help='Output file path')
    export_parser.set_defaults(func=cmd_export)

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        return

    args.func(args)


if __name__ == "__main__":
    main()
