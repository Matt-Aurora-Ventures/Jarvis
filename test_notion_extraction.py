#!/usr/bin/env python3
"""
Test script for Notion strategy extraction with headless scraper and NotebookLM.
"""

import sys
import os
from pathlib import Path

# Add project root to path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.notion_ingest import ingest_notion_page


def main():
    """Test the Notion extraction with headless scraper."""
    # Example Notion URL - replace with actual URL
    notion_url = "https://www.notion.so/your-trading-strategies-page"
    
    if len(sys.argv) > 1:
        notion_url = sys.argv[1]
    
    print(f"Extracting Notion page: {notion_url}")
    print("\nUsing headless scraper with full content expansion...")
    
    # Extract with headless scraper and NotebookLM
    result = ingest_notion_page(
        notion_url,
        use_headless=True,
        notebooklm_summary=True,
        crawl_links=True,
        max_links=50,
        crawl_depth=1,
    )
    
    if "error" in result:
        print(f"Error: {result['error']}")
        return 1
    
    print("\n✅ Extraction completed!")
    print(f"Title: {result.get('title', 'Untitled')}")
    print(f"Method: {result.get('method', 'unknown')}")
    print(f"Links found: {result.get('links', 0)}")
    print(f"YouTube videos: {result.get('youtube_links', 0)}")
    print(f"YouTube summaries: {result.get('youtube_summaries', 0)}")
    print(f"Action items: {result.get('action_items', 0)}")
    print(f"Resources crawled: {result.get('resources', 0)}")
    
    print("\n📁 Files saved:")
    print(f"  Note: {result.get('note_path')}")
    print(f"  Raw data: {result.get('raw_path')}")
    print(f"  Exec payload: {result.get('exec_path')}")
    
    if result.get('scraped_files'):
        print("  Scraped files:")
        for key, path in result['scraped_files'].items():
            if path:
                print(f"    {key}: {path}")
    
    # Next step: feed into trading_notion compilation
    print("\n🔄 Next step: Feeding extracted data into trading_notion compilation...")
    
    # Import and run trading compilation
    try:
        from core.trading_notion import compile_notion_strategies
        
        # Load the execution payload
        exec_path = result.get('exec_path')
        if exec_path and Path(exec_path).exists():
            compile_result = compile_notion_strategies(exec_path)
            print("\n✅ Trading strategies compiled!")
            print(f"Strategies generated: {len(compile_result.get('strategies', []))}")
            
            # Show first strategy as example
            strategies = compile_result.get('strategies', [])
            if strategies:
                print("\n📊 Example strategy:")
                strategy = strategies[0]
                print(f"  Name: {strategy.get('name', 'Unnamed')}")
                print(f"  Type: {strategy.get('type', 'Unknown')}")
                print(f"  Description: {strategy.get('description', '')[:100]}...")
        
    except Exception as e:
        print(f"\n⚠️  Trading compilation failed: {e}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
