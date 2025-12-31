#!/usr/bin/env python3
"""
Test the Notion extraction with a simple example.
"""

import sys
from pathlib import Path

# Add project root to path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

def test_basic_extraction():
    """Test basic functionality without actual Notion URL."""
    print("=" * 60)
    print("NOTION EXTRACTION TEST")
    print("=" * 60)
    
    # Test 1: Import modules
    print("\n1. Testing imports...")
    try:
        from core.notion_ingest import ingest_notion_page, _ingest_with_api
        print("✓ notion_ingest imported")
    except Exception as e:
        print(f"✗ Failed to import notion_ingest: {e}")
        return 1
    
    try:
        from core.notion_scraper import NotionScraper
        print("✓ notion_scraper imported")
    except Exception as e:
        print(f"✗ Failed to import notion_scraper: {e}")
        return 1
    
    # Test 2: Check Playwright installation
    print("\n2. Testing Playwright...")
    try:
        from playwright.async_api import async_playwright
        print("✓ Playwright imported")
    except Exception as e:
        print(f"✗ Failed to import Playwright: {e}")
        print("  Run: ./venv/bin/pip install playwright")
        print("  Run: ./venv/bin/playwright install chromium")
        return 1
    
    # Test 3: Check MCP configuration
    print("\n3. Testing MCP configuration...")
    mcp_config_path = ROOT / "lifeos" / "config" / "mcp.config.json"
    if mcp_config_path.exists():
        import json
        with open(mcp_config_path) as f:
            config = json.load(f)
        
        notebooklm_found = False
        for server in config.get("servers", []):
            if server.get("name") == "notebooklm":
                notebooklm_found = True
                print("✓ NotebookLM MCP configured")
                print(f"  Command: {' '.join(server.get('args', []))}")
                break
        
        if not notebooklm_found:
            print("✗ NotebookLM MCP not found in config")
            print("  Available servers:", [s.get('name') for s in config.get('servers', [])])
    else:
        print("✗ MCP config file not found at", mcp_config_path)
    
    # Test 4: Test trading compilation
    print("\n4. Testing trading compilation...")
    try:
        from core.trading_notion import compile_notion_strategies
        print("✓ trading_notion imported")
    except Exception as e:
        print(f"✗ Failed to import trading_notion: {e}")
        return 1
    
    # Test 5: Create a mock execution payload
    print("\n5. Testing with mock data...")
    mock_payload = {
        "source": "https://www.notion.so/test",
        "title": "Test Trading Strategies",
        "generated_at": "2025-12-30T00:00:00Z",
        "method": "headless",
        "links": ["https://example.com/resource1"],
        "youtube_links": ["https://youtube.com/watch?v=test123"],
        "youtube_summaries": {
            "test123": {
                "url": "https://youtube.com/watch?v=test123",
                "summary": "Test video about trading strategies",
                "key_points": ["Use stop loss", "Diversify portfolio"]
            }
        },
        "code_blocks": [
            {"language": "python", "code": "def test_strategy(): pass"}
        ],
        "action_items": [
            "Test the RSI strategy",
            "Implement backtest"
        ],
        "sections": {
            "Overview": ["Trading strategy overview"],
            "Strategies": ["RSI strategy", "MACD strategy"]
        },
        "resources": []
    }
    
    # Save mock payload
    exec_dir = ROOT / "data" / "trader" / "notion"
    exec_dir.mkdir(parents=True, exist_ok=True)
    mock_path = exec_dir / "mock_execution.json"
    
    import json
    with open(mock_path, 'w') as f:
        json.dump(mock_payload, f, indent=2)
    
    print(f"✓ Mock payload saved: {mock_path}")
    
    # Test compilation
    try:
        result = compile_notion_strategies(str(mock_path))
        if result.get("error"):
            print(f"✗ Compilation failed: {result['error']}")
        else:
            print(f"✓ Compilation successful!")
            strategies = result.get('strategies_added', 0)
            if isinstance(strategies, list):
                strategies_count = len(strategies)
            else:
                strategies_count = strategies
            print(f"  Strategies: {strategies_count}")
            print(f"  Actions: {result.get('actions', 0)}")
    except Exception as e:
        print(f"✗ Compilation error: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 60)
    print("TEST COMPLETE")
    print("=" * 60)
    print("\nTo run full extraction:")
    print("1. Get a Notion page URL")
    print("2. Run: PYTHONPATH=/Users/burritoaccount/Desktop/LifeOS ./venv/bin/python core/cli.py trading-notion ingest --url <URL> --headless --notebooklm")
    print("3. Then: PYTHONPATH=/Users/burritoaccount/Desktop/LifeOS ./venv/bin/python core/cli.py trading-notion compile")
    
    return 0


if __name__ == "__main__":
    sys.exit(test_basic_extraction())
