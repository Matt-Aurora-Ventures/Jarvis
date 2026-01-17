#!/usr/bin/env python3
"""
Full demonstration of Notion strategy extraction pipeline.
"""

import sys
import os
from pathlib import Path

# Add project root to path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

def main():
    """Run full extraction pipeline demonstration."""
    
    print("=" * 70)
    print("NOTION STRATEGY EXTRACTION - FULL PIPELINE DEMONSTRATION")
    print("=" * 70)
    
    # Example public Notion page about trading strategies
    # This is a sample URL - replace with actual target page
    example_url = "https://www.notion.so/Trading-Strategies-Overview-1234567890abcdef"
    
    print("\n📝 This demonstration shows how to:")
    print("   1. Extract full content from a Notion page using headless scraping")
    print("   2. Summarize YouTube videos with NotebookLM")
    print("   3. Compile trading strategies from extracted content")
    print("   4. Feed strategies into the trading engine")
    
    print("\n🔧 Setup verification:")
    
    # Check if all components are ready
    checks = []
    
    # Check Playwright
    try:
        from playwright.async_api import async_playwright
        checks.append("✓ Playwright installed")
    except Exception:
        checks.append("✗ Playwright missing - run: ./venv/bin/pip install playwright")
    
    # Check Chromium
    try:
        from playwright.async_api import async_playwright
        # Quick check if chromium is installed
        import os
        browser_path = Path.home() / "Library/Caches/ms-playwright/chromium-1200"
        if browser_path.exists():
            checks.append("✓ Chromium browser installed")
        else:
            checks.append("✗ Chromium missing - run: ./venv/bin/playwright install chromium")
    except Exception:
        checks.append("✗ Cannot verify Chromium")
    
    # Check MCP config
    mcp_config = ROOT / "lifeos" / "config" / "mcp.config.json"
    if mcp_config.exists():
        checks.append("✓ MCP configuration exists")
    else:
        checks.append("✗ MCP config missing")
    
    # Check trading modules
    try:
        from core.trading_notion import compile_notion_strategies
        checks.append("✓ Trading compilation module ready")
    except Exception:
        checks.append("✗ Trading module error")
    
    for check in checks:
        print(f"   {check}")
    
    print("\n" + "-" * 70)
    print("USAGE EXAMPLES")
    print("-" * 70)
    
    print("\n1️⃣  Extract with API (limited content):")
    print(f"   PYTHONPATH={ROOT} ./venv/bin/python core/cli.py trading-notion ingest --url <URL>")
    
    print("\n2️⃣  Extract with headless scraper (full content):")
    print(f"   PYTHONPATH={ROOT} ./venv/bin/python core/cli.py trading-notion ingest \\")
    print(f"     --url <URL> --headless")
    
    print("\n3️⃣  Extract with YouTube summaries:")
    print(f"   PYTHONPATH={ROOT} ./venv/bin/python core/cli.py trading-notion ingest \\")
    print(f"     --url <URL> --headless --notebooklm")
    
    print("\n4️⃣  Compile strategies:")
    print(f"   PYTHONPATH={ROOT} ./venv/bin/python core/cli.py trading-notion compile")
    
    print("\n5️⃣  Run backtests:")
    print(f"   PYTHONPATH={ROOT} ./venv/bin/python core/cli.py overnight")
    
    print("\n" + "-" * 70)
    print("EXPECTED OUTPUT")
    print("-" * 70)
    
    print("\n📊 After extraction, you'll see:")
    print("   - Title and metadata")
    print("   - Number of links found")
    print("   - YouTube videos discovered")
    print("   - Code blocks extracted")
    print("   - Action items identified")
    print("   - Resources crawled")
    
    print("\n📈 After compilation, you'll get:")
    print("   - Trading strategies generated")
    print("   - Strategy shortlist")
    print("   - Action items for implementation")
    print("   - Files saved to data/trader/notion/")
    
    print("\n" + "-" * 70)
    print("FILE LOCATIONS")
    print("-" * 70)
    
    print("\n📁 Extracted data saved to:")
    print(f"   - Raw JSON: {ROOT}/data/notion/<page_id>.json")
    print(f"   - Markdown: {ROOT}/lifeos/notes/notion_*.md")
    print(f"   - Exec payload: {ROOT}/data/trader/notion/notion_execution_base.json")
    
    print("\n📁 Compiled strategies:")
    print(f"   - Strategies: {ROOT}/data/trader/notion/notion_strategies.json")
    print(f"   - Actions: {ROOT}/data/trader/notion/notion_actions.json")
    print(f"   - Final: {ROOT}/data/trader/strategies.json")
    
    print("\n" + "=" * 70)
    print("READY TO RUN!")
    print("=" * 70)
    
    print("\nTo start extraction:")
    print("1. Replace the example URL with your target Notion page")
    print("2. Run the ingest command with --headless --notebooklm flags")
    print("3. Compile strategies with the compile command")
    print("4. Check the generated files and run backtests")
    
    print("\n🚀 Happy extracting!")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
