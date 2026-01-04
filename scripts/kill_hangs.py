#!/usr/bin/env python3
"""
LifeOS Process Monitor - Check for and kill hanging processes.
Usage:
    python scripts/kill_hangs.py             # Check for hangs (dry run)
    python scripts/kill_hangs.py --kill       # Kill hanging processes
    python scripts/kill_hangs.py --emergency  # Nuclear option: kill ALL child processes
"""

import argparse
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.emergency_kill import (
    kill_hanging_processes,
    force_kill_by_pattern,
    emergency_reset
)


def main():
    parser = argparse.ArgumentParser(description="Monitor and kill hanging LifeOS processes")
    parser.add_argument("--kill", action="store_true", help="Actually kill hanging processes")
    parser.add_argument("--emergency", action="store_true", help="Emergency: kill ALL child processes")
    parser.add_argument("--pattern", type=str, help="Kill processes matching pattern")
    
    args = parser.parse_args()
    
    if args.emergency:
        confirm = input("⚠️  EMERGENCY RESET: This will kill ALL child processes. Continue? (yes/no): ")
        if confirm.lower() == "yes":
            emergency_reset()
        else:
            print("Cancelled")
        return
    
    if args.pattern:
        print(f"Searching for processes matching '{args.pattern}'...")
        result = force_kill_by_pattern(args.pattern, dry_run=not args.kill)
    else:
        print("Checking for hanging processes (> 5 minutes old)...")
        result = kill_hanging_processes(dry_run=not args.kill)
    
    print("\n" + "=" * 60)
    print(f"Found {len(result['found'])} hanging process(es)")
    print("=" * 60)
    
    if result["found"]:
        for proc in result["found"]:
            print(f"  {proc}")
        
        if result["dry_run"]:
            print("\n💡 Run with --kill to terminate these processes")
        else:
            print(f"\n✅ Killed {len(result['killed'])} process(es)")
            for kill_msg in result["killed"]:
                print(f"  {kill_msg}")
    else:
        print("✅ No hanging processes found")


if __name__ == "__main__":
    main()
