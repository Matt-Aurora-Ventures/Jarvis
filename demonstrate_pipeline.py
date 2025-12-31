#!/usr/bin/env python3
"""
Demonstrate feeding extracted Notion data into trading pipeline.
"""

import sys
import json
from pathlib import Path

# Add project root to path
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from core.trading_notion import compile_notion_strategies, _seed_trader_strategies


def demonstrate_pipeline():
    """Show how extracted Notion data flows into trading strategies."""
    
    print("=" * 60)
    print("NOTION STRATEGY EXTRACTION & TRADING PIPELINE DEMO")
    print("=" * 60)
    
    # 1. Check for existing execution payload
    exec_path = ROOT / "data" / "trader" / "notion" / "notion_headless_execution_base.json"
    
    if not exec_path.exists():
        print("❌ No execution payload found.")
        print("Run: ./venv/bin/python core/cli.py trading-notion ingest --headless --notebooklm")
        return 1
    
    print(f"\n📁 Loading execution payload: {exec_path}")
    with open(exec_path, 'r') as f:
        payload = json.load(f)
    
    print(f"✅ Loaded payload from: {payload.get('title', 'Unknown')}")
    print(f"   - Links: {len(payload.get('links', []))}")
    print(f"   - YouTube videos: {len(payload.get('youtube_links', []))}")
    print(f"   - Action items: {len(payload.get('action_items', []))}")
    print(f"   - Resources: {len(payload.get('resources', []))}")
    
    # 2. Compile strategies
    print("\n🔄 Compiling strategies from extracted data...")
    compile_result = compile_notion_strategies(str(exec_path))
    
    if compile_result.get("error"):
        print(f"❌ Compilation failed: {compile_result['error']}")
        return 1
    
    print("✅ Strategies compiled successfully!")
    strategies = compile_result.get('strategies_added', 0)
    if isinstance(strategies, list):
        strategies_count = len(strategies)
    else:
        strategies_count = strategies
    print(f"   - Strategies generated: {strategies_count}")
    actions = compile_result.get('actions', 0)
    if isinstance(actions, list):
        actions_count = len(actions)
    else:
        actions_count = actions
    print(f"   - Action items: {actions_count}")
    shortlist = compile_result.get('shortlist', 0)
    if isinstance(shortlist, list):
        shortlist_count = len(shortlist)
    else:
        shortlist_count = shortlist
    print(f"   - Shortlist items: {shortlist_count}")
    
    # 3. Show example strategies
    strategies = compile_result.get('strategies', [])
    if strategies:
        print("\n📊 Example Trading Strategies:")
        for i, strategy in enumerate(strategies[:3], 1):
            print(f"\n{i}. {strategy.get('name', 'Unnamed')}")
            print(f"   Type: {strategy.get('type', 'Unknown')}")
            print(f"   Description: {strategy.get('description', '')[:100]}...")
            print(f"   Confidence: {strategy.get('confidence', 0):.1%}")
    
    # 4. Seed into trading engine
    print("\n🚀 Seeding strategies into trading engine...")
    seed_result = _seed_trader_strategies(strategies)
    
    if seed_result is None:
        print("ℹ️  Strategies already exist in trading engine (no new ones to add)")
    elif seed_result.get("error"):
        print(f"❌ Seeding failed: {seed_result['error']}")
    else:
        print("✅ Strategies seeded into trading engine!")
        print(f"   - Strategies added: {seed_result.get('strategies_added', 0)}")
        print(f"   - Strategies file: {seed_result.get('strategies_path')}")
    
    # 5. Show final strategies.json location
    strategies_path = ROOT / "data" / "trader" / "strategies.json"
    if strategies_path.exists():
        print(f"\n📈 Final strategies ready for backtesting:")
        print(f"   File: {strategies_path}")
        
        with open(strategies_path, 'r') as f:
            final_strategies = json.load(f)
        
        print(f"   Total strategies: {len(final_strategies)}")
        
        # Show categories
        categories = {}
        for s in final_strategies:
            if isinstance(s, dict):
                cat = s.get('type', 'Unknown')
            else:
                cat = 'Unknown'
            categories[cat] = categories.get(cat, 0) + 1
        
        print("   By category:")
        for cat, count in categories.items():
            print(f"     - {cat}: {count}")
    
    print("\n" + "=" * 60)
    print("PIPELINE COMPLETE! Ready for backtesting.")
    print("=" * 60)
    print("\nNext steps:")
    print("1. Run backtests: ./venv/bin/python core/cli.py overnight")
    print("2. Check results: ./venv/bin/python core/cli.py report --daily")
    print("3. Monitor live trading: ./venv/bin/python core/cli.py status")
    
    return 0


if __name__ == "__main__":
    sys.exit(demonstrate_pipeline())
